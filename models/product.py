"""Product catalogue."""
from database.db import get_db
from models import stock

_FIELDS = "id, name, brand, type, thickness, size, purchase_price, selling_price, unit, " \
          "low_stock_threshold, opening_stock, is_active, created_at"


def _validate(name, purchase_price, selling_price, low_stock_threshold, opening_stock):
    if not (name or "").strip():
        raise ValueError("Product name is required.")
    if purchase_price < 0 or selling_price < 0:
        raise ValueError("Prices cannot be negative.")
    if low_stock_threshold < 0:
        raise ValueError("Low-stock level cannot be negative.")
    if opening_stock < 0:
        raise ValueError("Opening stock cannot be negative.")


def _clash(conn, name, brand, thickness, size, exclude_id=0):
    return conn.execute(
        """
        SELECT id FROM products
        WHERE is_active = 1 AND id != ?
          AND name = ? COLLATE NOCASE AND COALESCE(brand, '') = ? COLLATE NOCASE
          AND COALESCE(thickness, '') = ? COLLATE NOCASE AND COALESCE(size, '') = ? COLLATE NOCASE
        """, (exclude_id, name, brand or "", thickness or "", size or "")).fetchone()


def add_product(name, brand, type_, thickness, size, purchase_price, selling_price,
                unit="sheets", low_stock_threshold=10, opening_stock=0.0):
    name = (name or "").strip()
    _validate(name, purchase_price, selling_price, low_stock_threshold, opening_stock)
    with get_db() as conn:
        if _clash(conn, name, brand, thickness, size):
            raise ValueError("A product with the same name, brand, thickness and size already exists.")
        return conn.execute(
            "INSERT INTO products (name, brand, type, thickness, size, purchase_price, selling_price, unit, "
            "low_stock_threshold, opening_stock) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, brand, type_, thickness, size, purchase_price, selling_price, unit or "sheets",
             low_stock_threshold, opening_stock),
        ).lastrowid


def update_product(product_id, name, brand, type_, thickness, size, purchase_price, selling_price,
                   unit, low_stock_threshold, opening_stock=None):
    name = (name or "").strip()
    with get_db() as conn:
        current = conn.execute("SELECT opening_stock FROM products WHERE id = ?", (product_id,)).fetchone()
        if not current:
            return False
        if opening_stock is None:
            opening_stock = current["opening_stock"]
        _validate(name, purchase_price, selling_price, low_stock_threshold, opening_stock)
        if _clash(conn, name, brand, thickness, size, product_id):
            raise ValueError("A product with the same name, brand, thickness and size already exists.")
        conn.execute(
            "UPDATE products SET name = ?, brand = ?, type = ?, thickness = ?, size = ?, purchase_price = ?, "
            "selling_price = ?, unit = ?, low_stock_threshold = ?, opening_stock = ? WHERE id = ?",
            (name, brand, type_, thickness, size, purchase_price, selling_price, unit or "sheets",
             low_stock_threshold, opening_stock, product_id),
        )
        if opening_stock != current["opening_stock"] and stock.min_balance_from(product_id, "0000-01-01") < -stock.EPS:
            raise stock.StockError("Opening stock is too low for the sales already recorded.")
    return True


def soft_delete_product(product_id):
    """Hide a product; its history is kept."""
    with get_db() as conn:
        return conn.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,)).rowcount > 0


def restore_product(product_id):
    with get_db() as conn:
        return conn.execute("UPDATE products SET is_active = 1 WHERE id = ?", (product_id,)).rowcount > 0


def get_product_by_id(product_id):
    with get_db() as conn:
        row = conn.execute(f"SELECT {_FIELDS} FROM products WHERE id = ?", (product_id,)).fetchone()
    return dict(row) if row else None


def get_active_products():
    return list_products()


def list_products(include_inactive=False, with_stock=True):
    """Products sorted by name; each gets ``stock``, ``stock_value`` and ``status``."""
    where = "" if include_inactive else "WHERE is_active = 1"
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            f"SELECT {_FIELDS} FROM products {where} ORDER BY name COLLATE NOCASE, brand COLLATE NOCASE")]
    if with_stock:
        levels = stock.stock_map()
        for p in rows:
            qty = levels.get(p["id"], 0.0)
            p["stock"] = qty
            p["stock_value"] = round(qty * p["purchase_price"], 2)
            p["status"] = "out" if qty <= stock.EPS else "low" if qty <= p["low_stock_threshold"] else "ok"
    return rows


def label(p):
    """'Greenply BWP 18mm 8x4' style one-line description."""
    keys = ("name", "brand", "type", "thickness", "size")
    if "product_name" in p:
        keys = tuple("product_" + k for k in keys)
    return " · ".join(str(p[k]) for k in keys if p.get(k))


def distinct_values(column):
    """Existing values of a text column, for autocomplete."""
    if column not in ("brand", "type", "thickness", "size", "unit", "name"):
        raise ValueError(column)
    with get_db() as conn:
        return [r[0] for r in conn.execute(
            f"SELECT DISTINCT {column} FROM products WHERE {column} IS NOT NULL AND {column} != '' "
            f"ORDER BY {column} COLLATE NOCASE")]
