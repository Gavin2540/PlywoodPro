"""Read-only business numbers for the dashboard and reports. Nothing here writes."""
import datetime

from database.db import get_db
from models import product as product_model
from models.stock import iso


def _range(date_from, date_to):
    return (iso(date_from) if date_from else "0000-01-01", iso(date_to) if date_to else "9999-12-31")


def summary(date_from=None, date_to=None):
    """Headline numbers for a period.

    revenue      = sale lines at selling price
    cost         = same lines at the cost captured when sold
    gross_profit = revenue - cost - discounts
    net_profit   = gross_profit - expenses
    """
    lo, hi = _range(date_from, date_to)
    with get_db() as conn:
        s = conn.execute(
            "SELECT COALESCE(SUM(qty * unit_price), 0) AS revenue, "
            "COALESCE(SUM(qty * purchase_price_at_time), 0) AS cost, "
            "COALESCE(SUM(qty), 0) AS qty, COUNT(*) AS lines FROM sales WHERE date BETWEEN ? AND ?",
            (lo, hi)).fetchone()
        b = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(discount), 0) AS discount FROM bills "
            "WHERE kind = 'sale' AND date BETWEEN ? AND ?", (lo, hi)).fetchone()
        p = conn.execute(
            "SELECT COALESCE(SUM(qty * unit_price), 0) AS amount, COALESCE(SUM(qty), 0) AS qty "
            "FROM purchases WHERE date BETWEEN ? AND ?", (lo, hi)).fetchone()
        pd = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(discount), 0) AS discount FROM bills "
            "WHERE kind = 'purchase' AND date BETWEEN ? AND ?", (lo, hi)).fetchone()
        e = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date BETWEEN ? AND ?", (lo, hi)).fetchone()[0]
        pay = dict(conn.execute(
            "SELECT b.kind, COALESCE(SUM(p.amount), 0) FROM payments p JOIN bills b ON b.id = p.bill_id "
            "WHERE p.date BETWEEN ? AND ? GROUP BY b.kind", (lo, hi)).fetchall())
    revenue = round(s["revenue"] - b["discount"], 2)
    gross = round(s["revenue"] - s["cost"] - b["discount"], 2)
    return {
        "revenue": revenue,
        "cost": round(s["cost"], 2),
        "discount": round(b["discount"], 2),
        "gross_profit": gross,
        "margin_pct": round(gross / revenue * 100, 1) if revenue else 0.0,
        "expenses": round(e, 2),
        "net_profit": round(gross - e, 2),
        "qty_sold": s["qty"],
        "sale_bills": b["n"],
        "purchases": round(p["amount"] - pd["discount"], 2),
        "qty_purchased": p["qty"],
        "purchase_bills": pd["n"],
        "collected": round(pay.get("sale", 0), 2),
        "paid_out": round(pay.get("purchase", 0), 2),
    }


def compare(date_from, date_to):
    """Summary for a period plus the same-length period just before it."""
    a, b = datetime.date.fromisoformat(iso(date_from)), datetime.date.fromisoformat(iso(date_to))
    span = (b - a).days + 1
    prev_to = a - datetime.timedelta(days=1)
    prev_from = prev_to - datetime.timedelta(days=span - 1)
    return summary(a, b), summary(prev_from, prev_to)


def daily_series(date_from, date_to):
    """One entry per calendar day: revenue, gross profit, expenses, net profit."""
    lo, hi = _range(date_from, date_to)
    with get_db() as conn:
        sales = {r["date"]: r for r in conn.execute(
            "SELECT date, SUM(qty * unit_price) AS revenue, SUM(qty * purchase_price_at_time) AS cost "
            "FROM sales WHERE date BETWEEN ? AND ? GROUP BY date", (lo, hi))}
        disc = dict(conn.execute(
            "SELECT date, SUM(discount) FROM bills WHERE kind = 'sale' AND date BETWEEN ? AND ? GROUP BY date",
            (lo, hi)).fetchall())
        exp = dict(conn.execute(
            "SELECT date, SUM(amount) FROM expenses WHERE date BETWEEN ? AND ? GROUP BY date", (lo, hi)).fetchall())
    out = []
    day, end = datetime.date.fromisoformat(lo), datetime.date.fromisoformat(hi)
    while day <= end:
        k = day.isoformat()
        s = sales.get(k)
        revenue = (s["revenue"] if s else 0) - (disc.get(k) or 0)
        gross = revenue - (s["cost"] if s else 0)
        expenses = exp.get(k) or 0
        out.append({"date": k, "revenue": round(revenue, 2), "gross_profit": round(gross, 2),
                    "expenses": round(expenses, 2), "net_profit": round(gross - expenses, 2)})
        day += datetime.timedelta(days=1)
    return out


def product_performance(date_from=None, date_to=None):
    """Per-product sales for a period, best revenue first."""
    lo, hi = _range(date_from, date_to)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT pr.id AS product_id, pr.name AS product_name, pr.brand AS product_brand,
                   pr.type AS product_type, pr.thickness AS product_thickness, pr.size AS product_size,
                   pr.unit AS product_unit,
                   SUM(s.qty) AS qty, ROUND(SUM(s.qty * s.unit_price), 2) AS revenue,
                   ROUND(SUM(s.qty * s.purchase_price_at_time), 2) AS cost,
                   ROUND(SUM(s.qty * (s.unit_price - s.purchase_price_at_time)), 2) AS profit
            FROM sales s JOIN products pr ON pr.id = s.product_id
            WHERE s.date BETWEEN ? AND ?
            GROUP BY pr.id ORDER BY revenue DESC
            """, (lo, hi)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["margin_pct"] = round(d["profit"] / d["revenue"] * 100, 1) if d["revenue"] else 0.0
        out.append(d)
    return out


def expense_breakdown(date_from=None, date_to=None):
    lo, hi = _range(date_from, date_to)
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT category, ROUND(SUM(amount), 2) AS amount, COUNT(*) AS entries FROM expenses "
            "WHERE date BETWEEN ? AND ? GROUP BY category ORDER BY amount DESC", (lo, hi))]


def stock_overview():
    """Totals for active products: value at cost, value at selling price, alerts."""
    products = product_model.list_products()
    low = [p for p in products if p["status"] == "low"]
    out = [p for p in products if p["status"] == "out"]
    return {
        "products": len(products),
        "stock_value": round(sum(p["stock_value"] for p in products), 2),
        "retail_value": round(sum(p["stock"] * p["selling_price"] for p in products), 2),
        "low": low,
        "out": out,
        "items": products,
    }


def outstanding():
    """Money owed by customers (receivable) and to suppliers (payable)."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT b.kind,
                   SUM(COALESCE((SELECT SUM(qty * unit_price) FROM sales WHERE bill_id = b.id), 0)
                     + COALESCE((SELECT SUM(qty * unit_price) FROM purchases WHERE bill_id = b.id), 0)
                     - b.discount
                     - COALESCE((SELECT SUM(amount) FROM payments WHERE bill_id = b.id), 0)) AS due
            FROM bills b GROUP BY b.kind
            """).fetchall()
    due = {r["kind"]: round(r["due"] or 0, 2) for r in rows}
    return {"receivable": due.get("sale", 0.0), "payable": due.get("purchase", 0.0)}


def first_activity_date():
    """Earliest date with any record, or None for an empty book."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT MIN(d) FROM (SELECT MIN(date) AS d FROM bills UNION ALL SELECT MIN(date) FROM expenses)"
        ).fetchone()
    return row[0]
