"""Sale and purchase bills.

A bill has a header (``bills``), one or more lines (``sales`` / ``purchases``
rows) and zero or more payments. Totals are always derived from the lines:

    subtotal = sum(qty * unit_price)        total = subtotal - discount
    paid     = sum(payments)                due   = total - paid
    profit   = sum(qty * (unit_price - purchase_price_at_time)) - discount   (sales)

Every write is one transaction: stock rules, closed-day rules and payment
rules are checked inside it, and any failure rolls the whole bill back.
"""
import math

from database.db import get_db
from models import parties, stock
from models.stock import EPS, StockError, iso

_LINE_TABLE = {"sale": "sales", "purchase": "purchases"}
_PARTY_KIND = {"sale": "customer", "purchase": "supplier"}


def _money(x):
    return round(float(x or 0) + 0.0, 2)


def _clean_items(items):
    if not items:
        raise ValueError("Add at least one item.")
    cleaned = []
    for it in items:
        qty, price = float(it["qty"]), float(it["unit_price"])
        if not (math.isfinite(qty) and math.isfinite(price)):
            raise ValueError("Quantity and price must be numbers.")
        if qty <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if price < 0:
            raise ValueError("Price cannot be negative.")
        cleaned.append({"product_id": int(it["product_id"]), "qty": qty, "unit_price": price,
                        "cost": it.get("cost")})
    return cleaned


def _product_rows(conn, product_ids):
    marks = ",".join("?" * len(product_ids))
    rows = conn.execute(
        f"SELECT id, name, purchase_price FROM products WHERE id IN ({marks})", list(product_ids)
    ).fetchall()
    found = {r["id"]: r for r in rows}
    if len(found) != len(set(product_ids)):
        raise ValueError("One of the products no longer exists.")
    return found


