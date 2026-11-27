import datetime, os, sqlite3
import pytest
from database.db import DatabaseManager, get_db, SCHEMA_VERSION
from models import bills, expense, parties, product, reports, settings, stock
from models.stock import LockedError, StockError
from utils import backup, helpers

T = datetime.date.today()
def d(n): return (T - datetime.timedelta(days=n)).isoformat()

def mk(name="Ply 18", cost=1000, price=1300, opening=0, **kw):
    return product.add_product(name, "Green", "BWP", "18mm", "8x4", cost, price, "sheets", 10, opening, **kw)

def buy(pid, qty, day=0, price=1000, **kw):
    return bills.save_bill("purchase", d(day), [{"product_id": pid, "qty": qty, "unit_price": price}], **kw)

def sell(pid, qty, day=0, price=1300, **kw):
    return bills.save_bill("sale", d(day), [{"product_id": pid, "qty": qty, "unit_price": price}], **kw)


def test_fresh_db_is_current_schema(db):
    assert DatabaseManager.get_connection().execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION

def test_stock_is_computed(db):
    p = mk(opening=5)
    buy(p, 10, day=3); sell(p, 4, day=2); sell(p, 1, day=0)
    assert stock.stock_on(p, d(4)) == 5
    assert stock.stock_on(p, d(3)) == 15
    assert stock.stock_on(p, d(2)) == 11
    assert stock.current_stock(p) == 10
    assert stock.stock_map()[p] == 10

def test_sale_cannot_exceed_stock(db):
    p = mk(); buy(p, 5)
    with pytest.raises(StockError): sell(p, 6)
    assert stock.current_stock(p) == 5 and bills.list_bills("sale") == []

def test_backdated_sale_checked_against_that_day(db):
    """v1 bug: stock arrived today, so a sale dated last week must be refused."""
    p = mk(); buy(p, 10, day=0)
    with pytest.raises(StockError): sell(p, 3, day=5)

def test_backdated_sale_cannot_starve_later_sales(db):
    p = mk(); buy(p, 10, day=5); sell(p, 8, day=1)
    with pytest.raises(StockError, match="later entries"): sell(p, 5, day=3)
    sell(p, 2, day=3)
    assert stock.current_stock(p) == 0

def test_purchase_delete_blocked_when_sold(db):
    p = mk(); b = buy(p, 10, day=2); sell(p, 6, day=1)
    with pytest.raises(StockError): bills.delete_bill(b)
    with pytest.raises(StockError): bills.save_bill("purchase", d(2), [{"product_id": p, "qty": 5, "unit_price": 1000}], bill_id=b)
    assert stock.current_stock(p) == 4
    bills.save_bill("purchase", d(2), [{"product_id": p, "qty": 6, "unit_price": 1000}], bill_id=b)
    assert stock.current_stock(p) == 0

def test_multi_item_bill_is_atomic(db):
    a, b = mk("A"), mk("B"); buy(a, 5); buy(b, 1)
    with pytest.raises(StockError):
        bills.save_bill("sale", d(0), [{"product_id": a, "qty": 2, "unit_price": 10}, {"product_id": b, "qty": 3, "unit_price": 10}])
    assert stock.current_stock(a) == 5 and bills.list_bills("sale") == []

def test_same_product_twice_on_bill_is_summed(db):
    p = mk(); buy(p, 5)
    with pytest.raises(StockError):
        bills.save_bill("sale", d(0), [{"product_id": p, "qty": 3, "unit_price": 10}] * 2)

def test_edit_sale(db):
    p = mk(); buy(p, 10, day=1)
    s = sell(p, 4)
    bills.save_bill("sale", d(0), [{"product_id": p, "qty": 9, "unit_price": 1400}], bill_id=s)
    assert stock.current_stock(p) == 1
    bill = bills.get_bill(s)
    assert bill["total"] == 12600 and bill["paid"] == 12600 and bill["due"] == 0
    assert bill["lines"][0]["cost"] == 1000

def test_cost_snapshot_and_profit(db):
    p = mk(cost=900); buy(p, 10, day=3, price=1000)          # cost follows the purchase
    assert product.get_product_by_id(p)["purchase_price"] == 1000
    s = sell(p, 2, day=2, price=1300, discount=100)
    buy(p, 10, day=1, price=1200)                             # later price rise
    assert bills.get_bill(s)["profit"] == 2 * 300 - 100       # unchanged
    r = reports.summary(d(2), d(2))
    assert r["revenue"] == 2500 and r["gross_profit"] == 500

