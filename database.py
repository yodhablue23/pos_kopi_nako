"""Lapisan akses database POS Kopi Nako.

File ini bertanggung jawab mengelola seluruh operasi database (CRUD: Create, Read, Update, Delete).
Mendukung dua engine secara mulus:
1. SQLite: Menggunakan pustaka standar Python (sqlite3), tanpa perlu XAMPP.
2. MySQL: Menggunakan mysql.connector jika diaktifkan di db_config.py.
"""
from datetime import datetime
import hashlib
import hmac
import secrets
import sqlite3
import unicodedata

from db_config import DB_ENGINE, SQLITE_DB_PATH, MYSQL_CONFIG
from config import SEED_PRODUCTS

# Batas stok maksimum untuk setiap produk.
MAX_PRODUCT_STOCK = 100
MAX_PRODUCT_NAME_LENGTH = 80
MAX_CUSTOMER_LABEL_LENGTH = 40
_PRODUCT_NAME_PUNCTUATION = frozenset("&+-/().,'")
_CUSTOMER_LABEL_PUNCTUATION = frozenset("#-/.,'")


def normalize_product_name(name):
    """Membersihkan dan memvalidasi nama produk untuk katalog POS."""
    if name is None:
        raise ValueError("Nama produk wajib diisi.")

    name = unicodedata.normalize("NFC", str(name))
    if any(
        unicodedata.category(char).startswith("C")
        or unicodedata.category(char) in ("Zl", "Zp")
        for char in name
    ):
        raise ValueError("Nama produk tidak boleh mengandung karakter kontrol atau baris baru.")

    name = " ".join(name.split())
    if not name:
        raise ValueError("Nama produk wajib diisi.")
    if len(name) > MAX_PRODUCT_NAME_LENGTH:
        raise ValueError(
            f"Nama produk maksimal {MAX_PRODUCT_NAME_LENGTH} karakter."
        )

    has_alphanumeric = False
    for char in name:
        category = unicodedata.category(char)
        if char.isspace() or category.startswith("M"):
            continue
        if category.startswith(("L", "N")):
            has_alphanumeric = True
            continue
        if char not in _PRODUCT_NAME_PUNCTUATION:
            raise ValueError(
                "Nama produk hanya boleh berisi huruf, angka, spasi, "
                "dan tanda baca umum."
            )

    if not has_alphanumeric:
        raise ValueError("Nama produk harus mengandung huruf atau angka.")
    return name


def normalize_customer_label(value):
    """Membersihkan dan memvalidasi nama pelanggan atau nomor meja untuk struk."""
    if value is None:
        return ""

    label = unicodedata.normalize("NFC", str(value))
    if any(unicodedata.category(char).startswith("C") for char in label):
        raise ValueError("Nama pelanggan/no. meja tidak boleh berisi karakter kontrol.")

    label = " ".join(label.split())
    if not label:
        return ""
    if len(label) > MAX_CUSTOMER_LABEL_LENGTH:
        raise ValueError(
            f"Nama pelanggan/no. meja maksimal "
            f"{MAX_CUSTOMER_LABEL_LENGTH} karakter."
        )

    has_alphanumeric = False
    for char in label:
        category = unicodedata.category(char)
        if char.isspace() or category.startswith("M"):
            continue
        if category.startswith(("L", "N")):
            has_alphanumeric = True
            continue
        if char not in _CUSTOMER_LABEL_PUNCTUATION:
            raise ValueError(
                "Nama pelanggan/no. meja hanya boleh berisi huruf, angka, "
                "spasi, dan tanda baca umum (# - / . , ')."
            )

    if not has_alphanumeric:
        raise ValueError("Nama pelanggan/no. meja harus berisi huruf atau angka.")
    return label


# Coba impor mysql.connector jika tersedia di sistem
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    MySQLError = Exception


