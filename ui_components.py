"""Komponen antarmuka (UI Components) POS Kopi Nako.

Modul ini menyediakan komponen-komponen dasar Kivy yang telah dikustomisasi
agar tampilan aplikasi rapi, konsisten, dan mudah digunakan kembali oleh seluruh halaman.
"""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.image import Image

from config import LOGO_PATH
from theme import (
    ACCENT, BUTTON_STYLES, COFFEE, CORAL, INPUT, MUTED, ON_ACCENT,
    SURFACE, TEXT, WHITE,
)


# Payment modal colors stay dark so the checkout step has a clear visual focus
# without changing the user's global application theme.
PAYMENT_BG = (0.07, 0.08, 0.10, 1)
PAYMENT_SURFACE = (0.11, 0.13, 0.16, 1)
PAYMENT_FIELD = (0.14, 0.16, 0.20, 1)
PAYMENT_TEXT = (0.96, 0.97, 0.99, 1)
PAYMENT_MUTED = (0.72, 0.76, 0.82, 1)
PAYMENT_BLUE = (0.18, 0.42, 0.70, 1)
PAYMENT_ERROR = (0.98, 0.46, 0.48, 1)


def rp(number):
    """Memformat angka menjadi format mata uang Rupiah.
    
    Contoh:
    18000 -> 'Rp 18.000'
    1250500 -> 'Rp 1.250.500'
    """
    return "Rp " + f"{int(number):,}".replace(",", ".")


def background(widget, color, radius=16, border_color=None, border_width=1):
    """Menambahkan latar belakang berwarna dengan sudut melengkung (rounded corner).
    
    Cara Kerja di Kivy:
    Kivy tidak memiliki properti border-radius di CSS bawaan.
    Oleh karena itu, kita menggambar RoundedRectangle secara dinamis pada kanvas
    sebelum widget dirender (widget.canvas.before), lalu mengikatnya (bind) agar
    posisi dan ukurannya selalu mengikuti perubahan ukuran jendela.
    """
    with widget.canvas.before:
        Color(*color)
        shape = RoundedRectangle(
            pos=widget.pos, size=widget.size, radius=[dp(radius)]
        )
        outline = None
        if border_color is not None:
            Color(*border_color)
            outline = Line(
                rounded_rectangle=(widget.x, widget.y, widget.width, widget.height, dp(radius)),
                width=border_width,
            )

    def update(*_):
        shape.pos = widget.pos
        shape.size = widget.size
        if outline is not None:
            outline.rounded_rectangle = (
                widget.x, widget.y, widget.width, widget.height, dp(radius)
            )

    # Bind perubahan koordinat posisi dan dimensi ukuran widget
    widget.bind(pos=update, size=update)


class Text(Label):
    """Komponen teks label kustom turunan dari Label Kivy.
    
    Keunggulan:
    Secara otomatis mengatur text_size agar pembungkusan teks (text wrap)
    berjalan sesuai lebar widget, sehingga teks panjang tidak terpotong ke samping.
    """

    def __init__(self, text="", size=14, color=None,
                 bold=False, align="left", **kwargs):
        color = TEXT if color is None else color
        super().__init__(
            text=str(text), font_size=dp(size), color=color,
            bold=bold, halign=align, valign="middle", **kwargs
        )
        self.bind(size=self.update_text)
        self.update_text()

    def update_text(self, *_):
        """Memperbarui batas area teks ketika ukuran widget berubah."""
        self.text_size = (max(0, self.width), None)


class Card(BoxLayout):
    """Container kartu berbentuk kotak tumpul (card layout).
    
    Digunakan untuk mengelompokkan elemen seperti item produk, kartu statistik,
    dan form login agar tampak terstruktur dan modern.
    """

    def __init__(self, color=None, radius=16, border_color=None, border_width=1, **kwargs):
        color = SURFACE if color is None else color
        super().__init__(**kwargs)
        background(
            self, color, radius=radius,
            border_color=border_color, border_width=border_width,
        )


def metric_badge(
    label, fill_color, text_color=ON_ACCENT,
    width=48, height=26, font_size=8,
):
    """Badge ringkas untuk menandai kategori metric tanpa ikon dekoratif."""
    badge = Card(
        orientation="vertical", size_hint=(None, None),
        size=(dp(width), dp(height)),
        padding=[dp(4), 0, dp(4), 0], color=fill_color, radius=7,
    )
    badge.add_widget(Text(
        label, size=font_size, bold=True, color=text_color, align="center"
    ))
    return badge


