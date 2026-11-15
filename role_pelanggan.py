"""Modul logika dan hak akses khusus role Pelanggan (Self-Order)."""
from database import normalize_customer_label

ROLE_NAME = "pelanggan"
ALLOWED_SCREENS = ("products", "cart")
CAN_MANAGE_PRODUCTS = False
CAN_MANAGE_STOCK = False
CAN_DELETE_ORDERS = False
REQUIRE_CUSTOMER_LABEL = True


def build_customer_session():
    """Mengembalikan data sesi pengguna untuk mode Self-Order Pelanggan."""
    return {
        "id": 0,
        "username": "pelanggan",
        "nama": "Pelanggan Mandiri",
        "role": ROLE_NAME,
    }


def validate_customer_checkout(customer_name):
    """Memastikan nama pelanggan atau nomor meja wajib diisi saat mode pelanggan."""
    cleaned = normalize_customer_label(customer_name)
    if not cleaned:
        raise ValueError(
            "Harap isi Nama Anda atau Nomor Meja terlebih dahulu sebelum membayar!"
        )
    return cleaned


def pelanggan_pay_at_cashier(app, popup, total):
    """Memproses pesanan mandiri dengan metode Tunai (Kasir) tanpa form kembalian kasir."""
    app.finish_payment("Tunai (Kasir)", popup, bayar=total, kembalian=0)

