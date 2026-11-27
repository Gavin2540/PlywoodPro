"""Stock Ledger: the daily stock register and physical stock check."""
import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFrame, QLineEdit, QScrollArea, QVBoxLayout, QWidget)

from models import product, stock
from ui import theme
from ui.table import Action, Col, DataTable
from ui.widgets import (Dialog, DateField, NumberEdit, Page, SearchBox, Segmented, button, confirm, hbox,
                        icon_button, label, vbox)
from utils.helpers import format_date, format_qty

EPS = 0.0005
FILTERS = [("all", "All"), ("moved", "Moved today"), ("counted", "Counted"), ("mismatch", "Mismatch")]


def _spec(r):
    return " · ".join(str(r[k]) for k in ("product_brand", "product_type", "product_thickness", "product_size")
                      if r.get(k))


def _unit(r):
    return r.get("product_unit") or "sheets"


def _diff_text(diff, unit):
    """(text, theme colour key) for a counted-minus-expected difference."""
    if abs(diff) < EPS:
        return "Matches the books", "good"
    if diff < 0:
        return f"{format_qty(-diff)} short", "bad"
    return f"{format_qty(diff)} extra", "warn"


class CountDialog(Dialog):
    """Record the physical count of one product on one day."""
    saved = Signal()

    def __init__(self, parent, row, date):
        self.row, self.date = row, date
        super().__init__(parent, "Record stock count",
                         f"{product.label(row)} · {format_date(date)}", ok_text="Save count", width=460)
        unit = _unit(row)
        expected = row["expected_closing"]
        self.expected_label = label(f"Expected by the books: {format_qty(expected)} {unit}", "muted")
        self.body.addWidget(self.expected_label)

        self.qty = NumberEdit(row["closing_stock"], decimals=2, placeholder="0")
        self.body.addWidget(self._field("Counted quantity", self.qty))
        self.diff_label = label("", "field")
        self.body.addWidget(self.diff_label)
        self.note = QLineEdit(row.get("count_note") or "")
        self.note.setPlaceholderText("e.g. 2 sheets water damaged")
        self.note_caption = label("Note", "field")
        self.body.addWidget(self._wrap(self.note_caption, self.note))
        self.qty.textChanged.connect(self._update)
        self._update()
        self.on_accept = self.save
        if hasattr(parent, "_after_write"):
            self.saved.connect(parent._after_write)
        self.qty.setFocus()

    @staticmethod
    def _wrap(*widgets):
        w = QWidget()
        w.setLayout(vbox(*widgets, spacing=6))
        return w

    def _field(self, caption, widget):
        return self._wrap(label(caption, "field"), widget)

    def difference(self):
        return round(self.qty.value() - self.row["expected_closing"], 4)

    def _update(self, *_):
        if self.qty.is_blank():
            self.diff_label.setText("")
            self.note_caption.setText("Note")
            return
        text, key = _diff_text(self.difference(), _unit(self.row))
        self.diff_label.setText(text)
        self.diff_label.setStyleSheet(f"color:{theme.c(key)}; font-size:13px; font-weight:600;")
        self.note_caption.setText("Note (required when the count differs)" if abs(self.difference()) >= EPS
                                  else "Note")

    def save(self):
        if self.qty.is_blank():
            raise ValueError("Enter the quantity you counted.")
        note = self.note.text().strip()
        if abs(self.difference()) >= EPS and not note:
            raise ValueError("Add a short note explaining the difference, e.g. damaged or miscounted.")
        stock.set_count(self.row["product_id"], self.date, self.qty.value(), note or None)
        self.saved.emit()
        return True


class CountAllDialog(Dialog):
    """Full stock-take in one go: one counted quantity per product."""
    saved = Signal()

    def __init__(self, parent, rows, date):
        self.rows, self.date, self.edits = rows, date, {}
        super().__init__(parent, "Count all stock", f"{format_date(date)} · type what is on the shelf; "
                         "only products you change are saved", ok_text="Save counts", width=620)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(6)
        for r in rows:
            edit = NumberEdit(r["closing_stock"], decimals=2, width=96)
            self.edits[r["product_id"]] = edit
            name = label(product.label(r), "muted")
            exp = label(f"Books: {format_qty(r['closing_stock'])}", "hint")
            exp.setMinimumWidth(90)
            lay.addLayout(hbox(name, None, exp, edit, spacing=10))
        lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(inner)
        scroll.setMinimumHeight(360)
        self.body.addWidget(scroll)
        self.on_accept = self.save
        if hasattr(parent, "_after_write"):
            self.saved.connect(parent._after_write)

    def save(self):
        changed = [(r, self.edits[r["product_id"]].value()) for r in self.rows
                   if abs(self.edits[r["product_id"]].value() - r["closing_stock"]) >= EPS]
        if not changed:
            raise ValueError("Nothing changed. Edit a quantity to record a count.")
        failed = []
        for r, qty in changed:
            try:
                stock.set_count(r["product_id"], self.date, qty, "Stock-take")
            except (ValueError, PermissionError) as e:
                failed.append(f"{product.label(r)}: {e}")
        self.saved.emit()
        if failed:
            raise ValueError("Some counts were not saved. " + " ".join(failed[:2]))
        return True


