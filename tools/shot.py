"""Render app screens to PNG without showing a window (for visual checks).

    python tools/shot.py dashboard products          # pages by key
    python tools/shot.py --all --theme light
    python tools/shot.py sales --call open new=True   # call page.open(new=True) first; grabs the
                                                     # dialog it opens (if any) as <key>-dialog.png

Uses data/demo.db, or --db PATH (seeded with demo data if missing). Output: screenshots/<key>[-light].png
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main():
    args = sys.argv[1:]
    theme_name = "dark"
    if "--theme" in args:
        i = args.index("--theme")
        theme_name = args[i + 1]
        del args[i:i + 2]
    call = None
    if "--call" in args:
        i = args.index("--call")
        call = args[i + 1:]
        del args[i:]
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QDialog
    from database.db import DatabaseManager
    import seed_demo

    db = os.path.join(ROOT, "data", "demo.db")
    if "--db" in args:
        i = args.index("--db")
        db = args[i + 1]
        del args[i:i + 2]
    if not os.path.exists(db) or "--reseed" in args:
        seed_demo.seed(db)
    args = [a for a in args if a != "--reseed"]
    app = QApplication([])
    app.setStyle("Fusion")
    DatabaseManager.initialize(db)
    from ui import theme
    from ui.main_window import MainWindow
    from ui.pages import PAGES
    theme.apply(theme_name)
    window = MainWindow(check_updates=False)
    window.resize(1320, 820)
    window.show()
    keys = [e[0] for e in PAGES if e] if "--all" in args or not args else [a for a in args if not a.startswith("--")]
    out_dir = os.path.join(ROOT, "screenshots")
    os.makedirs(out_dir, exist_ok=True)
    suffix = "" if theme_name == "dark" else "-" + theme_name

    def settle(ms=900):
        from PySide6.QtCore import QEventLoop
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    for key in keys:
        window.navigate(key)
        settle()
        path = os.path.join(out_dir, f"{key}{suffix}.png")
        window.grab().save(path)
        print(path)
        if call:
            method, kwargs = call[0], {}
            for pair in call[1:]:
                k, v = pair.split("=", 1)
                kwargs[k] = True if v == "True" else False if v == "False" else int(v) if v.isdigit() else v

            def grab_dialog():
                for w in app.topLevelWidgets():
                    if isinstance(w, QDialog) and w.isVisible():
                        p = os.path.join(out_dir, f"{key}-dialog{suffix}.png")
                        w.grab().save(p)
                        print(p)
                        w.reject()
            QTimer.singleShot(1200, grab_dialog)
            getattr(window._pages[key], method)(**kwargs)
            settle(1600)
    DatabaseManager.close()


if __name__ == "__main__":
    main()
