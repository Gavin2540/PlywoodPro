"""Create or edit a sale / purchase bill.

The form logic lives in plain methods (``set_date``, ``add_line``, ``set_party``, ``collect``, ``save``) so it
can be driven without ``exec()``. Keyboard flow: Enter in Qty moves to Rate, Enter in Rate moves to the next
line (adding one at the end), Ctrl+Enter saves.
"""
import re

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QScrollArea, QVBoxLayout,
                               QWidget)

from models import bills, parties, product, stock
from ui import theme
from ui.widgets import (Card, DateField, Dialog, NumberEdit, SearchCombo, button, divider, field, hbox, icon_button,
                        label, restyle, toast, vbox)
from utils.helpers import format_currency, format_qty

METHODS = ["Cash", "UPI", "Bank transfer", "Cheque", "Card"]
EPS = 0.004
ROW_H = 60  # a line with its hint row
_AUTO_NO = re.compile(r"^[SP]-\d+$")
QTY_W, RATE_W, AMOUNT_W, X_W = 92, 116, 116, 34
MIN_ROWS, MAX_ROWS = 4, 8


def find_app(widget):
    """Walk up the parent chain to the object that has ``data_changed`` (the main window)."""
    w = widget
    while w is not None:
        if hasattr(w, "data_changed"):
            return w
        w = w.parent()
    return None


class _LineRow(QWidget):
    """One editable line: product, qty, rate, computed amount, remove, plus hints underneath."""

    def __init__(self, editor):
        super().__init__()
        self.ed = editor
        self.pid = None
        self.avail = None  # (available on date, unit) cache for sales
        self.product = SearchCombo("Search product…")
        self.qty = NumberEdit(placeholder="Qty", width=QTY_W)
        self.rate = NumberEdit(placeholder="Rate", width=RATE_W)
        self.amount = label("")
        self.amount.setFixedWidth(AMOUNT_W)
        self.amount.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.amount.setFont(theme.font(13, QFont.DemiBold, tabular=True))
        self.remove = icon_button("close", "Remove this item", self._remove, size=16)
        self.remove.setFixedSize(X_W, 34)
        self.remove.setFocusPolicy(Qt.NoFocus)
        sp = self.remove.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self.remove.setSizePolicy(sp)
        self.remove.hide()
        self.hint = label("", "hint")
        self.cost_hint = label("")
        self.hint_row = QWidget()
        self.hint_row.setLayout(hbox(self.hint, self.cost_hint, None, spacing=14, margins=(2, 0, 0, 0)))
        self.hint_row.hide()
        lay = vbox(hbox(self.product, self.qty, self.rate, self.amount, self.remove, spacing=8),
                   self.hint_row, spacing=3, margins=(0, 0, 0, 4))
        self.setLayout(lay)
        self.product.picked.connect(self._picked)
        self.product.lineEdit().editingFinished.connect(self.sync_product)
        self.qty.textChanged.connect(self._edited)
        self.rate.textChanged.connect(self._edited)
        for w in (self.qty, self.rate, self.product.lineEdit()):
            w.installEventFilter(editor)

    # ── state ───────────────────────────────────────────────────────────
    def is_empty(self):
        return not self.product.text() and self.qty.is_blank()

    def product_id(self):
        return self.product.current_data()

    def amount_value(self):
        return round(self.qty.value() * self.rate.value(), 2)

    def set_product(self, pid, fill_rate=True):
        self.product.set_current_data(pid)
        self.sync_product(fill_rate)

    def sync_product(self, fill_rate=True):
        """React to the product text now matching a (different) product."""
        pid = self.product.current_data()
        if pid == self.pid:
            return
        self.pid = pid
        self.avail = None
        if pid is not None and fill_rate:
            self.rate.set_value(self.ed.default_rate(pid))
        self._edited()

    def _picked(self, pid):
        self.sync_product()
        self.qty.setFocus()

    def _edited(self):
        both = not self.qty.is_blank() and not self.rate.is_blank()
        self.amount.setText(format_currency(self.amount_value()) if both else "")
        self.remove.setVisible(not self.is_empty())
        self.ed.line_changed()

    def _remove(self):
        self.ed.remove_row(self)

    def set_hints(self, avail_text, over, below_cost_text):
        self.hint.setText(avail_text or "")
        if self.hint.property("role") != ("error" if over else "hint"):
            self.hint.setProperty("role", "error" if over else "hint")
            restyle(self.hint)
        self.cost_hint.setText(below_cost_text or "")
        self.cost_hint.setStyleSheet(f"color:{theme.c('warn')}; font-size:12px;")
        self.hint_row.setVisible(bool(avail_text or below_cost_text))


