#!/usr/bin/env python3
"""喵喵 / Miaomiao entry point."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Keep all application data inside the project folder.
BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

from glass_uninstaller import i18n, theme
from glass_uninstaller.window import MainWindow


def cleanup_legacy_user_files() -> None:
    """Remove launchers and cache left by 1.1.x (user-scoped only)."""
    home = Path.home()
    for path in (
        home / ".local/share/applications/liquid-uninstaller.desktop",
        home / "Desktop/Liquid Uninstaller.desktop",
        home / "Desktop/GlassUninstaller.desktop",
    ):
        try:
            if path.is_symlink():
                path.unlink()
            elif path.is_file():
                text = path.read_text(encoding="utf-8", errors="ignore")
                if "liquid-uninstaller" in text or "glass-uninstaller" in text:
                    path.unlink()
        except OSError:
            pass
    for cache in (home / ".cache/liquid-uninstaller",):
        try:
            if cache.is_dir():
                shutil.rmtree(cache)
        except OSError:
            pass


def main() -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    cleanup_legacy_user_files()
    app = QApplication(sys.argv)
    i18n.install()
    app.setApplicationName("miaomiao")
    app.setApplicationDisplayName("Miaomiao" if i18n.EN else "喵喵")
    app.setDesktopFileName("miaomiao")
    app.setApplicationVersion("1.6.0")
    app.setOrganizationName("Miaomiao")
    app.setStyle("Fusion")
    app.setFont(theme.font(11, 400))
    window = MainWindow()
    window.show()

    shot = os.environ.get("GLASS_SCREENSHOT", "")
    if shot:
        delay = int(os.environ.get("GLASS_SCREENSHOT_DELAY", "7000"))
        def capture() -> None:
            window.grab().save(shot)
            app.quit()
        QTimer.singleShot(delay, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