def metric_card(
    title, value, note, accent_color, badge_label,
    growth_text="", growth_color=None, color=None, border_color=None,
    height=176, compact=False,
):
    """Membuat card metric dashboard dengan badge dan indikator pertumbuhan."""
    if compact:
        padding = [dp(10), dp(6), dp(10), dp(6)]
        spacing = dp(1)
        header_height = dp(20)
        badge_kwargs = {"width": 44, "height": 20, "font_size": 7}
        value_size, value_height = 17, 22
        growth_size, growth_height = 9, 14
        note_size, note_height = 9, 14
    else:
        padding = [dp(16), dp(12), dp(16), dp(12)]
        spacing = dp(3)
        header_height = dp(26)
        badge_kwargs = {}
        value_size, value_height = 21, 32
        growth_size, growth_height = 11, 18
        note_size, note_height = 11, 18

    card = Card(
        orientation="vertical",
        padding=padding, spacing=spacing,
        size_hint_y=None, height=dp(height),
        color=SURFACE if color is None else color,
        radius=14, border_color=border_color,
    )
    header_row = BoxLayout(
        orientation="horizontal", size_hint_y=None,
        height=header_height, spacing=dp(6),
    )
    header_row.add_widget(Text(
        title, size=8 if compact else 10, bold=True, color=MUTED,
    ))
    header_row.add_widget(metric_badge(badge_label, accent_color, **badge_kwargs))
    card.add_widget(header_row)
    card.add_widget(Text(
        value, size=value_size, bold=True, color=COFFEE,
        size_hint_y=None, height=dp(value_height),
    ))
    if growth_text:
        card.add_widget(Text(
            growth_text, size=growth_size, bold=True,
            color=growth_color or MUTED,
            size_hint_y=None, height=dp(growth_height),
        ))
    else:
        card.add_widget(BoxLayout(size_hint_y=None, height=dp(growth_height)))
    card.add_widget(Text(
        note, size=note_size, color=MUTED,
        size_hint_y=None, height=dp(note_height),
    ))
    return card


def payment_surface(**kwargs):
    """Membuat permukaan modal pembayaran dengan hierarki dark yang konsisten."""
    kwargs.setdefault("orientation", "vertical")
    kwargs.setdefault("padding", [dp(20), dp(18), dp(20), dp(18)])
    kwargs.setdefault("spacing", dp(12))
    kwargs.setdefault("color", PAYMENT_BG)
    kwargs.setdefault("radius", 18)
    return Card(**kwargs)


def text_input(
    hint_text="", text="", height=44, font_size=13,
    input_filter=None, password=False, **kwargs
):
    """Membuat input standar untuk form kasir dan manajemen stok."""
    field = TextInput(
        hint_text=hint_text,
        text=text,
        password=password,
        multiline=False,
        size_hint_y=None,
        height=dp(height),
        font_size=dp(font_size),
        padding=[dp(12), dp(10)],
        background_normal="",
        background_active="",
        background_color=kwargs.pop("background_color", INPUT),
        foreground_color=kwargs.pop("foreground_color", TEXT),
        hint_text_color=kwargs.pop("hint_text_color", MUTED),
        cursor_color=kwargs.pop("cursor_color", ACCENT),
        input_filter=input_filter,
        **kwargs
    )
    return field