def _paid(conn, bill_id):
    return _money(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE bill_id = ?", (bill_id,)).fetchone()[0])


def _set_paid(conn, bill_id, target, date_str, method):
    """Bring the bill's paid total to ``target`` by adding or trimming payments."""
    diff = _money(target - _paid(conn, bill_id))
    if diff > 0:
        conn.execute(
            "INSERT INTO payments (bill_id, date, amount, method) VALUES (?, ?, ?, ?)",
            (bill_id, date_str, diff, method or "Cash"),
        )
    elif diff < 0:
        excess = -diff
        for p in conn.execute(
            "SELECT id, amount FROM payments WHERE bill_id = ? ORDER BY date DESC, id DESC", (bill_id,)
        ).fetchall():
            if excess <= EPS:
                break
            if p["amount"] <= excess + EPS:
                conn.execute("DELETE FROM payments WHERE id = ?", (p["id"],))
                excess = _money(excess - p["amount"])
            else:
                conn.execute("UPDATE payments SET amount = ? WHERE id = ?", (_money(p["amount"] - excess), p["id"]))
                excess = 0


def save_bill(kind, date, items, party_name=None, party_phone=None, discount=0, paid=None,
              method="Cash", notes=None, bill_no=None, bill_id=None, update_cost=True):
    """Create a bill, or replace an existing one when ``bill_id`` is given.

    items: [{"product_id", "qty", "unit_price"}]. ``paid`` is the total amount
    settled so far; ``None`` means paid in full. Returns the bill id.
    """
    table = _LINE_TABLE[kind]
    date = iso(date)
    if date > stock.today():
        raise ValueError("The date cannot be in the future.")
    items = _clean_items(items)
    discount = _money(discount)
    subtotal = _money(sum(i["qty"] * i["unit_price"] for i in items))
    if discount < 0 or discount > subtotal + EPS:
        raise ValueError("Discount must be between zero and the bill amount.")
    total = _money(subtotal - discount)
    paid = total if paid is None else _money(paid)
    if paid < 0 or paid > total + EPS:
        raise ValueError("Amount paid must be between zero and the bill total.")
    party_name = (party_name or "").strip() or None
    if paid + EPS < total and not party_name:
        who = "customer" if kind == "sale" else "supplier"
        raise ValueError(f"Enter the {who} name to keep a balance due on this bill.")

    with get_db() as conn:
        stock.assert_unlocked(date)
        products = _product_rows(conn, {i["product_id"] for i in items})
        old_costs, touched = {}, {}
        if bill_id:
            head = conn.execute("SELECT kind, date FROM bills WHERE id = ?", (bill_id,)).fetchone()
            if not head or head["kind"] != kind:
                raise ValueError("Bill not found.")
            stock.assert_unlocked(head["date"])
            for r in conn.execute(f"SELECT * FROM {table} WHERE bill_id = ?", (bill_id,)).fetchall():
                touched[r["product_id"]] = min(touched.get(r["product_id"], head["date"]), head["date"])
                if kind == "sale":
                    old_costs[r["product_id"]] = r["purchase_price_at_time"]
            conn.execute(f"DELETE FROM {table} WHERE bill_id = ?", (bill_id,))

        if kind == "sale":
            wanted = {}
            for i in items:
                wanted[i["product_id"]] = wanted.get(i["product_id"], 0) + i["qty"]
            for pid, qty in wanted.items():
                stock.assert_can_remove(pid, date, qty, products[pid]["name"])

        party_id = parties.get_or_create(_PARTY_KIND[kind], party_name, party_phone) if party_name else None
        if bill_id:
            conn.execute(
                "UPDATE bills SET date = ?, party_id = ?, party_name = ?, discount = ?, notes = ?, "
                "bill_no = COALESCE(?, bill_no) WHERE id = ?",
                (date, party_id, party_name, discount, notes or None, bill_no or None, bill_id),
            )
        else:
            bill_id = conn.execute(
                "INSERT INTO bills (kind, bill_no, date, party_id, party_name, discount, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (kind, bill_no or None, date, party_id, party_name, discount, notes or None),
            ).lastrowid
            if not bill_no:
                prefix = "S" if kind == "sale" else "P"
                conn.execute("UPDATE bills SET bill_no = ? WHERE id = ?", (f"{prefix}-{bill_id:05d}", bill_id))

        for i in items:
            pid = i["product_id"]
            touched[pid] = min(touched.get(pid, date), date)
            if kind == "sale":
                cost = i["cost"]
                if cost is None:
                    cost = old_costs.get(pid, products[pid]["purchase_price"])
                conn.execute(
                    "INSERT INTO sales (bill_id, product_id, date, qty, unit_price, purchase_price_at_time, "
                    "customer_name, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (bill_id, pid, date, i["qty"], i["unit_price"], cost, party_name, notes or None),
                )
            else:
                conn.execute(
                    "INSERT INTO purchases (bill_id, product_id, date, qty, unit_price, supplier_name, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (bill_id, pid, date, i["qty"], i["unit_price"], party_name, notes or None),
                )

        if kind == "purchase":
            _assert_stock_ok(conn, touched)
            if update_cost:
                _refresh_costs(conn, [i["product_id"] for i in items])
        _set_paid(conn, bill_id, paid, date, method)
    return bill_id


def _assert_stock_ok(conn, touched):
    """After removing or moving purchase stock, no later day may go negative."""
    for pid, from_date in touched.items():
        if stock.min_balance_from(pid, from_date) < -EPS:
            name = conn.execute("SELECT name FROM products WHERE id = ?", (pid,)).fetchone()["name"]
            raise StockError(
                f"Cannot change this purchase: {name} from it has already been sold. "
                "Remove or reduce the later sales first."
            )


def _refresh_costs(conn, product_ids):
    """Product cost follows the most recent purchase price."""
    for pid in set(product_ids):
        row = conn.execute(
            "SELECT unit_price FROM purchases WHERE product_id = ? ORDER BY date DESC, id DESC LIMIT 1", (pid,)
        ).fetchone()
        if row and row["unit_price"] > 0:
            conn.execute("UPDATE products SET purchase_price = ? WHERE id = ?", (row["unit_price"], pid))


def delete_bill(bill_id):
    with get_db() as conn:
        head = conn.execute("SELECT kind, date FROM bills WHERE id = ?", (bill_id,)).fetchone()
        if not head:
            return False
        stock.assert_unlocked(head["date"])
        table = _LINE_TABLE[head["kind"]]
        touched = {r["product_id"]: head["date"] for r in conn.execute(
            f"SELECT product_id FROM {table} WHERE bill_id = ?", (bill_id,)).fetchall()}
        conn.execute(f"DELETE FROM {table} WHERE bill_id = ?", (bill_id,))
        conn.execute("DELETE FROM payments WHERE bill_id = ?", (bill_id,))
        conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))
        if head["kind"] == "purchase":
            _assert_stock_ok(conn, touched)
    return True


