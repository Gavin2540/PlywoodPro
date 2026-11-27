"""Read-only view of one bill, with payments, printing and a shortcut to edit it."""
import os

from PySide6.QtCore import QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QLineEdit, QVBoxLayout,
                               QWidget)

from models import bills
from ui import theme
from ui.dialogs.bill_editor import METHODS, BillEditor, find_app
from ui.table import Col, DataTable
from ui.widgets import (Badge, Card, DateField, Dialog, NumberEdit, button, confirm, divider, hbox, icon_button,
                        label, restyle, toast, vbox)
from utils.helpers import format_currency, format_date, format_qty

EPS = 0.004


def status_badge(bill):
    if bill["due"] <= EPS:
        return "Paid", "good"
    if bill["paid"] > EPS:
        return "Part paid", "info"
    return f"Due {format_currency(bill['due'], decimals=0)}", "warn"


class BillView(Dialog):
    def __init__(self, parent, bill_id):
        bill = bills.get_bill(bill_id)
        if not bill:
            raise ValueError("That bill no longer exists.")
        noun = "Sale" if bill["kind"] == "sale" else "Purchase"
        super().__init__(parent, f"{noun} {bill['bill_no']}", ok_text="Close", cancel_text="", width=760)
        self.bill_id = bill_id
        self.changed = False
        self.ok_button.setProperty("variant", None)  # Close is secondary; "Add payment" is the primary action
        restyle(self.ok_button)
        self.ok_button.setDefault(False)
        self.print_button = button("Print / Save PDF", None, "print", self.print_pdf)
        self.edit_button = button("Edit", None, "edit", self.edit)
        self.footer.insertWidget(1, self.print_button)
        self.footer.insertWidget(2, self.edit_button)
        self.slot = QVBoxLayout()
        self.slot.setContentsMargins(0, 0, 0, 0)
        self.body.addLayout(self.slot)
        self.content = None
        self.pay_amount = self.pay_card = None
        self.bill = bill
        self.render()

    # ── drawing ─────────────────────────────────────────────────────────
    def render(self):
        self.bill = b = bills.get_bill(self.bill_id)
        if b is None:  # deleted elsewhere
            self.reject()
            return
        sale = b["kind"] == "sale"
        content = QWidget()
        self.col = QVBoxLayout(content)
        self.col.setContentsMargins(0, 0, 0, 0)
        self.col.setSpacing(14)
        # header
        text, kind = status_badge(b)
        who = b["party_name"] or ("Walk-in customer" if sale else "Supplier")
        name = label(who, "heading")
        who_row = hbox(name, spacing=10)
        if b.get("party_phone"):
            who_row.addWidget(label(b["party_phone"], "muted"))
        who_row.addStretch(1)
        badge = Badge(text, kind)
        badge.setFixedHeight(22)
        head = hbox(vbox(who_row, label(format_date(b["date"]), "muted"), spacing=2), None, badge, spacing=12)
        head.setAlignment(badge, Qt.AlignTop)
        self.col.addLayout(head)
        if b["locked"]:
            self.col.addWidget(label(
                "Closed day: this bill can no longer be edited. You can still add or remove payments.", "error",
                wrap=True))

        # items
        cols = [Col("product_name", "Product", stretch=True, bold=True,
                    sub=lambda r: " · ".join(str(r[k]) for k in ("product_brand", "product_type", "product_thickness",
                                                                 "product_size") if r.get(k))),
                Col("qty", "Qty", width=110, align="right", fmt=lambda v, r: format_qty(v, r["product_unit"])),
                Col("unit_price", "Rate", width=110, align="right", fmt=lambda v, r: format_currency(v)),
                Col("amount", "Amount", width=120, align="right", fmt=lambda v, r: format_currency(v), bold=True)]
        if sale:
            cols.insert(3, Col("cost", "Cost", width=100, align="right", color=lambda r: "text3",
                               fmt=lambda v, r: format_currency(v)))
        table = DataTable(cols, sortable=False)
        table.set_rows(b["lines"])
        table.setFixedHeight(38 + max(2, min(len(b["lines"]), 8)) * 46 + 4)
        table.view.setSelectionMode(QAbstractItemView.NoSelection)
        self.col.addWidget(table)

        # totals, right aligned
        def row(caption, value, bold=False, tone=None, big=False):
            v = label(value)
            f = theme.font(18 if big else 13, QFont.Bold if (bold or big) else QFont.Normal, tabular=True)
            v.setFont(f)
            v.setStyleSheet(f"font-size:{18 if big else 13}px;" + (f"color:{theme.c(tone)};" if tone else ""))
            return hbox(None, label(caption, "muted"), 24, v, spacing=0)
        tot = vbox(spacing=5)
        tot.addLayout(row("Subtotal", format_currency(b["subtotal"])))
        if b["discount"]:
            tot.addLayout(row("Discount", "- " + format_currency(b["discount"])))
        owing = b["due"] > EPS
        tot.addLayout(row("Total", format_currency(b["total"]), bold=True, big=not owing))
        tot.addLayout(row("Paid" if sale else "Paid to supplier", format_currency(b["paid"]), tone="good" if b["paid"] else None))
        tot.addLayout(row("Balance due", format_currency(max(b["due"], 0)), bold=True, big=owing,
                          tone="bad" if owing else None))
        if sale:
            tot.addLayout(row("Profit", format_currency(b["profit"]), tone="good" if b["profit"] >= 0 else "bad"))
        left = vbox(spacing=4)
        if b["notes"]:
            left.addWidget(label("NOTES", "caption"))
            left.addWidget(label(b["notes"], "muted", wrap=True))
        left.addStretch(1)
        self.col.addLayout(hbox(left, tot, spacing=24))

        # payments
        self.col.addWidget(divider())
        self.col.addWidget(label("Payments", "heading"))
        if not b["payments"]:
            self.col.addWidget(label("No payments recorded.", "hint"))
        for p in b["payments"]:
            note = f" · {p['note']}" if p["note"] else ""
            amount = label(format_currency(p["amount"]))
            amount.setFont(theme.font(13, QFont.DemiBold, tabular=True))
            amount.setMinimumWidth(110)
            amount.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            line = hbox(label(format_date(p["date"])), label(f"{p['method']}{note}", "muted"), None, amount,
                        icon_button("trash", "Remove this payment", lambda pid=p["id"]: self.remove_payment(pid), 16),
                        spacing=14)
            self.col.addLayout(line)

        # add payment form: only while something is due
        due = max(b["due"], 0)
        self.pay_amount = self.pay_card = None
        if due > EPS:
            self.pay_amount = NumberEdit(placeholder="Amount", width=120)
            self.pay_date = DateField()
            self.pay_method = QComboBox()
            self.pay_method.addItems(METHODS)
            self.pay_note = QLineEdit()
            self.pay_note.setPlaceholderText("Note (optional)")
            self.pay_button = button("Add payment", "primary", "plus", self.add_payment)
            self.pay_button.setAutoDefault(False)
            self.pay_amount.set_value(due)
            card = Card("Add a payment" if sale else "Record a payment to supplier", padding=14, spacing=10)
            card.body.addLayout(hbox(self.pay_amount, self.pay_date, self.pay_method, self.pay_note,
                                     self.pay_button, spacing=8))
            self.col.addWidget(card)
            self.pay_card = card
            QTimer.singleShot(0, self.pay_amount.setFocus)
        self.edit_button.setEnabled(not b["locked"])
        self.edit_button.setToolTip("This day is closed" if b["locked"] else "")
        if self.content is not None:
            self.slot.removeWidget(self.content)
            self.content.deleteLater()
        self.content = content
        self.slot.addWidget(content)
        QTimer.singleShot(0, self.adjustSize)

    # ── actions ─────────────────────────────────────────────────────────
    def _changed(self):
        self.changed = True
        app = find_app(self)
        if app is not None:
            app.data_changed()
        self.render()

    def add_payment(self):
        self.error.hide()
        if self.pay_amount is None:
            return False
        try:
            bills.add_payment(self.bill_id, self.pay_amount.value(), self.pay_date.iso(),
                              self.pay_method.currentText(), self.pay_note.text().strip() or None)
        except (ValueError, PermissionError) as e:
            self.show_error(e)
            return False
        self._changed()
        toast(self, "Payment added")
        return True

    def remove_payment(self, payment_id, ask=True):
        if ask and not confirm(self, "Remove payment?", "The balance due on this bill will go up by this amount.",
                               "Remove", danger=True):
            return False
        bills.delete_payment(payment_id)
        self._changed()
        toast(self, "Payment removed")
        return True

    def edit(self):
        try:
            dlg = BillEditor(self, self.bill["kind"], bill_id=self.bill_id)
        except ValueError as e:
            self.show_error(e)
            return
        if dlg.exec():
            self.changed = True
            self.render()
            toast(self, "Changes saved")

    def default_pdf_name(self):
        return f"{self.bill['bill_no']}.pdf"

    def print_pdf(self):
        start = os.path.join(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or "",
                             self.default_pdf_name())
        path, _ = QFileDialog.getSaveFileName(self, "Save invoice", start, "PDF (*.pdf)")
        if not path:
            return None
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        return self.write_pdf(path)

    def write_pdf(self, path):
        from utils.invoice import invoice_pdf
        try:
            invoice_pdf(self.bill_id, path)
        except (OSError, ValueError) as e:
            self.show_error(f"Could not save the PDF: {e}")
            return None
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        toast(self, "PDF saved")
        return path


def show_bill(parent, bill_id):
    """Open the bill dialog. Returns True when the bill (or its payments) changed."""
    try:
        dlg = BillView(parent, bill_id)
    except ValueError as e:
        toast(parent, str(e), "bad")
        return False
    dlg.exec()
    return dlg.changed