def payment_field(
    label, hint_text="", right_widget=None, height=46, font_size=14,
    input_filter=None, password=False, max_length=None, **kwargs
):
    """Membuat label dan field input yang khusus untuk surface pembayaran gelap."""
    wrapper = BoxLayout(
        orientation="vertical", spacing=dp(5), size_hint_y=None,
        height=dp(height + 22),
    )
    wrapper.add_widget(Text(
        label, size=11, bold=True, color=PAYMENT_MUTED,
        size_hint_y=None, height=dp(17),
    ))

    field_shell = Card(
        orientation="horizontal", spacing=dp(4), padding=[dp(8), 0, dp(8), 0],
        size_hint=(1, None), height=dp(height), color=PAYMENT_FIELD, radius=10,
    )
    field = text_input(
        hint_text=hint_text,
        height=height,
        font_size=font_size,
        input_filter=input_filter,
        password=password,
        background_color=(0, 0, 0, 0),
        foreground_color=PAYMENT_TEXT,
        hint_text_color=PAYMENT_MUTED,
        cursor_color=PAYMENT_BLUE,
        **kwargs,
    )
    if max_length is not None:
        def limit_length(_instance, value):
            if len(value) > max_length:
                field.text = value[:max_length]

        field.bind(text=limit_length)
    field_shell.add_widget(field)
    if right_widget is not None:
        field_shell.add_widget(right_widget)
    wrapper.add_widget(field_shell)
    return wrapper, field


def payment_brand_badges():
    """Menampilkan badge teks provider kartu saat aset logo resmi belum tersedia."""
    badges = BoxLayout(
        orientation="horizontal", spacing=dp(4), size_hint=(None, 1), width=dp(158),
    )
    for name in ("VISA", "MC", "BCA", "MANDIRI"):
        badge = Card(
            orientation="vertical", size_hint=(None, 1),
            width=dp(31 if len(name) <= 3 else 52),
            padding=[dp(2), 0, dp(2), 0], color=PAYMENT_SURFACE, radius=6,
        )
        badge.add_widget(Text(
            name, size=8, bold=True, color=PAYMENT_MUTED, align="center",
        ))
        badges.add_widget(badge)
    return badges


def payment_tab(label, callback, active=False, height=42):
    """Membuat tab pembayaran yang dapat berpindah state tanpa kehilangan callback."""
    tab = Button(
        text=label,
        size_hint_y=None,
        height=dp(height),
        font_size=dp(12),
        bold=True,
        color=PAYMENT_TEXT,
        background_normal="",
        background_down="",
        background_color=(0, 0, 0, 0),
        padding=[dp(10), dp(6)],
    )
    with tab.canvas.before:
        tab._payment_bg = Color(*PAYMENT_BLUE)
        tab._payment_shape = RoundedRectangle(
            pos=tab.pos, size=tab.size, radius=[dp(10)]
        )

    def update_shape(*_):
        tab._payment_shape.pos = tab.pos
        tab._payment_shape.size = tab.size

    def set_active(is_active):
        tab._payment_active = is_active
        fill = PAYMENT_BLUE if is_active else PAYMENT_FIELD
        tab._payment_bg.rgba = fill
        tab.color = PAYMENT_TEXT if is_active else PAYMENT_MUTED

    def pressed_state(_instance, state):
        if state == "down":
            fill = PAYMENT_BLUE if tab._payment_active else PAYMENT_FIELD
            tab._payment_bg.rgba = tuple(max(0, value * 0.86) for value in fill[:3]) + (1,)
        else:
            set_active(tab._payment_active)

    tab.set_active = set_active
    tab.bind(pos=update_shape, size=update_shape, state=pressed_state)
    tab.bind(on_release=lambda *_: callback() if callback else None)
    set_active(active)
    return tab


def payment_popup(content, **kwargs):
    """Membuat popup pembayaran tanpa surface bawaan agar Card rounded menjadi modalnya."""
    popup_options = {
        "title": "",
        "background": "atlas://data/images/defaulttheme/modalview-background",
        "background_color": (0, 0, 0, 0),
        "separator_height": 0,
        "title_size": 0,
        "content": content,
    }
    popup_options.update(kwargs)
    return Popup(**popup_options)


