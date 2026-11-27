"""Key-value app settings stored in the database (so they travel with backups)."""
from database.db import get_db

DEFAULTS = {
    "shop_name": "",
    "shop_address": "",
    "shop_phone": "",
    "shop_gstin": "",
    "invoice_footer": "Thank you for your business!",
    "theme": "dark",
    "auto_backup": "1",
    "backup_keep": "14",
}


def get(key, default=None):
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is not None and row["value"] is not None:
        return row["value"]
    return DEFAULTS.get(key, default) if default is None else default


def set(key, value):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, None if value is None else str(value)),
        )


def get_all():
    values = dict(DEFAULTS)
    with get_db() as conn:
        values.update({r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")})
    return values


def set_many(values):
    with get_db():
        for k, v in values.items():
            set(k, v)
