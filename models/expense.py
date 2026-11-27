"""Day-to-day shop expenses."""
from database.db import get_db
from models.stock import iso

DEFAULT_CATEGORIES = ["Transport", "Labour", "Loading", "Rent", "Electricity", "Salary", "Miscellaneous"]


def _validate(category, amount):
    if not (category or "").strip():
        raise ValueError("Choose a category.")
    if float(amount) <= 0:
        raise ValueError("Amount must be greater than zero.")


def insert_expense(date_str, category, amount, note=None):
    _validate(category, amount)
    with get_db() as conn:
        return conn.execute(
            "INSERT INTO expenses (date, category, amount, note) VALUES (?, ?, ?, ?)",
            (iso(date_str), category.strip(), round(float(amount), 2), (note or "").strip() or None),
        ).lastrowid


def update_expense(expense_id, date_str, category, amount, note=None):
    _validate(category, amount)
    with get_db() as conn:
        return conn.execute(
            "UPDATE expenses SET date = ?, category = ?, amount = ?, note = ? WHERE id = ?",
            (iso(date_str), category.strip(), round(float(amount), 2), (note or "").strip() or None, expense_id),
        ).rowcount > 0


def delete_expense(expense_id):
    with get_db() as conn:
        return conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,)).rowcount > 0


def list_expenses(date_from=None, date_to=None, category=None, search=None):
    where, args = [], []
    if date_from:
        where.append("date >= ?"); args.append(iso(date_from))
    if date_to:
        where.append("date <= ?"); args.append(iso(date_to))
    if category:
        where.append("category = ?"); args.append(category)
    if search:
        where.append("(note LIKE ? OR category LIKE ?)"); args += [f"%{search.strip()}%"] * 2
    sql = "SELECT id, date, category, amount, note, created_at FROM expenses"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql + " ORDER BY date DESC, id DESC", args)]


def get_expenses_by_date(date_str):
    return list_expenses(date_str, date_str)


def get_all_expenses():
    return list_expenses()


def total(date_from=None, date_to=None):
    return round(sum(e["amount"] for e in list_expenses(date_from, date_to)), 2)


def get_total_expenses_by_date(date_str):
    return total(date_str, date_str)


def categories():
    """Default categories plus any the shop has used."""
    with get_db() as conn:
        used = [r[0] for r in conn.execute("SELECT DISTINCT category FROM expenses ORDER BY category")]
    return DEFAULT_CATEGORIES + [c for c in used if c not in DEFAULT_CATEGORIES]
