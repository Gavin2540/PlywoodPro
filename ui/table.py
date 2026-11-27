"""DataTable: a fast, sortable, searchable table over a list of dicts.

    table = DataTable([
        Col("name", "Product", stretch=True, sub=lambda r: r["brand"]),
        Col("stock", "In stock", align="right", fmt=lambda v, r: format_qty(v, r["unit"])),
        Col("status", "Status", badge=lambda r: ("Low", "warn")),
    ], actions=[Action("edit", "Edit", self.edit), Action("trash", "Delete", self.delete)],
       empty=("box", "No products yet", "Add your first product to get started."))
    table.set_rows(rows)
    table.activated.connect(self.edit)      # double-click / Enter -> row dict

Rows are plain dicts; callbacks always receive the row dict.
"""
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QAbstractTableModel, QEvent, QModelIndex, QRect, QSize, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QMenu, QStackedLayout, QStyle,
                               QStyledItemDelegate, QTableView, QToolTip, QVBoxLayout, QWidget)

from ui import icons, theme
from ui.widgets import EmptyState, badge_colors

ROW_HEIGHT = 46


@dataclass
class Col:
    key: str
    title: str
    width: Optional[int] = None            # fixed px width; None = size to header/default
    stretch: bool = False                  # take the remaining width
    align: str = "left"                    # left | right | center
    fmt: Optional[Callable] = None         # (value, row) -> str
    sub: Optional[Callable] = None         # row -> small second line
    color: Optional[Callable] = None       # row -> theme key ("good", "bad", "text2"…) or None
    badge: Optional[Callable] = None       # row -> (text, kind) or None
    sort: Optional[Callable] = None        # row -> sortable value
    bold: bool = False
    numeric: bool = False                  # tabular digits


@dataclass
class Action:
    icon: str
    tooltip: str
    callback: Callable                     # row -> None
    visible: Optional[Callable] = None     # row -> bool
    color: Optional[str] = None            # theme key


class _Model(QAbstractTableModel):
    def __init__(self, cols, n_actions):
        super().__init__()
        self.cols, self.rows, self.n_actions = cols, [], n_actions

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.cols) + (1 if self.n_actions else 0)

    def text(self, row, col):
        v = row.get(col.key)
        if col.fmt:
            return col.fmt(v, row)
        return "—" if v is None or v == "" else str(v)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.column() >= len(self.cols):
            return None
        row, col = self.rows[index.row()], self.cols[index.column()]
        if role == Qt.DisplayRole:
            return self.text(row, col)
        if role == Qt.UserRole:  # sort value
            if col.sort:
                return col.sort(row)
            v = row.get(col.key)
            return v.lower() if isinstance(v, str) else (v if v is not None else "")
        if role == Qt.ToolTipRole:
            return None if col.badge or col.align == 'right' else self.text(row, col)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation != Qt.Horizontal:
            return None
        if role == Qt.DisplayRole:
            return self.cols[section].title.upper() if section < len(self.cols) else ""
        if role == Qt.TextAlignmentRole and section < len(self.cols):
            return int(_ALIGN[self.cols[section].align] | Qt.AlignVCenter)
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()


_ALIGN = {"left": Qt.AlignLeft, "right": Qt.AlignRight, "center": Qt.AlignHCenter}


class _Proxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.needle = ""
        self.predicate = None
        self.setSortRole(Qt.UserRole)

    def filterAcceptsRow(self, source_row, parent):
        m = self.sourceModel()
        row = m.rows[source_row]
        if self.predicate and not self.predicate(row):
            return False
        if not self.needle:
            return True
        hay = " ".join(m.text(row, c) + " " + (c.sub(row) or "" if c.sub else "") for c in m.cols).lower()
        return all(part in hay for part in self.needle.split())

    def lessThan(self, left, right):
        a, b = left.data(Qt.UserRole), right.data(Qt.UserRole)
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


