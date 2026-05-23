import os
import sqlite3

class DatabaseManager:
    _instance = None
    _db_path = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DatabaseManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    @classmethod
    def initialize(cls, db_path=None):
        """Initialize the database path and run schema creation if needed."""
        if db_path is None:
            import sys
            if getattr(sys, 'frozen', False):
                # Running as PyInstaller .exe — store DB next to the .exe
                base_dir = os.path.dirname(sys.executable)
            else:
                # Dev mode — store DB in project root
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            cls._db_path = os.path.join(data_dir, "plywoodpro.db")
        else:
            cls._db_path = db_path
            # Make sure parent directory exists
            parent_dir = os.path.dirname(db_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

        # Check if database is empty/new and create tables
        cls._create_all_tables()

    @classmethod
    def get_connection(cls):
        """Returns a connection to the SQLite database with row factory and foreign keys enabled."""
        if not cls._db_path:
            cls.initialize()
        
        conn = sqlite3.connect(cls._db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign key support in SQLite
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @classmethod
    def _create_all_tables(cls):
        """Reads schema.sql and runs it against the database to create all tables."""
        conn = sqlite3.connect(cls._db_path)
        cursor = conn.cursor()
        
        # Check if the products table exists to see if we need to load schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products';")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
            if os.path.exists(schema_path):
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                cursor.executescript(schema_sql)
                conn.commit()
            else:
                raise FileNotFoundError(f"Schema file not found at: {schema_path}")
        
        conn.close()

import contextlib

# Helper connection function for easy context-management
@contextlib.contextmanager
def get_db():
    """Returns a SQLite connection to use in a context manager.
    Ensures that transactions are committed and connection is closed.
    Example:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
    """
    conn = DatabaseManager.get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
