"""A4 invoice (sale) or purchase record (purchase) as a PDF, built with reportlab."""
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from models import bills, product, settings
from utils.helpers import format_currency, format_date, format_qty

ACCENT = colors.HexColor("#8A5A12")
INK = colors.HexColor("#1F1A15")
MUTED = colors.HexColor("#6A6057")
GOOD = colors.HexColor("#1F7A4D")
RULE = colors.HexColor("#DDD5CA")
TINT = colors.HexColor("#F6F1EA")
SYMBOL = "Rs. "  # Helvetica has no rupee glyph


def _money(x):
    return format_currency(x, symbol=SYMBOL)


def _styles():
    base = dict(fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)
    return {
        "body": ParagraphStyle("body", **base),
        "right": ParagraphStyle("right", alignment=TA_RIGHT, **base),
        "muted": ParagraphStyle("muted", **{**base, "textColor": MUTED, "fontSize": 9}),
        "mutedr": ParagraphStyle("mutedr", alignment=TA_RIGHT, **{**base, "textColor": MUTED, "fontSize": 9}),
        "shop": ParagraphStyle("shop", **{**base, "fontName": "Helvetica-Bold", "fontSize": 18, "leading": 22}),
        "title": ParagraphStyle("title", alignment=TA_RIGHT,
                                **{**base, "fontName": "Helvetica-Bold", "fontSize": 20, "leading": 24, "textColor": ACCENT}),
        "label": ParagraphStyle("label", **{**base, "fontName": "Helvetica-Bold", "fontSize": 8, "textColor": MUTED}),
        "head": ParagraphStyle("head", **{**base, "fontName": "Helvetica-Bold", "textColor": colors.white, "fontSize": 9}),
        "headr": ParagraphStyle("headr", alignment=TA_RIGHT,
                                **{**base, "fontName": "Helvetica-Bold", "textColor": colors.white, "fontSize": 9}),
        "strong": ParagraphStyle("strong", **{**base, "fontName": "Helvetica-Bold"}),
        "strongr": ParagraphStyle("strongr", alignment=TA_RIGHT, **{**base, "fontName": "Helvetica-Bold"}),
        "grand": ParagraphStyle("grand", alignment=TA_RIGHT,
                                **{**base, "fontName": "Helvetica-Bold", "fontSize": 11.5, "leading": 15, "textColor": ACCENT}),
        "paidfull": ParagraphStyle("paidfull", alignment=TA_RIGHT,
                                   **{**base, "fontName": "Helvetica-Bold", "fontSize": 12, "textColor": GOOD}),
        "footer": ParagraphStyle("footer", **{**base, "textColor": MUTED, "fontSize": 9}),
    }


