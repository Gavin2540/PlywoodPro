"""Schema migrations. MIGRATIONS[i] upgrades schema version i+1 -> i+2.

Each runs inside one transaction; never edit a shipped migration, add a new one.
"""


def _run(conn, script):
    """Run several statements without executescript's implicit COMMIT."""
    for statement in script.split(";"):
        if statement.strip():
            conn.execute(statement)


def _columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _v2_bills_parties_computed_stock(conn):
    """v1 -> v2.

    * Stock is now computed from transactions. The old per-day ``stock_ledger``
      rows are reduced to what was real user input: physical counts
      (``stock_counts``) and closed days (``day_locks``).
    * Sales and purchases become lines of a ``bills`` row (multi-item bill,
      discount, payments, dues).
    * Customers / suppliers (``parties``), ``payments`` and ``settings`` are new.
    """
    _run(conn,
        """
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL CHECK (kind IN ('customer', 'supplier')),
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            notes TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_parties_kind_name
            ON parties(kind, name COLLATE NOCASE);

        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL CHECK (kind IN ('sale', 'purchase')),
            bill_no TEXT,
            date TEXT NOT NULL,
            party_id INTEGER REFERENCES parties(id) ON DELETE RESTRICT,
            party_name TEXT,
            discount REAL NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_bills_kind_date ON bills(kind, date);
        CREATE INDEX IF NOT EXISTS idx_bills_party ON bills(party_id);

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            method TEXT DEFAULT 'Cash',
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_payments_bill ON payments(bill_id);
        CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(date);

        CREATE TABLE IF NOT EXISTS stock_counts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
            date TEXT NOT NULL,
            counted_qty REAL NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (product_id, date)
        );

        CREATE TABLE IF NOT EXISTS day_locks (
            date TEXT PRIMARY KEY,
            locked_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )

    if "opening_stock" not in _columns(conn, "products"):
        conn.execute("ALTER TABLE products ADD COLUMN opening_stock REAL NOT NULL DEFAULT 0")
    for table in ("sales", "purchases"):
        if "bill_id" not in _columns(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN bill_id INTEGER REFERENCES bills(id)")

    # Physical counts and closed days carried over from the v1 ledger.
    conn.execute(
        """
        INSERT OR IGNORE INTO stock_counts (product_id, date, counted_qty, note)
        SELECT product_id, date, closing_stock, override_note
        FROM stock_ledger WHERE manual_override = 1
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO day_locks (date) "
        "SELECT DISTINCT date FROM stock_ledger WHERE is_confirmed = 1"
    )

    # Wrap every legacy transaction row in a bill. Rows saved together in v1
    # (same date, same party, same second) become one multi-item bill.
    for table, kind, party_col, party_kind in (
        ("sales", "sale", "customer_name", "customer"),
        ("purchases", "purchase", "supplier_name", "supplier"),
    ):
        rows = conn.execute(
            f"SELECT id, date, {party_col} AS party, notes, created_at, qty, unit_price "
            f"FROM {table} WHERE bill_id IS NULL ORDER BY id"
        ).fetchall()
        groups = {}
        for r in rows:
            party = (r["party"] or "").strip()
            groups.setdefault((r["date"], party.lower(), r["created_at"]), []).append(r)
        for (_date, _party_key, _created), lines in groups.items():
            first = lines[0]
            party = (first["party"] or "").strip()
            party_id = None
            if party:
                found = conn.execute(
                    "SELECT id FROM parties WHERE kind = ? AND name = ? COLLATE NOCASE",
                    (party_kind, party),
                ).fetchone()
                party_id = found[0] if found else conn.execute(
                    "INSERT INTO parties (kind, name) VALUES (?, ?)", (party_kind, party)
                ).lastrowid
            notes = "; ".join(dict.fromkeys(l["notes"] for l in lines if l["notes"])) or None
            cur = conn.execute(
                "INSERT INTO bills (kind, date, party_id, party_name, notes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (kind, first["date"], party_id, party or None, notes, first["created_at"]),
            )
            bill_id = cur.lastrowid
            prefix = "S" if kind == "sale" else "P"
            conn.execute("UPDATE bills SET bill_no = ? WHERE id = ?", (f"{prefix}-{bill_id:05d}", bill_id))
            conn.executemany(
                f"UPDATE {table} SET bill_id = ? WHERE id = ?", [(bill_id, l["id"]) for l in lines]
            )
            # v1 had no credit tracking: treat old bills as settled in full.
            total = round(sum(l["qty"] * l["unit_price"] for l in lines), 2)
            if total > 0:
                conn.execute(
                    "INSERT INTO payments (bill_id, date, amount, method, note) VALUES (?, ?, ?, 'Cash', ?)",
                    (bill_id, first["date"], total, "Imported from v1"),
                )

    _run(conn,
        """
        CREATE INDEX IF NOT EXISTS idx_sales_product_date ON sales(product_id, date);
        CREATE INDEX IF NOT EXISTS idx_purchases_product_date ON purchases(product_id, date);
        CREATE INDEX IF NOT EXISTS idx_sales_bill ON sales(bill_id);
        CREATE INDEX IF NOT EXISTS idx_purchases_bill ON purchases(bill_id);
        """
    )


MIGRATIONS = [_v2_bills_parties_computed_stock]
