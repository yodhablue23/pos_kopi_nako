"""Titik masuk utama (Entry Point) aplikasi POS Kopi Nako.

File ini berfungsi sebagai gerbang utama untuk menjalankan aplikasi.
Cara menjalankan aplikasi:
    python main.py

Keterangan Konsep Pemrograman:
Blok 'if __name__ == "__main__":' memastikan bahwa kode di dalamnya hanya akan
dieksekusi jika berkas ini dijalankan secara langsung sebagai program utama,
dan tidak akan dieksekusi jika berkas ini diimpor oleh modul lain.
"""
from kivy.config import Config

mouse_input = Config.get("input", "mouse")
mouse_options = [option.strip() for option in mouse_input.split(",")]
if "disable_multitouch" not in mouse_options:
    Config.set("input", "mouse", ",".join(mouse_options + ["disable_multitouch"]))

from app_controller import POSApp

if __name__ == "__main__":
    # Membuat instance aplikasi POS dan memulai event loop Kivy
    POSApp().run()
