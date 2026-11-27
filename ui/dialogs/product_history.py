"""Stock movement history of one product."""
from models import product, stock
from ui.table import Col, DataTable
from ui.widgets import Dialog, DateRangeBar, hbox, label, vbox
from utils.helpers import format_currency, format_date, format_qty

_KINDS = {"purchase": ("Purchase", "info"), "sale": ("Sale", "good"), "count": ("Stock count", "warn")}


def _party(r):
    if r["kind"] == "count":
        return r.get("note") or "Physical count"
    return r.get("party") or ("Walk-in customer" if r["kind"] == "sale" else "Supplier")


def _sub(r):
    if r["kind"] == "count":
        v = r.get("variance") or 0
        return f"Counted {format_qty(r['qty'])} · " + ("matches stock" if abs(v) < 1e-6 else f"{v:+g} difference")
    return r.get("bill_no") or ""


class ProductHistoryDialog(Dialog):
    def __init__(self, parent, product_id):
        super().__init__(parent, "Stock history", ok_text="Close", cancel_text="", width=860)
        self.product_id = product_id
        self.p = product.get_product_by_id(product_id) or {}
        self.heading = label("", "heading")
        self.summary = label("", "muted")
        self.range = DateRangeBar("30d")
        self.range.changed.connect(lambda *_: self.reload())
        self.body.addLayout(vbox(self.heading, self.summary, spacing=2))
        self.body.addLayout(hbox(self.range, None))
        unit = self.p.get("unit")
        self.table = DataTable([
            Col("date", "Date", width=100, fmt=lambda v, r: format_date(v)),
            Col("kind", "Type", width=120, badge=lambda r: _KINDS[r["kind"]]),
            Col("party", "Party / bill", stretch=True, bold=True, fmt=lambda v, r: _party(r), sub=_sub),
            Col("in", "In", width=90, align="right", fmt=lambda v, r: format_qty(v) if v else "—",
                color=lambda r: "good" if r.get("in") else "text3"),
            Col("out", "Out", width=90, align="right", fmt=lambda v, r: format_qty(v) if v else "—",
                color=lambda r: "bad" if r.get("out") else "text3"),
            Col("unit_price", "Rate", width=100, align="right",
                fmt=lambda v, r: format_currency(v) if v is not None else "—", color=lambda r: "text2"),
            Col("balance", "Balance", width=100, align="right", bold=True,
                fmt=lambda v, r: format_qty(v, unit))],
            empty=("history", "No movement in this period", "Pick a longer date range to see older entries."),
            sortable=False)
        self.table.setMinimumHeight(8 * 46 + 42)
        self.body.addWidget(self.table, 1)
        self.reload()

    def reload(self):
        p = self.p
        stock_now = stock.stock_on(self.product_id)
        value = round(stock_now * (p.get("purchase_price") or 0), 2)
        self.heading.setText(product.label(p) if p else "Product")
        self.summary.setText(f"In stock {format_qty(stock_now, p.get('unit'))} · stock worth "
                             f"{format_currency(value, decimals=0)} at cost")
        rows = stock.product_movements(self.product_id, *self.range.range())
        for r in rows:
            r["in"] = r["qty"] if r["kind"] == "purchase" else 0
            r["out"] = r["qty"] if r["kind"] == "sale" else 0
        self.table.set_rows(rows)
