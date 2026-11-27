"""Report exports (PDF and Excel) for any date range. Data comes from the models only."""
import datetime
from xml.sax.saxutils import escape

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (CondPageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from models import bills, expense, reports, settings, stock
from utils.helpers import format_currency, format_date, format_qty

MAX_ITEMISED = 60          # more lines than this -> summarise by product in the PDF
BRAND = "#BA7517"
INK = "#1F1E1B"
GREEN = "#1F8F55"
RED = "#C0392B"
MUTED = "#6B665E"
RULE = "#E2DED6"
ZEBRA = "#F8F6F2"
NUM_FMT = "#,##0.00"


# ── shared data ─────────────────────────────────────────────────────────
def _iso(d):
    return d.isoformat() if isinstance(d, (datetime.date, datetime.datetime)) else str(d)[:10]


def _norm(date_from, date_to):
    a, b = _iso(date_from), _iso(date_to)
    return (b, a) if a > b else (a, b)


def _product_text(r, prefix="product_"):
    """'Plywood 18mm · Greenply · 8x4' from a model row."""
    head = " ".join(str(r.get(prefix + k)) for k in ("name", "thickness") if r.get(prefix + k))
    extra = [str(r[prefix + k]) for k in ("brand", "size") if r.get(prefix + k)]
    return " · ".join([head] + extra) if head else " · ".join(extra)


def _period_text(a, b):
    if a == b:
        return f"Daily report — {format_date(a)}"
    return f"{format_date(a)} to {format_date(b)}"


def _shop():
    s = settings.get_all()
    return {"name": (s.get("shop_name") or "").strip() or "Plywood Pro",
            "address": (s.get("shop_address") or "").strip(),
            "phone": (s.get("shop_phone") or "").strip(),
            "gstin": (s.get("shop_gstin") or "").strip()}


def _collect(date_from, date_to):
    a, b = _norm(date_from, date_to)
    data = {
        "from": a, "to": b, "single": a == b,
        "shop": _shop(),
        "summary": reports.summary(a, b),
        "sales": bills.list_lines("sale", a, b),
        "purchases": bills.list_lines("purchase", a, b),
        "expenses": expense.list_expenses(a, b),
        "products": reports.product_performance(a, b),
        "daily": reports.daily_series(a, b),
        "ledger": stock.day_ledger(a) if a == b else None,
        "stock": None,
    }
    if a != b:
        data["stock"] = reports.stock_overview()
    return data


def _purchase_by_product(lines):
    agg = {}
    for r in lines:
        d = agg.setdefault(r["product_id"], {"product": _product_text(r), "unit": r.get("product_unit"),
                                             "qty": 0.0, "amount": 0.0})
        d["qty"] += r["qty"]
        d["amount"] += r["amount"]
    return sorted(agg.values(), key=lambda x: -x["amount"])


def _ledger_note(r):
    if r.get("is_counted"):
        return "Counted"
    return "Closed" if r.get("is_locked") else ""


# ── PDF ─────────────────────────────────────────────────────────────────
def _rs(x):
    return format_currency(x, symbol="Rs. ")


def _styles():
    base = getSampleStyleSheet()["Normal"]

    def ps(name, **kw):
        return ParagraphStyle(name, parent=base, **kw)
    return {
        "shop": ps("shop", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=colors.HexColor(INK)),
        "meta": ps("meta", fontSize=8.5, leading=11, textColor=colors.HexColor(MUTED)),
        "title": ps("title", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.HexColor(BRAND),
                    alignment=2),
        "period": ps("period", fontSize=9.5, leading=12, textColor=colors.HexColor(INK), alignment=2),
        "h": ps("h", fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=colors.HexColor(INK),
                spaceBefore=14, spaceAfter=5),
        "note": ps("note", fontSize=8, leading=10.5, textColor=colors.HexColor(MUTED), spaceAfter=4,
                   fontName="Helvetica-Oblique"),
        "cell": ps("cell", fontSize=8, leading=10),
        "cellr": ps("cellr", fontSize=8, leading=10, alignment=2),
        "head": ps("head", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white),
        "headr": ps("headr", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white,
                    alignment=2),
        "kpi_l": ps("kpi_l", fontSize=7.5, leading=9, textColor=colors.HexColor(MUTED)),
        "kpi_v": ps("kpi_v", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor(INK)),
        "kpi_s": ps("kpi_s", fontSize=7.5, leading=9, textColor=colors.HexColor(MUTED)),
        "empty": ps("empty", fontSize=9, leading=12, textColor=colors.HexColor(MUTED)),
    }


def _p(text, style):
    return Paragraph(escape(str(text if text is not None else "")), style)


def _table(headers, rows, widths, st, right=(), total=None):
    """Header row (repeats on page breaks), body rows, optional bold total row."""
    right = set(right)
    data = [[_p(h, st["headr"] if i in right else st["head"]) for i, h in enumerate(headers)]]
    for r in rows:
        data.append([c if not isinstance(c, (str, int, float)) else _p(c, st["cellr"] if i in right else st["cell"])
                     for i, c in enumerate(r)])
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(INK)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor(RULE)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(ZEBRA)]),
    ]
    if total:
        bold_r = ParagraphStyle("tr", parent=st["cellr"], fontName="Helvetica-Bold")
        bold_l = ParagraphStyle("tl", parent=st["cell"], fontName="Helvetica-Bold")
        data.append([_p(c, bold_r if i in right else bold_l) for i, c in enumerate(total)])
        cmds += [("LINEABOVE", (0, -1), (-1, -1), 0.9, colors.HexColor(INK)),
                 ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EFEAE0"))]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


def _kpi_block(s, st, width):
    def cell(label, value, sub=""):
        return [_p(label.upper(), st["kpi_l"]), _p(value, st["kpi_v"]), _p(sub, st["kpi_s"])]
    row1 = [cell("Sales", _rs(s["revenue"]), f"{s['sale_bills']} {'bill' if s['sale_bills'] == 1 else 'bills'} · {format_qty(s['qty_sold'])} qty"),
            cell("Gross profit", _rs(s["gross_profit"]), f"{s['margin_pct']:.1f}% margin"),
            cell("Expenses", _rs(s["expenses"])),
            cell("Purchases", _rs(s["purchases"]), f"{s['purchase_bills']} {'bill' if s['purchase_bills'] == 1 else 'bills'}")]
    row2 = [cell("Collected from customers", _rs(s["collected"])),
            cell("Paid to suppliers", _rs(s["paid_out"])),
            cell("Discounts given", _rs(s["discount"])), ""]
    w = width / 4
    t = Table([row1, row2], colWidths=[w] * 4)
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(RULE)),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor(RULE)),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(ZEBRA)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    net = s["net_profit"]
    good = net >= 0
    colr = colors.HexColor(GREEN if good else RED)
    banner = Table([[Paragraph(f'<font color="white"><b>{"NET PROFIT" if good else "NET LOSS"}</b></font>',
                               ParagraphStyle("b1", parent=st["cell"], fontSize=10, leading=13)),
                     Paragraph(f'<font color="white"><b>{escape(_rs(net))}</b></font>',
                               ParagraphStyle("b2", parent=st["cellr"], fontSize=14, leading=17))]],
                   colWidths=[width * 0.5, width * 0.5])
    banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colr), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                                ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
    return [t, Spacer(1, 5), banner]