class _Stat(QFrame):
    """Compact summary block: small caption over a number."""

    def __init__(self, caption):
        super().__init__()
        self.setObjectName("Card")
        self.caption = label(caption.upper(), "caption")
        self.value = label("0", "heading")
        self.value.setStyleSheet("font-size:20px; font-weight:700;")
        self.setLayout(vbox(self.caption, self.value, spacing=2, margins=(14, 10, 14, 10)))

    def set(self, text, tone=None):
        self.value.setText(text)
        self.value.setStyleSheet(f"font-size:20px; font-weight:700;{f' color:{theme.c(tone)};' if tone else ''}")


class LedgerPage(Page):
    title = "Stock Ledger"

    def __init__(self, app):
        super().__init__(app)
        self._rows = []
        self.export_button = self.add_action(button("Export", None, "download", self.export_visible))
        self.count_all_button = self.add_action(button("Count all", None, "clipboard", self.count_all))
        self.lock_button = self.add_action(button("Close day", "primary", "lock", self.toggle_lock))

        self.date_field = DateField()
        self.prev_button = icon_button("chevron-left", "Previous day", self.prev_day)
        self.next_button = icon_button("chevron-right", "Next day", self.next_day)
        self.today_button = button("Today", "link", None, self.go_today)
        self.search = SearchBox("Search products…", 190)
        self.filter = Segmented(FILTERS, "all")
        self.removed = QCheckBox("Show removed products")
        for b in (self.prev_button, self.next_button):
            b.setFixedSize(34, 34)
        self.root.addLayout(hbox(self.prev_button, self.date_field, self.next_button, self.today_button, 8,
                                 self.search, self.filter, None, self.removed, spacing=8))

        self.stat_products = _Stat("Products")
        self.stat_in = _Stat("Total in")
        self.stat_out = _Stat("Total out")
        self.stat_counted = _Stat("Counted")
        self.stat_variance = _Stat("Count difference")
        self.root.addLayout(hbox(self.stat_products, self.stat_in, self.stat_out, self.stat_counted,
                                 self.stat_variance, spacing=12))

        self.table = DataTable(
            [Col("product_name", "Product", stretch=True, bold=True, sub=_spec),
             Col("opening_stock", "Opening", width=84, align="right", fmt=lambda v, r: format_qty(v),
                 color=lambda r: "text2"),
             Col("purchases_qty", "In", width=64, align="right",
                 fmt=lambda v, r: f"+{format_qty(v)}" if v else "—",
                 color=lambda r: "good" if r["purchases_qty"] else "text3"),
             Col("sales_qty", "Out", width=64, align="right",
                 fmt=lambda v, r: f"−{format_qty(v)}" if v else "—",
                 color=lambda r: "bad" if r["sales_qty"] else "text3"),
             Col("expected_closing", "Expected", width=84, align="right", fmt=lambda v, r: format_qty(v),
                 color=lambda r: "text2"),
             Col("closing_stock", "Closing", width=80, align="right", bold=True,
                 fmt=lambda v, r: format_qty(v), color=_closing_color),
             Col("is_counted", "Check", width=96, align="center", badge=_check_badge, sort=lambda r: r["variance"]),
             Col("count_note", "Count note", width=220, color=lambda r: "text2",
                 fmt=lambda v, r: v or "")],
            actions=[Action("clipboard", "Record count", self.record_count, visible=lambda r: not r["is_locked"]),
                     Action("close", "Clear count", self.clear_count,
                            visible=lambda r: r["is_counted"] and not r["is_locked"]),
                     Action("history", "History", self.show_history)],
            empty=("ledger", "No products yet", "Add products to see their daily stock here."))
        self.table.activated.connect(self._activated)
        self.closed_banner = QFrame()
        self.closed_banner.setStyleSheet(
            f"background:{theme.c('warn_soft')}; border:1px solid {theme.c('warn')}; border-radius:8px;")
        banner_text = label("This day is closed. Reopen it to change entries.")
        banner_text.setStyleSheet(f"color:{theme.c('warn')}; font-weight:600; border:none; background:transparent;")
        self.closed_banner.setLayout(hbox(banner_text, None, margins=(14, 9, 14, 9)))
        self.closed_banner.hide()
        self.root.addWidget(self.closed_banner)
        self.root.addWidget(self.table, 1)
        self.table.filtered.connect(self._summary)

        self.date_field.dateChanged.connect(lambda *_: self.refresh())
        self.filter.changed.connect(lambda _: self._apply_filter())
        self.search.searched.connect(self.table.set_search)
        self.removed.toggled.connect(lambda _: self.refresh())

    # ── helpers ─────────────────────────────────────────────────────────
    def date(self):
        return self.date_field.iso()

    def is_closed(self):
        return stock.is_locked(self.date())

    def _activated(self, row):
        if row["is_locked"]:
            self.show_history(row)
        else:
            self.record_count(row)

    def _apply_filter(self):
        key = self.filter.current() or "all"
        preds = {
            "all": None,
            "moved": lambda r: bool(r["purchases_qty"] or r["sales_qty"]),
            "counted": lambda r: r["is_counted"],
            "mismatch": lambda r: abs(r["variance"]) >= EPS,
        }
        self.table.set_filter(preds[key])

    # ── loading ─────────────────────────────────────────────────────────
    def refresh(self):
        d = self.date()
        today = datetime.date.today().isoformat()
        self.next_button.setEnabled(d < today)
        self.today_button.setEnabled(d != today)
        closed = stock.is_locked(d)
        long = datetime.date.fromisoformat(d).strftime("%A, %d %B %Y")
        state = "Closed — entries for this day cannot be changed" if closed else "Open"
        self.subtitle_label.setText(f"{long} · {state}")
        self.closed_banner.setVisible(closed)
        if closed:
            self.lock_button.setText("Reopen day")
            self.lock_button.setProperty("variant", None)
            self.lock_button.setIcon(_icon("unlock"))
        else:
            self.lock_button.setText("Close day")
            self.lock_button.setProperty("variant", "primary")
            self.lock_button.setIcon(_icon("lock", on_accent=True))
        from ui.widgets import restyle
        restyle(self.lock_button)
        self.count_all_button.setVisible(not closed)
        self.count_all_button.setEnabled(not closed)

        rows = stock.day_ledger(d, include_inactive=self.removed.isChecked())
        for r in rows:
            r["id"] = r["product_id"]
        self._rows = rows
        self.table.set_rows(rows)
        self._apply_filter()
        self.table.set_search(self.search.text())
        neg = sum(1 for r in rows if r["closing_stock"] < -stock.EPS)
        if neg:
            bad = theme.c("bad")
            self.subtitle_label.setText(
                f"{long} · {state} · <span style='color:{bad}; font-weight:600'>{neg} "
                f"product{'s' if neg != 1 else ''} below zero</span>")
        self.subtitle_label.setTextFormat(Qt.RichText if neg else Qt.PlainText)

    def _summary(self):
        rows = self.table.rows()
        counted = [r for r in rows if r["is_counted"]]
        variance = sum(r["variance"] for r in counted)
        self.stat_products.set(f"{len(rows):,}")
        self.stat_in.set(format_qty(sum(r["purchases_qty"] for r in rows)))
        self.stat_out.set(format_qty(sum(r["sales_qty"] for r in rows)))
        self.stat_counted.set(f"{len(counted)} of {len(rows)}" if rows else "0")
        if abs(variance) < EPS:
            self.stat_variance.set("0")
        else:
            self.stat_variance.set(f"{'+' if variance > 0 else '−'}{format_qty(abs(variance))}", "bad")

    # ── date navigation ─────────────────────────────────────────────────
    def set_date(self, iso):
        self.date_field.set_iso(iso)  # dateChanged triggers refresh

    def _shift(self, days):
        d = datetime.date.fromisoformat(self.date()) + datetime.timedelta(days=days)
        if d <= datetime.date.today():
            self.set_date(d.isoformat())

    def prev_day(self):
        self._shift(-1)

    def next_day(self):
        self._shift(1)

    def go_today(self):
        self.set_date(datetime.date.today().isoformat())

    def open(self, date=None, product_id=None):
        if date:
            self.date_field.blockSignals(True)
            self.date_field.set_iso(date)
            self.date_field.blockSignals(False)
        if product_id is not None:
            self.search.clear()
            self.filter.set("all")
        self.refresh()
        if product_id is not None:
            self.table.select_where(lambda r: r["product_id"] == product_id)

    # ── actions ─────────────────────────────────────────────────────────
    def record_count(self, row=None, product_id=None):
        if row is None and product_id is not None:
            row = next((r for r in self._rows if r["product_id"] == product_id), None)
        row = row or self.table.selected()
        if not row:
            return None
        if stock.is_locked(self.date()):
            self.toast("This day is closed. Reopen it to record a count.", "warn")
            return None
        dlg = CountDialog(self, row, self.date())
        if dlg.exec():
            self.toast("Count saved")
        return dlg

    def _after_write(self):
        self.app.data_changed()

    def clear_count(self, row=None, confirmed=False):
        row = row or self.table.selected()
        if not row:
            return
        if not confirmed and not confirm(self, "Clear this count?",
                                         f"The recorded count for {product.label(row)} on "
                                         f"{format_date(self.date())} will be removed and stock goes back to "
                                         "what the books say.", "Clear count", danger=True):
            return
        try:
            stock.clear_count(row["product_id"], self.date())
        except (ValueError, PermissionError) as e:
            self.toast(str(e), "bad")
            return
        self.app.data_changed()
        self.toast("Count cleared")

    def count_all(self):
        rows = [r for r in self._rows if not r["is_locked"]]
        if not rows:
            return None
        dlg = CountAllDialog(self, rows, self.date())
        if dlg.exec():
            self.toast("Counts saved")
        return dlg

    def show_history(self, row=None):
        row = row or self.table.selected()
        if not row:
            return
        try:
            from ui.dialogs.product_history import ProductHistoryDialog
        except Exception:
            self.toast("Product history is not available yet", "warn")
            return
        ProductHistoryDialog(self, row["product_id"]).exec()

    def toggle_lock(self):
        if self.is_closed():
            self.reopen_day()
        else:
            self.close_day()

    def close_day(self, confirmed=False):
        d = self.date()
        if not confirmed:
            text = (f"Closing {format_date(d)} freezes every sale, purchase and stock count dated that day. "
                    "Nothing can be added, changed or removed until you reopen the day.")
            negative = [r for r in self._rows if r["closing_stock"] < -stock.EPS]
            if negative:
                text += (f"\n\nWarning: {len(negative)} product(s) have negative closing stock. "
                         "You may want to check them first.")
            if not confirm(self, "Close this day?", text, "Close day"):
                return False
        stock.lock_day(d)
        self.app.data_changed()
        self.toast(f"{format_date(d)} is closed")
        return True

    def reopen_day(self, confirmed=False):
        d = self.date()
        if not confirmed and not confirm(self, "Reopen this day?",
                                         f"Entries dated {format_date(d)} can be changed again.", "Reopen day"):
            return False
        stock.unlock_day(d)
        self.app.data_changed()
        self.toast(f"{format_date(d)} is open again")
        return True

    def export_visible(self, path=None):
        rows = self.table.rows()
        if not rows:
            self.toast("Nothing to export", "warn")
            return None
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export stock ledger", f"Stock_Ledger_{self.date()}.xlsx",
                "Excel (*.xlsx);;CSV (*.csv)")
            if not path:
                return None
        from utils.tabular import export_rows
        headers = ["Product", "Brand", "Type", "Thickness", "Size", "Opening", "In", "Out", "Expected",
                   "Closing", "Counted", "Difference", "Note"]
        data = [[r["product_name"], r["product_brand"], r["product_type"], r["product_thickness"],
                 r["product_size"], r["opening_stock"], r["purchases_qty"], r["sales_qty"],
                 r["expected_closing"], r["closing_stock"], "Yes" if r["is_counted"] else "",
                 r["variance"] if r["is_counted"] else "", r["count_note"] or ""] for r in rows]
        try:
            export_rows(path, f"Stock {self.date()}", headers, data)
        except OSError as e:
            self.toast(f"Could not save the file: {e}", "bad")
            return None
        self.toast("Exported " + path.replace("\\", "/").split("/")[-1])
        return path


def _icon(name, on_accent=False):
    from ui import icons
    return icons.icon(name, theme.c("on_accent") if on_accent else theme.c("text2"), 16)


def _closing_color(r):
    q = r["closing_stock"]
    if q < 0 or q <= stock.EPS:
        return "bad"
    if q <= (r.get("low_stock_threshold") or 0):
        return "warn"
    return None


def _check_badge(r):
    if not r["is_counted"]:
        return None
    v = r["variance"]
    if abs(v) < EPS:
        return "Counted", "info"
    return (f"Short {format_qty(-v)}", "bad") if v < 0 else (f"Extra {format_qty(v)}", "warn")
