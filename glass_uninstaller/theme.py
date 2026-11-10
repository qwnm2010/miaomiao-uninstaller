"""Visual language: a cold, precise instrument panel for Miaomiao."""
from __future__ import annotations

import math
import random
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient,
)

APP_DIR = Path(__file__).resolve().parent.parent
ASSETS = APP_DIR / "assets"

# ---- Palette --------------------------------------------------------------
BG_TOP = QColor("#EFF2F5")
BG_BOTTOM = QColor("#E8ECF0")
PAGE = QColor("#EDF0F3")
SIDEBAR = QColor("#E9EDF1")
CARD = QColor("#FFFFFF")
RAISED = QColor("#F5F7F9")
ACTIVE = QColor("#E5ECF2")
TEXT = QColor("#11161C")
TEXT_SOFT = QColor("#3F4954")
TEXT_MUTED = QColor("#68737F")
TEXT_DIM = QColor("#98A1AB")
ACCENT = QColor("#315D78")
ACCENT_2 = QColor("#5D7D91")
MINT = QColor("#3F7565")
ROSE = QColor("#8C4D55")
AMBER = QColor("#846532")
WHITE = QColor("#FFFFFF")
DANGER = QColor("#8B3F47")
SUCCESS = QColor("#2F7658")
HAIRLINE = QColor(17, 22, 28, 24)
DIVIDER = QColor(17, 22, 28, 18)
SURFACE = QColor("#FFFFFF")

SOURCE_COLORS = {
    "APT": QColor("#315D78"),
    "Flatpak": QColor("#4E7568"),
    "Snap": QColor("#846532"),
    "本地": QColor("#5C6672"),
}

_families: list[str] | None = None


def families() -> list[str]:
    global _families
    if _families is None:
        _families = QFontDatabase.families()
    return _families


def ui_family() -> str:
    for name in ("Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans", "DejaVu Sans"):
        if name in families():
            return name
    return "Sans Serif"


def display_family() -> str:
    for name in ("Noto Sans Display", "Noto Sans CJK SC", "Noto Sans", "DejaVu Sans"):
        if name in families():
            return name
    return "Sans Serif"


def font(size: int, weight: int = 400, display: bool = False, spacing: float = 0.0) -> QFont:
    f = QFont(display_family() if display else ui_family())
    f.setPixelSize(size)
    # The interface uses two weights. 600 is reserved for the page title and
    # the wordmark; old 650/700 calls collapse into the same calm hierarchy.
    if weight >= 600:
        weight = 600 if display and size >= 24 else 500
    f.setWeight(QFont.Weight(weight))
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def mono_font(size: int, weight: int = 400) -> QFont:
    family = next((name for name in ("Noto Sans Mono", "Noto Sans Mono CJK SC",
                                     "DejaVu Sans Mono") if name in families()),
                  "Monospace")
    f = QFont(family)
    f.setPixelSize(size)
    f.setWeight(QFont.Weight(500 if weight >= 500 else 400))
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


# ---- Noise ---------------------------------------------------------------
_noise: QPixmap | None = None


def noise_pixmap() -> QPixmap:
    global _noise
    if _noise is None:
        rng = random.Random(2611)
        size = 160
        img = QPixmap(size, size)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        for _ in range(3300):
            x, y = rng.randrange(size), rng.randrange(size)
            a = rng.choice([8, 12, 16, 20])
            p.setPen(QColor(31, 39, 50, a))
            p.drawPoint(x, y)
        p.end()
        _noise = img
    return _noise


# ---- Painting helpers ----------------------------------------------------
def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def paint_glass(painter: QPainter, rect: QRectF, radius: float = 16,
                tint: QColor | None = None, hover: float = 0.0,
                fill: float = 1.0, border: float = 1.0,
                shadow: bool = False) -> QPainterPath:
    """Paint a quiet solid instrument surface.

    The name is historical; this deliberately has no blur, gradient, grain or
    specular highlight. Depth comes from the surface step and the hairline.
    """
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = rounded_path(rect, radius)
    painter.setClipPath(path)

    base = CARD if fill >= 0.65 else RAISED
    painter.fillPath(path, base)
    if tint is not None and fill >= 0.65:
        c = QColor(tint)
        c.setAlpha(int(8 * min(1.0, fill)))
        painter.fillPath(path, c)
    if hover > 0:
        c = QColor(17, 22, 28, int(4 + 6 * hover))
        painter.fillPath(path, c)
    if shadow:
        # A single neutral lower edge; no colored or blurred shadow.
        sg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        sg.setColorAt(0.0, QColor(0, 0, 0, 0))
        sg.setColorAt(1.0, QColor(0, 0, 0, 10))
        painter.fillPath(path, sg)

    painter.setClipping(False)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(HAIRLINE, 1.0 if border else 0.0))
    painter.drawPath(path)
    painter.restore()
    return path

