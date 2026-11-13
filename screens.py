"""Halaman-halaman antarmuka POS Kopi Nako.

Modul ini mendefinisikan 5 tampilan utama aplikasi kasir dengan tata letak visual modern:
1. LoginPage: Form autentikasi kasir yang terpusat, bersih, dan elegan.
2. Home: Dashboard ringkasan operasional harian, metrik omzet, jam digital, dan navigasi cepat.
3. ProductsPage: Katalog produk dengan pencarian instan dan filter kategori.
4. CartPage: Pengelolaan item keranjang belanja dan verifikasi pesanan.
5. ReportsPage: Riwayat nota transaksi, rincian pembayaran & kembalian, dan cetak ulang struk.
"""
from datetime import datetime
from pathlib import Path
import subprocess
from threading import Thread
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.image import Image
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.utils import platform

from database import (
    MAX_CUSTOMER_LABEL_LENGTH, MAX_PRODUCT_NAME_LENGTH, MAX_PRODUCT_STOCK,
)

from config import (
    ASSETS_DIR, LOGO_PATH, PRODUCT_IMAGE_DIR, PRODUCT_IMAGES, ART_BY_CATEGORY,
)
from theme import (
    ACCENT, ACCENT_DARK, ACCENT_TEXT, ACCENT_THEMES, BORDER, BORDER_STRONG,
    BROWN, COFFEE, CREAM, CORAL, DANGER_TEXT, GREEN, INPUT, MUTED, ON_ACCENT,
    PURPLE, SUCCESS_TEXT, SURFACE, TEXT, WARNING_TEXT, WHITE, accent_color,
)
from ui_components import (
    Text, Card, Page, button, metric_card, rp, status_chip, text_input,
    themed_popup,
)


def _style_popup_text_white(popup, content, exclude=()):
    """Memastikan teks isi dan judul popup terbaca pada latar popup gelap.

    Subtree yang dikecualikan dipakai untuk kartu terang, misalnya preview foto,
    agar teks di atas permukaan terang tetap memakai warna aslinya. Tombol tidak
    disentuh supaya warna label tombol tetap mengikuti warna tombol masing-masing.
    """
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

        # Text adalah komponen Label khusus dari ui_components. Button/Spinner
        # sengaja tidak disentuh agar teks tombol tetap kontras terhadap tombolnya.
        if widget.__class__.__name__ in ("Text", "Label"):
            if hasattr(widget, "color"):
                widget.color = (1, 1, 1, 1)


REPORT_PERIODS = (
    ("daily", "HARIAN"),
    ("weekly", "MINGGUAN"),
    ("monthly", "BULANAN"),
    ("yearly", "TAHUNAN"),
)

ACCENT_LABELS = {
    "purple": "Ungu",
    "orange": "Orange",
    "cyan": "Cyan",
    "blue": "Biru",
    "red": "Merah",
    "black": "Hitam",
}


