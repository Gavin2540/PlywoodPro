import datetime

import openpyxl

from models import bills, expense, product, reports, settings
from utils import export


def _today():
    return datetime.date.today()


def _is_pdf(path):
    data = path.read_bytes()
    return data.startswith(b"%PDF") and len(data) > 2048


def test_pdf_single_day_and_range(demo_db, tmp_path):
    day = _today()
    one = tmp_path / "day.pdf"
    export.export_report_pdf(day, day, one)
    assert _is_pdf(one)
    rng = tmp_path / "range.pdf"
    export.export_report_pdf(day - datetime.timedelta(days=29), day, rng)
    assert _is_pdf(rng)


def test_excel_matches_model(demo_db, tmp_path):
    day = _today()
    a = day - datetime.timedelta(days=29)
    path = tmp_path / "r.xlsx"
    export.export_report_excel(a, day, path)
    wb = openpyxl.load_workbook(path)
    for name in ("Summary", "Sales", "Purchases", "Expenses", "Products", "Daily", "Stock"):
        assert name in wb.sheetnames
    s = reports.summary(a, day)
    rows = {r[0].value: r[1].value for r in wb["Summary"].iter_rows(min_row=2)}
    assert rows["Net profit"] == s["net_profit"]
    assert isinstance(rows["Sales"], (int, float))
    lines = bills.list_lines("sale", a, day)
    ws = wb["Sales"]
    rows_ = {ws.cell(r, 1).value: [c.value for c in ws[r]] for r in range(2, ws.max_row + 1)}
    total_row = rows_["Total"]
    assert rows_["Net sales"][7] == s["revenue"]
    assert abs(rows_["Less: discounts"][7] + s["discount"]) < 0.01
    assert abs(total_row[7] - sum(r["amount"] for r in lines)) < 0.01
    assert ws.freeze_panes == "A2"


def test_single_day_has_ledger(demo_db, tmp_path):
    day = _today().isoformat()
    path = tmp_path / "d.xlsx"
    export.export_daily_excel(day, str(path))
    assert openpyxl.load_workbook(path)["Stock"]["B1"].value == "Opening"
    export.export_daily_pdf(day, str(tmp_path / "d.pdf"))
    assert _is_pdf(tmp_path / "d.pdf")


def test_special_characters_do_not_crash(demo_db, tmp_path):
    settings.set("shop_name", "Shah & Sons <Ply> Pvt")
    pid = product.add_product("Ply <A&B>", "Brand & Co", "Ply", "18mm", "8x4", 100, 150, opening_stock=50)
    day = _today().isoformat()
    bills.save_bill("sale", day, [{"product_id": pid, "qty": 2, "unit_price": 150}], party_name="R&D <x>")
    expense.insert_expense(day, "Tea & <snacks>", 40, "a < b & c")
    export.export_report_pdf(day, day, tmp_path / "x.pdf")
    export.export_report_excel(day, day, tmp_path / "x.xlsx")
    assert _is_pdf(tmp_path / "x.pdf")


def test_many_lines_summarised(demo_db, tmp_path):
    a = _today() - datetime.timedelta(days=74)
    assert len(bills.list_lines("sale", a, _today())) > export.MAX_ITEMISED
    export.export_report_pdf(a, _today(), tmp_path / "big.pdf")
    assert _is_pdf(tmp_path / "big.pdf")


def test_empty_period(demo_db, tmp_path):
    export.export_report_pdf("2001-01-01", "2001-01-31", tmp_path / "e.pdf")
    export.export_report_excel("2001-01-01", "2001-01-01", tmp_path / "e.xlsx")
    assert _is_pdf(tmp_path / "e.pdf")
    assert openpyxl.load_workbook(tmp_path / "e.xlsx")["Summary"]["A1"].value == "Item"
