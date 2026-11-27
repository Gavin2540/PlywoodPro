"""Design tokens and the application stylesheet.

Everything visual comes from here: pages never hard-code colours. Read the
active palette with ``theme.c("accent")``; build fonts with ``theme.font()``.
"""
import sys

from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

DARK = {
    "bg": "#141210",          # window
    "surface": "#1C1917",     # cards, sidebar
    "surface2": "#24201D",    # inputs, table header, hover
    "surface3": "#2E2925",    # pressed, selected row
    "border": "#332E29",
    "border_strong": "#4A423B",
    "text": "#F3EEE8",
    "text2": "#B5ABA0",       # secondary
    "text3": "#7D746A",       # hints, disabled
    "accent": "#E59A2F",      # amber — primary actions
    "accent_hover": "#F0AC4A",
    "accent_press": "#C98322",
    "accent_soft": "#3A2B14",
    "on_accent": "#1A1206",
    "good": "#4CC38A", "good_soft": "#163023",
    "bad": "#F0655B", "bad_soft": "#3B1B19",
    "warn": "#F2B84B", "warn_soft": "#3A2E12",
    "info": "#62A8F5", "info_soft": "#152B44",
    "shadow": "#00000066",
    "chart": ["#E59A2F", "#62A8F5", "#4CC38A", "#C58AF9", "#F0655B", "#5AD1C8", "#F2B84B"],
}

LIGHT = {
    "bg": "#F6F3EF",
    "surface": "#FFFFFF",
    "surface2": "#F3EFEA",
    "surface3": "#E9E3DB",
    "border": "#E4DDD4",
    "border_strong": "#CFC5B8",
    "text": "#1F1A15",
    "text2": "#6A6057",
    "text3": "#9A9086",
    "accent": "#C77A12",
    "accent_hover": "#B56D0C",
    "accent_press": "#9C5D08",
    "accent_soft": "#FBEBD3",
    "on_accent": "#FFFFFF",
    "good": "#1F9D62", "good_soft": "#DDF3E7",
    "bad": "#D6453B", "bad_soft": "#FBE3E0",
    "warn": "#B7791F", "warn_soft": "#FBF0D6",
    "info": "#2F7FD8", "info_soft": "#E0EEFB",
    "shadow": "#3B2A1522",
    "chart": ["#C77A12", "#2F7FD8", "#1F9D62", "#8E55D9", "#D6453B", "#1FA79C", "#B7791F"],
}

_state = {"name": "dark", "palette": DARK}

RADIUS = 10
SPACE = 16  # base gutter; use multiples of 4


def name():
    return _state["name"]


def c(key):
    """Colour string for the active theme."""
    return _state["palette"][key]


def qc(key, alpha=None):
    col = QColor(c(key))
    if alpha is not None:
        col.setAlpha(alpha)
    return col


def chart_colors():
    return _state["palette"]["chart"]


def family():
    if sys.platform == "darwin":
        return ".AppleSystemUIFont"
    if sys.platform.startswith("win"):
        return "Segoe UI"
    return QFontDatabase.systemFont(QFontDatabase.GeneralFont).family()


def font(size=13, weight=QFont.Normal, tabular=False):
    """UI font. Sizes are in px so the layout is identical on Windows and macOS."""
    f = QFont(family())
    f.setPixelSize(size)
    f.setWeight(weight)
    if tabular:
        f.setFeature(QFont.Tag("tnum"), 1)
    return f


def apply(theme_name="dark"):
    """Switch palette and restyle the running application."""
    _state["name"] = "light" if theme_name == "light" else "dark"
    _state["palette"] = LIGHT if _state["name"] == "light" else DARK
    app = QApplication.instance()
    if app:
        app.setFont(font(13))
        app.setStyleSheet(stylesheet())


def _arrow_file(color):
    """Chevron for combo boxes: QSS needs an image file, so render one per colour."""
    import os
    import tempfile
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QPainter, QPen, QPixmap
    path = os.path.join(tempfile.gettempdir(), f"plywoodpro-arrow-{color.lstrip('#')}.png")
    if not os.path.exists(path):
        pm = QPixmap(24, 24)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(color), 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPolyline([QPointF(5, 9), QPointF(12, 16), QPointF(19, 9)])
        painter.end()
        pm.save(path)
    return path.replace("\\", "/")