class LoginPage(Page):
    """Halaman login mengikuti desain Figma Kopi Nako, dengan autentikasi lama."""

    def on_pre_enter(self, *_):
        self.render()

    def render(self):
        self.content.clear_widgets()

        cream = SURFACE
        espresso = TEXT
        roast = ACCENT
        muted = MUTED
        border = BORDER

        self.content.padding = [dp(12), dp(12), dp(12), dp(24)]
        self.content.spacing = dp(0)

        # Menjaga desain tetap sempit seperti frame Figma (412 px), dan terpusat
        # ketika aplikasi dijalankan di desktop. Page tetap dapat di-scroll.
        outer = AnchorLayout(
            anchor_x="center", anchor_y="top",
            size_hint=(1, None), height=dp(850),
            padding=[dp(0), dp(0), dp(0), dp(0)],
        )
        shell = Card(
            orientation="vertical", size_hint=(None, None),
            width=dp(412), height=dp(820), padding=dp(0), spacing=dp(0),
            color=cream, radius=0,
        )

        def fit_shell(instance, *_):
            shell.width = min(dp(412), max(dp(280), instance.width - dp(8)))
        outer.bind(width=fit_shell)
        fit_shell(outer)

        # Banner Figma: foto sebagai background, lalu logo dan branding diletakkan
        # sebagai layer di atas foto (bukan bagian dari file JPG background).
        banner_path = ASSETS_DIR / "login_banner.jpg"
        banner = FloatLayout(size_hint=(1, None), height=dp(205))
        if banner_path.exists():
            banner.add_widget(Image(
                source=str(banner_path), size_hint=(1, 1),
                pos_hint={"x": 0, "y": 0}, fit_mode="cover",
            ))

        if LOGO_PATH.exists():
            banner.add_widget(Image(
                source=str(LOGO_PATH), size_hint=(None, None),
                size=(dp(78), dp(78)), pos_hint={"x": 0.035, "top": 0.92},
                fit_mode="contain",
            ))
        banner.add_widget(Text(
            "KOPI\nNAKO", size=30, bold=True, color=TEXT,
            size_hint=(0.55, None), height=dp(76),
            pos_hint={"x": 0.275, "top": 0.91},
        ))
        banner.add_widget(Text(
            "A good coffee.\nA better day.", size=25, bold=True,
            color=TEXT, size_hint=(0.67, None),
            height=dp(30), pos_hint={"x": 0.035, "top": 0.44},
        ))
        banner.add_widget(Text(
            "AUTHENTIC COFFEE EXPERIENCE", size=15, bold=True,
            color=ACCENT_TEXT, size_hint=(0.60, None),
            height=dp(14), pos_hint={"x": 0.035, "top": 0.17},
        ))
        shell.add_widget(banner)

        # Slot form memenuhi tinggi body desain. Isi form sendiri dipasang di
        # bagian atas supaya tidak muncul ruang kosong besar sebelum judul.
        form_slot = AnchorLayout(
            anchor_x="center", anchor_y="top", size_hint=(1, None), height=dp(615)
        )
        form = BoxLayout(
            orientation="vertical", size_hint=(1, None), height=dp(514),
            padding=[dp(28), dp(24), dp(28), dp(18)], spacing=dp(0),
        )
        form.canvas.before.clear()
        with form.canvas.before:
            Color(*cream)
            form_bg = RoundedRectangle(pos=form.pos, size=form.size, radius=[0])
        def update_form_bg(*_):
            form_bg.pos = form.pos
            form_bg.size = form.size
        form.bind(pos=update_form_bg, size=update_form_bg)

        form.add_widget(Text(
            "Log in to the POS system", size=22, bold=True, color=espresso,
            size_hint_y=None, height=dp(32),
        ))
        form.add_widget(Text(
            "Good coffee. Even better to see you.", size=13, color=muted,
            size_hint_y=None, height=dp(30),
        ))
        form.add_widget(BoxLayout(size_hint_y=None, height=dp(12)))

        def input_field(hint, password=False):
            """Input dengan latar cream dan border membulat ala desain Figma."""
            wrap = BoxLayout(
                orientation="horizontal", size_hint=(1, None), height=dp(58),
                padding=[dp(13), dp(3), dp(10), dp(3)],
            )
            with wrap.canvas.before:
                Color(*INPUT)
                shape = RoundedRectangle(pos=wrap.pos, size=wrap.size, radius=[dp(13)])
                Color(*border)
                outline = Line(rounded_rectangle=(wrap.x, wrap.y, wrap.width, wrap.height, dp(13)), width=1.0)
            def update_wrap(*_):
                shape.pos = wrap.pos
                shape.size = wrap.size
                outline.rounded_rectangle = (wrap.x, wrap.y, wrap.width, wrap.height, dp(13))
            wrap.bind(pos=update_wrap, size=update_wrap)

            field = TextInput(
                hint_text=hint, password=password, multiline=False,
                size_hint=(1, 1), font_size=dp(14),
                padding=[dp(2), dp(13), dp(2), dp(10)],
                background_normal="", background_active="",
                background_color=(0, 0, 0, 0), foreground_color=TEXT,
                cursor_color=ACCENT, hint_text_color=MUTED,
            )
            wrap.add_widget(field)
            if password:
                # Kontrol SHOW/HIDE memakai teks ASCII agar tidak muncul glyph kotak
                # ketika font sistem tidak punya ikon mata.
                toggle = Button(
                    text="SHOW", size_hint=(None, 1), width=dp(44),
                    font_size=dp(8), bold=True, color=muted,
                    background_normal="", background_down="",
                    background_color=(0, 0, 0, 0),
                )
                def toggle_password(*_):
                    field.password = not field.password
                    toggle.text = "SHOW" if field.password else "HIDE"
                toggle.bind(on_release=toggle_password)
                wrap.add_widget(toggle)
            return wrap, field

        self.username_input = None
        self.password_input = None

        user_label = Text("Username", size=11, bold=True, color=muted,
                          size_hint_y=None, height=dp(20))
        form.add_widget(user_label)
        user_wrap, self.username_input = input_field("Enter the cashier's username")
        self.username_input.bind(
            on_text_validate=lambda *_: setattr(self.password_input, "focus", True)
        )
        form.add_widget(user_wrap)
        form.add_widget(BoxLayout(size_hint_y=None, height=dp(12)))

        pass_label = Text("Password", size=11, bold=True, color=muted,
                          size_hint_y=None, height=dp(20))
        form.add_widget(pass_label)
        pass_wrap, self.password_input = input_field("Enter your password", password=True)
        self.password_input.bind(on_text_validate=lambda *_: self.submit())
        form.add_widget(pass_wrap)
        form.add_widget(BoxLayout(size_hint_y=None, height=dp(2)))

        # Tombol utama dibuat dengan RoundedRectangle langsung agar radius tampil
        # konsisten. Label tanpa panah khusus menghindari kotak glyph di macOS.
        sign_in = Button(
            text="Sign in", size_hint=(1, None), height=dp(50),
            font_size=dp(14), bold=True, color=ON_ACCENT,
            background_normal="", background_down="",
            background_color=(0, 0, 0, 0),
        )
        with sign_in.canvas.before:
            sign_in_bg_color = Color(*ACCENT)
            sign_in_bg_shape = RoundedRectangle(
                pos=sign_in.pos, size=sign_in.size, radius=[dp(26)]
            )
        def update_sign_in_shape(*_):
            sign_in_bg_shape.pos = sign_in.pos
            sign_in_bg_shape.size = sign_in.size
        sign_in.bind(pos=update_sign_in_shape, size=update_sign_in_shape)
        sign_in.bind(on_release=lambda *_: self.submit())
        form.add_widget(sign_in)
        form.add_widget(BoxLayout(size_hint_y=None, height=dp(14)))

        # Pemisah "or continue with".
        divider_row = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(22), spacing=dp(10)
        )
        for _ in range(1):
            left_line = BoxLayout(size_hint_y=None, height=dp(1))
            with left_line.canvas.before:
                Color(*border)
                left_shape = RoundedRectangle(pos=left_line.pos, size=left_line.size)
            left_line.bind(pos=lambda w, *_: setattr(left_shape, 'pos', w.pos),
                           size=lambda w, *_: setattr(left_shape, 'size', w.size))
            divider_row.add_widget(left_line)
        divider_row.add_widget(Text("or continue with", size=10, color=muted,
                                    size_hint_x=None, width=dp(98), align="center"))
        right_line = BoxLayout(size_hint_y=None, height=dp(1))
        with right_line.canvas.before:
            Color(*border)
            right_shape = RoundedRectangle(pos=right_line.pos, size=right_line.size)
        right_line.bind(pos=lambda w, *_: setattr(right_shape, 'pos', w.pos),
                        size=lambda w, *_: setattr(right_shape, 'size', w.size))
        divider_row.add_widget(right_line)
        form.add_widget(divider_row)
        form.add_widget(BoxLayout(size_hint_y=None, height=dp(10)))

        demo_btn = button(
            "Gunakan akun demo (admin/KopiNako123!)",
            self.fill_demo_credentials, False, 48,
            outline=True, outline_color=border,
        )
        demo_btn.font_size = dp(12)
        demo_btn.color = TEXT
        form.add_widget(demo_btn)

        form.add_widget(BoxLayout(size_hint_y=None, height=dp(20)))
        form.add_widget(Text(
            "POS KOPI NAKO - POINT OF SALE", size=11, color=muted,
            align="center", size_hint_y=None, height=dp(22),
        ))
        form.add_widget(BoxLayout(size_hint_y=None, height=dp(10)))
        form.add_widget(Text(
            "POS Kopi Nako v2.0  •  Keamanan PBKDF2-HMAC-SHA256  •  SQLite & MySQL Support",
            size=8, color=muted, align="center", size_hint_y=None, height=dp(32),
        ))

        form_slot.add_widget(form)
        shell.add_widget(form_slot)
        outer.add_widget(shell)
        self.content.add_widget(outer)

    def fill_demo_credentials(self):
        """Mengisi formulir login dengan kredensial demo secara instan."""
        if hasattr(self, "username_input") and self.username_input is not None:
            self.username_input.text = "admin"
        if hasattr(self, "password_input") and self.password_input is not None:
            self.password_input.text = "KopiNako123!"

    def submit(self):
        """Mengirimkan kredensial login ke pengendali aplikasi."""
        app = self.manager.app
        uname = self.username_input.text if getattr(self, "username_input", None) else ""
        passwd = self.password_input.text if getattr(self, "password_input", None) else ""
        app.login(uname, passwd)


