import os
import zipfile

import pytest

from models import product, settings
from ui import theme


@pytest.fixture
def page(window, qtbot):
    window.navigate("settings")
    qtbot.wait(50)
    return window._pages["settings"]


def test_shop_form_loads_and_saves(page):
    assert page.shop_name.text() == settings.get("shop_name")
    assert not page.save_button.isEnabled()
    page.shop_name.setText("  Test Plywoods ")
    page.shop_gstin.setText("36abcde1234f1z5")
    page.shop_address.setPlainText("1 Main Road\nHyderabad")
    assert page.save_button.isEnabled()
    page.save_shop()
    s = settings.get_all()
    assert s["shop_name"] == "Test Plywoods"
    assert s["shop_gstin"] == "36ABCDE1234F1Z5"
    assert s["shop_address"] == "1 Main Road\nHyderabad"
    assert not page.save_button.isEnabled()


def test_theme_choice_calls_toggle(page, monkeypatch):
    calls = []
    monkeypatch.setattr(page.app, "toggle_theme", lambda: calls.append(1))
    page.set_theme(theme.name())
    assert calls == []
    page.set_theme("light" if theme.name() == "dark" else "dark")
    assert calls == [1]


def test_backup_and_restore(page, tmp_path):
    path = str(tmp_path / "b.plypro")
    assert page.backup_now(path) == path and os.path.exists(path)
    before = len(product.list_products())
    product.soft_delete_product(product.list_products()[0]["id"])
    assert len(product.list_products()) == before - 1
    assert page.restore(path) is True
    assert len(product.list_products()) == before
    assert any(r["kind"] == "Before restore" for r in page.backups.model.rows)


def test_bad_backup_leaves_data_unchanged(page, tmp_path):
    bad = tmp_path / "bad.plypro"
    bad.write_text("not a zip")
    other = tmp_path / "other.plypro"
    with zipfile.ZipFile(other, "w") as z:
        z.writestr("hello.txt", "x")
    before = [p["id"] for p in product.list_products()]
    assert page.restore(str(bad)) is False
    assert page.restore(str(other)) is False
    assert [p["id"] for p in product.list_products()] == before


def test_auto_backup_toggle_and_keep(page):
    page.auto_check.setChecked(False)
    assert settings.get("auto_backup") == "0"
    page.auto_check.setChecked(True)
    assert settings.get("auto_backup") == "1"
    page.keep_seg._buttons["30"].click()
    assert settings.get("backup_keep") == "30"


def test_backup_list_kinds(page):
    from ui.pages.settings import _kind
    assert _kind("/x/auto-2026-01-01.plypro") == "Automatic"
    assert _kind("/x/before-restore-1.db") == "Before restore"
    assert _kind("/x/before-upgrade-schema2-1.db") == "Before upgrade"