def export_report_pdf(date_from, date_to, path):
    """Business report PDF (A4 portrait). A single day also gets the day's stock ledger."""
    data = _collect(date_from, date_to)
    a, b, s, shop = data["from"], data["to"], data["summary"], data["shop"]
    st = _styles()
    width = A4[0] - 3 * cm
    generated = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.setStrokeColor(colors.HexColor(RULE))
        canvas.line(1.5 * cm, 1.15 * cm, A4[0] - 1.5 * cm, 1.15 * cm)
        canvas.drawString(1.5 * cm, 0.7 * cm, f"Generated on {generated}")
        canvas.drawRightString(A4[0] - 1.5 * cm, 0.7 * cm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.7 * cm,
                            title=f"{shop['name']} - Business report", author=shop["name"])
    story = []
    contact = " · ".join(x for x in (f"Phone {shop['phone']}" if shop["phone"] else "",
                                      f"GSTIN {shop['gstin']}" if shop["gstin"] else "") if x)
    left = [_p(shop["name"], st["shop"])] + [_p(m, st["meta"]) for m in (shop["address"], contact) if m]
    head = Table([[left, [_p("Business report", st["title"]), _p(_period_text(a, b), st["period"])]]],
                 colWidths=[width * 0.58, width * 0.42])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                              ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(BRAND)),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [head, Spacer(1, 10)]
    story += _kpi_block(s, st, width)

    # Sales
    story += [CondPageBreak(4 * cm), _p("Sales", st["h"])]
    sales = data["sales"]
    if not sales:
        story.append(_p("No sales in this period.", st["empty"]))
    elif len(sales) <= MAX_ITEMISED:
        single = data["single"]
        rows = [([] if single else [format_date(r["date"], "%d-%m")]) +
                [r["bill_no"] or "", _p(_product_text(r), st["cell"]), format_qty(r["qty"]),
                 _rs(r["unit_price"]), _rs(r["cost"]), _rs(r["amount"]), _rs(r["margin"])] for r in sales]
        tot = (["Total", ""] if single else ["Total", "", ""]) + [
            format_qty(sum(r["qty"] for r in sales)), "", _rs(sum(r["cost_amount"] for r in sales)),
            _rs(sum(r["amount"] for r in sales)), _rs(sum(r["margin"] for r in sales))]
        lead = [] if single else [1.3 * cm]
        fixed = [1.7 * cm, 1.5 * cm, 2.45 * cm, 2.45 * cm, 2.6 * cm, 2.4 * cm]   # bill, qty, rate, cost, amount, margin
        widths = lead + [fixed[0], width - sum(lead) - sum(fixed)] + fixed[1:]
        headers = ([] if single else ["Date"]) + ["Bill", "Product", "Qty", "Rate", "Cost", "Amount", "Margin"]
        k = len(lead)
        story.append(_table(headers, rows, widths, st, right=tuple(range(k + 2, k + 7)), total=tot))
        story += _net_sales(s, st)
    else:
        story.append(_p(f"{len(sales)} lines in this period, so they are summarised by product. "
                        f"Sales {_rs(sum(r['revenue'] for r in data['products']))} before "
                        f"{_rs(s['discount'])} discounts.", st["note"]))
        story.append(_product_table(data["products"], st))
        story += _net_sales(s, st)

    # Purchases
    story += [CondPageBreak(4 * cm), _p("Purchases", st["h"])]
    purchases = data["purchases"]
    if not purchases:
        story.append(_p("No purchases in this period.", st["empty"]))
    elif len(purchases) <= MAX_ITEMISED:
        rows = [[format_date(r["date"]), r["bill_no"] or "", _p(r["party_name"] or "", st["cell"]),
                 _p(_product_text(r), st["cell"]), format_qty(r["qty"]),
                 _rs(r["unit_price"]), _rs(r["amount"])] for r in purchases]
        tot = ["Total", "", "", "", format_qty(sum(r["qty"] for r in purchases)), "",
               _rs(sum(r["amount"] for r in purchases))]
        story.append(_table(["Date", "Bill", "Supplier", "Product", "Qty", "Rate", "Amount"], rows,
                            [2.0 * cm, 1.6 * cm, 2.8 * cm, 4.6 * cm, 1.5 * cm, 2.5 * cm, 3.0 * cm],
                            st, right=(4, 5, 6), total=tot))
    else:
        story.append(_p(f"{len(purchases)} lines in this period, so they are summarised by product.", st["note"]))
        agg = _purchase_by_product(purchases)
        rows = [[_p(x["product"], st["cell"]), format_qty(x["qty"], x["unit"]), _rs(x["amount"])] for x in agg]
        story.append(_table(["Product", "Qty bought", "Amount"], rows, [10 * cm, 3.5 * cm, 4.5 * cm], st,
                            right=(1, 2), total=["Total", format_qty(sum(x["qty"] for x in agg)),
                                                 _rs(sum(x["amount"] for x in agg))]))

    # Expenses
    story += [CondPageBreak(4 * cm), _p("Expenses", st["h"])]
    exps = data["expenses"]
    if not exps:
        story.append(_p("No expenses in this period.", st["empty"]))
    else:
        rows = [[format_date(r["date"]), _p(r["category"], st["cell"]), _p(r["note"] or "", st["cell"]),
                 _rs(r["amount"])] for r in exps]
        story.append(_table(["Date", "Category", "Note", "Amount"], rows,
                            [2.0 * cm, 4.0 * cm, 8.5 * cm, 3.5 * cm], st, right=(3,),
                            total=["Total", "", "", _rs(sum(r["amount"] for r in exps))]))

    # Day stock
    if data["ledger"] is not None:
        story += [CondPageBreak(4 * cm), _p("Stock for the day", st["h"])]
        led = data["ledger"]
        if not led:
            story.append(_p("No products to show.", st["empty"]))
        else:
            rows = [[_p(_product_text(r), st["cell"]), format_qty(r["opening_stock"]),
                     format_qty(r["purchases_qty"]), format_qty(r["sales_qty"]),
                     format_qty(r["closing_stock"], r.get("product_unit")), _ledger_note(r)] for r in led]
            story.append(_table(["Product", "Opening", "In", "Out", "Closing", "Note"], rows,
                                [7.0 * cm, 2.0 * cm, 1.8 * cm, 1.8 * cm, 2.9 * cm, 2.5 * cm], st,
                                right=(1, 2, 3, 4)))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return str(path)