class Home(Page):
    """Halaman Dashboard Utama dengan Estetika Minimalis Modern & Palet Kohesif."""

    def on_pre_enter(self, *_):
        self.render()

    def render(self):
        self.content.clear_widgets()
        main_layout = BoxLayout(
            orientation="vertical", spacing=dp(16), padding=0,
            size_hint=(1, None),
        )
        main_layout.bind(minimum_height=main_layout.setter("height"))
        self.content.add_widget(main_layout)
        app = self.manager.app
        nama_kasir = app.current_user["nama"] if app.current_user else "Kasir"
        role_kasir = app.current_user["role"] if app.current_user else "staff"
        engine_name = "SQLite (Lokal)" if getattr(app.db, "engine", "sqlite") == "sqlite" else "MySQL"

        # 1. Header Banner Profil Kasir & Jam Digital
        banner = Card(
            orientation="horizontal", size_hint_y=None,
            height=dp(88), padding=[dp(20), dp(12), dp(20), dp(12)], spacing=dp(14),
            color=ACCENT_DARK, radius=16
        )
        if LOGO_PATH.exists():
            banner.add_widget(Image(
                source=str(LOGO_PATH), size_hint=(None, 1),
                width=dp(52), fit_mode="contain"
            ))

        info_box = BoxLayout(orientation="vertical", spacing=dp(2))
        info_box.add_widget(Text(
            f"Halo, {nama_kasir}!", size=18, bold=True, color=ON_ACCENT
        ))
        info_box.add_widget(Text(
            f"Peran: {role_kasir.capitalize()}  •  Database: {engine_name}",
            size=11, color=ON_ACCENT
        ))
        banner.add_widget(info_box)

        time_box = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(130), spacing=dp(2))
        self.clock_time = Text(
            datetime.now().strftime("%H:%M"), size=22, bold=True, color=ON_ACCENT, align="right"
        )
        self.clock_date = Text(
            datetime.now().strftime("%d %b %Y"), size=11, color=ON_ACCENT, align="right"
        )
        time_box.add_widget(self.clock_time)
        time_box.add_widget(self.clock_date)
        banner.add_widget(time_box)
        main_layout.add_widget(banner)

        # 2. Grid metric dengan pembanding kalender yang nyata.
        main_layout.add_widget(Text(
            "Ringkasan Operasional Hari Ini", size=15, bold=True, color=COFFEE,
            size_hint_y=None, height=dp(26)
        ))

        stats = GridLayout(
            cols=2, rows=2, spacing=dp(12),
            size_hint_y=None,
            row_default_height=dp(95), row_force_default=True,
        )
        stats.bind(minimum_height=stats.setter("height"))
        metrics = app.home_metrics()

        def growth_display(metric):
            growth = metric["growth"]
            if growth is None:
                if metric["value"] > 0:
                    return "Baru hari ini", SUCCESS_TEXT
                return "Belum ada data kemarin", MUTED
            if growth > 0:
                return f"{growth:+.1f}% vs kemarin", SUCCESS_TEXT
            if growth < 0:
                return f"{growth:+.1f}% vs kemarin", DANGER_TEXT
            return "0.0% vs kemarin", MUTED

        sales_growth, sales_growth_color = growth_display(metrics["sales"])
        transaction_growth, transaction_growth_color = growth_display(metrics["transactions"])
        metric_cards = [
            metric_card(
                "OMZET PENJUALAN", rp(metrics["sales"]["value"]),
                "Total omzet transaksi hari ini", ACCENT, "Rp",
                growth_text=sales_growth, growth_color=sales_growth_color,
                color=SURFACE, border_color=BORDER_STRONG,
                height=95, compact=True,
            ),
            metric_card(
                "JUMLAH TRANSAKSI", f"{metrics['transactions']['value']} Nota",
                "Pesanan selesai diproses", ACCENT_DARK, "TRX",
                growth_text=transaction_growth, growth_color=transaction_growth_color,
                color=SURFACE, border_color=BORDER_STRONG,
                height=95, compact=True,
            ),
            metric_card(
                "KATALOG MENU", f"{len(app.products)} Item",
                "Menu siap dipesan pelanggan", ACCENT, "MENU",
                color=SURFACE, border_color=BORDER_STRONG,
                height=95, compact=True,
            ),
            metric_card(
                "STATUS SISTEM", "Siap Melayani",
                f"Koneksi {engine_name} aktif normal", GREEN, "OK",
                color=SURFACE, border_color=BORDER_STRONG,
                height=95, compact=True,
            ),
        ]
        for card in metric_cards:
            stats.add_widget(card)
        main_layout.add_widget(stats)

        # 3. Menu Akses Cepat Kasir
        quick_actions = BoxLayout(
            orientation="vertical", spacing=dp(10),
            size_hint_y=None, height=dp(192),
        )
        quick_actions.add_widget(Text(
            "Aksi Cepat Kasir", size=15, bold=True, color=COFFEE,
            size_hint_y=None, height=dp(26)
        ))
        actions = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(102))
        actions.add_widget(button("BUKA MENU PRODUK", lambda: app.go("products"), True, 46))
        actions.add_widget(button("LIHAT KERANJANG", lambda: app.go("cart"), False, 46))
        actions.add_widget(button("RIWAYAT TRANSAKSI", lambda: app.go("reports"), False, 46))
        actions.add_widget(button("TRANSAKSI BARU", app.new_order, True, 46))
        quick_actions.add_widget(actions)
        quick_actions.add_widget(button(
            "PENGATURAN TAMPILAN", self.open_theme_settings, False, 44
        ))
        main_layout.add_widget(quick_actions)

        # 4. Kartu Panduan Operasional Kasir
        tips_card = Card(
            orientation="vertical", padding=[dp(16), dp(12), dp(16), dp(12)], spacing=dp(3),
            size_hint_y=None, height=dp(72), color=WHITE, radius=14
        )
        tips_card.add_widget(Text(
            "Tips Layanan Kasir Kopi Nako", size=12, bold=True, color=ACCENT_TEXT,
            size_hint_y=None, height=dp(20)
        ))
        tips_card.add_widget(Text(
            "Pastikan menghitung nominal uang kembalian pelanggan dengan teliti sebelum menyerahkan nota struk.",
            size=11, color=MUTED, size_hint_y=None, height=dp(22)
        ))
        main_layout.add_widget(tips_card)

    def on_enter(self, *_):
        if getattr(self, "_clock_event", None) is None:
            self._clock_event = Clock.schedule_interval(self._tick_clock, 1)

    def on_leave(self, *_):
        event = getattr(self, "_clock_event", None)
        if event is not None:
            event.cancel()
            self._clock_event = None

    def _tick_clock(self, *_):
        now = datetime.now()
        time_label = getattr(self, "clock_time", None)
        date_label = getattr(self, "clock_date", None)
        if time_label is not None:
            time_label.text = now.strftime("%H:%M")
        if date_label is not None:
            date_label.text = now.strftime("%d %b %Y")

    def open_theme_settings(self):
        """Membuka pemilih mode tampilan dan aksen warna aplikasi."""
        app = self.manager.app
        selected = {"mode": app.theme_mode, "accent": app.theme_accent}
        # Popup selalu memakai permukaan gelap; gunakan putih di kedua mode tema.
        popup_label_color = WHITE
        content = BoxLayout(
            orientation="vertical", padding=dp(18), spacing=dp(10)
        )
        content.add_widget(Text(
            "Pilih mode tampilan dan satu aksen warna untuk seluruh aplikasi.",
            size=12, color=MUTED, align="center",
            size_hint_y=None, height=dp(5)
        ))
        content.add_widget(Text(
            "Mode Tampilan", size=11, bold=True, color=popup_label_color,
            size_hint_y=None, height=dp(18)
        ))

        mode_buttons = {}
        mode_row = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(44))
        for mode, label in (("light", "LIGHT"), ("dark", "DARK")):
            mode_buttons[mode] = button(label, lambda m=mode: select_mode(m), False, 44)
            mode_row.add_widget(mode_buttons[mode])
        content.add_widget(mode_row)

        content.add_widget(Text(
            "Aksen Warna", size=11, bold=True, color=popup_label_color,
            size_hint_y=None, height=dp(18)
        ))
        accent_grid = GridLayout(
            cols=3, spacing=dp(8), size_hint_y=None, height=dp(96)
        )
        accent_buttons = {}
        for accent_name, label in ACCENT_LABELS.items():
            accent_buttons[accent_name] = button(
                label, lambda a=accent_name: select_accent(a), False, 44,
                fill_color=accent_color(accent_name), text_color=ON_ACCENT,
            )
            accent_grid.add_widget(accent_buttons[accent_name])
        content.add_widget(accent_grid)

        selection_label = Text(
            "", size=11, color=ACCENT_TEXT, bold=True, align="center",
            size_hint_y=None, height=dp(22)
        )
        content.add_widget(selection_label)

        popup = themed_popup(
            "Pengaturan Tampilan", content,
            size_hint=(0.88, None), height=dp(390), auto_dismiss=False,
        )
        # Semua teks isi popup dibuat putih karena permukaan modal berwarna gelap.
        _style_popup_text_white(popup, content)

        def refresh_selection():
            for mode, mode_button in mode_buttons.items():
                active = selected["mode"] == mode
                mode_button._bg_color.rgba = ACCENT if active else SURFACE
                mode_button.color = ON_ACCENT if active else TEXT
            selection_label.text = (
                f"Pilihan: {selected['mode'].upper()} + "
                f"{ACCENT_LABELS[selected['accent']]}"
            )

        def select_mode(mode):
            selected["mode"] = mode
            refresh_selection()

        def select_accent(accent_name):
            selected["accent"] = accent_name
            refresh_selection()

        def apply_selected_theme():
            popup.dismiss()
            app.apply_theme(selected["mode"], selected["accent"], persist=True)

        refresh_selection()
        actions = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        actions.add_widget(button("BATAL", popup.dismiss, False, 44))
        actions.add_widget(button("TERAPKAN", apply_selected_theme, True, 44))
        content.add_widget(actions)
        popup.open()


