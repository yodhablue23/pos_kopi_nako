"""Modul logika dan hak akses khusus role Kasir."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout

from theme import MUTED, SUCCESS_TEXT
from ui_components import Text, button, rp, text_input, themed_popup

ROLE_NAME = "kasir"
ALLOWED_SCREENS = ("home", "products", "cart", "reports")
CAN_MANAGE_PRODUCTS = False
CAN_MANAGE_STOCK = True
CAN_DELETE_ORDERS = False
REQUIRE_CUSTOMER_LABEL = False


def validate_stock_access(user_role):
    """Memastikan hanya Admin atau Kasir yang dapat menambah stok produk."""
    if user_role not in ("admin", ROLE_NAME):
        raise ValueError("Pelanggan tidak memiliki akses manajemen stok.")


def kasir_add_stock(app, product_id, raw_quantity):
    """Validasi dan eksekusi penambahan stok produk oleh Kasir/Admin."""
    if app.current_user is None:
        raise ValueError("Anda harus login sebagai kasir untuk mengubah stok.")
    validate_stock_access(app.user_role())
    if app.db_error:
        raise ValueError("Database belum tersambung.")
    if raw_quantity is None or not str(raw_quantity).strip():
        raise ValueError("Jumlah stok masuk wajib diisi.")

    try:
        quantity = int(str(raw_quantity).strip())
    except (TypeError, ValueError):
        raise ValueError("Jumlah stok harus berupa bilangan bulat.")
    if quantity <= 0:
        raise ValueError("Jumlah stok masuk harus lebih dari 0.")

    updated_product = app.db.increase_stock(product_id, quantity)
    app.refresh_data()
    return updated_product


def kasir_open_cash_tender(app, parent_popup, total, style_popup_fn=None):
    """Membuka jendela form penerimaan uang tunai kasir dan hitung kembalian otomatis."""
    if parent_popup is not None:
        parent_popup.dismiss()

    content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
    content.add_widget(Text(
        f"Total Tagihan: {rp(total)}",
        size=19, bold=True, color=(1, 1, 1, 1), size_hint_y=None, height=dp(6),
        align="center"
    ))

    content.add_widget(Text(
        "Uang Tunai Diterima (Rp):",
        size=12, bold=True, color=MUTED, size_hint_y=None, height=dp(18)
    ))

    cash_input = text_input(
        text=str(int(total)),
        height=46, font_size=18, input_filter="int"
    )
    content.add_widget(cash_input)

    quick_grid = GridLayout(cols=4, spacing=dp(6), size_hint_y=None, height=dp(36))
    quick_values = [
        ("Uang Pas", int(total)),
        ("Rp 20.000", 20000),
        ("Rp 50.000", 50000),
        ("Rp 100.000", 100000),
    ]
    for label, val in quick_values:
        quick_grid.add_widget(button(
            label,
            lambda v=val: setattr(cash_input, "text", str(v)),
            False, 34
        ))
    content.add_widget(quick_grid)

    change_label = Text(
        "Kembalian: Rp 0",
        size=16, bold=True, color=SUCCESS_TEXT, size_hint_y=None, height=dp(30),
        align="center"
    )
    content.add_widget(change_label)

    def update_change(*_):
        raw_text = cash_input.text.strip()
        if not raw_text:
            change_label.text = "Masukkan nominal pembayaran"
            change_label.color = (1, 1, 1, 1)
            return
        try:
            nominal = int(raw_text)
            kembalian = nominal - total
            if kembalian < 0:
                change_label.text = f"Uang Kurang: {rp(abs(kembalian))}"
                change_label.color = (1, 0.58, 0.58, 1)
            else:
                change_label.text = f"Kembalian: {rp(kembalian)}"
                change_label.color = (0.55, 1, 0.72, 1)
        except ValueError:
            change_label.text = "Nominal tidak valid"
            change_label.color = (1, 0.58, 0.58, 1)

    cash_input.bind(text=update_change)
    update_change()

    tender_popup = themed_popup(
        "Pembayaran Tunai & Kembalian", content,
        size_hint=(0.88, None), height=dp(390),
    )
    if style_popup_fn is not None:
        style_popup_fn(tender_popup, content)

    def submit_cash():
        raw_text = cash_input.text.strip()
        if not raw_text:
            app.notice("Harap masukkan nominal uang tunai.")
            return
        try:
            nominal = int(raw_text)
        except ValueError:
            app.notice("Nominal uang harus berupa angka.")
            return

        if nominal < total:
            app.notice(f"Uang tidak mencukupi! Kurang {rp(total - nominal)}.")
            return

        kembalian = nominal - total
        app.finish_payment("Tunai", tender_popup, bayar=nominal, kembalian=kembalian)

    actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
    actions.add_widget(button("BATAL", tender_popup.dismiss, False, 40))
    actions.add_widget(button("SELESAIKAN PEMBAYARAN", submit_cash, True, 40))
    content.add_widget(actions)

    tender_popup.open()

