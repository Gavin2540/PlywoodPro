"""Sales / Purchases pages, the bill editor and the bill view (all driven without exec())."""
import datetime

import pytest

from models import bills, parties, product, stock
from ui.dialogs.bill_editor import BillEditor
from ui.dialogs.bill_view import BillView

T = datetime.date.today()


def d(n):
    return (T - datetime.timedelta(days=n)).isoformat()


def page(window, key="sales", **kw):
    window.navigate(key, **kw)
    return window._pages[key]


def pid_with_stock(min_stock=5):
    return next(p for p in product.list_products() if p["stock"] >= min_stock)


def test_pages_list_bills_for_range(window):
    p = page(window)
    start, end = p.range.range()
    expected = bills.list_bills("sale", start, end)
    assert expected and len(p.table.rows()) == len(expected)
    assert f"{len(expected)} bill" in p.subtitle_label.text()
    assert p.table.rows()[0]["locked"] in (True, False)
    # purchases page uses its own kind and has no profit column
    pp = page(window, "purchases")
    pp.range.set_range(d(120), d(0))
    assert len(pp.table.rows()) == len(bills.list_bills("purchase", d(120), d(0)))
    assert "profit" not in [c.key for c in pp.table.cols] and "profit" in [c.key for c in p.table.cols]


def test_unpaid_filter_and_search(window):
    p = page(window)
    p.range.set_range(d(60), d(0))
    total = len(p.table.rows())
    p.filter.set("unpaid")
    p._filter_changed()
    unpaid = p.table.rows()
    assert unpaid and len(unpaid) < total and all(r["due"] > 0 for r in unpaid)
    assert "due" in p.subtitle_label.text()
    p.filter.set("all")
    p.search.setText(unpaid[0]["party_name"])
    p._filter_changed()
    assert p.table.rows() and all(unpaid[0]["party_name"] in (r["party_name"] or "") for r in p.table.rows())


def test_create_sale_drops_stock(window):
    p = pid_with_stock()
    before = stock.current_stock(p["id"])
    dlg = BillEditor(window, "sale")
    dlg.set_party("Test Buyer", "99999")
    row = dlg.add_line(p["id"], 2)
    assert row.rate.value() == pytest.approx(p["selling_price"]) or row.rate.value() > 0
    assert "Available on this date" in row.hint.text()
    assert dlg.total() == pytest.approx(2 * row.rate.value())
    assert dlg.paid.value() == pytest.approx(dlg.total())  # follows the total
    dlg.save()
    assert dlg.bill_id
    b = bills.get_bill(dlg.bill_id)
    assert b["party_name"] == "Test Buyer" and b["due"] == 0 and len(b["lines"]) == 1
    assert stock.current_stock(p["id"]) == before - 2
    assert parties.find_by_name("customer", "Test Buyer")["phone"] == "99999"


def test_editor_ignores_blank_rows_and_follows_total(window):
    p = pid_with_stock()
    dlg = BillEditor(window, "sale")
    dlg.add_line(p["id"], 1, rate=1000)
    dlg.add_line(p["id"], 1, rate=500)  # same product twice is allowed
    assert dlg.rows[-1].is_empty()
    kw = dlg.collect()
    assert len(kw["items"]) == 2
    dlg.discount.set_value(100)
    assert dlg.total() == 1400 and dlg.paid.value() == 1400
    dlg.paid.setText("400")
    dlg.paid.textEdited.emit("400")
    dlg.rows[0].rate.set_value(2000)
    assert dlg.paid.value() == 400  # no longer follows once edited
    dlg.pay_full()
    assert dlg.paid.value() == dlg.total()


def test_oversell_shows_error_and_saves_nothing(window):
    p = pid_with_stock()
    have = stock.current_stock(p["id"])
    n_before = len(bills.list_bills("sale"))
    dlg = BillEditor(window, "sale")
    row = dlg.add_line(p["id"], have + 5)
    assert row.hint.property("role") == "error"  # hint turns bad-coloured
    dlg._accept()
    assert dlg.error.isVisible() or not dlg.error.isHidden()
    assert "Not enough stock" in dlg.error.text()
    assert len(bills.list_bills("sale")) == n_before and stock.current_stock(p["id"]) == have
    assert dlg.result() == 0  # still open


def test_part_payment_needs_customer(window):
    p = pid_with_stock()
    dlg = BillEditor(window, "sale")
    dlg.add_line(p["id"], 1)
    dlg.paid.setText("10")
    dlg.paid.textEdited.emit("10")
    dlg._accept()
    assert "customer name" in dlg.error.text()
    dlg.set_party("Credit Customer")
    dlg._accept()
    b = bills.get_bill(dlg.bill_id)
    assert b["paid"] == 10 and b["due"] > 0


