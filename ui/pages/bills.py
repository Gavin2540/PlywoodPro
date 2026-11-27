"""Sales and Purchases: one page class parameterised by bill kind."""
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFileDialog, QFrame

from models import bills, stock
from ui import theme
from ui.dialogs.bill_editor import BillEditor
from ui.dialogs.bill_view import show_bill
from ui.table import Action, Col, DataTable
from ui.widgets import DateRangeBar, Page, SearchBox, Segmented, button, confirm, hbox, label, vbox
from utils.helpers import format_currency, format_date, format_qty

EPS = 0.004


class BillsPage(Page):
    kind = "sale"
    noun = "sale"
    default_range = "7d"

    def __init__(self, app):
        super().__init__(app)
        sale = self.kind == "sale"
        self.who = "Customer" if sale else "Supplier"
        self.walk_in = "Walk-in customer" if sale else "Supplier"
        self.add_action(button("Export", None, "download", self.export, tooltip="Save the visible rows to Excel or CSV"))
        self.new_button = self.add_action(button(f"New {self.noun}", "primary", "plus", self.new,
                                                 tooltip="Ctrl+N" if sale else "Ctrl+Shift+N"))

        self.range = DateRangeBar(self.default_range, [("today", "Today"), ("7d", "7 days"), ("30d", "30 days"), ("month", "Month"),
                                      ("year", "Year")])
        self.range.changed.connect(lambda *_: self.refresh())
        self.search = SearchBox("Search bills…", width=210)
        self.search.searched.connect(self._filter_changed)
        self.filter = Segmented([("all", "All"), ("unpaid", "Unpaid")], "all")
        self.filter.changed.connect(self._filter_changed)
        self.root.addLayout(hbox(self.range, None, self.search, self.filter, spacing=10))

        cols = [
            Col("date", "Date", width=112, fmt=lambda v, r: format_date(v), numeric=True,
                sub=lambda r: "Closed day" if r.get("locked") else None),
            Col("party_name", "Bill", stretch=True, bold=True,
                fmt=lambda v, r: v or self.walk_in,
                sub=lambda r: " · ".join(x for x in (r["bill_no"], r["summary"]) if x)),
            Col("qty", "Items / qty", width=120, align="right",
                fmt=lambda v, r: f"{r['items']} item{'s' if r['items'] != 1 else ''} · {format_qty(v)}"),
            Col("total", "Amount", width=124, align="right", bold=True,
                fmt=lambda v, r: format_currency(v, decimals=0),
                sub=lambda r: f"{format_currency(r['due'], decimals=0)} due" if r["due"] > EPS else None),
        ]
        if sale:
            cols.append(Col("profit", "Profit", width=112, align="right",
                            fmt=lambda v, r: format_currency(v, decimals=0),
                            color=lambda r: "good" if r["profit"] >= 0 else "bad"))
        cols.append(Col("due", "Status", width=116, badge=self._badge))
        actions = [Action("file", "View", lambda r: self.view_bill(r["id"])),
                   Action("edit", "Edit", lambda r: self.edit_bill(r["id"])),
                   Action("trash", "Delete", self.delete_bill, color="bad")]
        self.table = DataTable(
            cols, actions=actions,
            empty=("sale" if sale else "purchase", f"No {self.noun}s in this period",
                   f"Record a {self.noun} or widen the dates."))
        self.table.activated.connect(lambda r: self.view_bill(r["id"]))
        self.table.filtered.connect(self._update_summary)
        self.root.addWidget(self.table, 1)

        # footer totals for the visible rows
        self.foot = {}
        bar = QFrame()
        bar.setObjectName("Card")
        lay = hbox(label("VISIBLE BILLS", "caption"), None, spacing=28, margins=(16, 10, 16, 10))
        keys = [("amount", "Amount", None)]
        if sale:
            keys.append(("profit", "Profit", None))
        keys += [("paid", "Paid", "good"), ("due", "Due", "bad")]
        for key, text, tone in keys:
            value = label("")
            value.setFont(theme.font(15, QFont.Bold, tabular=True))
            self.foot[key] = (value, tone)
            lay.addLayout(vbox(label(text.upper(), "caption"), value, spacing=1))
        bar.setLayout(lay)
        self.foot_label = lay.itemAt(0).widget()
        self.root.addWidget(bar)
        self._range_widened = False

    # ── table helpers ───────────────────────────────────────────────────
    @staticmethod
    def _badge(r):
        if r["due"] <= EPS:
            return "Paid", "good"
        if r["paid"] > EPS:
            return "Part paid", "info"
        return f"Due {format_currency(r['due'], decimals=0)}", "warn"

    def _unpaid_only(self):
        return self.filter.current() == "unpaid"

    def _filter_changed(self, *_):
        self.table.set_search(self.search.text())
        self.table.set_filter((lambda r: r["due"] > EPS) if self._unpaid_only() else None)

    def _update_summary(self):
        rows = self.table.rows()
        amount = sum(r["total"] for r in rows)
        paid = sum(r["paid"] for r in rows)
        due = sum(max(r["due"], 0) for r in rows)
        n = len(rows)
        parts = [f"{n} bill{'s' if n != 1 else ''}", format_currency(amount, decimals=0)]
        if due > EPS:
            parts.append(f"{format_currency(due, decimals=0)} due")
        self.subtitle_label.setText(" · ".join(parts))
        values = {"amount": amount, "profit": sum(r["profit"] for r in rows), "paid": paid, "due": due}
        for key, (lb, tone) in self.foot.items():
            v = values[key]
            lb.setText(format_currency(v, decimals=0))
            color = theme.c(tone) if tone and (key != "due" or v > EPS) and (key != "paid" or v > EPS) else None
            if key == "profit":
                color = theme.c("good" if v >= 0 else "bad")
            lb.setStyleSheet(f"color:{color};" if color else "")

    # ── data ────────────────────────────────────────────────────────────
    def refresh(self):
        start, end = self.range.range()
        rows = bills.list_bills(self.kind, start, end)
        locked = stock.locked_days(start, end)  # once per refresh, not per row
        for r in rows:
            r["locked"] = r["date"] in locked
        self.table.set_rows(rows)
        self._filter_changed()

    # ── actions ─────────────────────────────────────────────────────────
    def _notify(self, text, kind="good"):
        self.toast(text, kind)

    def _run_editor(self, **kw):
        """Open the editor; returns the saved bill id or None."""
        dlg = BillEditor(self, self.kind, **kw)
        if dlg.exec():
            return dlg.bill_id
        return None

    def new(self, product_id=None, party_name=None):
        bill_id = self._run_editor(product_id=product_id, party_name=party_name)
        if bill_id:
            self.app.data_changed()
            self._notify(f"{self.noun.capitalize()} saved")
            self._select(bill_id)

    def edit_bill(self, bill_id):
        try:
            saved = self._run_editor(bill_id=bill_id)
        except ValueError as e:
            self._notify(str(e), "bad")
            return
        if saved:
            self.app.data_changed()
            self._notify(f"{self.noun.capitalize()} updated")
            self._select(saved)

    def view_bill(self, bill_id):
        if show_bill(self, bill_id):
            self.app.data_changed()
        self._select(bill_id)

    def delete_bill(self, row, ask=True):
        who = row["party_name"] or self.walk_in
        if ask and not confirm(
                self, f"Delete {row['bill_no']}?",
                f"This removes the {self.noun} to {who} on {format_date(row['date'])} and its payments. "
                + ("The items go back into stock." if self.kind == "sale" else "The items come out of stock."),
                "Delete", danger=True):
            return False
        try:
            bills.delete_bill(row["id"])
        except (ValueError, PermissionError) as e:
            self._notify(str(e), "bad")
            return False
        self.app.data_changed()
        self._notify(f"{self.noun.capitalize()} deleted")
        return True

    def _select(self, bill_id):
        """Select a bill's row, widening the date range first when it falls outside."""
        bill = bills.get_bill(bill_id)
        if not bill:
            return False
        start, end = self.range.range()
        if not (start <= bill["date"] <= end):
            self.range.set_range(min(start, bill["date"]), max(end, bill["date"]))
        if not self.table.select_where(lambda r: r["id"] == bill_id):
            self.refresh()
            return self.table.select_where(lambda r: r["id"] == bill_id)
        return True

    def export(self):
        start, end = self.range.range()
        path, _ = QFileDialog.getSaveFileName(self, "Export bills", f"{self.noun}s-{start}-to-{end}.xlsx",
                                              "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return None
        return self.export_to(path)

    def export_to(self, path):
        from utils.tabular import export_rows
        sale = self.kind == "sale"
        headers = ["Date", "Bill no", self.who, "Items", "Qty", "Amount"] + (["Profit"] if sale else []) + ["Paid", "Due"]
        rows = []
        for r in self.table.rows():
            rows.append([format_date(r["date"]), r["bill_no"], r["party_name"] or self.walk_in, r["items"],
                         r["qty"], r["total"]] + ([r["profit"]] if sale else []) + [r["paid"], max(r["due"], 0)])
        money = [5, 6, 7, 8] if sale else [5, 6, 7]
        try:
            export_rows(path, f"{self.noun.capitalize()}s", headers, rows, money)
        except OSError as e:
            self._notify(f"Could not save the file: {e}", "bad")
            return None
        self._notify(f"Exported {len(rows)} bills")
        return path

    def open(self, new=False, product_id=None, bill_id=None, party_name=None):
        if new:
            self.new(product_id=product_id, party_name=party_name)
        elif bill_id:
            self.filter.set("all")
            self.search.clear()
            self._filter_changed()
            if self._select(bill_id):
                self.view_bill(bill_id)


class SalesPage(BillsPage):
    kind, noun = "sale", "sale"
    title = "Sales"


class PurchasesPage(BillsPage):
    kind, noun = "purchase", "purchase"
    default_range = "30d"
    title = "Purchases"
