import datetime
from database.db import get_db

def get_date_str(date_obj):
    """Utility to convert date/datetime or string to YYYY-MM-DD string."""
    if isinstance(date_obj, (datetime.date, datetime.datetime)):
        return date_obj.strftime("%Y-%m-%d")
    return str(date_obj)

def get_or_create_ledger_row(product_id, date_str):
    """Gets an existing ledger row for a product and date, or creates it.
    If creating, calculates opening stock from the most recent closing stock in history.
    """
    date_str = get_date_str(date_str)
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Try to fetch existing row
        cursor.execute("""
            SELECT id, product_id, date, opening_stock, purchases_qty, sales_qty, closing_stock, is_confirmed, manual_override, override_note
            FROM stock_ledger
            WHERE product_id = ? AND date = ?
        """, (product_id, date_str))
        row = cursor.fetchone()
        if row:
            return dict(row)
        
        # 2. Find the most recent ledger row before this date
        cursor.execute("""
            SELECT closing_stock
            FROM stock_ledger
            WHERE product_id = ? AND date < ?
            ORDER BY date DESC
            LIMIT 1
        """, (product_id, date_str))
        prev_row = cursor.fetchone()
        opening_stock = prev_row['closing_stock'] if prev_row else 0.0
        
        # 3. Insert new row
        cursor.execute("""
            INSERT INTO stock_ledger (product_id, date, opening_stock, purchases_qty, sales_qty, closing_stock, is_confirmed, manual_override)
            VALUES (?, ?, ?, 0.0, 0.0, ?, 0, 0)
        """, (product_id, date_str, opening_stock, opening_stock))
        conn.commit()
        
        cursor.execute("""
            SELECT id, product_id, date, opening_stock, purchases_qty, sales_qty, closing_stock, is_confirmed, manual_override, override_note
            FROM stock_ledger
            WHERE id = ?
        """, (cursor.lastrowid,))
        return dict(cursor.fetchone())

def recalculate_ledger(product_id, date_str):
    """Recalculates the purchases_qty, sales_qty, and closing_stock for a specific product and date.
    Propagates the changes forward to all subsequent unconfirmed ledger rows.
    """
    date_str = get_date_str(date_str)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Ensure ledger row exists
        row = get_or_create_ledger_row(product_id, date_str)
        if row['is_confirmed'] == 1:
            # Locked: do not recalculate this row directly
            return row
            
        # Get actual sum of purchases on this date
        cursor.execute("""
            SELECT SUM(qty) as total_purchases
            FROM purchases
            WHERE product_id = ? AND date = ?
        """, (product_id, date_str))
        p_row = cursor.fetchone()
        purchases_qty = p_row['total_purchases'] if p_row['total_purchases'] is not None else 0.0
        
        # Get actual sum of sales on this date
        cursor.execute("""
            SELECT SUM(qty) as total_sales
            FROM sales
            WHERE product_id = ? AND date = ?
        """, (product_id, date_str))
        s_row = cursor.fetchone()
        sales_qty = s_row['total_sales'] if s_row['total_sales'] is not None else 0.0
        
        # Calculate closing stock unless overridden manually
        if row['manual_override'] == 1:
            closing_stock = row['closing_stock']
        else:
            closing_stock = row['opening_stock'] + purchases_qty - sales_qty
            
        cursor.execute("""
            UPDATE stock_ledger
            SET purchases_qty = ?, sales_qty = ?, closing_stock = ?
            WHERE product_id = ? AND date = ?
        """, (purchases_qty, sales_qty, closing_stock, product_id, date_str))
        conn.commit()
        
    # Propagate changes to subsequent dates
    propagate_ledger_forward(product_id, date_str)
    
    return get_or_create_ledger_row(product_id, date_str)

def propagate_ledger_forward(product_id, start_date_str):
    """Propagates the closing stock of start_date_str to all subsequent ledger rows.
    Stops at the first confirmed row.
    """
    start_date_str = get_date_str(start_date_str)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get closing stock of the starting day
        cursor.execute("""
            SELECT closing_stock
            FROM stock_ledger
            WHERE product_id = ? AND date = ?
        """, (product_id, start_date_str))
        start_row = cursor.fetchone()
        if not start_row:
            return
        
        current_closing = start_row['closing_stock']
        
        # Fetch all future ledger rows for this product, ordered by date ASC
        cursor.execute("""
            SELECT id, date, opening_stock, purchases_qty, sales_qty, closing_stock, is_confirmed, manual_override
            FROM stock_ledger
            WHERE product_id = ? AND date > ?
            ORDER BY date ASC
        """, (product_id, start_date_str))
        future_rows = [dict(r) for r in cursor.fetchall()]
        
        for row in future_rows:
            if row['is_confirmed'] == 1:
                # Propagation stops at the first confirmed/locked day
                # Ensure the confirmed day's opening stock matches the prior closing stock
                # If there's a discrepancy, we don't auto-correct the confirmed day's closing stock, 
                # but we do log it or enforce consistency on opening.
                cursor.execute("""
                    UPDATE stock_ledger
                    SET opening_stock = ?
                    WHERE id = ?
                """, (current_closing, row['id']))
                conn.commit()
                break
                
            # Recalculate opening and closing
            new_opening = current_closing
            if row['manual_override'] == 1:
                new_closing = row['closing_stock'] # keep manual override
            else:
                new_closing = new_opening + row['purchases_qty'] - row['sales_qty']
                
            cursor.execute("""
                UPDATE stock_ledger
                SET opening_stock = ?, closing_stock = ?
                WHERE id = ?
            """, (new_opening, new_closing, row['id']))
            conn.commit()
            
            current_closing = new_closing