def _check_file(color):
    """Tick mark for checked checkboxes."""
    import os
    import tempfile
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QPainter, QPen, QPixmap
    path = os.path.join(tempfile.gettempdir(), f"plywoodpro-check-{color.lstrip('#')}.png")
    if not os.path.exists(path):
        pm = QPixmap(32, 32)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(color), 4.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPolyline([QPointF(7, 17), QPointF(13, 23), QPointF(25, 9)])
        painter.end()
        pm.save(path)
    return path.replace("\\", "/")


def stylesheet():
    p = _state["palette"]
    return f"""
* {{ outline: none; }}
QWidget {{ color: {p['text']}; font-size: 13px; }}
QMainWindow, QDialog, #Root {{ background: {p['bg']}; }}
QToolTip {{ background: {p['surface3']}; color: {p['text']}; border: 1px solid {p['border_strong']};
           padding: 5px 8px; border-radius: 6px; }}

/* ── text roles ─────────────────────────────── */
QLabel {{ background: transparent; }}
QLabel[role="title"] {{ font-size: 22px; font-weight: 700; }}
QLabel[role="subtitle"] {{ color: {p['text2']}; font-size: 13px; }}
QLabel[role="heading"] {{ font-size: 15px; font-weight: 600; }}
QLabel[role="caption"] {{ color: {p['text3']}; font-size: 11px; font-weight: 600; letter-spacing: 0.6px; }}
QLabel[role="muted"] {{ color: {p['text2']}; }}
QLabel[role="hint"] {{ color: {p['text3']}; font-size: 12px; }}
QLabel[role="field"] {{ color: {p['text2']}; font-size: 12px; font-weight: 600; }}
QLabel[role="error"] {{ color: {p['bad']}; font-size: 12px; }}
QLabel[role="value"] {{ font-size: 24px; font-weight: 700; }}

/* ── surfaces ───────────────────────────────── */
QFrame#Card {{ background: {p['surface']}; border: 1px solid {p['border']}; border-radius: {RADIUS + 2}px; }}
QFrame#Sidebar {{ background: {p['surface']}; border: none; border-right: 1px solid {p['border']}; }}
QFrame#Divider {{ background: {p['border']}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#DialogPanel {{ background: {p['surface']}; border: 1px solid {p['border_strong']}; border-radius: 14px; }}
QFrame#Toast {{ background: {p['surface3']}; border: 1px solid {p['border_strong']}; border-radius: 10px; }}
QFrame#Banner {{ background: {p['accent_soft']}; border: 1px solid {p['accent']}; border-radius: {RADIUS}px; }}

/* ── buttons ────────────────────────────────── */
QPushButton {{ background: {p['surface2']}; border: 1px solid {p['border']}; border-radius: 8px;
              padding: 0 14px; min-height: 34px; font-weight: 600; }}
QPushButton:hover {{ background: {p['surface3']}; border-color: {p['border_strong']}; }}
QPushButton:pressed {{ background: {p['border']}; }}
QPushButton:disabled {{ color: {p['text3']}; background: {p['surface']}; border-color: {p['border']}; }}
QPushButton:focus {{ border-color: {p['accent']}; }}
QPushButton[variant="primary"] {{ background: {p['accent']}; color: {p['on_accent']}; border: none; }}
QPushButton[variant="primary"]:hover {{ background: {p['accent_hover']}; }}
QPushButton[variant="primary"]:pressed {{ background: {p['accent_press']}; }}
QPushButton[variant="primary"]:disabled {{ background: {p['surface3']}; color: {p['text3']}; }}
QPushButton[variant="danger"] {{ background: {p['bad']}; color: #FFFFFF; border: none; }}
QPushButton[variant="danger"]:hover {{ background: {p['bad']}; }}
QPushButton[variant="ghost"] {{ background: transparent; border: none; color: {p['text2']}; }}
QPushButton[variant="ghost"]:hover {{ background: {p['surface2']}; color: {p['text']}; }}
QPushButton[variant="link"] {{ background: transparent; border: none; color: {p['accent']}; padding: 0; min-height: 20px; }}
QPushButton[variant="link"]:hover {{ color: {p['accent_hover']}; }}
QPushButton[variant="nav"] {{ background: transparent; border: none; border-radius: 8px; text-align: left;
                             padding: 0 12px; min-height: 38px; color: {p['text2']}; font-weight: 500; }}
QPushButton[variant="nav"]:hover {{ background: {p['surface2']}; color: {p['text']}; }}
QPushButton[variant="nav"]:checked {{ background: {p['accent_soft']}; color: {p['accent']}; font-weight: 600; }}
QPushButton[variant="seg"] {{ background: transparent; border: none; border-radius: 6px; min-height: 28px;
                             padding: 0 12px; color: {p['text2']}; font-weight: 500; }}
QPushButton[variant="seg"]:hover {{ color: {p['text']}; }}
QPushButton[variant="seg"]:checked {{ background: {p['surface']}; color: {p['text']}; font-weight: 600;
                                     border: 1px solid {p['border']}; }}
QFrame#Segmented {{ background: {p['surface2']}; border: 1px solid {p['border']}; border-radius: 8px; }}
QToolButton {{ background: transparent; border: none; border-radius: 7px; padding: 6px; }}
QToolButton:hover {{ background: {p['surface2']}; }}
QToolButton:pressed {{ background: {p['surface3']}; }}

/* ── inputs ─────────────────────────────────── */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {p['surface2']}; border: 1px solid {p['border']}; border-radius: 8px;
    padding: 0 10px; min-height: 34px; selection-background-color: {p['accent']};
    selection-color: {p['on_accent']}; }}
QPlainTextEdit, QTextEdit {{ padding: 8px 10px; }}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {p['border_strong']}; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {p['accent']}; background: {p['surface']}; }}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{ color: {p['text3']}; }}
QLineEdit[invalid="true"], QComboBox[invalid="true"] {{ border: 1px solid {p['bad']}; }}
QLineEdit[flat="true"] {{ background: transparent; border: 1px solid transparent; }}
QLineEdit[flat="true"]:hover {{ border-color: {p['border']}; }}
QLineEdit[flat="true"]:focus {{ border-color: {p['accent']}; background: {p['surface2']}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url("{_arrow_file(p['text2'])}"); width: 12px; height: 12px;
    margin-right: 10px; }}
QComboBox QAbstractItemView, QListView#Popup {{ background: {p['surface']}; border: 1px solid {p['border_strong']};
    border-radius: 8px; padding: 4px; selection-background-color: {p['accent_soft']};
    selection-color: {p['text']}; }}
QComboBox QAbstractItemView::item, QListView#Popup::item {{ min-height: 30px; padding: 0 8px; border-radius: 6px; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {p['border_strong']};
                       background: {p['surface2']}; }}
QCheckBox::indicator:checked {{ background: {p['accent']}; border-color: {p['accent']};
                               image: url("{_check_file(p['on_accent'])}"); }}

/* ── calendar popup ─────────────────────────── */
QCalendarWidget QWidget {{ background: {p['surface']}; alternate-background-color: {p['surface']}; }}
QCalendarWidget QAbstractItemView {{ selection-background-color: {p['accent']}; selection-color: {p['on_accent']};
    border: none; }}
QCalendarWidget QToolButton {{ color: {p['text']}; font-weight: 600; padding: 4px 8px; }}
QCalendarWidget #qt_calendar_navigationbar {{ background: {p['surface2']}; min-height: 34px; }}

/* ── tables ─────────────────────────────────── */
QTableView {{ background: transparent; border: none; gridline-color: transparent;
             selection-background-color: {p['surface3']}; selection-color: {p['text']};
             alternate-background-color: transparent; }}
QTableView::item {{ border-bottom: 1px solid {p['border']}; padding: 0 12px; }}
QTableView::item:selected {{ background: {p['surface3']}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: {p['surface2']}; color: {p['text2']}; border: none;
    border-bottom: 1px solid {p['border']}; padding: 0 12px; min-height: 36px;
    font-size: 11px; font-weight: 700; }}
QHeaderView::section:first {{ border-top-left-radius: 8px; }}
QHeaderView::section:last {{ border-top-right-radius: 8px; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

/* ── scrollbars ─────────────────────────────── */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['border_strong']}; border-radius: 3px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {p['text3']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p['border_strong']}; border-radius: 3px; min-width: 32px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent; border: none; width: 0; height: 0; }}

/* ── menus, tabs, progress ──────────────────── */
QMenu {{ background: {p['surface']}; border: 1px solid {p['border_strong']}; border-radius: 8px; padding: 5px; }}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p['surface3']}; }}
QMenu::item:disabled {{ color: {p['text3']}; }}
QMenu::separator {{ height: 1px; background: {p['border']}; margin: 5px 6px; }}
QProgressBar {{ background: {p['surface2']}; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{ background: {p['accent']}; border-radius: 4px; }}
"""
