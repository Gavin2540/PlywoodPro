import pytest

from models import product
from ui.dialogs.product_dialog import ProductDialog
from ui.dialogs.product_history import ProductHistoryDialog


@pytest.fixture
def page(window, qtbot):
    window.navigate("products")
    p = window._pages["products"]
    qtbot.wait(50)
    return p


def _fill(dlg, name="Test Ply", cost=100, price=150, opening=5):
    dlg.name.setText(name)
    dlg.brand.setEditText("Acme")
    dlg.type.setEditText("MR")
    dlg.thickness.setEditText("12mm")
    dlg.size.setEditText("8x4")
    dlg.cost.set_value(cost)
    dlg.price.set_value(price)
    dlg.opening.set_value(opening)


def test_rows_match_model(page):
    # default view hides removed products
    assert len(page.table.rows()) == len(product.list_products())
    assert "products" in page.subtitle_label.text()


def test_search_and_filters(page, qtbot):
    page.search.setText("sainik")
    qtbot.waitUntil(lambda: 0 < len(page.table.rows()) < len(product.list_products()))
    assert all("sainik" in r["name"].lower() for r in page.table.rows())
    page.search.clear()
    qtbot.waitUntil(lambda: len(page.table.rows()) == len(product.list_products()))
    page.filter.set("out")
    page.filter.changed.emit("out")
    assert all(r["status"] == "out" for r in page.table.rows())
    assert len(page.table.rows()) == sum(p["status"] == "out" for p in product.list_products())
    page.filter.set("low")
    page.filter.changed.emit("low")
    assert all(r["status"] == "low" for r in page.table.rows())


def test_add_via_dialog(page, window):
    n = len(product.list_products())
    dlg = ProductDialog(window)
    _fill(dlg)
    pid = dlg.save()
    assert dlg.product_id == pid
    p = product.get_product_by_id(pid)
    assert p["name"] == "Test Ply" and p["opening_stock"] == 5
    assert len(page.table.rows()) == n + 1


def test_duplicate_shows_inline_error(window):
    dlg = ProductDialog(window)
    _fill(dlg, name="Dup")
    dlg.save()
    dlg2 = ProductDialog(window)
    _fill(dlg2, name="Dup")
    dlg2._accept()
    assert dlg2.error.isVisible() or not dlg2.error.isHidden()
    assert "already exists" in dlg2.error.text()
    assert dlg2.result() == 0
    assert dlg2.product_id is None


def test_blank_name_rejected(window):
    dlg = ProductDialog(window)
    dlg._accept()
    assert "name" in dlg.error.text().lower()


def test_margin_hint_goes_negative(window):
    dlg = ProductDialog(window)
    dlg.cost.set_value(200)
    dlg.price.set_value(150)
    assert "below cost" in dlg.margin.text()


def test_edit_persists_and_no_none_text(window):
    pid = product.add_product("NoBrand", None, None, None, None, 10, 20)
    dlg = ProductDialog(window, product.get_product_by_id(pid))
    assert dlg.brand.currentText() == ""
    dlg.price.set_value(25)
    dlg.save()
    assert product.get_product_by_id(pid)["selling_price"] == 25
    assert product.get_product_by_id(pid)["brand"] is None


def test_save_and_add_another(window):
    dlg = ProductDialog(window)
    _fill(dlg, name="First")
    dlg._save_another()
    assert product.list_products() and any(p["name"] == "First" for p in product.list_products())
    assert dlg.name.text() == "" and dlg.brand.currentText() == "Acme"
    _fill(dlg, name="Second")
    dlg.save()
    assert any(p["name"] == "Second" for p in product.list_products())


def test_remove_and_restore(page, monkeypatch):
    import ui.pages.products as mod
    monkeypatch.setattr(mod, "confirm", lambda *a, **k: True)
    row = page.table.rows()[0]
    page.remove(row)
    assert not product.get_product_by_id(row["id"])["is_active"]
    assert all(r["id"] != row["id"] for r in page.table.rows())
    page.show_removed.setChecked(True)
    assert any(r["id"] == row["id"] for r in page.table.rows())
    removed = next(r for r in page.table.rows() if r["id"] == row["id"])
    page.restore(removed)
    assert product.get_product_by_id(row["id"])["is_active"]


def test_open_selects_product(page):
    pid = page.table.rows()[3]["id"]
    page.open(product_id=pid)
    assert page.table.selected()["id"] == pid


def test_history_dialog(window):
    rows = product.list_products()
    pid = max(rows, key=lambda r: r["stock"])["id"]
    dlg = ProductHistoryDialog(window, pid)
    dlg.range._preset("year")
    from models import stock
    expected = stock.product_movements(pid, *dlg.range.range())
    assert len(dlg.table.rows()) == len(expected) > 0
    assert dlg.table.model.rows[0]["balance"] is not None


def test_blank_prices_rejected_zero_allowed(window):
    dlg = ProductDialog(window)
    dlg.name.setText("Priced")
    with pytest.raises(ValueError, match="cost price"):
        dlg.save()
    dlg.cost.set_value(10)
    with pytest.raises(ValueError, match="selling price"):
        dlg.save()
    dlg.price.set_value(0)
    assert dlg.save()