def test_collect_validation(window):
    dlg = BillEditor(window, "sale")
    with pytest.raises(ValueError, match="at least one"):
        dlg.collect()
    dlg.rows[0].product.setEditText("nonsense")
    with pytest.raises(ValueError, match="pick a product"):
        dlg.collect()
    dlg.rows[0].product.setEditText("")
    dlg.add_line(pid_with_stock()["id"])
    with pytest.raises(ValueError, match="quantity"):
        dlg.collect()


def test_closed_day_disables_save(window):
    p = pid_with_stock()
    stock.lock_day(d(3))
    dlg = BillEditor(window, "sale")
    dlg.set_date(d(3))
    assert not dlg.ok_button.isEnabled() and not dlg.lock_warn.isHidden()
    dlg.set_date(d(0))
    assert dlg.ok_button.isEnabled() and dlg.lock_warn.isHidden()


def test_hint_uses_selected_date(window):
    p = next(x for x in product.list_products() if x["stock"] > 0)
    dlg = BillEditor(window, "sale")
    row = dlg.add_line(p["id"], 1)
    dlg.set_date(d(70))
    assert row.hint.text().startswith("Available on this date:")


def test_below_cost_warning(window):
    p = pid_with_stock()
    dlg = BillEditor(window, "sale")
    row = dlg.add_line(p["id"], 1, rate=1)
    assert "Below cost" in row.cost_hint.text()
    row.rate.set_value(p["selling_price"])
    assert row.cost_hint.text() == ""


def test_save_and_new_resets_form(window):
    p = pid_with_stock(10)
    dlg = BillEditor(window, "sale")
    dlg.set_date(d(1))
    dlg.set_party("Repeat Buyer")
    dlg.add_line(p["id"], 1)
    assert dlg.save_and_new()
    assert bills.get_bill(dlg.bill_id)["date"] == d(1)
    assert dlg.date_field.iso() == d(1) and dlg.party.text() == "" and dlg.rows[0].is_empty() and len(dlg.rows) == 1
    assert dlg.paid.value() == 0


def test_prefill_product_and_party(window):
    p = pid_with_stock()
    dlg = BillEditor(window, "sale", product_id=p["id"], party_name="Ravi Interiors")
    assert dlg.rows[0].product_id() == p["id"] and dlg.party.text() == "Ravi Interiors"
    assert dlg.phone.text() == (parties.find_by_name("customer", "Ravi Interiors")["phone"] or "")
    assert dlg.rows[-1].is_empty()


def test_edit_sale(window):
    b = next(x for x in bills.list_bills("sale", d(10), d(0)) if x["items"] == 1 and x["due"] <= 0)
    full = bills.get_bill(b["id"])
    ln = full["lines"][0]
    dlg = BillEditor(window, "sale", bill_id=b["id"])
    assert dlg.windowTitle() == f"Edit sale {b['bill_no']}"
    assert dlg.paid.value() == pytest.approx(full["paid"])
    row = dlg.rows[0]
    assert row.qty.value() == ln["qty"] and row.rate.value() == ln["unit_price"]
    row.qty.set_value(ln["qty"] - 1 if ln["qty"] > 1 else ln["qty"] + 0)
    dlg.notes.setText("edited")
    dlg.save()
    after = bills.get_bill(b["id"])
    assert after["notes"] == "edited" and after["qty"] == (ln["qty"] - 1 if ln["qty"] > 1 else ln["qty"])
    assert after["paid"] <= after["total"] + 0.01
    assert dlg.bill_id == b["id"]


def test_bill_view_payments(window):
    b = next(x for x in bills.list_bills("sale", d(60), d(0)) if x["due"] > 0)
    v = BillView(window, b["id"])
    assert v.pay_amount.value() == pytest.approx(b["due"])
    v.pay_amount.set_value(b["due"] + 1000)
    assert v.add_payment() is False and "more than" in v.error.text()
    v.pay_amount.set_value(1)
    assert v.add_payment() and v.changed
    assert bills.get_bill(b["id"])["due"] == pytest.approx(b["due"] - 1)
    v.pay_amount.set_value(bills.get_bill(b["id"])["due"])
    v.add_payment()
    assert bills.get_bill(b["id"])["due"] == 0 and v.pay_card is None  # card disappears when fully paid
    pay = bills.get_bill(b["id"])["payments"][-1]
    assert v.remove_payment(pay["id"], ask=False)
    assert bills.get_bill(b["id"])["due"] == pytest.approx(pay["amount"]) and v.pay_card is not None


