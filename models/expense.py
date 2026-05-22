from database.db import get_db
import models.ledger as ledger

def insert_expense(date_str, category, amount, note):
    """Inserts a daily expense record."""
    date_str = ledger.get_date_str(date_str)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expenses (date, category, amount, note)
            VALUES (?, ?, ?, ?)
        """, (date_str, category, amount, note))
        expense_id = cursor.lastrowid
        conn.commit()
    return expense_id

def delete_expense(expense_id):
    """Deletes an expense record by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_expenses_by_date(date_str):
    """Retrieve all expenses logged on a specific date."""
    date_str = ledger.get_date_str(date_str)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, date, category, amount, note, created_at
            FROM expenses
            WHERE date = ?
            ORDER BY id DESC
        """, (date_str,))
        return [dict(row) for row in cursor.fetchall()]

def get_all_expenses():
    """Retrieve all logged expenses in reverse chronological order."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, date, category, amount, note, created_at
            FROM expenses
            ORDER BY date DESC, id DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

def get_total_expenses_by_date(date_str):
    """Gets the sum of all expenses recorded on a given date."""
    date_str = ledger.get_date_str(date_str)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) as total FROM expenses WHERE date = ?", (date_str,))
        row = cursor.fetchone()
        return row['total'] if row['total'] is not None else 0.0
