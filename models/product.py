from database.db import get_db

def get_active_products():
    """Retrieve all active (non-soft-deleted) products, sorted by name and brand."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, brand, type, thickness, size, purchase_price, selling_price, unit, low_stock_threshold, created_at
            FROM products
            WHERE is_active = 1
            ORDER BY name ASC, brand ASC
        """)
        return [dict(row) for row in cursor.fetchall()]

def get_product_by_id(product_id):
    """Retrieve a single product by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, brand, type, thickness, size, purchase_price, selling_price, unit, low_stock_threshold, is_active, created_at
            FROM products
            WHERE id = ?
        """, (product_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def add_product(name, brand, type_, thickness, size, purchase_price, selling_price, unit="sheets", low_stock_threshold=10):
    """Add a new product to the database."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (name, brand, type, thickness, size, purchase_price, selling_price, unit, low_stock_threshold)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, brand, type_, thickness, size, purchase_price, selling_price, unit, low_stock_threshold))
        conn.commit()
        return cursor.lastrowid

def update_product(product_id, name, brand, type_, thickness, size, purchase_price, selling_price, unit, low_stock_threshold):
    """Update all fields of an existing product."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE products
            SET name = ?, brand = ?, type = ?, thickness = ?, size = ?, purchase_price = ?, selling_price = ?, unit = ?, low_stock_threshold = ?
            WHERE id = ?
        """, (name, brand, type_, thickness, size, purchase_price, selling_price, unit, low_stock_threshold, product_id))
        conn.commit()
        return cursor.rowcount > 0

def soft_delete_product(product_id):
    """Soft delete a product by setting is_active = 0.
    This preserves the product record for historical transactions.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE products
            SET is_active = 0
            WHERE id = ?
        """, (product_id,))
        conn.commit()
        return cursor.rowcount > 0
