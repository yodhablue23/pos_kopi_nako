"""Pengendali alur aplikasi (Application Controller) POS Kopi Nako.

Modul ini adalah pusat logika aplikasi kasir (State Manager) yang mengontrol:
1. Autentikasi sesi kasir (login, logout, hak akses).
2. Navigasi antar halaman melalui Kivy ScreenManager.
3. Keranjang belanja kasir (tambah item, kurangi item, hitung total harga).
4. Alur transaksi checkout, penerimaan uang tunai & kalkulasi kembalian real-time.
5. Pencetakan struk pembayaran lengkap dan ekspor berkas fisik .txt.
"""
from datetime import datetime, timedelta
import json
from pathlib import Path
import shutil
import textwrap
import uuid

from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.text import LabelBase

# Registrasi font Monospace (Consolas / Courier) bawaan Windows untuk struk kasir
RECEIPT_FONT = None
for _font_path in [Path("C:/Windows/Fonts/consola.ttf"), Path("C:/Windows/Fonts/cour.ttf")]:
    if _font_path.exists():
        try:
            LabelBase.register(name="ReceiptMono", fn_regular=str(_font_path))
            RECEIPT_FONT = "ReceiptMono"
            break
        except Exception:
            pass

from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.image import Image

from config import BARCODE_PATH
from theme import (
    ACCENT_ALT, ACCENT_THEMES, CORAL, DANGER_TEXT, MUTED, NAV_COLORS, ON_ACCENT,
    RECEIPT_PAPER, RECEIPT_TEXT, SUCCESS_TEXT, SURFACE, TEAL, TEXT, apply_theme,
)
from database import (
    Database, MAX_CUSTOMER_LABEL_LENGTH, MAX_PRODUCT_STOCK,
    normalize_customer_label, normalize_product_name,
)
from screens import LoginPage, Home, ProductsPage, CartPage, ReportsPage
from ui_components import (
    PAYMENT_BLUE, PAYMENT_ERROR, PAYMENT_FIELD, PAYMENT_MUTED, PAYMENT_TEXT,
    Card, Text, button, payment_brand_badges, payment_field, payment_popup,
    payment_surface, payment_tab, rp, text_input, themed_popup,
)


def _style_popup_text_white(popup, content, exclude=()):
    """Membuat judul dan teks popup putih, kecuali isi kartu berlatar terang."""
    if hasattr(popup, "title_color"):
        popup.title_color = (1, 1, 1, 1)

    excluded_ids = {id(widget) for widget in exclude}
    for widget in content.walk():
        ancestor = widget
        skip = False
        while ancestor is not None:
            if id(ancestor) in excluded_ids:
                skip = True
                break
            ancestor = getattr(ancestor, "parent", None)
        if skip:
            continue
        if widget.__class__.__name__ in ("Text", "Label") and hasattr(widget, "color"):
            widget.color = (1, 1, 1, 1)


REPORT_PERIOD_LABELS = {
    "daily": "Harian",
    "weekly": "Mingguan",
    "monthly": "Bulanan",
    "yearly": "Tahunan",
}