def confirm_ledger_row(product_id, date_str):
    """Confirms/Locks a ledger row for a specific product and date.
    Automatically creates the next day's ledger row with carrying forward opening stock.
    """
    date_str = get_date_str(date_str)
    
    # Recalculate first to ensure accurate numbers
    row = recalculate_ledger(product_id, date_str)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE stock_ledger
            SET is_confirmed = 1
            WHERE product_id = ? AND date = ?
        """, (product_id, date_str))
        conn.commit()
        
    # Calculate next day's date string
    current_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    next_day_str = get_date_str(current_date + datetime.timedelta(days=1))
    
    # Initialize next day's ledger row (it will automatically carry forward today's closing stock)
    get_or_create_ledger_row(product_id, next_day_str)
    recalculate_ledger(product_id, next_day_str)
    
    return True

def confirm_all_ledger_rows(date_str):
    """Confirms all active products' ledger rows for a specific date."""
    date_str = get_date_str(date_str)
    
    # Fetch all active products
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM products WHERE is_active = 1")
        product_ids = [r['id'] for r in cursor.fetchall()]
        
    for p_id in product_ids:
        confirm_ledger_row(p_id, date_str)
        
    return True

def override_ledger_row(product_id, date_str, physical_qty, note):
    """Sets a manual physical count override on a ledger row, recalculates, and propagates forward."""
    date_str = get_date_str(date_str)
    
    # Ensure ledger row exists
    get_or_create_ledger_row(product_id, date_str)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE stock_ledger
            SET manual_override = 1, closing_stock = ?, override_note = ?
            WHERE product_id = ? AND date = ?
        """, (physical_qty, note, product_id, date_str))
        conn.commit()
        
    # Recalculate and propagate
    recalculate_ledger(product_id, date_str)
    return True

def get_current_stock(product_id):
    """Get the absolute current stock level of a product based on the latest ledger closing stock.
    If no ledger entries exist, returns 0.0.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        # First ensure there's at least one ledger row for today (so recent transactions are accounted for)
        today_str = get_date_str(datetime.date.today())
        
        # We check if there are transactions in history for this product
        cursor.execute("SELECT MAX(date) as max_date FROM purchases WHERE product_id = ?", (product_id,))
        p_max = cursor.fetchone()['max_date']
        
        cursor.execute("SELECT MAX(date) as max_date FROM sales WHERE product_id = ?", (product_id,))
        s_max = cursor.fetchone()['max_date']
        
        # Find latest date in transactions or today
        dates = [d for d in [p_max, s_max, today_str] if d is not None]
        latest_tx_date = max(dates) if dates else today_str
        
        # Ensure ledger row up to latest tx date exists
        get_or_create_ledger_row(product_id, latest_tx_date)
        recalculate_ledger(product_id, latest_tx_date)
        
        cursor.execute("""
            SELECT closing_stock
            FROM stock_ledger
            WHERE product_id = ?
            ORDER BY date DESC
            LIMIT 1
        """, (product_id,))
        row = cursor.fetchone()
        return row['closing_stock'] if row else 0.0

def get_ledger_for_date(date_str):
    """Retrieve the stock ledger records for all active products on a specific date."""
    date_str = get_date_str(date_str)
    
    # Ensure ledger rows exist for all active products on this date
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM products WHERE is_active = 1")
        active_products = [r['id'] for r in cursor.fetchall()]
        
    for p_id in active_products:
        get_or_create_ledger_row(p_id, date_str)
        recalculate_ledger(p_id, date_str)
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                l.id,
                l.product_id,
                l.date,
                l.opening_stock,
                l.purchases_qty,
                l.sales_qty,
                l.closing_stock,
                l.is_confirmed,
                l.manual_override,
                l.override_note,
                p.name as product_name,
                p.brand as product_brand,
                p.type as product_type,
                p.thickness as product_thickness,
                p.size as product_size,
                p.unit as product_unit
            FROM stock_ledger l
            JOIN products p ON l.product_id = p.id
            WHERE l.date = ? AND p.is_active = 1
            ORDER BY p.name ASC, p.brand ASC
        """, (date_str,))
        return [dict(row) for row in cursor.fetchall()]
