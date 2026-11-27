import datetime

import pytest

from models import stock
from ui.pages.ledger import CountDialog


@pytest.fixture
def page(window, qtbot):
    window.navigate("ledger")
    p = window._pages["ledger"]
    qtbot.wait(50)
    return p


def _ids(rows):
    return [r["product_id"] for r in rows]


def test_rows_match_day_ledger(page):
    expected = stock.day_ledger(page.date())
    assert _ids(page.table.rows()) == _ids(expected)
    assert page.stat_products.value.text() == f"{len(expected):,}"


def test_date_change_reloads(page):
    yday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    page.prev_day()
    assert page.date() == yday
    assert _ids(page.table.rows()) == _ids(stock.day_ledger(yday))
    assert page.table.rows()[0]["opening_stock"] == stock.day_ledger(yday)[0]["opening_stock"]
    page.next_day()
    assert page.date() == datetime.date.today().isoformat()
    assert not page.next_button.isEnabled()
    page.next_day()  # future is refused
    assert page.date() == datetime.date.today().isoformat()


def test_filters(page):
    page.set_date((datetime.date.today() - datetime.timedelta(days=3)).isoformat())
    all_rows = stock.day_ledger(page.date())
    moved = [r for r in all_rows if r["purchases_qty"] or r["sales_qty"]]
    page.filter.set("moved")
    page._apply_filter()
    assert len(page.table.rows()) == len(moved)
    page.filter.set("counted")
    page._apply_filter()
    assert page.table.rows() == []
    page.filter.set("all")
    page._apply_filter()
    page.search.setText(all_rows[0]["product_name"])
    page.search.searched.emit(page.search.text())
    assert 1 <= len(page.table.rows()) <= len(all_rows)


def test_count_dialog_records_variance(page, qtbot):
    row = page.table.rows()[0]
    dlg = CountDialog(page, row, page.date())
    qtbot.addWidget(dlg)
    dlg.qty.set_value(row["expected_closing"] - 2)
    with pytest.raises(ValueError):  # a difference needs a note
        dlg.save()
    dlg.note.setText("2 sheets water damaged")
    assert "short" in dlg.diff_label.text()
    assert dlg.save() is True
    r = next(x for x in page.table.rows() if x["product_id"] == row["product_id"])
    assert r["is_counted"] and r["variance"] == -2
    from ui.pages.ledger import _check_badge
    assert _check_badge(r) == ("Short 2", "bad")
    assert page.stat_counted.value.text().startswith("1 of")
    page.filter.set("mismatch")
    page._apply_filter()
    assert len(page.table.rows()) == 1
    # clearing the count
    page.clear_count(r, confirmed=True)
    assert not stock.day_ledger(page.date())[0]["is_counted"]


def test_count_matches_needs_no_note(page, qtbot):
    row = page.table.rows()[0]
    dlg = CountDialog(page, row, page.date())
    qtbot.addWidget(dlg)
    assert dlg.qty.value() == row["closing_stock"]
    assert dlg.save()
    assert dlg.diff_label.text() == "Matches the books"


def test_count_that_breaks_later_stock_shows_error(page, qtbot):
    # find a past day where a product has sales the next day
    today = datetime.date.today()
    for back in range(2, 30):
        d = (today - datetime.timedelta(days=back)).isoformat()
        nxt = (today - datetime.timedelta(days=back - 1)).isoformat()
        nxt_rows = {r["product_id"]: r for r in stock.day_ledger(nxt)}
        hit = next((r for r in stock.day_ledger(d) if nxt_rows[r["product_id"]]["sales_qty"] > 0
                    and nxt_rows[r["product_id"]]["opening_stock"] > 0), None)
        if hit:
            break
    assert hit
    page.set_date(d)
    row = next(r for r in page.table.rows() if r["product_id"] == hit["product_id"])
    dlg = CountDialog(page, row, d)
    qtbot.addWidget(dlg)
    dlg.qty.set_value(0)
    dlg.note.setText("lost")
    dlg.show()
    dlg._accept()
    assert dlg.error.isVisible()
    assert "later day" in dlg.error.text()


def test_close_and_reopen_day(page):
    d = page.date()
    assert page.close_day(confirmed=True)
    assert stock.is_locked(d)
    assert page.lock_button.text() == "Reopen day"
    assert "Closed" in page.subtitle_label.text()
    row = page.table.rows()[0]
    assert row["is_locked"]
    visible = page.table.actions[0].visible
    assert not visible(row)  # "Record count" no longer offered
    page.record_count(row)  # toasts, no dialog
    assert page.reopen_day(confirmed=True)
    assert not stock.is_locked(d)
    assert page.lock_button.text() == "Close day"
    assert page.table.actions[0].visible(page.table.rows()[0])


def test_open_jumps_to_date_and_product(page):
    d = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
    pid = stock.day_ledger(d)[2]["product_id"]
    page.open(date=d, product_id=pid)
    assert page.date() == d
    assert page.table.selected()["product_id"] == pid


def test_export_csv(page, tmp_path):
    out = page.export_visible(str(tmp_path / "ledger.csv"))
    assert out and (tmp_path / "ledger.csv").read_text(encoding="utf-8-sig").startswith("Product,")
