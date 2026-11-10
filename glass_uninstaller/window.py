"""Main window orchestration."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve, QObject, QPoint, QPropertyAnimation, QRect, QRectF, Qt,
    QThread, QTimer, QUrl, pyqtProperty, pyqtSignal,
)
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QKeyEvent, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMainWindow,
    QStackedWidget, QVBoxLayout, QWidget,
)

from . import __version__, theme
from .backend import (
    APP_DIR, DATA_DIR, SELF_PACKAGE, AppCatalog, AppInfo, CleanupWorker,
    HistoryStore, ProcessInfo, ScanResult, SelfUninstallWorker,
    UninstallOptions, UninstallWorker, build_plan, cancel_native_scans,
    human_size,
)
from .dialogs import (
    CleanupDialog, ConfirmDialog, ExecutionOverlay, PurgeDialog,
    SelfUninstallDialog,
)
from .pages import AppPage, HistoryPage, ResidualPage, Sidebar
from .widgets import (
    AmbientBackground, IconButton, IconProvider, IntroOverlay, Toast, WindowButton,
)


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

class ScanSignals(QObject):
    """Queued signal bridge for daemon scan threads (never a QThread)."""

    catalog_loaded = pyqtSignal(object, object)
    catalog_failed = pyqtSignal(str)
    detail_done = pyqtSignal(str, object, object, object)
    detail_failed = pyqtSignal(str, str)
    finished = pyqtSignal()


class CatalogJob:
    def __init__(self) -> None:
        self.signals = ScanSignals()
        self.thread = threading.Thread(
            target=self._run, name="miaomiao-catalog", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def _run(self) -> None:
        try:
            catalog = AppCatalog()
            apps = catalog.scan()
            self.signals.catalog_loaded.emit(catalog, apps)
        except Exception as exc:  # noqa: BLE001
            self.signals.catalog_failed.emit(str(exc))
        finally:
            self.signals.finished.emit()


class DetailScanJob:
    def __init__(self, catalog: AppCatalog, app: AppInfo) -> None:
        self.catalog = catalog
        self.app = app
        self.signals = ScanSignals()
        self.thread = threading.Thread(
            target=self._run, name="miaomiao-residual-scan", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def _run(self) -> None:
        try:
            scan = self.catalog.scan_residuals(self.app)
            deps = self.catalog.reverse_deps(self.app)
            procs = self.catalog.find_processes(self.app)
            self.signals.detail_done.emit(self.app.id, scan, deps, procs)
        except Exception as exc:  # noqa: BLE001
            self.signals.detail_failed.emit(self.app.id, str(exc))
        finally:
            self.signals.finished.emit()

# ---------------------------------------------------------------------------
# Window chrome
# ---------------------------------------------------------------------------

class Shell(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.radius = 0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.bg = AmbientBackground(self, radius=self.radius)
        self.bg.setGeometry(self.rect())
        self.bg.lower()

    def set_radius(self, radius: int) -> None:
        self.radius = radius
        self.bg.radius = radius
        self.bg.update()
        self.update()

    def resizeEvent(self, e) -> None:
        self.bg.setGeometry(self.rect())
        super().resizeEvent(e)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.6, 0.6, -0.6, -0.6)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 38), 1))
        p.drawRoundedRect(r, self.radius, self.radius)
        # inner top rim
        p.setPen(QPen(theme.HAIRLINE, 1))
        p.drawLine(int(r.left() + self.radius), 1,
                   int(r.right() - self.radius), 1)


class TitleBar(QWidget):
    minimize = pyqtSignal()
    maximize = pyqtSignal()
    close = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(56)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(32, 0, 20, 0)
        self.layout.setSpacing(8)
        dot = QLabel("●")
        dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        dot.setFont(theme.font(7, 600))
        dot.setStyleSheet("color: #718AA6; background: transparent;")
        self.layout.addWidget(dot)
        status = QLabel("喵喵 · 应用卸载与残留清理")
        status.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        status.setFont(theme.font(11, 500))
        status.setStyleSheet("color: #68737F; background: transparent;")
        self.layout.addWidget(status)
        self.layout.addStretch(1)
        for kind, signal in (("minimize", self.minimize),
                             ("maximize", self.maximize),
                             ("close", self.close)):
            btn = WindowButton(kind, self)
            btn.clicked.connect(signal)
            self.layout.addWidget(btn)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.maximize.emit()
        super().mouseDoubleClickEvent(e)




# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("喵喵")
        self.setWindowIcon(QIcon(str(theme.ASSETS / "icon-256.png")))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(1120, 740)
        self.resize(1280, 824)
        self._margin = 0
        self._dragging = False
        self._centered = False
        self._maximized = False
        self._open_played = False
        self._intro_t0 = 0.0
        self._intro_dismiss_pending = False
        self._exiting = False
        self._page_anim = None
        self._page_effect = None
        self.provider = IconProvider()
        self.catalog: AppCatalog | None = None
        self.apps: list[AppInfo] = []
        self.scan_cache: dict[str, tuple[ScanResult, list[str], list[ProcessInfo]]] = {}
        self._scan_pending: set[str] = set()
        self._scan_signals: set[QObject] = set()
        self._workers: set[QThread] = set()
        self._active_worker: QThread | None = None
        self._self_uninstalled = False
        self.history = HistoryStore()

        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.shell = Shell(self)
        self.outer.addWidget(self.shell)
        self.root = QVBoxLayout(self.shell)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(0)
        self.titlebar = TitleBar(self.shell)
        self.titlebar.minimize.connect(self.showMinimized)
        self.titlebar.maximize.connect(self.toggle_maximize)
        self.titlebar.close.connect(self.close)
        self.root.addWidget(self.titlebar)

        body = QHBoxLayout()
        body.setContentsMargins(14, 0, 14, 14)
        body.setSpacing(6)
        self.sidebar = Sidebar(self.shell)
        self.sidebar.page_requested.connect(self.navigate)
        body.addWidget(self.sidebar)
        self.stack = QStackedWidget(self.shell)
        self.stack.setStyleSheet("background: transparent;")
        self.app_page = AppPage(self.provider, self)
        self.residual_page = ResidualPage(self.provider, self)
        self.history_page = HistoryPage(self.provider, self)
        self.stack.addWidget(self.app_page)
        self.stack.addWidget(self.residual_page)
        self.stack.addWidget(self.history_page)
        body.addWidget(self.stack, 1)
        self.root.addLayout(body, 1)

        self.toast = Toast(self.shell)
        self.overlay = ExecutionOverlay(self.shell)
        self.overlay.hide()
        self.intro = IntroOverlay(self.shell)
        self._wire()

        self.catalog_loading = False
        self.setWindowOpacity(1.0)
        QTimer.singleShot(80, self.load_catalog)
        self.setMouseTracking(True)

    def _wire(self) -> None:
        self.app_page.refresh_requested.connect(self.load_catalog)
        self.app_page.scan_requested.connect(self.request_scan)
        self.app_page.uninstall_requested.connect(self.confirm_uninstall)
        self.app_page.residuals_requested.connect(self.open_residuals)
        self.sidebar.self_uninstall_requested.connect(self.self_uninstall)
        self.overlay.closed.connect(self._overlay_closed)
        self.residual_page.rescan_requested.connect(lambda app: self.request_scan(app, force=True))
        self.residual_page.cleanup_requested.connect(self.cleanup)
        self.history_page.restore_requested.connect(self.restore_record)
        self.history_page.purge_requested.connect(self.purge_record)
        self.history_page.open_data_requested.connect(self.open_data_dir)
        self.overlay.history_requested.connect(self._overlay_history)

    # -- catalog ----------------------------------------------------------
    def load_catalog(self) -> None:
        if self.catalog_loading or self._exiting:
            return
        self.catalog_loading = True
        self.app_page.refresh.setEnabled(False)
        self.app_page.subtitle.setText("正在读取 APT、Flatpak 与本地应用…")
        job = CatalogJob()
        self._scan_signals.add(job.signals)
        job.signals.catalog_loaded.connect(self._catalog_loaded)
        job.signals.catalog_failed.connect(self._catalog_failed)
        job.signals.finished.connect(lambda s=job.signals: self._scan_signals.discard(s))
        job.start()

    def _catalog_loaded(self, catalog: AppCatalog, apps: list[AppInfo]) -> None:
        if self._exiting:
            return
        self.catalog_loading = False
        self.catalog = catalog
        self.apps = apps
        self.scan_cache.clear()
        self._scan_pending.clear()
        self.app_page.refresh.setEnabled(True)
        self.app_page.set_catalog(catalog, apps)
        self._dismiss_intro()
        if not apps:
            self.app_page.detail.set_app(None)
            self._toast_after_intro("没有发现可管理的应用", "error")
        else:
            self._toast_after_intro(f"已载入 {len(apps)} 个可管理应用", "success")

    def _catalog_failed(self, message: str) -> None:
        if self._exiting:
            return
        self.catalog_loading = False
        self.app_page.refresh.setEnabled(True)
        self.app_page.subtitle.setText("读取失败，请重试")
        self.app_page.set_loading(False)
        self._dismiss_intro()
        self._toast_after_intro(f"读取软件列表失败：{message}", "error", 5000)

    def _toast_after_intro(self, text: str, kind: str = "info", duration: int = 2800) -> None:
        if self.intro.isVisible():
            QTimer.singleShot(500, lambda: self.toast.show_message(text, kind, duration))
        else:
            self.toast.show_message(text, kind, duration)

    def _dismiss_intro(self) -> None:
        if not self.intro.isVisible():
            self._intro_dismiss_pending = True
            return
        elapsed = time.monotonic() - self._intro_t0
        delay = max(0, int(900 - elapsed * 1000))
        QTimer.singleShot(delay, self.intro.dismiss)

    # -- scanning ---------------------------------------------------------
    def request_scan(self, app: AppInfo, force: bool = False) -> None:
        if app is None or self._exiting:
            return
        cached = self.scan_cache.get(app.id)
        if cached and not force:
            self._apply_scan(app, *cached)
            return
        if app.id in self._scan_pending or self.catalog is None:
            return
        self._scan_pending.add(app.id)
        self.residual_page.scan_state.set_text("扫描中…", theme.ACCENT)
        job = DetailScanJob(self.catalog, app)
        self._scan_signals.add(job.signals)
        job.signals.detail_done.connect(self._scan_done)
        job.signals.detail_failed.connect(self._scan_failed)
        job.signals.finished.connect(lambda s=job.signals: self._scan_signals.discard(s))
        job.start()

    def _scan_done(self, app_id: str, scan: ScanResult, deps: list[str],
                   procs: list[ProcessInfo]) -> None:
        if self._exiting:
            return
        self._scan_pending.discard(app_id)
        app = self.catalog.get(app_id) if self.catalog else None
        if app is None:
            return
        self.scan_cache[app_id] = (scan, deps, procs)
        self._apply_scan(app, scan, deps, procs)

    def _scan_failed(self, app_id: str, message: str) -> None:
        if self._exiting:
            return
        self._scan_pending.discard(app_id)
        self.toast.show_message(f"残留扫描失败：{message}", "error", 4200)
        if self.app_page.detail.app and self.app_page.detail.app.id == app_id:
            self.app_page.detail.set_scan_failed("扫描失败，已关闭自动清理")

    def _apply_scan(self, app: AppInfo, scan: ScanResult, deps: list[str],
                    procs: list[ProcessInfo]) -> None:
        if self._exiting:
            return
        if self.app_page.detail.app and self.app_page.detail.app.id == app.id:
            self.app_page.detail.set_details(deps, procs)
            self.app_page.detail.set_scan(scan)
        if self.residual_page.app and self.residual_page.app.id == app.id:
            self.residual_page.set_scan(scan)

    # -- navigation -------------------------------------------------------
    def navigate(self, index: int) -> None:
        if index == 0:
            app = self.app_page.detail.app
            cached = self.scan_cache.get(app.id) if app else None
            if app and cached:
                self.app_page.detail.set_scan(cached[0])
        if index == 1:
            app = self.app_page.detail.app
            if app is None:
                self.toast.show_message("请先选择一个应用", "info")
                self._select_nav(0)
                self.stack.setCurrentIndex(0)
                return
            self.residual_page.set_app(app)
            cached = self.scan_cache.get(app.id)
            if cached:
                self.residual_page.set_scan(cached[0])
            else:
                self.request_scan(app)
        if index == 2:
            self.history = HistoryStore()
            self.history_page.refresh(self.history.records)
        changing = self.stack.currentIndex() != index
        self.stack.setCurrentIndex(index)
        if changing:
            self._animate_page()

    def _select_nav(self, index: int) -> None:
        self.sidebar.set_index(index, emit=False)

    def switch_to(self, index: int) -> None:
        self._select_nav(index)
        self.navigate(index)

    def _animate_page(self) -> None:
        if self._page_anim is not None:
            self._page_anim.stop()
        if self._page_effect is not None:
            self.stack.setGraphicsEffect(None)
        effect = QGraphicsOpacityEffect(self.stack)
        effect.setOpacity(0.0)
        self.stack.setGraphicsEffect(effect)
        self._page_effect = effect
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(160)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: self._finish_page(effect))
        self._page_anim = anim
        anim.start()

    def _finish_page(self, effect) -> None:
        if self.stack.graphicsEffect() is effect:
            self.stack.setGraphicsEffect(None)
        self._page_effect = None
        self._page_anim = None

    def open_residuals(self) -> None:
        app = self.app_page.detail.app
        if app is None:
            return
        self.residual_page.set_app(app)
        cached = self.scan_cache.get(app.id)
        if cached:
            self.residual_page.set_scan(cached[0])
        else:
            self.request_scan(app)
        self.switch_to(1)

    def _overlay_history(self) -> None:
        self.switch_to(2)

    # -- uninstall --------------------------------------------------------
    def confirm_uninstall(self, app: AppInfo, options: UninstallOptions,
                          scan: ScanResult | None) -> None:
        if self.overlay.running:
            self.toast.show_message("已有操作正在进行", "info")
            return
        if app is None:
            return
        scan = scan or ScanResult()
        selected_paths = set(options.residual_ids)
        for item in scan.items:
            item.selected = item.path in selected_paths if options.clean_residuals else False
        cached = self.scan_cache.get(app.id)
        deps = cached[1] if cached else []
        procs = cached[2] if cached else []
        plan = build_plan(app, scan, options, deps, procs)
        dialog = ConfirmDialog(app, options, plan, self.provider, self)
        if dialog.exec() != int(dialog.DialogCode.Accepted):
            return
        selected = [i for i in scan.items if i.selected] if options.clean_residuals else []
        self.overlay.start(app, "uninstall")
        worker = UninstallWorker(app, options, selected, deps, self)
        worker.log.connect(self.overlay.append_log)
        worker.progress.connect(self.overlay.set_progress)
        worker.completed.connect(self._uninstall_done)
        worker.finished.connect(lambda w=worker: self._worker_finished(w))
        self._workers.add(worker)
        self._active_worker = worker
        worker.start()

    def _uninstall_done(self, result: dict) -> None:
        self.overlay.finish(result)
        app_dict = result.get("app", {})
        app_id = app_dict.get("id", "")
        self.scan_cache.pop(app_id, None)
        self.history = HistoryStore()
        native_ok = bool(result.get("native_ok"))
        if native_ok:
            self.apps = [a for a in self.apps if a.id != app_id]
            self.app_page.remove_app(app_id)
            self.residual_page.scan = None
            if result.get("status") == "success":
                self.toast.show_message(f"已卸载 {app_dict.get('name', '应用')}", "success")
            elif result.get("status") == "partial":
                self.toast.show_message("应用已卸载，但部分残留未清理", "error", 5000)
            else:
                self.toast.show_message("应用已移除，但清理过程出错", "error", 5000)
        else:
            self.toast.show_message(result.get("native_message") or "卸载未完成", "error", 5000)

    def _worker_finished(self, worker: QThread) -> None:
        self._workers.discard(worker)
        if self._active_worker is worker:
            self._active_worker = None

    # -- cleanup ----------------------------------------------------------
    def cleanup(self, app: AppInfo, items: list, mode: str) -> None:
        if self.overlay.running:
            self.toast.show_message("已有操作正在进行", "info")
            return
        count = len(items)
        size = sum(i.size for i in items)
        dialog = CleanupDialog(app, count, size, mode, self.provider, self)
        if dialog.exec() != int(dialog.DialogCode.Accepted):
            return
        for item in items:
            item.selected = True
        self.overlay.start(app, "cleanup")
        worker = CleanupWorker(app, items, mode, self)
        worker.log.connect(self.overlay.append_log)
        worker.progress.connect(self.overlay.set_progress)
        worker.completed.connect(self._cleanup_done)
        worker.finished.connect(lambda w=worker: self._worker_finished(w))
        self._workers.add(worker)
        self._active_worker = worker
        worker.start()

    def _cleanup_done(self, result: dict) -> None:
        self.overlay.finish(result)
        app_id = result.get("app", {}).get("id", "")
        self.scan_cache.pop(app_id, None)
        self.history = HistoryStore()
        if result.get("status") in ("success", "partial"):
            if result.get("status") == "partial":
                self.toast.show_message("部分残留未清理，可重新扫描后重试", "error", 5000)
            else:
                self.toast.show_message("残留清理完成", "success")
            QTimer.singleShot(200, lambda: self.request_scan(self.app_page.detail.app, force=True)
                              if self.app_page.detail.app and self.app_page.detail.app.id == app_id else None)
        else:
            self.toast.show_message(result.get("native_message") or "清理未完成", "error")

    # -- self uninstall ---------------------------------------------------
    def self_uninstall(self) -> None:
        if self.overlay.running:
            self.toast.show_message("已有操作正在进行", "info")
            return
        if self._self_uninstalled:
            return
        dialog = SelfUninstallDialog(__version__, self)
        if dialog.exec() != int(dialog.DialogCode.Accepted):
            return
        self_app = AppInfo(
            id="miaomiao", name="喵喵",
            version=__version__, source="系统", summary="",
            package=SELF_PACKAGE, icon=str(theme.ASSETS / "icon-256.png"),
        )
        self.overlay.start(self_app, "self")
        self.overlay.history_btn.hide()
        worker = SelfUninstallWorker(dialog.remove_data(), self)
        worker.log.connect(self.overlay.append_log)
        worker.progress.connect(self.overlay.set_progress)
        worker.completed.connect(self._self_uninstall_done)
        worker.finished.connect(lambda w=worker: self._worker_finished(w))
        self._workers.add(worker)
        self._active_worker = worker
        worker.start()

    def _self_uninstall_done(self, result: dict) -> None:
        self.overlay.finish(result)
        self.overlay.history_btn.hide()
        self.overlay.done_btn.setText("关闭")
        if result.get("status") in ("success", "partial"):
            self._self_uninstalled = True
            QTimer.singleShot(2800, self._finish_self_uninstall)

    def _finish_self_uninstall(self) -> None:
        if not self._self_uninstalled:
            return
        self.close()

    def _overlay_closed(self) -> None:
        if self._self_uninstalled:
            # Route through closeEvent so running worker threads are joined.
            self._finish_self_uninstall()

    # -- history ----------------------------------------------------------
    def restore_record(self, record_id: str) -> None:
        restored, skipped, errors = self.history.restore(record_id)
        self.history = HistoryStore()
        self.history_page.refresh(self.history.records)
        self.scan_cache.clear()
        if restored:
            self.toast.show_message(f"已恢复 {restored} 项"
                                    + (f"，跳过 {skipped} 项" if skipped else ""), "success")
        elif errors:
            self.toast.show_message(errors[0], "error", 4500)
        else:
            self.toast.show_message("没有可恢复的文件", "info")

    def purge_record(self, record_id: str) -> None:
        rec = self.history.get(record_id)
        if not rec:
            return
        app = rec.get("app", {}).get("name", "该应用")
        dialog = PurgeDialog("永久删除隔离文件",
                             f"{app} 的隔离文件与配置备份将被彻底删除，磁盘空间会被释放。",
                             self)
        if dialog.exec() != int(dialog.DialogCode.Accepted):
            return
        freed, errors = self.history.purge(record_id)
        self.history = HistoryStore()
        self.history_page.refresh(self.history.records)
        if errors:
            self.toast.show_message(errors[0], "error")
        else:
            self.toast.show_message(f"已释放 {human_size(freed)}", "success")

    def open_data_dir(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            DATA_DIR.chmod(0o700)
        except OSError:
            pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR)))

    # -- window chrome ----------------------------------------------------
    def toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self._maximized = False
        else:
            self.showMaximized()
            self._maximized = True
        self._update_radius()

    def _update_radius(self) -> None:
        maximized = self.isMaximized()
        self._margin = 0 if maximized else 12
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.shell.set_radius(0 if maximized else 30)

    def changeEvent(self, e) -> None:
        super().changeEvent(e)
        if e.type() == e.Type.WindowStateChange:
            self._update_radius()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        if not self._centered:
            self._centered = True
            screen = self.screen() or QApplication.primaryScreen()
            if screen:
                avail = screen.availableGeometry()
                target_w = max(self.minimumWidth(), min(1280, avail.width() - 36))
                target_h = max(self.minimumHeight(), min(824, avail.height() - 36))
                self.resize(target_w, target_h)
                geo = self.frameGeometry()
                geo.moveCenter(avail.center())
                self.move(geo.topLeft())
            self._play_open_animation()

    def _play_open_animation(self) -> None:
        """Show the fixed-size window with the glass intro; no live resizing.

        Animating QWidget.geometry() together with a translucent, animated
        background caused layout reflow and visible micro-stutter on KWin.
        The intro itself now carries the opening motion.
        """
        if self._open_played:
            return
        self._open_played = True
        self.setWindowOpacity(1.0)
        self._intro_t0 = time.monotonic()
        self.intro.setGeometry(self.shell.rect())
        self.intro.start()
        if self._intro_dismiss_pending:
            QTimer.singleShot(850, self.intro.dismiss)
        QTimer.singleShot(1350, self.intro.dismiss)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if self.toast.isVisible():
            self.toast._reposition()
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.shell.rect())
        if self.intro.isVisible():
            self.intro.setGeometry(self.shell.rect())

    def _prepare_exit(self) -> None:
        """Freeze timers and stop native scans before closing."""
        self._exiting = True
        cancel_native_scans()
        self.shell.bg.stop_animation()
        self.intro.stop_animation()
        self.app_page.loading.stop_animation()
        self.app_page._search_timer.stop()
        self.toast._timer.stop()

    def closeEvent(self, e) -> None:
        if self.overlay.running:
            e.ignore()
            self.toast.show_message("操作进行中，请等待完成", "info")
            return
        self._prepare_exit()
        for worker in list(self._workers):
            if worker.isRunning() and not worker.wait(8000):
                worker.terminate()
                worker.wait(1000)
        super().closeEvent(e)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if e.key() == Qt.Key.Key_F:
                self.app_page.search.edit.setFocus()
                self.app_page.search.edit.selectAll()
                return
            if e.key() == Qt.Key.Key_R:
                self.load_catalog()
                return
        super().keyPressEvent(e)

    def _edge_at(self, pos: QPoint):
        m = 14
        edges = Qt.Edge(0)
        if pos.x() <= m:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= self.width() - m:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= m:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= self.height() - m:
            edges |= Qt.Edge.BottomEdge
        return edges

    def mouseMoveEvent(self, e) -> None:
        if not self.isMaximized():
            edges = self._edge_at(e.position().toPoint())
            if edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge) and \
                    edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.unsetCursor()
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and not self.isMaximized():
            edges = self._edge_at(e.position().toPoint())
            if edges:
                handle = self.windowHandle()
                if handle and handle.startSystemResize(edges):
                    return
        super().mousePressEvent(e)

    def paintEvent(self, e) -> None:
        if self._margin <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Layered soft shadow around the floating shell.
        for i in range(self._margin + 3, 0, -1):
            alpha = max(0, int(1.9 * (self._margin + 3 - i)))
            p.setPen(QPen(QColor(0, 0, 0, alpha), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            r = QRectF(self.shell.geometry()).adjusted(-i, -i + 2, i, i + 2)
            p.drawRoundedRect(r, 30 + i, 30 + i)
