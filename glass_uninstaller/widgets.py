"""Instrument-panel widgets for Miaomiao."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve, QElapsedTimer, QPoint, QPointF, QPropertyAnimation, QRect,
    QRectF, QSize, Qt, QTimer, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QAbstractButton, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QSizePolicy, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QVBoxLayout,
    QWidget,
)

from . import theme
from .backend import AppInfo, ResidualItem, human_size


# ---------------------------------------------------------------------------
# Surfaces
# ---------------------------------------------------------------------------

class GlassPanel(QWidget):
    def __init__(self, parent=None, radius: int = 24, tint: QColor | None = None,
                 fill: float = 1.0, shadow: bool = False, backdrop: int = 0) -> None:
        super().__init__(parent)
        self.radius = radius
        self.tint = tint
        self.fill = fill
        self.with_shadow = shadow
        self.backdrop = backdrop
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        if shadow:
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(30)
            effect.setOffset(0, 8)
            effect.setColor(QColor(52, 63, 79, 48))
            self.setGraphicsEffect(effect)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self.backdrop:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(7, 9, 18, self.backdrop))
            p.drawRoundedRect(rect, self.radius, self.radius)
        theme.paint_glass(p, rect, self.radius, self.tint, fill=self.fill,
                          shadow=self.with_shadow)


class AmbientBackground(QWidget):
    """Flat, cold instrument backing; intentionally motionless."""

    def __init__(self, parent=None, radius: int = 0) -> None:
        super().__init__(parent)
        self.radius = radius
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def stop_animation(self) -> None:
        pass

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect())
        clip = theme.rounded_path(r, self.radius)
        p.setClipPath(clip)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0.0, QColor("#F1F3F6"))
        g.setColorAt(1.0, QColor("#E9EDF1"))
        p.fillRect(r, g)

# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------

class IconButton(QAbstractButton):
    def __init__(self, kind: str, size: int = 38, tooltip: str = "",
                 parent=None, color: QColor = theme.TEXT_SOFT) -> None:
        super().__init__(parent)
        self.kind = kind
        self._size = size
        self._hover = 0.0
        self.color = color
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_hover(self) -> float:
        return self._hover

    def set_hover(self, value: float) -> None:
        self._hover = value
        self.update()

    hover = pyqtProperty(float, get_hover, set_hover)

    def enterEvent(self, e) -> None:
        self._anim.stop(); self._anim.setEndValue(1.0); self._anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._anim.stop(); self._anim.setEndValue(0.0); self._anim.start()
        super().leaveEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.7, 0.7, -0.7, -0.7)
        if self._hover > 0.01:
            theme.paint_glass(p, r, 6, hover=self._hover, fill=1.0)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(Qt.PenStyle.NoPen)
        color = QColor(self.color)
        if not self.isEnabled():
            color.setAlpha(80)
        theme.draw_icon(p, self.kind, QRectF(self.rect()).adjusted(
            self._size * 0.29, self._size * 0.29, -self._size * 0.29, -self._size * 0.29),
            color, 1.5)


class WindowButton(QAbstractButton):
    def __init__(self, kind: str, parent=None) -> None:
        super().__init__(parent)
        self.kind = kind
        self._hover = 0.0
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(150)

    def get_hover(self): return self._hover
    def set_hover(self, v):
        self._hover = v; self.update()
    hover = pyqtProperty(float, get_hover, set_hover)

    def enterEvent(self, e):
        self._anim.stop(); self._anim.setEndValue(1.0); self._anim.start(); super().enterEvent(e)
    def leaveEvent(self, e):
        self._anim.stop(); self._anim.setEndValue(0.0); self._anim.start(); super().leaveEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if self._hover > 0:
            if self.kind == "close":
                c = QColor(166, 94, 105, int(120 + 90 * self._hover))
            else:
                c = QColor(26, 29, 35, int(12 + 16 * self._hover))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawEllipse(r)
        col = QColor(theme.TEXT_SOFT)
        if self.kind == "close" and self._hover > 0.2:
            col = QColor("#FFFFFF")
        theme.draw_icon(p, self.kind, QRectF(self.rect()).adjusted(7, 7, -7, -7), col, 1.8)


class GlassButton(QAbstractButton):
    VARIANTS = ("primary", "secondary", "danger", "danger_ghost", "ghost", "soft")

    def __init__(self, text: str, variant: str = "secondary", icon: str = "",
                 parent=None, height: int = 40, radius: int = 8) -> None:
        super().__init__(parent)
        self.setText(text)
        self.variant = variant
        self.icon_kind = icon
        self._hover = 0.0
        self._pressed = False
        self.btn_height = height
        self.radius = radius
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(height)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_hover(self): return self._hover
    def set_hover(self, v):
        self._hover = v; self.update()
    hover = pyqtProperty(float, get_hover, set_hover)

    def enterEvent(self, e):
        if self.isEnabled():
            self._anim.stop(); self._anim.setEndValue(1.0); self._anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._anim.stop(); self._anim.setEndValue(0.0); self._anim.start()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self._pressed = True; self.update(); super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._pressed = False; self.update(); super().mouseReleaseEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.6, 0.6, -0.6, -0.6)
        if self._pressed:
            c = r.center()
            p.translate(c)
            p.scale(0.98, 0.98)
            p.translate(-c)
        enabled = self.isEnabled()
        hover = self._hover if enabled else 0.0
        path = theme.rounded_path(r, self.radius)

        if self.variant == "primary":
            base = QColor("#1B222A") if enabled else QColor("#E5E9ED")
            if enabled and hover > 0:
                base = QColor("#252F39")
            if enabled and self._pressed:
                base = QColor("#10151A")
            p.fillPath(path, base)
            p.setPen(QPen(QColor(255, 255, 255, 18), 1))
            p.drawPath(path)
            text_color = QColor("#F7F9FA") if enabled else QColor("#8D97A1")
        elif self.variant == "danger":
            base = QColor("#8B3F47") if enabled else QColor("#E7E9EB")
            if enabled and hover > 0:
                base = QColor("#9A4A52")
            if enabled and self._pressed:
                base = QColor("#74343B")
            p.fillPath(path, base)
            p.setPen(QPen(QColor(255, 255, 255, 16), 1))
            p.drawPath(path)
            text_color = QColor("#FFFFFF") if enabled else QColor("#8D97A1")
        elif self.variant == "danger_ghost":
            if hover > 0:
                p.fillPath(path, QColor(139, 63, 71, int(10 + 12 * hover)))
                p.setPen(QPen(QColor(139, 63, 71, 48), 1))
                p.drawPath(path)
            text_color = QColor(theme.DANGER) if enabled else QColor("#A5ADB5")
        elif self.variant == "ghost":
            if hover > 0:
                p.fillPath(path, QColor(17, 22, 28, int(6 + 6 * hover)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawPath(path)
            text_color = QColor(theme.TEXT_SOFT) if enabled else QColor(17, 22, 28, 72)
        elif self.variant == "soft":
            p.fillPath(path, QColor("#E7EDF2") if enabled else QColor("#F1F3F5"))
            p.setPen(QPen(theme.HAIRLINE, 1))
            p.drawPath(path)
            text_color = QColor(theme.TEXT) if enabled else QColor(17, 22, 28, 72)
        else:
            p.fillPath(path, QColor(theme.RAISED) if enabled else QColor("#F3F5F7"))
            p.setPen(QPen(theme.HAIRLINE, 1))
            p.drawPath(path)
            text_color = QColor(theme.TEXT) if enabled else QColor(17, 22, 28, 72)

        f = theme.font(13, 500)
        p.setFont(f)
        fm = QFontMetrics(f)
        text = fm.elidedText(self.text(), Qt.TextElideMode.ElideRight,
                             int(r.width() - 32 - (26 if self.icon_kind else 0)))
        tw = fm.horizontalAdvance(text)
        iw = 16 if self.icon_kind else 0
        gap = 8 if self.icon_kind else 0
        total = tw + iw + gap
        start = r.center().x() - total / 2
        if self.icon_kind:
            ic = QColor(text_color)
            ic.setAlpha(225)
            theme.draw_icon(p, self.icon_kind,
                            QRectF(start, r.center().y() - 8, 16, 16), ic, 1.5)
        p.setPen(text_color)
        p.drawText(QRectF(start + iw + gap, r.top(), tw + 4, r.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(theme.ACCENT, 1.2))
            p.drawRoundedRect(r.adjusted(1.2, 1.2, -1.2, -1.2), max(4, self.radius - 1),
                              max(4, self.radius - 1))


class PillButton(QAbstractButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        self.setMinimumWidth(56)
        self._hover = 0.0
        self._select = 0.0
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(140)
        self._select_anim = QPropertyAnimation(self, b"select", self)
        self._select_anim.setDuration(140)
        self._select_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_hover(self): return self._hover
    def set_hover(self, v):
        self._hover = v; self.update()
    hover = pyqtProperty(float, get_hover, set_hover)

    def enterEvent(self, e):
        self._anim.stop(); self._anim.setEndValue(1.0); self._anim.start(); super().enterEvent(e)
    def leaveEvent(self, e):
        self._anim.stop(); self._anim.setEndValue(0.0); self._anim.start(); super().leaveEvent(e)
    def get_select(self): return self._select
    def set_select(self, value):
        self._select = max(0.0, min(1.0, value)); self.update()
    select = pyqtProperty(float, get_select, set_select)

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        if hasattr(self, "_select_anim"):
            self._select_anim.stop()
            self._select_anim.setEndValue(1.0 if checked else 0.0)
            self._select_anim.start()

    def sizeHint(self):
        fm = QFontMetrics(theme.font(12, 500))
        return QSize(fm.horizontalAdvance(self.text()) + 24, 32)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.6, 0.6, -0.6, -0.6)
        sel = self._select
        if sel > 0.01:
            p.setBrush(QColor(229, 236, 242, int(255 * sel)))
            p.setPen(QPen(theme.HAIRLINE, 1))
            p.drawRoundedRect(r, 6, 6)
        elif self._hover > 0:
            p.setBrush(QColor(245, 247, 249, int(255 * self._hover)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, 6, 6)
        p.setFont(theme.font(12, 500))
        p.setPen(QColor(theme.TEXT) if sel > 0.5 else QColor(theme.TEXT_MUTED))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.text())

class NavButton(QAbstractButton):
    def __init__(self, text: str, kind: str, parent=None, fluid: bool = False) -> None:
        super().__init__(parent)
        self.setText(text)
        self.kind = kind
        self.fluid = fluid
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(36)
        self._hover = 0.0
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_hover(self): return self._hover
    def set_hover(self, v):
        self._hover = v; self.update()
    hover = pyqtProperty(float, get_hover, set_hover)

    def enterEvent(self, e):
        self._anim.stop(); self._anim.setEndValue(1.0); self._anim.start(); super().enterEvent(e)
    def leaveEvent(self, e):
        self._anim.stop(); self._anim.setEndValue(0.0); self._anim.start(); super().leaveEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.6, 0.6, -0.6, -0.6)
        if self.isChecked():
            p.setBrush(QColor(theme.ACTIVE))
            p.setPen(QPen(theme.HAIRLINE, 1))
            p.drawRoundedRect(r, 8, 8)
        elif self._hover > 0:
            p.setBrush(QColor(17, 22, 28, int(5 * self._hover)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, 8, 8)
        col = QColor(theme.TEXT) if self.isChecked() else QColor(theme.TEXT_MUTED)
        theme.draw_icon(p, self.kind, QRectF(r.left() + 14, r.center().y() - 9, 18, 18), col, 1.5)
        p.setFont(theme.font(14, 500))
        p.setPen(col)
        p.drawText(QRectF(r.left() + 42, r.top(), r.width() - 50, r.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

class SearchBox(QWidget):
    textChanged = pyqtSignal(str)

    def __init__(self, placeholder: str, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setMinimumWidth(220)
        self._focus = 0.0
        self._placeholder = placeholder
        self.edit = QLineEdit(self)
        self.edit.setAccessibleName(placeholder)
        self.edit.setPlaceholderText("")
        self.edit.setFont(theme.font(13, 400))
        self.edit.setTextMargins(32, 0, 12, 0)
        self.edit.setStyleSheet("""
            QLineEdit { background: transparent; border: none; color: #11161C;
                        selection-background-color: rgba(49,93,120,70); }
            QLineEdit::placeholder { color: #98A1AB; }
        """)
        self.edit.textChanged.connect(self.textChanged)
        self.edit.installEventFilter(self)
        self._anim = QPropertyAnimation(self, b"focus", self)
        self._anim.setDuration(140)

    def get_focus(self): return self._focus
    def set_focus(self, v):
        self._focus = v; self.update()
    focus = pyqtProperty(float, get_focus, set_focus)

    def eventFilter(self, obj, event):
        if obj is self.edit:
            if event.type() == event.Type.FocusIn:
                self._anim.stop(); self._anim.setEndValue(1.0); self._anim.start()
            elif event.type() == event.Type.FocusOut:
                self._anim.stop(); self._anim.setEndValue(0.0); self._anim.start()
        return super().eventFilter(obj, event)

    def resizeEvent(self, e):
        self.edit.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.6, 0.6, -0.6, -0.6)
        p.setBrush(QColor(theme.RAISED))
        base = QColor(17, 22, 28, 24)
        focus = QColor(theme.ACCENT)
        mix = QColor(
            int(base.red() + (focus.red() - base.red()) * self._focus),
            int(base.green() + (focus.green() - base.green()) * self._focus),
            int(base.blue() + (focus.blue() - base.blue()) * self._focus),
            int(24 + (255 - 24) * self._focus),
        )
        p.setPen(QPen(mix, 1.0 + 0.3 * self._focus))
        p.drawRoundedRect(r, 8, 8)
        theme.draw_icon(p, "search", QRectF(11, r.center().y() - 8, 16, 16),
                        QColor(theme.TEXT_MUTED), 1.5)
        if not self.edit.hasFocus() and not self.edit.text():
            p.setFont(theme.font(13, 400))
            p.setPen(QColor(theme.TEXT_DIM))
            p.drawText(QRectF(32, 0, self.width() - 44, self.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       self._placeholder)


class GlassToggle(QAbstractButton):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(36, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._knob = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def get_knob(self): return self._knob
    def set_knob(self, v):
        self._knob = max(0.0, min(1.0, v)); self.update()
    knob = pyqtProperty(float, get_knob, set_knob)

    def _animate(self, checked):
        self._anim.stop()
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.8, 0.8, -0.8, -0.8)
        p.setPen(QPen(theme.HAIRLINE, 1))
        p.setBrush(QColor(theme.ACCENT) if self._knob > 0.5 else QColor("#D6DCE2"))
        p.drawRoundedRect(r, 9, 9)
        x = r.left() + 2 + self._knob * (r.width() - 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, r.top() + 2, 14, 14))


class GlassCheck(QAbstractButton):
    def __init__(self, parent=None, accent: QColor | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.accent = accent or theme.ACCENT
        self._check = 0.0
        self._check_anim = QPropertyAnimation(self, b"check", self)
        self._check_anim.setDuration(120)
        self._check_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate_check)

    def get_check(self): return self._check
    def set_check(self, value):
        self._check = max(0.0, min(1.0, value)); self.update()
    check = pyqtProperty(float, get_check, set_check)

    def _animate_check(self, checked: bool) -> None:
        self._check_anim.stop()
        self._check_anim.setEndValue(1.0 if checked else 0.0)
        self._check_anim.start()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.8, 0.8, -0.8, -0.8)
        progress = self._check
        if progress > 0.01:
            p.setBrush(QColor(self.accent))
            p.setPen(QPen(QColor(self.accent).darker(115), 1))
            p.drawRoundedRect(r, 4, 4)
            p.setOpacity(progress)
            theme.draw_icon(p, "check", r.adjusted(2.4, 2.4, -2.4, -2.4),
                            QColor("#FFFFFF"), 1.8)
            p.setOpacity(1.0)
        else:
            p.setBrush(QColor(theme.CARD))
            p.setPen(QPen(QColor(17, 22, 28, 55), 1))
            p.drawRoundedRect(r, 4, 4)


class SegmentedControl(QWidget):
    changed = pyqtSignal(int)

    def __init__(self, options: list[tuple[str, str]], parent=None) -> None:
        super().__init__(parent)
        self.options = options
        self.index = 0
        self._pos = 0.0
        self.setFixedHeight(36)
        self.setMinimumWidth(240)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_pos(self): return self._pos
    def set_pos(self, v):
        self._pos = v; self.update()
    pos = pyqtProperty(float, get_pos, set_pos)

    def set_index(self, index: int, emit: bool = True) -> None:
        if not 0 <= index < len(self.options):
            return
        self.index = index
        self._anim.stop(); self._anim.setEndValue(float(index)); self._anim.start()
        if emit:
            self.changed.emit(index)
        self.update()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            seg = (self.width() - 8) / len(self.options)
            idx = int((e.position().x() - 4) // seg)
            idx = max(0, min(len(self.options) - 1, idx))
            self.set_index(idx)
        super().mouseReleaseEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.7, 0.7, -0.7, -0.7)
        p.setBrush(QColor(theme.RAISED))
        p.setPen(QPen(theme.HAIRLINE, 1))
        p.drawRoundedRect(r, 8, 8)
        seg = (r.width() - 8) / len(self.options)
        x = r.left() + 4 + self._pos * seg
        ir = QRectF(x, r.top() + 4, seg, r.height() - 8)
        p.setPen(QPen(theme.HAIRLINE, 1))
        p.setBrush(QColor(theme.CARD))
        p.drawRoundedRect(ir, 6, 6)
        p.setFont(theme.font(12, 500))
        for i, (_, label) in enumerate(self.options):
            cr = QRectF(r.left() + 4 + i * seg, r.top() + 4, seg, r.height() - 8)
            p.setPen(QColor(theme.TEXT) if i == self.index else QColor(theme.TEXT_MUTED))
            p.drawText(cr, Qt.AlignmentFlag.AlignCenter, label)


# ---------------------------------------------------------------------------
# Small labels / badges
# ---------------------------------------------------------------------------

class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent=None, color: QColor = theme.TEXT,
                 size: int = 13, weight: int = 400) -> None:
        super().__init__(text, parent)
        self.full_text = text
        self.label_color = QColor(color)
        self.setFont(theme.font(size, weight))
        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:
        self.full_text = text
        super().setText(text)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setFont(self.font())
        p.setPen(self.label_color)
        fm = QFontMetrics(self.font())
        text = fm.elidedText(self.full_text, Qt.TextElideMode.ElideMiddle, self.width())
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)


def make_badge(painter: QPainter, rect: QRectF, text: str, color: QColor,
               size: int = 11, alpha: int = 24) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setFont(theme.font(size, 500))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(QRectF(rect.left(), rect.center().y() - 2, 4, 4))
    painter.setPen(QColor(theme.TEXT_MUTED))
    painter.drawText(QRectF(rect.left() + 10, rect.top(), rect.width() - 10, rect.height()),
                     Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
    painter.restore()

def make_chip(painter: QPainter, rect: QRectF, label: str, value: str,
              icon: str = "") -> None:
    theme.paint_glass(painter, rect, 8, fill=1.0)
    x = rect.left() + 12
    if icon:
        theme.draw_icon(painter, icon, QRectF(x, rect.center().y() - 8, 16, 16),
                        QColor(theme.TEXT_MUTED), 1.5)
        x += 22
    painter.setFont(theme.font(10, 500))
    painter.setPen(QColor(theme.TEXT_MUTED))
    painter.drawText(QRectF(x, rect.top() + 7, rect.width() - 16, 14),
                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
    painter.setFont(theme.mono_font(13, 500))
    painter.setPen(QColor(theme.TEXT))
    painter.drawText(QRectF(x, rect.top() + 20, rect.width() - 16, 16),
                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, value)


# ---------------------------------------------------------------------------
# Icons
# ---------------------------------------------------------------------------

class IconProvider:
    def __init__(self) -> None:
        self._cache: dict[str, QPixmap] = {}

    @staticmethod
    def _fallback(app: AppInfo, size: int) -> QPixmap:
        seed = int(hashlib.sha1(app.id.encode()).hexdigest()[:8], 16)
        hues = [(215, 70), (168, 60), (265, 55), (330, 55), (30, 65), (190, 60)]
        h, s = hues[seed % len(hues)]
        pix = QPixmap(size * 2, size * 2)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(2, 2, size * 2 - 4, size * 2 - 4)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor.fromHsl(h, min(255, s * 3), 158))
        g.setColorAt(1, QColor.fromHsl((h + 25) % 360, min(255, s * 3), 92))
        p.setPen(QPen(QColor(255, 255, 255, 70), 2))
        p.setBrush(g)
        p.drawRoundedRect(r, size * 0.48, size * 0.48)
        letter = (app.name or "?").strip()[:1].upper()
        p.setFont(theme.font(max(12, int(size * 1.12)), 700, display=True))
        p.setPen(QColor(255, 255, 255, 235))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, letter)
        p.end()
        pix.setDevicePixelRatio(2)
        return pix

    def get(self, app: AppInfo, size: int = 42) -> QPixmap:
        key = f"{app.id}|{app.icon}|{size}"
        if key in self._cache:
            return self._cache[key]
        source: QPixmap | None = None
        icon = (app.icon or "").strip()
        if icon and Path(icon).expanduser().exists() and Path(icon).is_file():
            source = QPixmap(str(Path(icon).expanduser()))
        elif icon:
            qi = QIcon.fromTheme(icon)
            if not qi.isNull():
                source = qi.pixmap(QSize(size * 2, size * 2))
        if source is None or source.isNull():
            pix = self._fallback(app, size)
        else:
            source = source.scaled(size * 2, size * 2, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                   Qt.TransformationMode.SmoothTransformation)
            canvas = QPixmap(size * 2, size * 2)
            canvas.fill(Qt.GlobalColor.transparent)
            p = QPainter(canvas)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, size * 2, size * 2), size * 0.44, size * 0.44)
            p.setClipPath(path)
            sx = max(0, (source.width() - size * 2) // 2)
            sy = max(0, (source.height() - size * 2) // 2)
            p.drawPixmap(-sx, -sy, source)
            p.setClipping(False)
            p.setPen(QPen(QColor(255, 255, 255, 55), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(1, 1, size * 2 - 2, size * 2 - 2),
                              size * 0.44, size * 0.44)
            p.end()
            canvas.setDevicePixelRatio(2)
            pix = canvas
        self._cache[key] = pix
        return pix


def draw_app_icon(painter: QPainter, provider: IconProvider, app: AppInfo,
                  rect: QRectF, size: int = 44) -> None:
    pix = provider.get(app, size)
    painter.drawPixmap(rect.toRect(), pix)


# ---------------------------------------------------------------------------
# App list
# ---------------------------------------------------------------------------

APP_ROLE = Qt.ItemDataRole.UserRole + 10


class AppDelegate(QStyledItemDelegate):
    def __init__(self, provider: IconProvider, catalog_lookup, parent=None) -> None:
        super().__init__(parent)
        self.provider = provider
        self.lookup = catalog_lookup

    def sizeHint(self, option, index) -> QSize:
        return QSize(100, 64)

    def paint(self, p: QPainter, option: QStyleOptionViewItem, index) -> None:
        app = self.lookup(index.data(APP_ROLE))
        if app is None:
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(option.rect).adjusted(2, 2, -2, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected:
            p.setPen(QPen(theme.HAIRLINE, 1))
            p.setBrush(QColor(theme.ACTIVE))
            p.drawRoundedRect(r, 8, 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.ACCENT))
            p.drawRect(QRectF(r.left(), r.top() + 8, 2, r.height() - 16))
        elif hover:
            p.setBrush(QColor(theme.RAISED))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, 8, 8)
        icon_rect = QRectF(r.left() + 10, r.top() + 13, 36, 36)
        draw_app_icon(p, self.provider, app, icon_rect, 36)
        x = icon_rect.right() + 12
        p.setFont(theme.font(14, 500))
        p.setPen(QColor(theme.TEXT))
        fm = QFontMetrics(p.font())
        right_pad = 70
        name = fm.elidedText(app.name, Qt.TextElideMode.ElideRight,
                             int(r.right() - x - right_pad))
        p.drawText(QRectF(x, r.top() + 11, r.right() - x - right_pad, 20),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)
        p.setFont(theme.font(11, 400))
        p.setPen(QColor(theme.TEXT_MUTED))
        sub = app.package if app.source != "本地" else "用户安装"
        sub = QFontMetrics(p.font()).elidedText(f"{app.source}  ·  {sub}",
                                                Qt.TextElideMode.ElideRight,
                                                int(r.right() - x - right_pad))
        p.drawText(QRectF(x, r.top() + 34, r.right() - x - right_pad, 16),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, sub)
        p.setFont(theme.mono_font(11, 500))
        p.setPen(QColor(theme.TEXT_MUTED))
        p.drawText(QRectF(r.right() - 74, r.top() + 12, 58, 16),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   human_size(app.size))
        theme.draw_icon(p, "chevron", QRectF(r.right() - 16, r.center().y() - 6, 12, 12),
                        QColor(theme.TEXT_DIM), 1.5)
        if app.protected:
            theme.draw_icon(p, "lock", QRectF(r.right() - 68, r.top() + 36, 11, 11),
                            QColor(theme.AMBER), 1.3)
        p.restore()


class AppList(QListWidget):
    def __init__(self, provider: IconProvider, lookup, parent=None) -> None:
        super().__init__(parent)
        self.provider = provider
        self.lookup = lookup
        self.setItemDelegate(AppDelegate(provider, lookup, self))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUniformItemSizes(True)
        self.setSpacing(0)
        self.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 7px; margin: 6px 1px 6px 1px; }
            QScrollBar::handle:vertical { background: rgba(17,22,28,34); min-height: 32px;
                                          border-radius: 3px; }
            QScrollBar::handle:vertical:hover { background: rgba(17,22,28,58); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        self.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 2px; }
            QScrollBar::handle:vertical { background: #B5BEC7; min-height: 32px; border-radius: 3px; }
            QScrollBar::handle:vertical:hover { background: #8E99A3; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

    def set_apps(self, apps: list[AppInfo]) -> None:
        selected = self.current_app_id()
        self.clear()
        for app in apps:
            item = QListWidgetItem()
            item.setData(APP_ROLE, app.id)
            item.setSizeHint(QSize(100, 64))
            item.setToolTip(f"{app.name}\n{app.package}\n{app.source} · {human_size(app.size)}")
            self.addItem(item)
        if selected:
            for i in range(self.count()):
                if self.item(i).data(APP_ROLE) == selected:
                    self.setCurrentRow(i)
                    break

    def current_app_id(self) -> str:
        item = self.currentItem()
        return item.data(APP_ROLE) if item else ""


# ---------------------------------------------------------------------------
# Residual / history widgets
# ---------------------------------------------------------------------------

class ResidualRow(QWidget):
    changed = pyqtSignal()

    def __init__(self, item: ResidualItem, parent=None) -> None:
        super().__init__(parent)
        self.item = item
        self._hover = False
        self.setFixedHeight(56)
        self.setToolTip(f"{item.reason}\n{item.path}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check = GlassCheck(self)
        self.check.move(12, 20)
        self.check.setChecked(item.selected)
        self.check.toggled.connect(self._on_toggle)
        self.setMouseTracking(True)

    def _on_toggle(self, checked: bool) -> None:
        self.item.selected = checked
        self.update()
        self.changed.emit()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.check.toggle()
        super().mouseReleaseEvent(e)

    def enterEvent(self, e):
        self._hover = True; self.update(); super().enterEvent(e)
    def leaveEvent(self, e):
        self._hover = False; self.update(); super().leaveEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if self.item.selected:
            p.setBrush(QColor(theme.ACTIVE))
            p.setPen(QPen(theme.HAIRLINE, 1))
            p.drawRoundedRect(r, 6, 6)
        elif self._hover:
            p.setBrush(QColor(theme.RAISED))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, 6, 6)
        theme.draw_icon(p, "database" if self.item.kind == "dir" else "terminal",
                        QRectF(38, r.center().y() - 8, 16, 16), QColor(theme.TEXT_MUTED), 1.5)
        p.setFont(theme.font(12, 500))
        p.setPen(QColor(theme.TEXT))
        name = QFontMetrics(p.font()).elidedText(self.item.name, Qt.TextElideMode.ElideRight,
                                                 int(self.width() * 0.34))
        p.drawText(QRectF(64, r.top() + 8, self.width() * 0.38, 18),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)
        p.setFont(theme.mono_font(10, 400))
        p.setPen(QColor(theme.TEXT_DIM))
        path = QFontMetrics(p.font()).elidedText(self.item.path, Qt.TextElideMode.ElideMiddle,
                                                 int(self.width() * 0.52))
        p.drawText(QRectF(64, r.top() + 28, self.width() * 0.54, 16),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, path)
        badge_col = theme.SUCCESS if self.item.safety == "safe" else theme.AMBER
        label = "可清理" if self.item.safety == "safe" else "需确认"
        make_badge(p, QRectF(self.width() - 150, r.center().y() - 9, 64, 18),
                   label, badge_col, 11, 22)
        p.setFont(theme.mono_font(11, 500))
        p.setPen(QColor(theme.TEXT_MUTED))
        p.drawText(QRectF(self.width() - 78, r.center().y() - 9, 68, 18),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   human_size(self.item.size))


class StatCard(QWidget):
    def __init__(self, label: str, value: str, icon: str, color: QColor, parent=None) -> None:
        super().__init__(parent)
        self.label, self.value, self.icon, self.color = label, value, icon, color
        self.setMinimumHeight(62)

    def set_value(self, value: str) -> None:
        self.value = value; self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        theme.paint_glass(p, r, 8, fill=1.0)
        p.setFont(theme.font(11, 500))
        p.setPen(QColor(theme.TEXT_MUTED))
        p.drawText(QRectF(r.left() + 12, r.top() + 8, r.width() - 24, 16),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.label)
        p.setFont(theme.mono_font(18, 500))
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(r.left() + 12, r.top() + 26, r.width() - 24, 24),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.value)


class ProgressRing(QWidget):
    def __init__(self, parent=None, size: int = 126) -> None:
        super().__init__(parent)
        self.value = 0
        self._display = 0.0
        self.label = "准备中"
        self.setFixedSize(size, size)
        self._anim = QPropertyAnimation(self, b"display", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_display(self): return self._display
    def set_display(self, value):
        self._display = max(0.0, min(100.0, value)); self.update()
    display = pyqtProperty(float, get_display, set_display)

    def set_progress(self, value: int, label: str = "") -> None:
        self.value = max(0, min(100, value))
        if label:
            self.label = label
        self._anim.stop()
        self._anim.setStartValue(self._display)
        self._anim.setEndValue(float(self.value))
        self._anim.start()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        s = min(self.width(), self.height())
        r = QRectF((self.width() - s) / 2 + 8, (self.height() - s) / 2 + 8, s - 16, s - 16)
        p.setPen(QPen(QColor(31, 39, 50, 26), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(r, 0, 360 * 16)
        if self._display > 0.1:
            p.setPen(QPen(QColor(theme.ACCENT), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(r, 90 * 16, -int(360 * 16 * self._display / 100))
        p.setFont(theme.mono_font(24, 500))
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(0, r.top() + r.height() * 0.32, self.width(), 38),
                   Qt.AlignmentFlag.AlignCenter, f"{int(round(self._display))}%")
        p.setFont(theme.font(10, 500))
        p.setPen(QColor(theme.TEXT_MUTED))
        p.drawText(QRectF(0, r.top() + r.height() * 0.34 + 34, self.width(), 18),
                   Qt.AlignmentFlag.AlignCenter, self.label)


class Toast(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.text = ""
        self.kind = "info"
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedHeight(40)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._show_anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._show_anim.setDuration(150)
        self._show_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_message(self, text: str, kind: str = "info", duration: int = 2800) -> None:
        self.text = text
        self.kind = kind
        fm = QFontMetrics(theme.font(12, 550))
        self.setFixedWidth(min(520, fm.horizontalAdvance(text) + 64))
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(duration)
        self._effect.setOpacity(0.0)
        self._show_anim.stop()
        self._show_anim.setStartValue(0.0)
        self._show_anim.setEndValue(1.0)
        self._show_anim.start()
        self.update()

    def _reposition(self) -> None:
        if self.parentWidget():
            self.move((self.parentWidget().width() - self.width()) // 2, 12)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        theme.paint_glass(p, r, 6, fill=1.0)
        col = {"success": theme.SUCCESS, "error": theme.DANGER}.get(self.kind, theme.ACCENT)
        theme.draw_icon(p, "check" if self.kind == "success" else
                        ("warning" if self.kind == "error" else "info"),
                        QRectF(14, r.center().y() - 8, 16, 16), col, 1.5)
        p.setFont(theme.font(12, 500))
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(38, 0, self.width() - 50, self.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text)


class IntroOverlay(QWidget):
    """Branded opening curtain that fades into the live interface."""

    finished = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.phase = 0.0
        self._opacity = 1.0
        self._fading = False
        self._clock = QElapsedTimer()
        self.pix = QPixmap(str(theme.ASSETS / "icon-256.png"))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._fade = QPropertyAnimation(self, b"opacity", self)
        self._fade.setDuration(420)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._done)
        self.hide()

    def get_opacity(self) -> float:
        return self._opacity

    def set_opacity(self, value: float) -> None:
        self._opacity = value
        self.update()

    opacity = pyqtProperty(float, get_opacity, set_opacity)

    def _tick(self) -> None:
        self.phase = self._clock.elapsed() / 1000.0
        self.update()

    def start(self) -> None:
        self._fading = False
        self._opacity = 1.0
        self.phase = 0.0
        self._clock.start()
        self._timer.start(16)
        self.show()
        self.raise_()

    def stop_animation(self) -> None:
        self._timer.stop()
        self._fade.stop()

    def dismiss(self) -> None:
        if self._fading or not self.isVisible():
            return
        self._fading = True
        self._fade.stop()
        self._fade.setStartValue(self._opacity)
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _done(self) -> None:
        self._timer.stop()
        self._fading = False
        self.hide()
        self.finished.emit()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.dismiss()
        super().mouseReleaseEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setOpacity(self._opacity)
        p.fillRect(self.rect(), QColor(theme.PAGE))
        cx, cy = self.width() / 2, self.height() / 2 - 36

        ir = QRectF(cx - 40, cy - 118, 80, 80)
        p.save()
        p.setClipPath(theme.rounded_path(ir, 18))
        p.drawPixmap(ir.toRect(), self.pix)
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(theme.HAIRLINE, 1))
        p.drawRoundedRect(ir.adjusted(0.5, 0.5, -0.5, -0.5), 18, 18)

        p.setFont(theme.font(28, 500))
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(0, cy - 18, self.width(), 36),
                   Qt.AlignmentFlag.AlignCenter, "喵喵")
        p.setFont(theme.font(12, 400))
        p.setPen(QColor(theme.TEXT_MUTED))
        p.drawText(QRectF(0, cy + 20, self.width(), 20),
                   Qt.AlignmentFlag.AlignCenter, "应用卸载与残留清理")

        p.setFont(theme.font(11, 400))
        p.setPen(QColor(theme.TEXT_DIM))
        p.drawText(QRectF(0, cy + 52, self.width(), 18),
                   Qt.AlignmentFlag.AlignCenter, "读取应用清单")

        track = QRectF(cx - 80, cy + 86, 160, 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(17, 22, 28, 18))
        p.drawRect(track)
        p.setPen(QPen(QColor(17, 22, 28, 30), 1))
        for i in range(5):
            x = track.left() + track.width() * i / 4
            p.drawLine(QPointF(x, track.top() - 2), QPointF(x, track.top() + 3))
        p.setPen(Qt.PenStyle.NoPen)
        pos = (self.phase * 0.24) % 1.0
        x = track.left() + pos * (track.width() - 54)
        p.setBrush(QColor(49, 93, 120, 28))
        p.drawRect(QRectF(x - 20, track.top(), 20, 2))
        p.setBrush(QColor(theme.ACCENT))
        p.drawRect(QRectF(x, track.top(), 54, 2))
        p.drawRect(QRectF(x + 52, track.top() - 3, 2, 8))

        p.setFont(theme.font(10, 400))
        p.setPen(QColor(theme.TEXT_DIM))
        p.drawText(QRectF(0, self.height() - 40, self.width(), 18),
                   Qt.AlignmentFlag.AlignCenter, "点击跳过")


class LoadingOverlay(QWidget):
    """Functional scan overlay used while the package inventory is collected."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.phase = 0.0
        self._opacity = 1.0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.WaitCursor)
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._fade = QPropertyAnimation(self, b"opacity", self)
        self._fade.setDuration(220)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self.hide)
        self.show()

    def get_opacity(self) -> float:
        return self._opacity

    def set_opacity(self, value: float) -> None:
        self._opacity = value
        self.update()

    opacity = pyqtProperty(float, get_opacity, set_opacity)

    def _tick(self) -> None:
        self.phase = self._clock.elapsed() / 1000.0
        self.update()

    def dismiss(self) -> None:
        if not self.isVisible() or self._fade.state() == QPropertyAnimation.State.Running:
            return
        self._fade.stop()
        self._fade.setStartValue(self._opacity)
        self._fade.setEndValue(0.0)
        self._fade.start()

    def stop_animation(self) -> None:
        self._timer.stop()
        self._fade.stop()

    def showEvent(self, e) -> None:
        self._clock.start()
        self._timer.start()
        self.raise_()
        super().showEvent(e)

    def hideEvent(self, e) -> None:
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setOpacity(self._opacity)
        p.fillRect(self.rect(), QColor(237, 240, 243, 238))

        cw, ch = 440, 144
        card = QRectF((self.width() - cw) / 2, (self.height() - ch) / 2, cw, ch)
        theme.paint_glass(p, card, 12, fill=1.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.ACCENT))
        p.drawRect(QRectF(card.left(), card.top() + 16, 2, card.height() - 32))

        p.setFont(theme.font(14, 500))
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(card.left() + 24, card.top() + 22, 260, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "读取应用清单")
        p.setFont(theme.font(11, 400))
        p.setPen(QColor(theme.TEXT_MUTED))
        p.drawText(QRectF(card.left() + 24, card.top() + 46, 300, 18),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "APT · Flatpak · Snap · 本地")
        p.setFont(theme.mono_font(10, 500))
        p.setPen(QColor(theme.TEXT_DIM))
        p.drawText(QRectF(card.left() + 24, card.top() + 70, card.width() - 48, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "读取  /  本地软件包")

        track = QRectF(card.left() + 24, card.top() + 105, card.width() - 48, 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(17, 22, 28, 18))
        p.drawRect(track)
        p.setPen(QPen(QColor(17, 22, 28, 30), 1))
        for i in range(9):
            x = track.left() + track.width() * i / 8
            p.drawLine(QPointF(x, track.top() - 3), QPointF(x, track.top() + 4))

        pos = (self.phase * 0.24) % 1.0
        span = 74.0
        x = track.left() + pos * (track.width() - span)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(49, 93, 120, 28))
        p.drawRect(QRectF(x - 26, track.top(), 26, 2))
        p.setBrush(QColor(49, 93, 120, 60))
        p.drawRect(QRectF(x - 12, track.top(), 12, 2))
        p.setBrush(QColor(theme.ACCENT))
        p.drawRect(QRectF(x, track.top(), span, 2))
        p.drawRect(QRectF(x + span - 2, track.top() - 4, 2, 10))

        p.setFont(theme.mono_font(9, 400))
        p.setPen(QColor(theme.TEXT_DIM))
        for i, label in enumerate(("0", "25", "50", "75", "100")):
            xx = track.left() + track.width() * i / 4
            p.drawText(QRectF(xx - 14, track.top() + 9, 28, 14),
                       Qt.AlignmentFlag.AlignCenter, label)