def paint_dot(painter: QPainter, center: QPointF, radius: float,
              color: QColor, glow: bool = False) -> None:
    painter.save()
    center = QPointF(center)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(center, radius, radius)
    painter.restore()


# ---- Icon set ------------------------------------------------------------
def draw_icon(painter: QPainter, kind: str, rect: QRectF,
              color: QColor = TEXT_SOFT, width: float = 1.7) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p = QPen(color, width)
    p.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(p)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    cx, cy = x + w / 2, y + h / 2
    s = min(w, h)

    def L(x1, y1, x2, y2):
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def R(rx, ry, rw, rh, rr=2.5):
        painter.drawRoundedRect(QRectF(rx, ry, rw, rh), rr, rr)

    if kind == "apps":
        g = s * 0.10
        cell = (s - g * 3) / 2
        for ix in range(2):
            for iy in range(2):
                R(x + g + ix * (cell + g), y + g + iy * (cell + g), cell, cell, 2.8)
    elif kind == "sparkles":
        # four-point stars
        for (px, py, sc) in ((0.34, 0.30, 0.28), (0.66, 0.66, 0.20), (0.70, 0.26, 0.13)):
            path = QPainterPath()
            cxp, cyp = x + s * px, y + s * py
            r = s * sc
            path.moveTo(cxp, cyp - r)
            path.quadTo(cxp + r * 0.18, cyp - r * 0.18, cxp + r, cyp)
            path.quadTo(cxp + r * 0.18, cyp + r * 0.18, cxp, cyp + r)
            path.quadTo(cxp - r * 0.18, cyp + r * 0.18, cxp - r, cyp)
            path.quadTo(cxp - r * 0.18, cyp - r * 0.18, cxp, cyp - r)
            painter.drawPath(path)
    elif kind == "history":
        painter.drawArc(QRectF(x + s * 0.13, y + s * 0.13, s * 0.74, s * 0.74), 45 * 16, 285 * 16)
        L(cx, y + s * 0.31, cx, cy)
        L(cx, cy, x + s * 0.67, y + s * 0.66)
        path = QPainterPath()
        path.moveTo(x + s * 0.11, y + s * 0.38)
        path.lineTo(x + s * 0.18, y + s * 0.74)
        path.lineTo(x + s * 0.25, y + s * 0.44)
        painter.drawPath(path)
    elif kind == "search":
        painter.drawEllipse(QRectF(x + s * 0.16, y + s * 0.15, s * 0.50, s * 0.50))
        L(x + s * 0.63, y + s * 0.63, x + s * 0.84, y + s * 0.84)
    elif kind == "refresh":
        painter.drawArc(QRectF(x + s * 0.17, y + s * 0.17, s * 0.66, s * 0.66), 25 * 16, 300 * 16)
        path = QPainterPath()
        path.moveTo(x + s * 0.74, y + s * 0.12)
        path.lineTo(x + s * 0.84, y + s * 0.30)
        path.lineTo(x + s * 0.62, y + s * 0.32)
        painter.drawPath(path)
    elif kind == "close":
        L(x + s * 0.28, y + s * 0.28, x + s * 0.72, y + s * 0.72)
        L(x + s * 0.72, y + s * 0.28, x + s * 0.28, y + s * 0.72)
    elif kind == "minimize":
        L(x + s * 0.26, y + s * 0.62, x + s * 0.74, y + s * 0.62)
    elif kind == "maximize":
        R(x + s * 0.28, y + s * 0.28, s * 0.44, s * 0.44, 2)
    elif kind == "restore":
        R(x + s * 0.22, y + s * 0.38, s * 0.40, s * 0.40, 2)
        L(x + s * 0.38, y + s * 0.38, x + s * 0.38, y + s * 0.22)
        L(x + s * 0.38, y + s * 0.22, x + s * 0.78, y + s * 0.22)
        L(x + s * 0.78, y + s * 0.22, x + s * 0.78, y + s * 0.60)
        L(x + s * 0.78, y + s * 0.60, x + s * 0.62, y + s * 0.60)
    elif kind == "chevron":
        path = QPainterPath()
        path.moveTo(x + s * 0.40, y + s * 0.25)
        path.lineTo(x + s * 0.64, y + s * 0.5)
        path.lineTo(x + s * 0.40, y + s * 0.75)
        painter.drawPath(path)
    elif kind == "back":
        path = QPainterPath()
        path.moveTo(x + s * 0.60, y + s * 0.25)
        path.lineTo(x + s * 0.36, y + s * 0.5)
        path.lineTo(x + s * 0.60, y + s * 0.75)
        painter.drawPath(path)
    elif kind == "shield":
        path = QPainterPath()
        path.moveTo(cx, y + s * 0.12)
        path.lineTo(x + s * 0.80, y + s * 0.28)
        path.lineTo(x + s * 0.76, y + s * 0.57)
        path.quadTo(x + s * 0.70, y + s * 0.82, cx, y + s * 0.90)
        path.quadTo(x + s * 0.30, y + s * 0.82, x + s * 0.24, y + s * 0.57)
        path.lineTo(x + s * 0.20, y + s * 0.28)
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == "check":
        path = QPainterPath()
        path.moveTo(x + s * 0.22, y + s * 0.53)
        path.lineTo(x + s * 0.43, y + s * 0.72)
        path.lineTo(x + s * 0.79, y + s * 0.30)
        painter.drawPath(path)
    elif kind == "trash":
        L(x + s * 0.22, y + s * 0.30, x + s * 0.78, y + s * 0.30)
        L(x + s * 0.38, y + s * 0.22, x + s * 0.62, y + s * 0.22)
        path = QPainterPath()
        path.moveTo(x + s * 0.29, y + s * 0.34)
        path.lineTo(x + s * 0.35, y + s * 0.84)
        path.lineTo(x + s * 0.65, y + s * 0.84)
        path.lineTo(x + s * 0.71, y + s * 0.34)
        painter.drawPath(path)
        L(x + s * 0.44, y + s * 0.45, x + s * 0.44, y + s * 0.72)
        L(x + s * 0.56, y + s * 0.45, x + s * 0.56, y + s * 0.72)
    elif kind == "folder":
        path = QPainterPath()
        path.moveTo(x + s * 0.14, y + s * 0.34)
        path.lineTo(x + s * 0.14, y + s * 0.75)
        path.quadTo(x + s * 0.14, y + s * 0.82, x + s * 0.22, y + s * 0.82)
        path.lineTo(x + s * 0.78, y + s * 0.82)
        path.quadTo(x + s * 0.86, y + s * 0.82, x + s * 0.86, y + s * 0.72)
        path.lineTo(x + s * 0.86, y + s * 0.40)
        path.quadTo(x + s * 0.86, y + s * 0.32, x + s * 0.77, y + s * 0.32)
        path.lineTo(x + s * 0.50, y + s * 0.32)
        path.lineTo(x + s * 0.40, y + s * 0.22)
        path.lineTo(x + s * 0.23, y + s * 0.22)
        path.quadTo(x + s * 0.14, y + s * 0.22, x + s * 0.14, y + s * 0.34)
        painter.drawPath(path)
    elif kind == "database":
        R(x + s * 0.20, y + s * 0.20, s * 0.60, s * 0.60, s * 0.28)
        L(x + s * 0.32, y + s * 0.46, x + s * 0.68, y + s * 0.46)
        L(x + s * 0.32, y + s * 0.60, x + s * 0.68, y + s * 0.60)
    elif kind == "terminal":
        R(x + s * 0.13, y + s * 0.20, s * 0.74, s * 0.60, 5)
        path = QPainterPath()
        path.moveTo(x + s * 0.28, y + s * 0.40)
        path.lineTo(x + s * 0.40, y + s * 0.50)
        path.lineTo(x + s * 0.28, y + s * 0.60)
        painter.drawPath(path)
        L(x + s * 0.50, y + s * 0.62, x + s * 0.68, y + s * 0.62)
    elif kind == "lock":
        R(x + s * 0.24, y + s * 0.45, s * 0.52, s * 0.40, 4)
        painter.drawArc(QRectF(x + s * 0.33, y + s * 0.20, s * 0.34, s * 0.44), 0, 180 * 16)
    elif kind == "warning":
        path = QPainterPath()
        path.moveTo(cx, y + s * 0.14)
        path.lineTo(x + s * 0.90, y + s * 0.84)
        path.lineTo(x + s * 0.10, y + s * 0.84)
        path.closeSubpath()
        painter.drawPath(path)
        L(cx, y + s * 0.38, cx, y + s * 0.60)
        painter.drawPoint(QPointF(cx, y + s * 0.70))
    elif kind == "cpu":
        R(x + s * 0.25, y + s * 0.25, s * 0.50, s * 0.50, 4)
        R(x + s * 0.38, y + s * 0.38, s * 0.24, s * 0.24, 2)
        for v in (0.38, 0.50, 0.62):
            L(x + s * v, y + s * 0.12, x + s * v, y + s * 0.25)
            L(x + s * v, y + s * 0.75, x + s * v, y + s * 0.88)
            L(x + s * 0.12, y + s * v, x + s * 0.25, y + s * v)
            L(x + s * 0.75, y + s * v, x + s * 0.88, y + s * v)
    elif kind == "external":
        L(x + s * 0.28, y + s * 0.72, x + s * 0.72, y + s * 0.28)
        L(x + s * 0.48, y + s * 0.28, x + s * 0.72, y + s * 0.28)
        L(x + s * 0.72, y + s * 0.28, x + s * 0.72, y + s * 0.52)
    elif kind == "plus":
        L(cx, y + s * 0.24, cx, y + s * 0.76)
        L(x + s * 0.24, cy, x + s * 0.76, cy)
    elif kind == "broom":
        L(x + s * 0.30, y + s * 0.70, x + s * 0.67, y + s * 0.24)
        path = QPainterPath()
        path.moveTo(x + s * 0.30, y + s * 0.64)
        path.lineTo(x + s * 0.20, y + s * 0.82)
        path.lineTo(x + s * 0.40, y + s * 0.76)
        path.closeSubpath()
        painter.drawPath(path)
        L(x + s * 0.16, y + s * 0.86, x + s * 0.30, y + s * 0.78)
    elif kind == "info":
        painter.drawEllipse(QRectF(x + s * 0.26, y + s * 0.26, s * 0.48, s * 0.48))
        L(cx, cy + s * 0.02, cx, cy + s * 0.22)
        L(cx, cy - s * 0.20, cx, cy - s * 0.18)
    elif kind == "leaf":
        path = QPainterPath()
        path.moveTo(x + s * 0.20, y + s * 0.80)
        path.quadTo(x + s * 0.18, y + s * 0.20, x + s * 0.82, y + s * 0.18)
        path.quadTo(x + s * 0.82, y + s * 0.80, x + s * 0.20, y + s * 0.80)
        painter.drawPath(path)
        L(x + s * 0.32, y + s * 0.68, x + s * 0.68, y + s * 0.32)
    else:
        painter.drawEllipse(QRectF(x + s * 0.25, y + s * 0.25, s * 0.5, s * 0.5))
    painter.restore()


def draw_paw(painter: QPainter, rect: QRectF, color: QColor) -> None:
    """Small paw stamp, used only for quarantined material."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    s = min(rect.width(), rect.height())
    x, y = rect.left(), rect.top()
    painter.drawEllipse(QRectF(x + s * 0.30, y + s * 0.44, s * 0.40, s * 0.30))
    painter.drawEllipse(QRectF(x + s * 0.16, y + s * 0.28, s * 0.18, s * 0.20))
    painter.drawEllipse(QRectF(x + s * 0.41, y + s * 0.16, s * 0.18, s * 0.22))
    painter.drawEllipse(QRectF(x + s * 0.66, y + s * 0.26, s * 0.18, s * 0.20))
    painter.restore()
