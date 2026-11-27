"""Page registry: (key, sidebar label, icon, module, class). Order = sidebar order.
A ``None`` entry is a gap between sidebar groups."""

PAGES = [
    ("dashboard", "Dashboard", "dashboard", "ui.pages.dashboard", "DashboardPage"),
    None,
    ("sales", "Sales", "sale", "ui.pages.bills", "SalesPage"),
    ("purchases", "Purchases", "purchase", "ui.pages.bills", "PurchasesPage"),
    ("expenses", "Expenses", "expense", "ui.pages.expenses", "ExpensesPage"),
    None,
    ("products", "Products", "products", "ui.pages.products", "ProductsPage"),
    ("ledger", "Stock Ledger", "ledger", "ui.pages.ledger", "LedgerPage"),
    ("parties", "Customers & Suppliers", "people", "ui.pages.parties", "PartiesPage"),
    None,
    ("reports", "Reports", "report", "ui.pages.reports", "ReportsPage"),
    ("settings", "Settings", "settings", "ui.pages.settings", "SettingsPage"),
]