def test_bill_view_pdf(window, tmp_path, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: True)
    b = bills.list_bills("sale")[0]
    out = str(tmp_path / "x.pdf")
    assert BillView(window, b["id"]).write_pdf(out) == out
    assert open(out, "rb").read(4) == b"%PDF"


def test_delete_bill(window):
    p = page(window)
    row = p.table.rows()[0]
    assert p.delete_bill(row, ask=False)
    assert bills.get_bill(row["id"]) is None
    assert all(r["id"] != row["id"] for r in p.table.rows())


def test_delete_locked_bill_shows_message(window):
    p = page(window)
    row = p.table.rows()[0]
    stock.lock_day(row["date"])
    p.refresh()
    assert p.table.rows()[0]["locked"]
    assert p.delete_bill(row, ask=False) is False
    assert bills.get_bill(row["id"]) is not None


def test_purchase_updates_product_cost(window):
    p = product.list_products()[0]
    dlg = BillEditor(window, "purchase", product_id=p["id"])
    row = dlg.rows[0]
    assert row.rate.value() > 0  # prefilled from last / product purchase price
    row.qty.set_value(7)
    row.rate.set_value(1234)
    dlg.supplier_bill_no.setText("INV-77")
    before = stock.current_stock(p["id"])
    dlg.set_party("New Supplier Co")
    dlg.paid.setText("1000")
    dlg.paid.textEdited.emit("1000")
    dlg.save()
    b = bills.get_bill(dlg.bill_id)
    assert b["bill_no"] == "INV-77" and b["due"] == pytest.approx(7 * 1234 - 1000)
    assert stock.current_stock(p["id"]) == before + 7
    assert product.get_product_by_id(p["id"])["purchase_price"] == 1234
    assert "New Supplier Co" in parties.names("supplier")


def test_open_with_bill_id_widens_range(window, monkeypatch):
    shown = []
    monkeypatch.setattr("ui.pages.bills.show_bill", lambda parent, bid: shown.append(bid) or False)
    old = bills.list_bills("sale", d(70), d(60))[0]
    p = page(window)
    assert old["id"] not in [r["id"] for r in p.table.rows()]
    p.open(bill_id=old["id"])
    assert shown == [old["id"]]
    assert p.table.selected()["id"] == old["id"]


def test_new_via_open_and_toast(window, monkeypatch):
    p = pid_with_stock()
    made = {}

    def fake_exec(self):
        made["row"] = self.rows[0].product_id()
        self.set_party("Opened Buyer")
        self.rows[0].qty.set_value(1)
        self.save()
        return 1
    monkeypatch.setattr(BillEditor, "exec", fake_exec)
    pg = page(window)
    pg.open(new=True, product_id=p["id"])
    assert made["row"] == p["id"]
    assert pg.table.selected()["party_name"] == "Opened Buyer"


def test_export(window, tmp_path):
    p = page(window)
    out = str(tmp_path / "s.csv")
    assert p.export_to(out) == out
    lines = open(out, encoding="utf-8-sig").read().splitlines()
    assert lines[0].startswith("Date,Bill no") and len(lines) == 1 + len(p.table.rows())


def test_edit_keeps_cost_snapshot(window):
    p = pid_with_stock(10)
    sid = bills.save_bill("sale", d(1), [{"product_id": p["id"], "qty": 2, "unit_price": p["purchase_price"] + 500}])
    cost_before = bills.get_bill(sid)["lines"][0]["cost"]
    bills.save_bill("purchase", d(0), [{"product_id": p["id"], "qty": 1, "unit_price": p["purchase_price"] + 300}])
    assert product.get_product_by_id(p["id"])["purchase_price"] != cost_before  # product cost has moved
    dlg = BillEditor(window, "sale", bill_id=sid)
    dlg.rows[0].qty.set_value(3)
    dlg.save()
    after = bills.get_bill(sid)
    assert after["lines"][0]["cost"] == cost_before and after["lines"][0]["qty"] == 3
    assert after["profit"] == pytest.approx(3 * (p["purchase_price"] + 500 - cost_before))


def test_party_hints_and_totals_placeholders(window):
    dlg = BillEditor(window, "sale")
    assert dlg.balance_l.text() == "—" and dlg.profit_l.isHidden() and dlg.paid.text() == ""
    dlg.party.setEditText("Brand New Person")
    assert "New customer" in dlg.party_hint.text()
    owing = next(x for x in parties.list_parties("customer") if x["due"] > 0)
    dlg.party.setEditText(owing["name"])
    assert dlg.party_hint.text().startswith("Owes")
    row = dlg.add_line(pid_with_stock()["id"], 1)
    assert row.amount.text() == "" or row.rate.value() > 0
    assert not dlg.rows[0].remove.isHidden()
    assert dlg.rows[-1].remove.isHidden()