def _net_sales(s, st):
    """'Less: discounts' and 'Net sales' lines under the sales table; net equals the Sales KPI."""
    bold = ParagraphStyle("nsb", parent=st["cellr"], fontName="Helvetica-Bold")
    t = Table([[_p("Less: discounts", st["cellr"]), _p(_rs(-abs(s["discount"])), st["cellr"])],
               [_p("Net sales", bold), _p(_rs(s["revenue"]), bold)]], colWidths=[4 * cm, 3.4 * cm], hAlign="RIGHT")
    t.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                           ("LINEABOVE", (0, 1), (-1, 1), 0.6, colors.HexColor(INK))]))
    return [Spacer(1, 3), t]


def _product_table(perf, st):
    rows = [[_p(_product_text(r), st["cell"]), format_qty(r["qty"], r.get("product_unit")), _rs(r["revenue"]),
             _rs(r["cost"]), _rs(r["profit"]), f"{r['margin_pct']:.1f}%"] for r in perf]
    tot = ["Total", "", _rs(sum(r["revenue"] for r in perf)), _rs(sum(r["cost"] for r in perf)),
           _rs(sum(r["profit"] for r in perf)), ""]
    return _table(["Product", "Qty", "Sales", "Cost", "Profit", "Margin %"], rows,
                  [6.2 * cm, 2.2 * cm, 2.7 * cm, 2.7 * cm, 2.5 * cm, 1.7 * cm], st, right=(1, 2, 3, 4, 5), total=tot)