class BillEditor(Dialog):
    def __init__(self, parent, kind, bill_id=None, product_id=None, party_name=None):
        existing = bills.get_bill(bill_id) if bill_id else None
        if bill_id and not existing:
            raise ValueError("That bill no longer exists.")
        noun = "sale" if kind == "sale" else "purchase"
        if existing:
            title, ok = f"Edit {noun} {existing['bill_no']}", "Save changes"
        else:
            title, ok = f"New {noun}", f"Save {noun}"
        super().__init__(parent, title, ok_text=ok, width=920)
        self.resize(960, 600)
        self.kind = kind
        self.is_sale = kind == "sale"
        self._editing = bill_id
        self._bill = existing
        self.locked = False
        self.noun = noun
        self.bill_id = bill_id
        self.rows = []
        self.products = {}
        self._avail_cache = {}
        self._paid_touched = False
        self._last_party = None
        self.on_accept = self.save
        self._build()
        self._load_products()
        self.set_party_choices()
        if self._bill:
            self._load_bill()
        else:
            if party_name:
                self.set_party(party_name)
            if product_id:
                self.add_line(product_id)
            self._ensure_blank()
        self._recalc()
        self._refresh_hints()
        self._check_locked()
        row = next((r for r in self.rows if r.is_empty()), self.rows[-1])
        QTimer.singleShot(0, lambda: (row.qty if row.pid and row.qty.is_blank() else row.product).setFocus())

    # ── layout ──────────────────────────────────────────────────────────
    def _build(self):
        who = "Customer" if self.is_sale else "Supplier"
        self.date_field = DateField()
        self.date_field.dateChanged.connect(lambda *_: self._date_changed())
        self.party = SearchCombo(f"{who} name (optional)" if self.is_sale else f"{who} name", free_text=True)
        self.party.picked.connect(lambda *_: self._party_chosen())
        self.party.lineEdit().editingFinished.connect(self._party_chosen)
        self.party.lineEdit().textChanged.connect(lambda *_: self._party_hint())
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("Phone (optional)")
        self.phone.setFixedWidth(170)
        top = QHBoxLayout()
        top.setSpacing(12)
        top.setAlignment(Qt.AlignTop)
        top.addWidget(field("Date", self.date_field), 0, Qt.AlignTop)
        party_field = field(who, self.party)
        self.party_hint = label("", "hint")
        self.party_hint.setMinimumHeight(16)
        party_field.layout().addWidget(self.party_hint)
        top.addWidget(party_field, 1, Qt.AlignTop)
        top.addWidget(field("Phone", self.phone), 0, Qt.AlignTop)
        self.supplier_bill_no = None
        if not self.is_sale:
            self.supplier_bill_no = QLineEdit()
            self.supplier_bill_no.setPlaceholderText("Optional")
            self.supplier_bill_no.setFixedWidth(170)
            top.addWidget(field("Supplier bill no.", self.supplier_bill_no), 0, Qt.AlignTop)
        self.body.addLayout(top)

        self.lock_warn = label("", "error", wrap=True)
        self.lock_warn.hide()
        self.body.addWidget(self.lock_warn)

        # line items
        def cap(text, w=None, right=False):
            lb = label(text.upper(), "caption")
            if w:
                lb.setFixedWidth(w)
            if right:
                lb.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return lb
        self.scroll_gutter = 6  # right margin of the rows
        head = hbox(cap("Product"), spacing=8, margins=(2, 0, self.scroll_gutter, 0))
        head.addWidget(cap("Qty", QTY_W, True))
        head.addWidget(cap("Rate", RATE_W, True))
        head.addWidget(cap("Amount", AMOUNT_W, True))
        head.addSpacing(X_W)
        head.insertStretch(1, 1)
        self.body.addLayout(head)

        self.lines_box = QVBoxLayout()
        self.lines_box.setSpacing(4)
        self.lines_box.setContentsMargins(0, 3, 6, 0)
        self.lines_box.addStretch(1)
        holder = QWidget()
        holder.setLayout(self.lines_box)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setMinimumHeight(ROW_H * MIN_ROWS)
        self.scroll.setMaximumHeight(ROW_H * MIN_ROWS)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setWidget(holder)
        self.body.addWidget(self.scroll, 1)

        links = hbox(button("+ Add item", "link", None, self.add_blank_line),
                     button("New product", "link", None, self.new_product), None, spacing=18)
        self.body.addLayout(links)
        self.body.addWidget(divider())

        # notes (left) and totals (right)
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Notes (optional)")
        left = vbox(field("Notes", self.notes), None, spacing=8)

        self.subtotal_l = label("", "muted")
        self.discount = NumberEdit(placeholder="0", width=130)
        self.total_l = label("")
        self.total_l.setFont(theme.font(22, QFont.Bold, tabular=True))
        self.total_l.setStyleSheet("font-size:22px;")
        self.paid = NumberEdit(placeholder="—", width=130)
        self.paid.textEdited.connect(self._paid_edited)
        self.full_link = button("Full", "link", None, self.pay_full)
        self.balance_l = label("")
        self.balance_l.setFont(theme.font(13, QFont.Bold, tabular=True))
        self.method = QComboBox()
        self.method.addItems(METHODS)
        self.method.setFixedWidth(130)
        self.profit_l = label("", "hint")
        self.discount.textChanged.connect(lambda *_: self._recalc())
        paid_word = "Amount received" if self.is_sale else "Amount paid"
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        grid.setColumnMinimumWidth(0, 120)

        def right(w):
            return w, Qt.AlignRight | Qt.AlignVCenter
        rows = [("Subtotal", self.subtotal_l), ("Discount", self.discount), ("Total", self.total_l),
                (paid_word, hbox(self.full_link, self.paid, spacing=10)),
                ("Balance due", self.balance_l), ("Payment method", self.method)]
        for i, (cap_text, w) in enumerate(rows):
            lb = label(cap_text, "heading" if cap_text == "Total" else "muted")
            grid.addWidget(lb, i, 0, Qt.AlignLeft | Qt.AlignVCenter)
            if isinstance(w, QHBoxLayout):
                grid.addLayout(w, i, 1, Qt.AlignRight | Qt.AlignVCenter)
            else:
                grid.addWidget(w, i, 1, Qt.AlignRight | Qt.AlignVCenter)
        if self.is_sale:
            grid.addWidget(self.profit_l, len(rows), 0, 1, 2, Qt.AlignRight)
        panel = Card(padding=14, spacing=0)
        panel.setFixedWidth(380)
        panel.body.addLayout(grid)
        self.body.addLayout(hbox(left, panel, spacing=22))

        # footer: secondary "Save and new" (create mode only)
        self.save_new_button = None
        if not self._bill:
            self.save_new_button = button("Save and new", None, None, self.save_and_new)
            self.save_new_button.setAutoDefault(False)
            self.footer.insertWidget(self.footer.count() - 1, self.save_new_button)

    # ── products and parties ────────────────────────────────────────────
    def _load_products(self):
        self.products = {p["id"]: p for p in product.list_products()}

    def _item_text(self, p):
        return product.label(p)

    def _items(self):
        return [(self._item_text(p), pid) for pid, p in self.products.items()]

    def reload_products(self, select_row=None, select_pid=None):
        self._load_products()
        for r in self.rows:  # lines of inactive products (editing old bills) stay selectable
            if r.pid is not None and r.pid not in self.products:
                self._ensure_product(r.pid)
        items = self._items()
        for r in self.rows:
            r.product.set_items(items)
        self._avail_cache.clear()
        if select_row is not None and select_pid is not None:
            select_row.set_product(select_pid)
            select_row.qty.setFocus()
        self._refresh_hints()

    def _ensure_product(self, pid):
        if pid not in self.products:
            p = product.get_product_by_id(pid)
            if p:
                p = dict(p)
                p["stock"] = stock.current_stock(pid)
                self.products[pid] = p

    def set_party_choices(self):
        """Party names for the picker, plus each party's balance (read once, not per keystroke)."""
        rows = parties.list_parties("customer" if self.is_sale else "supplier")
        own = self._bill["due"] if self._bill else 0
        own_name = (self._bill["party_name"] or "").lower() if self._bill else ""
        self._party_due = {r["name"].lower(): round(r["due"] - (own if r["name"].lower() == own_name else 0), 2)
                           for r in rows}
        self.party.set_items([(r["name"], r["name"]) for r in rows])
        self._party_hint()

    def _party_hint(self):
        name = self.party.text().lower()
        who = "customer" if self.is_sale else "supplier"
        if not name or not hasattr(self, "_party_due"):
            text = ""
        elif name not in self._party_due:
            text = f"New {who} — will be saved"
        else:
            due = self._party_due[name]
            text = (f"{'Owes' if self.is_sale else 'You owe'} {format_currency(due, decimals=0)} from earlier bills"
                    if due > EPS else "")
        self.party_hint.setText(text)

    def set_party(self, name, phone=None):
        self.party.setEditText(name or "")
        self._last_party = None
        self._party_chosen()
        if phone is not None:
            self.phone.setText(phone)

    def _party_chosen(self):
        name = self.party.text()
        if name == self._last_party:
            return
        self._last_party = name
        found = parties.find_by_name("customer" if self.is_sale else "supplier", name) if name else None
        if found:
            self.phone.setText(found.get("phone") or "")

    def default_rate(self, pid):
        p = self.products.get(pid) or {}
        last = bills.last_price(self.kind, pid, self.party.text() or None)
        if last is not None:
            return last
        return p.get("selling_price" if self.is_sale else "purchase_price")

    # ── lines ───────────────────────────────────────────────────────────
    def _new_row(self):
        row = _LineRow(self)
        row.product.set_items(self._items())
        self.lines_box.insertWidget(self.lines_box.count() - 1, row)
        self.rows.append(row)
        self._retab()
        self._fit_lines()
        QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(row))
        return row

    def _retab(self):
        chain = [self.date_field, self.party, self.phone] + ([self.supplier_bill_no] if self.supplier_bill_no else [])
        for r in self.rows:
            chain += [r.product, r.qty, r.rate]
        chain += [self.discount, self.paid, self.method, self.notes]
        for a, b in zip(chain, chain[1:]):
            QWidget.setTabOrder(a, b)

    def _ensure_blank(self):
        if not self.rows or not self.rows[-1].is_empty():
            return self._new_row()
        return self.rows[-1]

    def add_blank_line(self):
        row = self._ensure_blank()
        row.product.setFocus()
        return row

    def add_line(self, product_id=None, qty=None, rate=None, focus=False):
        """Fill the empty row at the end (or a new one) and keep a blank row ready."""
        row = self._ensure_blank()
        if product_id is not None:
            self._ensure_product(product_id)
            if product_id not in [d for _t, d in self._items()]:
                for r in self.rows:
                    r.product.set_items(self._items())
            row.set_product(product_id, fill_rate=rate is None)
        if rate is not None:
            row.rate.set_value(rate)
        if qty is not None:
            row.qty.set_value(qty)
        self._ensure_blank()
        if focus:
            row.qty.setFocus()
        return row

    def remove_row(self, row):
        if len(self.rows) == 1:
            row.product.setEditText("")
            row.product.setCurrentIndex(-1)
            row.qty.clear()
            row.rate.clear()
            row.sync_product()
            return
        idx = self.rows.index(row)
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._ensure_blank()
        self.rows[min(idx, len(self.rows) - 1)].product.setFocus()
        self._fit_lines()
        self.line_changed()

    def _fit_lines(self):
        """Grow the items area with the rows (4 to 8 visible), then let it scroll."""
        rh = ROW_H if self.is_sale else ROW_H - 18
        h = max(MIN_ROWS, min(MAX_ROWS, len(self.rows))) * rh
        if self.scroll.minimumHeight() != h:
            self.scroll.setMinimumHeight(h)
            self.scroll.setMaximumHeight(h)
            QTimer.singleShot(0, self.adjustSize)

    def line_changed(self):
        if hasattr(self, "total_l") and self.rows:
            self._recalc()
            self._refresh_hints()

    def _focus_row(self):
        w = self.focusWidget()
        while w is not None:
            if isinstance(w, _LineRow):
                return w
            w = w.parentWidget()
        return self.rows[-1]

    def new_product(self):
        from ui.dialogs.product_dialog import ProductDialog
        row = self._focus_row()
        dlg = ProductDialog(self)
        if dlg.exec():
            self.reload_products(row, dlg.product_id)
            app = find_app(self)
            if app is not None:
                app.data_changed()

    # keyboard flow inside the grid
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter) \
                and not (event.modifiers() & Qt.ControlModifier):
            for i, row in enumerate(self.rows):
                if obj is row.qty:
                    row.rate.setFocus()
                    return True
                if obj is row.rate:
                    nxt = self.rows[i + 1] if i + 1 < len(self.rows) else self.add_blank_line()
                    nxt.product.setFocus()
                    return True
                if obj is row.product.lineEdit() and not row.product.view().isVisible():
                    if row.product.current_data() is not None:
                        row.sync_product()
                        row.qty.setFocus()
                        return True
        return super().eventFilter(obj, event)

    # ── availability hints ──────────────────────────────────────────────
    def _available(self, pid):
        date = self.date_field.iso()
        key = (pid, date)
        if key not in self._avail_cache:
            avail = stock.min_balance_from(pid, date)
            if avail == float("inf"):
                avail = stock.stock_on(pid, date)
            if self._bill:  # this bill's own lines are already deducted
                avail += sum(ln["qty"] for ln in self._bill["lines"] if ln["product_id"] == pid)
            self._avail_cache[key] = avail
        return self._avail_cache[key]

    def _refresh_hints(self):
        if not self.is_sale:
            return
        want = {}
        for r in self.rows:
            if r.pid is not None:
                want[r.pid] = want.get(r.pid, 0) + r.qty.value()
        for r in self.rows:
            if r.pid is None:
                r.set_hints("", False, "")
                continue
            p = self.products.get(r.pid) or {}
            avail = self._available(r.pid)
            over = want[r.pid] > avail + 1e-6
            text = f"Available on this date: {format_qty(max(avail, 0), p.get('unit'))}"
            cost = p.get("purchase_price") or 0
            below = ""
            if not r.rate.is_blank() and r.rate.value() + 1e-9 < cost:
                below = f"Below cost {format_currency(cost, decimals=0 if cost == int(cost) else 2)}"
            r.set_hints(text, over, below)

    def set_date(self, iso_date):
        self.date_field.set_iso(iso_date)

    def _date_changed(self):
        self._avail_cache.clear()
        self._refresh_hints()
        self._check_locked()

    def _check_locked(self):
        dates = {self.date_field.iso()}
        if self._bill:
            dates.add(self._bill["date"])
        closed = sorted(d for d in dates if stock.is_locked(d))
        self.locked = bool(closed)
        if closed:
            from utils.helpers import format_date
            self.lock_warn.setText(f"{format_date(closed[0])} is a closed day, so its bills cannot be changed. "
                                   "Pick another date, or reopen the day in Stock Ledger.")
        self.lock_warn.setVisible(self.locked)
        self.ok_button.setEnabled(not self.locked)
        if self.save_new_button:
            self.save_new_button.setEnabled(not self.locked)

    # ── totals ──────────────────────────────────────────────────────────
    def subtotal(self):
        return round(sum(r.amount_value() for r in self.rows if not r.qty.is_blank()), 2)

    def total(self):
        return round(max(self.subtotal() - self.discount.value(), 0), 2)

    def _paid_edited(self, *_):
        self._paid_touched = True
        self._recalc()

    def pay_full(self):
        self._paid_touched = False
        self._recalc()

    def _recalc(self):
        if not hasattr(self, "paid"):
            return
        sub, total = self.subtotal(), self.total()
        self.subtotal_l.setText(format_currency(sub))
        self.total_l.setText(format_currency(total))
        if not self._paid_touched or self.paid.value() > total + EPS:
            self.paid.blockSignals(True)
            self.paid.set_value(total) if total else self.paid.clear()
            self.paid.blockSignals(False)
        due = round(total - self.paid.value(), 2)
        if not sub:
            self.balance_l.setText("—")
        else:
            self.balance_l.setText(format_currency(max(due, 0)))
        self.balance_l.setStyleSheet(f"color:{theme.c('bad')};" if due > EPS and sub else "")
        self.full_link.setVisible(abs(due) > EPS and bool(sub))
        self.profit_l.setVisible(self.is_sale and bool(sub))
        if self.is_sale:
            profit = 0.0
            for r in self.rows:
                if r.pid is not None and not r.qty.is_blank():
                    cost = (self.products.get(r.pid) or {}).get("purchase_price") or 0
                    profit += r.qty.value() * (r.rate.value() - cost)
            profit -= self.discount.value() if sub else 0
            self.profit_l.setText(f"Estimated profit on this bill: {format_currency(profit)}")

    # ── load / collect / save ───────────────────────────────────────────
    def _load_bill(self):
        b = self._bill
        self.set_date(b["date"])
        self.set_party(b["party_name"] or "", b.get("party_phone") or "")
        if self.supplier_bill_no is not None and b.get("bill_no") and not _AUTO_NO.match(b["bill_no"]):
            self.supplier_bill_no.setText(b["bill_no"])
        for ln in b["lines"]:
            self._ensure_product(ln["product_id"])
        for r in self.rows:
            r.product.set_items(self._items())
        for ln in b["lines"]:
            self.add_line(ln["product_id"], ln["qty"], ln["unit_price"])
        self._ensure_blank()
        self.discount.set_value(b["discount"] or None)
        self._paid_touched = b["due"] > EPS  # a fully paid bill stays fully paid as its total changes
        self.paid.set_value(b["paid"])
        self.notes.setText(b.get("notes") or "")
        if b["payments"]:
            m = b["payments"][-1]["method"]
            if m and self.method.findText(m) >= 0:
                self.method.setCurrentText(m)

    def collect(self):
        """Form -> keyword arguments for ``bills.save_bill``. Raises ValueError for unusable lines."""
        items = []
        for n, r in enumerate(self.rows, start=1):
            if r.is_empty():
                continue
            pid = r.product_id()
            if pid is None:
                raise ValueError(f"Line {n}: pick a product from the list.")
            if r.qty.value() <= 0:
                raise ValueError(f"Line {n}: enter a quantity.")
            items.append({"product_id": pid, "qty": r.qty.value(), "unit_price": r.rate.value()})
        if not items:
            raise ValueError("Add at least one item.")
        return dict(
            kind=self.kind, date=self.date_field.iso(), items=items,
            party_name=self.party.text() or None, party_phone=self.phone.text().strip() or None,
            discount=self.discount.value(), paid=self.paid.value(), method=self.method.currentText(),
            notes=self.notes.text().strip() or None,
            bill_no=(self.supplier_bill_no.text().strip() or None) if self.supplier_bill_no else None,
            bill_id=self._editing, update_cost=True)

    def save(self):
        """Save through the model; model errors propagate (shown inline by the dialog)."""
        self.bill_id = bills.save_bill(**self.collect())
        app = find_app(self)
        if app is not None:
            app.data_changed()
        return True

    def save_and_new(self):
        self.error.hide()
        try:
            self.save()
        except (ValueError, PermissionError) as e:
            self.show_error(e)
            return False
        toast(self, f"{self.noun.capitalize()} saved")
        self.reset_form()
        return True

    def reset_form(self):
        for r in list(self.rows):
            r.setParent(None)
            r.deleteLater()
        self.rows = []
        self._paid_touched = False
        self._avail_cache.clear()
        self.party.setEditText("")
        self._last_party = None
        self.phone.clear()
        self.discount.clear()
        self.notes.clear()
        if self.supplier_bill_no:
            self.supplier_bill_no.clear()
        self._load_products()
        self.set_party_choices()
        self._ensure_blank()
        self._recalc()
        self._refresh_hints()
        self.rows[0].product.setFocus()
