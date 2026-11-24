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
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.uix.image import Image
from kivy.uix.textinput import TextInput
from kivy.uix.behaviors import ButtonBehavior
from kivy.core.window import Window
from kivy.uix.spinner import Spinner
from kivy.utils import platform

from database import (
    MAX_CUSTOMER_LABEL_LENGTH, MAX_PRODUCT_NAME_LENGTH, MAX_PRODUCT_STOCK,
)

from config import (
    ASSETS_DIR, BEST_SELLER_PRODUCTS, ICE_LEVELS, LOGO_PATH, PRODUCT_IMAGE_DIR,
    PRODUCT_IMAGES, SUGAR_LEVELS, ART_BY_CATEGORY, VOUCHER_CODES,
)
from theme import (
    ACCENT, ACCENT_DARK, ACCENT_TEXT, ACCENT_THEMES, BORDER, BORDER_STRONG,
    BROWN, COFFEE, CREAM, CORAL, DANGER_TEXT, GREEN, INPUT, MUTED, ON_ACCENT,
    PURPLE, SUCCESS_TEXT, SURFACE, SURFACE_ALT, TEXT, WARNING_TEXT, WHITE, accent_color,
)
from ui_components import (
    Text, Card, Page, RevenueTrendChart, button, dashboard_hero_card,
    dashboard_mini_card, metric_card, rp, status_chip, text_input,
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


def _responsive_columns(width, min_card_width, max_columns, spacing):
    return max(1, min(max_columns, int((width + spacing) / (min_card_width + spacing))))


def _configure_responsive_grid(grid, min_card_width, max_columns, spacing):
    def update_columns(widget, width):
        widget.cols = _responsive_columns(
            width, min_card_width, max_columns, spacing
        )

    grid.bind(width=update_columns)
    update_columns(grid, grid.width)


_BRAND_BG = (0.169, 0.102, 0.071, 1)
_BRAND_TEXT = (0.965, 0.922, 0.855, 1)
_BRAND_MUTED = (0.80, 0.735, 0.65, 1)


class RoleRow(ButtonBehavior, BoxLayout):
    """Baris pilihan peran: lencana inisial, judul, deskripsi singkat, dan panah."""

    def __init__(self, title, subtitle, initial, callback, **kwargs):
        super().__init__(
            orientation="horizontal", size_hint_y=None, height=dp(68),
            padding=[dp(14), dp(12), dp(14), dp(12)], spacing=dp(14),
            **kwargs
        )
        self._hover = False
        with self.canvas.before:
            self._fill = Color(*SURFACE)
            self._shape = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(14)]
            )
            self._edge_color = Color(*BORDER)
            self._edge = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, dp(14)),
                width=1.1,
            )
        self.bind(pos=self._redraw, size=self._redraw, state=self._restyle)

        badge = Card(
            color=ACCENT, radius=11, size_hint=(None, None),
            size=(dp(42), dp(42)), pos_hint={"center_y": 0.5},
        )
        badge.add_widget(Text(
            initial, size=18, bold=True, color=ON_ACCENT, align="center",
        ))
        self.add_widget(badge)

        texts = BoxLayout(orientation="vertical", spacing=0)
        texts.add_widget(Text(
            title, size=15, bold=True, size_hint_y=None, height=dp(22),
        ))
        texts.add_widget(Text(
            subtitle, size=12, color=MUTED, size_hint_y=None, height=dp(18),
        ))
        self.add_widget(texts)

        self.add_widget(Text(
            "\u203a", size=24, color=MUTED, align="center",
            size_hint=(None, 1), width=dp(18),
        ))
        self.bind(on_release=lambda *_: callback() if callback else None)

    def _redraw(self, *_):
        self._shape.pos = self.pos
        self._shape.size = self.size
        self._edge.rounded_rectangle = (
            self.x, self.y, self.width, self.height, dp(14)
        )

    def _restyle(self, *_):
        active = self._hover or self.state == "down"
        self._fill.rgba = SURFACE_ALT if active else SURFACE
        self._edge_color.rgba = ACCENT if active else BORDER

    def on_parent(self, _widget, parent):
        if parent is not None:
            Window.bind(mouse_pos=self._on_mouse)
        else:
            Window.unbind(mouse_pos=self._on_mouse)

    def _on_mouse(self, _window, pos):
        if self.get_root_window() is None:
            return
        inside = self.collide_point(*self.to_widget(*pos))
        if inside != self._hover:
            self._hover = inside
            self._restyle()


