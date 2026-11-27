"""Application shell: sidebar navigation, animated page switching, shortcuts."""
import datetime
import importlib
import traceback

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from database.db import DatabaseManager
from models import settings
from ui import icons, theme
from ui.pages import PAGES
from ui.widgets import EmptyState, button, fade_in, hbox, icon_button, label, toast, vbox
from utils.helpers import get_resource_path
from utils.updater import CURRENT_VERSION


class MainWindow(QMainWindow):
    def __init__(self, check_updates=True):
        super().__init__()
        self.setWindowTitle("Plywood Pro")
        self.setWindowIcon(QIcon(get_resource_path("icon.ico")))
        self.resize(1320, 820)
        self.setMinimumSize(1100, 680)
        self._pages, self._dirty, self._current = {}, set(), None
        self._build()
        self._shortcuts()
        self.navigate("dashboard")
        if check_updates:
            QTimer.singleShot(1500, self._check_updates)

    # ── layout ──────────────────────────────────────────────────────────
    def _build(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(232)
        s = QVBoxLayout(side)
        s.setContentsMargins(14, 20, 14, 14)
        s.setSpacing(3)

        logo = QLabel()
        logo.setPixmap(icons.pixmap("products", theme.c("accent"), 24))
        name = label("Plywood Pro")
        name.setStyleSheet("font-size:17px; font-weight:700;")
        shop = (settings.get("shop_name") or "").strip()
        self.shop_label = label(shop or "Inventory & Margins", "hint")
        s.addLayout(hbox(logo, vbox(name, self.shop_label, spacing=0), None, spacing=10, margins=(6, 0, 0, 0)))
        s.addSpacing(18)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self._nav = {}
        n = 0
        for entry in PAGES:
            if entry is None:
                s.addSpacing(10)
                continue
            key, text, icon, _mod, _cls = entry
            n += 1
            b = QPushButton("  " + text.replace("&", "&&"))
            b.setProperty("variant", "nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setIconSize(QSize(18, 18))
            b.setToolTip(f"{text}  (Ctrl+{n})" if n <= 9 else text)
            b.clicked.connect(lambda _=False, k=key: self.navigate(k))
            b.toggled.connect(lambda on, b=b, i=icon: b.setIcon(
                icons.icon(i, theme.c("accent" if on else "text2"), 18)))
            b.setIcon(icons.icon(icon, theme.c("text2"), 18))
            self.nav_group.addButton(b)
            s.addWidget(b)
            self._nav[key] = b
        s.addStretch(1)

        self.theme_button = icon_button("sun" if theme.name() == "dark" else "moon",
                                        "Switch between dark and light", self.toggle_theme)
        s.addLayout(hbox(label(f"v{CURRENT_VERSION}", "hint"), None, self.theme_button, margins=(8, 0, 0, 0)))
        row.addWidget(side)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.banner = QFrame()
        self.banner.setObjectName("Banner")
        self.banner_text = label("")
        self.banner_button = button("", "primary")
        self.banner.setLayout(hbox(self.banner_text, None, self.banner_button,
                                   icon_button("close", "Dismiss", self.banner.hide), margins=(14, 8, 8, 8)))
        self.banner.hide()
        wrap = QVBoxLayout()
        wrap.setContentsMargins(28, 14, 28, 0)
        wrap.addWidget(self.banner)
        self.banner_wrap = QWidget()
        self.banner_wrap.setLayout(wrap)
        self.banner_wrap.hide()
        right.addWidget(self.banner_wrap)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        row.addLayout(right, 1)

    def _shortcuts(self):
        keys = [e[0] for e in PAGES if e]
        for i, key in enumerate(keys[:9], start=1):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, activated=lambda k=key: self.navigate(k))
        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self.navigate("sales", new=True))
        QShortcut(QKeySequence("Ctrl+Shift+N"), self, activated=lambda: self.navigate("purchases", new=True))
        QShortcut(QKeySequence("Ctrl+E"), self, activated=lambda: self.navigate("expenses", new=True))
        QShortcut(QKeySequence("F5"), self, activated=self.data_changed)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)

    def _focus_search(self):
        page = self._pages.get(self._current)
        box = getattr(page, "search", None)
        if box is not None:
            box.setFocus()
            box.selectAll()

    # ── navigation ──────────────────────────────────────────────────────
    def _make_page(self, key):
        entry = next(e for e in PAGES if e and e[0] == key)
        try:
            page = getattr(importlib.import_module(entry[3]), entry[4])(self)
        except Exception:  # a broken page must never take the whole app down
            traceback.print_exc()
            page = EmptyState("alert", f"{entry[1]} could not be opened",
                              traceback.format_exc().strip().splitlines()[-1])
        self._pages[key] = page
        self.stack.addWidget(page)
        self._dirty.add(key)
        return page

    def navigate(self, key, **kwargs):
        """Show a page. Extra keyword arguments go to the page's ``open()``."""
        page = self._pages.get(key) or self._make_page(key)
        self._nav[key].setChecked(True)
        changed = key != self._current
        self._current = key
        self.stack.setCurrentWidget(page)
        self._refresh(key)
        if changed:
            fade_in(page)
        if kwargs and hasattr(page, "open"):
            QTimer.singleShot(0, lambda: page.open(**kwargs))

    def _refresh(self, key):
        if key in self._dirty:
            self._dirty.discard(key)
            page = self._pages[key]
            if hasattr(page, "refresh"):
                try:
                    page.refresh()
                except Exception as e:
                    traceback.print_exc()
                    toast(self, f"Could not load this page: {e}", "bad")

    def data_changed(self):
        """Call after any write: every page reloads the next time it is shown."""
        self._dirty = set(self._pages)
        if self._current:
            self._refresh(self._current)
        shop = (settings.get("shop_name") or "").strip()
        self.shop_label.setText(shop or "Inventory & Margins")

    def current_key(self):
        return self._current

    # ── theme ───────────────────────────────────────────────────────────
    def toggle_theme(self):
        new = "light" if theme.name() == "dark" else "dark"
        settings.set("theme", new)
        theme.apply(new)
        icons._cache.clear()
        current = self._current or "dashboard"
        old = self.centralWidget()
        self._pages, self._dirty, self._current = {}, set(), None
        self._build()
        old.deleteLater()
        self.navigate(current)

    # ── banner / updates ────────────────────────────────────────────────
    def show_banner(self, text, action_text=None, on_action=None):
        self.banner_text.setText(text)
        self.banner_button.setVisible(bool(action_text))
        if action_text:
            self.banner_button.setText(action_text)
            try:
                self.banner_button.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.banner_button.clicked.connect(lambda *_: on_action())
        self.banner.show()
        self.banner_wrap.show()

    def _check_updates(self):
        from ui.update_flow import check_in_background
        check_in_background(self)

    # ── shutdown ────────────────────────────────────────────────────────
    def closeEvent(self, event):
        try:
            if settings.get("auto_backup") == "1" and DatabaseManager.db_path() != ":memory:":
                from utils import backup
                backup.auto_backup(int(settings.get("backup_keep") or 14))
        except Exception:
            traceback.print_exc()
        DatabaseManager.close()
        super().closeEvent(event)


def greeting():
    hour = datetime.datetime.now().hour
    return "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
