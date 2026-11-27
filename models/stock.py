"""Stock engine.

Stock is never stored — it is always derived:

    stock(product, D) = base + purchases - sales      (for dates after the base, up to D)

where *base* is the latest physical count on or before D (``stock_counts``),
or the product's opening stock when there is none. A physical count pins the
closing stock of its day: transactions on or before that day no longer affect
later stock.

Closed days (``day_locks``) reject any change dated on that day.
"""
import datetime

from database.db import get_db

EPS = 1e-6


class LockedError(PermissionError):
    """The day is closed; reopen it before changing its entries."""


class StockError(ValueError):
    """The change would make stock negative."""


def iso(d):
    if isinstance(d, (datetime.date, datetime.datetime)):
        return d.strftime("%Y-%m-%d")
    return str(d)


def today():
    return datetime.date.today().isoformat()


def _prev_day(date_str):
    return (datetime.date.fromisoformat(date_str) - datetime.timedelta(days=1)).isoformat()


# ── day locks ───────────────────────────────────────────────────────────
def is_locked(date_str):
    with get_db() as conn:
        return conn.execute("SELECT 1 FROM day_locks WHERE date = ?", (iso(date_str),)).fetchone() is not None


def assert_unlocked(date_str):
    if is_locked(date_str):
        d = datetime.date.fromisoformat(iso(date_str)).strftime("%d-%m-%Y")
        raise LockedError(f"{d} is closed. Reopen the day in Stock Ledger to change its entries.")


def lock_day(date_str):
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO day_locks (date) VALUES (?)", (iso(date_str),))


def unlock_day(date_str):
    with get_db() as conn:
        conn.execute("DELETE FROM day_locks WHERE date = ?", (iso(date_str),))


def locked_days(date_from, date_to):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT date FROM day_locks WHERE date BETWEEN ? AND ?", (iso(date_from), iso(date_to))
        ).fetchall()
    return {r["date"] for r in rows}


# ── stock levels ────────────────────────────────────────────────────────
_STOCK_SQL = """
WITH base AS (
    SELECT p.id AS pid, p.opening_stock,
           (SELECT MAX(c.date) FROM stock_counts c
             WHERE c.product_id = p.id AND c.date <= :d) AS cdate
    FROM products p {where}
)
SELECT pid,
       COALESCE((SELECT c.counted_qty FROM stock_counts c
                  WHERE c.product_id = pid AND c.date = cdate), opening_stock)
     + COALESCE((SELECT SUM(x.qty) FROM purchases x
                  WHERE x.product_id = pid AND x.date <= :d
                    AND (cdate IS NULL OR x.date > cdate)), 0)
     - COALESCE((SELECT SUM(x.qty) FROM sales x
                  WHERE x.product_id = pid AND x.date <= :d
                    AND (cdate IS NULL OR x.date > cdate)), 0) AS stock
FROM base
"""


def stock_map(date_str=None):
    """{product_id: closing stock on the date} for every product (default: latest)."""
    d = iso(date_str) if date_str else "9999-12-31"
    with get_db() as conn:
        rows = conn.execute(_STOCK_SQL.format(where=""), {"d": d}).fetchall()
    return {r["pid"]: round(r["stock"], 4) for r in rows}


def stock_on(product_id, date_str=None):
    d = iso(date_str) if date_str else "9999-12-31"
    with get_db() as conn:
        row = conn.execute(
            _STOCK_SQL.format(where="WHERE p.id = :pid"), {"d": d, "pid": product_id}
        ).fetchone()
    return round(row["stock"], 4) if row else 0.0


def current_stock(product_id):
    return stock_on(product_id)


def min_balance_from(product_id, date_str):
    """Lowest closing stock from the date onward, up to the next physical count.

    This is how much can be removed on that date without any later day going
    negative — the number to check a sale (or a purchase removal) against.
    """
    d = iso(date_str)
    with get_db() as conn:
        nxt = conn.execute(
            "SELECT MIN(date) FROM stock_counts WHERE product_id = ? AND date >= ?", (product_id, d)
        ).fetchone()[0]
        if nxt == d:
            return float("inf")  # the day's closing is pinned by a count
        upper = nxt or "9999-12-31"
        rows = conn.execute(
            """
            SELECT date, SUM(delta) AS delta FROM (
                SELECT date, qty AS delta FROM purchases WHERE product_id = :p AND date > :d AND date < :u
                UNION ALL
                SELECT date, -qty FROM sales WHERE product_id = :p AND date > :d AND date < :u
            ) GROUP BY date ORDER BY date
            """,
            {"p": product_id, "d": d, "u": upper},
        ).fetchall()
    balance = lowest = stock_on(product_id, d)
    for r in rows:
        balance += r["delta"]
        lowest = min(lowest, balance)
    return round(lowest, 4)


def assert_can_remove(product_id, date_str, qty, product_name="this product"):
    """Raise StockError if taking ``qty`` out on the date would drive stock negative."""
    if qty <= EPS:
        return
    available = min_balance_from(product_id, date_str)
    if available + EPS < qty:
        on_day = stock_on(product_id, date_str)
        shown = max(available, 0)
        if on_day + EPS >= qty:
            raise StockError(
                f"Not enough stock for {product_name}: later entries already use it. "
                f"Only {shown:g} can be taken out on this date."
            )
        raise StockError(f"Not enough stock for {product_name}. Available: {shown:g}, needed: {qty:g}.")


