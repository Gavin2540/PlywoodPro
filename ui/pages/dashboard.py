"""Dashboard: the shop at a glance."""
import datetime

from PySide6.QtWidgets import QGridLayout, QScrollArea, QVBoxLayout, QWidget

from models import bills, product, reports
from ui.charts import RankBars, TrendChart
from ui.table import Action, Col, DataTable
from ui.widgets import Card, Page, Segmented, StatCard, button, hbox, label
from utils.helpers import format_currency, format_date, format_qty

RANGES = [("today", "Today"), ("7d", "7 days"), ("30d", "30 days"), ("month", "This month")]


class DashboardPage(Page):
    title = "Dashboard"

    def __init__(self, app):
        super().__init__(app)
        from ui.main_window import greeting
        self.title_label.setText(greeting())
        self.subtitle_label.setText(datetime.date.today().strftime("%A, %d %B %Y"))
        self.range = Segmented(RANGES, "today")
        self.range.changed.connect(lambda _: self.refresh())
        self.add_action(self.range)
        self.add_action(button("Add expense", None, "expense", lambda: app.navigate("expenses", new=True)))
        self.add_action(button("New purchase", None, "purchase", lambda: app.navigate("purchases", new=True)))
        self.add_action(button("New sale", "primary", "plus", lambda: app.navigate("sales", new=True),
                               tooltip="Ctrl+N"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 8, 8)
        col.setSpacing(16)
        scroll.setWidget(inner)
        self.root.addWidget(scroll, 1)

        self.revenue = StatCard("Sales", "sale")
        self.gross = StatCard("Gross profit", "trend")
        self.expenses = StatCard("Expenses", "expense")
        self.net = StatCard("Net profit", "wallet", tone="sign")
        self.stock_value = StatCard("Stock value", "box")
        self.receivable = StatCard("Customers owe you", "arrow-down")
        self.payable = StatCard("You owe suppliers", "arrow-up")
        self.alerts = StatCard("Stock alerts", "alert", kind="int")
        grid = QGridLayout()
        grid.setSpacing(16)
        for i, card in enumerate((self.revenue, self.gross, self.expenses, self.net,
                                  self.stock_value, self.receivable, self.payable, self.alerts)):
            grid.addWidget(card, i // 4, i % 4)
        col.addLayout(grid)

        self.trend_card = Card("Sales and profit")
        self.trend_hint = label("", "hint")
        self.trend_card.add_header_widget(self.trend_hint)
        self.trend = TrendChart(height=250)
        self.trend_card.add(self.trend)
        self.top_card = Card("Top products")
        self.top_hint = label("", "hint")
        self.top_card.add_header_widget(self.top_hint)
        self.top = RankBars(rows=6)
        self.top_card.add(self.top)
        self.top_card.body.addStretch(1)
        self.top_card.setFixedWidth(380)
        col.addLayout(hbox(self.trend_card, self.top_card, spacing=16))

        self.low_card = Card("Needs restocking")
        self.low_card.add_header_widget(button("All products", "link", None, lambda: app.navigate("products")))
        self.low = DataTable(
            [Col("name", "Product", stretch=True, bold=True, sub=_spec),
             Col("stock", "In stock", width=110, align="right", fmt=lambda v, r: format_qty(v, r["unit"]),
                 color=lambda r: "bad" if r["status"] == "out" else "warn"),
             Col("low_stock_threshold", "Alert at", width=90, align="right", fmt=lambda v, r: format_qty(v),
                 color=lambda r: "text2"),
             Col("status", "Status", width=110,
                 badge=lambda r: ("Out of stock", "bad") if r["status"] == "out" else ("Low", "warn"))],
            actions=[Action("purchase", "Buy more", lambda r: app.navigate("purchases", new=True, product_id=r["id"]))],
            empty=("check", "Stock is healthy", "Nothing is below its alert level."), sortable=False)
        self.low_card.add(self.low)
        self.low_card.body.addStretch(1)

        self.recent_card = Card("Recent bills")
        self.recent_card.add_header_widget(button("All sales", "link", None, lambda: app.navigate("sales")))
        self.recent = DataTable(
            [Col("party_name", "Bill", stretch=True, bold=True,
                 fmt=lambda v, r: v or ("Walk-in customer" if r["kind"] == "sale" else "Supplier"),
                 sub=lambda r: f"{r['bill_no']} · {format_date(r['date'])} · {r['summary'] or ''}"),
             Col("kind", "Type", width=100, badge=lambda r: ("Sale", "good") if r["kind"] == "sale" else ("Purchase", "info")),
             Col("total", "Amount", width=120, align="right", fmt=lambda v, r: format_currency(v, decimals=0)),
             Col("due", "Status", width=110,
                 badge=lambda r: ("Paid", "neutral") if r["due"] <= 0.004 else (f"Due {format_currency(r['due'], decimals=0)}", "warn"))],
            empty=("sale", "No bills yet", "Record your first sale or purchase to see it here."), sortable=False)
        self.recent.activated.connect(lambda r: app.navigate("sales" if r["kind"] == "sale" else "purchases", bill_id=r["id"]))
        self.recent_card.add(self.recent)
        self.recent_card.body.addStretch(1)
        col.addLayout(hbox(self.low_card, self.recent_card, spacing=16))
        col.addStretch(1)

    def refresh(self):
        from ui.widgets import DateRangeBar
        key = self.range.current() or "today"
        start, end = DateRangeBar.preset_range(key)
        cur, prev = reports.compare(start, end)
        vs = {"today": "vs yesterday", "7d": "vs previous 7 days", "30d": "vs previous 30 days",
              "month": "vs previous period"}[key]
        self.revenue.set_value(cur["revenue"], f"{cur['sale_bills']} bills · {vs}", prev["revenue"])
        self.gross.set_value(cur["gross_profit"], f"{cur['margin_pct']:.1f}% margin", prev["gross_profit"])
        self.expenses.set_value(cur["expenses"], vs, prev["expenses"], good_when_up=False)
        self.net.set_value(cur["net_profit"], "after expenses", prev["net_profit"])

        overview = reports.stock_overview()
        owed = reports.outstanding()
        self.stock_value.set_value(overview["stock_value"], f"{overview['products']} products, at cost")
        self.receivable.set_value(owed["receivable"], "unpaid sale bills")
        self.payable.set_value(owed["payable"], "unpaid purchase bills")
        n_low, n_out = len(overview["low"]), len(overview["out"])
        self.alerts.set_value(n_low + n_out, f"{n_out} out of stock · {n_low} low")
        self.alerts.value.setProperty("role", "value")

        today = datetime.date.today()
        chart_start = min(start, today - datetime.timedelta(days=13))
        series = reports.daily_series(chart_start, today)
        fmt = "%d %b" if len(series) > 14 else "%a %d"
        self.trend.set_data([datetime.date.fromisoformat(s["date"]).strftime(fmt) for s in series],
                            [s["revenue"] for s in series], [s["net_profit"] for s in series],
                            "Sales", "Net profit")
        self.trend_hint.setText(f"Last {len(series)} days")

        top_start = min(start, today - datetime.timedelta(days=29))
        perf = reports.product_performance(top_start, today)
        self.top.set_data([(_short(p), p["revenue"], format_qty(p["qty"], p["product_unit"])) for p in perf])
        self.top_hint.setText(f"Last {(today - top_start).days + 1} days, by sales")

        low = sorted(overview["out"] + overview["low"], key=lambda p: p["stock"])
        self.low.set_rows(low)
        self.low.fit_height(6)
        self.recent.set_rows(bills.list_bills()[:6])
        self.recent.fit_height(6)


def _spec(p):
    return " · ".join(str(p[k]) for k in ("brand", "type", "thickness", "size") if p.get(k))


def _short(p):
    head = " ".join(str(p[k]) for k in ("product_name", "product_thickness") if p.get(k))
    return f"{head} · {p['product_brand']}" if p.get("product_brand") else head
