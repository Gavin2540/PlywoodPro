import pytest

from models import bills, parties


def _page(window, qtbot):
    window.navigate("parties")
    qtbot.wait(30)
    return window._pages["parties"]


@pytest.mark.parametrize("kind", ["customer", "supplier"])
def test_tabs_list_parties_with_model_balances(window, qtbot, kind):
    page = _page(window, qtbot)
    page.set_kind(kind)
    model = {p["id"]: p for p in parties.list_parties(kind)}
    shown = {r["id"]: r for r in page.table.rows()}
    assert model and shown.keys() == model.keys()
    for pid, r in shown.items():
        assert r["due"] == model[pid]["due"] and r["billed"] == model[pid]["billed"]


def test_with_balance_filter(window, qtbot):
    page = _page(window, qtbot)
    due_ids = {p["id"] for p in parties.list_parties("customer") if p["due"] > 0.004}
    page.view.set("due")
    page._apply_filter()
    assert {r["id"] for r in page.table.rows()} == due_ids
    page.view.set("all")
    page._apply_filter()
    assert len(page.table.rows()) == len(parties.list_parties("customer"))


def test_open_selects_party_and_tab(window, qtbot):
    page = _page(window, qtbot)
    sup = parties.list_parties("supplier")[0]
    page.open(kind="supplier", party_id=sup["id"])
    assert page.kind == "supplier" and page.table.selected()["id"] == sup["id"]
    assert page.add_button.text() == "Add supplier"


def test_add_party_and_duplicate_name(window, qtbot):
    from ui.dialogs.party_dialogs import PartyDialog
    dlg = PartyDialog(window, "customer")
    qtbot.addWidget(dlg)
    dlg.name.setText("Test Carpenters")
    dlg.phone.setText("99999")
    dlg.save()
    assert dlg.party_id and parties.get_party(dlg.party_id)["phone"] == "99999"

    dup = PartyDialog(window, "customer")
    qtbot.addWidget(dup)
    dup.name.setText("test carpenters")
    dup._accept()
    assert "already exists" in dup.error.text() and not dup.error.isHidden()

    empty = PartyDialog(window, "customer")
    qtbot.addWidget(empty)
    empty._accept()
    assert "Name is required" in empty.error.text()


def test_edit_party(window, qtbot):
    from ui.dialogs.party_dialogs import PartyDialog
    p = parties.list_parties("customer")[0]
    dlg = PartyDialog(window, "customer", p)
    qtbot.addWidget(dlg)
    dlg.address.setText("Main Road")
    dlg.save()
    assert parties.get_party(p["id"])["address"] == "Main Road"


def test_settle_reduces_due_and_overpayment_errors(window, qtbot):
    from ui.dialogs.party_dialogs import SettleDialog
    p = next(x for x in parties.list_parties("customer") if x["due"] > 0.004)
    dlg = SettleDialog(window, p)
    qtbot.addWidget(dlg)
    assert dlg.amount.value() == pytest.approx(p["due"])
    dlg.amount.set_value(p["due"] + 100)
    dlg._accept()
    assert "more than" in dlg.error.text() and not dlg.error.isHidden()
    dlg.amount.set_value(1000)
    dlg.save()
    after = next(x for x in parties.list_parties("customer") if x["id"] == p["id"])
    assert after["due"] == pytest.approx(p["due"] - 1000)
    dlg.amount.set_value(0)
    dlg._accept()
    assert "greater than zero" in dlg.error.text()


def test_statement_lists_party_bills(window, qtbot):
    from ui.dialogs.party_dialogs import StatementDialog
    p = parties.list_parties("supplier")[0]
    dlg = StatementDialog(window, p)
    qtbot.addWidget(dlg)
    dlg.range.set_range("2000-01-01", dlg.range.range()[1])
    expected = bills.list_bills(party_id=p["id"])
    assert len(dlg.table.rows()) == len(expected) > 0
    assert all(r["party_id"] == p["id"] for r in dlg.table.rows())
    assert dlg.due == pytest.approx(p["due"])
    assert dlg.pay_button.isHidden() == (p["due"] <= 0.004)


def test_remove_party_without_bills_deletes_and_with_bills_hides(window, qtbot):
    new_id = parties.save_party("customer", "Temp Person")
    parties.delete_party(new_id)
    assert parties.get_party(new_id) is None
    billed = next(p for p in parties.list_parties("customer") if p["bills"])
    parties.delete_party(billed["id"])
    assert parties.get_party(billed["id"])["is_active"] == 0


def test_statement_opens_real_bill_view_and_reloads(window, qtbot, monkeypatch):
    pytest.importorskip("ui.dialogs.bill_view")
    from ui.dialogs import bill_view
    from ui.dialogs.party_dialogs import StatementDialog
    p = parties.list_parties("supplier")[0]
    dlg = StatementDialog(window, p)
    qtbot.addWidget(dlg)
    opened, reloaded = [], []
    monkeypatch.setattr(bill_view, "show_bill", lambda parent, bid: opened.append(bid) or True)
    monkeypatch.setattr(dlg, "reload", lambda: reloaded.append(1))
    row = dlg.table.rows()[0]
    dlg.open_bill(row)
    assert opened == [row["id"]] and reloaded


def test_settle_preview_text(window, qtbot):
    from ui.dialogs.party_dialogs import SettleDialog
    p = next(x for x in parties.list_parties("customer") if x["due"] > 0.004)
    dlg = SettleDialog(window, p)
    qtbot.addWidget(dlg)
    assert "nothing left due" in dlg.preview.text()
    dlg.amount.set_value(p["due"] - 1000)
    assert "leaves ₹1,000 due" in dlg.preview.text()


def test_tab_counts_in_labels(window, qtbot):
    page = _page(window, qtbot)
    n = len(parties.list_parties("customer"))
    assert page.tabs._buttons["customer"].text() == f"Customers ({n})"
