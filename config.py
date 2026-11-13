"""Konfigurasi tampilan, palet warna, dan data awal POS Kopi Nako.

Modul ini memusatkan seluruh pengaturan antarmuka pengguna:
1. Konfigurasi jendela aplikasi (judul, ukuran minimal, warna latar belakang).
2. Palet warna tema kafe kopi (kontras tinggi, nyaman dipandang, dan rapi).
3. Data awal katalog menu (seed products) yang otomatis masuk ke database.
"""
from pathlib import Path

# Coba impor Window dari Kivy secara aman agar modul konfigurasi tetap dapat diimpor
# oleh modul pengujian database tanpa harus mewajibkan Kivy aktif terlebih dahulu.
try:
    from kivy.config import Config
    Config.set("graphics", "minimum_width", "720")
    Config.set("graphics", "minimum_height", "600")
    from kivy.core.window import Window
except ImportError:
    Window = None

# -------------------------------------------------------------------------
# 1. Konfigurasi Path Aset dan Gambar
# -------------------------------------------------------------------------
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo_kopi_nako.jpg"
BARCODE_PATH = ASSETS_DIR / "barcode_ewallet.png"
PRODUCT_IMAGE_DIR = ASSETS_DIR / "products"

# Pemetaan nama produk ke file gambar di dalam folder assets/products/
PRODUCT_IMAGES = {
    "Es Kopi Nako": "es_kopi_nako.jpg",
    "Kopi Susu Gula Aren": "kopi_susu_gula_aren.jpg",
    "Americano": "americano.jpg",
    "Cappuccino": "cappuccino.jpg",
    "Matcha Latte": "matcha_latte.jpg",
    "Cokelat": "cokelat.jpg",
    "Roti Bakar": "roti_bakar.jpg",
    "Pisang Goreng": "pisang_goreng.jpg",
}

# -------------------------------------------------------------------------
# 2. Pengaturan Jendela Aplikasi Kivy
# -------------------------------------------------------------------------
if Window is not None:
    Window.title = "POS Kopi Nako"
    if LOGO_PATH.exists():
        Window.icon = str(LOGO_PATH)

    # Batas minimum sudah ditetapkan melalui Config sebelum Window dibuat.
    Window.size = (1100, 760)

    # Warna latar belakang jendela (abu-abu kebiruan sangat lembut, format RGBA 0-1)
    Window.clearcolor = (0.965, 0.945, 0.905, 1.0)


# -------------------------------------------------------------------------
# 3. Palet Warna Coffee Premium — espresso, oat milk, dan jade teal
# Seluruh warna memakai RGBA (0-1).
COFFEE = (0.16, 0.095, 0.065, 1.0)      # Espresso pekat
BROWN = (0.34, 0.19, 0.12, 1.0)        # Roast brown
CREAM = (0.98, 0.94, 0.84, 1.0)        # Oat milk
WHITE = (1.00, 0.99, 0.96, 1.0)        # Warm white
MUTED = (0.48, 0.42, 0.36, 1.0)        # Taupe
GREEN = (0.20, 0.43, 0.31, 1.0)
TEAL = (0.04, 0.39, 0.35, 1.0)         # Deep jade
CORAL = (0.72, 0.29, 0.20, 1.0)        # Terracotta
PURPLE = (0.38, 0.25, 0.19, 1.0)      # Roast accent
BLUE = (0.20, 0.37, 0.34, 1.0)
GOLD = (0.78, 0.53, 0.20, 1.0)
MINT = (0.88, 0.92, 0.84, 1.0)
PEACH = (0.96, 0.87, 0.76, 1.0)
LILAC = (0.91, 0.86, 0.79, 1.0)
SKY = (0.97, 0.94, 0.88, 1.0)

PASTEL_BY_CATEGORY = {
    "Kopi": (0.96, 0.91, 0.82, 1.0),
    "Non Kopi": (0.88, 0.93, 0.85, 1.0),
    "Makanan": (0.98, 0.88, 0.77, 1.0),
}
ART_BY_CATEGORY = {
    "Kopi": (0.36, 0.22, 0.14, 1.0),
    "Non Kopi": (0.18, 0.43, 0.34, 1.0),
    "Makanan": (0.73, 0.38, 0.20, 1.0),
}
STAT_CARD_COLORS = [CREAM, MINT, PEACH, LILAC]
NAV_COLORS = {
    "home": TEAL,
    "products": BROWN,
    "cart": GREEN,
    "reports": PURPLE,
}
BUTTON_STYLES = {
    "BUKA MENU PRODUK": TEAL,
    "TAMBAH +": BROWN,
    "LIHAT STRUK": BLUE,
    "HAPUS": CORAL,
    "YA, HAPUS": CORAL,
    "LANJUT PEMBAYARAN": TEAL,
    "TRANSAKSI BARU": BROWN,
    "KOSONGKAN KERANJANG": GOLD,
    "Tunai": GREEN,
    "QRIS": BLUE,
    "Tunai (Uang Cash)": GREEN,
    "Saldo E-Wallet (Barcode)": BLUE,
    "Kartu": PURPLE,
    "Kartu Debit Digital": PURPLE,
    "VERIFIKASI & BAYAR": GREEN,
    "PROSES PEMBAYARAN": GREEN,
    "SELESAIKAN PEMBAYARAN": GREEN,
    "MASUK": TEAL,
    "KELUAR": CORAL,
}

# -------------------------------------------------------------------------
# 4. Data Awal Produk (Seed Data)
# -------------------------------------------------------------------------
# Data ini otomatis dimasukkan ke database pada saat pertama kali aplikasi dijalankan
SEED_PRODUCTS = [
    {"name": "Es Kopi Nako", "category": "Kopi", "price": 18000, "stok": 100},
    {"name": "Kopi Susu Gula Aren", "category": "Kopi", "price": 22000, "stok": 100},
    {"name": "Americano", "category": "Kopi", "price": 16000, "stok": 100},
    {"name": "Cappuccino", "category": "Kopi", "price": 20000, "stok": 100},
    {"name": "Matcha Latte", "category": "Non Kopi", "price": 22000, "stok": 100},
    {"name": "Cokelat", "category": "Non Kopi", "price": 21000, "stok": 100},
    {"name": "Roti Bakar", "category": "Makanan", "price": 15000, "stok": 100},
    {"name": "Pisang Goreng", "category": "Makanan", "price": 14000, "stok": 100},
]