class POSApp(App):
    """Kelas utama aplikasi POS Kopi Nako turunan dari kivy.app.App."""

    def build(self):
        """Metode siklus hidup Kivy untuk menginisialisasi state dan tata letak dasar aplikasi."""
        self.cart = {}              # Format: {product_id: jumlah_beli}
        self.orders = []            # Menyimpan daftar riwayat transaksi dari database
        self.products = []          # Menyimpan daftar menu produk dari database
        self.products_by_id = {}    # Kamus cepat untuk mencari produk berdasarkan ID
        self.current_user = None    # Menyimpan data kasir/admin yang sedang login
        self.transaction_logs = []  # Log audit transaksi kasir (metode, bank debit, total)
        self.customer_name = ""     # Nama pelanggan / nomor meja aktif
        self.theme_settings_path = Path.home() / "Documents" / "POS Kopi Nako" / "settings.json"
        self.theme_mode, self.theme_accent = self.load_theme_preferences()
        apply_theme(self.theme_mode, self.theme_accent)
        self.db = Database()
        self.db_error = None
        self.report_period = "daily"
        self.report_orders = []
        self.report_error = None
        self.report_loading = False

        # Inisialisasi database (membuat tabel dan data awal jika belum ada)
        try:
            self.db.initialize()
            self.refresh_data()
            self.refresh_report()
        except Exception as error:
            self.db_error = str(error)
            self.report_error = str(error)

        # Pengelola transisi halaman tanpa animasi agar transisi instan dan ringan
        self.sm = ScreenManager(transition=NoTransition())
        self.sm.app = self
        self.sm.add_widget(LoginPage(name="login"))
        self.sm.add_widget(Home(name="home"))
        self.sm.add_widget(ProductsPage(name="products"))
        self.sm.add_widget(CartPage(name="cart"))
        self.sm.add_widget(ReportsPage(name="reports"))

        # Root layout yang memuat layar utama dan bar navigasi bawah
        root = BoxLayout(orientation="vertical", spacing=0)
        root.add_widget(self.sm)

        # Bar navigasi bawah terpusat (Centered Bottom Navigation Container)
        self.nav_wrapper = AnchorLayout(
            anchor_x="center", anchor_y="center",
            size_hint=(1, None), height=dp(0),
            padding=[dp(12), dp(6), dp(12), dp(8)]
        )

        nav = GridLayout(
            cols=5, size_hint=(None, None), width=dp(660), height=dp(46),
            spacing=dp(8)
        )
        self.nav = nav
        self.nav_buttons = {}
        for title, screen in [
            ("HOME", "home"),
            ("PRODUK", "products"),
            ("KERANJANG", "cart"),
            ("LAPORAN", "reports")
        ]:
            b = button(title, lambda s=screen: self.go(s), False, 44)
            self.nav_buttons[screen] = b
            nav.add_widget(b)

        self.logout_button = button("KELUAR", self.logout, True, 44)
        nav.add_widget(self.logout_button)
        self.nav_wrapper.add_widget(nav)
        self.root_layout = root

        # Di halaman login: nav_wrapper TIDAK dimasukkan ke root_layout agar 100% bebas bocor visual
        self.nav_wrapper.opacity = 0
        self.nav_wrapper.disabled = True
        self.sm.current = "login"
        self.update_nav()
        return root

    def load_theme_preferences(self):
        """Membaca pilihan tema lokal tanpa menyimpan data sensitif."""
        defaults = ("light", "cyan")
        try:
            if not self.theme_settings_path.exists():
                return defaults
            data = json.loads(self.theme_settings_path.read_text(encoding="utf-8"))
            mode = data.get("mode")
            accent = data.get("accent")
            if mode not in ("light", "dark"):
                mode = defaults[0]
            if accent not in ACCENT_THEMES:
                accent = defaults[1]
            return mode, accent
        except (OSError, TypeError, ValueError):
            return defaults

    def save_theme_preferences(self):
        """Menyimpan pilihan tema agar tetap digunakan saat aplikasi dibuka lagi."""
        try:
            self.theme_settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.theme_settings_path.write_text(
                json.dumps({"mode": self.theme_mode, "accent": self.theme_accent}, indent=2),
                encoding="utf-8",
            )
        except OSError:
            # Tema tetap diterapkan walau folder Dokumen tidak dapat ditulis.
            pass

    def apply_theme(self, mode=None, accent=None, persist=True, rerender=True):
        """Menerapkan tema lalu merender ulang halaman aktif."""
        mode = mode if mode in ("light", "dark") else self.theme_mode
        accent = accent if accent in ACCENT_THEMES else self.theme_accent
        self.theme_mode = mode
        self.theme_accent = accent
        apply_theme(mode, accent)
        if persist:
            self.save_theme_preferences()

        if hasattr(self, "sm"):
            if rerender:
                self.sm.get_screen(self.sm.current).render()
            self.update_nav()

    def on_start(self):
        """Dipanggil oleh Kivy tepat setelah jendela aplikasi muncul."""
        if self.db_error:
            self.notice(
                f"Koneksi database ({self.db.engine}) bermasalah.\n"
                f"Detail: {self.db_error}"
            )

    # -------------------------------------------------------------------------
    # Autentikasi Pengguna & Navigasi
    # -------------------------------------------------------------------------
    def login(self, username, password):
        """Memproses login kasir dengan verifikasi username dan password."""
        if self.db_error:
            self.notice(
                f"Database ({self.db.engine}) belum tersambung:\n{self.db_error}"
            )
            return
        if not username.strip() or not password:
            self.notice("Username dan password wajib diisi.")
            return

        try:
            user = self.db.authenticate_user(username, password)
        except Exception as error:
            self.notice("Login gagal karena kendala database:\n" + str(error))
            return

        if user is None:
            self.notice("Username atau password salah.")
            return

        # Login berhasil
        self.current_user = user
        self.cart.clear()
        if self.nav_wrapper not in self.root_layout.children:
            self.root_layout.add_widget(self.nav_wrapper)
        self.nav_wrapper.opacity = 1
        self.nav_wrapper.disabled = False
        self.nav_wrapper.height = dp(62)
        self.nav.height = dp(46)
        self.sm.current = "home"
        self.refresh_data()
        self.refresh_report()
        self.update_nav()
        self.sm.get_screen("home").render()

    def logout(self):
        """Mengakhiri sesi kasir dan mengembalikan layar ke halaman login."""
        if self.sm.current == "login":
            return
        self.current_user = None
        self.cart.clear()
        if self.nav_wrapper in self.root_layout.children:
            self.root_layout.remove_widget(self.nav_wrapper)
        self.nav_wrapper.opacity = 0
        self.nav_wrapper.disabled = True
        self.sm.current = "login"
        self.update_nav()
        self.sm.get_screen("login").render()
        self.notice("Anda telah berhasil logout.")

    def go(self, name):
        """Berpindah ke halaman lain dengan validasi login."""
        if self.current_user is None:
            if hasattr(self, "root_layout") and self.nav_wrapper in self.root_layout.children:
                self.root_layout.remove_widget(self.nav_wrapper)
            self.nav_wrapper.opacity = 0
            self.nav_wrapper.disabled = True
            self.sm.current = "login"
            return
        if self.db_error:
            self.notice("Database belum tersambung. Periksa konfigurasi db_config.py.")
            return
        self.sm.current = name
        self.update_nav()
        self.sm.get_screen(name).render()

    def update_nav(self):
        """Memperbarui visual navigasi bawah: Active State kontras/solid, tombol lain redup/soft."""
        for name, btn in self.nav_buttons.items():
            active = self.sm.current == name
            if active:
                # Active State: Warna kontras solid yang jelas sesuai halaman
                solid_color = NAV_COLORS.get(name, TEAL)
                if hasattr(btn, "_bg_color"):
                    btn._bg_color.rgba = solid_color
                btn.color = ON_ACCENT
            else:
                # Inactive State: Lebih redup / outline lembut
                if hasattr(btn, "_bg_color"):
                    btn._bg_color.rgba = tuple(SURFACE[:3]) + (0.5,)
                btn.color = TEXT
        if hasattr(self, "logout_button"):
            if hasattr(self.logout_button, "_bg_color"):
                self.logout_button._bg_color.rgba = CORAL
            self.logout_button.color = ON_ACCENT

    def refresh_data(self):
        """Mengambil ulang data produk dan riwayat transaksi dari database."""
        self.products = self.db.get_products()
        self.products_by_id = {p["id"]: p for p in self.products}
        self.orders = self.db.get_orders()

    def import_product_image(self, selected_uri):
        """Menyalin foto pilihan ke folder sementara milik aplikasi.

        Android mengembalikan content:// URI, bukan selalu path file biasa.
        Karena itu foto dibaca melalui ContentResolver lalu disalin ke storage app.
        """
        if not selected_uri:
            raise ValueError("Foto belum dipilih.")

        temp_dir = Path(self.user_data_dir) / "product_image_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        selected_uri = str(selected_uri)

        if selected_uri.startswith("content://"):
            try:
                from jnius import autoclass  # type: ignore[reportMissingImports]  # tersedia di APK Android
            except ImportError as error:
                raise RuntimeError(
                    "Pembaca foto Android tidak tersedia. Pastikan APK dibuat "
                    "dengan python-for-android."
                ) from error

            Uri = autoclass("android.net.Uri")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            FileOutputStream = autoclass("java.io.FileOutputStream")
            Array = autoclass("java.lang.reflect.Array")
            Byte = autoclass("java.lang.Byte")

            activity = PythonActivity.mActivity
            resolver = activity.getContentResolver()
            uri = Uri.parse(selected_uri)
            mime_type = resolver.getType(uri)
            mime_type = str(mime_type) if mime_type else ""
            extension_by_mime = {
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
            }
            extension = extension_by_mime.get(mime_type)
            if not extension:
                raise ValueError(
                    "Format foto belum didukung. Gunakan JPG, PNG, atau WEBP."
                )

            destination = temp_dir / f"selected_{uuid.uuid4().hex}{extension}"
            input_stream = resolver.openInputStream(uri)
            if input_stream is None:
                raise RuntimeError("Foto tidak bisa dibaca dari galeri.")
            output_stream = None
            try:
                output_stream = FileOutputStream(str(destination))
                buffer = Array.newInstance(Byte.TYPE, 8192)
                while True:
                    count = int(input_stream.read(buffer))
                    if count < 0:
                        break
                    output_stream.write(buffer, 0, count)
                output_stream.flush()
            except Exception:
                try:
                    destination.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            finally:
                try:
                    input_stream.close()
                except Exception:
                    pass
                if output_stream is not None:
                    try:
                        output_stream.close()
                    except Exception:
                        pass
            if not destination.exists() or destination.stat().st_size == 0:
                raise RuntimeError("Foto yang dipilih kosong atau gagal disalin.")
            return str(destination)

        # Windows/macOS/Linux: native file chooser memberikan path file.
        source = Path(selected_uri)
        if not source.is_file():
            raise ValueError("File foto tidak ditemukan atau tidak bisa dibaca.")
        extension = source.suffix.lower()
        if extension not in (".jpg", ".jpeg", ".png", ".webp"):
            raise ValueError("Gunakan foto JPG, JPEG, PNG, atau WEBP.")

        destination = temp_dir / f"selected_{uuid.uuid4().hex}{extension}"
        shutil.copy2(source, destination)
        return str(destination)

    def discard_product_image(self, image_path):
        """Menghapus salinan sementara foto ketika form dibatalkan/diganti."""
        if not image_path:
            return
        try:
            path = Path(image_path).resolve()
            temp_dir = (Path(self.user_data_dir) / "product_image_temp").resolve()
            if path.parent == temp_dir and path.is_file():
                path.unlink()
        except (OSError, ValueError):
            pass

    def create_product(self, raw_name, category, raw_price, raw_stock, image_path=None):
        """Menambahkan produk baru beserta foto ke database."""
        if self.current_user is None:
            raise ValueError("Anda harus login untuk menambahkan produk.")
        if self.db_error:
            raise ValueError("Database belum tersambung.")
        name = normalize_product_name(raw_name)
        if raw_price is None or not str(raw_price).strip():
            raise ValueError("Harga produk wajib diisi.")
        if raw_stock is None or not str(raw_stock).strip():
            raise ValueError("Stok awal wajib diisi.")

        try:
            price_text = str(raw_price).strip().replace(",", "")
            price = float(price_text)
            stock = int(str(raw_stock).strip())
        except (TypeError, ValueError):
            raise ValueError("Harga harus angka dan stok harus bilangan bulat.")
        if price <= 0:
            raise ValueError("Harga harus lebih dari 0.")
        if price > 100000:
            raise ValueError("Harga produk maksimal Rp 100.000.")
        if stock < 0:
            raise ValueError("Stok tidak boleh negatif.")
        if stock > MAX_PRODUCT_STOCK:
            raise ValueError(f"Stok awal maksimal {MAX_PRODUCT_STOCK} item.")

        final_image_path = None
        saved_image = None
        if image_path:
            source = Path(image_path)
            if not source.is_file():
                raise ValueError("File foto produk tidak ditemukan.")
            extension = source.suffix.lower()
            if extension not in (".jpg", ".jpeg", ".png", ".webp"):
                raise ValueError("Format foto harus JPG, JPEG, PNG, atau WEBP.")
            image_dir = Path(self.user_data_dir) / "product_images"
            image_dir.mkdir(parents=True, exist_ok=True)
            saved_image = image_dir / f"product_{uuid.uuid4().hex}{extension}"
            shutil.copy2(source, saved_image)
            final_image_path = str(saved_image)

        try:
            product = self.db.create_product(
                name, category, price, stock, image_path=final_image_path
            )
        except Exception:
            if saved_image is not None:
                try:
                    saved_image.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

        self.discard_product_image(image_path)
        product["image_path"] = final_image_path
        self.refresh_data()
        return product

    def delete_product(self, product_id):
        """Mengarsipkan produk dari katalog tanpa merusak riwayat transaksi."""
        if self.current_user is None:
            raise ValueError("Anda harus login untuk menghapus produk.")
        if self.db_error:
            raise ValueError("Database belum tersambung.")

        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            raise ValueError("Produk yang dipilih tidak valid.")

        product = self.products_by_id.get(product_id)
        if product is None:
            raise ValueError("Produk tidak ditemukan atau sudah dihapus.")

        # Hapus juga dari keranjang aktif agar produk yang diarsipkan tidak ikut checkout.
        self.db.delete_product(product_id)
        self.cart.pop(product_id, None)
        self.refresh_data()

        if hasattr(self, "sm") and self.sm.current == "cart":
            self.sm.get_screen("cart").render()
        return product

    def add_stock(self, product_id, raw_quantity):
        """Menambahkan stok dari alur manajemen stok kasir/admin."""
        if self.current_user is None:
            raise ValueError("Anda harus login sebagai kasir untuk mengubah stok.")
        if self.db_error:
            raise ValueError("Database belum tersambung.")
        if raw_quantity is None or not str(raw_quantity).strip():
            raise ValueError("Jumlah stok masuk wajib diisi.")

        try:
            quantity = int(str(raw_quantity).strip())
        except (TypeError, ValueError):
            raise ValueError("Jumlah stok harus berupa bilangan bulat.")
        if quantity <= 0:
            raise ValueError("Jumlah stok masuk harus lebih dari 0.")

        updated_product = self.db.increase_stock(product_id, quantity)
        self.refresh_data()
        return updated_product

    def _report_range(self, period=None, reference=None):
        """Menghasilkan rentang waktu lokal untuk laporan kalender."""
        period = period or self.report_period
        if period not in REPORT_PERIOD_LABELS:
            raise ValueError("Periode laporan tidak valid.")

        current = reference or datetime.now()
        day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "daily":
            start = day_start
            end = start + timedelta(days=1)
        elif period == "weekly":
            start = day_start - timedelta(days=day_start.weekday())
            end = start + timedelta(days=7)
        elif period == "monthly":
            start = day_start.replace(day=1)
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        else:
            start = day_start.replace(month=1, day=1)
            end = start.replace(year=start.year + 1)
        return start, end

    def report_range_label(self):
        """Menghasilkan label rentang tanggal yang mudah dibaca di UI."""
        start, end = self._report_range()
        last_moment = end - timedelta(seconds=1)
        start_label = start.strftime("%d %b %Y")
        end_label = last_moment.strftime("%d %b %Y")
        return start_label if start_label == end_label else f"{start_label} - {end_label}"

    def refresh_report(self, period=None):
        """Mengambil ulang data laporan dari database sesuai periode aktif."""
        if period is not None:
            if period not in REPORT_PERIOD_LABELS:
                raise ValueError("Periode laporan tidak valid.")
            self.report_period = period

        self.report_loading = True
        self.report_error = None
        try:
            if self.db_error:
                raise ValueError(self.db_error)
            start, end = self._report_range()
            self.report_orders = self.db.get_orders(
                start_at=start.strftime("%Y-%m-%d %H:%M:%S"),
                end_at=end.strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception as error:
            self.report_orders = []
            self.report_error = str(error)
        finally:
            self.report_loading = False
        return self.report_orders

    def set_report_period(self, period):
        """Mengganti filter laporan lalu merender ulang halaman laporan."""
        self.refresh_report(period)
        if hasattr(self, "sm") and self.sm.current == "reports":
            self.sm.get_screen("reports").render()

    # -------------------------------------------------------------------------
    # Pengelolaan Keranjang Belanja
    # -------------------------------------------------------------------------
    def add_product(self, product):
        """Menambahkan produk ke keranjang belanja dengan validasi stok."""
        pid = product["id"]
        current_qty = self.cart.get(pid, 0)
        if int(product["stok"]) <= current_qty:
            self.notice(f"Stok {product['name']} tidak mencukupi!")
            return
        self.cart[pid] = current_qty + 1
        if self.sm.current == "cart":
            self.sm.get_screen("cart").render()
        self.notice(f"{product['name']} ditambahkan ke keranjang.")

    def set_qty(self, pid, raw_quantity):
        """Menetapkan jumlah item langsung dari input keranjang."""
        if pid not in self.products_by_id:
            self.notice("Produk tidak ditemukan.")
            return False
        if raw_quantity is None or not str(raw_quantity).strip():
            self.notice("Jumlah pesanan wajib diisi.")
            return False

        try:
            quantity = int(str(raw_quantity).strip())
        except (TypeError, ValueError):
            self.notice("Jumlah pesanan harus berupa bilangan bulat.")
            return False

        if quantity < 0:
            self.notice("Jumlah pesanan tidak boleh negatif.")
            return False
        available_stock = int(self.products_by_id[pid]["stok"])
        if quantity > available_stock:
            self.notice(f"Jumlah melebihi stok yang tersedia: {available_stock} item.")
            return False
        if quantity == 0:
            self.cart.pop(pid, None)
        else:
            self.cart[pid] = quantity
        self.sm.get_screen("cart").render()
        return True

    def change_qty(self, pid, delta):
        """Mengubah kuantitas item pesanan melalui tombol plus/minus."""
        current_qty = self.cart.get(pid, 0)
        return self.set_qty(pid, current_qty + delta)

    def cart_total(self):
        """Menghitung akumulasi total harga belanjaan seluruh item di keranjang."""
        return sum(
            self.products_by_id[pid]["price"] * qty
            for pid, qty in self.cart.items()
        )

    def sales_today(self):
        """Menghitung total omzet penjualan untuk tanggal hari ini."""
        today = datetime.now().strftime("%Y-%m-%d")
        return sum(
            o["total"] for o in self.orders if o["date"] == today
        )

    def transactions_today(self):
        """Menghitung jumlah transaksi pada tanggal hari ini."""
        today = datetime.now().strftime("%Y-%m-%d")
        return sum(1 for order in self.orders if order["date"] == today)

    def home_metrics(self, reference=None):
        """Menghasilkan metric dashboard hari ini dibandingkan hari kalender sebelumnya."""
        current = reference or datetime.now()
        today_key = current.strftime("%Y-%m-%d")
        yesterday_key = (current - timedelta(days=1)).strftime("%Y-%m-%d")

        today_orders = [order for order in self.orders if order["date"] == today_key]
        yesterday_orders = [
            order for order in self.orders if order["date"] == yesterday_key
        ]
        today_sales = sum(order["total"] for order in today_orders)
        yesterday_sales = sum(order["total"] for order in yesterday_orders)

        def growth(current_value, previous_value):
            if previous_value == 0:
                return None
            return ((current_value - previous_value) / previous_value) * 100

        return {
            "sales": {
                "value": today_sales,
                "previous": yesterday_sales,
                "growth": growth(today_sales, yesterday_sales),
            },
            "transactions": {
                "value": len(today_orders),
                "previous": len(yesterday_orders),
                "growth": growth(len(today_orders), len(yesterday_orders)),
            },
        }

    def clear_cart(self):
        """Mengosongkan seluruh isi keranjang belanja."""
        self.cart.clear()
        self.sm.get_screen("cart").render()

    def new_order(self):
        """Membuka pesanan baru: kosongkan keranjang lalu arahkan ke menu produk."""
        self.cart.clear()
        self.go("products")

    # -------------------------------------------------------------------------
    # Alur Checkout & Pembayaran Kasir (Dengan Fitur Kembalian Tunai)
    # -------------------------------------------------------------------------
    def checkout(self):
        """Menampilkan dialog pemilihan metode pembayaran."""
        if not self.cart:
            self.notice("Keranjang belanja masih kosong!")
            return
        try:
            self.customer_name = normalize_customer_label(self.customer_name)
        except ValueError as error:
            self.notice(str(error))
            return

        total = self.cart_total()
        content = BoxLayout(
            orientation="vertical", padding=dp(16), spacing=dp(12)
        )
        content.add_widget(Text(
            f"TOTAL TAGIHAN: {rp(total)}",
            size=20, bold=True, color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(10), align="center"
        ))
        content.add_widget(Text(
            "Pilih metode pembayaran yang digunakan pelanggan:",
            size=12, color=(1, 1, 1, 1),
            size_hint_y=None, height=dp(20), align="center"
        ))

        popup = themed_popup(
            "Metode Pembayaran", content,
            size_hint=(0.84, None), height=dp(340),
        )
        _style_popup_text_white(popup, content)

        # Opsi Tunai membuka form input penerimaan uang
        content.add_widget(button(
            "Tunai (Uang Cash)",
            lambda: self.open_cash_tender_popup(popup, total),
            True, 42
        ))
        content.add_widget(button(
            "Saldo E-Wallet (Barcode)",
            lambda: self.open_ewallet_barcode_popup(popup, total),
            True, 40
        ))
        content.add_widget(button(
            "Kartu Debit Digital",
            lambda: self.open_debit_card_popup(popup, total),
            True, 40
        ))
        content.add_widget(button("BATAL", popup.dismiss, False, 36))
        popup.open()

    def open_cash_tender_popup(self, parent_popup, total):
        """Membuka jendela form penerimaan uang tunai dan hitung kembalian otomatis."""
        parent_popup.dismiss()

        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        content.add_widget(Text(
            f"Total Tagihan: {rp(total)}",
            size=19, bold=True, color=(1, 1, 1, 1), size_hint_y=None, height=dp(6),
            align="center"
        ))

        content.add_widget(Text(
            "Uang Tunai Diterima (Rp):",
            size=12, bold=True, color=MUTED, size_hint_y=None, height=dp(18)
        ))

        # Input nominal uang tunai
        cash_input = text_input(
            text=str(int(total)),
            height=46, font_size=18, input_filter="int"
        )
        content.add_widget(cash_input)

        # Tombol jalan pintas pecahan uang
        quick_grid = GridLayout(cols=4, spacing=dp(6), size_hint_y=None, height=dp(36))
        quick_values = [
            ("Uang Pas", int(total)),
            ("Rp 20.000", 20000),
            ("Rp 50.000", 50000),
            ("Rp 100.000", 100000),
        ]
        for label, val in quick_values:
            quick_grid.add_widget(button(
                label,
                lambda v=val: setattr(cash_input, "text", str(v)),
                False, 34
            ))
        content.add_widget(quick_grid)

        # Label status kembalian / kekurangan uang
        change_label = Text(
            "Kembalian: Rp 0",
            size=16, bold=True, color=SUCCESS_TEXT, size_hint_y=None, height=dp(30),
            align="center"
        )
        content.add_widget(change_label)

        def update_change(*_):
            raw_text = cash_input.text.strip()
            if not raw_text:
                change_label.text = "Masukkan nominal pembayaran"
                change_label.color = (1, 1, 1, 1)
                return
            try:
                nominal = int(raw_text)
                kembalian = nominal - total
                if kembalian < 0:
                    change_label.text = f"Uang Kurang: {rp(abs(kembalian))}"
                    change_label.color = (1, 0.58, 0.58, 1)
                else:
                    change_label.text = f"Kembalian: {rp(kembalian)}"
                    change_label.color = (0.55, 1, 0.72, 1)
            except ValueError:
                change_label.text = "Nominal tidak valid"
                change_label.color = (1, 0.58, 0.58, 1)

        cash_input.bind(text=update_change)
        update_change()

        tender_popup = themed_popup(
            "Pembayaran Tunai & Kembalian", content,
            size_hint=(0.88, None), height=dp(390),
        )
        _style_popup_text_white(tender_popup, content)

        def submit_cash():
            raw_text = cash_input.text.strip()
            if not raw_text:
                self.notice("Harap masukkan nominal uang tunai.")
                return
            try:
                nominal = int(raw_text)
            except ValueError:
                self.notice("Nominal uang harus berupa angka.")
                return

            if nominal < total:
                self.notice(f"Uang tidak mencukupi! Kurang {rp(total - nominal)}.")
                return

            kembalian = nominal - total
            self.finish_payment("Tunai", tender_popup, bayar=nominal, kembalian=kembalian)

        actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        actions.add_widget(button("BATAL", tender_popup.dismiss, False, 40))
        actions.add_widget(button("SELESAIKAN PEMBAYARAN", submit_cash, True, 40))
        content.add_widget(actions)

        tender_popup.open()

    def open_ewallet_barcode_popup(self, parent_popup, total):
        """Membuka jendela modal QR Code / Barcode pembayaran saldo e-wallet."""
        parent_popup.dismiss()

        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        content.add_widget(Text(
            f"Total Tagihan: {rp(total)}",
            size=19, bold=True, color=(1, 1, 1, 1), size_hint_y=None, height=dp(10),
            align="center"
        ))
        content.add_widget(Text(
            "Pindai Barcode / QR Code untuk pembayaran saldo E-Wallet:",
            size=12, color=MUTED, size_hint_y=None, height=dp(20), align="center"
        ))

        # Kontainer kartu untuk menampilkan barcode / QR code
        qr_card = Card(
            orientation="vertical", padding=dp(10), spacing=dp(4),
            size_hint=(1, None), height=dp(200), color=RECEIPT_PAPER
        )
        if BARCODE_PATH.exists():
            qr_image = Image(
                source=str(BARCODE_PATH),
                size_hint=(1, 1),
                fit_mode="contain"
            )
            qr_card.add_widget(qr_image)
        else:
            qr_card.add_widget(Text(
                "[ BARCODE / QR CODE ]\n(Aset gambar barcode belum tersedia)",
                size=13, color=RECEIPT_TEXT, align="center"
            ))
        content.add_widget(qr_card)

        content.add_widget(Text(
            "Mendukung GoPay, OVO, Dana, ShopeePay, LinkAja, & Mobile Banking",
            size=11, color=MUTED, size_hint_y=None, height=dp(20), align="center"
        ))

        ewallet_popup = themed_popup(
            "Barcode Pembayaran Saldo (E-Wallet)", content,
            size_hint=(0.88, None), height=dp(420),
        )
        _style_popup_text_white(ewallet_popup, content, exclude=(qr_card,))

        def verify_and_pay():
            self.finish_payment(
                "E-Wallet", ewallet_popup, bayar=total, kembalian=0
            )

        actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        actions.add_widget(button("BATAL", ewallet_popup.dismiss, False, 40))
        actions.add_widget(button("VERIFIKASI & BAYAR", verify_and_pay, True, 40))
        content.add_widget(actions)

        ewallet_popup.open()

    def open_debit_card_popup(self, parent_popup, total):
        """Membuka modal pembayaran dark dengan tab kartu, e-wallet, dan QRIS."""
        parent_popup.dismiss()

        content = payment_surface(size_hint=(1, 1))
        header = BoxLayout(
            orientation="vertical", spacing=dp(2), size_hint_y=None, height=dp(58)
        )
        header.add_widget(Text(
            "Metode pembayaran", size=20, bold=True, color=PAYMENT_TEXT,
            size_hint_y=None, height=dp(30),
        ))
        header.add_widget(Text(
            f"Total yang harus dibayar: {rp(total)}",
            size=12, color=PAYMENT_MUTED, size_hint_y=None, height=dp(20),
        ))
        content.add_widget(header)

        selected_tab = {"name": "Card"}
        tab_buttons = {}
        tab_row = GridLayout(
            cols=3, spacing=dp(8), size_hint_y=None, height=dp(42)
        )
        content.add_widget(tab_row)

        body = BoxLayout(
            orientation="vertical", spacing=dp(10), size_hint=(1, 1)
        )
        content.add_widget(body)
        form_state = {}
        debit_popup = None

        def set_feedback(message):
            feedback = form_state.get("feedback")
            if feedback is not None:
                feedback.text = message
                feedback.color = PAYMENT_ERROR if message else PAYMENT_MUTED

        def process_debit():
            card_input = form_state.get("card_number")
            expiry_input = form_state.get("expiry")
            cvc_input = form_state.get("cvc")
            bank_spinner = form_state.get("bank")
            if not all((card_input, expiry_input, cvc_input, bank_spinner)):
                return

            card_digits = "".join(char for char in card_input.text if char.isdigit())
            if not 12 <= len(card_digits) <= 19:
                set_feedback("Nomor kartu harus berisi 12 sampai 19 digit.")
                card_input.focus = True
                return

            expiry = expiry_input.text.strip()
            expiry_parts = expiry.split("/")
            if (
                len(expiry_parts) != 2
                or len(expiry_parts[0]) != 2
                or len(expiry_parts[1]) != 2
                or not all(part.isdigit() for part in expiry_parts)
                or not 1 <= int(expiry_parts[0]) <= 12
            ):
                set_feedback("Masa berlaku harus memakai format MM/YY yang valid.")
                expiry_input.focus = True
                return

            expiry_year = 2000 + int(expiry_parts[1])
            current_month = (datetime.now().year, datetime.now().month)
            if (expiry_year, int(expiry_parts[0])) < current_month:
                set_feedback("Kartu sudah melewati masa berlaku.")
                expiry_input.focus = True
                return

            cvc = cvc_input.text.strip()
            if not cvc.isdigit() or len(cvc) not in (3, 4):
                set_feedback("Kode keamanan harus berisi 3 atau 4 digit.")
                cvc_input.focus = True
                return

            selected_bank = bank_spinner.text.strip() or "BCA"
            self.finish_payment(
                f"Debit {selected_bank}", debit_popup,
                bayar=total, kembalian=0,
                bank=selected_bank,
                extra_info={"bank": selected_bank, "card_last4": card_digits[-4:]},
            )

        def build_card_tab():
            body.clear_widgets()
            form_state.clear()
            body.add_widget(Text(
                "Masukkan detail kartu yang digunakan pada mesin EDC.",
                size=11, color=PAYMENT_MUTED,
                size_hint_y=None, height=dp(18),
            ))

            bank_label = Text(
                "Bank Penerbit", size=11, bold=True, color=PAYMENT_MUTED,
                size_hint_y=None, height=dp(17),
            )
            body.add_widget(bank_label)
            bank_spinner = Spinner(
                text="BCA", values=("BCA", "Mandiri", "BRI", "BNI"),
                size_hint=(1, None), height=dp(42),
                font_size=dp(13), bold=True, color=PAYMENT_TEXT,
                background_normal="", background_down="",
                background_color=PAYMENT_FIELD,
            )
            body.add_widget(bank_spinner)
            form_state["bank"] = bank_spinner

            card_wrapper, card_input = payment_field(
                "Nomor Kartu / Card Number",
                "1234 5678 9012 3456",
                right_widget=payment_brand_badges(),
                input_filter="int",
                max_length=19,
            )
            body.add_widget(card_wrapper)
            form_state["card_number"] = card_input

            fields_row = GridLayout(
                cols=2, spacing=dp(10), size_hint_y=None, height=dp(68)
            )
            expiry_wrapper, expiry_input = payment_field(
                "Masa Berlaku (MM/YY)", "MM/YY", max_length=5,
            )
            cvc_wrapper, cvc_input = payment_field(
                "Kode Keamanan / CVC", "CVC", input_filter="int",
                password=True, max_length=4,
            )
            fields_row.add_widget(expiry_wrapper)
            fields_row.add_widget(cvc_wrapper)
            body.add_widget(fields_row)
            form_state["expiry"] = expiry_input
            form_state["cvc"] = cvc_input

            feedback = Text(
                "", size=11, color=PAYMENT_MUTED, align="center",
                size_hint_y=None, height=dp(24),
            )
            body.add_widget(feedback)
            form_state["feedback"] = feedback
            body.add_widget(Text(
                "Konfirmasi hanya setelah pembayaran berhasil pada mesin EDC.",
                size=10, color=PAYMENT_MUTED, align="center",
                size_hint_y=None, height=dp(18),
            ))

            actions = BoxLayout(
                size_hint_y=None, height=dp(42), spacing=dp(8)
            )
            actions.add_widget(button(
                "BATAL", debit_popup.dismiss, height=40,
                fill_color=PAYMENT_FIELD, text_color=PAYMENT_MUTED,
            ))
            actions.add_widget(button(
                "Bayar Sekarang", process_debit, height=40,
                fill_color=PAYMENT_BLUE, text_color=PAYMENT_TEXT,
            ))
            body.add_widget(actions)
            card_input.bind(on_text_validate=lambda *_: process_debit())
            expiry_input.bind(on_text_validate=lambda *_: setattr(cvc_input, "focus", True))
            cvc_input.bind(on_text_validate=lambda *_: process_debit())

        def build_qr_tab(method):
            body.clear_widgets()
            form_state.clear()
            body.add_widget(Text(
                f"Pindai kode {method} untuk menyelesaikan pembayaran.",
                size=12, color=PAYMENT_MUTED, align="center",
                size_hint_y=None, height=dp(28),
            ))
            qr_card = Card(
                orientation="vertical", padding=dp(10),
                size_hint=(1, None), height=dp(200), color=RECEIPT_PAPER,
                radius=12,
            )
            if BARCODE_PATH.exists():
                qr_card.add_widget(Image(
                    source=str(BARCODE_PATH), size_hint=(1, 1), fit_mode="contain"
                ))
            else:
                qr_card.add_widget(Text(
                    "[ QR ASSET BELUM TERSEDIA ]", size=12,
                    color=RECEIPT_TEXT, align="center",
                ))
            body.add_widget(qr_card)
            body.add_widget(Text(
                "Gunakan kode pembayaran yang tersedia pada layar ini.",
                size=10, color=PAYMENT_MUTED, align="center",
                size_hint_y=None, height=dp(22),
            ))

            def process_qr():
                self.finish_payment(
                    method, debit_popup, bayar=total, kembalian=0
                )

            actions = BoxLayout(
                size_hint_y=None, height=dp(42), spacing=dp(8)
            )
            actions.add_widget(button(
                "BATAL", debit_popup.dismiss, height=40,
                fill_color=PAYMENT_FIELD, text_color=PAYMENT_MUTED,
            ))
            actions.add_widget(button(
                "Bayar Sekarang", process_qr, height=40,
                fill_color=PAYMENT_BLUE, text_color=PAYMENT_TEXT,
            ))
            body.add_widget(actions)

        def render_tab():
            for name, tab in tab_buttons.items():
                tab.set_active(name == selected_tab["name"])
            if selected_tab["name"] == "Card":
                build_card_tab()
            else:
                build_qr_tab(selected_tab["name"])

        def select_tab(name):
            selected_tab["name"] = name
            render_tab()

        for name in ("Card", "E-Wallet", "QRIS"):
            tab = payment_tab(
                name, lambda selected=name: select_tab(selected),
                active=name == selected_tab["name"],
            )
            tab_buttons[name] = tab
            tab_row.add_widget(tab)

        debit_popup = payment_popup(
            content,
            size_hint=(0.92, None), height=dp(560), auto_dismiss=True,
        )
        render_tab()
        debit_popup.open()

    def log_transaction(self, receipt, method, bank=None, extra_info=None):
        """Mencatat aktivitas transaksi kasir secara terstruktur ke memori dan log sistem."""
        safe_extra = dict(extra_info or {})
        for sensitive_key in (
            "card_number", "card_number_full", "cvc", "cvv",
            "security_code", "expiry", "card_expiry",
        ):
            safe_extra.pop(sensitive_key, None)
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "transaction_id": receipt["id"],
            "method": method,
            "bank": bank,
            "total": receipt["total"],
            "cashier": self.current_user["nama"] if self.current_user else "Kasir",
            "extra": safe_extra,
        }
        self.transaction_logs.append(entry)
        bank_str = f" [Bank: {bank}]" if bank else ""
        print(f"[LOG TRANSAKSI] KN-{receipt['id']} | Metode: {method}{bank_str} | Total: {rp(receipt['total'])} | Kasir: {entry['cashier']}")

    def finish_payment(self, method, popup, bayar=None, kembalian=0, bank=None, extra_info=None):
        """Menyimpan pesanan ke database, mengurangi stok barang, dan menampilkan nota struk."""
        total = self.cart_total()
        if bayar is None:
            bayar = total

        try:
            self.customer_name = normalize_customer_label(self.customer_name)
            receipt = self.db.save_order(
                self.cart, self.products_by_id, method, total, bayar, kembalian,
                customer_name=self.customer_name,
            )
            self.refresh_data()
            self.refresh_report()
        except ValueError as error:
            self.notice("Transaksi gagal:\n" + str(error))
            return
        except Exception as error:
            self.notice("Transaksi gagal disimpan:\n" + str(error))
            return

        # Catat log transaksi kasir (metode, bank debit, total)
        self.log_transaction(receipt, method, bank=bank, extra_info=extra_info)

        self.cart.clear()
        popup.dismiss()
        self.go("reports")
        self.show_receipt(receipt)
        self.customer_name = ""

    # -------------------------------------------------------------------------
    # Pembuatan & Tampilan Struk Pembayaran (Lengkap dengan Info Kembalian)
    # -------------------------------------------------------------------------
    def build_receipt_text(self, receipt):
        """Menyusun teks struk kasir dengan format string .ljust() dan .rjust() rata kiri-kanan."""
        kasir_name = self.current_user["nama"] if self.current_user else "Kasir"
        cust_name = normalize_customer_label(
            receipt.get("customer_name", getattr(self, "customer_name", ""))
        ) or "Pelanggan Umum"
        w = 34  # Lebar standar kertas thermal printer monospaced
        sep_double = "=" * w
        sep_single = "-" * w
        customer_name_lines = textwrap.wrap(
            cust_name, width=17, break_long_words=True, break_on_hyphens=False
        )
        customer_lines = [
            "Pelanggan".ljust(15) + f": {customer_name_lines[0]}".rjust(w - 15)
        ]
        customer_lines.extend(
            " " * 15 + name_part.rjust(w - 15)
            for name_part in customer_name_lines[1:]
        )

        lines = [
            sep_double,
            "KOPI NAKO".center(w),
            "STRUK PEMBAYARAN".center(w),
            sep_double,
            "No. Transaksi".ljust(15) + f": KN-{receipt['id']}".rjust(w - 15),
            "Tanggal".ljust(15) + f": {receipt['date']}".rjust(w - 15),
            "Waktu".ljust(15) + f": {receipt['time']}".rjust(w - 15),
            "Kasir".ljust(15) + f": {kasir_name}".rjust(w - 15),
            *customer_lines,
            "Metode Bayar".ljust(15) + f": {receipt['payment']}".rjust(w - 15),
            sep_single,
            "ITEM PESANAN".ljust(20) + "SUBTOTAL".rjust(w - 20),
            sep_single,
        ]
        for item in receipt["items"]:
            name = item["name"]
            sub_str = rp(item["subtotal"])
            if len(name) > (w - len(sub_str) - 1):
                name = name[:(w - len(sub_str) - 3)] + ".."
            lines.append(name.ljust(w - len(sub_str)) + sub_str)
            lines.append(f"  {item['qty']} x {rp(item['price'])}".ljust(w))

        bayar_val = receipt.get("bayar", receipt["total"])
        kembalian_val = receipt.get("kembalian", 0)

        lines.extend([
            sep_single,
            "TOTAL TAGIHAN".ljust(18) + rp(receipt["total"]).rjust(w - 18),
            "TOTAL BAYAR".ljust(18) + rp(bayar_val).rjust(w - 18),
            "KEMBALIAN".ljust(18) + rp(kembalian_val).rjust(w - 18),
            sep_double,
            "Terima kasih atas pesanan Anda!".center(w),
            "Instagram: @kopi.nako".center(w),
            sep_double,
        ])
        return "\n".join(lines)

    def show_receipt(self, receipt):
        """Menampilkan dialog popup berisi struk belanja berlatar putih bersih (#FFFFFF) & font Monospace."""
        receipt_text = self.build_receipt_text(receipt)
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        # Kontainer kertas struk berlatar putih bersih (#FFFFFF) terpisah dari background modal
        paper_card = Card(
            orientation="vertical",
            padding=[dp(16), dp(12), dp(16), dp(12)],
            color=RECEIPT_PAPER,
            radius=12
        )
        scroll = ScrollView(do_scroll_x=False)
        font_kwargs = {"font_name": RECEIPT_FONT} if RECEIPT_FONT else {}
        receipt_label = Text(
            receipt_text,
            size=12,
            color=RECEIPT_TEXT,
            align="left",
            size_hint_y=None,
            **font_kwargs
        )
        receipt_label.bind(
            texture_size=lambda widget, size: setattr(widget, "height", size[1] + dp(16))
        )
        scroll.add_widget(receipt_label)
        paper_card.add_widget(scroll)
        content.add_widget(paper_card)

        receipt_popup = themed_popup(
            f"Struk Transaksi KN-{receipt['id']}", content,
            size_hint=(0.86, 0.86),
        )
        # Hanya judul popup yang diubah; teks struk tetap gelap di atas kertas putih.
        if hasattr(receipt_popup, "title_color"):
            receipt_popup.title_color = (1, 1, 1, 1)

        actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(10))
        actions.add_widget(button(
            "SIMPAN STRUK .TXT",
            lambda: self.save_receipt_file(receipt_text, receipt["id"]),
            True, 40
        ))
        actions.add_widget(button("TUTUP", receipt_popup.dismiss, False, 40))
        content.add_widget(actions)

        receipt_popup.open()

    def save_receipt_file(self, receipt_text, transaction_id):
        """Menyimpan struk nota kasir ke berkas fisik (.txt) di folder Dokumen pengguna."""
        try:
            folder = Path.home() / "Documents" / "POS Kopi Nako" / "Struk"
            folder.mkdir(parents=True, exist_ok=True)
            filename = folder / f"struk_KN-{transaction_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filename.write_text(receipt_text, encoding="utf-8")
            self.notice(f"Struk berhasil disimpan di:\n{filename}")
        except OSError as error:
            self.notice(f"Gagal menyimpan struk:\n{error}")

    def show_saved_receipt(self, order):
        """Membuka dan menampilkan kembali struk transaksi yang tersimpan di database."""
        try:
            transaction_id = int(order["id"].replace("KN-", ""))
            details = self.db.get_order_details(transaction_id)
            receipt = {
                "id": transaction_id,
                "date": order["date"],
                "time": order["time"],
                "payment": order["payment"],
                "total": order["total"],
                "customer_name": order.get("customer_name", ""),
                "bayar": order.get("bayar", order["total"]),
                "kembalian": order.get("kembalian", 0),
                "items": [{
                    "name": item["nama"],
                    "qty": int(item["jumlah"]),
                    "price": float(item["harga"]),
                    "subtotal": float(item["subtotal"]),
                } for item in details],
            }
            self.show_receipt(receipt)
        except Exception as error:
            self.notice("Struk tidak dapat dibuka:\n" + str(error))

    # -------------------------------------------------------------------------
    # Dialog Notifikasi & Penghapusan Transaksi
    # -------------------------------------------------------------------------
    def confirm_delete_order(self, order):
        """Menampilkan dialog konfirmasi sebelum menghapus riwayat transaksi."""
        content = BoxLayout(
            orientation="vertical", padding=dp(16), spacing=dp(12)
        )
        content.add_widget(Text(
            f"Hapus catatan transaksi {order['id']}?\n"
            "Data transaksi akan dihapus permanen dari database.",
            align="center", size=14, color=TEXT
        ))
        popup = themed_popup(
            "Konfirmasi Pembatalan", content,
            size_hint=(0.82, None), height=dp(210),
        )
        _style_popup_text_white(popup, content)
        actions = BoxLayout(
            size_hint_y=None, height=dp(42), spacing=dp(8)
        )
        actions.add_widget(button("BATAL", popup.dismiss, False, 40))
        actions.add_widget(button("YA, HAPUS", lambda: self.delete_order(order, popup), True, 40))
        content.add_widget(actions)
        popup.open()

    def delete_order(self, order, popup):
        """Mengeksekusi penghapusan transaksi pada database."""
        try:
            transaction_id = int(order["id"].replace("KN-", ""))
            self.db.delete_order(transaction_id)
            self.refresh_data()
            self.refresh_report()
            popup.dismiss()
            self.sm.get_screen("reports").render()
            self.notice("Transaksi berhasil dihapus.")
        except Exception as error:
            self.notice("Transaksi gagal dihapus:\n" + str(error))

    def notice(self, message):
        """Menampilkan pesan pop-up informasi/peringatan dengan tema kafe yang rapi."""
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        message_label = Text(
            message, size=14, color=(1, 1, 1, 1), align="center", size_hint=(1, 1)
        )
        content.add_widget(message_label)
        dismiss_btn = button("MENGERTI", lambda: notice_popup.dismiss(), True, 38)
        content.add_widget(dismiss_btn)

        notice_popup = themed_popup(
            "Pemberitahuan", content,
            size_hint=(0.80, None),
            height=dp(190),
            auto_dismiss=True,
        )
        # Ubah warna judul popup menjadi putih bila properti tersedia.
        if hasattr(notice_popup, "title_color"):
            notice_popup.title_color = (1, 1, 1, 1)
        notice_popup.open()