"""Dialogs for customers and suppliers: add/edit, receive/pay money, and the account statement."""
import datetime

from PySide6.QtWidgets import QComboBox, QFileDialog, QFrame, QLineEdit, QPlainTextEdit

from PySide6.QtCore import Qt

from models import bills, parties
from ui.table import Col, DataTable
from ui.widgets import (Dialog, DateField, DateRangeBar, NumberEdit, button, field, hbox, label, restyle, toast, vbox)
from utils.helpers import format_currency, format_date
from utils.tabular import export_rows

METHODS = ["Cash", "UPI", "Bank transfer", "Cheque", "Card"]

WORDS = {
    "customer": {"one": "customer", "pay": "Receive payment", "new": "New sale", "page": "sales",
                 "owed": "Owes you", "add": "Add customer"},
    "supplier": {"one": "supplier", "pay": "Pay supplier", "new": "New purchase", "page": "purchases",
                 "owed": "You owe", "add": "Add supplier"},
}


def _changed(dialog):
    win = dialog.parent()
    if win is not None and hasattr(win, "data_changed"):
        win.data_changed()


def save_table(parent, title, default_name, headers, rows, money_columns=()):
    """Ask where to save, then write rows to Excel/CSV. Returns True when a file was written."""
    if not rows:
        toast(parent, "Nothing to export", "warn")
        return False
    path, _ = QFileDialog.getSaveFileName(parent, title, default_name, "Excel (*.xlsx);;CSV (*.csv)")
    if not path:
        return False
    try:
        export_rows(path, title, headers, rows, money_columns)
    except OSError as e:
        toast(parent, f"Could not save the file: {e}", "bad")
        return False
    toast(parent, "File saved")
    return True


class PartyDialog(Dialog):
    """Add or edit a customer or supplier. ``save()`` writes; ``party_id`` is set afterwards."""

    def __init__(self, parent, kind, party=None):
        w = WORDS[kind]
        editing = party is not None
        super().__init__(parent, f"Edit {w['one']}" if editing else w["add"],
                         "Bills you save for this name are kept under their account." if not editing else None,
                         ok_text="Save", width=460)
        self.kind, self.party = kind, party
        self.party_id = party["id"] if editing else None
        self.name = QLineEdit(party["name"] if editing else "")
        self.name.setPlaceholderText("Name")
        self.phone = QLineEdit((party.get("phone") or "") if editing else "")
        self.phone.setPlaceholderText("Phone number (optional)")
        self.address = QLineEdit((party.get("address") or "") if editing else "")
        self.address.setPlaceholderText("Address (optional)")
        self.notes = QPlainTextEdit((party.get("notes") or "") if editing else "")
        self.notes.setPlaceholderText("Anything worth remembering (optional)")
        self.notes.setFixedHeight(70)
        self.body.addWidget(field("Name *", self.name))
        self.body.addWidget(field("Phone", self.phone))
        self.body.addWidget(field("Address", self.address))
        self.body.addWidget(field("Notes", self.notes))
        self.on_accept = self.save
        self.name.setFocus()

    def save(self):
        self.party_id = parties.save_party(self.kind, self.name.text(), self.phone.text(), self.address.text(),
                                           self.notes.toPlainText(), self.party_id)
        _changed(self)
        return True


class SettleDialog(Dialog):
    """Take a payment from a customer or pay a supplier, against their oldest unpaid bills first."""

    def __init__(self, parent, party):
        w = WORDS[party["kind"]]
        super().__init__(parent, f"{w['pay']}", party["name"], ok_text="Save payment", width=440)
        self.party = party
        self.due = self._current_due()
        self.balance = label(format_currency(self.due, decimals=2), "title")
        self.balance.setStyleSheet("font-size:24px; font-weight:700;")
        self.amount = NumberEdit(self.due, placeholder="0.00")
        self.date = DateField()
        self.method = QComboBox()
        self.method.addItems(METHODS)
        self.note = QLineEdit()
        self.note.setPlaceholderText("Optional")
        self.body.addLayout(vbox(label("BALANCE DUE", "caption"), self.balance, spacing=2))
        self.body.addWidget(field("Amount (₹)", self.amount,
                                  "Applied to the oldest unpaid bills first."))
        self.preview = label("", "hint")
        self.body.addWidget(self.preview)
        self.amount.textChanged.connect(self._preview)
        self._preview()
        date_f, method_f = field("Date", self.date), field("Method", self.method)
        row = hbox(date_f, method_f, spacing=12)
        row.setStretch(1, 1)
        row.setAlignment(date_f, Qt.AlignTop)
        row.setAlignment(method_f, Qt.AlignTop)
        self.body.addLayout(row)
        self.body.addWidget(field("Note", self.note))
        self.on_accept = self.save
        self.amount.setFocus()

    def _preview(self, *_):
        amount = self.amount.value()
        open_bills = sorted(bills.list_bills(party_id=self.party["id"], only_due=True),
                            key=lambda b: (b["date"], b["id"]))
        if amount <= 0:
            self.preview.setText("Enter the amount received." if self.party["kind"] == "customer" else "Enter the amount paid.")
            return
        if amount > self.due + 0.004:
            self.preview.setText("More than the balance due.")
            return
        left, cleared = amount, 0
        for b in open_bills:
            if left + 0.004 >= b["due"]:
                left -= b["due"]
                cleared += 1
            else:
                break
        remaining = round(self.due - amount, 2)
        text = f"Clears {cleared} bill{'' if cleared == 1 else 's'}, " if cleared else "Clears no bill fully, "
        text += "nothing left due" if remaining <= 0.004 else f"leaves {format_currency(remaining, decimals=0)} due"
        self.preview.setText(text)

    def _current_due(self):
        rows = [p for p in parties.list_parties(self.party["kind"]) if p["id"] == self.party["id"]]
        return rows[0]["due"] if rows else 0.0

    def save(self):
        bills.settle_party(self.party["id"], self.amount.value(), self.date.iso(),
                           self.method.currentText(), self.note.text().strip() or None)
        _changed(self)
        return True