# ── physical counts ─────────────────────────────────────────────────────
def set_count(product_id, date_str, counted_qty, note=None):
    """Record a physical stock count; it becomes the closing stock of that day."""
    d = iso(date_str)
    if counted_qty < 0:
        raise ValueError("Counted quantity cannot be negative.")
    with get_db() as conn:
        assert_unlocked(d)
        conn.execute(
            """
            INSERT INTO stock_counts (product_id, date, counted_qty, note) VALUES (?, ?, ?, ?)
            ON CONFLICT(product_id, date) DO UPDATE SET counted_qty = excluded.counted_qty, note = excluded.note
            """,
            (product_id, d, counted_qty, note),
        )
        _assert_future_non_negative(product_id, d)


def clear_count(product_id, date_str):
    d = iso(date_str)
    with get_db() as conn:
        assert_unlocked(d)
        conn.execute("DELETE FROM stock_counts WHERE product_id = ? AND date = ?", (product_id, d))
        _assert_future_non_negative(product_id, d)


def _assert_future_non_negative(product_id, date_str):
    """After changing a count, make sure the days that follow still add up."""
    nxt_day = (datetime.date.fromisoformat(date_str) + datetime.timedelta(days=1)).isoformat()
    if stock_on(product_id, date_str) < -EPS or min_balance_from(product_id, nxt_day) < -EPS:
        raise StockError("That count would make stock negative on a later day. Check later sales first.")


# ── ledger views ────────────────────────────────────────────────────────
def day_ledger(date_str, include_inactive=False):
    """One row per product for the day: opening, in, out, closing, count info."""
    d = iso(date_str)
    opening = stock_map(_prev_day(d))
    closing = stock_map(d)
    with get_db() as conn:
        products = conn.execute(
            "SELECT id, name, brand, type, thickness, size, unit, low_stock_threshold, is_active "
            "FROM products ORDER BY name COLLATE NOCASE, brand COLLATE NOCASE"
        ).fetchall()
        bought = dict(conn.execute(
            "SELECT product_id, SUM(qty) FROM purchases WHERE date = ? GROUP BY product_id", (d,)).fetchall())
        sold = dict(conn.execute(
            "SELECT product_id, SUM(qty) FROM sales WHERE date = ? GROUP BY product_id", (d,)).fetchall())
        counts = {r["product_id"]: r for r in conn.execute(
            "SELECT product_id, counted_qty, note FROM stock_counts WHERE date = ?", (d,)).fetchall()}
    locked = is_locked(d)
    out = []
    for p in products:
        pid = p["id"]
        p_in, p_out = bought.get(pid, 0.0), sold.get(pid, 0.0)
        moved = p_in or p_out or pid in counts
        if not p["is_active"] and not include_inactive and not moved:
            continue
        expected = opening.get(pid, 0.0) + p_in - p_out
        count = counts.get(pid)
        out.append({
            "product_id": pid, "product_name": p["name"], "product_brand": p["brand"],
            "product_type": p["type"], "product_thickness": p["thickness"], "product_size": p["size"],
            "product_unit": p["unit"], "low_stock_threshold": p["low_stock_threshold"],
            "opening_stock": opening.get(pid, 0.0), "purchases_qty": p_in, "sales_qty": p_out,
            "expected_closing": round(expected, 4), "closing_stock": closing.get(pid, 0.0),
            "is_counted": count is not None,
            "variance": round(count["counted_qty"] - expected, 4) if count else 0.0,
            "count_note": count["note"] if count else None,
            "is_locked": locked,
        })
    return out


def product_movements(product_id, date_from=None, date_to=None):
    """Chronological stock movements for one product with a running balance."""
    lo = iso(date_from) if date_from else "0000-01-01"
    hi = iso(date_to) if date_to else "9999-12-31"
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT x.date, 'purchase' AS kind, x.qty, x.unit_price, b.party_name AS party, b.bill_no, b.id AS bill_id,
                   NULL AS note, 1 AS ord, x.id
              FROM purchases x LEFT JOIN bills b ON b.id = x.bill_id
             WHERE x.product_id = :p AND x.date BETWEEN :lo AND :hi
            UNION ALL
            SELECT x.date, 'sale', x.qty, x.unit_price, b.party_name, b.bill_no, b.id, NULL, 2, x.id
              FROM sales x LEFT JOIN bills b ON b.id = x.bill_id
             WHERE x.product_id = :p AND x.date BETWEEN :lo AND :hi
            UNION ALL
            SELECT c.date, 'count', c.counted_qty, NULL, NULL, NULL, NULL, c.note, 3, c.id
              FROM stock_counts c
             WHERE c.product_id = :p AND c.date BETWEEN :lo AND :hi
            ORDER BY 1, 9, 10
            """,
            {"p": product_id, "lo": lo, "hi": hi},
        ).fetchall()
    balance = stock_on(product_id, _prev_day(lo)) if date_from else _opening(product_id)
    out = []
    for r in rows:
        row = dict(r)
        if r["kind"] == "purchase":
            balance += r["qty"]
        elif r["kind"] == "sale":
            balance -= r["qty"]
        else:
            row["variance"] = round(r["qty"] - balance, 4)
            balance = r["qty"]
        row["balance"] = round(balance, 4)
        out.append(row)
    return out


def _opening(product_id):
    with get_db() as conn:
        row = conn.execute("SELECT opening_stock FROM products WHERE id = ?", (product_id,)).fetchone()
    return row["opening_stock"] if row else 0.0
