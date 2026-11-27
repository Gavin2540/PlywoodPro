"""Customers and suppliers: who owes you, and whom you owe."""
from models import parties, reports
from ui.dialogs.party_dialogs import WORDS, PartyDialog, SettleDialog, StatementDialog, save_table
from ui.table import Action, Col, DataTable
from ui.widgets import Card, Page, Segmented, SearchBox, button, confirm, divider, hbox, label
from utils.helpers import format_currency, format_date

KINDS = [("customer", "Customers"), ("supplier", "Suppliers")]
VIEWS = [("all", "All"), ("due", "With balance")]


def _money(v, r=None):
    return format_currency(v, decimals=0)


def _due_text(v, r):
    if v > 0.004:
        return _money(v)
    return "Settled" if r["bills"] else "—"


class PartiesPage(Page):
    title = "Customers & Suppliers"

    def __init__(self, app):
        super().__init__(app)
        self.kind = "customer"
        self.export_button = self.add_action(button("Export", None, "download", self.export))
        self.add_button = self.add_action(button("Add customer", "primary", "plus", self.add))

        self.tabs = Segmented(KINDS, "customer")
        self.tabs.changed.connect(self.set_kind)
        self.view = Segmented(VIEWS, "all")
        self.view.changed.connect(lambda _: self._apply_filter())
        self.search = SearchBox("Search name or phone…", 260)
        self.search.searched.connect(self._searched)

        self.pay_action = Action("wallet", "Receive payment", self.settle, visible=lambda r: r["due"] > 0.004)
        self.table = DataTable(
            [Col("name", "Name", stretch=True, bold=True, sub=lambda r: r.get("phone")),
             Col("bills", "Bills", width=70, align="right"),
             Col("billed", "Total business", width=125, align="right", fmt=_money),
             Col("paid", "Paid", width=110, align="right", fmt=_money, color=lambda r: "text2"),
             Col("due", "Balance due", width=130, align="right", bold=True, fmt=_due_text,
                 color=lambda r: "bad" if r["due"] > 0.004 else "text3"),
             Col("last_date", "Last bill", width=110, fmt=lambda v, r: format_date(v) if v else "—",
                 color=lambda r: "text2")],
            actions=[Action("file", "Statement", self.statement), self.pay_action,
                     Action("edit", "Edit", self.edit_row), Action("trash", "Remove", self.remove, color="bad")],
            empty=("people", "No customers yet", "Add a customer or save a sale with a name to see them here."))
        self.table.activated.connect(self.statement)
        self.table.filtered.connect(self._update_footer)
        self.footer = label("", "muted")
        self.f_billed, self.f_paid, self.f_due = label("", "heading"), label("", "heading"), label("", "heading")

        card = Card(padding=14, spacing=12)
        card.add(hbox(self.tabs, self.view, None, self.search, spacing=12))
        card.add(self.table, 1)
        card.add(divider())
        card.add(hbox(self.footer, None, label("Business", "muted"), self.f_billed, 14,
                      label("Paid", "muted"), self.f_paid, 14, label("Balance due", "muted"), self.f_due, spacing=8))
        self.root.addWidget(card, 1)

    # ── data ────────────────────────────────────────────────────────────
    def refresh(self):
        owed = reports.outstanding()
        self.subtitle_label.setText(f"Customers owe you {format_currency(owed['receivable'], decimals=0)}"
                                    f" · You owe suppliers {format_currency(owed['payable'], decimals=0)}")
        rows = parties.list_parties(self.kind)
        self.table.set_rows(rows)
        counts = {"customer": len(parties.list_parties("customer")), "supplier": len(parties.list_parties("supplier"))}
        counts[self.kind] = len(rows)
        self.tabs.set_label("customer", f"Customers ({counts['customer']})")
        self.tabs.set_label("supplier", f"Suppliers ({counts['supplier']})")
        self.view.set_label("due", f"With balance ({sum(1 for r in rows if r['due'] > 0.004)})")
        self._apply_filter()

    def _apply_filter(self):
        due_only = self.view.current() == "due"
        self.table.set_filter((lambda r: r["due"] > 0.004) if due_only else None)
        self.table.set_search(self.search.text())
        self._update_footer()

    def _searched(self, text):
        self.table.set_search(text)
        self._update_footer()

    def _update_footer(self):
        rows = self.table.rows()
        word = WORDS[self.kind]["one"]
        self.footer.setText(f"{len(rows)} {word}{'' if len(rows) == 1 else 's'} shown")
        self.f_billed.setText(_money(sum(r["billed"] for r in rows)))
        self.f_paid.setText(_money(sum(r["paid"] for r in rows)))
        self.f_due.setText(_money(sum(r["due"] for r in rows)))

    def set_kind(self, kind):
        self.kind = kind
        self.tabs.set(kind)
        w = WORDS[kind]
        self.add_button.setText(w["add"])
        self.pay_action.tooltip = w["pay"]
        plural = "customers" if kind == "customer" else "suppliers"
        self.table.empty.set_text(f"No {plural} yet", f"Add a {w['one']} or save a bill with a name to see them here.")
        self.table._empty_default = ("people", f"No {plural} yet", f"Add a {w['one']} or save a bill with a name to see them here.")
        self.table.set_rows([])
        self.refresh()

    # ── actions ─────────────────────────────────────────────────────────
    def open(self, kind=None, party_id=None, **_):
        if kind and kind != self.kind:
            self.set_kind(kind)
        if party_id:
            self.table.select_where(lambda r: r["id"] == party_id)

    def add(self):
        dlg = PartyDialog(self, self.kind)
        if dlg.exec():
            self.toast(f"{WORDS[self.kind]['one'].capitalize()} saved")
            self.table.select_where(lambda r: r["id"] == dlg.party_id)
        return dlg

    def edit_row(self, row):
        if PartyDialog(self, row["kind"], row).exec():
            self.toast("Details saved")

    def settle(self, row):
        if SettleDialog(self, row).exec():
            self.toast("Payment saved")

    def statement(self, row):
        StatementDialog(self, row).exec()

    def remove(self, row):
        text = (f"{row['name']} will be removed from your list. "
                + ("They have bills, so their account is hidden, not erased: past bills and reports stay correct."
                   if row["bills"] else "They have no bills, so they are deleted completely."))
        if confirm(self, f"Remove {row['name']}?", text, "Remove", danger=True):
            parties.delete_party(row["id"])
            self.app.data_changed()
            self.toast(f"{row['name']} removed")

    def export(self):
        rows = [[r["name"], r["phone"] or "", r["bills"], r["billed"], r["paid"], r["due"], r["last_date"] or ""]
                for r in self.table.rows()]
        title = "Customers" if self.kind == "customer" else "Suppliers"
        save_table(self, title, f"{title.lower()}.xlsx",
                   ["Name", "Phone", "Bills", "Total business", "Paid", "Balance due", "Last bill"], rows,
                   money_columns=(3, 4, 5))
