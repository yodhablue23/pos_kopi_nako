"""Palette runtime POS Kopi Nako untuk mode terang, gelap, dan aksen tema."""
from kivy.core.window import Window


THEME_MODES = ("light", "dark")
ACCENT_THEMES = {
    "purple": "#6742A7",
    "orange": "#B94F1F",
    "cyan": "#08777A",
    "blue": "#2F5FA8",
    "red": "#A83B3B",
    "black": "#2B2724",
}


def _rgba(value):
    value = value.lstrip("#")
    return [
        int(value[index:index + 2], 16) / 255
        for index in (0, 2, 4)
    ] + [1.0]


def _blend(foreground, background, amount):
    return [
        foreground[index] * (1 - amount) + background[index] * amount
        for index in range(3)
    ] + [1.0]


def accent_color(name):
    """Mengembalikan warna preview aksen tanpa mengubah tema aktif."""
    return _rgba(ACCENT_THEMES.get(name, ACCENT_THEMES["cyan"]))


# Mutable lists keep imported references valid when the user changes a theme.
BACKGROUND = _rgba("#F3EEE5")
SURFACE = _rgba("#FFFCF5")
SURFACE_ALT = _rgba("#F5E9D5")
TEXT = _rgba("#291811")
ON_ACCENT = _rgba("#FFFFFF")
MUTED_TEXT = _rgba("#7A6B5C")
BORDER = _rgba("#D5C7B8")
BORDER_STRONG = _rgba("#7A6D62")
INPUT = _rgba("#F6F0E7")
ACCENT = _rgba(ACCENT_THEMES["cyan"])
ACCENT_TEXT = _rgba(ACCENT_THEMES["cyan"])
ACCENT_DARK = _rgba("#07565A")
ACCENT_SOFT = _rgba("#D5ECE8")
ACCENT_ALT = _rgba(ACCENT_THEMES["cyan"])
SUCCESS = _rgba("#2E7D52")
SUCCESS_TEXT = _rgba("#2E7D52")
DANGER = _rgba("#B64040")
DANGER_TEXT = _rgba("#B64040")
WARNING = _rgba("#B86A1E")
WARNING_TEXT = _rgba("#9B591A")
INFO = _rgba("#2F5FA8")
RECEIPT_PAPER = _rgba("#FFFFFF")
RECEIPT_TEXT = _rgba("#0F0F0F")

# Compatibility aliases used by the existing screens. Their references remain
# live because the lists above are updated in place.
COFFEE = TEXT
BROWN = ACCENT_TEXT
WHITE = SURFACE
CREAM = SURFACE_ALT
MUTED = MUTED_TEXT
GREEN = SUCCESS
TEAL = ACCENT_TEXT
CORAL = DANGER
PURPLE = ACCENT_ALT
BLUE = INFO
GOLD = WARNING
MINT = SURFACE_ALT
PEACH = SURFACE_ALT
LILAC = SURFACE_ALT
SKY = INPUT

NAV_COLORS = {
    "home": ACCENT,
    "products": ACCENT_DARK,
    "cart": SUCCESS,
    "reports": ACCENT_ALT,
}
BUTTON_STYLES = {
    "BUKA MENU PRODUK": ACCENT,
    "TAMBAH +": ACCENT_DARK,
    "LIHAT STRUK": INFO,
    "HAPUS": DANGER,
    "YA, HAPUS": DANGER,
    "LANJUT PEMBAYARAN": ACCENT,
    "TRANSAKSI BARU": ACCENT_DARK,
    "KOSONGKAN KERANJANG": WARNING,
    "Tunai": SUCCESS,
    "QRIS": INFO,
    "Tunai (Uang Cash)": SUCCESS,
    "Saldo E-Wallet (Barcode)": INFO,
    "Kartu": ACCENT_ALT,
    "Kartu Debit Digital": ACCENT_ALT,
    "VERIFIKASI & BAYAR": SUCCESS,
    "PROSES PEMBAYARAN": SUCCESS,
    "SELESAIKAN PEMBAYARAN": SUCCESS,
    "MASUK": ACCENT,
    "KELUAR": DANGER,
}


def _update(target, value):
    target[:] = value


def apply_theme(mode="light", accent="cyan"):
    """Menerapkan palette aktif dan memperbarui warna jendela aplikasi."""
    if mode not in THEME_MODES:
        mode = "light"
    if accent not in ACCENT_THEMES:
        accent = "cyan"

    if mode == "dark":
        background = _rgba("#171412")
        surface = _rgba("#26211D")
        surface_alt = _rgba("#332A24")
        text = _rgba("#FFF8EF")
        muted = _rgba("#C7BDB2")
        border = _rgba("#5B4D42")
        input_color = _rgba("#302A25")
    else:
        background = _rgba("#F3EEE5")
        surface = _rgba("#FFFCF5")
        surface_alt = _rgba("#F5E9D5")
        text = _rgba("#291811")
        muted = _rgba("#7A6B5C")
        border = _rgba("#D5C7B8")
        input_color = _rgba("#F6F0E7")

    accent_color = _rgba(ACCENT_THEMES[accent])
    accent_dark = _blend(accent_color, _rgba("#000000"), 0.18)
    accent_soft = _blend(accent_color, surface, 0.82)
    if mode == "dark":
        accent_text = _blend(accent_color, _rgba("#FFFFFF"), 0.55)
        success_text = _blend(SUCCESS, _rgba("#FFFFFF"), 0.55)
        danger_text = _blend(DANGER, _rgba("#FFFFFF"), 0.55)
        warning_text = _blend(WARNING, _rgba("#FFFFFF"), 0.55)
    else:
        accent_text = accent_color
        success_text = SUCCESS
        danger_text = DANGER
        warning_text = WARNING_TEXT

    _update(BACKGROUND, background)
    _update(SURFACE, surface)
    _update(SURFACE_ALT, surface_alt)
    _update(TEXT, text)
    _update(MUTED_TEXT, muted)
    _update(BORDER, border)
    _update(BORDER_STRONG, _rgba("#7A6D62"))
    _update(INPUT, input_color)
    _update(ACCENT, accent_color)
    _update(ACCENT_TEXT, accent_text)
    _update(ACCENT_DARK, accent_dark)
    _update(ACCENT_SOFT, accent_soft)
    _update(ACCENT_ALT, accent_color)
    _update(SUCCESS_TEXT, success_text)
    _update(DANGER_TEXT, danger_text)
    _update(WARNING_TEXT, warning_text)
    _update(RECEIPT_PAPER, _rgba("#FFFFFF"))
    _update(RECEIPT_TEXT, _rgba("#0F0F0F"))

    if Window is not None:
        Window.clearcolor = BACKGROUND

    return {"mode": mode, "accent": accent}


apply_theme()