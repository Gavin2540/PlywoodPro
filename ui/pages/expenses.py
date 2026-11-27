"""Expenses: day-to-day shop costs, with a breakdown of where the money went."""
import datetime

from PySide6.QtCore import Qt

from PySide6.QtWidgets import QComboBox, QFileDialog, QLabel, QLineEdit, QVBoxLayout, QWidget

from models import expense, reports
from ui import theme
from ui.charts import DonutChart
from ui.table import Action, Col, DataTable
from ui.widgets import (Card, DateField, DateRangeBar, Dialog, NumberEdit, Page, SearchBox, SearchCombo, button,
                        confirm, divider, field, hbox, label, toast)
from utils.helpers import format_currency, format_date
from utils.tabular import export_rows

ALL = "All categories"
PRESETS = [("7d", "7 days"), ("30d", "30 days"), ("month", "Month"), ("year", "Year")]
_KINDS = ["info", "accent", "warn", "good", "neutral"]


class ExpenseDialog(Dialog):
    """Add or edit one expense. ``save()`` does the work so tests need no exec()."""

    def __init__(self, parent, expense_row=None):
        editing = expense_row is not None
        super().__init__(parent, "Edit expense" if editing else "Add expense",
                         "Money paid out for the shop, such as transport or rent.", ok_text="Save", width=440)
        self.expense = expense_row
        self.saved_id = None
        self.date = DateField(expense_row["date"] if editing else None)
        self.category = SearchCombo("Choose or type a category", free_text=True)
        self.category.set_items([(c, c) for c in expense.categories()])
        self.amount = NumberEdit(expense_row["amount"] if editing else None, placeholder="0.00")
        self.note = QLineEdit()
        self.note.setPlaceholderText("What was it for? (optional)")
        if editing:
            self.category.setEditText(expense_row["category"])
            self.note.setText(expense_row.get("note") or "")
        self.body.addWidget(field("Amount (₹)", self.amount))
        date_f, cat_f = field("Date", self.date), field("Category", self.category)
        row = hbox(date_f, cat_f, spacing=12)
        row.setStretch(1, 1)
        row.setAlignment(date_f, Qt.AlignTop)
        row.setAlignment(cat_f, Qt.AlignTop)
        self.body.addLayout(row)
        self.body.addWidget(field("Note", self.note))
        self.on_accept = self.save
        if not editing:
            self.another_button = button("Save and add another", None, None, self._save_another)
            self.another_button.setAutoDefault(False)
            self.footer.insertWidget(1, self.another_button)
        self.setTabOrder(self.amount, self.date)
        self.amount.setFocus()

    def save(self, another=False):
        """Validate and write. Returns True (close) or False (stay open, for 'add another')."""
        category = self.category.text()
        amount = self.amount.value()
        if self.expense:
            expense.update_expense(self.expense["id"], self.date.iso(), category, amount, self.note.text())
            self.saved_id = self.expense["id"]
        else:
            self.saved_id = expense.insert_expense(self.date.iso(), category, amount, self.note.text())
        win = self.parent()
        if win is not None and hasattr(win, "data_changed"):
            win.data_changed()
        if another:
            toast(self, "Expense saved")
            self.amount.clear()
            self.note.clear()
            self.amount.setFocus()
            return False
        return True

    def _save_another(self):
        self.error.hide()
        try:
            self.save(another=True)
        except (ValueError, PermissionError) as e:
            self.show_error(e)


