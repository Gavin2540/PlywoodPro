"""Customers and suppliers, with their running balances."""
from database.db import get_db


def get_or_create(kind, name, phone=None):
    name = (name or "").strip()
    if not name:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, phone FROM parties WHERE kind = ? AND name = ? COLLATE NOCASE", (kind, name)
        ).fetchone()
        if row:
            if phone and phone.strip() and phone.strip() != (row["phone"] or ""):
                conn.execute("UPDATE parties SET phone = ?, is_active = 1 WHERE id = ?", (phone.strip(), row["id"]))
            return row["id"]
        return conn.execute(
            "INSERT INTO parties (kind, name, phone) VALUES (?, ?, ?)", (kind, name, (phone or "").strip() or None)
        ).lastrowid


def save_party(kind, name, phone=None, address=None, notes=None, party_id=None):
    name = (name or "").strip()
    if not name:
        raise ValueError("Name is required.")
    with get_db() as conn:
        clash = conn.execute(
            "SELECT id FROM parties WHERE kind = ? AND name = ? COLLATE NOCASE AND id != ?",
            (kind, name, party_id or 0),
        ).fetchone()
        if clash:
            raise ValueError(f"A {kind} named '{name}' already exists.")
        vals = (name, (phone or "").strip() or None, (address or "").strip() or None, (notes or "").strip() or None)
        if party_id:
            conn.execute("UPDATE parties SET name = ?, phone = ?, address = ?, notes = ? WHERE id = ?",
                         vals + (party_id,))
            conn.execute("UPDATE bills SET party_name = ? WHERE party_id = ?", (name, party_id))
            return party_id
        return conn.execute(
            "INSERT INTO parties (kind, name, phone, address, notes) VALUES (?, ?, ?, ?, ?)", (kind,) + vals
        ).lastrowid


def get_party(party_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM parties WHERE id = ?", (party_id,)).fetchone()
    return dict(row) if row else None


def delete_party(party_id):
    """Remove a party with no bills; otherwise just hide it."""
    with get_db() as conn:
        used = conn.execute("SELECT 1 FROM bills WHERE party_id = ? LIMIT 1", (party_id,)).fetchone()
        if used:
            conn.execute("UPDATE parties SET is_active = 0 WHERE id = ?", (party_id,))
        else:
            conn.execute("DELETE FROM parties WHERE id = ?", (party_id,))


def list_parties(kind, search=None, include_inactive=False):
    """Parties with bill count, total billed, total paid and balance due."""
    where, args = ["pt.kind = ?"], [kind]
    if not include_inactive:
        where.append("pt.is_active = 1")
    if search:
        where.append("(pt.name LIKE ? OR pt.phone LIKE ?)")
        args += [f"%{search.strip()}%"] * 2
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT pt.id, pt.kind, pt.name, pt.phone, pt.address, pt.notes, pt.is_active,
                   COUNT(b.id) AS bills,
                   ROUND(COALESCE(SUM(b.total), 0), 2) AS billed,
                   ROUND(COALESCE(SUM(b.paid), 0), 2) AS paid,
                   ROUND(COALESCE(SUM(b.total - b.paid), 0), 2) AS due,
                   MAX(b.date) AS last_date
            FROM parties pt
            LEFT JOIN (
                SELECT b.id, b.party_id, b.date,
                       COALESCE((SELECT SUM(qty * unit_price) FROM sales WHERE bill_id = b.id), 0)
                     + COALESCE((SELECT SUM(qty * unit_price) FROM purchases WHERE bill_id = b.id), 0)
                     - b.discount AS total,
                       COALESCE((SELECT SUM(amount) FROM payments WHERE bill_id = b.id), 0) AS paid
                FROM bills b
            ) b ON b.party_id = pt.id
            WHERE {' AND '.join(where)}
            GROUP BY pt.id
            ORDER BY pt.name COLLATE NOCASE
            """, args).fetchall()
    return [dict(r) for r in rows]


def names(kind):
    with get_db() as conn:
        return [r[0] for r in conn.execute(
            "SELECT name FROM parties WHERE kind = ? AND is_active = 1 ORDER BY name COLLATE NOCASE", (kind,))]


def find_by_name(kind, name):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM parties WHERE kind = ? AND name = ? COLLATE NOCASE", (kind, (name or "").strip())
        ).fetchone()
    return dict(row) if row else None
