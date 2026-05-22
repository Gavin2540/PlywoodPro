-- PlywoodPro SQLite Database Schema

PRAGMA foreign_keys = ON;

-- 1. Products Table
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT,
    type TEXT, -- MR, BWR, BWP, Commercial
    thickness TEXT, -- 4mm, 6mm, 9mm, 12mm, 16mm, 18mm, 25mm etc.
    size TEXT, -- 8x4, 7x4, 6x4, custom etc.
    purchase_price REAL NOT NULL DEFAULT 0.0,
    selling_price REAL NOT NULL DEFAULT 0.0,
    unit TEXT DEFAULT 'sheets', -- sheets, sqft
    low_stock_threshold INTEGER DEFAULT 10,
    is_active INTEGER DEFAULT 1, -- Soft delete: 1 = active, 0 = deleted
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 2. Purchases Table
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    date TEXT NOT NULL, -- Format: YYYY-MM-DD
    qty REAL NOT NULL,
    unit_price REAL NOT NULL,
    supplier_name TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

-- 3. Sales Table
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    date TEXT NOT NULL, -- Format: YYYY-MM-DD
    qty REAL NOT NULL,
    unit_price REAL NOT NULL,
    purchase_price_at_time REAL NOT NULL, -- Snapshot of purchase price at time of sale for accurate margins
    customer_name TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

-- 4. Expenses Table
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL, -- Format: YYYY-MM-DD
    category TEXT NOT NULL, -- Transport, Labour, Loading, Rent, Miscellaneous
    amount REAL NOT NULL,
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 5. Stock Ledger Table
CREATE TABLE IF NOT EXISTS stock_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    date TEXT NOT NULL, -- Format: YYYY-MM-DD
    opening_stock REAL NOT NULL DEFAULT 0.0,
    purchases_qty REAL NOT NULL DEFAULT 0.0,
    sales_qty REAL NOT NULL DEFAULT 0.0,
    closing_stock REAL NOT NULL DEFAULT 0.0,
    is_confirmed INTEGER DEFAULT 0, -- 1 = confirmed/locked, 0 = unconfirmed
    manual_override INTEGER DEFAULT 0, -- 1 = physical stock count corrected, 0 = calculated
    override_note TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    UNIQUE(product_id, date)
);

-- Performance indices
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(date);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
CREATE INDEX IF NOT EXISTS idx_ledger_date ON stock_ledger(date);
CREATE INDEX IF NOT EXISTS idx_ledger_product_date ON stock_ledger(product_id, date);
