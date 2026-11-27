"""Reusable building blocks. Pages compose these instead of styling raw Qt widgets."""
import datetime

from PySide6.QtCore import (QDate, QEasingCurve, QEvent, QPoint, QPropertyAnimation, QSize, QStringListModel, Qt,
                            QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import QDoubleValidator, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QCompleter, QDateEdit, QDialog, QFrame,
                               QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from ui import icons, theme
from utils.helpers import format_currency, parse_number


# ── basics ──────────────────────────────────────────────────────────────
def label(text="", role=None, wrap=False):
    lb = QLabel(text)
    if role:
        lb.setProperty("role", role)
    lb.setWordWrap(wrap)
    return lb


def restyle(widget):
    """Re-apply the stylesheet after changing a dynamic property."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def button(text, variant=None, icon=None, on_click=None, tooltip=None):
    """variant: None (secondary) | 'primary' | 'danger' | 'ghost' | 'link'."""
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    if variant:
        b.setProperty("variant", variant)
    if icon:
        color = theme.c("on_accent") if variant == "primary" else "#FFFFFF" if variant == "danger" else theme.c("text2")
        b.setIcon(icons.icon(icon, color, 16))
        b.setIconSize(QSize(16, 16))
    if on_click:
        b.clicked.connect(lambda *_: on_click())
    if tooltip:
        b.setToolTip(tooltip)
    return b


def icon_button(name, tooltip=None, on_click=None, size=18, color=None):
    b = QToolButton()
    b.setIcon(icons.icon(name, color, size))
    b.setIconSize(QSize(size, size))
    b.setCursor(Qt.PointingHandCursor)
    if tooltip:
        b.setToolTip(tooltip)
    if on_click:
        b.clicked.connect(lambda *_: on_click())
    return b


def divider():
    d = QFrame()
    d.setObjectName("Divider")
    return d


def hbox(*items, spacing=8, margins=(0, 0, 0, 0)):
    """Row layout. Items: widgets, layouts, ints (fixed space) or None (stretch)."""
    return _box(QHBoxLayout(), items, spacing, margins)


def vbox(*items, spacing=8, margins=(0, 0, 0, 0)):
    return _box(QVBoxLayout(), items, spacing, margins)


def _box(layout, items, spacing, margins):
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    for it in items:
        if it is None:
            layout.addStretch(1)
        elif isinstance(it, int):
            layout.addSpacing(it)
        elif isinstance(it, QWidget):
            layout.addWidget(it)
        else:
            layout.addLayout(it)
    return layout


def field(caption, widget, hint=None):
    """Caption above an input, optional hint below. Returns a QWidget."""
    w = QWidget()
    lay = vbox(label(caption, "field"), widget, spacing=6)
    if hint:
        lay.addWidget(label(hint, "hint", wrap=True))
    w.setLayout(lay)
    return w


class Card(QFrame):
    """Rounded surface. ``card.body`` is its QVBoxLayout."""

    def __init__(self, title=None, padding=18, spacing=12):
        super().__init__()
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)
        self.header = None
        if title:
            self.title_label = label(title, "heading")
            self.header = hbox(self.title_label, None)
            self.body.addLayout(self.header)

    def add(self, item, stretch=0):
        if isinstance(item, QWidget):
            self.body.addWidget(item, stretch)
        else:
            self.body.addLayout(item, stretch)
        return item

    def add_header_widget(self, widget):
        self.header.addWidget(widget)


class Badge(QLabel):
    """Small status pill. kind: good | bad | warn | info | neutral | accent."""

    def __init__(self, text="", kind="neutral"):
        super().__init__(text)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.set(text, kind)

    def set(self, text, kind="neutral"):
        self.setText(text)
        fg, bg = badge_colors(kind)
        self.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:9px; padding:2px 9px; font-size:11px; font-weight:700;")


def badge_colors(kind):
    if kind in ("good", "bad", "warn", "info"):
        return theme.c(kind), theme.c(kind + "_soft")
    if kind == "accent":
        return theme.c("accent"), theme.c("accent_soft")
    return theme.c("text2"), theme.c("surface3")


class StatCard(Card):
    """Headline number with a caption, optional icon and change-vs-before chip.

    ``set_value`` animates from the old number to the new one.
    """

    def __init__(self, caption, icon=None, kind="currency", tone=None):
        super().__init__(padding=16, spacing=6)
        self.kind, self.tone, self._value = kind, tone, 0.0
        self.caption = label(caption.upper(), "caption")
        top = hbox(self.caption, None)
        if icon:
            ic = QLabel()
            ic.setPixmap(icons.pixmap(icon, theme.c("text3"), 18))
            top.addWidget(ic)
        self.body.addLayout(top)
        self.value = label("—", "value")
        self.value.setFont(theme.font(24, QFont.Bold, tabular=True))
        self.body.addWidget(self.value)
        self.sub = label("", "hint")
        self.chip = Badge("", "neutral")
        self.chip.hide()
        self.body.addLayout(hbox(self.chip, self.sub, None, spacing=6))
        self.setMinimumHeight(112)
        self._anim = QVariantAnimation(self, duration=450, easingCurve=QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._render)

    def _render(self, v):
        v = float(v)
        if self.kind == "currency":
            text = format_currency(v, decimals=0)
        elif self.kind == "int":
            text = f"{round(v):,}"
        else:
            text = f"{v:,.1f}".rstrip("0").rstrip(".")
        self.value.setText(text)
        tone = self.tone
        if tone == "sign":
            tone = "good" if v >= 0 else "bad"
        self.value.setStyleSheet(f"color:{theme.c(tone)};" if tone else "")

    def set_value(self, value, sub=None, previous=None, good_when_up=True):
        value = float(value or 0)
        self._anim.stop()
        self._anim.setStartValue(float(self._value))
        self._anim.setEndValue(value)
        self._value = value
        self._anim.start()
        if sub is not None:
            self.sub.setText(sub)
        if previous is None:
            self.chip.hide()
        else:
            previous = float(previous or 0)
            if previous == 0 and value == 0:
                self.chip.hide()
            else:
                if previous == 0:
                    text, up = "new", value > 0
                else:
                    pct = (value - previous) / abs(previous) * 100
                    text, up = f"{'+' if pct >= 0 else ''}{pct:.0f}%", pct >= 0
                if text in ("+0%", "-0%"):
                    self.chip.set("0%", "neutral")
                    self.chip.show()
                    return
                self.chip.set(text, "good" if up == good_when_up else "bad")
                self.chip.show()


class Segmented(QFrame):
    """Pill switcher. options: [(key, label)]. Emits ``changed(key)``."""
    changed = Signal(str)

    def __init__(self, options, current=None):
        super().__init__()
        self.setObjectName("Segmented")
        lay = hbox(spacing=2, margins=(3, 3, 3, 3))
        self.setLayout(lay)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._buttons = {}
        for key, text in options:
            b = QPushButton(text)
            b.setProperty("variant", "seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
            self.group.addButton(b)
            lay.addWidget(b)
            self._buttons[key] = b
        self.set(current or options[0][0])
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def set(self, key):
        if key in self._buttons:
            self._buttons[key].setChecked(True)
        else:  # nothing selected (e.g. custom date range)
            self.group.setExclusive(False)
            for b in self._buttons.values():
                b.setChecked(False)
            self.group.setExclusive(True)

    def set_label(self, key, text):
        self._buttons[key].setText(text)

    def current(self):
        for k, b in self._buttons.items():
            if b.isChecked():
                return k
        return None


class SearchBox(QLineEdit):
    """Search input; emits ``searched(text)`` shortly after typing stops."""
    searched = Signal(str)

    def __init__(self, placeholder="Search…", width=260):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.addAction(icons.icon("search", theme.c("text3"), 16), QLineEdit.LeadingPosition)
        if width:
            self.setFixedWidth(width)
        self._timer = QTimer(self, singleShot=True, interval=140)
        self._timer.timeout.connect(lambda: self.searched.emit(self.text().strip()))
        self.textChanged.connect(lambda _: self._timer.start())


class NumberEdit(QLineEdit):
    """Right-aligned numeric input. ``value()`` returns a float (0 when blank)."""

    def __init__(self, value=None, decimals=2, placeholder="0", minimum=0.0, width=None):
        super().__init__()
        self.decimals = decimals
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setPlaceholderText(placeholder)
        v = QDoubleValidator(minimum, 1e12, decimals, self)
        v.setNotation(QDoubleValidator.StandardNotation)
        self.setValidator(v)
        self.setFont(theme.font(13, tabular=True))
        if width:
            self.setFixedWidth(width)
        if value is not None:
            self.set_value(value)

    def value(self):
        try:
            return parse_number(self.text() or "0")
        except ValueError:
            return 0.0

    def is_blank(self):
        return not self.text().strip()

    def set_value(self, value):
        if value is None:
            self.clear()
            return
        text = f"{float(value):.{self.decimals}f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        self.setText(text)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        QTimer.singleShot(0, self.selectAll)


class DateField(QDateEdit):
    """Calendar date picker shown as DD-MM-YYYY. Works in ISO strings."""

    def __init__(self, iso_date=None, allow_future=False, width=132):
        super().__init__()
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd-MM-yyyy")
        self.setFixedWidth(width)
        if not allow_future:
            self.setMaximumDate(QDate.currentDate())
        self.set_iso(iso_date or datetime.date.today().isoformat())

    def iso(self):
        return self.date().toString("yyyy-MM-dd")

    def set_iso(self, iso_date):
        self.setDate(QDate.fromString(str(iso_date)[:10], "yyyy-MM-dd"))


class DateRangeBar(QWidget):
    """Preset range buttons plus from/to pickers. Emits ``changed(from_iso, to_iso)``."""
    changed = Signal(str, str)
    PRESETS = [("today", "Today"), ("7d", "7 days"), ("30d", "30 days"), ("month", "This month"),
               ("year", "This year")]

    def __init__(self, default="30d", presets=None):
        super().__init__()
        self.seg = Segmented(presets or self.PRESETS, default)
        self.start, self.end = DateField(), DateField()
        self.setLayout(hbox(self.seg, 6, self.start, label("to", "muted"), self.end, spacing=8))
        self.seg.changed.connect(self._preset)
        self.start.dateChanged.connect(self._manual)
        self.end.dateChanged.connect(self._manual)
        self._quiet = False
        self._preset(default, emit=False)

    @staticmethod
    def preset_range(key):
        today = datetime.date.today()
        if key == "today":
            return today, today
        if key == "yesterday":
            y = today - datetime.timedelta(days=1)
            return y, y
        if key == "7d":
            return today - datetime.timedelta(days=6), today
        if key == "30d":
            return today - datetime.timedelta(days=29), today
        if key == "month":
            return today.replace(day=1), today
        if key == "year":  # Indian financial year, April to March
            start_year = today.year if today.month >= 4 else today.year - 1
            return datetime.date(start_year, 4, 1), today
        return today, today

    def _preset(self, key, emit=True):
        a, b = self.preset_range(key)
        self._quiet = True
        self.start.set_iso(a.isoformat())
        self.end.set_iso(b.isoformat())
        self._quiet = False
        if emit:
            self.changed.emit(*self.range())

    def _manual(self, *_):
        if self._quiet:
            return
        if self.start.date() > self.end.date():
            self._quiet = True
            (self.end if self.sender() is self.start else self.start).setDate(self.sender().date())
            self._quiet = False
        self.seg.set(None)
        self.changed.emit(*self.range())

    def range(self):
        return self.start.iso(), self.end.iso()

    def set_range(self, start_iso, end_iso):
        self._quiet = True
        self.start.set_iso(start_iso)
        self.end.set_iso(end_iso)
        self._quiet = False
        self.seg.set(None)
        self.changed.emit(*self.range())


class SearchCombo(QComboBox):
    """Type-to-filter dropdown. Items carry data; ``current_data()`` is None
    unless the text matches an item exactly (so free typing is never mistaken
    for a selection)."""
    picked = Signal(object)

    def __init__(self, placeholder="Search…", free_text=False):
        super().__init__()
        self.free_text = free_text
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.lineEdit().setPlaceholderText(placeholder)
        self.setMaxVisibleItems(12)
        self._completer = QCompleter(self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.popup().setObjectName("Popup")
        self.setCompleter(self._completer)
        self.activated.connect(lambda i: self.picked.emit(self.itemData(i)))
        self._completer.activated[str].connect(self._completed)

    def set_items(self, items):
        """items: [(text, data)]. Keeps the current selection when it still exists."""
        keep = self.current_data()
        text = self.currentText()
        self.blockSignals(True)
        self.clear()
        for t, d in items:
            self.addItem(t, d)
        self._completer.setModel(QStringListModel([t for t, _ in items], self))
        self.setCurrentIndex(-1)
        self.blockSignals(False)
        if keep is not None and self.set_current_data(keep):
            return
        self.setEditText(text if self.free_text else "")

    def _completed(self, text):
        i = self.findText(text, Qt.MatchFixedString)
        if i >= 0:
            self.setCurrentIndex(i)
            self.picked.emit(self.itemData(i))

    def current_data(self):
        i = self.findText(self.currentText().strip(), Qt.MatchFixedString)
        return self.itemData(i) if i >= 0 else None

    def set_current_data(self, data):
        for i in range(self.count()):
            if self.itemData(i) == data:
                self.setCurrentIndex(i)
                return True
        return False

    def text(self):
        return self.currentText().strip()


class EmptyState(QWidget):
    def __init__(self, icon="box", title="Nothing here yet", hint="", action_text=None, on_action=None):
        super().__init__()
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icons.pixmap(icon, theme.c("text3"), 40))
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.title = label(title, "heading")
        self.title.setAlignment(Qt.AlignCenter)
        self.hint = label(hint, "muted", wrap=True)
        self.hint.setAlignment(Qt.AlignCenter)
        lay = vbox(None, self.icon_label, self.title, self.hint, spacing=8, margins=(24, 24, 24, 24))
        if action_text:
            lay.addSpacing(6)
            lay.addLayout(hbox(None, button(action_text, "primary", "plus", on_action), None))
        lay.addStretch(1)
        self.setLayout(lay)

    def set_text(self, title, hint=""):
        self.title.setText(title)
        self.hint.setText(hint)


# ── motion ──────────────────────────────────────────────────────────────
def fade_in(widget, duration=180, offset=10):
    """Fade and rise a widget into place (used on page switches)."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    widget._fade_anim = anim


# ── toasts ──────────────────────────────────────────────────────────────
class Toast(QFrame):
    """Transient message that slides up from the bottom of its host window."""
    _ICONS = {"good": "check", "bad": "alert", "warn": "alert", "info": "info"}

    def __init__(self, host, text, kind="good", duration=2800):
        super().__init__(host)
        self.setObjectName("Toast")
        ic = QLabel()
        ic.setPixmap(icons.pixmap(self._ICONS.get(kind, "info"), theme.c(kind), 18))
        msg = label(text)
        msg.setWordWrap(True)
        msg.setMaximumWidth(420)
        self.setLayout(hbox(ic, msg, spacing=10, margins=(14, 10, 16, 10)))
        self.adjustSize()
        self._host = host
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._place(0)
        self.show()
        self.raise_()
        self._run(0.0, 1.0, 20, 0)
        QTimer.singleShot(duration, self._dismiss)

    def _place(self, dy):
        x = (self._host.width() - self.width()) // 2
        self.move(x, self._host.height() - self.height() - 28 + dy)

    def _run(self, a, b, y0, y1, then=None):
        fade = QPropertyAnimation(self._effect, b"opacity", self)
        fade.setDuration(200)
        fade.setStartValue(a)
        fade.setEndValue(b)
        slide = QPropertyAnimation(self, b"pos", self)
        slide.setDuration(220)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        x = (self._host.width() - self.width()) // 2
        base = self._host.height() - self.height() - 28
        slide.setStartValue(QPoint(x, base + y0))
        slide.setEndValue(QPoint(x, base + y1))
        if then:
            fade.finished.connect(then)
        fade.start()
        slide.start()
        self._anims = (fade, slide)

    def _dismiss(self):
        try:
            self._run(1.0, 0.0, 0, 12, self.deleteLater)
        except RuntimeError:
            pass


def toast(widget, text, kind="good"):
    """Show a toast on the window that owns ``widget``."""
    host = widget.window()
    old = getattr(host, "_toast", None)
    if old is not None:
        try:
            old.deleteLater()
        except RuntimeError:
            pass
    host._toast = Toast(host, text, kind)


# ── dialogs ─────────────────────────────────────────────────────────────
class Dialog(QDialog):
    """Modal dialog with a title, a body layout, an inline error line and a footer.

        dlg = Dialog(parent, "Add expense", ok_text="Save")
        dlg.body.addWidget(...)
        dlg.on_accept = self.save      # return True to close; raise ValueError to show an error
        if dlg.exec(): ...

    Enter submits, Esc cancels.
    """

    def __init__(self, parent, title, subtitle=None, ok_text="Save", cancel_text="Cancel",
                 width=460, danger=False, ok_icon=None):
        super().__init__(parent.window() if parent else None)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(width)
        self.on_accept = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        head = vbox(label(title, "title"), spacing=3)
        head.itemAt(0).widget().setStyleSheet("font-size:18px;")
        if subtitle:
            head.addWidget(label(subtitle, "subtitle", wrap=True))
        outer.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(12)
        outer.addLayout(self.body, 1)
        self.error = label("", "error", wrap=True)
        self.error.hide()
        outer.addWidget(self.error)
        self.ok_button = button(ok_text, "danger" if danger else "primary", ok_icon, self._accept)
        self.ok_button.setDefault(True)
        self.cancel_button = button(cancel_text, None, None, self.reject)
        self.cancel_button.setAutoDefault(False)
        self.footer = hbox(None, self.cancel_button, self.ok_button)
        if not cancel_text:
            self.cancel_button.hide()
        outer.addLayout(self.footer)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._accept)

    def show_error(self, text):
        self.error.setText(str(text))
        self.error.show()

    def _accept(self):
        self.error.hide()
        if self.on_accept is None:
            self.accept()
            return
        try:
            if self.on_accept() is not False:
                self.accept()
        except (ValueError, PermissionError) as e:
            self.show_error(e)

    def showEvent(self, e):
        super().showEvent(e)
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(140)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start(QPropertyAnimation.DeleteWhenStopped)


