"""Page compositions for 喵喵 (Miaomiao)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPixmap, QTextOption
from PyQt6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel,
    QScrollArea, QSizePolicy, QSpacerItem, QStackedWidget, QVBoxLayout, QWidget,
)

from . import theme
from .backend import (
    AppInfo, ProcessInfo, ResidualItem, ScanResult, UninstallOptions, human_size,
)
from .widgets import (
    APP_ROLE, AppList, ElidedLabel, GlassButton, GlassCheck, GlassPanel,
    GlassToggle, IconButton, IconProvider, LoadingOverlay, NavButton, PillButton,
    ResidualRow, SearchBox, SegmentedControl, StatCard, draw_app_icon, make_badge,
)


def section_label(text: str, size: int = 12, color: QColor = theme.TEXT_SOFT) -> QLabel:
    lab = QLabel(text)
    lab.setFont(theme.font(size, 500))
    lab.setStyleSheet(f"color: {color.name()}; background: transparent;")
    return lab


def body_label(text: str, size: int = 12, color: QColor = theme.TEXT_SOFT,
               weight: int = 400) -> QLabel:
    lab = QLabel(text)
    lab.setFont(theme.font(size, weight))
    lab.setWordWrap(True)
    lab.setStyleSheet(f"color: {color.name()}; background: transparent;")
    return lab


def hline() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet("background: rgba(17,22,28,20); border: none;")
    return line


class Badge(QWidget):
    def __init__(self, text: str, color: QColor, parent=None) -> None:
        super().__init__(parent)
        self.text = text
        self.color = QColor(color)
        self.setFixedHeight(18)
        self._resize()

    def set_text(self, text: str, color: QColor | None = None) -> None:
        self.text = text
        if color:
            self.color = QColor(color)
        self._resize()
        self.update()

    def _resize(self) -> None:
        fm = QFontMetrics(theme.font(11, 500))
        self.setFixedWidth(fm.horizontalAdvance(self.text) + 16)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        make_badge(p, QRectF(0, 0, self.width(), self.height()), self.text,
                   self.color, 11, 25)


class InfoCard(QWidget):
    def __init__(self, icon: str, title: str, body: str, color: QColor, parent=None) -> None:
        super().__init__(parent)
        self.icon_kind = icon
        self.color = QColor(color)
        self.title = title
        self.body = body
        self.setMinimumHeight(64)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(16, 10, 16, 10)
        self.layout.setSpacing(10)
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setFont(theme.font(12, 500))
        self.title_label.setStyleSheet(f"color: {self.color.name()}; background: transparent;")
        self.body_label = QLabel(body)
        self.body_label.setFont(theme.font(12, 400))
        self.body_label.setWordWrap(True)
        self.body_label.setStyleSheet(f"color: {theme.TEXT_MUTED.name()}; background: transparent;")
        text_box.addWidget(self.title_label)
        text_box.addWidget(self.body_label)
        self.layout.addLayout(text_box)

    def set_content(self, title: str, body: str, color: QColor | None = None) -> None:
        if color:
            self.color = QColor(color)
            self.title_label.setStyleSheet(f"color: {self.color.name()}; background: transparent;")
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        theme.paint_glass(p, r, 8, fill=1.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.color)
        p.drawRect(QRectF(r.left(), r.top() + 12, 2, r.height() - 24))


class OptionRow(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, title: str, body: str, checked: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(12)
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        self.title = QLabel(title)
        self.title.setFont(theme.font(12, 500))
        self.title.setStyleSheet("color: #11161C; background: transparent;")
        self.sub = QLabel(body)
        self.sub.setFont(theme.font(12, 400))
        self.sub.setStyleSheet("color: #68737F; background: transparent;")
        text_box.addWidget(self.title)
        text_box.addWidget(self.sub)
        self.layout.addLayout(text_box, 1)
        self.toggle = GlassToggle(self)
        self.toggle.setChecked(checked)
        self.toggle.toggled.connect(self.toggled)
        self.layout.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignVCenter)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.toggle.toggle()
        super().mouseReleaseEvent(e)


class EmptyState(QWidget):
    def __init__(self, title: str, body: str, icon: str = "sparkles", parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.body = body
        self.icon_kind = icon
        self.setMinimumHeight(220)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        c = self.rect().center()
        theme.draw_icon(p, self.icon_kind, QRectF(c.x() - 12, c.y() - 66, 24, 24),
                        QColor(theme.TEXT_DIM), 1.5)
        p.setFont(theme.font(16, 500))
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(0, c.y() - 26, self.width(), 28),
                   Qt.AlignmentFlag.AlignCenter, self.title)
        p.setFont(theme.font(12, 400))
        p.setPen(QColor(theme.TEXT_MUTED))
        p.drawText(QRectF(30, c.y() + 8, self.width() - 60, 52),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                   self.body)


class BrandMark(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(48, 48)
        self.pix = QPixmap(str(theme.ASSETS / "icon-256.png"))

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(0, 0, 48, 48)
        p.save()
        path = theme.rounded_path(r, 12)
        p.setClipPath(path)
        p.drawPixmap(r.toRect(), self.pix)
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(theme.HAIRLINE, 1))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)


class Sidebar(QWidget):
    page_requested = pyqtSignal(int)
    self_uninstall_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(240)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(0)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(4, 0, 0, 0)
        brand_row.setSpacing(12)
        brand_row.addWidget(BrandMark())
        names = QVBoxLayout()
        names.setSpacing(2)
        title = QLabel("喵喵")
        title.setFont(theme.font(20, 500, display=True))
        title.setStyleSheet("color: #11161C; background: transparent;")
        sub = QLabel("应用卸载与残留清理")
        sub.setFont(theme.font(12, 400))
        sub.setStyleSheet("color: #68737F; background: transparent;")
        names.addStretch()
        names.addWidget(title)
        names.addWidget(sub)
        names.addStretch()
        brand_row.addLayout(names, 1)
        self.layout.addLayout(brand_row)
        self.layout.addSpacing(28)

        self.nav_buttons: list[NavButton] = []
        for idx, (label, icon) in enumerate((("应用程序", "apps"),
                                             ("残留清理", "sparkles"),
                                             ("历史记录", "history"))):
            btn = NavButton(label, icon, self)
            btn.clicked.connect(lambda checked=False, i=idx: self.select(i))
            self.layout.addWidget(btn)
            self.layout.addSpacing(4)
            self.nav_buttons.append(btn)
        self.nav_buttons[0].setChecked(True)
        self._current_nav = 0
        self.nav_rail = QWidget(self)
        self.nav_rail.setFixedWidth(2)
        self.nav_rail.setStyleSheet("background: #315D78; border-radius: 1px;")
        self.nav_rail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.nav_rail.show()
        self.nav_rail.raise_()
        self._rail_anim = QPropertyAnimation(self.nav_rail, b"geometry", self)
        self._rail_anim.setDuration(220)
        self._rail_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        QTimer.singleShot(0, lambda: self._move_nav_rail(0, False))
        self.layout.addStretch(1)

        safety = GlassPanel(self, radius=12, fill=1.0)
        safety.setFixedHeight(76)
        sl = QVBoxLayout(safety)
        sl.setContentsMargins(12, 10, 12, 10)
        sl.setSpacing(4)
        h = QLabel("隔离删除")
        h.setFont(theme.font(12, 500))
        h.setStyleSheet("color: #11161C; background: transparent;")
        sl.addWidget(h)
        b = QLabel("残留先进入隔离区，可从历史记录恢复")
        b.setFont(theme.font(12, 400))
        b.setWordWrap(True)
        b.setStyleSheet("color: #68737F; background: transparent;")
        sl.addWidget(b)
        self.layout.addWidget(safety)
        self.layout.addSpacing(8)
        self.self_uninstall = GlassButton("卸载本程序", "danger_ghost", "trash",
                                          height=32, radius=6)
        self.self_uninstall.setToolTip("从系统中完整卸载喵喵并清理自身残留")
        self.self_uninstall.clicked.connect(self.self_uninstall_requested)
        self.layout.addWidget(self.self_uninstall)
        self.layout.addSpacing(8)
        version = QLabel("喵喵 1.5.0 · C 加速")
        version.setFont(theme.mono_font(10, 400))
        version.setStyleSheet("color: #98A1AB; background: transparent;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(version)

    def set_index(self, index: int, emit: bool = False) -> None:
        if not 0 <= index < len(self.nav_buttons):
            return
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self._move_nav_rail(index, True)
        if emit:
            self.page_requested.emit(index)

    def select(self, index: int) -> None:
        self.set_index(index, emit=True)

    def _move_nav_rail(self, index: int, animate: bool) -> None:
        if not 0 <= index < len(self.nav_buttons):
            return
        btn = self.nav_buttons[index]
        target = QRect(btn.geometry().left() + 3,
                       btn.geometry().center().y() - 9, 2, 18)
        self._current_nav = index
        self._rail_anim.stop()
        if animate:
            self._rail_anim.setStartValue(self.nav_rail.geometry())
            self._rail_anim.setEndValue(target)
            self._rail_anim.start()
        else:
            self.nav_rail.setGeometry(target)
            self.nav_rail.raise_()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if hasattr(self, "nav_rail"):
            self.nav_rail.setGeometry(QRect(
                self.nav_buttons[self._current_nav].geometry().left() + 3,
                self.nav_buttons[self._current_nav].geometry().center().y() - 9,
                2, 18))
            self.nav_rail.raise_()


class PawMark(QWidget):
    """Signature: the paw appears only beside a restorable quarantine state."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(12, 12)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        theme.draw_paw(p, QRectF(self.rect()), QColor(theme.ACCENT))


