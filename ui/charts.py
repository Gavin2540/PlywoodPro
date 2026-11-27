"""Lightweight animated charts painted with QPainter (no QtCharts dependency).

    chart = TrendChart()                       # bars + optional line
    chart.set_data(labels, bars, line=None, bar_name="Revenue", line_name="Net profit")

    donut = DonutChart()
    donut.set_data([("Transport", 1200.0), ("Labour", 800.0)])

    hbar = RankBars()                          # horizontal ranked bars
    hbar.set_data([("Ply 18mm", 54000.0, "42 sheets"), ...])
"""
import math

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from ui import theme
from utils.helpers import format_compact, format_currency


class _Animated(QWidget):
    def __init__(self):
        super().__init__()
        self._t = 1.0
        self._anim = QVariantAnimation(self, duration=520, easingCurve=QEasingCurve.OutCubic)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.valueChanged.connect(self._tick)
        self.setMouseTracking(True)

    def _tick(self, v):
        self._t = float(v)
        self.update()

    def _play(self):
        self._anim.stop()
        self._anim.start()


def _nice_max(v):
    if v <= 0:
        return 1.0
    exp = math.floor(math.log10(v))
    frac = v / 10 ** exp
    for step in (1, 1.2, 1.6, 2, 2.4, 3.2, 4, 6, 8, 10):  # each divides cleanly into 4 ticks
        if frac <= step:
            return step * 10 ** exp
    return 10 ** (exp + 1)


