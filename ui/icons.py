"""Inline stroke icons (24x24 grid), tinted to any theme colour at runtime.

    icons.icon("plus")                      # QIcon in the secondary text colour
    icons.icon("check", theme.c("good"), 18)
"""
from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ui import theme

_PATHS = {
    "dashboard": '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
    "sale": '<path d="M6 2h12v20l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
    "purchase": '<path d="M3 7h13v10H3z"/><path d="M16 10h3l2 3v4h-5"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
    "products": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 12l9 5 9-5"/><path d="M3 16l9 5 9-5"/>',
    "people": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.900 1.900 6.500 5.500"/><path d="M16 4.800a3.500 3.500 0 010 6.400M18.500 14.800c1.700.800 2.700 2.500 3 5.200"/>',
    "expense": '<rect x="2.500" y="6" width="19" height="13" rx="2"/><path d="M2.500 10h19"/><path d="M6.500 15h4"/>',
    "report": '<path d="M4 20V4"/><path d="M4 20h16"/><path d="M8 16v-5M12 16V8M16 16v-3"/>',
    "ledger": '<path d="M5 3h12a2 2 0 012 2v16H7a2 2 0 01-2-2z"/><path d="M5 17a2 2 0 012-2h12"/><path d="M9 7h6M9 11h4"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.400 15a1.700 1.700 0 00.300 1.800l.100.100a2 2 0 11-2.800 2.800l-.100-.100a1.700 1.700 0 00-2.800 1.200V21a2 2 0 11-4 0v-.100a1.700 1.700 0 00-2.900-1.100l-.100.100a2 2 0 11-2.800-2.800l.100-.100A1.700 1.700 0 003.100 14H3a2 2 0 110-4h.100a1.700 1.700 0 001.100-2.900l-.100-.100a2 2 0 112.800-2.800l.100.100a1.700 1.700 0 001.800.300H9a1.700 1.700 0 001-1.500V3a2 2 0 114 0v.100a1.700 1.700 0 002.900 1.100l.100-.100a2 2 0 112.800 2.800l-.100.100a1.700 1.700 0 00-.300 1.800V9a1.700 1.700 0 001.500 1H21a2 2 0 110 4h-.100a1.700 1.700 0 00-1.500 1z"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20.500 20.500L16 16"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.500 6.500l4 4"/>',
    "trash": '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/><path d="M10 11v5M14 11v5"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "check": '<path d="M4.500 12.500l5 5 10-11"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7.500a4 4 0 018 0V11"/>',
    "unlock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7.500a4 4 0 017.500-2"/>',
    "download": '<path d="M12 4v11"/><path d="M7 11l5 5 5-5"/><path d="M5 20h14"/>',
    "upload": '<path d="M12 16V5"/><path d="M7 9l5-5 5 5"/><path d="M5 20h14"/>',
    "print": '<path d="M7 8V3h10v5"/><rect x="3" y="8" width="18" height="9" rx="2"/><path d="M7 14h10v7H7z"/>',
    "alert": '<path d="M12 3.500l9.500 16.500h-19z"/><path d="M12 10v4.500M12 17.300v.200"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.500v.200"/>',
    "calendar": '<rect x="3.500" y="5" width="17" height="15.500" rx="2"/><path d="M3.500 10h17M8 3v4M16 3v4"/>',
    "chevron-right": '<path d="M9 5l7 7-7 7"/>',
    "chevron-left": '<path d="M15 5l-7 7 7 7"/>',
    "chevron-down": '<path d="M5 9l7 7 7-7"/>',
    "arrow-up": '<path d="M12 19V5"/><path d="M6 11l6-6 6 6"/>',
    "arrow-down": '<path d="M12 5v14"/><path d="M6 13l6 6 6-6"/>',
    "refresh": '<path d="M20 11a8 8 0 00-14.500-4.200L4 8.500"/><path d="M4 4v4.500h4.500"/><path d="M4 13a8 8 0 0014.500 4.200l1.500-1.700"/><path d="M20 20v-4.500h-4.500"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.500v2M12 19.500v2M2.500 12h2M19.500 12h2M5.300 5.300l1.400 1.400M17.300 17.300l1.400 1.400M5.300 18.700l1.400-1.400M17.300 6.700l1.400-1.400"/>',
    "moon": '<path d="M20 14.500A8.500 8.500 0 119.500 4a7 7 0 0010.500 10.500z"/>',
    "wallet": '<path d="M4 6.500A2.500 2.500 0 016.500 4H18v4"/><rect x="4" y="8" width="17" height="12" rx="2"/><path d="M16.500 14h.200"/>',
    "box": '<path d="M3.500 7.500L12 3l8.500 4.500v9L12 21l-8.500-4.500z"/><path d="M3.500 7.500L12 12l8.500-4.500M12 12v9"/>',
    "history": '<path d="M4 12a8 8 0 108-8 8.500 8.500 0 00-6 2.500L4 8.500"/><path d="M4 4v4.500h4.500"/><path d="M12 8v4.500l3 2"/>',
    "file": '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/>',
    "more": '<circle cx="5" cy="12" r="1.200"/><circle cx="12" cy="12" r="1.200"/><circle cx="19" cy="12" r="1.200"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "phone": '<path d="M5 4h4l2 5-2.500 1.500a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z"/>',
    "rupee": '<path d="M7 4h11M7 9h11M7 4c6 0 6 9 0 9l8 7"/>',
    "clipboard": '<rect x="5" y="4.500" width="14" height="16.500" rx="2"/><path d="M9 4.500V3h6v1.500"/><path d="M9 11l2 2 4-4M9 17h6"/>',
}

_cache = {}


def names():
    return sorted(_PATHS)


def pixmap(name, color=None, size=18):
    color = color or theme.c("text2")
    app_dpr = 2.0
    key = (name, color, size)
    if key in _cache:
        return _cache[key]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="1.800" stroke-linecap="round" stroke-linejoin="round">{_PATHS[name]}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(QSize(int(size * app_dpr), int(size * app_dpr)))
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    renderer.render(painter, QRectF(0, 0, size * app_dpr, size * app_dpr))
    painter.end()
    pm.setDevicePixelRatio(app_dpr)
    _cache[key] = pm
    return pm


def icon(name, color=None, size=18):
    return QIcon(pixmap(name, color, size))
