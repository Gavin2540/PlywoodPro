# Plywood Pro v2 — UI developer guide

Python 3.11, PySide6 (Qt Widgets, Essentials only: QtCore/QtGui/QtWidgets/QtSvg — **no QtCharts, no QtWebEngine**).
Run everything with the project venv: `.venv/bin/python`.

## Layout
- `database/` connection + migrations · `models/` all business logic (the UI never runs SQL)
- `ui/theme.py` colours/fonts/QSS · `ui/icons.py` · `ui/widgets.py` · `ui/table.py` · `ui/charts.py` — the shared kit
- `ui/main_window.py` shell · `ui/pages/<key>.py` one screen each (registered in `ui/pages/__init__.py`)
- `ui/dialogs/` dialogs shared between pages · `utils/` helpers, export, backup, updater
- `ui/pages/dashboard.py` is the reference implementation of a page. Read it and the kit files first.

## Rules
1. **Never hard-code a colour or font.** Use `theme.c("accent")`, label roles (`label(text, "title"|"subtitle"|"heading"|"caption"|"muted"|"hint"|"field"|"error")`), button variants (`button(text, "primary"|"danger"|"ghost"|"link"|None, icon)`), `Badge`, `Card`. Both dark and light themes must look right.
2. Pages subclass `widgets.Page`: set `title`/`subtitle`, put header buttons in with `self.add_action(...)`, build under `self.root`, load data **only** in `refresh()` (called on show and after any data change). Never query in `__init__`. Do not reset the user's filters/date in `refresh()`.
3. After every successful write call `self.app.data_changed()` then `self.toast("Sale saved")`. Errors from models are `ValueError` / `PermissionError` subclasses (`stock.StockError`, `stock.LockedError`) with user-ready messages: show them inline in the dialog (`Dialog.on_accept` does this automatically when you raise) or with `self.toast(str(e), "bad")`. Never show a traceback or a raw `QMessageBox`.
4. Lists use `DataTable` (`Col`, `Action`), with a `SearchBox` named `self.search` on the page (Ctrl+F focuses it) wired to `table.set_search`. Destructive actions go through `confirm(parent, title, text, ok_text, danger=True)`.
5. Dialogs subclass or instantiate `widgets.Dialog` (Enter/Ctrl+Enter saves, Esc cancels, inline error line). First input focused on open; Tab order top-to-bottom.
6. Money: `format_currency(x)` (₹ Indian grouping; `decimals=0` in dense tables/cards). Quantities: `format_qty(q, unit)`. Dates shown `format_date(iso)` → DD-MM-YYYY; stored/passed as ISO `YYYY-MM-DD`. Date inputs are `DateField` / `DateRangeBar`. Number inputs are `NumberEdit`. Product/party pickers are `SearchCombo`.
7. Plain language for a shop owner: "Sale", "Purchase", "Customer owes", "Close day". Sentence case. No jargon, no emoji.
8. Layout: 16px gaps between cards, 12px inside. Right-align numbers. One primary button per view. Tables fill the height; put the summary/total in a footer row of labels under the table.
9. Keep it fast: no per-row queries; models already return joined/aggregated rows.

## Models cheat-sheet (read the files for exact signatures)
- `models.product`: `list_products(include_inactive=False)` → rows with `stock`, `stock_value`, `status` ('ok'|'low'|'out'); `add_product`, `update_product`, `soft_delete_product`, `restore_product`, `get_product_by_id`, `label(row)`, `distinct_values(column)`
- `models.bills`: `save_bill(kind, date, items, party_name, party_phone, discount, paid, method, notes, bill_no, bill_id, update_cost)`, `get_bill(id)` (→ lines, payments, locked), `list_bills(kind, date_from, date_to, party_id, only_due, search)`, `delete_bill`, `add_payment`, `delete_payment`, `settle_party`, `list_lines(kind, from, to)`, `last_price(kind, product_id, party_name)`
- `models.stock`: `stock_on`, `stock_map`, `min_balance_from`, `day_ledger(date)`, `product_movements(product_id, from, to)`, `set_count`, `clear_count`, `lock_day`, `unlock_day`, `is_locked`, `locked_days`
- `models.parties`: `list_parties(kind, search)` (with `bills`, `billed`, `paid`, `due`, `last_date`), `save_party`, `delete_party`, `names(kind)`, `find_by_name`
- `models.expense`: `insert_expense`, `update_expense`, `delete_expense`, `list_expenses(from, to, category, search)`, `categories()`
- `models.reports`: `summary`, `compare`, `daily_series`, `product_performance`, `expense_breakdown`, `stock_overview`, `outstanding`
- `models.settings`: `get`, `set`, `get_all`, `set_many` (keys: shop_name, shop_address, shop_phone, shop_gstin, invoice_footer, theme, auto_backup, backup_keep)
- `utils.tabular.export_rows(path, title, headers, rows, money_columns)` — Excel/CSV of any table
- `utils.helpers`: `format_currency`, `format_compact`, `format_qty`, `format_date`, `parse_date`, `parse_number`

## Checking your work
- Visual: `.venv/bin/python tools/shot.py <page-key> --db data/demo-<yourname>.db [--theme light] [--call open new=True]` writes `screenshots/<key>.png` (and `<key>-dialog.png` for a dialog opened by the call). **Open the PNGs and look at them**, in both themes; fix clipping, misalignment, cramped or empty areas. Use your own `--db` file so parallel work does not collide; never write to `data/demo.db` or `data/plywoodpro.db`.
- Tests: add `tests/test_ui_<area>.py` using the `window` fixture (pytest-qt, offscreen, temp demo DB): navigate to the page, exercise the main flows through the widgets or the dialog classes (create/edit/delete, validation errors), and assert on model state. Dialogs must be testable without `exec()` blocking: put the save logic in a method the test can call. Run `.venv/bin/python -m pytest -q`.
