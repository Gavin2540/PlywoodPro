"""SQLite access for PlywoodPro.

One shared connection (the UI is single-threaded), re-entrant transactions,
and versioned migrations tracked in ``PRAGMA user_version``.

    with get_db() as conn:
        conn.execute(...)

Nested ``get_db()`` blocks join the outer transaction: everything commits
when the outermost block exits cleanly, or rolls back as a whole on error.
"""
import contextlib
import datetime
import os
import shutil
import sqlite3
import sys

from database.migrations import MIGRATIONS

SCHEMA_VERSION = len(MIGRATIONS) + 1  # v1 = schema.sql, then one per migration


def _resource_dir():
    """Folder holding bundled read-only files (schema.sql)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "database")
    return os.path.dirname(os.path.abspath(__file__))


def app_dir():
    """Folder where user data lives: next to the .exe, or the project root in dev."""
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":  # a .app bundle must not write inside itself
            return os.path.expanduser("~/Library/Application Support/PlywoodPro")
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_db_path():
    override = os.environ.get("PLYWOODPRO_DB")
    if override:
        return override
    return os.path.join(app_dir(), "data", "plywoodpro.db")


class DatabaseManager:
    _db_path = None
    _conn = None
    _depth = 0

    @classmethod
    def initialize(cls, db_path=None):
        """Open (creating if needed) the database and bring it to the current schema."""
        cls.close()
        cls._db_path = db_path or default_db_path()
        if cls._db_path != ":memory:":
            parent = os.path.dirname(cls._db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        cls._migrate()

    @classmethod
    def db_path(cls):
        if not cls._db_path:
            cls.initialize()
        return cls._db_path

    @classmethod
    def get_connection(cls):
        if not cls._db_path:
            cls.initialize()
        if cls._conn is None:
            conn = sqlite3.connect(cls._db_path, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            if cls._db_path != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
            cls._conn = conn
        return cls._conn

    @classmethod
    def close(cls):
        if cls._conn is not None:
            try:
                cls._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
            cls._conn.close()
        cls._conn = None
        cls._depth = 0

    # ── migrations ──────────────────────────────────────────────────────
    @classmethod
    def _migrate(cls):
        conn = cls.get_connection()
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        has_tables = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='products'"
        ).fetchone()

        if version == 0 and not has_tables:
            with open(os.path.join(_resource_dir(), "schema.sql"), encoding="utf-8") as f:
                conn.executescript(f.read())
            version = 1
            conn.execute("PRAGMA user_version = 1")
        elif version == 0:
            version = 1  # a v1.x database: tables exist but were never versioned

        if version > SCHEMA_VERSION:
            raise RuntimeError(
                "This data file was created by a newer version of Plywood Pro. "
                "Please update the application."
            )
        if version < SCHEMA_VERSION and has_tables:
            cls._backup_before_migration(version)

        while version < SCHEMA_VERSION:
            migration = MIGRATIONS[version - 1]
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("BEGIN")
            try:
                migration(conn)
                conn.execute(f"PRAGMA user_version = {version + 1}")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                conn.execute("PRAGMA foreign_keys = ON")
            version += 1

    @classmethod
    def _backup_before_migration(cls, version):
        if cls._db_path == ":memory:" or not os.path.exists(cls._db_path):
            return
        cls._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        backup_dir = os.path.join(os.path.dirname(cls._db_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(
            cls._db_path,
            os.path.join(backup_dir, f"before-upgrade-schema{version}-{stamp}.db"),
        )


@contextlib.contextmanager
def get_db():
    """Re-entrant transaction scope on the shared connection."""
    conn = DatabaseManager.get_connection()
    outermost = DatabaseManager._depth == 0
    if outermost:
        conn.execute("BEGIN")
    DatabaseManager._depth += 1
    try:
        yield conn
    except BaseException:
        DatabaseManager._depth -= 1
        if outermost:
            conn.execute("ROLLBACK")
        raise
    else:
        DatabaseManager._depth -= 1
        if outermost:
            conn.execute("COMMIT")