class TrendChart(_Animated):
    """Bars per label with an optional overlaid line (which may go negative)."""

    def __init__(self, height=240):
        super().__init__()
        self.labels, self.bars, self.line = [], [], None
        self.bar_name, self.line_name = "", ""
        self._hover = -1
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, labels, bars, line=None, bar_name="", line_name=""):
        self.labels, self.bars, self.line = list(labels), [float(b) for b in bars], \
            ([float(x) for x in line] if line is not None else None)
        self.bar_name, self.line_name = bar_name, line_name
        self._hover = -1
        self._play()

    def _plot(self):
        return QRectF(52, 14, self.width() - 62, self.height() - 44)

    def _scale(self):
        values = self.bars + (self.line or [])
        hi = _nice_max(max(values + [0]))
        lo = min(values + [0])
        lo = -_nice_max(-lo) if lo < 0 else 0.0
        return lo, hi

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        plot = self._plot()
        n = len(self.bars)
        if n == 0 or not any(self.bars + (self.line or [])):
            p.setPen(theme.qc("text3"))
            p.setFont(theme.font(13))
            p.drawText(self.rect(), Qt.AlignCenter, "No activity in this period")
            return
        lo, hi = self._scale()
        span = hi - lo

        def y_of(v):
            return plot.bottom() - (v - lo) / span * plot.height()

        p.setFont(theme.font(11, tabular=True))
        ticks = 4
        for i in range(ticks + 1):
            v = lo + span * i / ticks
            y = y_of(v)
            p.setPen(QPen(theme.qc("border"), 1, Qt.SolidLine if abs(v) < 1e-9 else Qt.DotLine))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(theme.qc("text3"))
            p.drawText(QRectF(0, y - 9, plot.left() - 8, 18), Qt.AlignRight | Qt.AlignVCenter, format_compact(v))

        slot = plot.width() / n
        bw = max(3.0, min(34.0, slot * 0.62))
        zero = y_of(0)
        accent = QColor(theme.chart_colors()[0])
        for i, v in enumerate(self.bars):
            x = plot.left() + slot * i + (slot - bw) / 2
            top = y_of(v * self._t)
            r = QRectF(x, min(top, zero), bw, abs(zero - top))
            col = QColor(accent)
            col.setAlpha(255 if i == self._hover or self._hover < 0 else 130)
            path = QPainterPath()
            rad = min(4.0, bw / 2)
            path.addRoundedRect(r.adjusted(0, 0, 0, rad), rad, rad)
            p.save()
            p.setClipRect(QRectF(x - 1, plot.top() - 2, bw + 2, zero - plot.top() + 2))
            p.fillPath(path, col)
            p.restore()

        if self.line:
            col = QColor(theme.chart_colors()[2])
            pts = [QPointF(plot.left() + slot * i + slot / 2, y_of(v * self._t)) for i, v in enumerate(self.line)]
            p.setPen(QPen(col, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            path = QPainterPath(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            p.drawPath(path)
            if n <= 40:
                p.setBrush(theme.qc("surface"))
                for i, pt in enumerate(pts):
                    p.drawEllipse(pt, 4 if i == self._hover else 2.6, 4 if i == self._hover else 2.6)

        p.setPen(theme.qc("text3"))
        step = max(1, math.ceil(n / max(1, int(plot.width() // 58))))
        for i, text in enumerate(self.labels):
            if i % step == 0 or i == self._hover:
                cx = plot.left() + slot * i + slot / 2
                p.drawText(QRectF(cx - 40, plot.bottom() + 8, 80, 16), Qt.AlignCenter, text)

        # legend
        x = plot.left()
        p.setFont(theme.font(11))
        for name, color in ((self.bar_name, theme.chart_colors()[0]),
                            (self.line_name if self.line else "", theme.chart_colors()[2])):
            if not name:
                continue
            p.setBrush(QColor(color))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x, 2, 8, 8), 2, 2)
            p.setPen(theme.qc("text2"))
            w = p.fontMetrics().horizontalAdvance(name)
            p.drawText(QRectF(x + 13, -3, w + 4, 18), Qt.AlignVCenter, name)
            x += w + 30

    def mouseMoveEvent(self, e):
        plot, n = self._plot(), len(self.bars)
        i = -1
        if n and plot.left() <= e.position().x() <= plot.right():
            i = min(n - 1, int((e.position().x() - plot.left()) / (plot.width() / n)))
        if i != self._hover:
            self._hover = i
            self.update()
        if i >= 0:
            text = f"<b>{self.labels[i]}</b><br>{self.bar_name}: {format_currency(self.bars[i], decimals=0)}"
            if self.line:
                text += f"<br>{self.line_name}: {format_currency(self.line[i], decimals=0)}"
            QToolTip.showText(e.globalPosition().toPoint(), text, self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, _):
        self._hover = -1
        self.update()


class DonutChart(_Animated):
    """Share-of-total ring with a legend on the right."""

    def __init__(self, height=200, center_caption="Total", legend=True):
        super().__init__()
        self.items, self.caption, self.legend = [], center_caption, legend
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, items, max_slices=6):
        items = [(n, float(v)) for n, v in items if v and v > 0]
        items.sort(key=lambda x: -x[1])
        if len(items) > max_slices:
            rest = sum(v for _, v in items[max_slices - 1:])
            items = items[:max_slices - 1] + [("Other", rest)]
        self.items = items
        self._play()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        total = sum(v for _, v in self.items)
        if total <= 0:
            p.setPen(theme.qc("text3"))
            p.setFont(theme.font(13))
            p.drawText(self.rect(), Qt.AlignCenter, "Nothing recorded in this period")
            return
        if self.legend:
            size = min(self.height() - 16, self.width() * 0.45, 190)
            ring = QRectF(8, (self.height() - size) / 2, size, size)
        else:  # ring only, centred; the page draws its own legend
            size = min(self.height() - 16, self.width() - 16, 200)
            ring = QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size)
        thickness = max(14.0, size * 0.16)
        colors = theme.chart_colors()
        start = 90 * 16
        for i, (_name, v) in enumerate(self.items):
            sweep = -v / total * 360 * 16 * self._t
            pen = QPen(QColor(colors[i % len(colors)]), thickness, Qt.SolidLine, Qt.FlatCap)
            p.setPen(pen)
            inset = thickness / 2
            p.drawArc(ring.adjusted(inset, inset, -inset, -inset), int(start), int(sweep))
            start += sweep
        p.setPen(theme.qc("text3"))
        p.setFont(theme.font(11))
        p.drawText(QRectF(ring.left(), ring.center().y() - 22, ring.width(), 16), Qt.AlignCenter, self.caption)
        p.setPen(theme.qc("text"))
        p.setFont(theme.font(16, QFont.Bold, tabular=True))
        p.drawText(QRectF(ring.left(), ring.center().y() - 6, ring.width(), 24), Qt.AlignCenter,
                   format_compact(total))

        if not self.legend:
            return
        x = ring.right() + 22
        row_h = 24
        y = (self.height() - row_h * len(self.items)) / 2
        for i, (name, v) in enumerate(self.items):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(colors[i % len(colors)]))
            p.drawRoundedRect(QRectF(x, y + 8, 9, 9), 2.5, 2.5)
            p.setPen(theme.qc("text"))
            p.setFont(theme.font(12))
            avail = self.width() - x - 22 - 96
            p.drawText(QRectF(x + 17, y, avail, row_h), Qt.AlignVCenter,
                       p.fontMetrics().elidedText(name, Qt.ElideRight, int(avail)))
            p.setPen(theme.qc("text2"))
            p.setFont(theme.font(12, tabular=True))
            p.drawText(QRectF(self.width() - 104, y, 96, row_h), Qt.AlignVCenter | Qt.AlignRight,
                       f"{format_compact(v)}  {v / total * 100:.0f}%")
            y += row_h


class RankBars(_Animated):
    """Horizontal ranked bars: [(label, value, caption)]."""

    ROW = 38

    def __init__(self, rows=5, color_index=0):
        super().__init__()
        self.items, self.color_index, self._rows = [], color_index, rows
        self.setMinimumHeight(self.ROW * rows + 4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_data(self, items):
        self.items = list(items)[: self._rows]
        self._play()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.items:
            p.setPen(theme.qc("text3"))
            p.setFont(theme.font(13))
            p.drawText(self.rect(), Qt.AlignCenter, "No sales in this period")
            return
        top = max(v for _, v, _ in self.items) or 1
        color = QColor(theme.chart_colors()[self.color_index])
        w = self.width()
        for i, (name, v, caption) in enumerate(self.items):
            y = i * self.ROW
            p.setPen(theme.qc("text"))
            p.setFont(theme.font(12))
            p.drawText(QRectF(0, y, w - 170, 18), Qt.AlignVCenter,
                       p.fontMetrics().elidedText(name, Qt.ElideRight, w - 170))
            p.setPen(theme.qc("text2"))
            p.setFont(theme.font(12, tabular=True))
            p.drawText(QRectF(w - 160, y, 160, 18), Qt.AlignVCenter | Qt.AlignRight,
                       f"{caption}   {format_compact(v)}" if caption else format_compact(v))
            track = QRectF(0, y + 22, w, 6)
            p.setPen(Qt.NoPen)
            p.setBrush(theme.qc("surface2"))
            p.drawRoundedRect(track, 3, 3)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(0, y + 22, max(6.0, w * v / top * self._t), 6), 3, 3)