def test_locks(db):
    p = mk(); buy(p, 10, day=2); s = sell(p, 1, day=1)
    stock.lock_day(d(1))
    with pytest.raises(LockedError): sell(p, 1, day=1)
    with pytest.raises(LockedError): bills.delete_bill(s)
    with pytest.raises(LockedError): bills.save_bill("sale", d(0), [{"product_id": p, "qty": 1, "unit_price": 1}], bill_id=s)
    with pytest.raises(LockedError): stock.set_count(p, d(1), 3)
    sell(p, 1, day=0)
    stock.unlock_day(d(1)); bills.delete_bill(s)
    assert stock.current_stock(p) == 9

def test_physical_count_pins_closing(db):
    p = mk(); buy(p, 10, day=5); sell(p, 2, day=4)
    stock.set_count(p, d(3), 7, "one damaged")
    assert stock.stock_on(p, d(3)) == 7 and stock.current_stock(p) == 7
    buy(p, 5, day=6)                                           # backdated before the count
    assert stock.current_stock(p) == 7
    row = [r for r in stock.day_ledger(d(3)) if r["product_id"] == p][0]
    assert row["is_counted"] and row["expected_closing"] == 13 and row["variance"] == -6
    sell(p, 7, day=0)
    with pytest.raises(StockError): stock.set_count(p, d(3), 6)
    stock.clear_count(p, d(3))
    assert stock.current_stock(p) == 6

def test_day_ledger_and_movements(db):
    p = mk(opening=2); buy(p, 10, day=1); sell(p, 3, day=1); sell(p, 1, day=0)
    row = stock.day_ledger(d(1))[0]
    assert (row["opening_stock"], row["purchases_qty"], row["sales_qty"], row["closing_stock"]) == (2, 10, 3, 9)
    assert stock.day_ledger(d(0))[0]["opening_stock"] == 9
    mv = stock.product_movements(p)
    assert [m["balance"] for m in mv] == [12, 9, 8]

def test_viewing_does_not_write(db):
    p = mk(); buy(p, 1)
    before = DatabaseManager.get_connection().total_changes
    stock.day_ledger(d(-30)); stock.stock_map(); product.list_products(); reports.summary(); reports.stock_overview()
    assert DatabaseManager.get_connection().total_changes == before

def test_credit_and_payments(db):
    p = mk(); buy(p, 20, day=3)
    with pytest.raises(ValueError, match="customer name"): sell(p, 1, paid=0)
    s1 = sell(p, 2, day=2, party_name="Ravi Traders", party_phone="98", paid=600)
    s2 = sell(p, 1, day=1, party_name="ravi traders", paid=0)
    cust = parties.list_parties("customer")
    assert len(cust) == 1 and cust[0]["due"] == 2000 + 1300 and cust[0]["phone"] == "98"
    with pytest.raises(ValueError): bills.add_payment(s1, 5000)
    bills.settle_party(cust[0]["id"], 2500)
    assert bills.get_bill(s1)["due"] == 0 and bills.get_bill(s2)["due"] == 800
    assert reports.outstanding()["receivable"] == 800
    assert [b["id"] for b in bills.list_bills("sale", only_due=True)] == [s2]
    # shrinking a bill below what was paid trims the payments
    bills.save_bill("sale", d(2), [{"product_id": p, "qty": 1, "unit_price": 1300}], party_name="Ravi Traders", paid=1300, bill_id=s1)
    assert bills.get_bill(s1)["paid"] == 1300

def test_supplier_payable(db):
    p = mk(); buy(p, 10, party_name="Century", paid=4000)
    assert reports.outstanding()["payable"] == 6000
    assert parties.list_parties("supplier")[0]["due"] == 6000

def test_validation(db):
    p = mk()
    for bad in ([], [{"product_id": p, "qty": 0, "unit_price": 1}], [{"product_id": p, "qty": float("nan"), "unit_price": 1}]):
        with pytest.raises(ValueError): bills.save_bill("purchase", d(0), bad)
    with pytest.raises(ValueError, match="future"): buy(p, 1, day=-1)
    with pytest.raises(ValueError): buy(p, 1, discount=5000)
    with pytest.raises(ValueError, match="already exists"): mk()
    with pytest.raises(ValueError): expense.insert_expense(d(0), "Rent", 0)

def test_opening_stock_edit_guard(db):
    p = mk(opening=5); sell(p, 5)
    pr = product.get_product_by_id(p)
    with pytest.raises(StockError):
        product.update_product(p, pr["name"], pr["brand"], pr["type"], pr["thickness"], pr["size"], 1, 1, "sheets", 1, opening_stock=2)
    assert product.get_product_by_id(p)["opening_stock"] == 5

