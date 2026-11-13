# POS Kopi Nako (Point of Sale)

Aplikasi kasir desktop kafe **Kopi Nako** yang dibangun menggunakan bahasa pemrograman Python dengan antarmuka grafis (GUI) **Kivy** dan dukungan database relasional ganda (**SQLite** dan **MySQL**).

---

## Fitur Utama

1. **Autentikasi Kasir & Admin:**
   - Password diamankan menggunakan algoritma hashing standar industri: `PBKDF2-HMAC-SHA256` dengan salt acak 16-byte untuk mencegah kebocoran data dan *timing attack*.
2. **Dashboard Statistik (Home):**
   - Menampilkan tanggal, jam digital *real-time*, omzet penjualan hari ini, jumlah transaksi, status database, dan akses cepat.
3. **Katalog Produk & Kasir (Products):**
   - Pencarian instan berdasarkan nama menu (*real-time search*).
   - Filter kategori (Semua, Kopi, Non Kopi, Makanan).
   - Indikator sisa stok otomatis.
4. **Keranjang Belanja (Cart):**
   - Penyesuaian jumlah item secara fleksibel (`+` dan `-`).
   - Kalkulasi subtotal dan total harga secara otomatis.
   - Pilihan metode pembayaran kasir: Tunai, QRIS, dan Kartu.
5. **Manajemen Transaksi & Laporan (Reports):**
   - Rekap omzet penjualan harian dan sepanjang waktu.
   - Cetak ulang struk nota kasir di layar dan penyimpanan berkas struk fisik berformat `.txt` ke folder `Documents/POS Kopi Nako/Struk/`.
   - Pembatalan / penghapusan transaksi dengan konfirmasi modal.

---

## Struktur Berkas Proyek

```text
├── main.py              # Titik masuk utama (Entry Point) aplikasi
├── app_controller.py    # Logika alur aplikasi, keranjang, sesi kasir, dan struk
├── database.py          # Operasi database relasional (CRUD, transaksi SQL atomik)
├── screens.py           # Halaman visual Kivy (Login, Home, Produk, Keranjang, Laporan)
├── ui_components.py     # Komponen UI pembantu (Text, Card, Button, Format Rp)
├── config.py            # Konfigurasi jendela, palet warna kafe, dan data awal produk
├── db_config.py         # Pengaturan driver database (SQLite / MySQL)
├── requirements.txt     # Daftar pustaka yang dibutuhkan
├── assets/              # Aset gambar menu kopi dan logo Kopi Nako
└── pos_kopi_nako.db     # File database SQLite lokal (otomatis dibuat saat run)
```

---

## Cara Menjalankan Aplikasi

### 1. Persiapan Environment
Pastikan pustaka GUI Kivy telah terpasang:
```bash
pip install -r requirements.txt
```

### 2. Menjalankan Program
Jalankan file `main.py`:
```bash
python main.py
```

### 3. Akun Login Bawaan
- **Username:** `admin`
- **Password:** `KopiNako123!`

---

## Pengaturan Database: SQLite vs MySQL

Aplikasi ini dilengkapi arsitektur **Dual-Engine** pada `db_config.py`:

* **Mode SQLite (Bawaan / Default):**
  - Menggunakan modul bawaan Python (`sqlite3`).
  - Tidak perlu instalasi XAMPP atau MySQL server.
  - Sangat direkomendasikan saat pengujian dan demonstrasi tugas di depan dosen karena dijamin langsung berjalan lancar.

* **Mode MySQL:**
  - Ubah `DB_ENGINE = "mysql"` di dalam `db_config.py`.
  - Pastikan server MySQL (XAMPP) sudah aktif di komputer Anda.