# ── payments ────────────────────────────────────────────────────────────
def bill_due(bill_id):
    bill = get_bill(bill_id)
    return bill["due"] if bill else 0.0


def add_payment(bill_id, amount, date=None, method="Cash", note=None):
    amount = _money(amount)
    if amount <= 0:
        raise ValueError("Payment must be greater than zero.")
    with get_db() as conn:
        due = bill_due(bill_id)
        if amount > due + EPS:
            raise ValueError(f"Payment is more than the balance due ({due:.2f}).")
        return conn.execute(
            "INSERT INTO payments (bill_id, date, amount, method, note) VALUES (?, ?, ?, ?, ?)",
            (bill_id, iso(date or stock.today()), amount, method or "Cash", note or None),
        ).lastrowid


def delete_payment(payment_id):
    with get_db() as conn:
        return conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,)).rowcount > 0


def settle_party(party_id, amount, date=None, method="Cash", note=None):
    """Apply a lump-sum payment to a party's unpaid bills, oldest first."""
    amount = _money(amount)
    if amount <= 0:
        raise ValueError("Payment must be greater than zero.")
    with get_db() as conn:
        open_bills = [b for b in list_bills(party_id=party_id, only_due=True)]
        open_bills.sort(key=lambda b: (b["date"], b["id"]))
        outstanding = _money(sum(b["due"] for b in open_bills))
        if amount > outstanding + EPS:
            raise ValueError(f"Payment is more than the total balance due ({outstanding:.2f}).")
        left = amount
        for b in open_bills:
            if left <= EPS:
                break
            part = min(left, b["due"])
            add_payment(b["id"], part, date, method, note)
            left = _money(left - part)
    return amount


# ── queries ─────────────────────────────────────────────────────────────
_BILL_SQL = """
SELECT b.id, b.kind, b.bill_no, b.date, b.party_id, b.party_name, b.discount, b.notes, b.created_at,
       pt.phone AS party_phone,
       COALESCE(l.items, 0) AS items, COALESCE(l.qty, 0) AS qty,
       ROUND(COALESCE(l.subtotal, 0), 2) AS subtotal,
       ROUND(COALESCE(l.subtotal, 0) - b.discount, 2) AS total,
       ROUND(COALESCE(l.cost, 0), 2) AS cost,
       ROUND(COALESCE(l.subtotal, 0) - b.discount - COALESCE(l.cost, 0), 2) AS profit,
       ROUND(COALESCE(p.paid, 0), 2) AS paid,
       ROUND(COALESCE(l.subtotal, 0) - b.discount - COALESCE(p.paid, 0), 2) AS due,
       l.summary
FROM bills b
LEFT JOIN parties pt ON pt.id = b.party_id
LEFT JOIN (
    SELECT bill_id, COUNT(*) AS items, SUM(qty) AS qty, SUM(qty * unit_price) AS subtotal,
           SUM(qty * cost) AS cost, GROUP_CONCAT(pname, ', ') AS summary
    FROM (
        SELECT s.bill_id, s.qty, s.unit_price, s.purchase_price_at_time AS cost, pr.name AS pname
          FROM sales s JOIN products pr ON pr.id = s.product_id
        UNION ALL
        SELECT u.bill_id, u.qty, u.unit_price, 0, pr.name
          FROM purchases u JOIN products pr ON pr.id = u.product_id
    ) GROUP BY bill_id
) l ON l.bill_id = b.id
LEFT JOIN (SELECT bill_id, SUM(amount) AS paid FROM payments GROUP BY bill_id) p ON p.bill_id = b.id
"""


