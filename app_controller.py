"""Pengendali alur aplikasi (Application Controller) POS Kopi Nako.

Modul ini adalah pusat logika aplikasi kasir (State Manager) yang mengontrol:
1. Autentikasi sesi kasir (login, logout, hak akses).
2. Navigasi antar halaman melalui Kivy ScreenManager.
3. Keranjang belanja kasir (tambah item, kurangi item, hitung total harga).
4. Alur transaksi checkout, penerimaan uang tunai & kalkulasi kembalian real-time.
5. Pencetakan struk pembayaran lengkap dan ekspor berkas fisik .txt.
"""
from datetime import datetime, timedelta
import csv
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

from config import ASSETS_DIR, BARCODE_PATH, LOGO_PATH, VOUCHER_CODES
from theme import (
    ACCENT, ACCENT_ALT, ACCENT_TEXT, ACCENT_THEMES, BORDER, CORAL, DANGER_TEXT,
    MUTED, NAV_COLORS, ON_ACCENT, RECEIPT_PAPER, RECEIPT_TEXT, SUCCESS_TEXT,
    SURFACE, TEAL, TEXT, WHITE, apply_theme,
)
from database import (
    Database, MAX_CUSTOMER_LABEL_LENGTH, MAX_PRODUCT_STOCK,
    normalize_customer_label, normalize_product_name,
)
import role_admin
import role_kasir
import role_pelanggan
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
        self.order_type = "Dine-In" # Tipe layanan: 'Dine-In' atau 'Take Away'
        self.voucher_code = ""      # Kode promo voucher aktif
        self.cart_notes = {}        # Catatan kustomisasi racikan per product_id
        self.theme_settings_path = Path.home() / "Documents" / "POS Kopi Nako" / "settings.json"
        self.theme_mode, self.theme_accent = self.load_theme_preferences()
        apply_theme(self.theme_mode, self.theme_accent)
        self.db = Database()
        self.db_error = None
        self.report_period = "daily"
        self.report_orders = []
        self.report_top_products = []
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

        # Root layout horizontal: Sidebar Kiri + Kolom Utama (Top Header Bar + ScreenManager)
        root = BoxLayout(orientation="horizontal", spacing=0)
        self.main_column = BoxLayout(orientation="vertical", spacing=0)
        self.main_column.add_widget(self.sm)
        root.add_widget(self.main_column)

        # Top Header Bar ala Dashboard POS Referensi
        self.top_bar = Card(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(54),
            padding=[dp(18), dp(8), dp(18), dp(8)],
            spacing=dp(10),
            color=SURFACE,
            radius=0,
            border_color=BORDER,
        )
        self.menu_icon_box = Card(
            orientation="vertical",
            size_hint=(None, None),
            size=(dp(34), dp(34)),
            color=tuple(ACCENT[:3]) + (0.14,),
            radius=8,
        )
        self.menu_icon_label = Text("=", size=16, bold=True, color=ACCENT_TEXT, align="center")
        self.menu_icon_box.add_widget(self.menu_icon_label)
        self.menu_icon_box.bind(on_touch_down=self.toggle_navigation)
        self.top_bar.add_widget(self.menu_icon_box)

        self.top_bar_title = Text(
            "Dashboard", size=15, bold=True, color=TEXT,
            size_hint_x=None, width=dp(240),
        )
        self.top_bar.add_widget(self.top_bar_title)
        self.top_bar.add_widget(BoxLayout())  # Spacer tengah

        self.theme_btn = button(
            "TEMA", self.open_global_theme_settings, False, 34,
            outline=True, outline_color=BORDER,
        )
        self.theme_btn.size_hint_x = None
        self.theme_btn.width = dp(76)
        self.top_bar.add_widget(self.theme_btn)

        self.notif_badge = Card(
            orientation="vertical",
            size_hint=(None, None),
            size=(dp(36), dp(36)),
            color=(0.45, 0.48, 0.56, 0.12),
            radius=18,
        )
        self.notif_label = Text("0", size=11, bold=True, color=TEXT, align="center")
        self.notif_badge.add_widget(self.notif_label)
        self.top_bar.add_widget(self.notif_badge)

        self.top_user_label = Text(
            "", size=11, bold=True, color=MUTED,
            size_hint_x=None, width=dp(135), align="right",
        )
        self.top_bar.add_widget(self.top_user_label)

        self.avatar_badge = Card(
            orientation="vertical",
            size_hint=(None, None),
            size=(dp(36), dp(36)),
            color=tuple(ACCENT[:3]) + (0.18,),
            radius=18,
        )
        self.avatar_label = Text(
            "A", size=13, bold=True, color=ACCENT_TEXT, align="center"
        )
        self.avatar_badge.add_widget(self.avatar_label)
        self.top_bar.add_widget(self.avatar_badge)

        def adapt_top_bar(_widget, width):
            narrow = width < dp(680)
            self.top_bar.padding = [dp(8 if narrow else 18), dp(8), dp(8 if narrow else 18), dp(8)]
            self.top_bar.spacing = dp(6 if narrow else 10)
            self.top_bar_title.width = dp(105 if narrow else 240)
            self.top_bar_title.font_size = dp(13 if narrow else 15)
            self.theme_btn.width = dp(58 if narrow else 76)
            self.notif_badge.width = dp(0 if narrow else 36)
            self.notif_badge.opacity = 0 if narrow else 1
            self.top_user_label.width = dp(0 if narrow else 135)
            self.top_user_label.opacity = 0 if narrow else 1

        self.top_bar.bind(width=adapt_top_bar)
        adapt_top_bar(self.top_bar, self.top_bar.width)

        # Sidebar Navigasi Kiri bergaya Brand Header (Logo + Kopi Nako di Kiri Atas)
        self.nav_wrapper = Card(
            orientation="vertical",
            size_hint=(None, 1),
            width=dp(162),
            padding=[dp(12), dp(14), dp(12), dp(14)],
            spacing=dp(8),
            color=SURFACE,
            radius=0,
            border_color=BORDER,
        )
        brand_header = BoxLayout(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(44),
            spacing=dp(10),
        )
        self.brand_box = Card(
            orientation="vertical",
            size_hint=(None, None),
            size=(dp(38), dp(38)),
            padding=dp(3),
            color=ACCENT,
            radius=10,
        )
        if LOGO_PATH.exists():
            self.brand_label = None
            self.brand_box.add_widget(Image(
                source=str(LOGO_PATH),
                size_hint=(1, 1),
                fit_mode="contain",
            ))
        else:
            self.brand_label = Text(
                "KN", size=14, bold=True, color=ON_ACCENT, align="center"
            )
            self.brand_box.add_widget(self.brand_label)
        brand_header.add_widget(self.brand_box)

        brand_titles = BoxLayout(orientation="vertical", spacing=dp(1))
        self.brand_title_text = Text(
            "Kopi Nako", size=14, bold=True, color=TEXT,
            size_hint_y=None, height=dp(22),
        )
        self.brand_sub_text = Text(
            "POS System", size=9, color=MUTED,
            size_hint_y=None, height=dp(14),
        )
        brand_titles.add_widget(self.brand_title_text)
        brand_titles.add_widget(self.brand_sub_text)
        brand_header.add_widget(brand_titles)
        self.nav_wrapper.add_widget(brand_header)

        self.sidebar_section_label = Text(
            "NAVIGASI", size=9, bold=True, color=MUTED,
            size_hint_y=None, height=dp(20),
        )
        self.nav_wrapper.add_widget(self.sidebar_section_label)

        nav = GridLayout(
            cols=1, size_hint=(1, None), spacing=dp(8)
        )
        nav.bind(minimum_height=nav.setter("height"))
        self.nav = nav
        self.nav_buttons = {}
        for title, screen in [
            ("HOME", "home"),
            ("PRODUK", "products"),
            ("KERANJANG", "cart"),
            ("LAPORAN", "reports"),
        ]:
            b = button(title, lambda s=screen: self.go(s), False, 42)
            b.font_size = dp(11)
            self.nav_buttons[screen] = b
            nav.add_widget(b)

        self.nav_wrapper.add_widget(nav)
        self.nav_wrapper.add_widget(BoxLayout())  # Spacer pendorong tombol keluar ke bawah

        self.logout_button = button("KELUAR", self.logout, True, 42)
        self.logout_button.font_size = dp(11)
        self.nav_wrapper.add_widget(self.logout_button)
        self.root_layout = root
        self._navigation_hidden_for_width = False
        root.bind(width=self._adapt_navigation_for_width)

        # Di halaman login: sidebar & top_bar tidak ditampilkan agar halaman login bersih
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

    def open_global_theme_settings(self):
        """Membuka dialog pengaturan tampilan dari Top Header Bar di halaman mana saja."""
        if hasattr(self, "sm"):
            home_screen = self.sm.get_screen("home")
            if hasattr(home_screen, "open_theme_settings"):
                home_screen.open_theme_settings()

    def _show_app_shell(self):
        """Menampilkan Sidebar Kiri dan Top Header Bar setelah login berhasil."""
        if hasattr(self, "root_layout") and self.nav_wrapper not in self.root_layout.children:
            self.root_layout.add_widget(self.nav_wrapper, index=len(self.root_layout.children))
        if hasattr(self, "main_column") and hasattr(self, "top_bar"):
            if self.top_bar not in self.main_column.children:
                self.main_column.add_widget(self.top_bar, index=len(self.main_column.children))
        self.nav_wrapper.opacity = 1
        self.nav_wrapper.disabled = False
        self.nav_wrapper.width = dp(162)

    def _adapt_navigation_for_width(self, _root, width):
        if self.user_role() is None:
            return
        if width < dp(740):
            if self.nav_wrapper in self.root_layout.children:
                self.root_layout.remove_widget(self.nav_wrapper)
                self._navigation_hidden_for_width = True
        elif self._navigation_hidden_for_width:
            if self.nav_wrapper not in self.root_layout.children:
                self.root_layout.add_widget(
                    self.nav_wrapper, index=len(self.root_layout.children)
                )
                self.nav_wrapper.opacity = 1
                self.nav_wrapper.disabled = False
                self.nav_wrapper.width = dp(162)
            self._navigation_hidden_for_width = False

    def toggle_navigation(self, widget, touch):
        """Membuka atau menutup sidebar melalui tombol garis di header."""
        if self.sm.current == "login" or not widget.collide_point(*touch.pos):
            return False

        if self.nav_wrapper in self.root_layout.children:
            self.root_layout.remove_widget(self.nav_wrapper)
        else:
            self.root_layout.add_widget(
                self.nav_wrapper, index=len(self.root_layout.children)
            )
            self.nav_wrapper.opacity = 1
            self.nav_wrapper.disabled = False
            self.nav_wrapper.width = dp(162)
        self._navigation_hidden_for_width = False
        return True

    def _hide_app_shell(self):
        """Menyembunyikan Sidebar Kiri dan Top Header Bar saat kembali ke halaman login."""
        if hasattr(self, "root_layout") and self.nav_wrapper in self.root_layout.children:
            self.root_layout.remove_widget(self.nav_wrapper)
        if hasattr(self, "main_column") and hasattr(self, "top_bar"):
            if self.top_bar in self.main_column.children:
                self.main_column.remove_widget(self.top_bar)
        self.nav_wrapper.opacity = 0
        self.nav_wrapper.disabled = True

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
    def user_role(self):
        """Mengembalikan role pengguna aktif ('admin', 'kasir', 'pelanggan'), atau None jika belum login."""
        if not self.current_user:
            return None
        return self.current_user.get("role", "kasir")

    def role_permissions(self):
        """Mengembalikan dictionary izin aktif sesuai role pengguna yang sedang login."""
        role = self.user_role()
        role_map = {
            role_admin.ROLE_NAME: role_admin,
            role_kasir.ROLE_NAME: role_kasir,
            role_pelanggan.ROLE_NAME: role_pelanggan,
        }
        mod = role_map.get(role)
        if mod is None:
            return {
                "can_manage_products": False,
                "can_manage_stock": False,
                "can_delete_orders": False,
                "require_customer_label": False,
                "allowed_screens": (),
            }
        return {
            "can_manage_products": mod.CAN_MANAGE_PRODUCTS,
            "can_manage_stock": mod.CAN_MANAGE_STOCK,
            "can_delete_orders": mod.CAN_DELETE_ORDERS,
            "require_customer_label": mod.REQUIRE_CUSTOMER_LABEL,
            "allowed_screens": mod.ALLOWED_SCREENS,
        }

    def open_login_dialog(self, expected_role):
        """Meminta kredensial setelah pengguna memilih jenis akun."""
        role_labels = {
            "admin": "Admin",
            "kasir": "Kasir",
            "pelanggan": "Pelanggan",
        }
        role_label = role_labels.get(expected_role)
        if role_label is None:
            self.notice("Jenis akun tidak dikenal.")
            return

        content = BoxLayout(
            orientation="vertical", padding=dp(16), spacing=dp(10),
            size_hint_y=None, height=dp(180),
        )
        username_field = text_input("Username", height=44)
        password_field = text_input("Password", password=True, height=44)
        content.add_widget(username_field)
        content.add_widget(password_field)
        actions = BoxLayout(
            orientation="horizontal", spacing=dp(8),
            size_hint_y=None, height=dp(44),
        )
        login_popup = None

        def submit_login(*_):
            if self.login(
                username_field.text,
                password_field.text,
                expected_role=expected_role,
            ):
                login_popup.dismiss()

        actions.add_widget(button(
            "BATAL", lambda *_: login_popup.dismiss(),
            False, 44, outline=True,
        ))
        actions.add_widget(button("MASUK", submit_login, True, 44))
        content.add_widget(actions)
        password_field.bind(on_text_validate=submit_login)

        login_popup = themed_popup(
            f"Login sebagai {role_label}", content,
            size_hint=(0.86, None), height=dp(260),
            auto_dismiss=True,
        )
        _style_popup_text_white(login_popup, content)
        login_popup.open()

    def login(self, username, password, expected_role=None):
        """Memproses login pengguna dengan verifikasi kredensial dan jenis akun."""
        if self.db_error:
            self.notice(
                f"Database ({self.db.engine}) belum tersambung:\n{self.db_error}"
            )
            return False
        if not username.strip() or not password:
            self.notice("Username dan password wajib diisi.")
            return False

        try:
            user = self.db.authenticate_user(username, password)
        except Exception as error:
            self.notice("Login gagal karena kendala database:\n" + str(error))
            return False

        if user is None:
            self.notice("Username atau password salah.")
            return False
        if expected_role is not None and user["role"] != expected_role:
            self.notice("Akun ini bukan akun " + expected_role + ".")
            return False

        # Login berhasil
        self.current_user = user
        self.cart.clear()
        self.cart_notes.clear()
        self.customer_name = ""
        self.order_type = "Dine-In"
        self.voucher_code = ""
        self._show_app_shell()
        target_screen = "products" if self.user_role() == "pelanggan" else "home"
        self.sm.current = target_screen
        self._adapt_navigation_for_width(self.root_layout, self.root_layout.width)
        self.refresh_data()
        self.refresh_report()
        self.update_nav()
        self.sm.get_screen(target_screen).render()
        return True

    def login_as_customer(self):
        """Jalan pintas Self-Order Pelanggan tanpa mengetik password."""
        if self.db_error:
            self.notice(
                f"Database ({self.db.engine}) belum tersambung:\n{self.db_error}"
            )
            return

        self.current_user = role_pelanggan.build_customer_session()
        self.cart.clear()
        self.cart_notes.clear()
        self.customer_name = ""
        self.order_type = "Dine-In"
        self.voucher_code = ""
        self._show_app_shell()
        self.sm.current = "products"
        self._adapt_navigation_for_width(self.root_layout, self.root_layout.width)
        self.refresh_data()
        self.refresh_report()
        self.update_nav()
        self.sm.get_screen("products").render()

    def open_customer_registration(self):
        """Membuka formulir pendaftaran akun pelanggan."""
        if self.db_error:
            self.notice(
                f"Database ({self.db.engine}) belum tersambung:\n{self.db_error}"
            )
            return

        content = BoxLayout(
            orientation="vertical", padding=dp(16), spacing=dp(8),
            size_hint_y=None, height=dp(330),
        )
        content.add_widget(Text(
            "Daftar untuk membuat akun pelanggan.",
            size=12, color=WHITE, align="center",
            size_hint_y=None, height=dp(28),
        ))
        name_field = text_input("Nama lengkap", height=44)
        username_field = text_input("Username", height=44)
        password_field = text_input("Password (minimal 6 karakter)", password=True, height=44)
        confirm_field = text_input("Konfirmasi password", password=True, height=44)
        content.add_widget(name_field)
        content.add_widget(username_field)
        content.add_widget(password_field)
        content.add_widget(confirm_field)

        actions = BoxLayout(
            orientation="horizontal", spacing=dp(8),
            size_hint_y=None, height=dp(44),
        )
        register_popup = None

        def submit_registration(*_):
            name = name_field.text.strip()
            username = username_field.text.strip()
            password = password_field.text
            confirm = confirm_field.text
            if password != confirm:
                self.notice("Konfirmasi password tidak sama.")
                return
            try:
                user = self.db.register_customer(username, name, password)
            except ValueError as error:
                self.notice(str(error))
                return
            except Exception as error:
                self.notice("Registrasi gagal:\n" + str(error))
                return

            if register_popup is not None:
                register_popup.dismiss()
            self.current_user = user
            self.cart.clear()
            self.cart_notes.clear()
            self.customer_name = ""
            self.order_type = "Dine-In"
            self.voucher_code = ""
            self._show_app_shell()
            self.sm.current = "products"
            self._adapt_navigation_for_width(self.root_layout, self.root_layout.width)
            self.refresh_data()
            self.refresh_report()
            self.update_nav()
            self.sm.get_screen("products").render()
            self.notice("Registrasi berhasil. Selamat datang!")

        cancel_btn = button("BATAL", lambda *_: register_popup.dismiss(), False, 44, outline=True)
        register_btn = button("DAFTAR", submit_registration, True, 44)
        actions.add_widget(cancel_btn)
        actions.add_widget(register_btn)
        content.add_widget(actions)

        register_popup = themed_popup(
            "Daftar Akun Pelanggan", content,
            size_hint=(0.86, None), height=dp(390),
            auto_dismiss=False,
        )
        _style_popup_text_white(register_popup, content)
        register_popup.open()

    def logout(self):
        """Mengakhiri sesi kasir dan mengembalikan layar ke halaman login."""
        if self.sm.current == "login":
            return
        self.current_user = None
        self.cart.clear()
        self.cart_notes.clear()
        self.customer_name = ""
        self.order_type = "Dine-In"
        self.voucher_code = ""
        self._hide_app_shell()
        self.sm.current = "login"
        self.update_nav()
        self.sm.get_screen("login").render()
        self.notice("Anda telah berhasil logout.")

    def go(self, name):
        """Berpindah ke halaman lain dengan validasi login dan hak akses role."""
        if self.current_user is None:
            self._hide_app_shell()
            self.sm.current = "login"
            return
        if self.db_error:
            self.notice("Database belum tersambung. Periksa konfigurasi db_config.py.")
            return
        if self.user_role() == "pelanggan" and name in ("home", "reports"):
            self.notice("Halaman ini hanya untuk Kasir dan Admin.")
            return
        allowed_screens = self.role_permissions().get("allowed_screens", ())
        if allowed_screens and name not in allowed_screens:
            self.notice("Halaman ini tidak tersedia untuk peran Anda.")
            return
        self.sm.current = name
        self.update_nav()
        self.sm.get_screen(name).render()

    def update_nav(self):
        """Memperbarui Sidebar Kiri dan Top Header Bar secara dinamis sesuai role aktif."""
        allowed = self.role_permissions().get(
            "allowed_screens", ("home", "products", "cart", "reports")
        )
        if not allowed:
            allowed = ("home", "products", "cart", "reports")

        if hasattr(self, "nav"):
            self.nav.clear_widgets()
            visible_screens = [
                screen for screen in ("home", "products", "cart", "reports")
                if screen in allowed and screen in self.nav_buttons
            ]
            self.nav.cols = 1
            for screen in visible_screens:
                btn = self.nav_buttons[screen]
                btn.disabled = False
                btn.opacity = 1
                self.nav.add_widget(btn)
            if hasattr(self, "logout_button"):
                self.logout_button.disabled = False
                self.logout_button.opacity = 1

        for name, btn in self.nav_buttons.items():
            active = self.sm.current == name
            if active:
                solid_color = list(NAV_COLORS.get(name, ACCENT))
                if hasattr(btn, "_bg_color"):
                    btn._bg_color.rgba = solid_color
                btn._bg_default = solid_color
                btn._text_default = list(ON_ACCENT)
                btn.color = ON_ACCENT
            else:
                inactive_bg = tuple(SURFACE[:3]) + (0.65,)
                if hasattr(btn, "_bg_color"):
                    btn._bg_color.rgba = inactive_bg
                btn._bg_default = inactive_bg
                btn._text_default = list(TEXT)
                btn.color = TEXT
        if hasattr(self, "logout_button"):
            if hasattr(self.logout_button, "_bg_color"):
                self.logout_button._bg_color.rgba = CORAL
            self.logout_button._bg_default = list(CORAL)
            self.logout_button._text_default = list(ON_ACCENT)
            self.logout_button.color = ON_ACCENT

        # Sinkronisasi warna Sidebar Kiri & Top Header Bar dengan tema aktif (Light/Dark + Aksen)
        if hasattr(self, "nav_wrapper"):
            if hasattr(self.nav_wrapper, "_bg_color"):
                self.nav_wrapper._bg_color.rgba = SURFACE
            if hasattr(self.nav_wrapper, "_outline_color"):
                self.nav_wrapper._outline_color.rgba = BORDER
        if hasattr(self, "top_bar"):
            if hasattr(self.top_bar, "_bg_color"):
                self.top_bar._bg_color.rgba = SURFACE
            if hasattr(self.top_bar, "_outline_color"):
                self.top_bar._outline_color.rgba = BORDER
        if hasattr(self, "brand_box") and hasattr(self.brand_box, "_bg_color"):
            self.brand_box._bg_color.rgba = ACCENT
        if getattr(self, "brand_label", None) is not None:
            self.brand_label.color = ON_ACCENT
        if hasattr(self, "brand_title_text"):
            self.brand_title_text.color = TEXT
        if hasattr(self, "brand_sub_text"):
            self.brand_sub_text.color = MUTED
        if hasattr(self, "sidebar_section_label"):
            self.sidebar_section_label.color = MUTED
        if hasattr(self, "menu_icon_box") and hasattr(self.menu_icon_box, "_bg_color"):
            self.menu_icon_box._bg_color.rgba = tuple(ACCENT[:3]) + (0.14,)
        if hasattr(self, "menu_icon_label"):
            self.menu_icon_label.color = ACCENT_TEXT
        if hasattr(self, "theme_btn"):
            theme_bg = tuple(ACCENT[:3]) + (0.10,)
            self.theme_btn.color = TEXT
            self.theme_btn._text_default = list(TEXT)
            self.theme_btn._bg_default = theme_bg
            self.theme_btn._bg_pressed = list(ACCENT)
            if hasattr(self.theme_btn, "_line_color"):
                self.theme_btn._line_color.rgba = BORDER
            if hasattr(self.theme_btn, "_bg_color"):
                self.theme_btn._bg_color.rgba = theme_bg
        if hasattr(self, "notif_badge") and hasattr(self.notif_badge, "_bg_color"):
            self.notif_badge._bg_color.rgba = tuple(ACCENT[:3]) + (0.14,)
        if hasattr(self, "avatar_badge") and hasattr(self.avatar_badge, "_bg_color"):
            self.avatar_badge._bg_color.rgba = tuple(ACCENT[:3]) + (0.18,)
        if hasattr(self, "avatar_label"):
            self.avatar_label.color = ACCENT_TEXT

        # Perbarui informasi pada Top Header Bar
        page_titles = {
            "home": "Dashboard",
            "products": "Katalog Produk",
            "cart": "Keranjang Pesanan",
            "reports": "Laporan Penjualan",
        }
        if hasattr(self, "top_bar_title"):
            self.top_bar_title.text = page_titles.get(self.sm.current, "POS Kopi Nako")
            self.top_bar_title.color = TEXT
        if hasattr(self, "top_user_label") and hasattr(self, "avatar_label"):
            self.top_user_label.color = MUTED
            if self.current_user:
                user_name = str(self.current_user.get("nama", "User"))
                role_label = str(self.current_user.get("role", "")).upper()
                self.top_user_label.text = f"{user_name} ({role_label})"
                self.avatar_label.text = user_name[:1].upper() if user_name else "U"
            else:
                self.top_user_label.text = ""
                self.avatar_label.text = "U"
        if hasattr(self, "notif_label"):
            if self.user_role() == "pelanggan":
                cart_count = sum(self.cart.values())
                self.notif_label.text = f"{cart_count}"
                self.notif_label.color = ACCENT_TEXT if cart_count > 0 else TEXT
            else:
                low_count = sum(1 for p in getattr(self, "products", []) if int(p.get("stok", 0)) < 15)
                self.notif_label.text = str(low_count)
                self.notif_label.color = DANGER_TEXT if low_count > 0 else TEXT
        if "cart" in getattr(self, "nav_buttons", {}):
            cart_total_qty = sum(self.cart.values())
            self.nav_buttons["cart"].text = (
                f"KERANJANG ({cart_total_qty})"
                if cart_total_qty > 0
                else "KERANJANG"
            )

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
        """Menambahkan produk baru beserta foto ke database (khusus Admin)."""
        return role_admin.admin_create_product(
            self, raw_name, category, raw_price, raw_stock, image_path=image_path
        )

    def delete_product(self, product_id):
        """Mengarsipkan produk dari katalog tanpa merusak riwayat transaksi (khusus Admin)."""
        return role_admin.admin_delete_product(self, product_id)

    def add_stock(self, product_id, raw_quantity):
        """Menambahkan stok dari alur manajemen stok kasir/admin."""
        return role_kasir.kasir_add_stock(self, product_id, raw_quantity)

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
            start_str = start.strftime("%Y-%m-%d %H:%M:%S")
            end_str = end.strftime("%Y-%m-%d %H:%M:%S")
            self.report_orders = self.db.get_orders(
                start_at=start_str,
                end_at=end_str,
            )
            self.report_top_products = self.db.get_top_products(
                start_at=start_str,
                end_at=end_str,
                limit=3,
            )
        except Exception as error:
            self.report_orders = []
            self.report_top_products = []
            self.report_error = str(error)
        finally:
            self.report_loading = False
        return self.report_orders

    def set_report_period(self, period):
        """Mengganti filter laporan lalu merender ulang halaman laporan."""
        self.refresh_report(period)
        if hasattr(self, "sm") and self.sm.current == "reports":
            self.sm.get_screen("reports").render()

    def export_report_csv(self):
        """Mengekspor daftar transaksi pada periode laporan aktif ke file CSV (Excel)."""
        if not self.report_orders:
            self.notice("Belum ada data transaksi pada periode ini untuk diekspor.")
            return None
        try:
            folder = Path.home() / "Documents" / "POS Kopi Nako" / "Laporan"
            folder.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = folder / f"laporan_{self.report_period}_{timestamp}.csv"
            with filename.open("w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow([
                    "ID Transaksi",
                    "Tanggal",
                    "Waktu",
                    "Pelanggan / Meja",
                    "Tipe Pesanan",
                    "Metode Pembayaran",
                    "Kode Voucher",
                    "Diskon (Rp)",
                    "Total Tagihan (Rp)",
                    "Total Bayar (Rp)",
                    "Kembalian (Rp)",
                ])
                for order in self.report_orders:
                    writer.writerow([
                        order.get("id", ""),
                        order.get("date", ""),
                        order.get("time", ""),
                        order.get("customer_name", "") or "Pelanggan Umum",
                        order.get("tipe_pesanan", "Dine-In"),
                        order.get("payment", "-"),
                        order.get("kode_voucher", "") or "-",
                        int(order.get("diskon", 0)),
                        int(order.get("total", 0)),
                        int(order.get("bayar", 0)),
                        int(order.get("kembalian", 0)),
                    ])
            self.notice(f"Laporan CSV berhasil diekspor ke:\n{filename}")
            return str(filename)
        except OSError as error:
            self.notice(f"Gagal mengekspor laporan CSV:\n{error}")
            return None

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
        self.update_nav()
        if self.sm.current == "cart":
            self.sm.get_screen("cart").render()
        self.notice(f"{product['name']} ditambahkan ke keranjang.")

    def set_item_note(self, product_id, note_text):
        """Menyimpan catatan kustomisasi racikan (gula, es, catatan) untuk produk di keranjang."""
        product = self.products_by_id.get(product_id)
        if product is not None and product.get("category") == "Makanan":
            self.cart_notes.pop(product_id, None)
            raise ValueError("Racikan hanya tersedia untuk kategori minuman.")
        cleaned = " ".join(str(note_text or "").split())[:60]
        if cleaned:
            self.cart_notes[product_id] = cleaned
        else:
            self.cart_notes.pop(product_id, None)
        if hasattr(self, "sm") and self.sm.current in ("cart", "products"):
            self.sm.get_screen(self.sm.current).render()

    def get_item_note(self, product_id):
        """Mengambil catatan kustomisasi racikan untuk produk di keranjang."""
        product = self.products_by_id.get(product_id)
        if product is not None and product.get("category") == "Makanan":
            self.cart_notes.pop(product_id, None)
            return ""
        return self.cart_notes.get(product_id, "")

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
            self.cart_notes.pop(pid, None)
        else:
            self.cart[pid] = quantity
        self.update_nav()
        self.sm.get_screen("cart").render()
        return True

    def change_qty(self, pid, delta):
        """Mengubah kuantitas item pesanan melalui tombol plus/minus."""
        current_qty = self.cart.get(pid, 0)
        return self.set_qty(pid, current_qty + delta)

    def cart_subtotal(self):
        """Menghitung akumulasi subtotal harga belanjaan sebelum diskon voucher."""
        return sum(
            self.products_by_id[pid]["price"] * qty
            for pid, qty in self.cart.items()
            if pid in self.products_by_id
        )

    def cart_discount(self):
        """Menghitung nominal diskon dari kode voucher aktif berdasarkan subtotal keranjang."""
        code = str(getattr(self, "voucher_code", "") or "").strip().upper()
        if not code or code not in VOUCHER_CODES:
            return 0.0
        subtotal = float(self.cart_subtotal())
        rule = VOUCHER_CODES[code]
        if subtotal < float(rule.get("min_subtotal", 0)):
            return 0.0
        if rule["type"] == "percent":
            raw_disc = subtotal * (float(rule["value"]) / 100.0)
        else:
            raw_disc = float(rule["value"])
        max_disc = float(rule.get("max_discount", raw_disc))
        return min(subtotal, raw_disc, max_disc)

    def cart_total(self):
        """Menghitung total tagihan bersih setelah dikurangi diskon voucher."""
        return max(0.0, float(self.cart_subtotal()) - float(self.cart_discount()))

    def set_order_type(self, order_type):
        """Mengatur tipe layanan pesanan ('Dine-In' atau 'Take Away')."""
        self.order_type = "Take Away" if order_type == "Take Away" else "Dine-In"
        if hasattr(self, "sm") and self.sm.current == "cart":
            self.sm.get_screen("cart").render()

    def apply_voucher(self, raw_code):
        """Memvalidasi dan menerapkan kode voucher promo pada keranjang aktif."""
        code = str(raw_code or "").strip().upper()
        if not code:
            self.voucher_code = ""
            if hasattr(self, "sm") and self.sm.current == "cart":
                self.sm.get_screen("cart").render()
            self.notice("Kode voucher dikosongkan.")
            return False

        if code not in VOUCHER_CODES:
            self.notice(
                "Kode voucher tidak ditemukan.\n"
                f"Gunakan: {', '.join(VOUCHER_CODES.keys())}"
            )
            return False

        rule = VOUCHER_CODES[code]
        subtotal = self.cart_subtotal()
        min_sub = float(rule.get("min_subtotal", 0))
        if subtotal < min_sub:
            self.notice(
                f"Voucher {code} membutuhkan minimal belanja {rp(min_sub)}.\n"
                f"Subtotal saat ini: {rp(subtotal)}."
            )
            return False

        self.voucher_code = code
        disc = self.cart_discount()
        if hasattr(self, "sm") and self.sm.current == "cart":
            self.sm.get_screen("cart").render()
        self.notice(f"Voucher {code} diterapkan!\nHemat {rp(disc)} ({rule['label']}).")
        return True

    def clear_voucher(self):
        """Menghapus kode voucher aktif dari keranjang."""
        self.voucher_code = ""
        if hasattr(self, "sm") and self.sm.current == "cart":
            self.sm.get_screen("cart").render()

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

    def sales_this_month(self, reference=None):
        """Menghitung akumulasi omzet pada bulan berjalan untuk indikator Target Bulan Ini."""
        current = reference or datetime.now()
        month_prefix = current.strftime("%Y-%m")
        return sum(
            float(order.get("total", 0))
            for order in self.orders
            if str(order.get("date", "")).startswith(month_prefix)
        )

    def revenue_trend_series(self, days=7, reference=None):
        """Menghasilkan seri data omzet harian (7 hari terakhir) untuk grafik Tren Pendapatan."""
        current = (reference or datetime.now()).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        totals_by_date = {}
        for order in self.orders:
            d_key = str(order.get("date", ""))
            totals_by_date[d_key] = totals_by_date.get(d_key, 0.0) + float(order.get("total", 0))

        series = []
        for offset in range(days - 1, -1, -1):
            day_dt = current - timedelta(days=offset)
            d_key = day_dt.strftime("%Y-%m-%d")
            series.append({
                "date": d_key,
                "label": day_dt.strftime("%d %b"),
                "value": totals_by_date.get(d_key, 0.0),
            })
        return series

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
        self.cart_notes.clear()
        self.voucher_code = ""
        self.update_nav()
        self.sm.get_screen("cart").render()

    def new_order(self):
        """Membuka pesanan baru: kosongkan keranjang lalu arahkan ke menu produk."""
        self.cart.clear()
        self.cart_notes.clear()
        self.voucher_code = ""
        self.order_type = "Dine-In"
        self.update_nav()
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
            if self.user_role() == "pelanggan":
                self.customer_name = role_pelanggan.validate_customer_checkout(
                    self.customer_name
                )
            else:
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

        if self.user_role() == "pelanggan":
            content.add_widget(button(
                "Bayar Tunai di Kasir",
                lambda: role_pelanggan.pelanggan_pay_at_cashier(self, popup, total),
                True, 42
            ))
        else:
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
        role_kasir.kasir_open_cash_tender(
            self, parent_popup, total, style_popup_fn=_style_popup_text_white
        )

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

        ewallet_logos = GridLayout(
            cols=5, spacing=dp(6), size_hint_y=None, height=dp(48),
        )
        for logo_name in (
            "shopeepay.jpg",
            "Logo_dana_blue.svg.webp",
            "Logo_ovo_purple.svg.webp",
            "linkaja.png",
            "Gopay_logo_(2019).svg.webp",
        ):
            logo_card = Card(
                orientation="vertical", padding=dp(4),
                color=WHITE, radius=8,
            )
            logo_card.add_widget(Image(
                source=str(ASSETS_DIR / "ewallet" / logo_name),
                fit_mode="contain",
            ))
            ewallet_logos.add_widget(logo_card)
        content.add_widget(ewallet_logos)

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
        """Membuka modal pembayaran kartu debit digital dan QRIS."""
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
            cols=2, spacing=dp(8), size_hint_y=None, height=dp(42)
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

        for name in ("Card", "QRIS"):
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
            discount = self.cart_discount()
            active_voucher = self.voucher_code if discount > 0 else ""
            receipt = self.db.save_order(
                self.cart, self.products_by_id, method, total, bayar, kembalian,
                customer_name=self.customer_name,
                diskon=discount,
                kode_voucher=active_voucher,
                tipe_pesanan=getattr(self, "order_type", "Dine-In"),
            )
            self.refresh_data()
            self.refresh_report()
        except ValueError as error:
            self.notice("Transaksi gagal:\n" + str(error))
            return
        except Exception as error:
            self.notice("Transaksi gagal disimpan:\n" + str(error))
            return

        for item in receipt.get("items", []):
            note_val = self.get_item_note(item.get("id"))
            if note_val:
                item["note"] = note_val

        # Catat log transaksi kasir (metode, bank debit, total)
        self.log_transaction(receipt, method, bank=bank, extra_info=extra_info)

        self.cart.clear()
        self.cart_notes.clear()
        self.voucher_code = ""
        self.order_type = "Dine-In"
        self.update_nav()
        popup.dismiss()
        if self.user_role() == "pelanggan":
            self.go("products")
        else:
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

        order_type_val = receipt.get("tipe_pesanan", "Dine-In") or "Dine-In"
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
            "Layanan".ljust(15) + f": {order_type_val}".rjust(w - 15),
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
            if item.get("note"):
                lines.append(f"  * {item['note']}"[:w].ljust(w))

        bayar_val = receipt.get("bayar", receipt["total"])
        kembalian_val = receipt.get("kembalian", 0)
        diskon_val = float(receipt.get("diskon", 0) or 0)
        voucher_val = receipt.get("kode_voucher", "") or ""
        subtotal_val = float(
            receipt.get("subtotal", float(receipt["total"]) + diskon_val)
        )

        lines.append(sep_single)
        if diskon_val > 0:
            voucher_tag = f" ({voucher_val})" if voucher_val else ""
            lines.append("SUBTOTAL".ljust(18) + rp(subtotal_val).rjust(w - 18))
            lines.append(
                f"DISKON{voucher_tag}"[:18].ljust(18)
                + f"-{rp(diskon_val)}".rjust(w - 18)
            )
        lines.extend([
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
                "diskon": order.get("diskon", 0),
                "kode_voucher": order.get("kode_voucher", ""),
                "tipe_pesanan": order.get("tipe_pesanan", "Dine-In"),
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
        try:
            role_admin.validate_admin_access(
                self.user_role(), "menghapus riwayat transaksi"
            )
        except ValueError as error:
            self.notice(str(error))
            return
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

    def delete_order(self, order, popup=None):
        """Mengeksekusi penghapusan transaksi pada database (khusus Admin)."""
        return role_admin.admin_delete_order(self, order, popup)

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