class LoginPage(Page):
    """Halaman login dua panel: merek di kiri, pilihan peran di kanan."""

    def _adapt_content_padding(self, _widget, _width):
        # Halaman login memakai seluruh lebar jendela tanpa padding.
        self.content.padding = [0, 0, 0, 0]

    def on_pre_enter(self, *_):
        self.render()

    def on_leave(self, *_):
        self._unbind_layout()

    def _unbind_layout(self):
        sync = getattr(self, "_login_sync", None)
        if sync is not None:
            self.unbind(height=sync)
            self._login_sync = None

    def render(self):
        self._unbind_layout()
        self.content.clear_widgets()
        self.content.padding = [0, 0, 0, 0]
        self.content.spacing = 0

        outer = BoxLayout(
            orientation="horizontal", size_hint=(1, None), height=dp(640),
        )

        # ---------- Panel kiri: merek ----------
        brand = FloatLayout(size_hint=(0.46, 1))
        banner_path = ASSETS_DIR / "login_banner.jpg"
        has_photo = banner_path.exists()
        if has_photo:
            brand.add_widget(Image(
                source=str(banner_path), size_hint=(1, 1),
                pos_hint={"x": 0, "y": 0}, fit_mode="cover",
            ))
        brand.add_widget(Card(
            color=tuple(_BRAND_BG[:3]) + (0.80 if has_photo else 1.0,),
            radius=0, size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        ))

        box = BoxLayout(
            orientation="vertical", size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
            padding=[dp(48), dp(44), dp(48), dp(40)], spacing=0,
        )
        mark = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(52),
            spacing=dp(14),
        )
        if LOGO_PATH.exists():
            tile = Card(
                color=(1, 1, 1, 1), radius=12, size_hint=(None, None),
                size=(dp(52), dp(52)), padding=dp(5),
            )
            tile.add_widget(Image(source=str(LOGO_PATH), fit_mode="contain"))
            mark.add_widget(tile)
        mark.add_widget(Text(
            "Kopi Nako", size=22, bold=True, color=_BRAND_TEXT,
        ))
        box.add_widget(mark)
        box.add_widget(BoxLayout())

        tagline = Text(
            "Kopi enak,\nsuasana nyaman.", size=38, bold=True,
            color=_BRAND_TEXT, size_hint_y=None, height=dp(104),
        )
        box.add_widget(tagline)
        gap = BoxLayout(size_hint_y=None, height=dp(16))
        box.add_widget(gap)
        sub = Text(
            "Catat pesanan, kelola stok, dan tutup hari dengan rapi.",
            size=14, color=_BRAND_MUTED, size_hint_y=None, height=dp(48),
        )
        box.add_widget(sub)
        box.add_widget(BoxLayout())
        footer = Text(
            "POS Kopi Nako", size=12, color=_BRAND_MUTED,
            size_hint_y=None, height=dp(20),
        )
        box.add_widget(footer)
        brand.add_widget(box)

        # ---------- Panel kanan: pilihan peran ----------
        entry = AnchorLayout(
            anchor_x="center", anchor_y="center", size_hint=(0.54, 1),
            padding=[dp(24), dp(24), dp(24), dp(24)],
        )
        form = BoxLayout(
            orientation="vertical", size_hint=(None, None),
            width=dp(400), height=dp(520),
        )

        def space(height):
            return BoxLayout(size_hint_y=None, height=dp(height))

        def open_role(role):
            return lambda: self.manager.app.open_login_dialog(role)

        form.add_widget(Text(
            "Selamat datang", size=28, bold=True,
            size_hint_y=None, height=dp(40),
        ))
        form.add_widget(Text(
            "Pilih peran Anda untuk masuk ke aplikasi.",
            size=13, color=MUTED, size_hint_y=None, height=dp(24),
        ))
        form.add_widget(space(24))

        form.add_widget(Text(
            "Tim Kopi Nako", size=12, bold=True, color=MUTED,
            size_hint_y=None, height=dp(22),
        ))
        form.add_widget(space(8))
        form.add_widget(RoleRow(
            "Admin", "Kelola menu, stok, dan laporan", "A",
            open_role("admin"),
        ))
        form.add_widget(space(10))
        form.add_widget(RoleRow(
            "Kasir", "Terima pesanan dan pembayaran", "K",
            open_role("kasir"),
        ))
        form.add_widget(space(20))
        form.add_widget(Card(
            color=BORDER, radius=0, size_hint_y=None, height=dp(1),
        ))
        form.add_widget(space(20))

        form.add_widget(Text(
            "Pelanggan", size=12, bold=True, color=MUTED,
            size_hint_y=None, height=dp(22),
        ))
        form.add_widget(space(8))
        form.add_widget(RoleRow(
            "Pelanggan", "Pesan dan lihat riwayat belanja", "P",
            open_role("pelanggan"),
        ))
        form.add_widget(space(14))
        form.add_widget(Text(
            "Belum punya akun?", size=12, color=MUTED, align="center",
            size_hint_y=None, height=dp(20),
        ))
        register_btn = button(
            "Daftar sebagai pelanggan",
            lambda: self.manager.app.open_customer_registration(),
            False, 38, fill_color=(0, 0, 0, 0), text_color=ACCENT_TEXT,
        )
        register_btn.font_size = dp(13)
        form.add_widget(register_btn)
        form.add_widget(BoxLayout())
        form.add_widget(Text(
            "POS Kopi Nako \u00b7 Point of Sale", size=11, color=MUTED,
            align="center", size_hint_y=None, height=dp(18),
        ))
        entry.add_widget(form)

        def fit_form(_widget, width):
            form.width = min(dp(400), max(dp(260), width - dp(48)))
        entry.bind(width=fit_form)
        fit_form(entry, entry.width)

        outer.add_widget(brand)
        outer.add_widget(entry)
        self.content.add_widget(outer)

        def sync(*_):
            wide = outer.width >= dp(820)
            if wide:
                outer.orientation = "horizontal"
                outer.height = max(dp(620), self.height)
                brand.size_hint = (0.46, 1)
                entry.size_hint = (0.54, 1)
                box.padding = [dp(48), dp(44), dp(48), dp(40)]
                tagline.font_size = dp(38)
                tagline.height = dp(104)
                gap.height = dp(16)
                sub.height = dp(48)
                footer.height = dp(20)
                sub.opacity = footer.opacity = 1
            else:
                outer.orientation = "vertical"
                brand.size_hint = (1, None)
                brand.height = dp(200)
                entry.size_hint = (1, None)
                entry.height = dp(560)
                outer.height = brand.height + entry.height
                box.padding = [dp(24), dp(20), dp(24), dp(20)]
                tagline.font_size = dp(22)
                tagline.height = dp(60)
                gap.height = 0
                sub.height = 0
                footer.height = 0
                sub.opacity = footer.opacity = 0

        self._login_sync = sync
        self.bind(height=sync)
        outer.bind(width=sync)
        sync()


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

        # 1. Header Baris Atas: Judul Dashboard & Tombol Aksi Utama (seperti gambar referensi)
        top_header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(54),
            spacing=dp(12),
        )
        title_box = BoxLayout(orientation="vertical", spacing=dp(2))
        if role_kasir == "admin":
            subtitle_text = f"Panel Administrator: {nama_kasir}  •  Ringkasan aktivitas bisnis Anda"
        elif role_kasir == "kasir":
            subtitle_text = f"Terminal Kasir: {nama_kasir}  •  Ringkasan operasional kasir hari ini"
        else:
            subtitle_text = "Ringkasan aktivitas bisnis Anda"

        dashboard_title = Text(
            "Dashboard", size=22, bold=True, color=COFFEE,
            size_hint_y=None, height=dp(30),
        )
        title_box.add_widget(dashboard_title)
        dashboard_subtitle = Text(
            subtitle_text, size=12, color=MUTED,
            size_hint_y=None, height=dp(20),
        )
        title_box.add_widget(dashboard_subtitle)
        top_header.add_widget(title_box)

        self.clock_time = Text(
            datetime.now().strftime("%H:%M"), size=14, bold=True, color=MUTED,
            size_hint_x=None, width=dp(58), align="right",
        )
        self.clock_date = Text(
            datetime.now().strftime("%d %b %Y"), size=11, color=MUTED,
            size_hint_x=None, width=dp(85), align="right",
        )
        top_header.add_widget(self.clock_time)
        top_header.add_widget(self.clock_date)

        if role_kasir == "admin":
            cta_btn = button(
                "+ Kelola Katalog",
                lambda: app.go("products"),
                True, 42,
                fill_color=ACCENT,
                text_color=ON_ACCENT,
            )
        else:
            cta_btn = button(
                "+ Transaksi Baru",
                app.new_order,
                True, 42,
                fill_color=ACCENT,
                text_color=ON_ACCENT,
            )
        cta_btn.size_hint_x = None
        cta_btn.width = dp(168)
        top_header.add_widget(cta_btn)

        def adapt_dashboard_header(_widget, width):
            narrow = width < dp(620)
            top_header.spacing = dp(6 if narrow else 12)
            self.clock_time.width = dp(48 if narrow else 58)
            self.clock_date.width = dp(0 if narrow else 85)
            self.clock_date.opacity = 0 if narrow else 1
            cta_btn.width = dp(112 if narrow else 168)
            dashboard_title.font_size = dp(18 if narrow else 22)
            dashboard_subtitle.font_size = dp(9 if narrow else 12)
            dashboard_subtitle.height = dp(16 if narrow else 20)
            dashboard_subtitle.text = (
                "Panel Administrator" if role_kasir == "admin"
                else "Terminal Kasir" if role_kasir == "kasir"
                else "Ringkasan"
            ) if narrow else subtitle_text

        top_header.bind(width=adapt_dashboard_header)
        adapt_dashboard_header(top_header, top_header.width)
        main_layout.add_widget(top_header)

        # 2. Baris 1: 4 Kartu Metrik Berwarna Solid Sejajar (Royal Blue, Emerald, Violet, Amber)
        metrics = app.home_metrics()
        today_sales_val = float(metrics["sales"]["value"])
        today_profit_val = today_sales_val * 0.45
        monthly_sales_val = float(app.sales_this_month())
        monthly_target_val = 15000000.0
        target_ratio = min(1.0, monthly_sales_val / monthly_target_val) if monthly_target_val > 0 else 0.0
        target_pct = int(round(target_ratio * 100))

        hero_grid = GridLayout(
            cols=4, spacing=dp(14), size_hint_y=None,
        )
        hero_grid.bind(minimum_height=hero_grid.setter("height"))
        _configure_responsive_grid(hero_grid, dp(210), 4, dp(14))
        if role_kasir == "kasir":
            first_hero = dashboard_hero_card(
                "Item di Keranjang",
                f"{sum(app.cart.values())} Item",
                "Pesanan aktif di keranjang",
                (0.26, 0.31, 0.85, 1),
                icon_text="$",
            )
        else:
            first_hero = dashboard_hero_card(
                "Penjualan Hari Ini",
                rp(today_sales_val),
                "Total penjualan hari ini",
                (0.26, 0.31, 0.85, 1),
                icon_text="$",
            )

        hero_grid.add_widget(first_hero)
        hero_grid.add_widget(dashboard_hero_card(
            "Profit Hari Ini",
            rp(today_profit_val),
            "Profit bersih hari ini (est. 45%)",
            (0.06, 0.58, 0.42, 1),
            icon_text="%",
        ))
        hero_grid.add_widget(dashboard_hero_card(
            "Target Bulan Ini",
            f"{target_pct}%",
            f"{rp(monthly_sales_val)} / {rp(monthly_target_val)}",
            (0.31, 0.27, 0.90, 1),
            icon_text="O",
            progress=target_ratio,
        ))
        hero_grid.add_widget(dashboard_hero_card(
            "Transaksi Hari Ini",
            f"{metrics['transactions']['value']}",
            "Transaksi",
            (0.87, 0.48, 0.07, 1),
            icon_text="#",
        ))
        main_layout.add_widget(hero_grid)

        # 3. Baris 2: 4 Kartu Putih Ringkas Sejajar (Total Kategori, Produk, Transaksi, Stok/Status)
        categories_count = len({p.get("category") for p in app.products}) or 3
        low_stock_items = [p for p in app.products if int(p["stok"]) < 15]
        mini_grid = GridLayout(
            cols=4, spacing=dp(14), size_hint_y=None,
        )
        mini_grid.bind(minimum_height=mini_grid.setter("height"))
        _configure_responsive_grid(mini_grid, dp(210), 4, dp(14))
        mini_grid.add_widget(dashboard_mini_card(
            "Total Kategori", categories_count, icon_text="::", border_color=BORDER
        ))
        mini_grid.add_widget(dashboard_mini_card(
            "Total Produk", len(app.products), icon_text="[]", border_color=BORDER
        ))
        mini_grid.add_widget(dashboard_mini_card(
            "Total Transaksi", len(app.orders), icon_text="TX", border_color=BORDER
        ))
        mini_grid.add_widget(dashboard_mini_card(
            "Stok Menipis (<15)", len(low_stock_items), icon_text="!", border_color=BORDER
        ))
        main_layout.add_widget(mini_grid)

        if low_stock_items:
            alert_names = ", ".join(
                f"{p['name']} ({p['stok']})" for p in low_stock_items[:4]
            )
            if len(low_stock_items) > 4:
                alert_names += f", +{len(low_stock_items) - 4} lainnya"
            low_stock_card = Card(
                orientation="horizontal",
                padding=[dp(16), dp(10), dp(16), dp(10)],
                spacing=dp(12),
                size_hint_y=None,
                height=dp(62),
                color=CREAM,
                radius=12,
                border_color=WARNING_TEXT,
            )
            alert_info = BoxLayout(orientation="vertical", spacing=dp(2))
            alert_info.add_widget(Text(
                f"Peringatan Stok Menipis ({len(low_stock_items)} Menu < 15 Item)",
                size=12, bold=True, color=DANGER_TEXT,
                size_hint_y=None, height=dp(20),
            ))
            alert_info.add_widget(Text(
                alert_names, size=11, color=COFFEE,
                size_hint_y=None, height=dp(20),
            ))
            low_stock_card.add_widget(alert_info)
            restock_btn = button(
                "CEK STOK", lambda: app.go("products"), True, 40
            )
            restock_btn.size_hint_x = None
            restock_btn.width = dp(120)
            low_stock_card.add_widget(restock_btn)

            def adapt_low_stock_alert(_widget, width):
                narrow = width < dp(520)
                low_stock_card.height = dp(72 if narrow else 62)
                restock_btn.width = dp(0 if narrow else 120)
                restock_btn.opacity = 0 if narrow else 1
                restock_btn.disabled = narrow

            low_stock_card.bind(width=adapt_low_stock_alert)
            adapt_low_stock_alert(low_stock_card, low_stock_card.width)
            main_layout.add_widget(low_stock_card)

        # 4. Baris 3: Kartu Grafik Tren Pendapatan (Persis Gambar Referensi)
        chart_card = Card(
            orientation="vertical",
            padding=[dp(18), dp(16), dp(18), dp(14)],
            spacing=dp(10),
            size_hint_y=None,
            height=dp(295),
            color=WHITE,
            radius=14,
            border_color=BORDER,
        )
        chart_header = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(38), spacing=dp(10)
        )
        chart_icon = Card(
            orientation="vertical",
            size_hint=(None, None),
            size=(dp(34), dp(34)),
            color=tuple(ACCENT[:3]) + (0.14,),
            radius=9,
        )
        chart_icon.add_widget(Text(
            "||", size=12, bold=True, color=ACCENT_TEXT, align="center"
        ))
        chart_header.add_widget(chart_icon)

        chart_titles = BoxLayout(orientation="vertical", spacing=dp(1))
        chart_titles.add_widget(Text(
            "Tren Pendapatan", size=13, bold=True, color=COFFEE,
            size_hint_y=None, height=dp(18),
        ))
        chart_titles.add_widget(Text(
            "7 hari terakhir", size=10, color=MUTED,
            size_hint_y=None, height=dp(16),
        ))
        chart_header.add_widget(chart_titles)

        if role_kasir == "admin":
            btn_left = button("KELOLA KATALOG", lambda: app.go("products"), False, 34)
            btn_right = button("AUDIT LAPORAN", lambda: app.go("reports"), False, 34)
        else:
            btn_left = button("LIHAT KERANJANG", lambda: app.go("cart"), False, 34)
            btn_right = button("RIWAYAT TRANSAKSI", lambda: app.go("reports"), False, 34)
        btn_left.size_hint_x = None
        btn_left.width = dp(145)
        btn_right.size_hint_x = None
        btn_right.width = dp(155)
        chart_header.add_widget(btn_left)
        chart_header.add_widget(btn_right)

        def adapt_chart_header(_widget, width):
            narrow = width < dp(660)
            for action_button in (btn_left, btn_right):
                action_button.width = dp(0 if narrow else 150)
                action_button.opacity = 0 if narrow else 1
                action_button.disabled = narrow
            chart_header.spacing = dp(6 if narrow else 10)

        chart_header.bind(width=adapt_chart_header)
        adapt_chart_header(chart_header, chart_header.width)
        chart_card.add_widget(chart_header)

        chart_card.add_widget(RevenueTrendChart(app.revenue_trend_series(days=7)))
        main_layout.add_widget(chart_card)

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
            size_hint_y=None, height=dp(22)
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
            for accent_name, accent_button in accent_buttons.items():
                label = ACCENT_LABELS[accent_name]
                accent_button.text = (
                    f"✓ {label}" if selected["accent"] == accent_name else label
                )
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
        perms = app.role_permissions()
        role = app.user_role()

        # Header Halaman
        subtitle = (
            "Pilih menu favorit Anda dan lanjutkan ke Keranjang"
            if role == "pelanggan"
            else "Pilih menu kopi atau makanan untuk pesanan kasir"
        )
        self.heading("Katalog Menu", subtitle)

        if perms["can_manage_products"]:
            add_product_button = button(
                "+ TAMBAH PRODUK BARU", self.open_add_product, True, 46
            )
            self.content.add_widget(add_product_button)

        if role == "admin" and perms["can_manage_stock"]:
            stock_action = Card(
                orientation="horizontal", size_hint_y=None, height=dp(58),
                padding=[dp(14), dp(8), dp(14), dp(8)], spacing=dp(8),
                color=CREAM, radius=12
            )
            stock_action.add_widget(Text(
                "Stok kosong atau menipis? Kelola stok & audit riwayat mutasi.",
                size=11, color=COFFEE
            ))
            history_button = button(
                "RIWAYAT MUTASI", self.open_stock_mutations, False, 44
            )
            history_button.size_hint_x = None
            history_button.width = dp(155)
            stock_action.add_widget(history_button)
            stock_button = button("MANAJEMEN STOK", self.open_stock_management, True, 44)
            stock_button.size_hint_x = None
            stock_button.width = dp(165)
            stock_action.add_widget(stock_button)
            self.content.add_widget(stock_action)

        if role == "pelanggan":
            promo_banner = Card(
                orientation="vertical",
                padding=[dp(14), dp(10), dp(14), dp(10)],
                spacing=dp(6),
                size_hint_y=None,
                height=dp(82),
                color=CREAM,
                radius=12,
                border_color=BORDER,
            )
            active_v = getattr(app, "voucher_code", "")
            promo_title = (
                f"Voucher Aktif: {active_v} ({VOUCHER_CODES[active_v]['label']})"
                if active_v in VOUCHER_CODES
                else "Promo Spesial Hari Ini — Klik untuk Klaim Voucher Otomatis:"
            )
            promo_banner.add_widget(Text(
                promo_title,
                size=11,
                bold=True,
                color=SUCCESS_TEXT if active_v in VOUCHER_CODES else COFFEE,
                size_hint_y=None,
                height=dp(18),
            ))
            promo_pills = GridLayout(
                cols=3, spacing=dp(8), size_hint_y=None, height=dp(38)
            )
            for v_code, v_info in VOUCHER_CODES.items():
                is_claimed = active_v == v_code
                pill_text = f"✓ {v_code}" if is_claimed else f"KLAIM {v_code}"
                promo_pills.add_widget(button(
                    pill_text,
                    lambda c=v_code: self.claim_customer_voucher(c),
                    is_claimed,
                    38,
                    fill_color=ACCENT if is_claimed else WHITE,
                    text_color=ON_ACCENT if is_claimed else TEXT,
                ))
            promo_banner.add_widget(promo_pills)
            self.content.add_widget(promo_banner)

            self.customer_cart_holder = BoxLayout(
                orientation="vertical", size_hint_y=None, height=dp(0)
            )
            self.content.add_widget(self.customer_cart_holder)

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
        categories = ["Kopi", "Non Kopi", "Makanan"]
        categories.append("Best Seller")
        for cat in categories:
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
        _configure_responsive_grid(self.grid, dp(390), 2, dp(12))
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
        content = Card(
            orientation="vertical", padding=[dp(20), dp(14)], spacing=dp(8),
            color=SURFACE, radius=20, border_color=ACCENT,
        )

        header = BoxLayout(
            orientation="horizontal", size_hint_y=None,
            height=dp(50), spacing=dp(12),
        )
        stock_icon = Card(
            orientation="vertical", size_hint=(None, None),
            size=(dp(46), dp(42)), color=ACCENT, radius=13,
        )
        stock_icon.add_widget(Text(
            "ST", size=14, bold=True, color=ON_ACCENT, align="center",
        ))
        header.add_widget(stock_icon)

        heading = BoxLayout(orientation="vertical", spacing=dp(1))
        heading.add_widget(Text(
            "Kontrol Persediaan", size=17, bold=True, color=TEXT,
            size_hint_y=None, height=dp(24),
        ))
        heading.add_widget(Text(
            "Catat stok masuk dan pantau kapasitas produk.",
            size=10, color=MUTED,
        ))
        header.add_widget(heading)

        stock_tag = Card(
            orientation="vertical", size_hint=(None, None),
            size=(dp(58), dp(24)), color=SURFACE_ALT, radius=8,
        )
        stock_tag.add_widget(Text(
            "KASIR", size=8, bold=True, color=ACCENT_TEXT, align="center",
        ))
        header.add_widget(stock_tag)
        content.add_widget(header)
        content.add_widget(Card(
            color=ACCENT, radius=1, size_hint_y=None, height=dp(2),
        ))

        content.add_widget(Text(
            "PILIH PRODUK", size=10, bold=True, color=MUTED,
            size_hint_y=None, height=dp(14),
        ))

        product_spinner = Spinner(
            text=product_names[0], values=product_names,
            size_hint_y=None, height=dp(44),
            font_size=dp(13), bold=True, color=TEXT,
            background_normal="", background_down="",
            background_color=(0, 0, 0, 0),
        )
        product_selector = Card(
            orientation="horizontal", padding=[dp(12), 0],
            color=INPUT, radius=12, border_color=BORDER,
            size_hint_y=None, height=dp(48),
        )
        product_selector.add_widget(product_spinner)
        content.add_widget(product_selector)

        current_stock_label = Text(
            "", size=14, bold=True, color=TEXT,
            size_hint_y=None, height=dp(20),
        )
        remaining_stock_label = Text(
            "", size=9, bold=True, color=ACCENT_TEXT, align="right",
            size_hint=(None, 1), width=dp(150),
        )
        stock_summary = Card(
            orientation="horizontal", padding=[dp(14), dp(7)],
            spacing=dp(8), color=SURFACE_ALT, radius=12,
            border_color=BORDER, size_hint_y=None, height=dp(52),
        )
        stock_details = BoxLayout(orientation="vertical", spacing=dp(1))
        stock_details.add_widget(Text(
            "STOK SAAT INI", size=8, bold=True, color=MUTED,
            size_hint_y=None, height=dp(14),
        ))
        stock_details.add_widget(current_stock_label)
        stock_summary.add_widget(stock_details)
        stock_summary.add_widget(remaining_stock_label)
        content.add_widget(stock_summary)

        quantity_header = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(16),
        )
        quantity_header.add_widget(Text(
            "JUMLAH STOK MASUK", size=10, bold=True, color=MUTED,
        ))
        quantity_header.add_widget(Text(
            f"BATAS {MAX_PRODUCT_STOCK} ITEM", size=8, bold=True,
            color=MUTED, align="right",
        ))
        content.add_widget(quantity_header)
        stock_input = text_input(
            hint_text="Contoh: 20",
            height=46,
            font_size=15, foreground_color=TEXT,
            hint_text_color=MUTED, background_color=(0, 0, 0, 0),
            input_filter="int",
            halign="left",
        )
        stock_input_shell = Card(
            orientation="horizontal", padding=[dp(14), 0, dp(12), 0],
            spacing=dp(8), color=INPUT, radius=12, border_color=BORDER,
            size_hint_y=None, height=dp(50),
        )
        stock_input_shell.add_widget(stock_input)
        stock_input_shell.add_widget(Text(
            "ITEM", size=9, bold=True, color=ACCENT_TEXT,
            size_hint=(None, 1), width=dp(38), align="center",
        ))
        content.add_widget(stock_input_shell)

        feedback_label = Text(
            "", size=10, color=DANGER_TEXT, align="left",
            size_hint_y=None, height=dp(18),
        )
        content.add_widget(feedback_label)

        popup = themed_popup(
            "", content, size_hint=(0.88, None), height=dp(430),
            background_color=(0, 0, 0, 0),
            separator_height=0, title_size=0,
            auto_dismiss=False,
        )

        def selected_product():
            return products_by_name.get(product_spinner.text)

        def update_current_stock(*_):
            product = selected_product()
            if product is None:
                current_stock_label.text = "Produk tidak ditemukan"
                current_stock_label.color = DANGER_TEXT
                remaining_stock_label.text = ""
                return
            current_stock = int(product["stok"])
            remaining = max(0, MAX_PRODUCT_STOCK - current_stock)
            current_stock_label.text = f"{current_stock} / {MAX_PRODUCT_STOCK} item"
            remaining_stock_label.text = f"SISA {remaining} ITEM"
            stock_input.hint_text = f"Maksimal tambah {remaining} item"
            stock_input.disabled = remaining <= 0
            feedback_label.text = (
                "Stok sudah mencapai batas maksimal."
                if remaining <= 0 else ""
            )
            feedback_label.color = WARNING_TEXT
            add_stock_button.disabled = remaining <= 0

        def submit_stock():
            product = selected_product()
            if product is None:
                feedback_label.text = "Pilih produk yang valid."
                feedback_label.color = DANGER_TEXT
                return
            try:
                updated = app.add_stock(product["id"], stock_input.text)
            except (ValueError, TypeError) as error:
                feedback_label.text = str(error)
                feedback_label.color = DANGER_TEXT
                return
            except Exception as error:
                feedback_label.text = f"Stok gagal diperbarui: {error}"
                feedback_label.color = DANGER_TEXT
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
        actions.add_widget(button(
            "BATAL", popup.dismiss, False, 44,
            outline=True, outline_color=BORDER_STRONG,
        ))
        add_stock_button = button("TAMBAH STOK", submit_stock, True, 44)
        actions.add_widget(add_stock_button)
        content.add_widget(actions)
        update_current_stock()
        popup.open()

    def open_stock_mutations(self):
        """Membuka modal daftar riwayat mutasi keluar-masuk stok produk."""
        app = self.manager.app
        try:
            mutations = app.db.get_stock_mutations(limit=30)
        except Exception as error:
            app.notice(f"Gagal memuat riwayat mutasi stok:\n{error}")
            return

        content = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
        content.add_widget(Text(
            "Rekam jejak penambahan stok, penjualan, dan pembatalan transaksi.",
            size=11, color=MUTED, align="center",
            size_hint_y=None, height=dp(20),
        ))

        list_card = Card(
            orientation="vertical", padding=dp(10), spacing=dp(6),
            color=WHITE, radius=12,
        )
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(5))
        rows_box = BoxLayout(
            orientation="vertical", spacing=dp(6), size_hint=(1, None)
        )
        rows_box.bind(minimum_height=rows_box.setter("height"))

        if not mutations:
            rows_box.add_widget(Text(
                "Belum ada catatan mutasi stok.",
                size=12, color=MUTED, align="center",
                size_hint_y=None, height=dp(60),
            ))
        else:
            for item in mutations:
                tipe = item["tipe"]
                sign = "+" if tipe in ("MASUK", "RETUR_HAPUS") else "-"
                badge_color = (
                    SUCCESS_TEXT if tipe in ("MASUK", "RETUR_HAPUS") else DANGER_TEXT
                )
                row_item = Card(
                    orientation="vertical",
                    padding=[dp(10), dp(6), dp(10), dp(6)],
                    spacing=dp(2),
                    size_hint_y=None,
                    height=dp(54),
                    color=CREAM,
                    radius=8,
                )
                top_line = BoxLayout(
                    orientation="horizontal", size_hint_y=None, height=dp(20)
                )
                top_line.add_widget(Text(
                    f"{item['nama']} ({tipe})",
                    size=11, bold=True, color=COFFEE,
                ))
                top_line.add_widget(Text(
                    f"{sign}{item['jumlah']}  ->  Stok: {item['stok_akhir']}",
                    size=11, bold=True, color=badge_color, align="right",
                ))
                row_item.add_widget(top_line)
                row_item.add_widget(Text(
                    f"{item['tanggal']}  •  {item['keterangan']}",
                    size=10, color=MUTED, size_hint_y=None, height=dp(18),
                ))
                rows_box.add_widget(row_item)

        scroll.add_widget(rows_box)
        list_card.add_widget(scroll)
        content.add_widget(list_card)

        popup = themed_popup(
            "Riwayat Mutasi Stok (30 Terbaru)", content,
            size_hint=(0.90, 0.82),
        )
        _style_popup_text_white(popup, content, exclude=(list_card,))
        content.add_widget(button("TUTUP", popup.dismiss, True, 42))
        popup.open()

    def search_changed(self, _instance, value):
        self.query = value
        self.render_products()

    def set_category(self, category):
        if self.category == category:
            self.category = "Semua"
        else:
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
        perms = app.role_permissions()
        role = app.user_role()
        self.refresh_customer_cart_bar()

        matched_products = []
        for product in app.products:
            if self.category == "Best Seller":
                if product["name"] not in BEST_SELLER_PRODUCTS:
                    continue
            elif self.category != "Semua" and product["category"] != self.category:
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
            can_customize = product.get("category") in ("Kopi", "Non Kopi")
            image_width = dp(92 if self.grid.width < dp(480) else 120)

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
                    size_hint=(None, 1), width=image_width,
                    fit_mode="contain"
                )
                card.add_widget(photo)
            else:
                art = Card(
                    size_hint=(None, 1), width=image_width,
                    color=ART_BY_CATEGORY.get(product["category"], ACCENT)
                )
                art.add_widget(Text(
                    product["category"].upper(),
                    size=13, bold=True, align="center", color=ON_ACCENT
                ))
                card.add_widget(art)

            # Bagian Kanan: Detail Informasi & Tombol Kasir
            details = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_x=1)

            # Header Kategori (+ Badge Favorit untuk menu unggulan)
            is_best = product["name"] in BEST_SELLER_PRODUCTS
            cat_header_text = (
                f"{product['category'].upper()}  •  ★ FAVORIT"
                if is_best
                else product["category"].upper()
            )
            details.add_widget(Text(
                cat_header_text, size=10, bold=True,
                color=ACCENT_TEXT if is_best else ART_BY_CATEGORY.get(product["category"], ACCENT_TEXT),
                size_hint_y=None, height=dp(16)
            ))

            # Nama Produk (ketinggian tetap agar baris aksi di bawah sejajar sempurna)
            details.add_widget(Text(
                product["name"], size=14, bold=True, color=COFFEE,
                size_hint_y=None, height=dp(30)
            ))

            # Badge Status Stok Dinamis (Pelanggan juga dapat melihat sisa porsi)
            if role == "pelanggan":
                if is_out_of_stock:
                    stock_text = "Stok Habis"
                    stock_color = DANGER_TEXT
                    stock_bold = True
                elif stok < 15:
                    stock_text = f"Hampir Habis • Sisa {stok} porsi!"
                    stock_color = WARNING_TEXT
                    stock_bold = True
                else:
                    stock_text = f"Tersedia • Sisa {stok} porsi"
                    stock_color = MUTED
                    stock_bold = False
            else:
                if is_out_of_stock:
                    stock_text = "STOK HABIS"
                    stock_color = DANGER_TEXT
                elif stok < 15:
                    stock_text = f"Sisa Sedikit: {stok} item"
                    stock_color = WARNING_TEXT
                else:
                    stock_text = f"Tersedia: {stok} item"
                    stock_color = MUTED
                stock_bold = stok < 15

            details.add_widget(Text(
                stock_text, size=11, bold=stock_bold, color=stock_color,
                size_hint_y=None, height=dp(16)
            ))

            # Harga Produk Tegas (+ indikator racikan bila sudah diatur)
            custom_note = app.get_item_note(pid) if can_customize else ""
            price_line = (
                f"{rp(product['price'])}  •  {custom_note}"
                if custom_note
                else rp(product["price"])
            )
            details.add_widget(Text(
                price_line, size=14 if custom_note else 15, bold=True, color=COFFEE,
                size_hint_y=None, height=dp(22)
            ))

            # Spacer fleksibel untuk menjamin baris tombol aksi selalu sejajar di dasar kartu
            details.add_widget(BoxLayout())

            # Baris Aksi: berbeda antara Admin (tambah stok) vs Kasir/Pelanggan (keranjang)
            action_row = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(44))
            if role == "admin":
                btn_quick_stock = button(
                    "+ STOK (10)",
                    lambda p_id=pid: self.quick_add_stock(p_id, 10),
                    True, 44
                )
                action_row.add_widget(btn_quick_stock)
            elif is_out_of_stock:
                action_row.add_widget(Text(
                    "Stok habis." if role == "pelanggan" else "Stok habis. Gunakan Manajemen Stok.",
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
                btn_minus.width = dp(42)
                action_row.add_widget(btn_minus)

                # Indikator angka kuantitas
                action_row.add_widget(Text(
                    f"{qty_in_cart}", size=13, bold=True, color=COFFEE,
                    size_hint=(None, 1), width=dp(28), align="center"
                ))

                # Tombol Plus (+) berwarna hijau solid
                btn_plus = button(
                    "+",
                    lambda p=product: self.add_and_refresh(p),
                    True, 44
                )
                btn_plus.size_hint_x = None
                btn_plus.width = dp(42)
                action_row.add_widget(btn_plus)

                if can_customize:
                    btn_custom = button(
                        "RACIK",
                        lambda p=product: self.open_customize_item(p),
                        False, 44, outline=True, outline_color=ACCENT
                    )
                    action_row.add_widget(btn_custom)
            else:
                add_label_text = "PESAN +" if role == "pelanggan" else "TAMBAH +"
                btn_add = button(
                    add_label_text,
                    lambda p=product: self.add_and_refresh(p),
                    True, 44
                )
                action_row.add_widget(btn_add)

            details.add_widget(action_row)

            # Tombol hapus dipisahkan dari aksi keranjang agar tidak mudah tersentuh.
            if perms["can_manage_products"]:
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

    def quick_add_stock(self, product_id, quantity=10):
        """Menambah stok cepat langsung dari kartu produk pada mode Admin."""
        app = self.manager.app
        try:
            app.add_stock(product_id, quantity)
            self.render_products()
        except Exception as error:
            app.notice(str(error))

    def minus_and_refresh(self, product):
        """Mengurangi kuantitas produk dari keranjang dan memperbarui indikator kartu secara instan."""
        self.manager.app.change_qty(product["id"], -1)
        self.render_products()

    def claim_customer_voucher(self, code):
        """Klaim kode voucher langsung dari banner promo di halaman Katalog Pelanggan."""
        app = self.manager.app
        rule = VOUCHER_CODES.get(code)
        if not rule:
            return
        app.voucher_code = code
        self.render()
        app.notice(
            f"Voucher {code} berhasil dipilih!\n"
            f"({rule['label']})\n"
            "Diskon akan otomatis dihitung di Keranjang saat syarat terpenuhi."
        )

    def refresh_customer_cart_bar(self):
        """Menampilkan bar pintas menuju Keranjang saat pelanggan sudah memilih menu."""
        holder = getattr(self, "customer_cart_holder", None)
        if holder is None:
            return
        holder.clear_widgets()
        app = self.manager.app
        if app.user_role() != "pelanggan" or not app.cart:
            holder.height = dp(0)
            return

        holder.height = dp(58)
        total_qty = sum(app.cart.values())
        bar = Card(
            orientation="horizontal",
            padding=[dp(16), dp(8), dp(16), dp(8)],
            spacing=dp(12),
            size_hint=(1, None),
            height=dp(54),
            color=SURFACE,
            radius=12,
            border_color=ACCENT,
        )
        bar.add_widget(Text(
            f"{total_qty} Menu Dipilih  •  Total Sementara: {rp(app.cart_total())}",
            size=13, bold=True, color=ACCENT_TEXT,
        ))
        go_cart_btn = button(
            "LANJUT KE KERANJANG ->",
            lambda: app.go("cart"),
            True, 40,
            fill_color=ACCENT,
            text_color=ON_ACCENT,
        )
        go_cart_btn.size_hint_x = None
        go_cart_btn.width = dp(210)
        bar.add_widget(go_cart_btn)
        holder.add_widget(bar)

    def open_customize_item(self, product):
        """Membuka modal pilihan Level Gula, Level Es, dan Catatan Barista."""
        app = self.manager.app
        if product.get("category") not in ("Kopi", "Non Kopi"):
            app.notice("Racikan hanya tersedia untuk kategori minuman.")
            return
        pid = product["id"]
        is_drink = product.get("category") in ("Kopi", "Non Kopi")
        selected = {
            "sugar": SUGAR_LEVELS[0],
            "ice": ICE_LEVELS[0],
        }

        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(8))
        content.add_widget(Text(
            f"Atur racikan untuk {product['name']}:",
            size=12, color=MUTED, align="center",
            size_hint_y=None, height=dp(20),
        ))

        sugar_btns = {}
        ice_btns = {}

        if is_drink:
            content.add_widget(Text(
                "Takaran Gula (Sugar Level)", size=11, bold=True, color=WHITE,
                size_hint_y=None, height=dp(18),
            ))
            sugar_row = GridLayout(cols=3, spacing=dp(6), size_hint_y=None, height=dp(38))
            for s_opt in SUGAR_LEVELS:
                sugar_btns[s_opt] = button(
                    s_opt, lambda val=s_opt: select_sugar(val), False, 38
                )
                sugar_btns[s_opt].font_size = dp(10)
                sugar_row.add_widget(sugar_btns[s_opt])
            content.add_widget(sugar_row)

            content.add_widget(Text(
                "Takaran Es / Suhu (Ice / Temp)", size=11, bold=True, color=WHITE,
                size_hint_y=None, height=dp(18),
            ))
            ice_row = GridLayout(cols=3, spacing=dp(6), size_hint_y=None, height=dp(38))
            for i_opt in ICE_LEVELS:
                ice_btns[i_opt] = button(
                    i_opt, lambda val=i_opt: select_ice(val), False, 38
                )
                ice_btns[i_opt].font_size = dp(10)
                ice_row.add_widget(ice_btns[i_opt])
            content.add_widget(ice_row)

        content.add_widget(Text(
            "Catatan Tambahan (Opsional)", size=11, bold=True, color=WHITE,
            size_hint_y=None, height=dp(18),
        ))
        note_input = text_input(
            text="",
            hint_text="Contoh: Es dipisah / Ekstra garing / Tanpa sedotan",
            height=40,
            font_size=12,
        )
        content.add_widget(note_input)

        popup = themed_popup(
            f"Racikan Pesanan - {product['name']}",
            content,
            size_hint=(0.88, None),
            height=dp(380 if is_drink else 250),
            auto_dismiss=True,
        )
        _style_popup_text_white(popup, content)

        def refresh_custom_buttons():
            for name, btn in sugar_btns.items():
                active = selected["sugar"] == name
                btn._bg_color.rgba = ACCENT if active else SURFACE
                btn._bg_default = list(ACCENT if active else SURFACE)
                btn._text_default = list(ON_ACCENT if active else TEXT)
                btn.color = ON_ACCENT if active else TEXT
            for name, btn in ice_btns.items():
                active = selected["ice"] == name
                btn._bg_color.rgba = ACCENT if active else SURFACE
                btn._bg_default = list(ACCENT if active else SURFACE)
                btn._text_default = list(ON_ACCENT if active else TEXT)
                btn.color = ON_ACCENT if active else TEXT

        def select_sugar(val):
            selected["sugar"] = val
            refresh_custom_buttons()

        def select_ice(val):
            selected["ice"] = val
            refresh_custom_buttons()

        def save_custom():
            parts = []
            if is_drink:
                parts.append(selected["sugar"])
                parts.append(selected["ice"])
            extra = note_input.text.strip()
            if extra:
                parts.append(extra)
            app.set_item_note(pid, ", ".join(parts))
            popup.dismiss()

        refresh_custom_buttons()
        actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        actions.add_widget(button("BATAL", popup.dismiss, False, 40))
        actions.add_widget(button("SIMPAN RACIKAN", save_custom, True, 40))
        content.add_widget(actions)
        popup.open()


class CartPage(Page):
    """Halaman Keranjang Belanja dan Alur Pembayaran Kasir."""

    def on_pre_enter(self, *_):
        self.render()

    def render(self):
        self.content.clear_widgets()
        app = self.manager.app
        perms = app.role_permissions()
        role = app.user_role()
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
        grid_top = GridLayout(
            cols=2, spacing=dp(12), size_hint=(1, None), height=dp(140)
        )

        def adapt_summary_grid(grid, width):
            grid.cols = _responsive_columns(width, dp(300), 2, dp(12))
            grid.height = dp(140 if grid.cols == 2 else 292)

        grid_top.bind(width=adapt_summary_grid)
        adapt_summary_grid(grid_top, grid_top.width)

        # Panel Kiri: Tanggal & Nama Pelanggan / No. Meja
        left_box = Card(
            orientation="vertical", padding=dp(14), spacing=dp(6),
            size_hint=(1, 1), color=WHITE, radius=14
        )
        left_box.add_widget(Text("DATA TRANSAKSI", size=10, bold=True, color=MUTED, size_hint_y=None, height=dp(16)))
        today_str = datetime.now().strftime("%d %b %Y, %H:%M WIB")
        left_box.add_widget(Text(f"Waktu: {today_str}", size=12, bold=True, color=COFFEE, size_hint_y=None, height=dp(20)))
        customer_label_text = (
            "Nama Anda / Nomor Meja (Wajib Diisi):"
            if perms["require_customer_label"]
            else "Nama Pelanggan / No. Meja:"
        )
        left_box.add_widget(Text(customer_label_text, size=11, bold=True, color=BROWN, size_hint_y=None, height=dp(18)))
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
        subtotal_val = app.cart_subtotal()
        discount_val = app.cart_discount()
        active_order_type = getattr(app, "order_type", "Dine-In")
        right_box.add_widget(Text(
            f"RINGKASAN TAGIHAN ({active_order_type.upper()})",
            size=10, bold=True, color=MUTED, size_hint_y=None, height=dp(16)
        ))
        if discount_val > 0:
            summary_note = (
                f"Harga Awal: {rp(subtotal_val)}  |  Diskon: -{rp(discount_val)}"
            )
            summary_color = SUCCESS_TEXT
            summary_bold = True
            bottom_note = (
                f"Voucher {app.voucher_code} aktif • Hemat {rp(discount_val)}"
            )
            bottom_color = SUCCESS_TEXT
        else:
            summary_note = f"{total_items} item di dalam pesanan"
            summary_color = COFFEE
            summary_bold = False
            bottom_note = "Siap diproses ke pembayaran kasir"
            bottom_color = MUTED
        right_box.add_widget(Text(
            summary_note, size=11, bold=summary_bold, color=summary_color,
            size_hint_y=None, height=dp(18)
        ))
        hero_total = Text(
            rp(app.cart_total()),
            size=26, bold=True, color=ACCENT_TEXT,
            size_hint_y=None, height=dp(42)
        )
        right_box.add_widget(hero_total)
        right_box.add_widget(Text(
            bottom_note, size=11, bold=summary_bold, color=bottom_color,
            size_hint_y=None, height=dp(18)
        ))
        grid_top.add_widget(right_box)

        self.content.add_widget(grid_top)

        # Panel Opsi Layanan (Dine-In / Take Away) & Kode Voucher Diskon
        promo_card = Card(
            orientation="vertical", padding=dp(12), spacing=dp(8),
            size_hint=(1, None), height=dp(116), color=WHITE, radius=14
        )
        type_row = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(40))
        for opt_type, opt_label in (
            ("Dine-In", "MAKAN DI TEMPAT (DINE-IN)"),
            ("Take Away", "BAWA PULANG (TAKE AWAY)"),
        ):
            is_selected = active_order_type == opt_type
            type_row.add_widget(button(
                opt_label,
                lambda t=opt_type: app.set_order_type(t),
                is_selected, 40,
                fill_color=ACCENT if is_selected else CREAM,
                text_color=ON_ACCENT if is_selected else TEXT,
            ))
        promo_card.add_widget(type_row)

        voucher_row = BoxLayout(
            orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(42)
        )
        voucher_hints = ", ".join(VOUCHER_CODES.keys())
        voucher_input = text_input(
            text=getattr(app, "voucher_code", ""),
            hint_text=f"Kode Promo/Voucher ({voucher_hints})",
            height=42, font_size=12,
        )
        voucher_input.size_hint_x = 1
        voucher_input.bind(
            on_text_validate=lambda instance: app.apply_voucher(instance.text)
        )
        voucher_row.add_widget(voucher_input)

        apply_voucher_btn = button(
            "PAKAI VOUCHER",
            lambda: app.apply_voucher(voucher_input.text),
            True, 42
        )
        apply_voucher_btn.size_hint_x = None
        apply_voucher_btn.width = dp(140)
        voucher_row.add_widget(apply_voucher_btn)

        reset_voucher_btn = None
        if getattr(app, "voucher_code", ""):
            reset_voucher_btn = button(
                "HAPUS",
                app.clear_voucher,
                False, 42, outline=True, outline_color=CORAL
            )
            reset_voucher_btn.size_hint_x = None
            reset_voucher_btn.width = dp(86)
            voucher_row.add_widget(reset_voucher_btn)

        def adapt_promo_card(_widget, width):
            narrow = width < dp(540)
            type_row.cols = 1 if narrow else 2
            type_row.height = dp(88 if narrow else 40)
            promo_card.height = dp(164 if narrow else 116)
            apply_voucher_btn.width = dp(110 if width < dp(500) else 140)
            if reset_voucher_btn is not None:
                reset_voucher_btn.width = dp(68 if width < dp(500) else 86)

        promo_card.bind(width=adapt_promo_card)
        adapt_promo_card(promo_card, promo_card.width)
        promo_card.add_widget(voucher_row)
        self.content.add_widget(promo_card)

        # Judul Daftar Pesanan
        self.content.add_widget(Text("Daftar Item Pesanan", size=15, bold=True, color=COFFEE, size_hint_y=None, height=dp(24)))

        # 2. List Item Keranjang dengan Counter Ringkas & Info Racikan
        for pid, qty in list(app.cart.items()):
            product = app.products_by_id[pid]
            can_customize = product.get("category") in ("Kopi", "Non Kopi")
            item_note = app.get_item_note(pid)
            row = Card(
                orientation="horizontal", padding=dp(12),
                spacing=dp(8), size_hint_y=None, height=dp(88), color=WHITE, radius=12
            )
            info = BoxLayout(orientation="vertical", spacing=dp(2))
            info.add_widget(Text(product["name"], size=13, bold=True, color=COFFEE))
            sub_line = f"{qty} x {rp(product['price'])} = {rp(product['price'] * qty)}"
            if item_note:
                sub_line += f"   •   Racikan: {item_note}"
            info.add_widget(Text(
                sub_line,
                size=11, color=ACCENT_TEXT if item_note else MUTED,
                bold=bool(item_note),
            ))
            row.add_widget(info)

            controls_row = BoxLayout(
                orientation="horizontal", spacing=dp(4),
                size_hint=(None, 1),
                width=dp(284 if can_customize else 206),
            )
            if can_customize:
                custom_btn = button(
                    "RACIK",
                    lambda p=product: app.sm.get_screen("products").open_customize_item(p),
                    False, 44, outline=True, outline_color=ACCENT
                )
                custom_btn.size_hint_x = None
                custom_btn.width = dp(74)
                controls_row.add_widget(custom_btn)

            # Tombol counter - [qty] +
            btn_sub = button(
                "-",
                lambda p=pid: app.change_qty(p, -1),
                False, 44, outline=True, outline_color=CORAL
            )
            btn_sub.size_hint_x = None
            btn_sub.width = dp(44)
            controls_row.add_widget(btn_sub)

            qty_input = text_input(
                text=str(qty), height=44, font_size=13,
                input_filter="int", halign="center",
            )
            qty_input.size_hint_x = None
            qty_input.width = dp(60)

            def apply_qty(*_, product_id=pid, field=qty_input):
                app.set_qty(product_id, field.text)

            qty_input.bind(on_text_validate=apply_qty)
            controls_row.add_widget(qty_input)

            apply_button = button("OK", apply_qty, False, 44)
            apply_button.size_hint_x = None
            apply_button.width = dp(46)
            controls_row.add_widget(apply_button)

            btn_add = button(
                "+",
                lambda p=pid: app.change_qty(p, 1),
                True, 44
            )
            btn_add.size_hint_x = None
            btn_add.width = dp(44)
            controls_row.add_widget(btn_add)

            def adapt_cart_item(_widget, width, item_row=row, item_info=info, controls=controls_row):
                narrow = width < dp(620)
                item_row.orientation = "vertical" if narrow else "horizontal"
                item_row.height = dp(132 if narrow else 88)
                item_info.size_hint_y = None if narrow else 1
                item_info.height = dp(48 if narrow else 0)
                controls.size_hint_x = 1 if narrow else None
                controls.size_hint_y = None if narrow else 1
                controls.height = dp(44)

            row.bind(width=adapt_cart_item)
            adapt_cart_item(row, row.width)
            row.add_widget(controls_row)

            self.content.add_widget(row)

        if discount_val > 0:
            discount_bar = Card(
                orientation="horizontal",
                padding=[dp(14), dp(10), dp(14), dp(10)],
                spacing=dp(8),
                size_hint_y=None,
                height=dp(46),
                color=CREAM,
                radius=12,
                border_color=SUCCESS_TEXT,
            )
            discount_bar.add_widget(Text(
                f"Subtotal: {rp(subtotal_val)}   —   "
                f"Potongan Voucher ({app.voucher_code}): -{rp(discount_val)}",
                size=12, bold=True, color=SUCCESS_TEXT,
            ))
            discount_bar.add_widget(Text(
                f"Total Bayar: {rp(app.cart_total())}",
                size=13, bold=True, color=ACCENT_TEXT, align="right",
            ))
            def adapt_discount_bar(widget, width):
                narrow = width < dp(520)
                widget.orientation = "vertical" if narrow else "horizontal"
                widget.height = dp(74 if narrow else 46)

            discount_bar.bind(width=adapt_discount_bar)
            adapt_discount_bar(discount_bar, discount_bar.width)
            self.content.add_widget(discount_bar)

        # 3. Tombol Aksi Kasir / Pelanggan
        total_label = rp(app.cart_total())
        checkout_label = (
            f"BUAT PESANAN & BAYAR ({total_label})"
            if perms["require_customer_label"]
            else f"LANJUT PEMBAYARAN ({total_label})"
        )
        self.content.add_widget(button(checkout_label, app.checkout, True, 48))
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
        perms = app.role_permissions()

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
        def adapt_report_filter(_widget, width):
            narrow = width < dp(620)
            filter_row.cols = 2 if narrow else 4
            filter_row.height = dp(96 if narrow else 44)
            filter_card.height = dp(148 if narrow else 96)

        filter_card.bind(width=adapt_report_filter)
        adapt_report_filter(filter_card, filter_card.width)
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

        top_products = list(getattr(app, "report_top_products", []))
        if top_products:
            top_card = Card(
                orientation="vertical",
                padding=[dp(14), dp(10), dp(14), dp(10)],
                spacing=dp(4),
                size_hint_y=None,
                height=dp(34 + len(top_products) * 24),
                color=WHITE,
                radius=12,
            )
            top_card.add_widget(Text(
                f"Top {len(top_products)} Menu Terlaris ({active_label.title()})",
                size=12, bold=True, color=COFFEE,
                size_hint_y=None, height=dp(20),
            ))
            for idx, item in enumerate(top_products, start=1):
                top_card.add_widget(Text(
                    f"{idx}. {item['name']} ({item['category']})  —  "
                    f"Terjual {item['qty']} item  •  Omzet {rp(item['revenue'])}",
                    size=11, color=ACCENT_TEXT if idx == 1 else MUTED,
                    bold=(idx == 1),
                    size_hint_y=None, height=dp(20),
                ))
            self.content.add_widget(top_card)

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
            order_id = Text(
                f"{order['id']}", size=13, bold=True, color=COFFEE,
                size_hint_x=None, width=dp(80)
            )
            order_date = Text(
                f"{order['date']}  {order['time']}", size=11, color=MUTED,
                size_hint_x=None, width=dp(138)
            )
            top_row.add_widget(order_id)
            top_row.add_widget(order_date)
            top_row.add_widget(BoxLayout()) # spacer

            pm = order.get("payment", "-")
            chip_color = ACCENT if "E-Wallet" in pm else (GREEN if "Tunai" in pm else PURPLE)
            payment_chip = status_chip(pm, chip_color, width=130, height=28)
            top_row.add_widget(payment_chip)

            def adapt_order_header(_widget, width):
                if width < dp(520):
                    available = width - dp(32)
                    order_id.width = dp(56)
                    order_date.width = max(dp(82), available * 0.36)
                    payment_chip.width = max(dp(90), available * 0.32)
                else:
                    order_id.width = dp(80)
                    order_date.width = dp(138)
                    payment_chip.width = dp(130)

            top_row.bind(width=adapt_order_header)
            adapt_order_header(top_row, top_row.width)
            row.add_widget(top_row)

            # Baris Bawah: Total Belanja, Tipe Layanan, Voucher, & Info Kembalian
            order_type_tag = f" [{order.get('tipe_pesanan', 'Dine-In')}]"
            voucher_tag = (
                f" • Voucher {order['kode_voucher']} (-{rp(order['diskon'])})"
                if order.get("diskon", 0) > 0
                else ""
            )
            kembalian_info = f"   [Kembalian: {rp(order['kembalian'])}]" if order.get("kembalian", 0) > 0 else ""
            bot_text = f"Total: {rp(order['total'])}{order_type_tag}{voucher_tag}{kembalian_info}"
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
            if perms["can_delete_orders"]:
                actions.add_widget(button(
                    "HAPUS",
                    lambda o=order: app.confirm_delete_order(o), False, 44,
                    outline=True, outline_color=CORAL
                ))
            self.content.add_widget(actions)