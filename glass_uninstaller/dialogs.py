"""Modal confirmation and in-window execution overlays."""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QKeyEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
    QWidget,
)

from . import theme
from .backend import AppInfo, UninstallOptions, human_size
from .widgets import GlassButton, GlassCheck, GlassPanel, IconProvider, ProgressRing, draw_app_icon


def _label(text: str, size: int = 11, color=theme.TEXT_SOFT, weight: int = 400) -> QLabel:
    lab = QLabel(text)
    lab.setFont(theme.font(size, weight))
    lab.setStyleSheet(f"color: {QColor(color).name()}; background: transparent;")
    lab.setWordWrap(True)
    return lab



class ConfirmDialog(QDialog):
    def __init__(self, app: AppInfo, options: UninstallOptions, plan: dict,
                 provider: IconProvider, parent=None) -> None:
        super().__init__(parent)
        self.app = app
        self.options = options
        self.plan = plan
        self.provider = provider
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFixedWidth(560)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.surface = QWidget(self)
        self.surface.setObjectName("surface")
        self.layout.addWidget(self.surface)
        sl = QVBoxLayout(self.surface)
        sl.setContentsMargins(28, 24, 28, 22)
        sl.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(13)
        icon = QLabel()
        icon.setFixedSize(54, 54)
        icon.setPixmap(provider.get(app, 54))
        head.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        t = _label("确认卸载", 20, theme.TEXT, 650)
        t.setFont(theme.font(20, 650, display=True))
        s = _label(f"{app.name}  ·  {app.source}", 10, theme.TEXT_MUTED)
        titles.addWidget(t)
        titles.addWidget(s)
        titles.addStretch(1)
        head.addLayout(titles, 1)
        sl.addLayout(head)

        summary = QLabel(
            f"将删除应用本体，并{'清理 ' + str(plan.get('selected_count', 0)) + ' 项用户残留' if options.clean_residuals else '保留用户配置'}。"
            + (" 残留会先进入隔离区，可从历史记录恢复。" if options.mode == "quarantine"
               else " 残留将从原位置永久删除，配置会打包保存为恢复备份。"))
        summary.setFont(theme.font(11, 400))
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #5A6572; background: transparent;")
        sl.addWidget(summary)

        details = GlassPanel(self.surface, radius=14, tint=QColor(theme.ACCENT), fill=0.66)
        details.setMinimumHeight(104)
        dl = QVBoxLayout(details)
        dl.setContentsMargins(14, 10, 14, 10)
        dl.setSpacing(4)
        for label, value in (
            ("卸载方式", plan.get("steps", ["—"])[0]),
            ("可清理", f"{plan.get('selected_count', 0)} 项 · {human_size(plan.get('size', 0))}"),
            ("清理模式", "隔离区（可恢复）" if options.mode == "quarantine" else "永久删除 · 保留备份"),
            ("系统授权", "需要 · Polkit 将弹出验证" if plan.get("needs_auth") else "不需要"),
        ):
            row = QHBoxLayout()
            k = _label(label, 9, theme.TEXT_DIM)
            k.setFixedWidth(64)
            v = _label(str(value), 10, theme.TEXT_SOFT, 500)
            row.addWidget(k)
            row.addWidget(v, 1)
            dl.addLayout(row)
        sl.addWidget(details)

        warnings = plan.get("warnings") or []
        if warnings:
            warn = GlassPanel(self.surface, radius=14, tint=QColor(theme.AMBER), fill=0.72)
            wl = QVBoxLayout(warn)
            wl.setContentsMargins(14, 10, 14, 10)
            wt = _label("请留意", 10, theme.AMBER, 650)
            wl.addWidget(wt)
            for w in warnings[:4]:
                wl.addWidget(_label("• " + w, 9, QColor("#806B49")))
            sl.addWidget(warn)

        if options.mode == "permanent" or plan.get("warnings"):
            self.ack = QHBoxLayout()
            self.check = GlassCheck(self.surface)
            self.check.setChecked(False)
            ack_label = _label("我已了解此操作的影响，并确认继续", 9, theme.TEXT_MUTED)
            self.ack.addWidget(self.check)
            self.ack.addWidget(ack_label, 1)
            sl.addLayout(self.ack)
            self.check.toggled.connect(self._ack)
        else:
            self.check = None
        sl.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(9)
        actions.addStretch(1)
        cancel = GlassButton("取消", "secondary", "", height=44, radius=14)
        cancel.setFixedWidth(118)
        cancel.clicked.connect(self.reject)
        self.confirm = GlassButton("确认卸载", "danger", "trash", height=44, radius=14)
        self.confirm.setFixedWidth(156)
        self.confirm.clicked.connect(self.accept)
        if self.check is not None:
            self.confirm.setEnabled(False)
        actions.addWidget(cancel)
        actions.addWidget(self.confirm)
        sl.addLayout(actions)
        self.adjustSize()

    def _ack(self, checked: bool) -> None:
        self.confirm.setEnabled(checked)

    def showEvent(self, e) -> None:
        super().showEvent(e)
        if self.parentWidget():
            pg = self.parentWidget().window()
            geo = self.frameGeometry()
            geo.moveCenter(pg.frameGeometry().center())
            self.move(geo.topLeft())

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.7, 0.7, -0.7, -0.7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(250, 251, 253, 248))
        p.drawRoundedRect(r, 16, 16)
        theme.paint_glass(p, r, 16, tint=QColor(theme.ACCENT), fill=1.0)
        p.setPen(QPen(QColor(31, 39, 50, 42), 1))
        p.drawRoundedRect(r, 16, 16)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(e)