def _p(text, style):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def invoice_pdf(bill_id, path):
    """Write the bill as a PDF at ``path`` and return the path."""
    bill = bills.get_bill(bill_id)
    if not bill:
        raise ValueError("Bill not found.")
    st = _styles()
    sale = bill["kind"] == "sale"
    cfg = settings.get_all()
    shop = (cfg.get("shop_name") or "").strip() or "Plywood Pro"
    width = A4[0] - 36 * mm
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"{bill['bill_no']}", author=shop)
    story = []

    # header: shop on the left, document title on the right
    shop_lines = [_p(shop, st["shop"])]
    for text in ((cfg.get("shop_address") or "").strip(), (cfg.get("shop_phone") or "").strip()):
        if text:
            shop_lines.append(_p(text, st["muted"]))
    gst = (cfg.get("shop_gstin") or "").strip()
    if gst:
        shop_lines.append(_p(f"GSTIN: {gst}", st["muted"]))
    meta = [_p("INVOICE" if sale else "PURCHASE RECORD", st["title"]),
            _p(f"No. {bill['bill_no']}", st["strongr"]),
            _p(f"Date: {format_date(bill['date'])}", st["mutedr"])]
    head = Table([[shop_lines, meta]], colWidths=[width * 0.58, width * 0.42])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    story += [head, Spacer(1, 5 * mm), HRFlowable(width="100%", thickness=1.4, color=ACCENT), Spacer(1, 5 * mm)]

    # party
    party = [_p("BILL TO" if sale else "SUPPLIER", st["label"]),
             _p(bill["party_name"] or ("Walk-in customer" if sale else "Supplier"), st["strong"])]
    if bill.get("party_phone"):
        party.append(_p(bill["party_phone"], st["muted"]))
    story += [Table([[party]], colWidths=[width], style=[("LEFTPADDING", (0, 0), (-1, -1), 0)]), Spacer(1, 6 * mm)]

    # items
    rows = [[_p("#", st["head"]), _p("Description", st["head"]), _p("Qty", st["headr"]),
             _p("Rate", st["headr"]), _p("Amount", st["headr"])]]
    for i, ln in enumerate(bill["lines"], start=1):
        rows.append([_p(i, st["body"]), _p(product.label(ln), st["body"]),
                     _p(format_qty(ln["qty"], ln.get("product_unit")), st["right"]),
                     _p(_money(ln["unit_price"]), st["right"]), _p(_money(ln["amount"]), st["right"])])
    cols = [8 * mm, width - 8 * mm - 22 * mm - 30 * mm - 32 * mm, 22 * mm, 30 * mm, 32 * mm]
    items = Table(rows, colWidths=cols, repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), ACCENT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
             ("LINEBELOW", (0, 1), (-1, -1), 0.5, RULE), ("LINEBELOW", (0, -1), (-1, -1), 0.8, ACCENT)]
    for r in range(2, len(rows), 2):
        style.append(("BACKGROUND", (0, r), (-1, r), TINT))
    items.setStyle(TableStyle(style))
    story += [items, Spacer(1, 4 * mm)]

    # totals
    t = [[_p("Subtotal", st["body"]), _p(_money(bill["subtotal"]), st["right"])]]
    if bill["discount"]:
        t.append([_p("Discount", st["body"]), _p("- " + _money(bill["discount"]), st["right"])])
    t.append([_p("Total", st["strong"]), _p(_money(bill["total"]), st["grand"])])
    settled = bill["due"] <= 0.004
    if settled:
        t.append(["", _p("PAID IN FULL", st["paidfull"])])
    else:
        t.append([_p("Paid" if sale else "Paid to supplier", st["body"]), _p(_money(bill["paid"]), st["right"])])
        t.append([_p("Balance due", st["strong"]), _p(_money(max(bill["due"], 0)), st["strongr"])])
    totals = Table(t, colWidths=[40 * mm, 46 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                ("LINEABOVE", (0, 2 if bill["discount"] else 1), (-1, 2 if bill["discount"] else 1), 0.8, ACCENT),
                                ("LINEABOVE", (0, -1), (-1, -1), 0.5, RULE)]))
    story.append(totals)

    pays = bill["payments"]
    if len(pays) > 1:
        story += [Spacer(1, 6 * mm), _p("PAYMENTS", st["label"]), Spacer(1, 1.5 * mm)]
        prow = [[_p(format_date(p["date"]), st["body"]), _p(p["method"] or "", st["body"]),
                 _p(p["note"] or "", st["muted"]), _p(_money(p["amount"]), st["right"])] for p in pays]
        pt = Table(prow, colWidths=[28 * mm, 34 * mm, width - 28 * mm - 34 * mm - 36 * mm, 36 * mm])
        pt.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (0, -1), 0)]))
        story.append(pt)

    if bill.get("notes"):
        story += [Spacer(1, 5 * mm), _p("NOTES", st["label"]), _p(bill["notes"], st["muted"])]

    footer = (cfg.get("invoice_footer") or "").strip()
    if footer:
        story += [Spacer(1, 10 * mm), _p(footer, st["footer"])]
    sig = Table([["", _p("Authorised signature", st["mutedr"])]], colWidths=[width - 60 * mm, 60 * mm],
                style=[("LINEABOVE", (1, 0), (1, 0), 0.6, MUTED), ("TOPPADDING", (0, 0), (-1, -1), 4),
                       ("RIGHTPADDING", (0, 0), (-1, -1), 0)])
    story += [Spacer(1, 22 * mm), sig]
    doc.build(story)
    return path