def list_bills(kind=None, date_from=None, date_to=None, party_id=None, only_due=False, search=None):
    where, args = [], []
    if kind:
        where.append("b.kind = ?"); args.append(kind)
    if date_from:
        where.append("b.date >= ?"); args.append(iso(date_from))
    if date_to:
        where.append("b.date <= ?"); args.append(iso(date_to))
    if party_id:
        where.append("b.party_id = ?"); args.append(party_id)
    if only_due:
        where.append("ROUND(COALESCE(l.subtotal, 0) - b.discount - COALESCE(p.paid, 0), 2) > 0.004")
    if search:
        like = f"%{search.strip()}%"
        where.append("(b.party_name LIKE ? OR b.bill_no LIKE ? OR l.summary LIKE ? OR b.notes LIKE ?)")
        args += [like] * 4
    sql = _BILL_SQL + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY b.date DESC, b.id DESC"
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def get_bill(bill_id):
    with get_db() as conn:
        head = conn.execute(_BILL_SQL + " WHERE b.id = ?", (bill_id,)).fetchone()
        if not head:
            return None
        bill = dict(head)
        table = _LINE_TABLE[bill["kind"]]
        cost_col = "x.purchase_price_at_time" if bill["kind"] == "sale" else "0"
        bill["lines"] = [dict(r) for r in conn.execute(
            f"""
            SELECT x.id, x.product_id, x.qty, x.unit_price, {cost_col} AS cost,
                   ROUND(x.qty * x.unit_price, 2) AS amount,
                   pr.name AS product_name, pr.brand AS product_brand, pr.type AS product_type,
                   pr.thickness AS product_thickness, pr.size AS product_size, pr.unit AS product_unit
            FROM {table} x JOIN products pr ON pr.id = x.product_id
            WHERE x.bill_id = ? ORDER BY x.id
            """, (bill_id,)).fetchall()]
        bill["payments"] = [dict(r) for r in conn.execute(
            "SELECT id, date, amount, method, note FROM payments WHERE bill_id = ? ORDER BY date, id",
            (bill_id,)).fetchall()]
        bill["locked"] = stock.is_locked(bill["date"])
    return bill


def list_lines(kind, date_from=None, date_to=None):
    """Flat line items (one row per product on a bill) for reports and exports."""
    table = _LINE_TABLE[kind]
    cost_col = "x.purchase_price_at_time" if kind == "sale" else "0"
    lo = iso(date_from) if date_from else "0000-01-01"
    hi = iso(date_to) if date_to else "9999-12-31"
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            f"""
            SELECT x.id, x.bill_id, b.bill_no, x.date, x.product_id, x.qty, x.unit_price, {cost_col} AS cost,
                   ROUND(x.qty * x.unit_price, 2) AS amount,
                   ROUND(x.qty * {cost_col}, 2) AS cost_amount,
                   ROUND(x.qty * (x.unit_price - {cost_col}), 2) AS margin,
                   b.party_name, b.notes,
                   pr.name AS product_name, pr.brand AS product_brand, pr.type AS product_type,
                   pr.thickness AS product_thickness, pr.size AS product_size, pr.unit AS product_unit
            FROM {table} x
            JOIN products pr ON pr.id = x.product_id
            LEFT JOIN bills b ON b.id = x.bill_id
            WHERE x.date BETWEEN ? AND ?
            ORDER BY x.date DESC, x.id DESC
            """, (lo, hi)).fetchall()]


def last_price(kind, product_id, party_name=None):
    """Most recent unit price for the product (for this party if they have one)."""
    table = _LINE_TABLE[kind]
    with get_db() as conn:
        if party_name:
            row = conn.execute(
                f"SELECT x.unit_price FROM {table} x JOIN bills b ON b.id = x.bill_id "
                "WHERE x.product_id = ? AND b.party_name = ? COLLATE NOCASE ORDER BY x.date DESC, x.id DESC LIMIT 1",
                (product_id, party_name.strip())).fetchone()
            if row:
                return row[0]
        row = conn.execute(
            f"SELECT unit_price FROM {table} WHERE product_id = ? ORDER BY date DESC, id DESC LIMIT 1",
            (product_id,)).fetchone()
    return row[0] if row else None
