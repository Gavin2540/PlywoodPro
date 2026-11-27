"""Plywood Pro entry point.

    python main.py                 normal start (data/plywoodpro.db)
    python main.py --demo          open a throwaway copy filled with sample data
    python main.py --db PATH       open a specific data file
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
import seed_demo  # noqa: E402,F401  (bundled so --demo and --selftest work in the packaged app)


def _log_path():
    from database.db import app_dir
    return os.path.join(app_dir(), "data", "error.log")


def _excepthook(exc_type, exc, tb):
    """Uncaught errors in button handlers: log them and tell the user, never die silently."""
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    sys.stderr.write(text)
    try:
        import datetime
        os.makedirs(os.path.dirname(_log_path()), exist_ok=True)
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.datetime.now().isoformat(timespec='seconds')} ---\n{text}")
    except OSError:
        pass
    try:
        from PySide6.QtWidgets import QApplication
        from ui.widgets import toast
        window = QApplication.activeWindow()
        if window:
            toast(window, f"Something went wrong: {exc}", "bad")
    except Exception:
        pass


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        from utils import selftest
        code = selftest.run()
        os._exit(code)  # skip Qt/interpreter teardown, which can crash after an offscreen run
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Plywood Pro")
    app.setStyle("Fusion")
    sys.excepthook = _excepthook
    try:
        from database.db import DatabaseManager, app_dir
        db_path = None
        if "--db" in argv:
            db_path = argv[argv.index("--db") + 1]
        elif "--demo" in argv:
            db_path = seed_demo.seed(os.path.join(app_dir(), "data", "demo.db"))
        DatabaseManager.initialize(db_path)

        from models import settings
        from ui import theme
        from ui.main_window import MainWindow
        theme.apply(settings.get("theme"))
        window = MainWindow(check_updates="--demo" not in argv and "--no-update-check" not in argv)
        window.show()
    except Exception as e:
        traceback.print_exc()
        QMessageBox.critical(None, "Plywood Pro could not start",
                             f"{e}\n\nYour data has not been changed. If this keeps happening, "
                             "send the file data/error.log to support.")
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
