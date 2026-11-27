"""Products: catalogue, prices, margins and stock levels."""
import datetime
import os

from PySide6.QtWidgets import QCheckBox, QFileDialog

from models import product
from ui.dialogs.product_dialog import ProductDialog
from ui.dialogs.product_history import ProductHistoryDialog
from ui.table import Action, Col, DataTable
from ui.widgets import Page, Segmented, SearchBox, button, confirm, hbox, label
from utils.helpers import format_currency, format_qty
from utils.tabular import export_rows


def _spec(r):
    return " · ".join(str(r[k]) for k in ("brand", "type", "thickness", "size") if r.get(k))


def _status(r):
    if not r["is_active"]:
        return "Removed", "neutral"
    return {"ok": ("In stock", "good"), "low": ("Low", "warn"), "out": ("Out of stock", "bad")}[r["status"]]


def _stock_color(r):
    if not r["is_active"]:
        return "text3"
    return {"ok": "text", "low": "warn", "out": "bad"}[r["status"]]


class ProductsPage(Page):
    title = "Products"

    def __init__(self, app):
        super().__init__(app)
        self.add_action(button("Export", None, "download", self.export))
        self.add_action(button("Add product", "primary", "plus", self.add))

        self.search = SearchBox("Search products…", 280)
        self.filter = Segmented([("all", "All"), ("low", "Low stock"), ("out", "Out of stock")], "all")
        self.show_removed = QCheckBox("Show removed")
        self.root.addLayout(hbox(self.search, self.filter, None, self.show_removed, spacing=12))

        self.table = DataTable([
            Col("name", "Product", stretch=True, bold=True, sub=_spec),
            Col("purchase_price", "Cost", width=88, align="right", fmt=lambda v, r: _money(v),
                color=lambda r: "text2"),
            Col("selling_price", "Selling price", width=118, align="right", fmt=lambda v, r: _money(v)),
            Col("margin", "Margin", width=96, align="right", fmt=_margin_text, sub=_margin_pct,
                color=lambda r: "bad" if r["margin"] < 0 else "good" if r["is_active"] else "text3"),
            Col("stock", "In stock", width=100, align="right", fmt=lambda v, r: format_qty(v, r["unit"]),
                color=_stock_color),
            Col("stock_value", "Stock value", width=104, align="right",
                fmt=lambda v, r: format_currency(v, decimals=0), color=lambda r: "text2"),
            Col("status", "Status", width=104, badge=_status, sort=lambda r: (r["is_active"], r["status"]))],
            actions=[Action("history", "History", self.history),
                     Action("edit", "Edit", self.edit),
                     Action("trash", "Remove", self.remove, visible=lambda r: bool(r["is_active"]), color="bad"),
                     Action("refresh", "Restore", self.restore, visible=lambda r: not r["is_active"], color="good")],
            menu=self._menu,
            empty=("products", "No products yet", "Add your first product to start tracking stock and margins."))
        self.root.addWidget(self.table, 1)
        self.footer = label("", "muted")
        self.root.addLayout(hbox(self.footer, None))

        self.search.searched.connect(self._search)
        self.filter.changed.connect(lambda _: self._apply())
        self.show_removed.toggled.connect(lambda _: self._apply())
        self.table.activated.connect(self.edit)
        self._rows = []

    # ── data ────────────────────────────────────────────────────────────
    def refresh(self):
        self._rows = product.list_products(include_inactive=True)
        for r in self._rows:
            r["margin"] = r["selling_price"] - r["purchase_price"]
        active = [r for r in self._rows if r["is_active"]]
        worth = sum(r["stock_value"] for r in active)
        n = len(active)
        self.subtitle_label.setText(
            f"{n} product{'s' if n != 1 else ''} · stock worth {format_currency(worth, decimals=0)}")
        self.table.set_rows(self._rows)
        self._apply()

    def _search(self, text):
        self.table.set_search(text)
        self._update_footer()

    def _apply(self):
        key, removed = self.filter.current() or "all", self.show_removed.isChecked()
        self.table.set_filter(lambda r: (removed or r["is_active"]) and key in ("all", r["status"]))
        self.refresh_counts()
        self._update_footer()

    def refresh_counts(self):
        removed = self.show_removed.isChecked()
        pool = [r for r in self._rows if removed or r["is_active"]]
        self.filter.set_label("all", f"All ({len(pool)})")
        self.filter.set_label("low", f"Low stock ({sum(r['status'] == 'low' for r in pool)})")
        self.filter.set_label("out", f"Out of stock ({sum(r['status'] == 'out' for r in pool)})")

    def _update_footer(self):
        rows = self.table.rows()
        cost = sum(r["stock_value"] for r in rows)
        sell = sum(r["stock"] * r["selling_price"] for r in rows)
        n = len(rows)
        self.footer.setText(
            f"Showing {n} product{'s' if n != 1 else ''}   ·   stock worth {format_currency(cost, decimals=0)} at cost"
            f"   ·   {format_currency(sell, decimals=0)} at selling price")

    def open(self, new=False, product_id=None, **_):
        if new:
            self.add()
        elif product_id is not None:
            row = next((r for r in self._rows if r["id"] == product_id), None)
            if row and not row["is_active"]:
                self.show_removed.setChecked(True)
            self.filter.set("all")
            self.search.clear()
            self.table.set_search("")
            self._apply()
            self.table.select_where(lambda r: r["id"] == product_id)

    # ── actions ─────────────────────────────────────────────────────────
    def _menu(self, r):
        items = [("History", lambda: self.history(r)), ("Edit", lambda: self.edit(r)), None]
        if r["is_active"]:
            items += [("Sell this", lambda: self.app.navigate("sales", new=True, product_id=r["id"])),
                      ("Buy more", lambda: self.app.navigate("purchases", new=True, product_id=r["id"])),
                      None, ("Remove", lambda: self.remove(r))]
        else:
            items.append(("Restore", lambda: self.restore(r)))
        return items

    def add(self):
        dlg = ProductDialog(self)
        if dlg.exec():
            self.toast("Product saved")
            self.table.select_where(lambda r: r["id"] == dlg.product_id)
        elif dlg.product_id is not None:  # "Save and add another" used, then closed
            self.app.data_changed()

    def edit(self, r):
        dlg = ProductDialog(self, product.get_product_by_id(r["id"]))
        if dlg.exec():
            self.toast("Product updated")

    def history(self, r):
        ProductHistoryDialog(self, r["id"]).exec()

    def remove(self, r):
        text = ("It will be hidden from the product list and bill pickers. "
                "Past sales, purchases and stock history are kept, and you can restore it any time.")
        if r["stock"] > 0:
            text = f"{format_qty(r['stock'], r['unit'])} is still in stock. " + text
        if confirm(self, f"Remove {r['name']}?", text, "Remove", danger=True):
            product.soft_delete_product(r["id"])
            self.app.data_changed()
            self.toast("Product removed")

    def restore(self, r):
        product.restore_product(r["id"])
        self.app.data_changed()
        self.toast("Product restored")

    def export(self):
        rows = self.table.rows()
        if not rows:
            self.toast("Nothing to export", "warn")
            return
        default = os.path.join(os.path.expanduser("~"), f"products-{datetime.date.today().isoformat()}.xlsx")
        path, _ = QFileDialog.getSaveFileName(self, "Export products", default, "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        data = [[r["name"], r["brand"] or "", r["type"] or "", r["thickness"] or "", r["size"] or "",
                 r["purchase_price"], r["selling_price"], r["margin"], r["stock"], r["unit"],
                 r["stock_value"], _status(r)[0]] for r in rows]
        try:
            export_rows(path, "Products", ["Product", "Brand", "Type", "Thickness", "Size", "Cost price",
                                           "Selling price", "Margin", "In stock", "Unit", "Stock value", "Status"],
                        data, money_columns=(5, 6, 7, 10))
        except OSError as e:
            self.toast(f"Could not save the file: {e}", "bad")
            return
        self.toast("Exported " + os.path.basename(path))


def _margin_text(v, r):
    return ("-" if v < 0 else "") + _money(abs(v))


def _margin_pct(r):
    return f"{r['margin'] / r['purchase_price'] * 100:.1f}%" if r["purchase_price"] > 0 else None


def _money(v):
    """Whole rupees when there are no paise, otherwise two decimals."""
    return format_currency(v, decimals=0 if abs(v - round(v)) < 0.005 else 2)