class _Delegate(QStyledItemDelegate):
    def __init__(self, table):
        super().__init__(table.view)
        self.t = table

    def sizeHint(self, option, index):
        return QSize(60, ROW_HEIGHT)

    def _action_rects(self, rect, row):
        size, gap = 30, 2
        x = rect.right() - 8 - len(self.t.actions) * (size + gap)
        out = []
        for a in self.t.actions:  # hidden actions keep their slot so icons line up across rows
            if not a.visible or a.visible(row):
                out.append((a, QRect(x, rect.center().y() - size // 2, size, size)))
            x += size + gap
        return out

    def paint(self, p, option, index):
        t = self.t
        src = t.proxy.mapToSource(index)
        row = t.model.rows[src.row()]
        rect = option.rect
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        hovered = index.row() == t._hover_row
        if option.state & QStyle.State_Selected:
            p.fillRect(rect, theme.qc("surface3"))
        elif hovered:
            p.fillRect(rect, theme.qc("surface2"))
        p.setPen(theme.qc("border"))
        p.drawLine(rect.bottomLeft(), rect.bottomRight())

        if src.column() >= len(t.cols):  # actions column
            for a, r in self._action_rects(rect, row):
                hot = hovered and t._hover_pos is not None and r.contains(t._hover_pos)
                if hot:
                    path = QPainterPath()
                    path.addRoundedRect(r, 7, 7)
                    p.fillPath(path, theme.qc("border"))
                color = theme.c(a.color) if a.color and hot else theme.c("text" if hot else "text3")
                if hovered or option.state & QStyle.State_Selected:
                    p.drawPixmap(r.center().x() - 8, r.center().y() - 8, icons.pixmap(a.icon, color, 16))
                else:
                    p.setOpacity(0.55)
                    p.drawPixmap(r.center().x() - 8, r.center().y() - 8, icons.pixmap(a.icon, theme.c("text3"), 16))
                    p.setOpacity(1)
            p.restore()
            return

        col = t.cols[src.column()]
        inner = rect.adjusted(12, 0, -12, 0)
        if col.badge:
            b = col.badge(row)
            if b:
                text, kind = b
                fg, bg = badge_colors(kind)
                f = theme.font(11, QFont.Bold)
                p.setFont(f)
                w = p.fontMetrics().horizontalAdvance(text) + 18
                h = 20
                if col.align == "right":
                    x = inner.right() - w
                elif col.align == "center":
                    x = inner.center().x() - w // 2
                else:
                    x = inner.left()
                pill = QRect(x, rect.center().y() - h // 2 + 1, w, h)
                path = QPainterPath()
                path.addRoundedRect(pill, h / 2, h / 2)
                p.fillPath(path, QColor(bg))
                p.setPen(QColor(fg))
                p.drawText(pill, Qt.AlignCenter, text)
            p.restore()
            return

        text = t.model.text(row, col)
        sub = col.sub(row) if col.sub else None
        key = col.color(row) if col.color else None
        p.setPen(theme.qc(key or "text"))
        f = theme.font(13, QFont.DemiBold if col.bold else QFont.Normal, tabular=col.numeric or col.align == "right")
        p.setFont(f)
        flags = _ALIGN[col.align] | Qt.AlignVCenter
        if sub:
            top = QRect(inner.left(), rect.top() + 6, inner.width(), 18)
            p.drawText(top, _ALIGN[col.align] | Qt.AlignVCenter, p.fontMetrics().elidedText(text, Qt.ElideRight, inner.width()))
            p.setPen(theme.qc("text3"))
            p.setFont(theme.font(11))
            bottom = QRect(inner.left(), rect.top() + 24, inner.width(), 16)
            p.drawText(bottom, _ALIGN[col.align] | Qt.AlignVCenter, p.fontMetrics().elidedText(sub, Qt.ElideRight, inner.width()))
        else:
            p.drawText(inner, flags, p.fontMetrics().elidedText(text, Qt.ElideRight, inner.width()))
        p.restore()


class DataTable(QWidget):
    activated = Signal(dict)          # double-click or Enter on a row
    selection_changed = Signal()
    filtered = Signal()               # visible rows changed (set_rows / set_search / set_filter)

    def __init__(self, cols, actions=None, empty=None, menu=None, sortable=True):
        """empty: (icon, title, hint). menu: row -> [(text, callback) | None for separator]."""
        super().__init__()
        self.cols, self.actions, self.menu = list(cols), list(actions or []), menu
        self._hover_row, self._hover_pos = -1, None
        self.model = _Model(self.cols, len(self.actions))
        self.proxy = _Proxy()
        self.proxy.setSourceModel(self.model)

        v = self.view = QTableView()
        v.setModel(self.proxy)
        v.setItemDelegate(_Delegate(self))
        v.setSelectionBehavior(QAbstractItemView.SelectRows)
        v.setSelectionMode(QAbstractItemView.SingleSelection)
        v.setEditTriggers(QAbstractItemView.NoEditTriggers)
        v.setShowGrid(False)
        v.setWordWrap(False)
        v.setMouseTracking(True)
        v.setSortingEnabled(sortable)
        v.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        v.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        v.verticalScrollBar().setSingleStep(16)
        v.verticalHeader().hide()
        v.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        v.setFocusPolicy(Qt.StrongFocus)
        h = v.horizontalHeader()
        h.setHighlightSections(False)
        h.setSectionsClickable(sortable)
        h.setFixedHeight(38)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        h.setMinimumSectionSize(40)
        h.setSortIndicatorShown(sortable)
        if sortable:
            h.setSortIndicator(-1, Qt.AscendingOrder)
        any_stretch = any(c.stretch for c in self.cols)
        for i, c in enumerate(self.cols):
            if c.stretch or (not any_stretch and i == 0):
                h.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                h.setSectionResizeMode(i, QHeaderView.Interactive)
                v.setColumnWidth(i, c.width or 120)
        if self.actions:
            i = len(self.cols)
            h.setSectionResizeMode(i, QHeaderView.Fixed)
            v.setColumnWidth(i, 20 + 32 * len(self.actions))

        self.empty = EmptyState(*(empty or ("box", "Nothing to show", "")))
        self.stack = QStackedLayout()
        self.stack.addWidget(v)
        self.stack.addWidget(self.empty)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self.stack)
        self._empty_default = empty or ("box", "Nothing to show", "")

        v.viewport().installEventFilter(self)
        v.installEventFilter(self)
        v.doubleClicked.connect(self._activate)
        v.setContextMenuPolicy(Qt.CustomContextMenu)
        v.customContextMenuRequested.connect(self._context)
        v.selectionModel().selectionChanged.connect(lambda *_: self.selection_changed.emit())

    # ── data ────────────────────────────────────────────────────────────
    def set_rows(self, rows):
        keep = self.selected()
        scroll = self.view.verticalScrollBar().value()
        self.model.set_rows(rows)
        self._hover_row = -1
        self._sync_empty()
        self.view.verticalScrollBar().setValue(scroll)
        if keep and "id" in keep:
            self.select_where(lambda r: r.get("id") == keep["id"])

    def rows(self):
        """Rows currently visible (after search / filter), in display order."""
        return [self.model.rows[self.proxy.mapToSource(self.proxy.index(i, 0)).row()]
                for i in range(self.proxy.rowCount())]

    def set_search(self, text):
        self.proxy.needle = (text or "").lower().strip()
        self.proxy.invalidate()
        self._sync_empty()

    def set_filter(self, predicate):
        """predicate: row -> bool, or None to clear."""
        self.proxy.predicate = predicate
        self.proxy.invalidate()
        self._sync_empty()

    def _sync_empty(self):
        self.filtered.emit()
        if self.proxy.rowCount():
            self.stack.setCurrentIndex(0)
            return
        if self.model.rows:
            self.empty.set_text("No matches", "Try a different search or filter.")
        else:
            self.empty.set_text(self._empty_default[1], self._empty_default[2])
        self.stack.setCurrentIndex(1)

    def selected(self):
        idx = self.view.selectionModel().selectedRows() if self.view.selectionModel() else []
        if not idx:
            return None
        return self.model.rows[self.proxy.mapToSource(idx[0]).row()]

    def select_where(self, predicate):
        for i in range(self.proxy.rowCount()):
            row = self.model.rows[self.proxy.mapToSource(self.proxy.index(i, 0)).row()]
            if predicate(row):
                self.view.selectRow(i)
                self.view.scrollTo(self.proxy.index(i, 0))
                return True
        return False

    def sort_by(self, key, descending=False):
        for i, c in enumerate(self.cols):
            if c.key == key:
                self.view.sortByColumn(i, Qt.DescendingOrder if descending else Qt.AscendingOrder)

    def fit_height(self, max_rows=None):
        """Size the table to its rows (for tables inside a scrolling page)."""
        n = self.proxy.rowCount()
        if max_rows:
            n = min(n, max_rows)
        self.setFixedHeight(38 + max(n, 3) * ROW_HEIGHT + 4)

    # ── interaction ─────────────────────────────────────────────────────
    def _row_at(self, index):
        return self.model.rows[self.proxy.mapToSource(index).row()]

    def _activate(self, index):
        if index.isValid() and self.proxy.mapToSource(index).column() < len(self.cols):
            self.activated.emit(self._row_at(index))

    def _context(self, pos):
        index = self.view.indexAt(pos)
        if not index.isValid():
            return
        row = self._row_at(index)
        items = self.menu(row) if self.menu else [
            (a.tooltip, (lambda a=a: a.callback(row))) for a in self.actions if not a.visible or a.visible(row)]
        if not items:
            return
        menu = QMenu(self)
        for it in items:
            if it is None:
                menu.addSeparator()
            else:
                menu.addAction(it[0], it[1])
        menu.exec(self.view.viewport().mapToGlobal(pos))

    def eventFilter(self, obj, event):
        vp = self.view.viewport()
        if obj is vp:
            et = event.type()
            if et == QEvent.MouseMove:
                index = self.view.indexAt(event.pos())
                row = index.row() if index.isValid() else -1
                self._hover_pos = event.pos()
                if row != self._hover_row or self.actions:
                    self._hover_row = row
                    vp.update()
                hit = self._action_at(event.pos())
                vp.setCursor(Qt.PointingHandCursor if hit else Qt.ArrowCursor)
                if hit:
                    QToolTip.showText(event.globalPosition().toPoint(), hit[0].tooltip, vp)
            elif et == QEvent.Leave:
                self._hover_row, self._hover_pos = -1, None
                vp.update()
            elif et == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                hit = self._action_at(event.pos())
                if hit:
                    hit[0].callback(hit[1])
                    return True
        elif obj is self.view and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                row = self.selected()
                if row:
                    self.activated.emit(row)
                    return True
        return super().eventFilter(obj, event)

    def _action_at(self, pos):
        if not self.actions:
            return None
        index = self.view.indexAt(pos)
        if not index.isValid() or self.proxy.mapToSource(index).column() < len(self.cols):
            return None
        row = self._row_at(index)
        for a, r in self.view.itemDelegate()._action_rects(self.view.visualRect(index), row):
            if r.contains(pos):
                return a, row
        return None
