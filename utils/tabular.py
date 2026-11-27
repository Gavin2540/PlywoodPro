"""Save any on-screen table to Excel or CSV."""
import csv

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def export_rows(path, title, headers, rows, money_columns=()):
    """Write rows (lists of plain values) to .xlsx, or .csv when the path ends with .csv.

    money_columns: zero-based column indexes formatted as currency in Excel.
    """
    if path.lower().endswith(".csv"):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(headers)
            w.writerows(rows)
        return path
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="8A5A12")
        c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 22
    for r in rows:
        ws.append(list(r))
    for i, h in enumerate(headers):
        width = max([len(str(h))] + [len(str(r[i])) for r in rows if i < len(r) and r[i] is not None] or [8])
        ws.column_dimensions[get_column_letter(i + 1)].width = min(max(10, width + 3), 48)
        if i in money_columns:
            for cell in ws[get_column_letter(i + 1)][1:]:
                cell.number_format = '#,##0.00'
    ws.freeze_panes = "A2"
    wb.save(path)
    return path
