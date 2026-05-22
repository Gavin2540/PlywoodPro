from database.db import get_db
import models.ledger as ledger

def insert_purchase(product_id, date_str, qty, unit_price, supplier_name, notes):
    """Inserts a purchase record, then recalculates the stock ledger for that product and date."""
    date_str = ledger.get_date_str(date_str)
    
    # Verify ledger row is not locked/confirmed
    ledger_row = ledger.get_or_create_ledger_row(product_id, date_str)
    if ledger_row['is_confirmed'] == 1:
        raise PermissionError(f"Ledger is locked/confirmed for this date: {date_str}. Cannot add purchases.")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO purchases (product_id, date, qty, unit_price, supplier_name, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (product_id, date_str, qty, unit_price, supplier_name, notes))
        purchase_id = cursor.lastrowid
        conn.commit()
        
    # Recalculate ledger for this product and date
    ledger.recalculate_ledger(product_id, date_str)
    
    return purchase_id

def delete_purchase(purchase_id):
    """Deletes a purchase record, then triggers recalculation of the stock ledger."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Fetch info before deletion for ledger recalculation
        cursor.execute("SELECT product_id, date FROM purchases WHERE id = ?", (purchase_id,))
        row = cursor.fetchone()
        if not row:
            return False
            
        product_id = row['product_id']
        date_str = row['date']
        
        # Verify ledger row is not locked/confirmed
        ledger_row = ledger.get_or_create_ledger_row(product_id, date_str)
        if ledger_row['is_confirmed'] == 1:
            raise PermissionError(f"Ledger is locked/confirmed for this date: {date_str}. Cannot delete purchases.")
            
        # 2. Perform deletion
        cursor.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,))
        conn.commit()
        
    # Recalculate ledger for this product and date
    ledger.recalculate_ledger(product_id, date_str)
    
    return True

def get_purchases_by_date(date_str):
    """Retrieve all purchases made on a specific date, joined with product metadata."""
    date_str = ledger.get_date_str(date_str)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                p.id,
                p.product_id,
                p.date,
                p.qty,
                p.unit_price,
                (p.qty * p.unit_price) as total_cost,
                p.supplier_name,
                p.notes,
                p.created_at,
                prod.name as product_name,
                prod.brand as product_brand,
                prod.type as product_type,
                prod.thickness as product_thickness,
                prod.size as product_size,
                prod.unit as product_unit
            FROM purchases p
            JOIN products prod ON p.product_id = prod.id
            WHERE p.date = ?
            ORDER BY p.id DESC
        """, (date_str,))
        return [dict(row) for row in cursor.fetchall()]

def get_all_purchases():
    """Retrieve all purchase records in reverse chronological order."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                p.id,
                p.product_id,
                p.date,
                p.qty,
                p.unit_price,
                (p.qty * p.unit_price) as total_cost,
                p.supplier_name,
                p.notes,
                p.created_at,
                prod.name as product_name,
                prod.brand as product_brand,
                prod.type as product_type,
                prod.thickness as product_thickness,
                prod.size as product_size,
                prod.unit as product_unit
            FROM purchases p
            JOIN products prod ON p.product_id = prod.id
            ORDER BY p.date DESC, p.id DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