class ExpensesPage(Page):
    title = "Expenses"

    def __init__(self, app):
        super().__init__(app)
        self.add_action(button("Export", None, "download", self.export))
        self.add_action(button("Add expense", "primary", "plus", lambda: self.add(), tooltip="Ctrl+E"))

        self.range = DateRangeBar("30d", presets=PRESETS)
        self.range.changed.connect(lambda *_: self.refresh())
        self.category = QComboBox()
        self.category.setMinimumWidth(170)
        self.category.addItem(ALL)
        self.category.currentIndexChanged.connect(lambda *_: self.refresh())
        self.search = SearchBox("Search notes…", 220)
        self.search.searched.connect(self._searched)

        self.table = DataTable(
            [Col("date", "Date", width=120, fmt=lambda v, r: format_date(v), color=lambda r: "text2"),
             Col("category", "Category", width=170, badge=self._badge),
             Col("note", "Note", stretch=True),
             Col("amount", "Amount", width=130, align="right", bold=True,
                 fmt=lambda v, r: format_currency(v, decimals=0 if float(v).is_integer() else 2))],
            actions=[Action("edit", "Edit", self.edit_row), Action("trash", "Delete", self.delete_row, color="bad")],
            empty=("expense", "No expenses in this period", "Add an expense to see it here."))
        self.table.activated.connect(self.edit_row)
        self.table.filtered.connect(self._update_footer)
        self.footer = label("", "muted")
        self.footer_total = label("", "heading")

        left = Card(padding=14, spacing=12)
        self.search.setFixedWidth(16777215)
        left.add(hbox(self.range, None, spacing=10))
        left.add(hbox(self.category, self.search, spacing=10))
        left.add(self.table, 1)
        left.add(divider())
        left.add(hbox(self.footer, None, label("Total shown", "muted"), self.footer_total, spacing=10))

        self.donut = DonutChart(height=190, center_caption="Spent", legend=False)
        self.top_line = label("", "muted", wrap=True)
        self.avg_line = label("", "muted", wrap=True)
        self.count_line = label("", "muted", wrap=True)
        self.side = Card("Where the money went")
        self.side.add(self.donut)
        self.legend = QVBoxLayout()
        self.legend.setSpacing(2)
        self.side.add(self.legend)
        self.side.add(divider())
        self.side.add(self.avg_line)
        self.side.add(self.top_line)
        self.side.add(self.count_line)
        self.side.body.addStretch(1)
        self.side.setFixedWidth(360)
        self.root.addLayout(hbox(left, self.side, spacing=16), 1)
        self._cats = []

    # ── data ────────────────────────────────────────────────────────────
    def refresh(self):
        start, end = self.range.range()
        self._sync_categories()
        cat = self.category.currentText()
        cat = None if cat == ALL else cat
        rows = expense.list_expenses(start, end, cat)
        self.table.set_rows(rows)
        self.table.set_search(self.search.text())
        self._update_footer()

        total = round(sum(r["amount"] for r in rows), 2)
        self.subtitle_label.setText(
            f"{format_currency(total, decimals=0)} in this period · {len(rows)} {'entry' if len(rows) == 1 else 'entries'}")

        breakdown = reports.expense_breakdown(start, end)
        self.donut.set_data([(b["category"], b["amount"]) for b in breakdown])
        self._legend(breakdown)
        days = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(start)).days + 1
        grand = sum(b["amount"] for b in breakdown)
        entries = sum(b["entries"] for b in breakdown)
        self.avg_line.setText(f"Daily average  {format_currency(grand / max(days, 1), decimals=0)}")
        if breakdown:
            top = breakdown[0]
            self.top_line.setText(f"Biggest: {top['category']}  {format_currency(top['amount'], decimals=0)}")
        else:
            self.top_line.setText("Biggest: none yet")
        self.count_line.setText(f"{entries} {'entry' if entries == 1 else 'entries'} over {days} days")

    def _legend(self, breakdown):
        while self.legend.count():
            item = self.legend.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        total = sum(b["amount"] for b in breakdown) or 1
        colors = theme.chart_colors()
        shown = breakdown[:5]
        rest = sum(b["amount"] for b in breakdown[5:])
        rows = [(b["category"], b["amount"]) for b in shown] + ([("Other", rest)] if rest else [])
        for i, (name, amt) in enumerate(rows):
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background:{colors[i % len(colors)]}; border-radius:3px;")
            pct = label(f"{amt / total * 100:.0f}%", "hint")
            pct.setFixedWidth(34)
            pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amount = label(format_currency(amt, decimals=0))
            amount.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row = QWidget()
            row.setFixedHeight(26)
            row.setLayout(hbox(dot, label(name), None, amount, pct, spacing=10))
            self.legend.addWidget(row)

    def _sync_categories(self):
        cats = expense.categories()
        if cats == self._cats:
            return
        keep = self.category.currentText()
        self._cats = cats
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem(ALL)
        self.category.addItems(cats)
        i = self.category.findText(keep)
        self.category.setCurrentIndex(max(i, 0))
        self.category.blockSignals(False)

    def _badge(self, row):
        c = row["category"]
        i = self._cats.index(c) if c in self._cats else 0
        return c, _KINDS[i % len(_KINDS)]

    def _searched(self, text):
        self.table.set_search(text)
        self._update_footer()

    def _update_footer(self):
        rows = self.table.rows()
        total = round(sum(r["amount"] for r in rows), 2)
        self.footer.setText(f"{len(rows)} {'entry' if len(rows) == 1 else 'entries'} shown")
        self.footer_total.setText(format_currency(total, decimals=0 if float(total).is_integer() else 2))

    # ── actions ─────────────────────────────────────────────────────────
    def open(self, new=False, **_):
        if new:
            self.add()

    def add(self):
        dlg = ExpenseDialog(self)
        if dlg.exec():
            self.toast("Expense saved")
        return dlg

    def edit_row(self, row):
        dlg = ExpenseDialog(self, row)
        if dlg.exec():
            self.toast("Expense updated")

    def delete_row(self, row):
        text = f"{format_currency(row['amount'], decimals=0)} for {row['category']} on {format_date(row['date'])} will be removed."
        if confirm(self, "Delete this expense?", text, "Delete", danger=True):
            expense.delete_expense(row["id"])
            self.app.data_changed()
            self.toast("Expense deleted")

    def export(self):
        rows = self.table.rows()
        if not rows:
            self.toast("Nothing to export", "warn")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export expenses", "expenses.xlsx",
                                              "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        try:
            export_rows(path, "Expenses", ["Date", "Category", "Note", "Amount"],
                        [[r["date"], r["category"], r["note"] or "", r["amount"]] for r in rows], money_columns=(3,))
            self.toast("Expenses exported")
        except OSError as e:
            self.toast(f"Could not save the file: {e}", "bad")
