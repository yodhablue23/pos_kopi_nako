"""Pengaturan konfigurasi database POS Kopi Nako.

File ini mendukung dua pilihan engine database:
1. "sqlite" (Default, Sangat Direkomendasikan untuk tugas/dosen):
   - Menggunakan pustaka bawaan standar Python (sqlite3).
   - Tidak memerlukan instalasi server tambahan (tidak perlu XAMPP).
   - Data otomatis tersimpan ke file lokal 'pos_kopi_nako.db'.

2. "mysql":
   - Menggunakan server MySQL lokal (misalnya melalui XAMPP).
   - Memerlukan paket 'mysql-connector-python' terpasang dan service MySQL berjalan.
"""
import os
from pathlib import Path

# Pilihan driver database: "sqlite" atau "mysql"
# Disetel ke "sqlite" agar langsung berjalan lancar di komputer dosen tanpa perlu menyalakan XAMPP.
DB_ENGINE = "sqlite"

# Lokasi penyimpanan file database SQLite
BASE_DIR = Path(__file__).resolve().parent
SQLITE_DB_PATH = BASE_DIR / "pos_kopi_nako.db"

# Pengaturan koneksi MySQL (aktif jika DB_ENGINE diubah menjadi "mysql")
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": os.environ.get("POS_DB_PASSWORD", ""),
    "database": "pos_kopi_nako",
}

# Alias kompatibilitas mundur untuk kode lama yang mengimpor DB_CONFIG
DB_CONFIG = MYSQL_CONFIG