def confirm(parent, title, text, ok_text="Confirm", danger=False):
    dlg = Dialog(parent, title, ok_text=ok_text, danger=danger, width=400)
    body = label(text, "muted", wrap=True)
    dlg.body.addWidget(body)
    return dlg.exec() == QDialog.Accepted


def message(parent, title, text, ok_text="OK"):
    dlg = Dialog(parent, title, ok_text=ok_text, cancel_text="", width=400)
    dlg.body.addWidget(label(text, "muted", wrap=True))
    dlg.exec()


# ── page scaffold ───────────────────────────────────────────────────────
class Page(QWidget):
    """Base class for a screen.

    ``self.app`` is the main window: ``app.navigate(key, **kw)``,
    ``app.data_changed()`` (call after any write so other pages reload),
    and ``toast(self, "Saved")`` for feedback. Override ``refresh()``; it runs
    every time the page is shown or data changes elsewhere.
    """
    title = ""
    subtitle = ""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(28, 24, 28, 20)
        self.root.setSpacing(16)
        self.title_label = label(self.title, "title")
        self.subtitle_label = label(self.subtitle, "subtitle")
        self.actions = hbox(spacing=8)
        self.root.addLayout(hbox(vbox(self.title_label, self.subtitle_label, spacing=2), None, self.actions))

    def add_action(self, widget):
        self.actions.addWidget(widget)
        return widget

    def refresh(self):
        pass

    def open(self, **kwargs):
        """Called by ``app.navigate(key, **kwargs)`` after the page is shown."""

    def toast(self, text, kind="good"):
        toast(self, text, kind)