class _Stat(QFrame):
    def __init__(self, caption, hint):
        super().__init__()
        self.setObjectName("Card")
        self.value = label("—", "title")
        self.value.setStyleSheet("font-size:20px; font-weight:700;")
        self.hint = label(hint, "hint")
        lay = vbox(label(caption.upper(), "caption"), self.value, self.hint, spacing=3, margins=(14, 10, 14, 10))
        self.setLayout(lay)

    def set(self, amount, tone=None):
        from ui import theme
        self.value.setText(format_currency(amount, decimals=0))
        self.value.setStyleSheet(f"font-size:20px; font-weight:700;" + (f"color:{theme.c(tone)};" if tone else ""))


class StatementDialog(Dialog):
    """Everything one customer or supplier has bought or sold, with a running balance due."""

    def __init__(self, parent, party):
        w = WORDS[party["kind"]]
        contact = "  ·  ".join(x for x in (party.get("phone"), party.get("address")) if x)
        super().__init__(parent, party["name"], contact or None, ok_text="Close", cancel_text="", width=880)
        self.party, self.words = party, w
        self.ok_button.setProperty("variant", None)
        restyle(self.ok_button)
        self.rows = []

        self.range = DateRangeBar("year", presets=[("30d", "30 days"), ("year", "This year")])
        self.range.changed.connect(lambda *_: self.reload())
        self.s_total = _Stat("Total business", "in this period")
        self.s_paid = _Stat("Paid", "in this period")
        self.s_due = _Stat("Balance due", "on all bills")
        self.body.addLayout(hbox(self.s_total, self.s_paid, self.s_due, spacing=12))
        self.body.addLayout(hbox(label("Bills", "heading"), None, self.range))
        self.table = DataTable(
            [Col("date", "Date", width=110, fmt=lambda v, r: format_date(v)),
             Col("bill_no", "Bill no", width=110, bold=True),
             Col("summary", "Items", stretch=True),
             Col("total", "Amount", width=110, align="right", fmt=lambda v, r: format_currency(v, decimals=0)),
             Col("paid", "Paid", width=110, align="right", fmt=lambda v, r: format_currency(v, decimals=0),
                 color=lambda r: "text2"),
             Col("due", "Status", width=120, align="right", badge=_status_badge)],
            empty=("file", "No bills in this period", "Pick a longer period to see earlier bills."))
        self.table.setMinimumHeight(260)
        self.table.activated.connect(self.open_bill)
        self.body.addWidget(self.table, 1)

        self.footer.insertWidget(0, button("Export", None, "download", self.export))
        self.footer.insertWidget(1, button(w["new"], None, "plus", self.new_bill))
        self.pay_button = button(w["pay"], "primary", "wallet", self.settle)
        self.footer.insertWidget(self.footer.count() - 1, self.pay_button)
        self.reload()

    def reload(self):
        start, end = self.range.range()
        self.rows = bills.list_bills(party_id=self.party["id"], date_from=start, date_to=end)
        self.table.set_rows(self.rows)
        total = sum(r["total"] for r in self.rows)
        paid = sum(r["paid"] for r in self.rows)
        due = sum(r["due"] for r in bills.list_bills(party_id=self.party["id"]))
        self.due = round(due, 2)
        self.s_total.set(total)
        self.s_paid.set(paid)
        self.s_due.set(self.due, "bad" if self.due > 0.004 else None)
        self.pay_button.setVisible(self.due > 0.004)

    def settle(self):
        dlg = SettleDialog(self, self.party)
        if dlg.exec():
            toast(self.parent(), "Payment saved")
            self.reload()

    def new_bill(self):
        win = self.parent()
        self.accept()
        win.navigate(self.words["page"], new=True, party_name=self.party["name"])

    def open_bill(self, row):
        try:
            from ui.dialogs.bill_view import show_bill
        except ImportError:
            toast(self, "Bill view is not available yet", "warn")
            return
        if show_bill(self, row["id"]):
            self.reload()
            _changed(self)

    def export(self):
        rows = [[r["date"], r["bill_no"], r["summary"] or "", r["total"], r["paid"], r["due"]] for r in self.rows]
        save_table(self, f"Statement {self.party['name']}", f"statement-{self.party['name']}.xlsx",
                   ["Date", "Bill no", "Items", "Amount", "Paid", "Due"], rows, money_columns=(3, 4, 5))


def _status_badge(row):
    if row["due"] > 0.004:
        return f"Due {format_currency(row['due'], decimals=0)}", "warn"
    return "Paid", "neutral"
