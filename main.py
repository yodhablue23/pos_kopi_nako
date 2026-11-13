"""Titik masuk utama (Entry Point) aplikasi POS Kopi Nako.

File ini berfungsi sebagai gerbang utama untuk menjalankan aplikasi.
Cara menjalankan aplikasi:
    python main.py

Keterangan Konsep Pemrograman:
Blok 'if __name__ == "__main__":' memastikan bahwa kode di dalamnya hanya akan
dieksekusi jika berkas ini dijalankan secara langsung sebagai program utama,
dan tidak akan dieksekusi jika berkas ini diimpor oleh modul lain.
"""
from app_controller import POSApp

if __name__ == "__main__":
    # Membuat instance aplikasi POS dan memulai event loop Kivy
    POSApp().run()