class ExecutionOverlay(QWidget):
    closed = pyqtSignal()
    history_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.running = False
        self.result: dict | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.hide()
        self.card = GlassPanel(self, radius=16, fill=1.0)
        self.card.setFixedSize(630, 566)
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(28, 24, 28, 22)
        cl.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(22)
        self.ring = ProgressRing(self.card, 128)
        top.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignTop)
        info = QVBoxLayout()
        info.setSpacing(4)
        self.kicker = QLabel("正在处理")
        self.kicker.setFont(theme.font(9, 650, spacing=1.4))
        self.kicker.setStyleSheet("color: #607B99; background: transparent;")
        self.title = QLabel("准备卸载")
        self.title.setFont(theme.font(21, 650, display=True))
        self.title.setStyleSheet("color: #1A1D23; background: transparent;")
        self.subtitle = QLabel("")
        self.subtitle.setFont(theme.font(10, 400))
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet("color: #6E7987; background: transparent;")
        self.status = QLabel("请不要关闭窗口")
        self.status.setFont(theme.font(9, 500))
        self.status.setStyleSheet("color: #6E7987; background: transparent;")
        info.addWidget(self.kicker)
        info.addWidget(self.title)
        info.addWidget(self.subtitle)
        info.addSpacing(2)
        info.addWidget(self.status)
        info.addStretch(1)
        top.addLayout(info, 1)
        cl.addLayout(top)

        self.log = QPlainTextEdit(self.card)
        self.log.setReadOnly(True)
        self.log.setFixedHeight(244)
        self.log.setMaximumBlockCount(1200)
        self.log.setFont(theme.font(9, 400))
        self.log.setStyleSheet("""
            QPlainTextEdit {
                background: rgba(255, 255, 255, 148); border: 1px solid rgba(31,39,50,22);
                border-radius: 14px; color: #47505C; padding: 10px;
                selection-background-color: rgba(113,138,166,70);
            }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 3px; }
            QScrollBar::handle:vertical { background: rgba(31,39,50,34); border-radius: 3px; min-height: 24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.log.setPlainText("正在启动…")
        cl.addWidget(self.log)

        bottom = QHBoxLayout()
        bottom.setSpacing(9)
        self.hint = QLabel("操作完成后可关闭")
        self.hint.setFont(theme.font(9, 400))
        self.hint.setStyleSheet("color: #8B95A2; background: transparent;")
        bottom.addWidget(self.hint, 1)
        self.history_btn = GlassButton("历史记录", "secondary", "history", height=40, radius=13)
        self.history_btn.setFixedWidth(126)
        self.history_btn.hide()
        self.history_btn.clicked.connect(self._history)
        bottom.addWidget(self.history_btn)
        self.done_btn = GlassButton("完成", "primary", "check", height=40, radius=13)
        self.done_btn.setFixedWidth(106)
        self.done_btn.hide()
        self.done_btn.clicked.connect(self._close)
        bottom.addWidget(self.done_btn)
        cl.addLayout(bottom)

    def start(self, app: AppInfo, operation: str = "uninstall") -> None:
        self.running = True
        self.result = None
        self.operation = operation
        self.log.setPlainText("")
        self.ring.set_progress(0, "准备中")
        self.kicker.setText("正在处理")
        if operation == "self":
            self.title.setText("正在卸载本程序")
        elif operation == "uninstall":
            self.title.setText(f"正在卸载 {app.name}")
        else:
            self.title.setText("正在清理残留")
        self.subtitle.setText(f"{app.source} · {app.package}")
        self.status.setText("请不要关闭窗口 · 正在准备授权与清理计划")
        self.done_btn.hide()
        self.history_btn.hide()
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self._reposition()

    def set_progress(self, value: int, label: str) -> None:
        self.ring.set_progress(value, label)
        self.status.setText(label)

    def append_log(self, text: str) -> None:
        if not text:
            return
        self.log.appendPlainText(text)
        bar = self.log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def finish(self, result: dict) -> None:
        self.running = False
        self.result = result
        status = result.get("status")
        if status in ("success", "empty", "partial"):
            if status == "partial":
                self.kicker.setText("部分完成")
                if self.operation == "self":
                    self.title.setText("本程序已卸载")
                    self.status.setText(result.get("native_message") or "部分用户残留未清理")
                else:
                    self.title.setText("应用已卸载" if self.operation == "uninstall" else "部分残留未清理")
                    self.status.setText(result.get("cleanup_error") or "部分项目未能处理，请查看日志")
                self.hint.setText("已写入历史记录，可查看详情")
            else:
                self.kicker.setText("操作完成")
                if self.operation == "self":
                    self.title.setText("卸载完成")
                    self.status.setText(result.get("native_message") or "本程序已从系统中移除")
                    self.hint.setText("窗口即将关闭")
                else:
                    self.title.setText("卸载完成" if self.operation == "uninstall" else "清理完成")
                    if result.get("backup"):
                        self.status.setText("配置备份已保存，可在历史记录中恢复")
                    else:
                        self.status.setText("隔离的文件可在历史记录中恢复")
                    self.hint.setText("已写入本地历史记录")
            self.ring.set_progress(100, "完成" if status != "partial" else "部分完成")
        else:
            self.kicker.setText("需要处理")
            self.title.setText("操作未完成")
            self.ring.set_progress(100, "失败")
            self.status.setText(result.get("native_message") or "请查看日志")
            self.hint.setText("未对配置做进一步删除")
        self.done_btn.show()
        self.history_btn.show()

    def resizeEvent(self, e) -> None:
        self._reposition()
        super().resizeEvent(e)

    def _reposition(self) -> None:
        self.card.move((self.width() - self.card.width()) // 2,
                       max(12, (self.height() - self.card.height()) // 2))

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(234, 239, 245, 210))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    def _close(self) -> None:
        if self.running:
            return
        self.hide()
        self.closed.emit()

    def _history(self) -> None:
        self.hide()
        self.history_requested.emit()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape and not self.running:
            self._close()


class CleanupDialog(QDialog):
    """Confirm residual-only cleanup."""

    def __init__(self, app: AppInfo, count: int, size: int, mode: str,
                 provider: IconProvider, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFixedSize(500, 326 if mode == "permanent" else 288)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.surface = QWidget(self)
        self.layout.addWidget(self.surface)
        sl = QVBoxLayout(self.surface)
        sl.setContentsMargins(26, 22, 26, 20)
        sl.setSpacing(12)

        head = QHBoxLayout()
        icon = QLabel()
        icon.setFixedSize(48, 48)
        icon.setPixmap(provider.get(app, 48))
        head.addWidget(icon)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        t = _label("清理残留", 19, theme.TEXT, 650)
        t.setFont(theme.font(19, 650, display=True))
        s = _label(f"{app.name} 仍保留，只移除用户目录中的残留", 9, theme.TEXT_MUTED)
        titles.addWidget(t)
        titles.addWidget(s)
        head.addLayout(titles, 1)
        sl.addLayout(head)

        body = _label(
            f"将处理 {count} 个项目，共 {human_size(size)}。"
            + ("文件会进入隔离区，可从历史记录恢复。" if mode == "quarantine"
               else "文件将从原位置永久删除，配置会保存为恢复备份。"), 10, QColor("#5A6572"))
        sl.addWidget(body)
        if mode == "permanent":
            ack_row = QHBoxLayout()
            self.check = GlassCheck(self.surface)
            self.check.setChecked(False)
            ack = _label("我了解文件会从原位置删除，仅保留配置备份", 9, theme.TEXT_MUTED)
            ack_row.addWidget(self.check)
            ack_row.addWidget(ack, 1)
            sl.addLayout(ack_row)
        else:
            self.check = None
        sl.addStretch(1)
        actions = QHBoxLayout()
        actions.setSpacing(9)
        actions.addStretch(1)
        cancel = GlassButton("取消", "secondary", "", height=42, radius=13)
        cancel.setFixedWidth(108)
        cancel.clicked.connect(self.reject)
        self.confirm = GlassButton("开始清理", "primary", "broom", height=42, radius=13)
        self.confirm.setFixedWidth(142)
        self.confirm.clicked.connect(self.accept)
        if self.check is not None:
            self.confirm.setEnabled(False)
            self.check.toggled.connect(self.confirm.setEnabled)
        actions.addWidget(cancel)
        actions.addWidget(self.confirm)
        sl.addLayout(actions)

    def showEvent(self, e) -> None:
        super().showEvent(e)
        if self.parentWidget():
            pg = self.parentWidget().window()
            geo = self.frameGeometry()
            geo.moveCenter(pg.frameGeometry().center())
            self.move(geo.topLeft())

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.7, 0.7, -0.7, -0.7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(250, 251, 253, 248))
        p.drawRoundedRect(r, 16, 16)
        theme.paint_glass(p, r, 16, tint=QColor(theme.ACCENT), fill=1.0)
        p.setPen(QPen(QColor(31, 39, 50, 42), 1))
        p.drawRoundedRect(r, 16, 16)


class PurgeDialog(QDialog):
    """Irreversible quarantine purge confirmation."""

    def __init__(self, title: str, body: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFixedSize(478, 284)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.surface = QWidget(self)
        self.layout.addWidget(self.surface)
        sl = QVBoxLayout(self.surface)
        sl.setContentsMargins(26, 22, 26, 20)
        sl.setSpacing(10)
        t = _label(title, 18, theme.TEXT, 650)
        t.setFont(theme.font(18, 650, display=True))
        sl.addWidget(t)
        b = _label(body, 10, QColor("#5A6572"))
        sl.addWidget(b)
        warn = _label("此操作不可撤销。", 10, theme.DANGER, 600)
        sl.addWidget(warn)
        row = QHBoxLayout()
        self.check = GlassCheck(self.surface)
        self.check.setChecked(False)
        lab = _label("确认永久删除隔离文件与配置备份", 9, theme.TEXT_MUTED)
        row.addWidget(self.check)
        row.addWidget(lab, 1)
        sl.addLayout(row)
        sl.addStretch(1)
        actions = QHBoxLayout()
        actions.setSpacing(9)
        actions.addStretch(1)
        cancel = GlassButton("取消", "secondary", "", height=42, radius=13)
        cancel.setFixedWidth(106)
        cancel.clicked.connect(self.reject)
        self.confirm = GlassButton("永久删除", "danger", "trash", height=42, radius=13)
        self.confirm.setFixedWidth(132)
        self.confirm.setEnabled(False)
        self.confirm.clicked.connect(self.accept)
        self.check.toggled.connect(self.confirm.setEnabled)
        actions.addWidget(cancel)
        actions.addWidget(self.confirm)
        sl.addLayout(actions)

    def showEvent(self, e) -> None:
        super().showEvent(e)
        if self.parentWidget():
            pg = self.parentWidget().window()
            geo = self.frameGeometry()
            geo.moveCenter(pg.frameGeometry().center())
            self.move(geo.topLeft())

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.7, 0.7, -0.7, -0.7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(250, 251, 253, 248))
        p.drawRoundedRect(r, 16, 16)
        theme.paint_glass(p, r, 16, tint=QColor(theme.DANGER), fill=1.0)
        p.setPen(QPen(QColor(31, 39, 50, 42), 1))
        p.drawRoundedRect(r, 16, 16)


class SelfUninstallDialog(QDialog):
    """Confirmation for removing Miaomiao itself."""

    def __init__(self, version: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFixedWidth(560)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.surface = QWidget(self)
        self.layout.addWidget(self.surface)
        sl = QVBoxLayout(self.surface)
        sl.setContentsMargins(28, 24, 28, 22)
        sl.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(14)
        icon = QLabel()
        icon.setFixedSize(54, 54)
        pix = QPixmap(str(theme.ASSETS / "icon-256.png"))
        if not pix.isNull():
            icon.setPixmap(pix.scaled(54, 54, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation))
        head.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        t = _label("卸载喵喵", 20, theme.TEXT, 650)
        t.setFont(theme.font(20, 650, display=True))
        s = _label(f"喵喵 Miaomiao {version}  ·  Debian 系统包", 10, theme.TEXT_MUTED)
        titles.addWidget(t)
        titles.addWidget(s)
        titles.addStretch(1)
        head.addLayout(titles, 1)
        sl.addLayout(head)

        intro = _label(
            "将从系统中移除喵喵、关闭当前窗口，并清理本程序写入用户目录的数据。"
            " 此操作需要 Polkit 系统授权。", 10, QColor("#5A6572"))
        sl.addWidget(intro)

        data_row = QHBoxLayout()
        self.data_check = GlassCheck(self.surface)
        self.data_check.setChecked(True)
        data_label = _label("同时删除历史记录、隔离区与配置备份", 10, theme.TEXT_SOFT, 500)
        data_row.addWidget(self.data_check)
        data_row.addWidget(data_label, 1)
        sl.addLayout(data_row)

        self.data_note = _label(
            "注意：隔离区和配置备份中可能包含其他应用的恢复数据，删除后不可恢复。",
            9, QColor("#8A6448"))
        self.data_note.setContentsMargins(30, 0, 0, 0)
        sl.addWidget(self.data_note)
        self.data_check.toggled.connect(self._on_data_toggled)

        ack_row = QHBoxLayout()
        self.ack = GlassCheck(self.surface)
        self.ack.setChecked(False)
        ack_label = _label("我确认从系统中卸载喵喵", 9, theme.TEXT_MUTED)
        ack_row.addWidget(self.ack)
        ack_row.addWidget(ack_label, 1)
        sl.addLayout(ack_row)

        sl.addStretch(1)
        actions = QHBoxLayout()
        actions.setSpacing(9)
        actions.addStretch(1)
        cancel = GlassButton("取消", "secondary", "", height=44, radius=14)
        cancel.setFixedWidth(110)
        cancel.clicked.connect(self.reject)
        self.confirm = GlassButton("卸载喵喵", "danger", "trash", height=44, radius=14)
        self.confirm.setFixedWidth(154)
        self.confirm.setEnabled(False)
        self.confirm.clicked.connect(self.accept)
        self.ack.toggled.connect(self.confirm.setEnabled)
        actions.addWidget(cancel)
        actions.addWidget(self.confirm)
        sl.addLayout(actions)
        self.adjustSize()

    def _on_data_toggled(self, checked: bool) -> None:
        self.data_note.setVisible(checked)

    def remove_data(self) -> bool:
        return self.data_check.isChecked()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        if self.parentWidget():
            pg = self.parentWidget().window()
            geo = self.frameGeometry()
            geo.moveCenter(pg.frameGeometry().center())
            self.move(geo.topLeft())

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.7, 0.7, -0.7, -0.7)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(250, 251, 253, 248))
        p.drawRoundedRect(r, 16, 16)
        theme.paint_glass(p, r, 16, tint=QColor(theme.DANGER), fill=1.0)
        p.setPen(QPen(QColor(31, 39, 50, 42), 1))
        p.drawRoundedRect(r, 16, 16)