class FootprintRuler(QWidget):
    """Actual storage footprint of the app and its detected residue."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(84)
        self.app_size = 0
        self.residual_size = 0
        self.shared = 0
        self.scanned = False
        self._fill = 0.0
        self._anim = QPropertyAnimation(self, b"fill", self)
        self._anim.setDuration(320)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_fill(self): return self._fill
    def set_fill(self, value):
        self._fill = max(0.0, min(1.0, value)); self.update()
    fill = pyqtProperty(float, get_fill, set_fill)

    def set_data(self, app_size: int, residual_size: int = 0,
                 shared: int = 0, scanned: bool = False) -> None:
        self.app_size = max(0, app_size)
        self.residual_size = max(0, residual_size)
        self.shared = max(0, shared)
        self.scanned = scanned
        self._anim.stop()
        if scanned and self.residual_size > 0:
            self._fill = 0.0
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.start()
        else:
            self._fill = 1.0
        self.update()

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        theme.paint_glass(p, r, 8, fill=1.0)
        p.setFont(theme.font(12, 500))
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(r.left() + 12, r.top() + 9, 120, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "残留足迹")
        p.setFont(theme.mono_font(10, 500))
        p.setPen(QColor(theme.TEXT_MUTED))
        right = ("残留 %s" % human_size(self.residual_size)) if self.scanned else "扫描中"
        p.drawText(QRectF(r.left() + 120, r.top() + 9, r.width() - 132, 16),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   "应用 %s  ·  %s" % (human_size(self.app_size), right))
        total = self.app_size + self.residual_size
        bar = QRectF(r.left() + 12, r.top() + 34, r.width() - 24, 8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#E1E6EB"))
        p.drawRect(bar)
        if total > 0:
            aw = bar.width() * self.app_size / total
            p.setBrush(QColor(theme.TEXT_SOFT))
            p.drawRect(QRectF(bar.left(), bar.top(), aw, bar.height()))
            p.setBrush(QColor(theme.ACCENT))
            p.drawRect(QRectF(bar.left() + aw, bar.top(),
                              max(0.0, (bar.width() - aw) * self._fill), bar.height()))
        # Ruler ticks, one small mono label under each end.
        p.setPen(QPen(QColor(17, 22, 28, 34), 1))
        for i in range(5):
            x = bar.left() + bar.width() * i / 4
            p.drawLine(QPointF(x, bar.bottom() + 3), QPointF(x, bar.bottom() + 7))
        p.setFont(theme.mono_font(9, 400))
        p.setPen(QColor(theme.TEXT_DIM))
        p.setFont(theme.mono_font(9, 400))
        p.setPen(QColor(theme.TEXT_MUTED))
        p.drawText(QRectF(bar.left(), bar.bottom() + 10, bar.width() / 2, 14),
                   Qt.AlignmentFlag.AlignLeft, "应用")
        p.drawText(QRectF(bar.left() + bar.width() / 2, bar.bottom() + 10,
                          bar.width() / 2, 14),
                   Qt.AlignmentFlag.AlignRight, "残留" if self.scanned else "扫描中")
        if self.shared:
            p.setFont(theme.font(10, 400))
            p.drawText(QRectF(r.left() + 12, r.bottom() - 16, r.width() - 24, 14),
                       Qt.AlignmentFlag.AlignLeft, f"已排除 {self.shared} 个共享目录")


class DetailPanel(GlassPanel):
    uninstall_requested = pyqtSignal(object, object)
    residuals_requested = pyqtSignal()
    scan_requested = pyqtSignal(object)

    def __init__(self, provider: IconProvider, parent=None) -> None:
        super().__init__(parent, radius=16, fill=1.0)
        self.provider = provider
        self.app: AppInfo | None = None
        self.scan: ScanResult | None = None
        self.deps: list[str] = []
        self.processes: list[ProcessInfo] = []
        self._entry_anim = None
        self._entry_effect = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget(self)
        self.stack.setStyleSheet("background: transparent;")
        self.layout.addWidget(self.stack)

        self.empty = EmptyState("选择一个应用", "从左侧选择应用，查看卸载范围与残留。", "apps")
        self.stack.addWidget(self.empty)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 14px 1px; }
            QScrollBar::handle:vertical { background: #B5BEC7; min-height: 32px; border-radius: 3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.cl = QVBoxLayout(self.content)
        self.cl.setContentsMargins(20, 20, 20, 20)
        self.cl.setSpacing(12)
        scroll.setWidget(self.content)
        self.scroll = scroll
        self.stack.addWidget(scroll)

        # Hero
        hero = QHBoxLayout()
        hero.setSpacing(16)
        self.hero_icon = QLabel()
        self.hero_icon.setFixedSize(48, 48)
        hero.addWidget(self.hero_icon, 0, Qt.AlignmentFlag.AlignTop)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(3)
        badge_row = QHBoxLayout()
        badge_row.setSpacing(12)
        self.source_badge = Badge("APT", theme.ACCENT)
        self.risk_badge = Badge("可卸载", theme.SUCCESS)
        badge_row.addWidget(self.source_badge)
        badge_row.addWidget(self.risk_badge)
        badge_row.addStretch(1)
        self.name_label = QLabel("")
        self.name_label.setFont(theme.font(24, 600, display=True))
        self.name_label.setStyleSheet("color: #11161C; background: transparent;")
        self.meta_label = QLabel("")
        self.meta_label.setFont(theme.mono_font(10, 400))
        self.meta_label.setStyleSheet("color: #68737F; background: transparent;")
        self.meta_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        hero_text.addLayout(badge_row)
        hero_text.addWidget(self.name_label)
        hero_text.addWidget(self.meta_label)
        hero_text.addStretch(1)
        hero.addLayout(hero_text, 1)
        self.cl.addLayout(hero)

        self.summary_label = QLabel("")
        self.summary_label.setFont(theme.font(12, 400))
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color: #68737F; background: transparent;")
        self.cl.addWidget(self.summary_label)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        self.stat_source = StatCard("来源", "—", "", theme.ACCENT)
        self.stat_size = StatCard("磁盘占用", "—", "", theme.MINT)
        self.stat_version = StatCard("版本", "—", "", theme.ACCENT_2)
        for card in (self.stat_source, self.stat_size, self.stat_version):
            card.setFixedHeight(52)
            stats.addWidget(card, 1)
        self.cl.addLayout(stats)

        self.footprint = FootprintRuler()
        self.cl.addWidget(self.footprint)

        self.safety = InfoCard("shield", "评估", "正在检查依赖与系统影响…", theme.SUCCESS)
        self.cl.addWidget(self.safety)

        self.cl.addSpacing(2)
        self.cl.addWidget(section_label("卸载范围"))
        self.clean_row = OptionRow("清理配置与残留",
                                   "配置、本地数据、缓存", True)
        self.clean_row.toggled.connect(self._on_clean_toggled)
        self.cl.addWidget(self.clean_row)
        self.auto_row = OptionRow("移除不再需要的依赖",
                                  "仅对 APT 软件包可用，由 apt 计算依赖关系", False)
        self.auto_row.setVisible(False)
        self.cl.addWidget(self.auto_row)
        self.kill_row = OptionRow("结束相关进程",
                                  "仅匹配当前用户下与该应用同名或同路径的进程", False)
        self.kill_row.setVisible(False)
        self.cl.addWidget(self.kill_row)

        mode_head = QHBoxLayout()
        mode_head.addWidget(section_label("处理方式"))
        mode_head.addStretch(1)
        self.paw = PawMark()
        mode_head.addWidget(self.paw)
        self.mode_hint = QLabel("可恢复")
        self.mode_hint.setFont(theme.font(12, 400))
        self.mode_hint.setStyleSheet("color: #68737F; background: transparent;")
        mode_head.addWidget(self.mode_hint)
        self.cl.addLayout(mode_head)
        self.mode = SegmentedControl([("quarantine", "移至隔离区"),
                                      ("permanent", "永久删除")])
        self.mode.changed.connect(self._on_mode_changed)
        self.cl.addWidget(self.mode)

        self.cl.addStretch(1)

        # Pinned action dock: residual status and the destructive action share
        # one row so the content area keeps more vertical space.
        self.footer = QWidget(self)
        self.footer.setStyleSheet("background: transparent;")
        fl = QVBoxLayout(self.footer)
        fl.setContentsMargins(20, 4, 20, 12)
        fl.setSpacing(8)
        top_line = QFrame(self.footer)
        top_line.setFixedHeight(1)
        top_line.setStyleSheet("background: rgba(17,22,28,20); border: none;")
        fl.addWidget(top_line)
        dock = QHBoxLayout()
        dock.setSpacing(9)
        residual = GlassPanel(self.footer, radius=8, fill=1.0)
        residual.setFixedHeight(58)
        residual.setMinimumWidth(145)
        rl = QHBoxLayout(residual)
        rl.setContentsMargins(12, 7, 8, 7)
        rtext = QVBoxLayout()
        rtext.setSpacing(1)
        rt = QLabel("残留与配置")
        rt.setFont(theme.font(11, 500))
        rt.setStyleSheet("color: #3F4954; background: transparent;")
        self.residual_label = QLabel("等待扫描…")
        self.residual_label.setFont(theme.mono_font(10, 400))
        self.residual_label.setStyleSheet("color: #68737F; background: transparent;")
        self.residual_label.setWordWrap(False)
        rtext.addWidget(rt)
        rtext.addWidget(self.residual_label)
        rl.addLayout(rtext, 1)
        self.view_residuals = GlassButton("", "ghost", "chevron", height=30, radius=9)
        self.view_residuals.setFixedWidth(34)
        self.view_residuals.setToolTip("查看全部残留与配置")
        self.view_residuals.clicked.connect(self.residuals_requested)
        rl.addWidget(self.view_residuals)
        dock.addWidget(residual, 1)
        right = QVBoxLayout()
        right.setSpacing(2)
        self.uninstall_btn = GlassButton("卸载应用", "danger", "trash", height=40, radius=8)
        self.uninstall_btn.setFixedWidth(200)
        self.uninstall_btn.clicked.connect(self._request_uninstall)
        right.addWidget(self.uninstall_btn)
        self.auth_hint = QLabel("需要系统授权 · 由 Polkit 验证")
        self.auth_hint.setFont(theme.font(10, 400))
        self.auth_hint.setStyleSheet("color: #98A1AB; background: transparent;")
        self.auth_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.auth_hint)
        dock.addLayout(right)
        fl.addLayout(dock)
        self.footer.hide()
        self.layout.addWidget(self.footer)

    # -- updates ----------------------------------------------------------
    def set_app(self, app: AppInfo | None) -> None:
        self.app = app
        self.scan = None
        self.deps = []
        self.processes = []
        if app is None:
            self.stack.setCurrentIndex(0)
            self.footer.hide()
            return
        self.stack.setCurrentIndex(1)
        self.footer.show()
        self.scroll.verticalScrollBar().setValue(0)
        pix = self.provider.get(app, 48)
        self.hero_icon.setPixmap(pix)
        self.name_label.setText(app.name)
        self.meta_label.setText(f"{app.package}  ·  {app.version}")
        self.source_badge.set_text(app.source, theme.SOURCE_COLORS.get(app.source, theme.ACCENT))
        self.summary_label.setText(app.summary or "此应用没有提供描述。")
        self.stat_source.set_value(app.source)
        self.stat_size.set_value(human_size(app.size))
        self.stat_version.set_value(app.version[:20] or "—")
        self.auto_row.setVisible(app.source == "APT")
        self.kill_row.setVisible(False)
        self.risk_badge.set_text("检查中", theme.TEXT_MUTED)
        self.safety.set_content("正在检查", "分析依赖、运行进程与残留中", theme.ACCENT)
        self.residual_label.setText("正在扫描残留…")
        self.uninstall_btn.setEnabled(False)
        self.uninstall_btn.setText("系统组件 · 已保护" if app.protected else f"卸载 {app.name}")
        self.uninstall_btn.icon_kind = "lock" if app.protected else "trash"
        self.uninstall_btn.update()
        self.mode.set_index(0, emit=False)
        self.clean_row.toggle.setChecked(True)
        self.auto_row.toggle.setChecked(False)
        self.kill_row.toggle.setChecked(False)
        self.auth_hint.setText("需要系统授权 · 由 Polkit 验证" if app.source != "本地"
                               else "本地应用 · 无需系统授权")
        self.footprint.set_data(app.size, scanned=False)
        self._animate_detail_entry()
        self.scan_requested.emit(app)

    def _animate_detail_entry(self) -> None:
        if self._entry_anim is not None:
            self._entry_anim.stop()
        if self._entry_effect is not None:
            self.scroll.setGraphicsEffect(None)
        effect = QGraphicsOpacityEffect(self.scroll)
        effect.setOpacity(0.0)
        self.scroll.setGraphicsEffect(effect)
        self._entry_effect = effect
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(150)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self._finish_detail_entry(effect))
        self._entry_anim = anim
        anim.start()

    def _finish_detail_entry(self, effect) -> None:
        if self.scroll.graphicsEffect() is effect:
            self.scroll.setGraphicsEffect(None)
        self._entry_effect = None
        self._entry_anim = None


    def set_details(self, deps: list[str], processes: list[ProcessInfo]) -> None:
        if self.app is None:
            return
        self.deps = deps or []
        self.processes = processes or []
        self.kill_row.setVisible(bool(self.processes) and not self.app.protected)
        if self.processes:
            self.kill_row.sub.setText(
                f"检测到 {len(self.processes)} 个进程：" +
                "、".join(p.name for p in self.processes[:3]))
        app = self.app
        if app.protected:
            self.risk_badge.set_text("系统保护", theme.AMBER)
            self.safety.set_content("系统保护",
                                    f"{app.protection_reason}。为避免系统损坏，此应用不允许在此卸载。",
                                    theme.AMBER)
        elif self.deps:
            self.risk_badge.set_text("需要复核", theme.AMBER)
            self.safety.set_content("存在依赖",
                                    "以下已安装软件依赖此包：" + "、".join(self.deps[:5]) +
                                    "。卸载可能影响它们，请确认后再继续。", theme.AMBER)
        elif self.processes:
            self.risk_badge.set_text("应用运行中", theme.AMBER)
            self.safety.set_content("应用运行中",
                                    f"检测到 {len(self.processes)} 个相关进程。建议先退出应用，或在下方开启“结束相关进程”。",
                                    theme.AMBER)
        else:
            self.risk_badge.set_text("可卸载", theme.SUCCESS)
            src_note = "系统包管理器会一并清理 /etc 中的系统配置。" if app.source == "APT" else \
                ("Flatpak 沙盒数据会随应用一起删除。" if app.source == "Flatpak" else
                 "仅删除用户目录内的文件。")
            self.safety.set_content("可卸载",
                                    "未发现反向依赖或运行中的进程。" + src_note, theme.SUCCESS)

    def set_scan(self, scan: ScanResult) -> None:
        self.scan = scan
        if self.app is None:
            return
        self.footprint.set_data(self.app.size, scan.total_size, scan.excluded_shared, scanned=True)
        selected = [i for i in scan.items if i.selected]
        size = sum(i.size for i in selected)
        if not scan.items:
            self.residual_label.setText("未发现用户残留")
            self.residual_label.setToolTip("")
        else:
            self.residual_label.setText(f"{len(scan.items)} 项 · {human_size(size)}")
            self.residual_label.setToolTip(
                f"{len(scan.items)} 个残留项目，可清理 {human_size(size)}；"
                f"{scan.excluded_shared} 个共享目录已保护")
        self.view_residuals.setEnabled(bool(scan.items))
        self.uninstall_btn.setEnabled(not self.app.protected)
        self.uninstall_btn.setText(f"卸载 {self.app.name}")

    def set_scan_failed(self, message: str = "扫描失败") -> None:
        # Keep a valid empty plan so the app can still be uninstalled without
        # touching residual files when scanning itself failed.
        self.scan = ScanResult()
        self.residual_label.setText(message)
        self.clean_row.toggle.setChecked(False)
        self.view_residuals.setEnabled(False)
        self.uninstall_btn.setEnabled(not (self.app and self.app.protected))

    def _on_clean_toggled(self, checked: bool) -> None:
        self.mode.setEnabled(checked)

    def _on_mode_changed(self, index: int) -> None:
        if index == 0:
            self.mode_hint.setText("可恢复")
            self.mode_hint.setStyleSheet("color: #68737F; background: transparent;")
            self.paw.show()
        else:
            self.mode_hint.setText("不保留")
            self.mode_hint.setStyleSheet("color: #8B3F47; background: transparent;")
            self.paw.hide()

    def _request_uninstall(self) -> None:
        if self.app is None:
            return
        if self.scan is None:
            self.scan_requested.emit(self.app)
            self.residual_label.setText("正在扫描残留，请稍候…")
            return
        selected = [i for i in self.scan.items if i.selected]
        opts = UninstallOptions(
            clean_residuals=self.clean_row.toggle.isChecked(),
            residual_ids=[i.path for i in selected],
            mode="permanent" if self.mode.index == 1 else "quarantine",
            remove_install_dir=True,
            auto_remove=self.auto_row.toggle.isChecked(),
            kill_processes=self.kill_row.toggle.isChecked(),
        )
        self.uninstall_requested.emit(self.app, opts)


class AppPage(QWidget):
    app_selected = pyqtSignal(object)
    refresh_requested = pyqtSignal()
    scan_requested = pyqtSignal(object)
    uninstall_requested = pyqtSignal(object, object, object)
    residuals_requested = pyqtSignal()

    def __init__(self, provider: IconProvider, parent=None) -> None:
        super().__init__(parent)
        self.provider = provider
        self.catalog = None
        self.apps: list[AppInfo] = []
        self.filter_key = "all"
        self.search_text = ""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(32, 24, 32, 24)
        self.layout.setSpacing(24)

        header = QHBoxLayout()
        header.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.title = QLabel("应用程序")
        self.title.setFont(theme.font(28, 600, display=True))
        self.title.setStyleSheet("color: #11161C; background: transparent;")
        self.subtitle = QLabel("正在读取软件包…")
        self.subtitle.setFont(theme.font(12, 400))
        self.subtitle.setStyleSheet("color: #68737F; background: transparent;")
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)
        self.search = SearchBox("搜索应用或包名")
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self._on_search)
        header.addWidget(self.search, 0, Qt.AlignmentFlag.AlignVCenter)
        self.refresh = IconButton("refresh", 32, "重新扫描应用")
        self.refresh.clicked.connect(self.refresh_requested)
        header.addWidget(self.refresh, 0, Qt.AlignmentFlag.AlignVCenter)
        self.layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(16)
        list_panel = GlassPanel(self, radius=16, fill=1.0)
        list_panel.setMinimumWidth(400)
        list_panel.setMaximumWidth(460)
        ll = QVBoxLayout(list_panel)
        ll.setContentsMargins(12, 16, 12, 12)
        ll.setSpacing(12)
        lh = QHBoxLayout()
        lh.setContentsMargins(4, 0, 4, 0)
        installed = QLabel("已安装")
        installed.setFont(theme.font(12, 500))
        installed.setStyleSheet("color: #11161C; background: transparent;")
        lh.addWidget(installed)
        lh.addStretch(1)
        self.list_count = QLabel("0")
        self.list_count.setFont(theme.mono_font(12, 500))
        self.list_count.setStyleSheet("color: #68737F; background: transparent;")
        lh.addWidget(self.list_count)
        ll.addLayout(lh)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(4, 0, 4, 0)
        filter_row.setSpacing(4)
        self.pills: list[PillButton] = []
        for key, label in (("all", "全部"), ("gui", "图形应用"),
                           ("APT", "APT"), ("Flatpak", "Flatpak"), ("本地", "本地")):
            pill = PillButton(label)
            pill.setCheckable(True)
            pill.setChecked(key == "all")
            pill.clicked.connect(lambda checked=False, k=key: self._set_filter(k))
            filter_row.addWidget(pill)
            self.pills.append(pill)
        filter_row.addStretch(1)
        ll.addLayout(filter_row)

        self.filter_indicator = QWidget(list_panel)
        self.filter_indicator.setFixedHeight(2)
        self.filter_indicator.setStyleSheet("background: #315D78; border-radius: 1px;")
        self.filter_indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.filter_indicator.show()
        self.filter_indicator.raise_()
        self._filter_anim = QPropertyAnimation(self.filter_indicator, b"geometry", self)
        self._filter_anim.setDuration(220)
        self._filter_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        QTimer.singleShot(0, lambda: self._move_filter_indicator(False))

        self.list = AppList(self.provider, self._lookup, list_panel)
        self.list.currentItemChanged.connect(self._on_current)
        self.list_stack = QStackedWidget(list_panel)
        self.list_stack.setStyleSheet("background: transparent;")
        self.list_stack.addWidget(self.list)
        self.empty_list_state = EmptyState(
            "没有匹配的应用", "换一个来源筛选，或清除搜索关键词。", "search")
        self.list_stack.addWidget(self.empty_list_state)
        self.list_stack.setCurrentIndex(0)
        ll.addWidget(self.list_stack, 1)
        footer = QLabel("APT · Flatpak · Snap · 本地")
        footer.setFont(theme.font(12, 400))
        footer.setStyleSheet("color: #98A1AB; background: transparent;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(footer)

        self.detail = DetailPanel(self.provider, self)
        self.detail.uninstall_requested.connect(
            lambda app, opts: self.uninstall_requested.emit(app, opts, self.detail.scan))
        self.detail.residuals_requested.connect(self.residuals_requested)
        self.detail.scan_requested.connect(self._scan_for_detail)
        body.addWidget(list_panel, 0)
        body.addWidget(self.detail, 1)
        self.layout.addLayout(body, 1)
        self._detail_timer = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(90)
        self._search_timer.timeout.connect(self._apply_filter)
        self.loading = LoadingOverlay(self)
        self.loading.show()
        self.loading.raise_()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if hasattr(self, "loading"):
            self.loading.setGeometry(self.rect())
            self.loading.raise_()
        if hasattr(self, "filter_indicator"):
            QTimer.singleShot(0, lambda: self._move_filter_indicator(False))

    def set_loading(self, visible: bool) -> None:
        if visible:
            self.loading.setGeometry(self.rect())
            self.loading.show()
            self.loading.raise_()
        else:
            self.loading.dismiss()

    def set_catalog(self, catalog, apps: list[AppInfo]) -> None:
        self.set_loading(False)
        self.catalog = catalog
        self.apps = apps
        self._apply_filter(select_first=False)
        preferred = None
        for needle in ("telegram", "chromium", "firefox", "code", "vlc"):
            preferred = next((a for a in apps if a.kind == "gui" and
                              needle in (a.name + " " + a.package).casefold()), None)
            if preferred:
                break
        target = preferred.id if preferred else (apps[0].id if apps else "")
        for i in range(self.list.count()):
            if self.list.item(i).data(APP_ROLE) == target:
                self.list.setCurrentRow(i)
                break
        gui_count = sum(1 for a in apps if a.kind == "gui")
        self.subtitle.setText(f"{gui_count} 个应用 · {len(apps)} 个可管理包")
        self.refresh.setEnabled(True)

    def _lookup(self, app_id: str):
        if self.catalog is None:
            return None
        return self.catalog.get(app_id)

    def remove_app(self, app_id: str) -> None:
        self.apps = [a for a in self.apps if a.id != app_id]
        self._apply_filter(select_first=True)
        if self.list.count() == 0:
            self.detail.set_app(None)

    def _on_search(self, text: str) -> None:
        self.search_text = text.strip().casefold()
        self._search_timer.start()

    def _set_filter(self, key: str) -> None:
        self.filter_key = key
        for pill in self.pills:
            pill.setChecked(pill.text() == {
                "all": "全部", "gui": "图形应用", "APT": "APT",
                "Flatpak": "Flatpak", "本地": "本地",
            }[key])
        self._move_filter_indicator(True)
        self._apply_filter()

    def _move_filter_indicator(self, animate: bool = True) -> None:
        active = next((p for p in self.pills if p.isChecked()), None)
        if active is None or not hasattr(self, "filter_indicator"):
            return
        parent = self.filter_indicator.parentWidget()
        if parent is None:
            return
        pos = active.mapTo(parent, QPoint(7, active.height() - 3))
        target = QRect(pos.x(), pos.y(), max(0, active.width() - 14), 2)
        self._filter_anim.stop()
        if animate:
            self._filter_anim.setStartValue(self.filter_indicator.geometry())
            self._filter_anim.setEndValue(target)
            self._filter_anim.start()
        else:
            self.filter_indicator.setGeometry(target)
            self.filter_indicator.raise_()

    def _matches(self, app: AppInfo) -> bool:
        if self.filter_key == "gui" and app.kind != "gui":
            return False
        if self.filter_key in ("APT", "Flatpak", "本地") and app.source != self.filter_key:
            return False
        if self.search_text:
            haystack = f"{app.name} {app.package} {app.summary} {app.source}".casefold()
            if self.search_text not in haystack:
                return False
        return True

    def _apply_filter(self, select_first: bool = False) -> None:
        filtered = [a for a in self.apps if self._matches(a)]
        current = self.list.current_app_id()
        self.list.set_apps(filtered)
        self.list_count.setText(str(len(filtered)))
        self.list_stack.setCurrentIndex(0 if filtered else 1)
        if select_first and filtered:
            self.list.setCurrentRow(0)
            return
        restored = False
        if current:
            for i in range(self.list.count()):
                if self.list.item(i).data(APP_ROLE) == current:
                    self.list.setCurrentRow(i)
                    restored = True
                    break
        if not restored and filtered:
            self.list.setCurrentRow(0)
        if not filtered and self.detail.app is not None:
            self.detail.set_app(None)

    def _on_current(self, current, previous) -> None:
        if current is None:
            return
        app = self._lookup(current.data(APP_ROLE))
        if app:
            self.detail.set_app(app)

    def _scan_for_detail(self, app: AppInfo) -> None:
        self.detail.residual_label.setText("正在扫描残留…")
        self.scan_requested.emit(app)


class ResidualPage(QWidget):
    rescan_requested = pyqtSignal(object)
    cleanup_requested = pyqtSignal(object, object, str)
    back_requested = pyqtSignal()

    def __init__(self, provider: IconProvider, parent=None) -> None:
        super().__init__(parent)
        self.provider = provider
        self.app: AppInfo | None = None
        self.scan: ScanResult | None = None
        self.rows: list[ResidualRow] = []
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(32, 24, 32, 24)
        self.layout.setSpacing(24)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.title = QLabel("残留清理")
        self.title.setFont(theme.font(28, 600, display=True))
        self.title.setStyleSheet("color: #11161C; background: transparent;")
        self.subtitle = QLabel("精确匹配用户目录中的配置、数据与缓存")
        self.subtitle.setFont(theme.font(11, 400))
        self.subtitle.setStyleSheet("color: #68737F; background: transparent;")
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)
        self.rescan = GlassButton("重新扫描", "secondary", "refresh", height=36, radius=8)
        self.rescan.setFixedWidth(130)
        self.rescan.clicked.connect(self._rescan)
        header.addWidget(self.rescan)
        self.layout.addLayout(header)

        self.app_bar = GlassPanel(self, radius=12, fill=1.0)
        self.app_bar.setFixedHeight(82)
        ab = QHBoxLayout(self.app_bar)
        ab.setContentsMargins(16, 10, 18, 10)
        self.app_icon = QLabel()
        self.app_icon.setFixedSize(46, 46)
        ab.addWidget(self.app_icon)
        self.app_name = QLabel("未选择应用")
        self.app_name.setFont(theme.font(15, 650))
        self.app_name.setStyleSheet("color: #11161C; background: transparent;")
        self.app_meta = QLabel("返回应用页选择一个应用")
        self.app_meta.setFont(theme.font(9, 400))
        self.app_meta.setStyleSheet("color: #68737F; background: transparent;")
        ab.addSpacing(10)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(self.app_name)
        text.addWidget(self.app_meta)
        ab.addLayout(text, 1)
        self.scan_state = Badge("待扫描", theme.TEXT_MUTED)
        ab.addWidget(self.scan_state)
        self.layout.addWidget(self.app_bar)

        summary = QHBoxLayout()
        summary.setSpacing(9)
        self.card_total = StatCard("检测到", "—", "sparkles", theme.ACCENT)
        self.card_size = StatCard("可清理", "—", "database", theme.MINT)
        self.card_shared = StatCard("共享保护", "—", "shield", theme.ACCENT_2)
        for c in (self.card_total, self.card_size, self.card_shared):
            summary.addWidget(c, 1)
        self.layout.addLayout(summary)

        self.list_panel = GlassPanel(self, radius=16, fill=1.0)
        ll = QVBoxLayout(self.list_panel)
        ll.setContentsMargins(10, 10, 10, 10)
        ll.setSpacing(2)
        lh = QHBoxLayout()
        lh.setContentsMargins(8, 2, 8, 4)
        cap = QLabel("残留项目")
        cap.setFont(theme.font(11, 650))
        cap.setStyleSheet("color: #3F4954; background: transparent;")
        lh.addWidget(cap)
        lh.addStretch(1)
        self.select_safe = GlassButton("全选可清理", "ghost", "check", height=32, radius=6)
        self.select_safe.setFixedWidth(150)
        self.select_safe.clicked.connect(self._select_safe)
        lh.addWidget(self.select_safe)
        ll.addLayout(lh)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollBar:vertical { background: transparent; width: 7px; margin: 4px 1px; }
            QScrollBar::handle:vertical { background: rgba(17,22,28,32); min-height: 30px;
                                          border-radius: 3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        self.list_content = QWidget()
        self.list_content.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_content)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(2)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_content)
        ll.addWidget(self.scroll, 1)
        self.empty = EmptyState("没有发现用户残留",
                                "这个应用很干净。共享目录与系统配置已自动排除。", "leaf")
        ll.addWidget(self.empty, 1)
        self.empty.hide()
        hint = QLabel("共享目录、系统配置与其他应用可能共用的配置已自动排除")
        hint.setFont(theme.font(9, 400))
        hint.setStyleSheet("color: #98A1AB; background: transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(hint)
        self.layout.addWidget(self.list_panel, 1)

        action = GlassPanel(self, radius=16, fill=1.0)
        action.setFixedHeight(78)
        al = QHBoxLayout(action)
        al.setContentsMargins(16, 10, 12, 10)
        self.selected_label = QLabel("已选择 0 项")
        self.selected_label.setFont(theme.font(11, 600))
        self.selected_label.setStyleSheet("color: #11161C; background: transparent;")
        self.selected_size = QLabel("0 B")
        self.selected_size.setFont(theme.font(9, 400))
        self.selected_size.setStyleSheet("color: #68737F; background: transparent;")
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(self.selected_label)
        text.addWidget(self.selected_size)
        al.addLayout(text, 1)
        self.mode = SegmentedControl([("quarantine", "隔离区"), ("permanent", "永久删除")])
        self.mode.changed.connect(lambda _index: self._update_selection())
        self.mode.setFixedWidth(238)
        al.addWidget(self.mode)
        al.addSpacing(8)
        self.clean_btn = GlassButton("清理所选", "primary", "broom", height=40, radius=8)
        self.clean_btn.setFixedWidth(148)
        self.clean_btn.clicked.connect(self._clean)
        al.addWidget(self.clean_btn)
        self.layout.addWidget(action)
        self._update_selection()

    def set_app(self, app: AppInfo) -> None:
        self.app = app
        if app is None:
            self.app_name.setText("未选择应用")
            self.app_meta.setText("返回应用页选择一个应用")
            self.app_icon.clear()
            return
        self.app_icon.setPixmap(self.provider.get(app, 46))
        self.app_name.setText(app.name)
        self.app_meta.setText(f"{app.package}  ·  {app.source}")
        self.scan_state.set_text("扫描中…", theme.ACCENT)
        self.scan = None
        self._clear_rows()
        self.card_total.set_value("—")
        self.card_size.set_value("—")
        self.card_shared.set_value("—")
        self.scroll.show()
        self.empty.hide()
        self._update_selection()

    def set_scan(self, scan: ScanResult) -> None:
        self.scan = scan
        self._clear_rows()
        for item in scan.items:
            row = ResidualRow(item)
            row.changed.connect(self._update_selection)
            self.rows.append(row)
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
        self.card_total.set_value(f"{len(scan.items)} 项")
        self.card_size.set_value(human_size(sum(i.size for i in scan.items)))
        self.card_shared.set_value(f"{scan.excluded_shared} 项")
        self.scan_state.set_text("扫描完成", theme.SUCCESS)
        if scan.items:
            self.empty.hide()
            self.scroll.show()
        else:
            self.empty.show()
            self.scroll.hide()
        self._update_selection()

    def _clear_rows(self) -> None:
        for row in self.rows:
            row.setParent(None)
            row.deleteLater()
        self.rows = []

    def _select_safe(self) -> None:
        if not self.scan:
            return
        for row in self.rows:
            if row.item.safety == "safe":
                row.check.setChecked(True)
            else:
                row.check.setChecked(False)
        self._update_selection()

    def _update_selection(self) -> None:
        if not self.scan:
            self.clean_btn.setEnabled(False)
            return
        selected = [i for i in self.scan.items if i.selected]
        size = sum(i.size for i in selected)
        self.selected_label.setText(f"已选择 {len(selected)} 项")
        self.selected_size.setText(f"{human_size(size)} · " +
                                   ("移至隔离区后可恢复" if self.mode.index == 0 else "删除后保留配置备份"))
        self.clean_btn.setEnabled(bool(selected))
        self.clean_btn.setText(f"清理 {len(selected)} 项" if selected else "清理所选")
        self.select_safe.setEnabled(any(i.safety == "safe" for i in self.scan.items))

    def _rescan(self) -> None:
        if self.app:
            self.rescan_requested.emit(self.app)

    def _clean(self) -> None:
        if not self.app or not self.scan:
            return
        selected = [i for i in self.scan.items if i.selected]
        if not selected:
            return
        self.cleanup_requested.emit(self.app, selected,
                                    "quarantine" if self.mode.index == 0 else "permanent")


class HistoryCard(GlassPanel):
    restore_requested = pyqtSignal(str)
    purge_requested = pyqtSignal(str)
    open_requested = pyqtSignal(str)

    def __init__(self, record: dict, provider: IconProvider, parent=None) -> None:
        super().__init__(parent, radius=8, fill=1.0)
        self.record = record
        self.setMinimumHeight(88)
        app = AppInfo.from_dict(record.get("app", {}))
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(16, 12, 16, 12)
        self.layout.setSpacing(12)
        icon = QLabel()
        icon.setFixedSize(40, 40)
        icon.setPixmap(provider.get(app, 40))
        self.layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)
        info = QVBoxLayout()
        info.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(8)
        name = QLabel(app.name)
        name.setFont(theme.font(13, 500))
        name.setStyleSheet("color: #11161C; background: transparent;")
        top.addWidget(name)
        status_map = {"success": ("完成", theme.SUCCESS), "partial": ("部分完成", theme.AMBER),
                      "failed": ("失败", theme.DANGER), "empty": ("无项目", theme.TEXT_MUTED)}
        st, color = status_map.get(record.get("status"), ("完成", theme.SUCCESS))
        badge = Badge(st, color)
        top.addWidget(badge)
        top.addStretch(1)
        info.addLayout(top)
        try:
            dt = datetime.fromisoformat(record.get("created_at", ""))
            stamp = dt.astimezone().strftime("%Y-%m-%d  %H:%M")
        except (ValueError, TypeError):
            stamp = "—"
        residual_count = len([r for r in record.get("residuals", []) if r.get("moved_to")])
        mode = "隔离" if record.get("mode") == "quarantine" else "永久删除 · 备份"
        meta = QLabel(f"{stamp}  ·  {record.get('native_message') or '处理完成'}  ·  "
                      f"{residual_count} 项残留 · {human_size(record.get('freed', 0))} · {mode}")
        meta.setFont(theme.mono_font(10, 400))
        meta.setStyleSheet("color: #68737F; background: transparent;")
        info.addWidget(meta)
        self.layout.addLayout(info, 1)

        if residual_count or record.get("backup"):
            btn = GlassButton("恢复", "secondary", "restore", height=32, radius=6)
            btn.setFixedWidth(84)
            btn.clicked.connect(lambda: self.restore_requested.emit(record.get("id", "")))
            self.layout.addWidget(btn)
        if record.get("quarantine_dir") or record.get("backup"):
            btn2 = GlassButton("彻底删除", "ghost", "trash", height=32, radius=6)
            btn2.setFixedWidth(92)
            btn2.clicked.connect(lambda: self.purge_requested.emit(record.get("id", "")))
            self.layout.addWidget(btn2)


class HistoryPage(QWidget):
    restore_requested = pyqtSignal(str)
    purge_requested = pyqtSignal(str)
    open_data_requested = pyqtSignal()

    def __init__(self, provider: IconProvider, parent=None) -> None:
        super().__init__(parent)
        self.provider = provider
        self.cards: list[HistoryCard] = []
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(32, 24, 32, 24)
        self.layout.setSpacing(24)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        title = QLabel("历史记录")
        title.setFont(theme.font(28, 600, display=True))
        title.setStyleSheet("color: #11161C; background: transparent;")
        self.subtitle = QLabel("隔离区内的文件可随时恢复")
        self.subtitle.setFont(theme.font(11, 400))
        self.subtitle.setStyleSheet("color: #68737F; background: transparent;")
        titles.addWidget(title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)
        self.open_btn = GlassButton("数据目录", "secondary", "folder", height=36, radius=8)
        self.open_btn.setFixedWidth(146)
        self.open_btn.clicked.connect(self.open_data_requested)
        header.addWidget(self.open_btn)
        self.layout.addLayout(header)

        self.stats = QHBoxLayout()
        self.stats.setSpacing(9)
        self.card_ops = StatCard("操作记录", "0", "history", theme.ACCENT)
        self.card_items = StatCard("隔离项目", "0", "database", theme.MINT)
        self.card_recover = StatCard("可恢复空间", "—", "restore", theme.ACCENT_2)
        for c in (self.card_ops, self.card_items, self.card_recover):
            self.stats.addWidget(c, 1)
        self.layout.addLayout(self.stats)

        self.panel = GlassPanel(self, radius=16, fill=1.0)
        pl = QVBoxLayout(self.panel)
        pl.setContentsMargins(10, 10, 10, 10)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollBar:vertical { background: transparent; width: 7px; margin: 4px; }
            QScrollBar::handle:vertical { background: rgba(17,22,28,32); min-height: 30px;
                                          border-radius: 3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(7)
        self.content_layout.addStretch(1)
        self.scroll.setWidget(self.content)
        pl.addWidget(self.scroll)
        self.empty = EmptyState("还没有卸载记录",
                                "完成一次卸载后，操作记录和可恢复的隔离文件会出现在这里。", "history")
        pl.addWidget(self.empty)
        self.layout.addWidget(self.panel, 1)

    def refresh(self, records: list[dict]) -> None:
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards = []
        for record in records:
            card = HistoryCard(record, self.provider)
            card.restore_requested.connect(self.restore_requested)
            card.purge_requested.connect(self.purge_requested)
            self.content_layout.insertWidget(self.content_layout.count() - 1, card)
            self.cards.append(card)
        if records:
            self.empty.hide()
            self.scroll.show()
        else:
            self.empty.show()
            self.scroll.hide()
        items = sum(1 for r in records for i in r.get("residuals", []) if i.get("moved_to"))
        recover = sum(r.get("freed", 0) for r in records if r.get("quarantine_dir"))
        self.card_ops.set_value(str(len(records)))
        self.card_items.set_value(f"{items} 项")
        self.card_recover.set_value(human_size(recover))
        self.subtitle.setText(f"{len(records)} 次操作 · {items} 项隔离文件可恢复")
