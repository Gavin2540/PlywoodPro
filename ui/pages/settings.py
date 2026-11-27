"""Settings: shop details, appearance, backup, updates and shortcuts."""
import datetime
import os
import sys

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QGridLayout, QLabel, QLineEdit, QPlainTextEdit, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from database.db import DatabaseManager
from models import settings
from ui import theme
from ui.table import Action, Col, DataTable
from ui.widgets import Card, Page, Segmented, button, confirm, divider, field, hbox, label
from utils import backup
from utils.updater import CURRENT_VERSION

MAX_WIDTH = 760
KEEP_OPTIONS = [("7", "7"), ("14", "14"), ("30", "30")]
SHOP_KEYS = ("shop_name", "shop_phone", "shop_address", "shop_gstin", "invoice_footer")
_MOD = "Cmd" if sys.platform == "darwin" else "Ctrl"
SHORTCUTS = [(f"{_MOD}+N", "New sale"), (f"{_MOD}+Shift+N", "New purchase"), (f"{_MOD}+E", "Add expense"),
             (f"{_MOD}+F", "Search this page"), (f"{_MOD}+1 … 9", "Switch page"), ("F5", "Refresh"),
             ("Enter", "Save in a dialog"), ("Esc", "Cancel")]


def _kind(path):
    name = os.path.basename(path)
    if name.startswith("auto-"):
        return "Automatic"
    if name.startswith("before-restore"):
        return "Before restore"
    if name.startswith("before-upgrade"):
        return "Before upgrade"
    return "Manual"


def _size(n):
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


