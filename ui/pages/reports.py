"""Reports: how the business is doing for any period, plus a stock valuation view."""
import datetime
import os

from PySide6.QtCore import QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QFileDialog, QFrame, QGridLayout, QScrollArea, QVBoxLayout, QWidget

from models import reports
from ui import theme
from ui.charts import DonutChart, TrendChart
from ui.table import Col, DataTable
from ui.widgets import Card, DateRangeBar, Page, SearchBox, Segmented, StatCard, button, hbox, label
from utils import export
from utils.helpers import format_currency, format_date, format_qty

VIEWS = [("pl", "Profit && loss"), ("stock", "Stock")]
PRODUCT_SORTS = [("revenue", "By sales"), ("profit", "By profit"), ("qty", "By quantity")]
WEEKLY_AFTER_DAYS = 62      # daily bars up to this many days, then weeks
MONTHLY_AFTER_DAYS = 400    # then months


# ── pure helpers (unit-tested) ──────────────────────────────────────────
def _d(iso):
    return datetime.date.fromisoformat(iso)


def period_text(start, end):
    a, b = _d(start), _d(end)
    days = (b - a).days + 1
    fmt = lambda d: f"{d.day} {d:%b %Y}"
    unit = "day" if days == 1 else "days"
    if days == 1:
        return f"{fmt(a)} · 1 day"
    return f"{fmt(a)} – {fmt(b)} · {days} {unit}"


def aggregate_series(series):
    """Daily series -> (labels, sales, net_profit, granularity) readable on a chart."""
    n = len(series)
    if n <= WEEKLY_AFTER_DAYS:
        fmt = "%d %b" if n > 14 else "%a %d"
        return ([_d(s["date"]).strftime(fmt) for s in series], [s["revenue"] for s in series],
                [s["net_profit"] for s in series], "Daily")
    monthly = n > MONTHLY_AFTER_DAYS
    buckets = {}
    for s in series:
        d = _d(s["date"])
        key = d.replace(day=1) if monthly else d - datetime.timedelta(days=d.weekday())
        b = buckets.setdefault(key, [0.0, 0.0])
        b[0] += s["revenue"]
        b[1] += s["net_profit"]
    keys = sorted(buckets)
    labels = [f"{k:%b %y}" if monthly else f"{k.day:02d} {k:%b}" for k in keys]
    return (labels, [round(buckets[k][0], 2) for k in keys], [round(buckets[k][1], 2) for k in keys],
            "Monthly" if monthly else "Weekly")


def _spec(r, prefix="product_"):
    return " · ".join(str(r[prefix + k]) for k in ("brand", "thickness", "size") if r.get(prefix + k))


def _money(v):
    return format_currency(v, decimals=0)


class _Mini(QWidget):
    """A small, quiet figure: caption above, value below."""

    def __init__(self, caption):
        super().__init__()
        self.caption = label(caption, "hint")
        self.value = label("—", "muted")
        self.value.setFont(theme.font(15, QFont.DemiBold, tabular=True))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self.caption)
        lay.addWidget(self.value)

    def set(self, text):
        self.value.setText(text)


class _ShareList(QWidget):
    """Expense categories with a swatch matching the donut slice, entries, share and amount."""

    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(0)
        self.empty = label("No expenses in this period", "hint")
        self.names = []

    def set_rows(self, rows, max_slices=6):
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.names = [r["category"] for r in rows]
        if not rows:
            self.lay.addWidget(self.empty)
            self.empty.show()
            return
        total = sum(r["amount"] for r in rows) or 1
        colors = theme.chart_colors()
        head = hbox(label("", "caption"), label("CATEGORY", "caption"), None, label("ENTRIES", "caption"),
                    label("SHARE", "caption"), label("AMOUNT", "caption"), spacing=0, margins=(4, 0, 4, 6))
        for i, w in ((3, 62), (4, 58), (5, 86)):
            head.itemAt(i).widget().setFixedWidth(w)
            head.itemAt(i).widget().setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        head.itemAt(0).widget().setFixedWidth(18)
        self._add(head)
        n = len(rows)
        for i, r in enumerate(rows):
            slot = i if n <= max_slices else min(i, max_slices - 1)
            sw = QFrame()
            sw.setFixedSize(10, 10)
            sw.setStyleSheet(f"background:{colors[slot % len(colors)]}; border-radius:3px;")
            name = label(r["category"])
            name.setFont(theme.font(13, QFont.DemiBold))
            cells = [label(str(r["entries"]), "muted"), label(f"{r['amount'] / total * 100:.0f}%", "muted"),
                     label(_money(r["amount"]))]
            row = hbox(sw, 8, name, None, *cells, spacing=0, margins=(4, 0, 4, 0))
            for j, (w, c) in enumerate(zip((62, 58, 86), cells)):
                c.setFixedWidth(w)
                c.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                c.setFont(theme.font(13, tabular=True))
            holder = QWidget()
            holder.setLayout(row)
            holder.setFixedHeight(34)
            self._add(holder)

    def _add(self, item):
        if isinstance(item, QWidget):
            self.lay.addWidget(item)
        else:
            w = QWidget()
            w.setLayout(item)
            self.lay.addWidget(w)


