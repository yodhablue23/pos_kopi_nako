POS KOPI NAKO - STRUKTUR MODULAR

File:
- main.py: titik masuk aplikasi
- app_controller.py: alur aplikasi, login/logout, checkout, struk, navigasi
- database.py: koneksi dan operasi MySQL
- screens.py: halaman Kivy
- ui_components.py: komponen UI reusable
- config.py: warna, aset, dan produk awal
- db_config.py: salin dari project lama (jangan bagikan karena berisi kredensial)
- assets/: salin dari project lama

PENTING:
1. Jangan mengganti db_config.py dan folder assets lama.
2. Backup database sebelum uji.
3. Jalankan dengan environment project: python main.py