def button(
    label, callback, primary=False, height=44, outline=False,
    outline_color=None, fill_color=None, text_color=None
):
    """Tombol bergaya coffee premium dengan bidang membulat, state tekan, dan opsi outline secondary."""
    is_outline = outline or (label == "HAPUS")
    if is_outline:
        base_color = outline_color or CORAL
        bg_default = (base_color[0], base_color[1], base_color[2], 0.08)  # Latar transparan redup
        bg_pressed = base_color                                          # Solid saat ditekan
        text_default = base_color
        text_pressed = ON_ACCENT
    else:
        bg = fill_color or BUTTON_STYLES.get(label, ACCENT if primary else WHITE)
        bg_default = bg
        bg_pressed = tuple(max(0, c * 0.88) for c in bg[:3]) + (bg[3],)
        text_default = text_color or (ON_ACCENT if (primary or label in BUTTON_STYLES) else TEXT)
        text_pressed = text_default

    btn = Button(
        text=label,
        size_hint_y=None,
        height=dp(height),
        font_size=dp(12),
        bold=True,
        color=text_default,
        background_normal="",
        background_down="",
        background_color=(0, 0, 0, 0),
        padding=[dp(12), dp(8)],
    )

    with btn.canvas.before:
        btn._bg_color = Color(*bg_default)
        btn._bg_shape = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(12)])
        if is_outline:
            btn._line_color = Color(*base_color)
            btn._line_shape = Line(
                rounded_rectangle=(btn.x, btn.y, btn.width, btn.height, dp(12)),
                width=1.1
            )

    def update_shape(*_):
        btn._bg_shape.pos = btn.pos
        btn._bg_shape.size = btn.size
        if is_outline and hasattr(btn, "_line_shape"):
            btn._line_shape.rounded_rectangle = (
                btn.pos[0], btn.pos[1], btn.size[0], btn.size[1], dp(12)
            )

    btn.bind(pos=update_shape, size=update_shape)

    def pressed_state(_instance, state):
        if state == "down":
            btn._bg_color.rgba = bg_pressed
            btn.color = text_pressed
        else:
            btn._bg_color.rgba = bg_default
            btn.color = text_default

    btn.bind(state=pressed_state)
    btn.bind(on_release=lambda *_: callback() if callback else None)
    return btn


def status_chip(label, color, width=120, height=30):
    """Membuat label status ringkas dengan kontras warna yang tetap terbaca."""
    chip = Card(
        orientation="vertical",
        size_hint=(None, None),
        size=(dp(width), dp(height)),
        padding=[dp(6), 0, dp(6), 0],
        color=color,
        radius=8,
    )
    chip.add_widget(Text(
        str(label).upper(), size=10, bold=True, color=ON_ACCENT, align="center"
    ))
    return chip


def themed_popup(title, content, **kwargs):
    """Membuat popup dengan permukaan, teks, dan aksen tema aktif."""
    popup_options = {
        "background": "atlas://data/images/defaulttheme/modalview-background",
        "background_color": SURFACE,
        "title_color": TEXT,
        "separator_color": ACCENT,
        "separator_height": dp(2),
        "title_size": dp(17),
    }
    popup_options.update(kwargs)
    return Popup(title=title, content=content, **popup_options)


class Page(Screen):
    """Kelas dasar (base class) untuk setiap halaman di aplikasi POS.
    
    Setiap halaman dibungkus dengan ScrollView vertikal sehingga jika kontennya
    melebihi tinggi layar (misalnya saat katalog produk memiliki banyak menu),
    halaman tetap dapat digulir ke bawah tanpa merusak tata letak.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scroll = ScrollView(
            size_hint=(1, 1), do_scroll_x=False, bar_width=dp(5)
        )
        # Content box adalah wadah tempat widget halaman ditempatkan
        self.content = BoxLayout(
            orientation="vertical",
            size_hint=(1, None),
            spacing=dp(14),
            padding=[dp(22), dp(20), dp(22), dp(24)]
        )
        # Mengikat tinggi minimum konten agar scrollable mengikuti isi widget di dalamnya
        self.content.bind(minimum_height=self.content.setter("height"))
        self.scroll.add_widget(self.content)
        self.add_widget(self.scroll)

    def heading(self, title, subtitle):
        """Menambahkan bagian kepala halaman (header) yang seragam berisi judul dan subjudul."""
        box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(72),
            spacing=dp(12)
        )
        if LOGO_PATH.exists():
            logo = Image(
                source=str(LOGO_PATH),
                size_hint=(None, None),
                size=(dp(62), dp(62)),
                fit_mode="contain"
            )
            box.add_widget(logo)

        titles = BoxLayout(orientation="vertical", spacing=dp(2))
        titles.add_widget(Text(
            title, size=24, bold=True,
            size_hint_y=None, height=dp(38)
        ))
        titles.add_widget(Text(
            subtitle, size=13, color=MUTED,
            size_hint_y=None, height=dp(24)
        ))
        box.add_widget(titles)
        self.content.add_widget(box)