def test_reports(db):
    p = mk(); buy(p, 10, day=1); sell(p, 2, day=1); sell(p, 1, day=0)
    expense.insert_expense(d(0), "Transport", 200)
    s = reports.summary(d(1), d(0))
    assert s["revenue"] == 3900 and s["gross_profit"] == 900 and s["net_profit"] == 700 and s["sale_bills"] == 2
    series = reports.daily_series(d(1), d(0))
    assert [x["net_profit"] for x in series] == [600, 100]
    assert reports.product_performance()[0]["qty"] == 3
    assert reports.expense_breakdown()[0]["category"] == "Transport"
    ov = reports.stock_overview()
    assert ov["stock_value"] == 7000 and len(ov["low"]) == 1
    cur, prev = reports.compare(d(0), d(0))
    assert cur["revenue"] == 1300 and prev["revenue"] == 2600

def test_settings(db):
    assert settings.get("theme") == "dark"
    settings.set("shop_name", "Sri Plywoods"); assert settings.get_all()["shop_name"] == "Sri Plywoods"

def test_helpers():
    assert helpers.format_currency(1543200.5) == "₹15,43,200.50"
    assert helpers.format_currency(-0.001) == "₹0.00"
    assert helpers.format_currency(-500) == "-₹500.00"
    assert helpers.format_qty(12.0) == "12" and helpers.format_qty(2.5, "sqft") == "2.5 sqft"
    assert helpers.parse_date("5/1/2026") == "2026-01-05"
    with pytest.raises(ValueError): helpers.parse_number("nan")
    assert helpers.parse_number("1,200.50") == 1200.5

def test_backup_roundtrip_and_bad_file(db, tmp_path):
    p = mk(); buy(p, 3)
    f = str(tmp_path / "b.plypro"); backup.export_database(f)
    buy(p, 4); assert stock.current_stock(p) == 7
    bad = tmp_path / "bad.plypro"
    import zipfile
    with zipfile.ZipFile(bad, "w") as z: z.writestr("plywoodpro.db", "not a database")
    with pytest.raises(ValueError): backup.import_database(str(bad))
    assert stock.current_stock(p) == 7                       # data untouched
    safety = backup.import_database(f)
    assert stock.current_stock(p) == 3 and os.path.exists(safety)
    backup.auto_backup(); assert any("auto-" in x for x in backup.list_backups())


def test_v1_database_upgrades(tmp_path):
    """A real v1.0.1 data file must open in v2 with every number intact."""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = str(tmp_path / "data" / "plywoodpro.db"); os.makedirs(os.path.dirname(path))
    c = sqlite3.connect(path)
    c.executescript(open(os.path.join(root, "database", "schema.sql")).read())
    c.executescript("""
      INSERT INTO products (id,name,brand,purchase_price,selling_price) VALUES (1,'Ply','G',1000,1300),(2,'MDF',NULL,500,650);
      INSERT INTO purchases (product_id,date,qty,unit_price,supplier_name,created_at) VALUES
        (1,'2026-05-01',20,1000,'Century','2026-05-01 10:00:00'),(2,'2026-05-01',10,500,'Century','2026-05-01 10:00:00');
      INSERT INTO sales (product_id,date,qty,unit_price,purchase_price_at_time,customer_name,created_at) VALUES
        (1,'2026-05-02',5,1300,1000,'Ravi','2026-05-02 11:00:00'),(2,'2026-05-02',2,650,500,'Ravi','2026-05-02 11:00:00'),
        (1,'2026-05-03',1,1300,1000,NULL,'2026-05-03 09:00:00');
      INSERT INTO expenses (date,category,amount) VALUES ('2026-05-02','Rent',100);
      INSERT INTO stock_ledger (product_id,date,opening_stock,purchases_qty,sales_qty,closing_stock,is_confirmed,manual_override,override_note) VALUES
        (1,'2026-05-01',0,20,0,20,1,0,NULL),(1,'2026-05-02',20,0,5,15,0,0,NULL),
        (2,'2026-05-02',10,0,2,7,0,1,'one broken');
    """); c.commit(); c.close()
    DatabaseManager.initialize(path)
    try:
        assert stock.current_stock(1) == 14 and stock.current_stock(2) == 7
        assert stock.is_locked("2026-05-01") and not stock.is_locked("2026-05-02")
        sales = bills.list_bills("sale")
        assert len(sales) == 2 and sales[1]["items"] == 2 and sales[1]["party_name"] == "Ravi"
        assert all(b["due"] == 0 for b in bills.list_bills())
        assert len(bills.list_bills("purchase")) == 1
        assert reports.summary("2026-05-02", "2026-05-02")["net_profit"] == 5*300 + 2*150 - 100
        assert [x for x in os.listdir(os.path.join(os.path.dirname(path), "backups")) if x.startswith("before-upgrade")]
        DatabaseManager.initialize(path)                      # reopening is a no-op
        assert len(bills.list_bills()) == 3
    finally:
        DatabaseManager.close()