def _open_folder(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


class _ElidedLabel(QLabel):
    """Hint label that shortens its text in the middle to fit."""

    def __init__(self):
        super().__init__()
        self.setProperty("role", "hint")
        self.setMinimumWidth(60)
        self.setMaximumWidth(10000)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._full = ""

    def set_full(self, text):
        self._full = text
        self.setToolTip(text)
        self._fit()

    def _fit(self):
        self.setText(self.fontMetrics().elidedText(self._full, Qt.ElideMiddle, max(self.width() - 4, 60)))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()


class SettingsPage(Page):
    title = "Settings"
    subtitle = "Shop details, appearance, backups and updates"

    def __init__(self, app):
        super().__init__(app)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(0, 0, 8, 8)
        content = QWidget()
        content.setMaximumWidth(MAX_WIDTH)
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(16)
        outer.addLayout(hbox(content, None, spacing=0), 0)
        outer.addStretch(1)
        scroll.setWidget(inner)
        self.root.addWidget(scroll, 1)
        self._saved = {}
        col.addWidget(self._build_shop())
        col.addWidget(self._build_appearance())
        col.addWidget(self._build_backup())
        col.addWidget(self._build_updates())
        col.addWidget(self._build_shortcuts())
        col.addStretch(1)

    # ── shop details ────────────────────────────────────────────────────
    def _build_shop(self):
        card = Card("Shop details")
        card.add(label("Shown on invoices and reports.", "hint"))
        self.shop_name = QLineEdit()
        self.shop_name.setPlaceholderText("e.g. Sharma Plywood House")
        self.shop_phone = QLineEdit()
        self.shop_phone.setPlaceholderText("e.g. 98765 43210")
        self.shop_gstin = QLineEdit()
        self.shop_gstin.setPlaceholderText("Optional")
        self.shop_address = QPlainTextEdit()
        self.shop_address.setFixedHeight(68)
        self.shop_address.setPlaceholderText("Street, area, city, PIN")
        self.invoice_footer = QLineEdit()
        self.invoice_footer.setPlaceholderText("Printed at the bottom of every invoice")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.addWidget(field("Shop name", self.shop_name), 0, 0)
        grid.addWidget(field("Phone", self.shop_phone), 0, 1)
        grid.addWidget(field("Address", self.shop_address), 1, 0, 1, 2)
        grid.addWidget(field("GSTIN", self.shop_gstin), 2, 0)
        grid.addWidget(field("Invoice footer text", self.invoice_footer), 2, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        card.add(grid)
        self.save_button = button("Save", "primary", "check", self.save_shop)
        self.save_button.setEnabled(False)
        card.add(hbox(None, self.save_button))
        for w in (self.shop_name, self.shop_phone, self.shop_gstin, self.invoice_footer):
            w.textChanged.connect(self._dirty_check)
        self.shop_address.textChanged.connect(self._dirty_check)
        return card

    def _shop_values(self):
        return {"shop_name": self.shop_name.text().strip(), "shop_phone": self.shop_phone.text().strip(),
                "shop_address": self.shop_address.toPlainText().strip(),
                "shop_gstin": self.shop_gstin.text().strip().upper(),
                "invoice_footer": self.invoice_footer.text().strip()}

    def _load_shop(self):
        data = settings.get_all()
        self._saved = {k: (data.get(k) or "") for k in SHOP_KEYS}
        for w in (self.shop_name, self.shop_phone, self.shop_gstin, self.invoice_footer, self.shop_address):
            w.blockSignals(True)
        self.shop_name.setText(self._saved["shop_name"])
        self.shop_phone.setText(self._saved["shop_phone"])
        self.shop_gstin.setText(self._saved["shop_gstin"])
        self.invoice_footer.setText(self._saved["invoice_footer"])
        self.shop_address.setPlainText(self._saved["shop_address"])
        for w in (self.shop_name, self.shop_phone, self.shop_gstin, self.invoice_footer, self.shop_address):
            w.blockSignals(False)
        self._dirty_check()

    def _dirty_check(self, *_):
        self.save_button.setEnabled(self._shop_values() != self._saved)

    def save_shop(self):
        values = self._shop_values()
        settings.set_many(values)
        self._saved = dict(values)
        self.app.data_changed()
        self._dirty_check()
        self.toast("Shop details saved")

    # ── appearance ──────────────────────────────────────────────────────
    def _build_appearance(self):
        card = Card("Appearance")
        self.theme_seg = Segmented([("dark", "Dark"), ("light", "Light")], theme.name())
        self.theme_seg.changed.connect(self.set_theme)
        card.add(hbox(label("Choose how Plywood Pro looks on this computer.", "muted"), None, self.theme_seg))
        return card

    def set_theme(self, key):
        if key != theme.name():
            self.app.toggle_theme()  # rebuilds every page, including this one

    # ── backup ──────────────────────────────────────────────────────────
    def _build_backup(self):
        card = Card("Backup")
        card.add(label("A backup is one file holding all your products, bills and settings. Save one to a pen "
                       "drive or cloud folder now and then, so your books are safe if this computer fails.",
                       "muted", wrap=True))
        self.backup_button = button("Back up now", "primary", "download", self.backup_now)
        self.restore_button = button("Restore from backup…", None, "upload", self.restore)
        card.add(hbox(self.backup_button, self.restore_button, None))

        self.auto_check = QCheckBox("Back up automatically when I close the app")
        self.auto_check.toggled.connect(self.set_auto_backup)
        self.keep_seg = Segmented(KEEP_OPTIONS, "14")
        self.keep_seg.changed.connect(self.set_keep)
        card.add(hbox(self.auto_check, None, label("Keep last", "muted"), self.keep_seg,
                      label("backups", "muted"), spacing=8))
        card.add(divider())
        card.add(label("Saved backups", "field"))
        self.backups = DataTable(
            [Col("name", "File", stretch=True, bold=True),
             Col("kind", "Kind", width=120),
             Col("when", "Date and time", width=150, sort=lambda r: r["mtime"]),
             Col("size", "Size", width=80, align="right", sort=lambda r: r["bytes"])],
            actions=[Action("upload", "Restore", self._restore_row, visible=lambda r: r["name"].endswith(".plypro")),
                     Action("file", "Show in folder", lambda r: _open_folder(os.path.dirname(r["path"])))],
            empty=("download", "No backups yet", "Press Back up now, or turn on automatic backup."))
        card.add(self.backups)
        self.no_backups = label("No backups yet.", "muted")
        card.add(self.no_backups)
        self.data_path = _ElidedLabel()
        card.add(hbox(self.data_path, button("Open folder", "link", None, self.open_data_folder), spacing=8))
        return card

    def _load_backup(self):
        self.auto_check.blockSignals(True)
        self.auto_check.setChecked(settings.get("auto_backup") == "1")
        self.auto_check.blockSignals(False)
        keep = settings.get("backup_keep") or "14"
        self.keep_seg.set(keep if keep in dict(KEEP_OPTIONS) else None)
        rows = []
        try:
            files = backup.list_backups()
        except OSError:
            files = []
        for p in files:
            if not os.path.isfile(p):
                continue
            st = os.stat(p)
            rows.append({"path": p, "name": os.path.basename(p), "kind": _kind(p), "mtime": st.st_mtime,
                         "when": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d-%m-%Y  %H:%M"),
                         "bytes": st.st_size, "size": _size(st.st_size)})
        self.backups.set_rows(rows)
        self.backups.setVisible(bool(rows))
        self.no_backups.setVisible(not rows)
        self.backups.fit_height(5)
        db = DatabaseManager.db_path()
        self.data_path.set_full("Your data file: " + ("in memory" if db == ":memory:" else db))

    def set_auto_backup(self, on):
        settings.set("auto_backup", "1" if on else "0")

    def set_keep(self, key):
        settings.set("backup_keep", key)

    def open_data_folder(self):
        db = DatabaseManager.db_path()
        if db != ":memory:":
            _open_folder(os.path.dirname(db))

    def backup_now(self, path=None):
        if path is None:
            default = f"PlywoodPro_Backup_{datetime.date.today():%Y%m%d}.plypro"
            path, _ = QFileDialog.getSaveFileName(self, "Save backup", default, "Plywood Pro backup (*.plypro)")
            if not path:
                return None
            if not path.lower().endswith(".plypro"):
                path += ".plypro"
        try:
            backup.export_database(path)
        except OSError as e:
            self.toast(f"Could not save the backup: {e}", "bad")
            return None
        self._load_backup()
        self.toast("Backup saved: " + os.path.basename(path))
        return path

    _RESTORE_WARNING = ("Restoring replaces ALL the data currently in Plywood Pro (products, bills, expenses, "
                        "settings) with the contents of this backup. A safety copy of your current data is kept "
                        "in the backups list, so you can go back if needed.")

    def restore(self, path=None):
        """With no path: ask for a file and confirm. With a path: restore it directly."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Choose a backup", "", "Plywood Pro backup (*.plypro)")
            if not path:
                return False
            if not confirm(self, "Restore this backup?",
                           f"{os.path.basename(path)}\n\n{self._RESTORE_WARNING}", "Restore", danger=True):
                return False
        return self._do_restore(path)

    def _restore_row(self, row):
        if confirm(self, "Restore this backup?", f"{row['name']}\n\n{self._RESTORE_WARNING}",
                   "Restore", danger=True):
            self._do_restore(row["path"])

    def _do_restore(self, path):
        try:
            backup.import_database(path)
        except (ValueError, OSError) as e:
            self.toast(str(e), "bad")
            return False
        self.app.data_changed()
        self._load_shop()
        self._load_backup()
        self.toast("Backup restored: " + os.path.basename(path))
        return True

    # ── updates ─────────────────────────────────────────────────────────
    def _build_updates(self):
        card = Card("Updates")
        self.check_button = button("Check for updates", None, "refresh", self.check_updates)
        card.add(hbox(label(f"You are using version {CURRENT_VERSION}", "muted"), None, self.check_button))
        return card

    def check_updates(self):
        from ui.update_flow import check_in_background
        check_in_background(self.app, on_none=lambda: self.toast("You have the latest version", "info"))

    # ── shortcuts ───────────────────────────────────────────────────────
    def _build_shortcuts(self):
        card = Card("Keyboard shortcuts")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        half = (len(SHORTCUTS) + 1) // 2
        for i, (keys, text) in enumerate(SHORTCUTS):
            r, c = i % half, (i // half) * 2
            k = label(keys)
            k.setStyleSheet(f"background:{theme.c('surface2')}; border:1px solid {theme.c('border')}; "
                            "border-radius:6px; padding:3px 8px; font-size:12px; font-weight:600;")
            k.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            grid.addWidget(k, r, c, Qt.AlignLeft)
            grid.addWidget(label(text, "muted"), r, c + 1)
        grid.setColumnMinimumWidth(0, 110)
        grid.setColumnMinimumWidth(2, 110)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        card.add(grid)
        return card

    # ── page lifecycle ──────────────────────────────────────────────────
    def refresh(self):
        if not self.save_button.isEnabled():  # keep unsaved edits
            self._load_shop()
        self._load_backup()