class ProductsPage(Page):
    """Halaman Katalog Produk dan Pemilihan Menu dengan UI/UX Modern."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.category = "Semua"
        self.query = ""

    def on_pre_enter(self, *_):
        self.render()

    def render(self):
        self.content.clear_widgets()
        app = self.manager.app

        # Header Halaman
        self.heading("Katalog Menu", "Pilih menu kopi atau makanan untuk pesanan kasir")

        add_product_button = button(
            "+ TAMBAH PRODUK BARU", self.open_add_product, True, 46
        )
        self.content.add_widget(add_product_button)

        stock_action = Card(
            orientation="horizontal", size_hint_y=None, height=dp(58),
            padding=[dp(14), dp(8), dp(14), dp(8)], spacing=dp(12),
            color=CREAM, radius=12
        )
        stock_action.add_widget(Text(
            "Stok kosong atau menipis? Tambahkan stok dari panel kasir.",
            size=11, color=COFFEE
        ))
        stock_button = button("MANAJEMEN STOK", self.open_stock_management, True, 44)
        stock_button.size_hint_x = None
        stock_button.width = dp(180)
        stock_action.add_widget(stock_button)
        self.content.add_widget(stock_action)

        # Kotak Pencarian Modern Dibatasi 48% Lebar Halaman
        search_wrap = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(46))
        search = TextInput(
            hint_text="Cari nama menu (contoh: Kopi, Aren, Roti)...",
            text=self.query, multiline=False,
            size_hint=(0.48, 1),
            font_size=dp(13), padding=[dp(14), dp(11)],
            background_normal="", background_active="",
            background_color=INPUT, foreground_color=TEXT, cursor_color=ACCENT
        )
        search.bind(text=self.search_changed)
        search_wrap.add_widget(search)
        search_wrap.add_widget(BoxLayout())  # Spacer agar tidak melar melebar
        self.content.add_widget(search_wrap)

        # Baris Filter Kategori Modern (Pills / Chips)
        filter_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8))
        for cat in ["Semua", "Kopi", "Non Kopi", "Makanan"]:
            is_active = self.category == cat
            btn = button(
                cat,
                lambda c=cat: self.set_category(c),
                is_active, 44,
                fill_color=ACCENT if is_active else WHITE,
                text_color=ON_ACCENT if is_active else TEXT,
            )
            filter_box.add_widget(btn)
        self.content.add_widget(filter_box)

        # Wadah Grid Produk
        self.grid = GridLayout(cols=2, spacing=dp(12), size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter("height"))
        self.content.add_widget(self.grid)
        self.render_products()

    def open_add_product(self):
        """Form tambah produk mobile dengan pemilihan foto dari galeri/file."""
        app = self.manager.app
        if app.current_user is None:
            app.notice("Silakan login terlebih dahulu.")
            return

        selected_image = {"path": None, "saved": False}
        # Ukuran dibuat lebih ringkas agar seluruh isi form muat di area popup.
        # Versi sebelumnya menumpuk tinggi konten melebihi ruang popup sehingga
        # deskripsi dan label pertama naik ke area judul.
        content = BoxLayout(
            orientation="vertical", padding=dp(10), spacing=dp(3)
        )

        def add_label(caption):
            content.add_widget(Text(
                caption, size=11, bold=True, color=COFFEE,
                size_hint_y=None, height=dp(16)
            ))

        add_label("Nama Produk")
        name_input = text_input(
            hint_text=f"Maks. {MAX_PRODUCT_NAME_LENGTH} karakter",
            height=36, font_size=14,
        )
        content.add_widget(name_input)

        add_label("Kategori")
        category_spinner = Spinner(
            text="Kopi", values=("Kopi", "Non Kopi", "Makanan"),
            size_hint_y=None, height=dp(36),
            font_size=dp(13), color=ON_ACCENT,
            background_normal="", background_down="",
            background_color=ACCENT,
        )
        content.add_widget(category_spinner)

        add_label("Harga (Rp)")
        price_input = text_input(
            hint_text="Contoh: 18000", height=36, font_size=14,
            input_filter="float"
        )
        content.add_widget(price_input)

        add_label(f"Stok Awal (maks. {MAX_PRODUCT_STOCK})")
        stock_input = text_input(
            hint_text=f"Isi 0 sampai {MAX_PRODUCT_STOCK}", height=36, font_size=14,
            input_filter="int"
        )
        content.add_widget(stock_input)

        add_label("Foto Produk (opsional)")
        photo_row = BoxLayout(
            orientation="horizontal", size_hint_y=None,
            height=dp(68), spacing=dp(10)
        )
        photo_preview = Card(
            orientation="vertical", size_hint=(None, 1), width=dp(68),
            padding=dp(3), color=CREAM, radius=9
        )
        photo_preview.add_widget(Text(
            "NO\nPHOTO", size=10, bold=True, color=MUTED, align="center"
        ))
        photo_row.add_widget(photo_preview)

        photo_actions = BoxLayout(orientation="vertical", spacing=dp(5))
        photo_status = Text(
            "Belum ada foto dipilih", size=10, color=MUTED,
            size_hint_y=None, height=dp(20)
        )
        photo_actions.add_widget(photo_status)
        photo_actions.add_widget(button(
            "PILIH FOTO DARI GALERI", lambda: choose_product_photo(), True, 38
        ))
        photo_row.add_widget(photo_actions)
        content.add_widget(photo_row)

        feedback = Text(
            "", size=10, color=DANGER_TEXT, align="center",
            size_hint_y=None, height=dp(20)
        )
        content.add_widget(feedback)

        popup = themed_popup(
            "Tambah Produk Baru", content,
            size_hint=(0.92, None), height=dp(500),
            auto_dismiss=False,
        )
        _style_popup_text_white(popup, content, exclude=(photo_preview,))

        def show_selected_photo(path):
            if selected_image["path"] and selected_image["path"] != path:
                app.discard_product_image(selected_image["path"])
            selected_image["path"] = path
            photo_preview.clear_widgets()
            photo_preview.add_widget(Image(
                source=path, fit_mode="contain"
            ))
            photo_status.text = Path(path).name
            photo_status.color = WHITE
            feedback.text = ""

        def handle_photo_selection(path):
            if not path:
                return
            try:
                imported = app.import_product_image(path)
                show_selected_photo(imported)
            except Exception as error:
                feedback.text = f"Foto gagal dipilih: {error}"
                feedback.color = WHITE

        def choose_product_photo():
            """Membuka galeri Android atau pemilih file desktop."""
            feedback.text = ""
            if platform == "android":
                try:
                    from android import activity  # type: ignore[reportMissingImports]  # tersedia di APK Android
                    from jnius import autoclass  # type: ignore[reportMissingImports]  # tersedia di APK Android

                    Intent = autoclass("android.content.Intent")
                    Activity = autoclass("android.app.Activity")
                    PythonActivity = autoclass("org.kivy.android.PythonActivity")
                    String = autoclass("java.lang.String")
                    request_code = 0x4B4E

                    def on_activity_result(request_code_result, result_code, intent_result):
                        if int(request_code_result) != request_code:
                            return
                        activity.unbind(on_activity_result=on_activity_result)
                        if int(result_code) != int(Activity.RESULT_OK) or intent_result is None:
                            return
                        uri = intent_result.getData()
                        if uri is None:
                            feedback.text = "Foto tidak berhasil dipilih."
                            feedback.color = WHITE
                            return
                        handle_photo_selection(str(uri.toString()))

                    activity.unbind(on_activity_result=on_activity_result)
                    activity.bind(on_activity_result=on_activity_result)
                    pick_intent = Intent(Intent.ACTION_GET_CONTENT)
                    pick_intent.setType("image/*")
                    pick_intent.addCategory(Intent.CATEGORY_OPENABLE)
                    pick_intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    chooser = Intent.createChooser(
                        pick_intent, String("Pilih foto produk")
                    )
                    PythonActivity.mActivity.startActivityForResult(
                        chooser, request_code
                    )
                except Exception as error:
                    feedback.text = f"Galeri tidak bisa dibuka: {error}"
                    feedback.color = WHITE
                return

            # macOS: gunakan dialog file bawaan Finder melalui AppleScript.
            # Ini tidak membutuhkan pyobjus/Plyer yang sering belum ada di
            # virtual environment Kivy pada macOS.
            if platform == "macosx":
                def open_macos_picker():
                    try:
                        result = subprocess.run(
                            [
                                "osascript", "-e",
                                'POSIX path of (choose file with prompt "Pilih foto produk")',
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        selected_path = result.stdout.strip()
                        if result.returncode == 0 and selected_path:
                            Clock.schedule_once(
                                lambda *_: handle_photo_selection(selected_path), 0
                            )
                            return

                        # Membatalkan dialog Finder adalah tindakan normal.
                        error_text = (result.stderr or "").strip()
                        if "-128" in error_text or "User canceled" in error_text:
                            return
                        message = error_text or "Finder tidak mengembalikan lokasi foto."
                        Clock.schedule_once(
                            lambda *_: show_picker_error(message), 0
                        )
                    except Exception as error:
                        Clock.schedule_once(
                            lambda *_: show_picker_error(str(error)), 0
                        )

                Thread(target=open_macos_picker, daemon=True).start()
                return

            # Windows/Linux: Plyer menyediakan dialog native. Jalankan di
            # thread terpisah karena open_file() menunggu dialog ditutup.
            def open_desktop_picker():
                try:
                    from plyer import filechooser
                    selection = filechooser.open_file(
                        title="Pilih Foto Produk",
                        filters=[["Gambar", "*.jpg", "*.jpeg", "*.png", "*.webp"]],
                        multiple=False,
                    )
                    selected_path = selection[0] if selection else None
                    if selected_path:
                        Clock.schedule_once(
                            lambda *_: handle_photo_selection(selected_path), 0
                        )
                except ImportError:
                    Clock.schedule_once(
                        lambda *_: show_picker_error(
                            "Modul pemilih file belum terpasang. Jalankan: python -m pip install plyer"
                        ), 0
                    )
                except Exception as error:
                    Clock.schedule_once(
                        lambda *_: show_picker_error(str(error)), 0
                    )

            Thread(target=open_desktop_picker, daemon=True).start()

        def show_picker_error(message):
            feedback.text = f"Pemilih file gagal dibuka: {message}"
            feedback.color = WHITE

        def submit_product():
            try:
                product = app.create_product(
                    name_input.text,
                    category_spinner.text,
                    price_input.text,
                    stock_input.text,
                    image_path=selected_image["path"],
                )
            except (ValueError, TypeError) as error:
                feedback.text = str(error)
                feedback.color = WHITE
                return
            except Exception as error:
                feedback.text = f"Produk gagal disimpan: {error}"
                feedback.color = WHITE
                return

            selected_image["saved"] = True
            popup.dismiss()
            self.category = "Semua"
            self.query = ""
            self.render()
            app.notice(
                f"Produk {product['name']} berhasil ditambahkan.\n"
                f"Harga: {rp(product['price'])} | Stok awal: {product['stok']}"
            )

        actions = BoxLayout(
            orientation="horizontal", size_hint_y=None,
            height=dp(40), spacing=dp(8)
        )
        actions.add_widget(button("BATAL", popup.dismiss, False, 40))
        actions.add_widget(button("SIMPAN PRODUK", submit_product, True, 40))
        content.add_widget(actions)

        def cleanup_uncommitted_photo(*_):
            if not selected_image["saved"] and selected_image["path"]:
                app.discard_product_image(selected_image["path"])
                selected_image["path"] = None
        popup.bind(on_dismiss=cleanup_uncommitted_photo)
        popup.open()

    def open_stock_management(self):
        """Membuka panel khusus kasir untuk menambah stok produk."""
        app = self.manager.app
        if not app.products:
            app.notice("Belum ada produk yang dapat dikelola.")
            return

        products_by_name = {product["name"]: product for product in app.products}
        product_names = tuple(products_by_name.keys())
        content = BoxLayout(
            orientation="vertical", padding=dp(18), spacing=dp(9)
        )
        content.add_widget(Text(
            "Gunakan panel ini untuk mencatat stok pembelian yang baru datang.",
            size=12, color=MUTED, align="center",
            size_hint_y=None, height=dp(32)
        ))
        content.add_widget(Text(
            "Pilih Produk", size=11, bold=True, color=COFFEE,
            size_hint_y=None, height=dp(2)
        ))

        product_spinner = Spinner(
            text=product_names[0], values=product_names,
            size_hint_y=None, height=dp(44),
            font_size=dp(13), bold=True, color=ON_ACCENT,
            background_normal="", background_down="",
            background_color=ACCENT,
        )
        content.add_widget(product_spinner)

        current_stock_label = Text(
            "", size=12, bold=True, color=ACCENT_TEXT,
            size_hint_y=None, height=dp(22), align="center"
        )
        content.add_widget(current_stock_label)

        content.add_widget(Text(
            f"Jumlah Stok Masuk (batas total {MAX_PRODUCT_STOCK})",
            size=11, bold=True, color=COFFEE,
            size_hint_y=None, height=dp(18)
        ))
        stock_input = text_input(
            hint_text="Contoh: 20",
            height=46,
            font_size=15,
            input_filter="int",
            halign="center",
        )
        content.add_widget(stock_input)

        feedback_label = Text(
            "", size=11, color=DANGER_TEXT, align="center",
            size_hint_y=None, height=dp(30)
        )
        content.add_widget(feedback_label)

        popup = themed_popup(
            "Manajemen Stok Kasir", content,
            size_hint=(0.88, None), height=dp(350),
            auto_dismiss=False,
        )
        _style_popup_text_white(popup, content)

        def selected_product():
            return products_by_name.get(product_spinner.text)

        def update_current_stock(*_):
            product = selected_product()
            if product is None:
                current_stock_label.text = "Produk tidak ditemukan"
                current_stock_label.color = WHITE
                return
            current_stock = int(product["stok"])
            remaining = max(0, MAX_PRODUCT_STOCK - current_stock)
            current_stock_label.text = (
                f"Stok: {current_stock}/{MAX_PRODUCT_STOCK} item "
                f"• kapasitas tersisa: {remaining}"
            )
            current_stock_label.color = WHITE
            stock_input.hint_text = f"Maksimal tambah {remaining} item"
            stock_input.disabled = remaining <= 0
            feedback_label.text = (
                "Stok sudah mencapai batas maksimal."
                if remaining <= 0 else ""
            )
            feedback_label.color = WHITE
            add_stock_button.disabled = remaining <= 0

        def submit_stock():
            product = selected_product()
            if product is None:
                feedback_label.text = "Pilih produk yang valid."
                feedback_label.color = WHITE
                return
            try:
                updated = app.add_stock(product["id"], stock_input.text)
            except (ValueError, TypeError) as error:
                feedback_label.text = str(error)
                feedback_label.color = WHITE
                return
            except Exception as error:
                feedback_label.text = f"Stok gagal diperbarui: {error}"
                feedback_label.color = WHITE
                return

            popup.dismiss()
            self.render_products()
            app.notice(
                f"Stok {updated['name']} bertambah {updated['added']} item.\n"
                f"Stok sekarang: {updated['stok']} item."
            )

        product_spinner.bind(text=update_current_stock)
        stock_input.bind(on_text_validate=lambda *_: submit_stock())
        actions = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        actions.add_widget(button("BATAL", popup.dismiss, False, 44))
        add_stock_button = button("TAMBAH STOK", submit_stock, True, 44)
        actions.add_widget(add_stock_button)
        content.add_widget(actions)
        update_current_stock()
        popup.open()

    def search_changed(self, _instance, value):
        self.query = value
        self.render_products()

    def set_category(self, category):
        self.category = category
        self.render()

    def reset_search(self):
        self.category = "Semua"
        self.query = ""
        self.render()

    def render_products(self):
        if not hasattr(self, "grid"):
            return
        self.grid.clear_widgets()
        app = self.manager.app

        matched_products = []
        for product in app.products:
            if self.category != "Semua" and product["category"] != self.category:
                continue
            if self.query.lower() not in product["name"].lower():
                continue
            matched_products.append(product)

        # Penanganan Empty State (Jika tidak ada menu yang cocok)
        if not matched_products:
            empty_card = Card(
                orientation="vertical", padding=dp(20), spacing=dp(8),
                size_hint_y=None, height=dp(130), color=WHITE
            )
            empty_card.add_widget(Text(
                "Menu Tidak Ditemukan", size=16, bold=True, color=COFFEE, align="center"
            ))
            empty_card.add_widget(Text(
                f"Tidak ada menu yang sesuai dengan pencarian '{self.query}' pada kategori '{self.category}'.",
                size=12, color=MUTED, align="center"
            ))
            empty_card.add_widget(button("TAMPILKAN SEMUA MENU", self.reset_search, True, 38))
            self.grid.add_widget(empty_card)
            return

        # Render Kartu Produk
        for product in matched_products:
            pid = product["id"]
            stok = int(product["stok"])
            qty_in_cart = app.cart.get(pid, 0)
            is_out_of_stock = stok <= 0

            card = Card(
                orientation="horizontal", padding=dp(12),
                spacing=dp(12), size_hint_y=None, height=dp(235),
                color=SURFACE if not is_out_of_stock else CREAM
            )

            # Bagian Kiri: Gambar Produk / Visual Kategori
            custom_image = product.get("image_path")
            image_name = PRODUCT_IMAGES.get(product["name"])
            bundled_image = PRODUCT_IMAGE_DIR / image_name if image_name else None
            image_path = (
                Path(custom_image) if custom_image else bundled_image
            )
            if image_path is not None and image_path.exists():
                photo = Image(
                    source=str(image_path),
                    size_hint=(None, 1), width=dp(120),
                    fit_mode="contain"
                )
                card.add_widget(photo)
            else:
                art = Card(
                    size_hint=(None, 1), width=dp(120),
                    color=ART_BY_CATEGORY.get(product["category"], ACCENT)
                )
                art.add_widget(Text(
                    product["category"].upper(),
                    size=13, bold=True, align="center", color=ON_ACCENT
                ))
                card.add_widget(art)

            # Bagian Kanan: Detail Informasi & Tombol Kasir
            details = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_x=1)

            # Header Kategori
            details.add_widget(Text(
                product["category"].upper(), size=10, bold=True,
                color=ART_BY_CATEGORY.get(product["category"], ACCENT_TEXT),
                size_hint_y=None, height=dp(16)
            ))

            # Nama Produk (ketinggian tetap agar baris aksi di bawah sejajar sempurna)
            details.add_widget(Text(
                product["name"], size=14, bold=True, color=COFFEE,
                size_hint_y=None, height=dp(30)
            ))

            # Badge Status Stok Dinamis
            if is_out_of_stock:
                stock_text = "STOK HABIS"
                stock_color = DANGER_TEXT
            elif stok < 15:
                stock_text = f"Sisa Sedikit: {stok} item"
                stock_color = WARNING_TEXT
            else:
                stock_text = f"Tersedia: {stok} item"
                stock_color = MUTED

            details.add_widget(Text(
                stock_text, size=11, bold=(stok < 15), color=stock_color,
                size_hint_y=None, height=dp(16)
            ))

            # Harga Produk Tegas
            details.add_widget(Text(
                rp(product["price"]), size=15, bold=True, color=COFFEE,
                size_hint_y=None, height=dp(22)
            ))

            # Spacer fleksibel untuk menjamin baris tombol aksi selalu sejajar di dasar kartu
            details.add_widget(BoxLayout())

            # Baris Aksi Kasir: Counter ringkas [-] [qty] [+] atau tombol "TAMBAH +"
            action_row = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(44))
            if is_out_of_stock:
                action_row.add_widget(Text(
                    "Stok habis. Gunakan Manajemen Stok.",
                    size=10, bold=True, color=DANGER_TEXT
                ))
            elif qty_in_cart > 0:
                # Tombol Minus (-) berwarna merah redup
                btn_minus = button(
                    "-",
                    lambda p=product: self.minus_and_refresh(p),
                    False, 44, outline=True, outline_color=CORAL
                )
                btn_minus.size_hint_x = None
                btn_minus.width = dp(44)
                action_row.add_widget(btn_minus)

                # Indikator angka kuantitas
                action_row.add_widget(Text(
                    f"{qty_in_cart}", size=13, bold=True, color=COFFEE,
                    size_hint=(None, 1), width=dp(34), align="center"
                ))

                # Tombol Plus (+) berwarna hijau solid
                btn_plus = button(
                    "+",
                    lambda p=product: self.add_and_refresh(p),
                    True, 44
                )
                btn_plus.size_hint_x = None
                btn_plus.width = dp(44)
                action_row.add_widget(btn_plus)

                action_row.add_widget(Text("di keranjang", size=10, color=MUTED, align="left"))
            else:
                btn_add = button(
                    "TAMBAH +",
                    lambda p=product: self.add_and_refresh(p),
                    True, 44
                )
                action_row.add_widget(btn_add)

            details.add_widget(action_row)

            # Tombol hapus dipisahkan dari aksi keranjang agar tidak mudah tersentuh.
            delete_button = button(
                "HAPUS PRODUK",
                lambda p=product: self.confirm_delete_product(p),
                False, 32, outline=True, outline_color=DANGER_TEXT
            )
            details.add_widget(delete_button)
            card.add_widget(details)
            self.grid.add_widget(card)

    def confirm_delete_product(self, product):
        """Meminta konfirmasi sebelum produk diarsipkan dari katalog aktif."""
        content = BoxLayout(
            orientation="vertical", padding=dp(16), spacing=dp(10)
        )
        content.add_widget(Text(
            f"Yakin ingin menghapus produk '{product['name']}' dari katalog?\n"
            "Produk tidak akan muncul lagi saat kasir memilih menu. "
            "Riwayat transaksi lama tetap tersimpan.",
            align="center", size=13, color=TEXT
        ))
        popup = themed_popup(
            "Konfirmasi Hapus Produk", content,
            size_hint=(0.86, None), height=dp(235),
            auto_dismiss=False,
        )
        _style_popup_text_white(popup, content)
        actions = BoxLayout(
            size_hint_y=None, height=dp(42), spacing=dp(8)
        )
        actions.add_widget(button("BATAL", popup.dismiss, False, 40))
        actions.add_widget(button(
            "YA, HAPUS", lambda: self.delete_product(product, popup), True, 40
        ))
        content.add_widget(actions)
        popup.open()

    def delete_product(self, product, popup):
        """Mengarsipkan produk dan memperbarui katalog setelah konfirmasi."""
        app = self.manager.app
        try:
            app.delete_product(product["id"])
        except Exception as error:
            app.notice(f"Produk gagal dihapus:\n{error}")
            return

        popup.dismiss()
        self.render_products()
        app.notice(
            f"Produk '{product['name']}' berhasil dihapus dari katalog.\n"
            "Riwayat transaksi lama tetap aman."
        )

    def add_and_refresh(self, product):
        """Menambahkan produk ke keranjang belanja dan memperbarui indikator kartu secara instan."""
        self.manager.app.add_product(product)
        self.render_products()

    def minus_and_refresh(self, product):
        """Mengurangi kuantitas produk dari keranjang dan memperbarui indikator kartu secara instan."""
        self.manager.app.change_qty(product["id"], -1)
        self.render_products()


class CartPage(Page):
    """Halaman Keranjang Belanja dan Alur Pembayaran Kasir."""

    def on_pre_enter(self, *_):
        self.render()

    def render(self):
        self.content.clear_widgets()
        app = self.manager.app
        self.heading("Keranjang", "Periksa pesanan sebelum pembayaran")

        if not app.cart:
            self.content.add_widget(Text(
                "Keranjang masih kosong. Buka Menu Produk untuk mulai pesanan.",
                size=14, color=MUTED,
                size_hint_y=None, height=dp(80)
            ))
            self.content.add_widget(button(
                "BUKA MENU PRODUK",
                lambda: app.go("products"), True, 46
            ))
            return

        # 1. Grid 2 Kolom Sejajar Horizontal: Form Data Transaksi (Kiri) & Hero Component Total (Kanan)
        grid_top = GridLayout(cols=2, spacing=dp(12), size_hint=(1, None), height=dp(140))

        # Panel Kiri: Tanggal & Nama Pelanggan / No. Meja
        left_box = Card(
            orientation="vertical", padding=dp(14), spacing=dp(6),
            size_hint=(1, 1), color=WHITE, radius=14
        )
        left_box.add_widget(Text("DATA TRANSAKSI", size=10, bold=True, color=MUTED, size_hint_y=None, height=dp(16)))
        today_str = datetime.now().strftime("%d %b %Y, %H:%M WIB")
        left_box.add_widget(Text(f"Waktu: {today_str}", size=12, bold=True, color=COFFEE, size_hint_y=None, height=dp(20)))
        left_box.add_widget(Text("Nama Pelanggan / No. Meja:", size=11, bold=True, color=BROWN, size_hint_y=None, height=dp(18)))
        customer_input = text_input(
            text=getattr(app, "customer_name", ""),
            hint_text=(
                f"Maks. {MAX_CUSTOMER_LABEL_LENGTH} karakter, "
                "contoh: Meja 03 / Kak Budi"
            ),
            height=38, font_size=13,
        )
        def on_customer_change(instance, val):
            if len(val) > MAX_CUSTOMER_LABEL_LENGTH:
                cursor_column, cursor_row = instance.cursor
                val = val[:MAX_CUSTOMER_LABEL_LENGTH]
                instance.text = val
                instance.cursor = (
                    min(cursor_column, MAX_CUSTOMER_LABEL_LENGTH), cursor_row
                )
            app.customer_name = val
        customer_input.bind(text=on_customer_change)
        left_box.add_widget(customer_input)
        grid_top.add_widget(left_box)

        # Panel Kanan: Hero Component Total Harga (Font 26 Bold Tajam)
        right_box = Card(
            orientation="vertical", padding=dp(14), spacing=dp(4),
            size_hint=(1, 1), color=CREAM, radius=14
        )
        total_items = sum(app.cart.values())
        right_box.add_widget(Text("RINGKASAN TOTAL TAGIHAN", size=10, bold=True, color=MUTED, size_hint_y=None, height=dp(16)))
        right_box.add_widget(Text(f"{total_items} item di dalam pesanan", size=11, color=COFFEE, size_hint_y=None, height=dp(18)))
        hero_total = Text(
            rp(app.cart_total()),
            size=26, bold=True, color=ACCENT_TEXT,
            size_hint_y=None, height=dp(42)
        )
        right_box.add_widget(hero_total)
        right_box.add_widget(Text("Siap diproses ke pembayaran kasir", size=11, color=MUTED, size_hint_y=None, height=dp(18)))
        grid_top.add_widget(right_box)

        self.content.add_widget(grid_top)

        # Judul Daftar Pesanan
        self.content.add_widget(Text("Daftar Item Pesanan", size=15, bold=True, color=COFFEE, size_hint_y=None, height=dp(24)))

        # 2. List Item Keranjang dengan Counter Ringkas
        for pid, qty in list(app.cart.items()):
            product = app.products_by_id[pid]
            row = Card(
                orientation="horizontal", padding=dp(12),
                spacing=dp(10), size_hint_y=None, height=dp(84), color=WHITE, radius=12
            )
            info = BoxLayout(orientation="vertical", spacing=dp(2))
            info.add_widget(Text(product["name"], size=13, bold=True, color=COFFEE))
            info.add_widget(Text(
                f"{qty} x {rp(product['price'])} = {rp(product['price'] * qty)}",
                size=11, color=MUTED
            ))
            row.add_widget(info)

            # Tombol counter - [qty] +
            btn_sub = button(
                "-",
                lambda p=pid: app.change_qty(p, -1),
                False, 44, outline=True, outline_color=CORAL
            )
            btn_sub.size_hint_x = None
            btn_sub.width = dp(44)
            row.add_widget(btn_sub)

            qty_input = text_input(
                text=str(qty), height=44, font_size=13,
                input_filter="int", halign="center",
            )
            qty_input.size_hint_x = None
            qty_input.width = dp(60)

            def apply_qty(*_, product_id=pid, field=qty_input):
                app.set_qty(product_id, field.text)

            qty_input.bind(on_text_validate=apply_qty)
            row.add_widget(qty_input)

            apply_button = button("OK", apply_qty, False, 44)
            apply_button.size_hint_x = None
            apply_button.width = dp(46)
            row.add_widget(apply_button)

            btn_add = button(
                "+",
                lambda p=pid: app.change_qty(p, 1),
                True, 44
            )
            btn_add.size_hint_x = None
            btn_add.width = dp(44)
            row.add_widget(btn_add)

            self.content.add_widget(row)

        # 3. Tombol Aksi Kasir
        self.content.add_widget(button("LANJUT PEMBAYARAN", app.checkout, True, 48))
        self.content.add_widget(button(
            "KOSONGKAN KERANJANG", app.clear_cart, False, 44, outline=True, outline_color=CORAL
        ))


class ReportsPage(Page):
    """Halaman Riwayat Transaksi dan Manajemen Laporan Penjualan."""

    def on_pre_enter(self, *_):
        self.render()

    def render(self):
        self.content.clear_widgets()
        app = self.manager.app

        period_labels = dict(REPORT_PERIODS)
        active_period = app.report_period
        active_label = period_labels.get(active_period, "HARIAN")
        filtered_orders = list(getattr(app, "report_orders", []))
        period_total = sum(order["total"] for order in filtered_orders)

        # Header menampilkan ringkasan berdasarkan query periode yang aktif.
        header_card = Card(
            orientation="vertical",
            padding=[dp(18), dp(15), dp(18), dp(15)],
            spacing=dp(6),
            size_hint=(1, None),
            height=dp(148),
            color=WHITE,
            radius=16
        )
        header_card.add_widget(Text(
            "Laporan Penjualan", size=21, bold=True, color=COFFEE,
            size_hint_y=None, height=dp(28)
        ))
        header_card.add_widget(Text(
            "Rekap nota transaksi yang tersimpan di database",
            size=11, color=MUTED, size_hint_y=None, height=dp(18)
        ))
        header_card.add_widget(Text(
            f"{active_label}: {rp(period_total)}",
            size=17, bold=True, color=ACCENT_TEXT, size_hint_y=None, height=dp(26)
        ))
        header_card.add_widget(Text(
            f"{len(filtered_orders)} transaksi  |  {app.report_range_label()}",
            size=11, color=MUTED, size_hint_y=None, height=dp(20)
        ))
        self.content.add_widget(header_card)

        filter_card = Card(
            orientation="vertical", padding=[dp(12), dp(10), dp(12), dp(10)],
            spacing=dp(8), size_hint_y=None, height=dp(96),
            color=CREAM, radius=12
        )
        filter_card.add_widget(Text(
            "Periode laporan", size=11, bold=True, color=COFFEE,
            size_hint_y=None, height=dp(18)
        ))
        filter_row = GridLayout(
            cols=4, spacing=dp(8), size_hint_y=None, height=dp(44)
        )
        for period, label in REPORT_PERIODS:
            is_active = active_period == period
            filter_row.add_widget(button(
                label,
                lambda p=period: app.set_report_period(p),
                is_active, 44,
                fill_color=ACCENT if is_active else WHITE,
                text_color=ON_ACCENT if is_active else TEXT,
            ))
        filter_card.add_widget(filter_row)
        self.content.add_widget(filter_card)

        if app.report_loading:
            self.content.add_widget(Text(
                "Memuat laporan...", size=14, color=MUTED, align="center",
                size_hint_y=None, height=dp(80)
            ))
            return

        if app.report_error:
            error_card = Card(
                orientation="vertical", padding=dp(18), spacing=dp(8),
                size_hint_y=None, height=dp(150), color=WHITE, radius=14
            )
            error_card.add_widget(Text(
                "Laporan tidak dapat dimuat", size=15, bold=True,
                color=DANGER_TEXT, align="center"
            ))
            error_card.add_widget(Text(
                app.report_error, size=11, color=MUTED, align="center"
            ))
            error_card.add_widget(button(
                "COBA LAGI",
                lambda: app.set_report_period(app.report_period),
                True, 44
            ))
            self.content.add_widget(error_card)
            return

        if not filtered_orders:
            empty_card = Card(
                orientation="vertical", padding=dp(20), spacing=dp(6),
                size_hint_y=None, height=dp(100), color=WHITE, radius=14
            )
            empty_card.add_widget(Text(
                f"Belum ada transaksi {active_label.lower()}.",
                size=14, bold=True, color=MUTED, align="center"
            ))
            empty_card.add_widget(Text(
                "Selesaikan pesanan di menu Keranjang untuk mengisi laporan ini.",
                size=12, color=MUTED, align="center"
            ))
            self.content.add_widget(empty_card)

        for order in filtered_orders:
            row = Card(
                orientation="vertical", padding=[dp(16), dp(12), dp(16), dp(12)],
                spacing=dp(6), size_hint_y=None, height=dp(94),
                color=WHITE, radius=14
            )
            
            # Baris Atas: ID Nota, Waktu, dan Badge Chip Metode Bayar
            top_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(22), spacing=dp(8))
            top_row.add_widget(Text(
                f"{order['id']}", size=13, bold=True, color=COFFEE,
                size_hint_x=None, width=dp(80)
            ))
            top_row.add_widget(Text(
                f"{order['date']}  {order['time']}", size=11, color=MUTED,
                size_hint_x=None, width=dp(138)
            ))
            top_row.add_widget(BoxLayout()) # spacer

            pm = order.get("payment", "-")
            chip_color = ACCENT if "E-Wallet" in pm else (GREEN if "Tunai" in pm else PURPLE)
            top_row.add_widget(status_chip(pm, chip_color, width=130, height=28))
            row.add_widget(top_row)

            # Baris Bawah: Total Belanja & Info Kembalian
            kembalian_info = f"   [Kembalian: {rp(order['kembalian'])}]" if order.get("kembalian", 0) > 0 else ""
            bot_text = f"Total: {rp(order['total'])}{kembalian_info}"
            row.add_widget(Text(bot_text, size=13, bold=True, color=ACCENT_TEXT))
            self.content.add_widget(row)

            actions = BoxLayout(
                orientation="horizontal", size_hint_y=None,
                height=dp(44), spacing=dp(8)
            )
            actions.add_widget(button(
                "LIHAT STRUK",
                lambda o=order: app.show_saved_receipt(o), False, 44
            ))
            actions.add_widget(button(
                "HAPUS",
                lambda o=order: app.confirm_delete_order(o), False, 44,
                outline=True, outline_color=CORAL
            ))
            self.content.add_widget(actions)