class _Footer(QWidget):
    """Total line under a table: description on the left, figures on the right."""

    def __init__(self):
        super().__init__()
        self.left = label("", "muted")
        self.right = label("")
        self.right.setFont(theme.font(13, QFont.Bold, tabular=True))
        lay = hbox(self.left, None, self.right, margins=(12, 4, 12, 0))
        self.setLayout(lay)

    def set(self, left, right):
        self.left.setText(left)
        self.right.setText(right)


class ReportsPage(Page):
    title = "Reports"

    def __init__(self, app):
        super().__init__(app)
        self.view_key = "pl"
        self.product_sort = "revenue"
        self._perf = []
        self._discount = 0.0
        self.last_export = None

        self.add_action(button("Export Excel", None, "download", lambda: self.export_excel()))
        self.add_action(button("Export PDF", "primary", "file", lambda: self.export_pdf()))

        self.view_seg = Segmented(VIEWS, "pl")
        self.view_seg.changed.connect(self._set_view)
        self.range_bar = DateRangeBar("month")
        self.range_bar.changed.connect(lambda *_: self.refresh())
        self.asof = label("", "muted")
        self.search = SearchBox("Search products…", 240)
        self.root.addLayout(hbox(self.view_seg, None, self.range_bar, self.asof, self.search, spacing=12))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll = scroll
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 8, 8)
        col.setSpacing(16)
        scroll.setWidget(inner)
        self.root.addWidget(scroll, 1)

        self.pl_view = QWidget()
        pl = QVBoxLayout(self.pl_view)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(16)
        self.stock_view = QWidget()
        sv = QVBoxLayout(self.stock_view)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(16)
        col.addWidget(self.pl_view)
        col.addWidget(self.stock_view)
        col.addStretch(1)
        self._build_pl(pl)
        self._build_stock(sv)
        self._apply_view()

    # ── layout ──────────────────────────────────────────────────────────
    def _build_pl(self, pl):
        self.k_sales = StatCard("Sales", "sale")
        self.k_gross = StatCard("Gross profit", "trend")
        self.k_exp = StatCard("Expenses", "expense")
        self.k_net = StatCard("Net profit", "wallet", tone="sign")
        self.k_buy = StatCard("Purchases", "purchase")
        grid = QGridLayout()
        grid.setSpacing(16)
        for i, c in enumerate((self.k_sales, self.k_gross, self.k_exp, self.k_net, self.k_buy)):
            grid.addWidget(c, 0, i)
            grid.setColumnStretch(i, 1)
        pl.addLayout(grid)

        self.m_bills = _Mini("Sale bills")
        self.m_qty = _Mini("Quantity sold")
        self.m_disc = _Mini("Discounts given")
        self.m_in = _Mini("Collected from customers")
        self.m_out = _Mini("Paid to suppliers")
        quiet = Card(padding=14)
        row = hbox(spacing=16)
        for m in (self.m_bills, self.m_qty, self.m_disc, self.m_in, self.m_out):
            row.addWidget(m, 1)
        quiet.add(row)
        pl.addWidget(quiet)

        self.trend_card = Card("Profit over time")
        self.trend_hint = label("", "hint")
        self.trend_card.add_header_widget(self.trend_hint)
        self.trend = TrendChart(height=260)
        self.trend_card.add(self.trend)
        pl.addWidget(self.trend_card)

        # products
        self.prod_card = Card("Products")
        self.prod_seg = Segmented(PRODUCT_SORTS, "revenue")
        self.prod_seg.changed.connect(self._set_product_sort)
        self.prod_card.add_header_widget(self.prod_seg)
        self.prod_table = DataTable(
            [Col("product_name", "Product", stretch=True, bold=True, sub=_spec),
             Col("qty", "Qty", width=58, align="right", fmt=lambda v, r: format_qty(v)),
             Col("revenue", "Sales", width=96, align="right", fmt=lambda v, r: _money(v)),
             Col("cost", "Cost", width=96, align="right", fmt=lambda v, r: _money(v), color=lambda r: "text2"),
             Col("profit", "Profit", width=96, align="right", fmt=lambda v, r: _money(v),
                 color=lambda r: "good" if r["profit"] >= 0 else "bad", bold=True),
             Col("margin_pct", "Margin", width=72, align="right", fmt=lambda v, r: f"{v:.1f}%",
                 color=lambda r: "text2")],
            empty=("sale", "No sales in this period", "Pick a longer period to see product results."),
            sortable=False)
        self.prod_card.add(self.prod_table)
        self.prod_footer = _Footer()
        self.prod_card.add(self.prod_footer)

        # expenses
        self.exp_card = Card("Expenses")
        self.donut = DonutChart(height=170, center_caption="Spent", legend=False)
        self.exp_card.add(self.donut)
        self.exp_table = _ShareList()
        self.exp_card.add(self.exp_table)
        self.exp_footer = _Footer()
        self.exp_card.add(self.exp_footer)
        self.exp_card.body.addStretch(1)
        both = hbox(spacing=16)
        self.exp_card.setFixedWidth(380)
        both.addWidget(self.prod_card, 1)
        both.addWidget(self.exp_card)
        pl.addLayout(both)

        # day by day
        self.day_card = Card("Day by day")
        self.day_hint = label("Double-click a day to open just that day", "hint")
        self.day_card.add_header_widget(self.day_hint)
        self.day_table = DataTable(
            [Col("date", "Date", stretch=True, bold=True, fmt=lambda v, r: format_date(v),
                 sub=lambda r: _d(r["date"]).strftime("%A")),
             Col("revenue", "Sales", width=120, align="right", fmt=lambda v, r: _money(v)),
             Col("gross_profit", "Gross profit", width=120, align="right", fmt=lambda v, r: _money(v)),
             Col("expenses", "Expenses", width=120, align="right", fmt=lambda v, r: _money(v),
                 color=lambda r: "text2"),
             Col("net_profit", "Net profit", width=120, align="right", fmt=lambda v, r: _money(v), bold=True,
                 color=lambda r: "good" if r["net_profit"] >= 0 else "bad")],
            empty=("calendar", "No activity in this period", "Nothing was sold or spent on these days."),
            sortable=False)
        self.day_table.activated.connect(self._open_day)
        self.day_card.add(self.day_table)
        self.day_footer = _Footer()
        self.day_card.add(self.day_footer)
        pl.addWidget(self.day_card)

    def _build_stock(self, sv):
        self.stock_card = Card("Stock valuation")
        self.stock_table = DataTable(
            [Col("name", "Product", stretch=True, bold=True, sub=lambda r: _spec(r, "")),
             Col("stock", "In stock", width=110, align="right", fmt=lambda v, r: format_qty(v, r["unit"]),
                 color=lambda r: {"out": "bad", "low": "warn"}.get(r["status"])),
             Col("purchase_price", "Cost", width=100, align="right",
                 fmt=lambda v, r: format_currency(v), color=lambda r: "text2"),
             Col("stock_value", "Value at cost", width=130, align="right", fmt=lambda v, r: _money(v), bold=True),
             Col("retail_value", "At selling price", width=130, align="right", fmt=lambda v, r: _money(v)),
             Col("status", "Status", width=120, badge=lambda r: {"ok": ("In stock", "good"),
                                                                  "low": ("Low", "warn"),
                                                                  "out": ("Out of stock", "bad")}[r["status"]])],
            empty=("box", "No products yet", "Add products to see their stock value here."))
        self.search.searched.connect(self.stock_table.set_search)
        self.stock_card.add(self.stock_table)
        self.stock_footer = _Footer()
        self.stock_card.add(self.stock_footer)
        sv.addWidget(self.stock_card)

    # ── state ───────────────────────────────────────────────────────────
    def range(self):
        return self.range_bar.range()

    def _set_view(self, key):
        self.view_key = key
        self._apply_view()
        self.refresh()

    def _apply_view(self):
        pl = self.view_key == "pl"
        self.view_seg.set(self.view_key)
        self.pl_view.setVisible(pl)
        self.stock_view.setVisible(not pl)
        self.range_bar.setVisible(pl)
        self.asof.setVisible(not pl)
        self.search.setVisible(not pl)
        self.scroll.verticalScrollBar().setValue(0)

    def _set_product_sort(self, key):
        self.product_sort = key
        self.prod_table.view.horizontalHeader().setSortIndicator(-1, self.prod_table.view.horizontalHeader().sortIndicatorOrder())
        self._fill_products()

    def _open_day(self, row):
        self.range_bar.set_range(row["date"], row["date"])   # emits changed -> refresh

    # ── data ────────────────────────────────────────────────────────────
    def refresh(self):
        if self.view_key == "stock":
            self._refresh_stock()
        else:
            self._refresh_pl()

    def _refresh_pl(self):
        start, end = self.range()
        self.subtitle_label.setText(period_text(start, end))
        cur, prev = reports.compare(start, end)
        days = (_d(end) - _d(start)).days + 1
        vs = "vs prev. day" if days == 1 else f"vs prev. {days} days"
        self.k_sales.set_value(cur["revenue"], vs, prev["revenue"])
        self.k_gross.set_value(cur["gross_profit"], f"{cur['margin_pct']:.1f}% margin", prev["gross_profit"])
        self.k_exp.set_value(cur["expenses"], vs, prev["expenses"], good_when_up=False)
        self.k_net.set_value(cur["net_profit"], vs, prev["net_profit"])
        self.k_buy.set_value(cur["purchases"], vs, prev["purchases"])

        self.m_bills.set(f"{cur['sale_bills']:,}")
        self.m_qty.set(format_qty(cur["qty_sold"]))
        self.m_disc.set(_money(cur["discount"]))
        self.m_in.set(_money(cur["collected"]))
        self.m_out.set(_money(cur["paid_out"]))

        series = reports.daily_series(start, end)
        labels, sales, net, gran = aggregate_series(series)
        self.trend.set_data(labels, sales, net, "Sales", "Net profit")
        self.trend_hint.setText(gran)

        self._discount = cur["discount"]
        self._perf = reports.product_performance(start, end)
        self._fill_products()

        exps = reports.expense_breakdown(start, end)
        self.donut.set_data([(e["category"], e["amount"]) for e in exps])
        self.exp_table.set_rows(exps)
        self.exp_footer.set(f"{sum(e['entries'] for e in exps)} entries", _money(sum(e["amount"] for e in exps)))

        active = [s for s in series if s["revenue"] or s["expenses"] or s["gross_profit"]]
        active.sort(key=lambda s: s["date"], reverse=True)
        self.day_table.set_rows(active)
        self.day_table.fit_height(31)
        self.day_footer.set(f"{len(active)} days with activity", _money(sum(s["net_profit"] for s in active))
                            + " net")

    def _fill_products(self):
        key = self.product_sort
        rows = sorted(self._perf, key=lambda r: (-r[key], r["product_name"] or ""))
        self.prod_table.set_rows(rows)
        self.prod_table.fit_height(12)
        rev = sum(r["revenue"] for r in rows)
        profit = sum(r["profit"] for r in rows)
        self.prod_footer.set(f"{len(rows)} products · {_money(profit)} profit",
                             f"Sales {_money(rev)} before {_money(self._discount)} discounts")

    def _refresh_stock(self):
        data = reports.stock_overview()
        today = datetime.date.today()
        self.subtitle_label.setText(f"Stock as of today · {today.day} {today:%b %Y}")
        self.asof.setText("As of today. The date range does not apply here.")
        rows = []
        for p in data["items"]:
            r = dict(p)
            r["retail_value"] = round(p["stock"] * p["selling_price"], 2)
            rows.append(r)
        self.stock_table.set_rows(rows)
        self.stock_table.fit_height(14)
        self.stock_footer.set(f"{data['products']} products · {len(data['low'])} low · {len(data['out'])} out",
                              f"{_money(data['stock_value'])} at cost  ·  {_money(data['retail_value'])} at "
                              f"selling price")

    # ── exports ─────────────────────────────────────────────────────────
    def export_pdf(self, path=None):
        return self._export("pdf", path)

    def export_excel(self, path=None):
        return self._export("xlsx", path)

    def _export(self, ext, path):
        """Write the report for the chosen period. With no ``path`` a save dialog is shown and the
        finished file is opened; with a ``path`` (tests, scripts) it is only written."""
        start, end = self.range()
        interactive = path is None
        if interactive:
            docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or os.path.expanduser("~")
            name = f"PlywoodPro_Report_{start}_to_{end}.{ext}"
            kind = "PDF files (*.pdf)" if ext == "pdf" else "Excel files (*.xlsx)"
            path, _ = QFileDialog.getSaveFileName(self, "Save report", os.path.join(docs, name), kind)
            if not path:
                return None
            if not path.lower().endswith("." + ext):
                path += "." + ext
        try:
            (export.export_report_pdf if ext == "pdf" else export.export_report_excel)(start, end, path)
        except (OSError, ValueError, PermissionError) as e:
            self.toast(f"Could not save the report: {e}", "bad")
            return None
        self.last_export = path
        self.toast(f"Saved {os.path.basename(path)}")
        if interactive:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        return path
