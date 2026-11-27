import datetime
import os

import openpyxl

from models import reports
from ui.pages import reports as rp
from utils.helpers import format_currency


def _page(window, qtbot):
    window.navigate("reports")
    page = window._pages["reports"]
    qtbot.wait(50)
    return page


def _value(card):
    return card._value


def test_builds_and_kpis_match(window, qtbot):
    page = _page(window, qtbot)
    a, b = page.range()
    s = reports.summary(a, b)
    assert _value(page.k_sales) == s["revenue"]
    assert _value(page.k_gross) == s["gross_profit"]
    assert _value(page.k_exp) == s["expenses"]
    assert _value(page.k_net) == s["net_profit"]
    assert _value(page.k_buy) == s["purchases"]
    assert "days" in page.subtitle_label.text() or "day" in page.subtitle_label.text()


def test_range_switch_updates_and_survives_refresh(window, qtbot):
    page = _page(window, qtbot)
    page.range_bar.seg.changed.emit("7d")
    qtbot.wait(50)
    a, b = page.range()
    assert (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days == 6
    assert _value(page.k_sales) == reports.summary(a, b)["revenue"]
    page.refresh()
    assert page.range() == (a, b)
    assert "7 days" in page.subtitle_label.text()


def test_product_sort_modes(window, qtbot):
    page = _page(window, qtbot)
    page.range_bar.seg.changed.emit("year")
    qtbot.wait(50)
    for key in ("revenue", "profit", "qty"):
        page.prod_seg.changed.emit(key)
        vals = [r[key] for r in page.prod_table.rows()]
        assert vals == sorted(vals, reverse=True) and len(vals) > 1
    page.prod_seg.changed.emit("profit")
    assert [r["profit"] for r in page.prod_table.rows()] != [r["revenue"] for r in page.prod_table.rows()]


def test_day_table_double_click_sets_single_day(window, qtbot):
    page = _page(window, qtbot)
    row = page.day_table.rows()[0]
    page._open_day(row)
    assert page.range() == (row["date"], row["date"])
    assert _value(page.k_sales) == reports.summary(row["date"], row["date"])["revenue"]


def test_stock_view_totals(window, qtbot):
    page = _page(window, qtbot)
    page.view_seg.changed.emit("stock")
    qtbot.wait(50)
    data = reports.stock_overview()
    rows = page.stock_table.rows()
    assert len(rows) == data["products"]
    assert abs(sum(r["stock_value"] for r in rows) - data["stock_value"]) < 0.01
    assert abs(sum(r["retail_value"] for r in rows) - data["retail_value"]) < 0.01
    assert format_currency(data["stock_value"], decimals=0) in page.stock_footer.right.text()
    assert not page.range_bar.isVisibleTo(page)
    page.view_seg.changed.emit("pl")
    assert page.range_bar.isVisibleTo(page)


def test_aggregate_series_granularity():
    day = datetime.date(2025, 1, 1)

    def mk(n):
        return [{"date": (day + datetime.timedelta(days=i)).isoformat(), "revenue": 10.0, "net_profit": 1.0}
                for i in range(n)]
    assert rp.aggregate_series(mk(30))[3] == "Daily"
    labels, sales, net, g = rp.aggregate_series(mk(120))
    assert g == "Weekly" and len(labels) <= 19 and abs(sum(sales) - 1200) < 0.01
    labels, sales, net, g = rp.aggregate_series(mk(500))
    assert g == "Monthly" and len(labels) <= 18 and abs(sum(net) - 500) < 0.01
    assert rp.period_text("2026-11-01", "2026-11-27") == "1 Nov 2026 – 27 Nov 2026 · 27 days"
    assert rp.period_text("2026-11-27", "2026-11-27").endswith("1 day")


def test_exports_write_files(window, qtbot, tmp_path):
    page = _page(window, qtbot)
    pdf = page.export_pdf(str(tmp_path / "r.pdf"))
    xlsx = page.export_excel(str(tmp_path / "r.xlsx"))
    assert open(pdf, "rb").read(4) == b"%PDF"
    wb = openpyxl.load_workbook(xlsx)
    a, b = page.range()
    rows = {r[0].value: r[1].value for r in wb["Summary"].iter_rows(min_row=2)}
    assert rows["Net profit"] == reports.summary(a, b)["net_profit"]
    bad = page.export_pdf(str(tmp_path / "missing" / "r.pdf"))
    assert bad is None
