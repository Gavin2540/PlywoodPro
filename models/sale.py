from database.db import get_db
import models.ledger as ledger
import models.product as product

def insert_sale(product_id, date_str, qty, unit_price, customer_name, notes):
    """Inserts a sale transaction after validating stock levels.
    Snapshots the purchase price at this time, then recalculates the stock ledger.
    """
    date_str = ledger.get_date_str(date_str)
    
    # 1. Verify ledger is not locked/confirmed for this date
    ledger_row = ledger.get_or_create_ledger_row(product_id, date_str)
    if ledger_row['is_confirmed'] == 1:
        raise PermissionError(f"Ledger is locked/confirmed for this date: {date_str}. Cannot add sales.")
        
    # 2. Check stock availability
    current_stock = ledger.get_current_stock(product_id)
    if current_stock < qty:
        raise ValueError(f"Insufficient stock for this sale. Available: {current_stock} units, Requested: {qty} units.")
        
    # 3. Snapshot purchase price at this time
    product_details = product.get_product_by_id(product_id)
    if not product_details:
        raise ValueError("Product not found.")
    purchase_price_at_time = product_details['purchase_price']
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sales (product_id, date, qty, unit_price, purchase_price_at_time, customer_name, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (product_id, date_str, qty, unit_price, purchase_price_at_time, customer_name, notes))
        sale_id = cursor.lastrowid
        conn.commit()
        
    # 4. Recalculate ledger for this product and date
    ledger.recalculate_ledger(product_id, date_str)
    
    return sale_id

def delete_sale(sale_id):
    """Deletes a sale record and triggers stock ledger recalculation."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Fetch info before deletion for ledger recalculation
        cursor.execute("SELECT product_id, date FROM sales WHERE id = ?", (sale_id,))
        row = cursor.fetchone()
        if not row:
            return False
            
        product_id = row['product_id']
        date_str = row['date']
        
        # Verify ledger row is not locked/confirmed
        ledger_row = ledger.get_or_create_ledger_row(product_id, date_str)
        if ledger_row['is_confirmed'] == 1:
            raise PermissionError(f"Ledger is locked/confirmed for this date: {date_str}. Cannot delete sales.")
            
        # 2. Perform deletion
        cursor.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
        conn.commit()
        
    # Recalculate ledger for this product and date
    ledger.recalculate_ledger(product_id, date_str)
    
    return True

def get_sales_by_date(date_str):
    """Retrieve all sales made on a specific date, joined with product metadata and profit computations."""
    date_str = ledger.get_date_str(date_str)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                s.id,
                s.product_id,
                s.date,
                s.qty,
                s.unit_price,
                s.purchase_price_at_time,
                (s.qty * s.unit_price) as total_revenue,
                (s.qty * s.purchase_price_at_time) as total_cost,
                ((s.unit_price - s.purchase_price_at_time) * s.qty) as margin_profit,
                s.customer_name,
                s.notes,
                s.created_at,
                prod.name as product_name,
                prod.brand as product_brand,
                prod.type as product_type,
                prod.thickness as product_thickness,
                prod.size as product_size,
                prod.unit as product_unit
            FROM sales s
            JOIN products prod ON s.product_id = prod.id
            WHERE s.date = ?
            ORDER BY s.id DESC
        """, (date_str,))
        return [dict(row) for row in cursor.fetchall()]

def get_all_sales():
    """Retrieve all sales records in reverse chronological order with profit calculation."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                s.id,
                s.product_id,
                s.date,
                s.qty,
                s.unit_price,
                s.purchase_price_at_time,
                (s.qty * s.unit_price) as total_revenue,
                (s.qty * s.purchase_price_at_time) as total_cost,
                ((s.unit_price - s.purchase_price_at_time) * s.qty) as margin_profit,
                s.customer_name,
                s.notes,
                s.created_at,
                prod.name as product_name,
                prod.brand as product_brand,
                prod.type as product_type,
                prod.thickness as product_thickness,
                prod.size as product_size,
                prod.unit as product_unit
            FROM sales s
            JOIN products prod ON s.product_id = prod.id
            ORDER BY s.date DESC, s.id DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
