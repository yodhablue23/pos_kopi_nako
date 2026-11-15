"""Modul logika dan hak akses khusus role Administrator (Admin)."""
from pathlib import Path
import shutil
import uuid

from database import MAX_PRODUCT_STOCK, normalize_product_name

ROLE_NAME = "admin"
ALLOWED_SCREENS = ("home", "products", "reports")
CAN_MANAGE_PRODUCTS = True
CAN_MANAGE_STOCK = True
CAN_DELETE_ORDERS = True
REQUIRE_CUSTOMER_LABEL = False


def validate_admin_access(user_role, action_name="aksi ini"):
    """Memastikan hanya role admin yang dapat menjalankan aksi sensitif."""
    if user_role != ROLE_NAME:
        if action_name in ("menambah atau menghapus produk", "produk"):
            raise ValueError("Hanya Admin yang dapat menambah atau menghapus produk.")
        if action_name in ("menghapus riwayat transaksi", "transaksi"):
            raise ValueError("Hanya Admin yang dapat menghapus riwayat transaksi.")
        raise ValueError(f"Hanya Admin yang dapat melakukan {action_name}.")


def admin_create_product(app, raw_name, category, raw_price, raw_stock, image_path=None):
    """Validasi dan eksekusi penambahan produk baru oleh Admin."""
    if app.current_user is None:
        raise ValueError("Anda harus login untuk menambahkan produk.")
    validate_admin_access(app.user_role(), "menambah atau menghapus produk")
    if app.db_error:
        raise ValueError("Database belum tersambung.")

    name = normalize_product_name(raw_name)
    if raw_price is None or not str(raw_price).strip():
        raise ValueError("Harga produk wajib diisi.")
    if raw_stock is None or not str(raw_stock).strip():
        raise ValueError("Stok awal wajib diisi.")

    try:
        price_text = str(raw_price).strip().replace(",", "")
        price = float(price_text)
        stock = int(str(raw_stock).strip())
    except (TypeError, ValueError):
        raise ValueError("Harga harus angka dan stok harus bilangan bulat.")
    if price <= 0:
        raise ValueError("Harga harus lebih dari 0.")
    if price > 100000:
        raise ValueError("Harga produk maksimal Rp 100.000.")
    if stock < 0:
        raise ValueError("Stok tidak boleh negatif.")
    if stock > MAX_PRODUCT_STOCK:
        raise ValueError(f"Stok awal maksimal {MAX_PRODUCT_STOCK} item.")

    final_image_path = None
    saved_image = None
    if image_path:
        source = Path(image_path)
        if not source.is_file():
            raise ValueError("File foto produk tidak ditemukan.")
        extension = source.suffix.lower()
        if extension not in (".jpg", ".jpeg", ".png", ".webp"):
            raise ValueError("Format foto harus JPG, JPEG, PNG, atau WEBP.")
        image_dir = Path(app.user_data_dir) / "product_images"
        image_dir.mkdir(parents=True, exist_ok=True)
        saved_image = image_dir / f"product_{uuid.uuid4().hex}{extension}"
        shutil.copy2(source, saved_image)
        final_image_path = str(saved_image)

    try:
        product = app.db.create_product(
            name, category, price, stock, image_path=final_image_path
        )
    except Exception:
        if saved_image is not None:
            try:
                saved_image.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    app.discard_product_image(image_path)
    product["image_path"] = final_image_path
    app.refresh_data()
    return product


def admin_delete_product(app, product_id):
    """Validasi dan eksekusi pengarsipan/penghapusan produk oleh Admin."""
    if app.current_user is None:
        raise ValueError("Anda harus login untuk menghapus produk.")
    validate_admin_access(app.user_role(), "menambah atau menghapus produk")
    if app.db_error:
        raise ValueError("Database belum tersambung.")

    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        raise ValueError("Produk yang dipilih tidak valid.")

    product = app.products_by_id.get(product_id)
    if product is None:
        raise ValueError("Produk tidak ditemukan atau sudah dihapus.")

    app.db.delete_product(product_id)
    app.cart.pop(product_id, None)
    app.refresh_data()

    if hasattr(app, "sm") and app.sm.current == "cart":
        app.sm.get_screen("cart").render()
    return product


def admin_delete_order(app, order, popup=None):
    """Validasi dan eksekusi penghapusan riwayat transaksi oleh Admin."""
    try:
        validate_admin_access(app.user_role(), "menghapus riwayat transaksi")
    except ValueError as error:
        app.notice(str(error))
        return False

    try:
        transaction_id = int(str(order["id"]).replace("KN-", ""))
        app.db.delete_order(transaction_id)
        app.refresh_data()
        app.refresh_report()
        if popup is not None:
            popup.dismiss()
        if hasattr(app, "sm") and app.sm.current == "reports":
            app.sm.get_screen("reports").render()
        app.notice("Transaksi berhasil dihapus.")
        return True
    except Exception as error:
        app.notice("Transaksi gagal dihapus:\n" + str(error))
        return False

