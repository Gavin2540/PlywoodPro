import datetime

from models import expense


def _page(window, qtbot):
    window.navigate("expenses")
    qtbot.wait(30)
    return window._pages["expenses"]


def _range(page):
    return page.range.range()


def test_lists_expenses_for_range(window, qtbot):
    page = _page(window, qtbot)
    start, end = _range(page)
    rows = expense.list_expenses(start, end)
    assert rows and len(page.table.rows()) == len(rows)
    total = sum(r["amount"] for r in rows)
    assert f"{len(rows)} " in page.subtitle_label.text()
    assert page.footer_total.text().replace(",", "").replace("₹", "").replace(".00", "") == str(round(total))


def test_category_filter_and_refresh_keeps_it(window, qtbot):
    page = _page(window, qtbot)
    start, end = _range(page)
    page.category.setCurrentText("Transport")
    expected = expense.list_expenses(start, end, "Transport")
    assert expected and len(page.table.rows()) == len(expected)
    page.refresh()
    assert page.category.currentText() == "Transport" and page.range.range() == (start, end)
    assert len(page.table.rows()) == len(expected)


def test_range_change_reloads(window, qtbot):
    page = _page(window, qtbot)
    page.range.seg._buttons["7d"].click()
    start, end = _range(page)
    assert len(page.table.rows()) == len(expense.list_expenses(start, end))


def test_add_edit_delete(window, qtbot):
    from ui.pages.expenses import ExpenseDialog
    page = _page(window, qtbot)
    dlg = ExpenseDialog(page)
    qtbot.addWidget(dlg)
    dlg.amount.set_value(1234)
    dlg.category.setEditText("Tea and snacks")  # a brand-new category is allowed
    dlg.note.setText("for workers")
    assert dlg.save() is True
    row = expense.list_expenses(category="Tea and snacks")[0]
    assert row["amount"] == 1234 and row["note"] == "for workers"
    assert "Tea and snacks" in expense.categories()

    dlg2 = ExpenseDialog(page, row)
    qtbot.addWidget(dlg2)
    assert dlg2.amount.value() == 1234
    dlg2.amount.set_value(999)
    dlg2.save()
    assert expense.list_expenses(category="Tea and snacks")[0]["amount"] == 999

    page.refresh()
    assert page.table.select_where(lambda r: r["id"] == row["id"])
    expense.delete_expense(row["id"])
    window.data_changed()
    assert not any(r["id"] == row["id"] for r in page.table.rows())


def test_zero_amount_shows_inline_error(window, qtbot):
    from ui.pages.expenses import ExpenseDialog
    dlg = ExpenseDialog(window._pages["expenses"] if "expenses" in window._pages else window)
    qtbot.addWidget(dlg)
    dlg.category.setEditText("Rent")
    before = len(expense.list_expenses())
    dlg._accept()
    assert dlg.error.isVisible() or not dlg.error.isHidden()
    assert "greater than zero" in dlg.error.text()
    assert len(expense.list_expenses()) == before


def test_save_and_add_another_keeps_date_and_category(window, qtbot):
    from ui.pages.expenses import ExpenseDialog
    dlg = ExpenseDialog(window)
    qtbot.addWidget(dlg)
    dlg.date.set_iso((datetime.date.today() - datetime.timedelta(days=3)).isoformat())
    dlg.category.setEditText("Labour")
    dlg.amount.set_value(500)
    before = len(expense.list_expenses())
    assert dlg.save(another=True) is False
    assert len(expense.list_expenses()) == before + 1
    assert dlg.amount.is_blank() and dlg.category.text() == "Labour"
    assert dlg.date.iso() == (datetime.date.today() - datetime.timedelta(days=3)).isoformat()


def test_open_new_opens_dialog(window, qtbot, monkeypatch):
    from ui.pages import expenses as mod
    opened = []
    monkeypatch.setattr(mod.ExpenseDialog, "exec", lambda self: opened.append(self) or 0)
    page = _page(window, qtbot)
    page.open(new=True)
    assert len(opened) == 1