# ── Excel ───────────────────────────────────────────────────────────────
_HEAD_FILL = PatternFill("solid", start_color="BA7517", end_color="BA7517")
_HEAD_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
_TOTAL_FILL = PatternFill("solid", start_color="F3EEE3", end_color="F3EEE3")
_THIN = Side(style="thin", color="D8D2C6")


def _sheet(wb, title, headers, rows, money=(), total=None, widths=None, first=False):
    """Header row + data rows (+ totals row as values). ``money`` = 0-based numeric columns."""
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.append(headers)
    for cell in ws[1]:
        cell.font, cell.fill = _HEAD_FONT, _HEAD_FILL
        cell.alignment = Alignment(horizontal="center" if cell.column - 1 not in money else "right",
                                   vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 24
    for r in rows:
        ws.append(list(r))
    if total:
        ws.append(list(total))
        for cell in ws[ws.max_row]:
            cell.font, cell.fill = Font(name="Calibri", size=11, bold=True), _TOTAL_FILL
            cell.border = Border(top=Side(style="medium", color="1F1E1B"))
    for row in ws.iter_rows(min_row=2):
        for i, cell in enumerate(row):
            if i in money and isinstance(cell.value, (int, float)):
                cell.number_format = NUM_FMT
                cell.alignment = Alignment(horizontal="right")
    ws.freeze_panes = "A2"
    for i, h in enumerate(headers):
        longest = max([len(str(h))] + [len(str(r[i])) for r in rows if i < len(r) and r[i] is not None] + [0])
        ws.column_dimensions[get_column_letter(i + 1)].width = (widths[i] if widths else
                                                                 min(46, max(11, longest + 3)))
    return ws


def export_report_excel(date_from, date_to, path):
    data = _collect(date_from, date_to)
    a, b, s = data["from"], data["to"], data["summary"]
    wb = openpyxl.Workbook()

    summary_rows = [
        ("Shop", data["shop"]["name"]), ("Period", _period_text(a, b)),
        ("Sales", s["revenue"]), ("Cost of goods sold", s["cost"]), ("Discounts given", s["discount"]),
        ("Gross profit", s["gross_profit"]), ("Margin %", s["margin_pct"]), ("Expenses", s["expenses"]),
        ("Net profit", s["net_profit"]), ("Purchases", s["purchases"]),
        ("Collected from customers", s["collected"]), ("Paid to suppliers", s["paid_out"]),
        ("Sale bills", s["sale_bills"]), ("Quantity sold", s["qty_sold"]),
        ("Purchase bills", s["purchase_bills"]), ("Quantity purchased", s["qty_purchased"]),
    ]
    ws = _sheet(wb, "Summary", ["Item", "Value"], summary_rows, money=(1,), widths=[30, 26], first=True)
    for row in ws.iter_rows(min_row=2):
        if row[0].value in ("Sale bills", "Purchase bills"):
            row[1].number_format = "0"
        elif row[0].value in ("Net profit", "Gross profit", "Sales"):
            row[0].font = row[1].font = Font(name="Calibri", size=11, bold=True)
        if row[0].value in ("Shop", "Period"):
            row[1].alignment = Alignment(horizontal="left")

    sales = data["sales"]
    _sheet(wb, "Sales", ["Date", "Bill", "Customer", "Product", "Qty", "Rate", "Cost", "Amount", "Margin"],
           [(r["date"], r["bill_no"], r["party_name"] or "", _product_text(r), r["qty"], r["unit_price"],
             r["cost"], r["amount"], r["margin"]) for r in sales], money=(4, 5, 6, 7, 8),
           total=("Total", "", "", "", sum(r["qty"] for r in sales), "", sum(r["cost_amount"] for r in sales),
                  round(sum(r["amount"] for r in sales), 2), round(sum(r["margin"] for r in sales), 2)),
           widths=[12, 12, 22, 36, 10, 12, 12, 14, 14])
    wsx = wb["Sales"]
    for label_, val in (("Less: discounts", -s["discount"]), ("Net sales", s["revenue"])):
        wsx.append([label_, "", "", "", "", "", "", val])
        for cell in wsx[wsx.max_row]:
            cell.font = Font(name="Calibri", size=11, bold=label_ == "Net sales")
        wsx.cell(wsx.max_row, 8).number_format = NUM_FMT
    purchases = data["purchases"]
    _sheet(wb, "Purchases", ["Date", "Bill", "Supplier", "Product", "Qty", "Rate", "Amount"],
           [(r["date"], r["bill_no"], r["party_name"] or "", _product_text(r), r["qty"], r["unit_price"],
             r["amount"]) for r in purchases], money=(4, 5, 6),
           total=("Total", "", "", "", sum(r["qty"] for r in purchases), "",
                  round(sum(r["amount"] for r in purchases), 2)),
           widths=[12, 12, 22, 36, 10, 12, 14])
    exps = data["expenses"]
    _sheet(wb, "Expenses", ["Date", "Category", "Note", "Amount"],
           [(r["date"], r["category"], r["note"] or "", r["amount"]) for r in exps], money=(3,),
           total=("Total", "", "", round(sum(r["amount"] for r in exps), 2)), widths=[12, 22, 44, 14])
    perf = data["products"]
    _sheet(wb, "Products", ["Product", "Qty sold", "Sales", "Cost", "Profit", "Margin %"],
           [(_product_text(r), r["qty"], r["revenue"], r["cost"], r["profit"], r["margin_pct"]) for r in perf],
           money=(1, 2, 3, 4, 5),
           total=("Total", sum(r["qty"] for r in perf), round(sum(r["revenue"] for r in perf), 2),
                  round(sum(r["cost"] for r in perf), 2), round(sum(r["profit"] for r in perf), 2), ""),
           widths=[40, 12, 14, 14, 14, 11])
    daily = data["daily"]
    _sheet(wb, "Daily", ["Date", "Sales", "Gross profit", "Expenses", "Net profit"],
           [(d["date"], d["revenue"], d["gross_profit"], d["expenses"], d["net_profit"]) for d in daily],
           money=(1, 2, 3, 4),
           total=("Total", round(sum(d["revenue"] for d in daily), 2), round(sum(d["gross_profit"] for d in daily), 2),
                  round(sum(d["expenses"] for d in daily), 2), round(sum(d["net_profit"] for d in daily), 2)),
           widths=[12, 14, 14, 14, 14])
    if data["ledger"] is not None:
        led = data["ledger"]
        _sheet(wb, "Stock", ["Product", "Opening", "In", "Out", "Closing", "Note"],
               [(_product_text(r), r["opening_stock"], r["purchases_qty"], r["sales_qty"], r["closing_stock"],
                 _ledger_note(r)) for r in led], money=(1, 2, 3, 4), widths=[40, 12, 12, 12, 12, 12])
    else:
        items = data["stock"]["items"]
        _sheet(wb, "Stock", ["Product", "In stock", "Cost", "Stock value at cost", "Value at selling price",
                             "Status"],
               [(_product_text(p, ""), p["stock"], p["purchase_price"], p["stock_value"],
                 round(p["stock"] * p["selling_price"], 2),
                 {"ok": "OK", "low": "Low", "out": "Out of stock"}.get(p["status"], p["status"])) for p in items],
               money=(1, 2, 3, 4),
               total=("Total", "", "", data["stock"]["stock_value"], data["stock"]["retail_value"], ""),
               widths=[40, 12, 12, 20, 22, 14])
    wb.save(str(path))
    return str(path)


# ── backwards-compatible wrappers ───────────────────────────────────────
def export_daily_pdf(date_str, filepath):
    return export_report_pdf(date_str, date_str, filepath)


def export_daily_excel(date_str, filepath):
    return export_report_excel(date_str, date_str, filepath)
