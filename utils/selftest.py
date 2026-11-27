"""Packaged-build self-test: `"Plywood Pro" --selftest`.

Runs against a throwaway demo database in a temp folder: opens every screen,
saves a sale, and writes an invoice, a PDF report, an Excel report and a
backup. Writes selftest.log next to the temp data and exits 0 on success, 1 on
failure. Used by the build pipeline to prove the .exe really works.
"""
import datetime
import os
import sys
import tempfile
import traceback


def run():
    folder = tempfile.mkdtemp(prefix="plywoodpro-selftest-")
    log_path = os.path.join(folder, "selftest.log")
    lines = []

    def log(text):
        lines.append(text)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        try:
            print(text, flush=True)
        except Exception:
            pass

    ok = True
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv[:1])
        app.setStyle("Fusion")
        import seed_demo
        from database.db import DatabaseManager
        db = seed_demo.seed(os.path.join(folder, "data", "demo.db"))
        DatabaseManager.initialize(db)
        from models import bills, product, reports, stock
        from ui import theme
        from ui.main_window import MainWindow
        from ui.pages import PAGES
        from ui.widgets import EmptyState
        from utils import backup, export, invoice

        for theme_name in ("dark", "light"):
            theme.apply(theme_name)
            window = MainWindow(check_updates=False)
            window.show()
            for entry in PAGES:
                if not entry:
                    continue
                window.navigate(entry[0])
                app.processEvents()
                page = window._pages[entry[0]]
                if isinstance(page, EmptyState):
                    ok = False
                    log(f"FAIL page {entry[0]} ({theme_name}): {page.hint.text()}")
                else:
                    log(f"ok   page {entry[0]} ({theme_name})")
            window.close()
            DatabaseManager.initialize(db)

        p = next(x for x in product.list_products() if x["stock"] >= 2)
        before = stock.current_stock(p["id"])
        bill_id = bills.save_bill("sale", datetime.date.today(), [
            {"product_id": p["id"], "qty": 1, "unit_price": p["selling_price"]}], party_name="Self Test & Co", paid=0)
        assert stock.current_stock(p["id"]) == before - 1
        log("ok   sale saved, stock reduced")
        today = datetime.date.today()
        outputs = {
            "invoice.pdf": lambda path: invoice.invoice_pdf(bill_id, path),
            "report.pdf": lambda path: export.export_report_pdf(today - datetime.timedelta(days=30), today, path),
            "day.pdf": lambda path: export.export_report_pdf(today, today, path),
            "report.xlsx": lambda path: export.export_report_excel(today - datetime.timedelta(days=30), today, path),
            "backup.plypro": backup.export_database,
        }
        for name, make in outputs.items():
            path = os.path.join(folder, name)
            make(path)
            size = os.path.getsize(path)
            if size < 1000:
                ok = False
                log(f"FAIL {name}: only {size} bytes")
            else:
                log(f"ok   {name} ({size:,} bytes)")
        assert reports.summary(today, today)["sale_bills"] >= 1
        DatabaseManager.close()
    except Exception:
        ok = False
        log("FAIL " + traceback.format_exc())
    log("SELFTEST PASSED" if ok else "SELFTEST FAILED")
    log(f"log: {log_path}")
    return 0 if ok else 1