class Database:
    """Pengelola koneksi dan operasi database POS Kopi Nako."""

    def __init__(self):
        # Tentukan engine database yang aktif
        if DB_ENGINE == "mysql" and MYSQL_AVAILABLE:
            self.engine = "mysql"
        else:
            self.engine = "sqlite"

    def connect(self):
        """Membuka koneksi baru ke database yang sedang aktif."""
        if self.engine == "sqlite":
            # sqlite3.Row memungkinkan akses data menggunakan nama kolom, contoh: row['nama']
            conn = sqlite3.connect(str(SQLITE_DB_PATH))
            conn.row_factory = sqlite3.Row
            return conn
        else:
            return mysql.connector.connect(**MYSQL_CONFIG)

    def _prepare_sql(self, sql):
        """Menyesuaikan tanda parameter SQL.
        
        SQLite menggunakan tanda tanya (?), sedangkan MySQL menggunakan (%s).
        """
        if self.engine == "sqlite":
            return sql.replace("%s", "?")
        return sql

    def initialize(self):
        """Membuat tabel-tabel utama dan mengisi data awal jika masih kosong.
        
        Tabel yang dibuat:
        1. akun: Menyimpan data pengguna kasir/admin dengan password yang di-hash.
        2. produk: Menyimpan daftar menu, kategori, harga, dan sisa stok barang.
        3. transaksi: Menyimpan nota penjualan (tanggal, total belanja, metode pembayaran, bayar, kembalian).
        4. detail_transaksi: Menyimpan rincian item barang yang dibeli per transaksi.
        """
        conn = self.connect()
        try:
            cur = conn.cursor()

            # 1. Pembuatan Tabel Akun (Pengguna & Kasir)
            if self.engine == "sqlite":
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS akun (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL UNIQUE,
                        nama TEXT NOT NULL DEFAULT 'Kasir',
                        role TEXT NOT NULL DEFAULT 'kasir',
                        password_hash TEXT NOT NULL,
                        dibuat_pada TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )"""
                )
            else:
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS akun (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(50) NOT NULL UNIQUE,
                        nama VARCHAR(100) NOT NULL DEFAULT 'Kasir',
                        role VARCHAR(20) NOT NULL DEFAULT 'kasir',
                        password_hash VARCHAR(255) NOT NULL,
                        dibuat_pada DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )"""
                )

            # 2. Pembuatan Tabel Produk
            if self.engine == "sqlite":
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS produk (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nama TEXT NOT NULL,
                        kategori TEXT NOT NULL,
                        harga REAL NOT NULL,
                        stok INTEGER NOT NULL,
                        image_path TEXT,
                        aktif INTEGER NOT NULL DEFAULT 1
                    )"""
                )
            else:
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS produk (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        nama VARCHAR(100) NOT NULL,
                        kategori VARCHAR(50) NOT NULL,
                        harga DECIMAL(10,2) NOT NULL,
                        stok INT NOT NULL,
                        image_path VARCHAR(500) NULL,
                        aktif TINYINT(1) NOT NULL DEFAULT 1
                    )"""
                )

            # Migrasi tabel produk lama agar mendukung foto produk.
            if self.engine == "sqlite":
                try:
                    cur.execute("ALTER TABLE produk ADD COLUMN image_path TEXT")
                except sqlite3.OperationalError as error:
                    if "duplicate column" not in str(error).lower():
                        raise
            else:
                try:
                    cur.execute("ALTER TABLE produk ADD COLUMN image_path VARCHAR(500) NULL")
                except MySQLError as error:
                    # MySQL error 1060 berarti kolom sudah tersedia.
                    if getattr(error, "errno", None) != 1060:
                        raise

            # Migrasi aman: tandai produk aktif/nonaktif untuk penghapusan yang aman.
            # Produk nonaktif disembunyikan dari katalog, tetapi tetap tersedia untuk
            # JOIN detail transaksi sehingga nota dan laporan lama tidak rusak.
            if self.engine == "sqlite":
                try:
                    cur.execute(
                        "ALTER TABLE produk ADD COLUMN aktif INTEGER NOT NULL DEFAULT 1"
                    )
                except sqlite3.OperationalError as error:
                    if "duplicate column" not in str(error).lower():
                        raise
            else:
                try:
                    cur.execute(
                        "ALTER TABLE produk ADD COLUMN aktif TINYINT(1) NOT NULL DEFAULT 1"
                    )
                except MySQLError as error:
                    if getattr(error, "errno", None) != 1060:
                        raise

            # 3. Pembuatan Tabel Transaksi (Nota Induk Lengkap dengan Bayar & Kembalian)
            if self.engine == "sqlite":
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS transaksi (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tanggal TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        total REAL NOT NULL,
                        metode_pembayaran TEXT,
                        bayar REAL DEFAULT 0,
                        kembalian REAL DEFAULT 0,
                        customer_name TEXT
                    )"""
                )
                # Migrasi aman: tambahkan kolom bayar dan kembalian jika tabel lama sudah ada
                try:
                    cur.execute("ALTER TABLE transaksi ADD COLUMN bayar REAL DEFAULT 0")
                except sqlite3.OperationalError:
                    pass
                try:
                    cur.execute("ALTER TABLE transaksi ADD COLUMN kembalian REAL DEFAULT 0")
                except sqlite3.OperationalError:
                    pass
                try:
                    cur.execute("ALTER TABLE transaksi ADD COLUMN customer_name TEXT")
                except sqlite3.OperationalError as error:
                    if "duplicate column" not in str(error).lower():
                        raise
            else:
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS transaksi (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        tanggal DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        total DECIMAL(10,2) NOT NULL,
                        metode_pembayaran VARCHAR(50),
                        bayar DECIMAL(10,2) DEFAULT 0,
                        kembalian DECIMAL(10,2) DEFAULT 0,
                        customer_name VARCHAR(40) NULL
                    )"""
                )
                try:
                    cur.execute(
                        "ALTER TABLE transaksi ADD COLUMN customer_name VARCHAR(40) NULL"
                    )
                except MySQLError as error:
                    if getattr(error, "errno", None) != 1060:
                        raise

            # 4. Pembuatan Tabel Detail Transaksi (Item Belanjaan)
            if self.engine == "sqlite":
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS detail_transaksi (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaksi_id INTEGER NOT NULL,
                        produk_id INTEGER NOT NULL,
                        jumlah INTEGER NOT NULL,
                        harga REAL NOT NULL,
                        FOREIGN KEY (transaksi_id) REFERENCES transaksi (id),
                        FOREIGN KEY (produk_id) REFERENCES produk (id)
                    )"""
                )
            else:
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS detail_transaksi (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        transaksi_id INT NOT NULL,
                        produk_id INT NOT NULL,
                        jumlah INT NOT NULL,
                        harga DECIMAL(10,2) NOT NULL
                    )"""
                )

            # Isi produk awal (seed products) jika tabel masih kosong
            cur.execute("SELECT COUNT(*) FROM produk")
            count = cur.fetchone()[0]
            if count == 0:
                insert_sql = self._prepare_sql(
                    "INSERT INTO produk (nama, kategori, harga, stok) VALUES (%s, %s, %s, %s)"
                )
                cur.executemany(
                    insert_sql,
                    [(p["name"], p["category"], p["price"], p["stok"]) for p in SEED_PRODUCTS]
                )

            # Rapikan data lama: stok produk yang sudah terlanjur di atas batas
            # disesuaikan menjadi 100 agar seluruh data mengikuti aturan baru.
            clamp_sql = self._prepare_sql(
                "UPDATE produk SET stok = %s WHERE stok > %s"
            )
            cur.execute(clamp_sql, (MAX_PRODUCT_STOCK, MAX_PRODUCT_STOCK))

            # Buat akun admin awal jika tabel akun masih kosong
            cur.execute("SELECT COUNT(*) FROM akun")
            account_count = cur.fetchone()[0]
            if account_count == 0:
                salt = secrets.token_hex(16)
                iterations = 200000
                digest = hashlib.pbkdf2_hmac(
                    "sha256", "KopiNako123!".encode("utf-8"),
                    salt.encode("utf-8"), iterations
                ).hex()
                password_hash = f"pbkdf2_sha256${iterations}${salt}${digest}"

                insert_acc_sql = self._prepare_sql(
                    "INSERT INTO akun (username, nama, role, password_hash) VALUES (%s, %s, %s, %s)"
                )
                cur.execute(
                    insert_acc_sql,
                    ("admin", "Administrator", "admin", password_hash)
                )

            conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def authenticate_user(self, username, password):
        """Memvalidasi login pengguna kasir/admin dengan verifikasi hash PBKDF2."""
        conn = self.connect()
        try:
            if self.engine == "mysql":
                cur = conn.cursor(dictionary=True)
            else:
                cur = conn.cursor()

            sql = self._prepare_sql(
                "SELECT id, username, nama, role, password_hash FROM akun WHERE username = %s LIMIT 1"
            )
            cur.execute(sql, (username.strip(),))
            row = cur.fetchone()
            cur.close()

            if not row:
                return None

            try:
                algorithm, iteration_text, salt, expected = row["password_hash"].split("$", 3)
                if algorithm != "pbkdf2_sha256":
                    return None
                iterations = int(iteration_text)
                actual = hashlib.pbkdf2_hmac(
                    "sha256", password.encode("utf-8"),
                    salt.encode("utf-8"), iterations
                ).hex()

                if hmac.compare_digest(actual, expected):
                    return {
                        "id": int(row["id"]),
                        "username": row["username"],
                        "nama": row["nama"],
                        "role": row["role"],
                    }
            except (ValueError, TypeError, AttributeError):
                return None
            return None
        finally:
            conn.close()

    def get_products(self):
        """Mengambil seluruh daftar produk yang tersimpan di database."""
        conn = self.connect()
        try:
            if self.engine == "mysql":
                cur = conn.cursor(dictionary=True)
            else:
                cur = conn.cursor()

            cur.execute(
                "SELECT id, nama, kategori, harga, stok, image_path "
                "FROM produk WHERE aktif = 1 ORDER BY id"
            )
            rows = cur.fetchall()
            cur.close()
            return [
                {
                    "id": row["id"],
                    "name": row["nama"],
                    "category": row["kategori"],
                    "price": float(row["harga"]),
                    "stok": int(row["stok"]),
                    "image_path": row["image_path"],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def get_orders(self, start_at=None, end_at=None):
        """Mengambil riwayat transaksi, opsional dibatasi rentang waktu.

        Batas akhir bersifat eksklusif agar rentang laporan tidak tumpang tindih.
        Contoh: [2026-10-01 00:00:00, 2026-11-01 00:00:00).
        """
        conn = self.connect()
        try:
            if self.engine == "mysql":
                cur = conn.cursor(dictionary=True)
            else:
                cur = conn.cursor()

            sql = (
                "SELECT id, tanggal, total, metode_pembayaran, "
                "COALESCE(bayar, total) as bayar, "
                "COALESCE(kembalian, 0) as kembalian, "
                "COALESCE(customer_name, '') as customer_name "
                "FROM transaksi"
            )
            params = []
            conditions = []
            if start_at is not None:
                conditions.append("tanggal >= %s")
                params.append(start_at)
            if end_at is not None:
                conditions.append("tanggal < %s")
                params.append(end_at)
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY id DESC"

            cur.execute(self._prepare_sql(sql), tuple(params))
            rows = cur.fetchall()
            cur.close()
            orders = []
            for row in rows:
                raw_dt = row["tanggal"]
                if isinstance(raw_dt, datetime):
                    date_str = raw_dt.strftime("%Y-%m-%d")
                    time_str = raw_dt.strftime("%H:%M")
                elif isinstance(raw_dt, str):
                    parts = raw_dt.split(" ")
                    date_str = parts[0] if len(parts) > 0 else ""
                    time_str = parts[1][:5] if len(parts) > 1 else ""
                else:
                    date_str = ""
                    time_str = ""

                orders.append({
                    "id": f"KN-{row['id']}",
                    "date": date_str,
                    "time": time_str,
                    "total": float(row["total"]),
                    "payment": row["metode_pembayaran"] or "-",
                    "bayar": float(row["bayar"]),
                    "kembalian": float(row["kembalian"]),
                    "customer_name": row["customer_name"] or "",
                })
            return orders
        finally:
            conn.close()

    def create_product(self, name, category, price, stock, image_path=None):
        """Menyimpan produk baru beserta lokasi foto jika tersedia."""
        name = normalize_product_name(name)
        category = str(category or "").strip()
        try:
            price = float(price)
            stock = int(stock)
        except (TypeError, ValueError):
            raise ValueError("Harga harus angka dan stok harus bilangan bulat.")

        if category not in ("Kopi", "Non Kopi", "Makanan"):
            raise ValueError("Kategori produk tidak valid.")
        if price <= 0:
            raise ValueError("Harga harus lebih dari 0.")
        if stock < 0:
            raise ValueError("Stok tidak boleh negatif.")
        if stock > MAX_PRODUCT_STOCK:
            raise ValueError(f"Stok awal maksimal {MAX_PRODUCT_STOCK} item.")

        conn = self.connect()
        try:
            cur = conn.cursor()
            sql = self._prepare_sql(
                "INSERT INTO produk (nama, kategori, harga, stok, image_path) "
                "VALUES (%s, %s, %s, %s, %s)"
            )
            cur.execute(sql, (name, category, price, stock, image_path))
            product_id = cur.lastrowid
            conn.commit()
            cur.close()
            return {
                "id": int(product_id),
                "name": name,
                "category": category,
                "price": float(price),
                "stok": int(stock),
                "image_path": image_path,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_product(self, product_id):
        """Menonaktifkan produk dari katalog tanpa menghapus riwayat penjualannya."""
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            raise ValueError("Produk yang dipilih tidak valid.")
        if product_id <= 0:
            raise ValueError("Produk yang dipilih tidak valid.")

        conn = self.connect()
        try:
            cur = conn.cursor()
            sql = self._prepare_sql(
                "UPDATE produk SET aktif = 0 WHERE id = %s AND aktif = 1"
            )
            cur.execute(sql, (product_id,))
            if cur.rowcount != 1:
                raise ValueError("Produk tidak ditemukan atau sudah dihapus.")
            conn.commit()
            cur.close()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def increase_stock(self, product_id, quantity):
        """Menambahkan stok produk secara atomik dan mengembalikan stok terbaru."""
        try:
            product_id = int(product_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise ValueError("Jumlah stok harus berupa bilangan bulat.")

        if product_id <= 0:
            raise ValueError("Produk tidak valid.")
        if quantity <= 0:
            raise ValueError("Jumlah stok masuk harus lebih dari 0.")

        conn = self.connect()
        try:
            if self.engine == "mysql":
                cur = conn.cursor(dictionary=True)
            else:
                cur = conn.cursor()

            # UPDATE bersyarat membuat pemeriksaan dan penambahan stok berjalan
            # atomik, sehingga dua proses bersamaan tetap tidak bisa melewati 100.
            update_sql = self._prepare_sql(
                "UPDATE produk SET stok = stok + %s "
                "WHERE id = %s AND stok + %s <= %s"
            )
            cur.execute(
                update_sql,
                (quantity, product_id, quantity, MAX_PRODUCT_STOCK),
            )
            updated_rows = cur.rowcount

            select_sql = self._prepare_sql(
                "SELECT id, nama, stok FROM produk WHERE id = %s"
            )
            cur.execute(select_sql, (product_id,))
            row = cur.fetchone()
            if row is None:
                raise ValueError("Produk tidak ditemukan.")
            if updated_rows == 0:
                current_stock = int(row["stok"])
                remaining = max(0, MAX_PRODUCT_STOCK - current_stock)
                raise ValueError(
                    f"Stok maksimal {MAX_PRODUCT_STOCK} item. "
                    f"Stok sekarang {current_stock}; maksimal bisa ditambah {remaining} item."
                )

            conn.commit()
            cur.close()
            return {
                "id": int(row["id"]),
                "name": row["nama"],
                "stok": int(row["stok"]),
                "added": quantity,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_order(
        self, cart, products_by_id, method, total, bayar=None, kembalian=None,
        customer_name=None,
    ):
        """Menyimpan transaksi kasir dan mengurangi stok barang dalam satu transaksi atomik.
        
        Parameter:
        - cart: Dictionary {product_id: qty}
        - products_by_id: Dictionary data produk lengkap
        - method: Metode pembayaran ('Tunai', 'QRIS', 'Kartu')
        - total: Total nominal belanja
        - bayar: Nominal uang yang dibayarkan kasir (jika None, default sama dengan total)
        - kembalian: Nominal kembalian (jika None, default dihitung otomatis)
        - customer_name: Nama pelanggan atau nomor meja untuk struk transaksi
        """
        customer_name = normalize_customer_label(customer_name)
        if bayar is None:
            bayar = total
        if kembalian is None:
            kembalian = max(0.0, float(bayar) - float(total))

        conn = self.connect()
        try:
            if self.engine == "mysql":
                conn.start_transaction()
                cur = conn.cursor(dictionary=True)
            else:
                cur = conn.cursor()

            receipt_items = []

            # 1. Validasi ketersediaan stok
            for product_id, qty in cart.items():
                sql_check = self._prepare_sql(
                    "SELECT id, nama, harga, stok FROM produk WHERE id = %s"
                )
                cur.execute(sql_check, (product_id,))
                row = cur.fetchone()
                if row is None:
                    raise ValueError(f"Produk ID {product_id} tidak ditemukan.")
                if int(row["stok"]) < int(qty):
                    raise ValueError(
                        f"Stok {row['nama']} tidak mencukupi. Tersedia: {row['stok']}, diminta: {qty}."
                    )
                receipt_items.append({
                    "id": int(row["id"]),
                    "name": row["nama"],
                    "qty": int(qty),
                    "price": float(row["harga"]),
                    "subtotal": float(row["harga"]) * int(qty),
                })

            # 2. Masukkan data ke tabel induk transaksi
            transaction_dt = datetime.now()
            transaction_timestamp = transaction_dt.strftime("%Y-%m-%d %H:%M:%S")
            sql_trans = self._prepare_sql(
                "INSERT INTO transaksi "
                "(tanggal, total, metode_pembayaran, bayar, kembalian, customer_name) "
                "VALUES (%s, %s, %s, %s, %s, %s)"
            )
            cur.execute(
                sql_trans, (
                    transaction_timestamp, total, method, bayar, kembalian,
                    customer_name,
                )
            )
            transaction_id = cur.lastrowid

            # 3. Masukkan item detail transaksi dan perbarui stok barang
            for item in receipt_items:
                sql_detail = self._prepare_sql(
                    "INSERT INTO detail_transaksi (transaksi_id, produk_id, jumlah, harga) VALUES (%s, %s, %s, %s)"
                )
                cur.execute(sql_detail, (transaction_id, item["id"], item["qty"], item["price"]))

                sql_update_stock = self._prepare_sql(
                    "UPDATE produk SET stok = stok - %s WHERE id = %s AND stok >= %s"
                )
                cur.execute(sql_update_stock, (item["qty"], item["id"], item["qty"]))
                if cur.rowcount != 1:
                    raise ValueError(f"Stok barang '{item['name']}' berubah saat diproses. Silakan ulangi checkout.")

            conn.commit()
            cur.close()
            return {
                "id": transaction_id,
                "date": transaction_dt.strftime("%Y-%m-%d"),
                "time": transaction_dt.strftime("%H:%M:%S"),
                "payment": method,
                "total": float(total),
                "bayar": float(bayar),
                "kembalian": float(kembalian),
                "customer_name": customer_name,
                "items": receipt_items,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_order(self, transaction_id):
        """Menghapus data transaksi dan rincian itemnya secara permanen."""
        conn = self.connect()
        try:
            if self.engine == "mysql":
                conn.start_transaction()
            cur = conn.cursor()

            sql_del_detail = self._prepare_sql(
                "DELETE FROM detail_transaksi WHERE transaksi_id = %s"
            )
            cur.execute(sql_del_detail, (transaction_id,))

            sql_del_trans = self._prepare_sql(
                "DELETE FROM transaksi WHERE id = %s"
            )
            cur.execute(sql_del_trans, (transaction_id,))
            if cur.rowcount == 0:
                raise ValueError("Transaksi tidak ditemukan.")

            conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_order_details(self, transaction_id):
        """Mengambil rincian item barang dari suatu transaksi berdasarkan ID transaksi."""
        conn = self.connect()
        try:
            if self.engine == "mysql":
                cur = conn.cursor(dictionary=True)
            else:
                cur = conn.cursor()

            sql = self._prepare_sql(
                """SELECT p.nama, dt.jumlah, dt.harga,
                          (dt.jumlah * dt.harga) AS subtotal
                   FROM detail_transaksi dt
                   JOIN produk p ON p.id = dt.produk_id
                   WHERE dt.transaksi_id = %s ORDER BY dt.id"""
            )
            cur.execute(sql, (transaction_id,))
            rows = cur.fetchall()
            cur.close()
            return [
                {
                    "nama": row["nama"],
                    "jumlah": int(row["jumlah"]),
                    "harga": float(row["harga"]),
                    "subtotal": float(row["subtotal"]),
                }
                for row in rows
            ]
        finally:
            conn.close()