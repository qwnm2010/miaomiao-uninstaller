"""Core engine for 喵喵 (Miaomiao).

The backend deliberately limits destructive home-directory operations to:
  * exact matches for the selected application's identifiers;
  * paths owned by the current user and below $HOME;
  * explicit exclusions for shared XDG/system directories;
  * a quarantine-first workflow (restorable) by default.

System package removal is delegated to apt/flatpak/snap so their dependency
resolution and configuration purge rules remain authoritative.
"""

from __future__ import annotations

import configparser
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import tarfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from PyQt6.QtCore import QThread, pyqtSignal

try:
    from .native import native
except Exception:  # pragma: no cover - optional acceleration
    native = None

APP_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = APP_DIR / "assets"
HOME = Path(os.path.expanduser("~"))
UID = os.getuid()
XDG_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
DATA_DIR = Path(os.environ.get(
    "MIAOMIAO_DATA", XDG_DATA_HOME / "miaomiao"))
LEGACY_DATA_DIR = XDG_DATA_HOME / "liquid-uninstaller"
QUARANTINE_DIR = DATA_DIR / "quarantine"
BACKUP_DIR = DATA_DIR / "backups"
HISTORY_FILE = DATA_DIR / "history.json"
SELF_PACKAGE = "liquid-uninstaller"   # technical package id kept for upgrades
SELF_APP_NAME = "喵喵"

CRITICAL_PACKAGES = {
    "apt", "bash", "coreutils", "dpkg", "init", "libc6", "libc-bin",
    "login", "mount", "passwd", "perl-base", "python3", "python3-minimal",
    "sed", "sudo", "systemd", "systemd-sysv", "udev", "util-linux",
    "kali-linux", "kali-linux-core", "kali-linux-default",
    "kali-desktop-core", "kali-desktop-xfce", "kali-desktop-kde",
    "grub-common", "grub2-common", "grub-pc", "network-manager",
    "polkitd", "pkexec", "sddm", "lightdm", "xorg", "xserver-xorg",
    "python3-pyqt6", "python3-pyqt6.sip",
    "plasma-desktop", "xfce4", "xfce4-session", "kwin-x11", "kwin-wayland",
}
CRITICAL_PREFIXES = (
    "linux-image", "linux-headers", "linux-libc-dev", "firmware-",
    "nvidia-", "mesa-", "libc", "libqt", "libgtk",
)
GENERIC_PROCESS_NAMES = {
    "bash", "sh", "zsh", "python", "python3", "python3.14", "java", "node",
    "electron", "chrome_crashpad", "WebKitWebProcess", "xdg-open", "ps",
}

SHARED_NAMES = {
    "applications", "autostart", "icons", "fonts", "themes", "Trash", "trash",
    "dconf", "gconf", "gtk-2.0", "gtk-3.0", "gtk-4.0", "glib-2.0", "pulse",
    "pulseaudio", "fontconfig", "systemd", "user-dirs.dirs", "mimeapps.list",
    "recently-used.xbel", "kdeglobals", "kwinrc", "plasmashellrc", "katerc",
    "katevirc", "kded5rc", "kactivitymanagerdrc", "kactivitymanagerd-statsrc",
    "kwalletrc", "kwalletmanager5rc", "kioslaverc", "kglobalshortcutsrc",
    "kxkbrc", "klauncherrc", "krunnerrc", "ksmserverrc", "ksplashrc",
    "kwinrulesrc", "plasmanotifyrc", "powerdevilrc", "powermanagementprofilesrc",
    "spectaclerc", "dolphinrc", "konsolerc", "qt5ct", "qt6ct", "KDE",
    "kde.org", "session", "Trolltech.conf", "baloofilerc",
    "baloofileinformationrc", "gtkrc", "gtkrc-2.0", "user-dirs.locale",
    "plasma-localerc", "plasmaparc", "kwinoutputconfig.json",
    "pkgcache.bin", "srcpkgcache.bin", "mesa_shader_cache",
    "mesa_shader_cache_db", "fontconfig", "thumbnails", "event-sound-cache.tdb",
}
SHARED_PATH_FRAGMENTS = (
    "/.config/gtk-", "/.config/dconf", "/.config/pulse", "/.config/fontconfig",
    "/.config/systemd", "/.config/autostart", "/.config/KDE", "/.local/share/Trash",
    "/.local/share/icons", "/.local/share/fonts", "/.local/share/applications",
    "/.local/share/recently-used.xbel", "/.cache/fontconfig", "/.cache/thumbnails",
    "/.cache/mesa_shader_cache", "/.cache/pip", "/.cache/dconf",
)
ALIASES = {
    "firefox-esr": ["firefox", "mozilla"],
    "firefox": ["firefox", "mozilla"],
    "thunderbird": ["thunderbird"],
    "chromium": ["chromium"],
    "google-chrome-stable": ["google-chrome"],
    "code": ["code", "vscode"],
    "telegram-desktop": ["telegramdesktop", "telegram"],
    "org.telegram.desktop": ["telegramdesktop", "telegram"],
    "vlc": ["vlc"],
    "gimp": ["gimp"],
    "inkscape": ["inkscape"],
    "libreoffice": ["libreoffice"],
    "obs-studio": ["obs-studio"],
    "discord": ["discord"],
    "spotify-client": ["spotify"],
    "steam": ["steam"],
    "wireshark": ["wireshark"],
    "burpsuite": ["burpsuite"],
    "kate": ["kate"],
    "okular": ["okular"],
    "dolphin": ["dolphin"],
    "konsole": ["konsole"],
}
SOURCE_APT = "APT"
SOURCE_FLATPAK = "Flatpak"
SOURCE_SNAP = "Snap"
SOURCE_LOCAL = "本地"


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def human_size(num: int | float | None) -> str:
    if not num or num <= 0:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}" if value < 100 else f"{value:.0f} {unit}"
        value /= 1024
    return "—"


def parse_size(text: str) -> int:
    text = (text or "").strip().replace(",", ".")
    m = re.match(r"([\d.]+)\s*([KMGT]?i?B)", text, re.I)
    if not m:
        return 0
    value = float(m.group(1))
    unit = m.group(2).upper().replace("I", "")
    power = {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4}.get(unit, 0)
    return int(value * (1024 ** power))


def _run(cmd: list[str], timeout: float = 12.0, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env=env, errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 1, "", str(exc))


def _safe_under_home(path: Path) -> bool:
    try:
        resolved = path.resolve()
        home = HOME.resolve()
        return resolved == home or home in resolved.parents
    except OSError:
        return False


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").casefold())


def _parse_exec(exec_line: str) -> str:
    if not exec_line:
        return ""
    line = exec_line.strip()
    try:
        parts = shlex.split(line, posix=True)
    except ValueError:
        parts = line.split()
    for part in parts:
        if part.startswith("%") or "=" in part and not part.startswith("/"):
            continue
        if part.startswith("/") or "/" in part:
            return os.path.expanduser(part)
    return ""


def _read_desktop(path: Path) -> Optional[dict]:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            parser.read_file(fh)
        if not parser.has_section("Desktop Entry"):
            return None
        entry = dict(parser["Desktop Entry"])
    except (OSError, configparser.Error):
        return None
    if entry.get("Type", "Application") != "Application":
        return None
    if entry.get("Hidden", "").lower() == "true":
        return None
    return {
        "name": entry.get("Name", path.stem).strip(),
        "comment": (entry.get("Comment") or "").strip(),
        "icon": (entry.get("Icon") or "").strip(),
        "exec": (entry.get("Exec") or "").strip(),
        "exec_path": _parse_exec(entry.get("Exec") or ""),
        "startup_wm_class": (entry.get("StartupWMClass") or "").strip(),
        "categories": (entry.get("Categories") or "").strip(),
        "no_display": entry.get("NoDisplay", "").lower() == "true",
        "path": str(path),
        "terminal": entry.get("Terminal", "").lower() == "true",
    }


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class AppInfo:
    id: str
    name: str
    version: str
    source: str
    summary: str
    size: int = 0
    icon: str = ""
    kind: str = "gui"              # gui / cli
    package: str = ""
    desktop_file: str = ""
    desktop_files: list[str] = field(default_factory=list)
    exec_names: list[str] = field(default_factory=list)
    install_paths: list[str] = field(default_factory=list)
    protected: bool = False
    protection_reason: str = ""
    section: str = ""
    installation: str = "system"   # user / system
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "version": self.version,
            "source": self.source, "summary": self.summary, "size": self.size,
            "icon": self.icon, "kind": self.kind, "package": self.package,
            "desktop_file": self.desktop_file, "desktop_files": self.desktop_files,
            "exec_names": self.exec_names, "install_paths": self.install_paths,
            "protected": self.protected, "protection_reason": self.protection_reason,
            "section": self.section, "installation": self.installation,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AppInfo":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class ResidualItem:
    path: str
    category: str
    safety: str          # safe / review
    reason: str
    size: int = 0
    selected: bool = True
    kind: str = "dir"    # dir / file / link

    @property
    def name(self) -> str:
        return Path(self.path).name

    def to_dict(self) -> dict:
        return {
            "path": self.path, "category": self.category, "safety": self.safety,
            "reason": self.reason, "size": self.size, "selected": self.selected,
            "kind": self.kind,
        }


@dataclass
class ScanResult:
    items: list[ResidualItem] = field(default_factory=list)
    excluded_shared: int = 0
    tokens: list[str] = field(default_factory=list)
    scanned_at: str = field(default_factory=utc_now)

    @property
    def total_size(self) -> int:
        return sum(i.size for i in self.items)


@dataclass
class ProcessInfo:
    pid: int
    name: str
    args: str


@dataclass
class UninstallOptions:
    clean_residuals: bool = True
    residual_ids: list[str] = field(default_factory=list)
    mode: str = "quarantine"       # quarantine / permanent
    remove_install_dir: bool = True
    auto_remove: bool = False
    kill_processes: bool = False


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class AppCatalog:
    def __init__(self) -> None:
        self.apps: list[AppInfo] = []
        self._rdeps_cache: dict[str, list[str]] = {}
        self._dpkg: dict[str, dict] = {}
        self._owners: Optional[dict[str, set[str]]] = None

    # -- scan -------------------------------------------------------------
    def scan(self) -> list[AppInfo]:
        self.apps = []
        self._scan_apt()
        self._scan_flatpak()
        self._scan_snap()
        self._scan_local()
        # User-installed applications first; distro packages after them.
        source_rank = {SOURCE_LOCAL: 0, SOURCE_FLATPAK: 1, SOURCE_SNAP: 2, SOURCE_APT: 3}
        self.apps.sort(key=lambda a: (source_rank.get(a.source, 9),
                                      0 if a.kind == "gui" else 1,
                                      a.name.casefold(), a.package.casefold()))
        return self.apps

    def _dpkg_rows(self) -> None:
        fmt = ("${Package}\t${Version}\t${Installed-Size}\t${Status}\t"
               "${Essential}\t${Priority}\t${Section}\t${binary:Summary}\n")
        out = _run(["dpkg-query", "-W", "-f=" + fmt], timeout=20).stdout
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 8:
                continue
            pkg, ver, size, status, essential, priority, section, summary = parts[:8]
            if "installed" not in status:
                continue
            self._dpkg[pkg] = {
                "version": ver,
                "size": int(size or 0) * 1024,
                "essential": essential.strip().lower() == "yes",
                "priority": priority.strip().lower(),
                "section": section.strip(),
                "summary": summary.strip(),
            }

    def _desktop_entries(self) -> tuple[dict[str, list[dict]], list[dict]]:
        """Return apt-owned entries and user entries."""
        system_paths = sorted(Path("/usr/share/applications").glob("*.desktop"))
        local_paths = sorted((HOME / ".local/share/applications").glob("*.desktop"))

        owners: dict[str, str] = {}
        chunks = [system_paths[i:i + 500] for i in range(0, len(system_paths), 500)]
        for chunk in chunks:
            proc = _run(["dpkg", "-S", *[str(p) for p in chunk]], timeout=20)
            for line in proc.stdout.splitlines():
                m = re.match(r"^(.+?):\s+(/.*)$", line)
                if m:
                    owners[m.group(2)] = m.group(1).split(",")[0].strip()
                elif ":" in line:
                    left, right = line.split(":", 1)
                    if right.strip().startswith("/"):
                        owners[right.strip()] = left.split(",")[0].strip()

        owned: dict[str, list[dict]] = {}
        for path in system_paths:
            entry = _read_desktop(path)
            if not entry or entry["no_display"]:
                continue
            owner = owners.get(str(path), "")
            if not owner:
                continue
            entry["owner"] = owner
            owned.setdefault(owner, []).append(entry)

        user_entries: list[dict] = []
        for path in local_paths:
            entry = _read_desktop(path)
            if entry and not entry["no_display"]:
                entry["owner"] = ""
                user_entries.append(entry)
        return owned, user_entries

    def _scan_apt(self) -> None:
        self._dpkg_rows()
        manual = set(_run(["apt-mark", "showmanual"], timeout=15).stdout.split())
        owned, _ = self._desktop_entries()

        packages: set[str] = set(manual)
        packages.update(owned.keys())
        for pkg in sorted(packages):
            info = self._dpkg.get(pkg)
            if not info or pkg == SELF_PACKAGE:
                continue
            if info["section"].startswith("libs"):
                continue
            if pkg.startswith("kcm_"):
                continue
            entries = [e for e in owned.get(pkg, []) if e.get("name")]
            entries.sort(key=lambda e: (
                0 if e.get("icon") else 1,
                0 if e.get("comment") else 1,
                0 if e.get("categories") else 1,
                len(e.get("name", "")),
            ))
            entry = entries[0] if entries else None
            name = entry["name"] if entry else pkg
            summary = (entry["comment"] if entry and entry["comment"] else info["summary"]) or "系统软件包"
            icon = (entry["icon"] if entry else "") or pkg
            desktop_files = [e["path"] for e in entries]
            execs = set()
            for e in entries:
                if e.get("exec_path"):
                    execs.add(Path(e["exec_path"]).name)
            execs.add(pkg)
            if pkg.startswith("kali-") and pkg.endswith("-tools"):
                pass
            essential = info["essential"] or info["priority"] in {"required", "important"}
            protected = essential or pkg in CRITICAL_PACKAGES or pkg.startswith(CRITICAL_PREFIXES)
            reason = ""
            if info["essential"]:
                reason = "系统必需软件包"
            elif info["priority"] in {"required", "important"}:
                reason = f"系统 {info['priority']} 优先级"
            elif pkg in CRITICAL_PACKAGES or pkg.startswith(CRITICAL_PREFIXES):
                reason = "系统关键组件"
            install_paths = []
            if desktop_files:
                install_paths.extend(desktop_files[:2])
            app = AppInfo(
                id=f"apt:{pkg}", name=name, version=info["version"], source=SOURCE_APT,
                summary=summary, size=info["size"], icon=icon,
                kind="gui" if entries else "cli", package=pkg,
                desktop_file=(entries[0]["path"] if entries else ""),
                desktop_files=desktop_files, exec_names=sorted(x for x in execs if x),
                install_paths=install_paths, protected=protected,
                protection_reason=reason, section=info["section"],
            )
            self.apps.append(app)

    def _scan_flatpak(self) -> None:
        proc = _run(["flatpak", "list", "--app", "--columns=application,name,version,size,origin,installation"],
                    timeout=15)
        if proc.returncode != 0:
            return
        for line in proc.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) < 6:
                continue
            app_id, name, version, size, origin, installation = fields[:6]
            if not app_id:
                continue
            self.apps.append(AppInfo(
                id=f"flatpak:{app_id}", name=name or app_id, version=version or "—",
                source=SOURCE_FLATPAK, summary=f"Flatpak · {origin or '仓库'}",
                size=parse_size(size), icon=app_id, kind="gui", package=app_id,
                exec_names=[app_id.split(".")[-1]], install_paths=[
                    str(HOME / ".var/app" / app_id) if installation == "user"
                    else f"/var/lib/flatpak/app/{app_id}"
                ], installation=installation or "system",
            ))

    def _scan_snap(self) -> None:
        if not shutil.which("snap"):
            return
        proc = _run(["snap", "list"], timeout=12)
        if proc.returncode != 0:
            return
        for line in proc.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) < 2:
                continue
            name, version = parts[0], parts[1]
            self.apps.append(AppInfo(
                id=f"snap:{name}", name=name.replace("-", " ").title(),
                version=version, source=SOURCE_SNAP, summary="Snap 软件包",
                size=0, icon=name, kind="gui", package=name,
                exec_names=[name], install_paths=[f"/snap/{name}"],
                installation="system",
            ))

    def _scan_local(self) -> None:
        local_paths = sorted((HOME / ".local/share/applications").glob("*.desktop"))
        seen_paths: set[str] = set()
        for path in local_paths:
            entry = _read_desktop(path)
            if not entry or entry["no_display"]:
                continue
            exec_path = entry.get("exec_path", "")
            if not exec_path:
                continue
            target = Path(exec_path)
            if not _safe_under_home(target) or not target.exists():
                continue
            app_dir, bundle = self._local_root(target, entry["name"])
            if not app_dir:
                continue
            if str(app_dir) in seen_paths or str(target) in seen_paths:
                continue
            seen_paths.add(str(app_dir))
            seen_paths.add(str(target))
            name = entry["name"] or app_dir.name
            icon = entry["icon"]
            if not icon:
                icon = str(app_dir)
            size = _quick_size(app_dir)
            self.apps.append(AppInfo(
                id=f"local:{app_dir if app_dir.is_dir() else target}",
                name=name, version="用户安装", source=SOURCE_LOCAL,
                summary=entry["comment"] or "本地用户应用",
                size=size, icon=icon, kind="gui", package=str(target),
                desktop_file=str(path), desktop_files=[str(path)],
                exec_names=sorted({target.name, entry.get("startup_wm_class", "")} - {""}),
                install_paths=[str(app_dir if app_dir.is_dir() else target)],
                installation="user",
                extra={"local_root": str(app_dir), "exec_path": str(target),
                       "is_dir": app_dir.is_dir(), "bundle": bundle},
            ))

        # Standalone AppImages without desktop integration
        roots = [HOME / "Applications", HOME / "Downloads", HOME / "bin", HOME / ".local/bin"]
        for root in roots:
            if not root.is_dir():
                continue
            try:
                candidates = list(root.glob("*.AppImage"))[:40]
            except OSError:
                continue
            for target in candidates:
                if str(target) in seen_paths or not target.is_file():
                    continue
                seen_paths.add(str(target))
                self.apps.append(AppInfo(
                    id=f"local:{target}", name=target.stem.replace("-", " ").replace("_", " "),
                    version="AppImage", source=SOURCE_LOCAL, summary="便携式 AppImage",
                    size=target.stat().st_size, icon=str(target), kind="gui",
                    package=str(target), exec_names=[target.name],
                    install_paths=[str(target)], installation="user",
                    extra={"local_root": str(target), "exec_path": str(target),
                           "is_dir": False, "bundle": False},
                ))

    @staticmethod
    def _local_root(exec_path: Path, app_name: str = "") -> tuple[Optional[Path], bool]:
        """Return the safe removal root and whether it is a self-contained bundle.

        A desktop entry may point at one script in a shared folder. Recursively
        deleting that folder would be dangerous, so a directory is only treated
        as a bundle when its name matches the executable or the desktop Name.
        """
        if not _safe_under_home(exec_path):
            return None, False
        forbidden = {
            HOME, HOME / "Desktop", HOME / "Downloads", HOME / "Documents",
            HOME / "Pictures", HOME / "Music", HOME / "Videos", HOME / "Public",
            HOME / "Templates", HOME / ".local", HOME / ".local/bin",
            HOME / ".config", APP_DIR, DATA_DIR,
        }
        parent = exec_path.parent
        if parent in forbidden or APP_DIR in parent.parents or parent == APP_DIR \
                or DATA_DIR in parent.parents or parent == DATA_DIR:
            if exec_path.is_file() and exec_path.suffix == ".AppImage":
                return exec_path, False
            return None, False
        if len(parent.parts) - len(HOME.parts) < 1:
            return None, False
        if exec_path.suffix == ".AppImage":
            return exec_path, False
        if not parent.is_dir():
            return exec_path, False
        pn = normalize(parent.name)
        en = normalize(exec_path.name)
        nn = normalize(app_name)
        related = bool(
            (pn and en and (pn == en or pn.startswith(en) or en.startswith(pn)))
            or (pn and nn and pn == nn)
        )
        # Avoid extremely broad matches such as "app" or "bin" claiming a folder.
        if related and min(len(pn), len(en)) >= 3:
            return parent, True
        return exec_path, False

    # -- details ----------------------------------------------------------
    def get(self, app_id: str) -> Optional[AppInfo]:
        return next((a for a in self.apps if a.id == app_id), None)

    def reverse_deps(self, app: AppInfo) -> list[str]:
        if app.source != SOURCE_APT:
            return []
        if app.package in self._rdeps_cache:
            return self._rdeps_cache[app.package]
        proc = _run(["apt-cache", "rdepends", "--installed", "--no-recommends",
                     "--no-suggests", app.package], timeout=10)
        deps: list[str] = []
        if proc.returncode == 0:
            active = False
            for raw in proc.stdout.splitlines():
                if raw.strip().startswith("Reverse Depends:"):
                    active = True
                    continue
                if not active:
                    continue
                name = raw.strip().strip("|").strip()
                if not name or name == app.package:
                    continue
                if re.match(r"^[a-zA-Z0-9+.:_-]+$", name):
                    deps.append(name)
        deps = sorted(set(deps))
        self._rdeps_cache[app.package] = deps
        return deps

    def install_size(self, app: AppInfo) -> int:
        if app.size:
            return app.size
        paths = [Path(p) for p in app.install_paths[:4]]
        if native is not None and native.available and paths:
            result = native.paths_size(paths, 2500)
            if result is not None:
                return result
        return sum(_quick_size(path) for path in paths)

    # -- residuals --------------------------------------------------------
    def _owner_index(self) -> dict[str, set[str]]:
        if self._owners is not None:
            return self._owners
        owners: dict[str, set[str]] = {}

        def add(value: str, app_id: str) -> None:
            token = normalize(value)
            if len(token) >= 4:
                owners.setdefault(token, set()).add(app_id)

        for other in self.apps:
            add(other.package, other.id)
            add(other.name, other.id)
            for path in other.desktop_files:
                add(Path(path).stem, other.id)
            for name in other.exec_names:
                add(name, other.id)
            for path in other.install_paths:
                add(Path(path).name, other.id)
        self._owners = owners
        return owners

    def scan_residuals(self, app: AppInfo) -> ScanResult:
        scan = ResidualScanner().scan(app)
        if not self.apps:
            return scan
        owners = self._owner_index()
        for item in scan.items:
            other_ids = owners.get(normalize(Path(item.path).name), set()) - {app.id}
            if other_ids and item.safety == "safe":
                names = [a.name for a in self.apps if a.id in other_ids][:2]
                item.safety = "review"
                item.selected = False
                item.reason = "可能与其他应用共享" + ("（" + "、".join(names) + "）" if names else "")
        return scan

    def find_processes(self, app: AppInfo) -> list[ProcessInfo]:
        names = {normalize(n) for n in app.exec_names if n}
        names.add(normalize(Path(app.package).name))
        if app.desktop_file:
            names.add(normalize(Path(app.desktop_file).stem))
        names.update(normalize(x) for x in (app.extra.get("startup_wm_class", ""),))
        names = {n for n in names if len(n) >= 3 and n not in GENERIC_PROCESS_NAMES}
        if not names:
            return []
        proc = _run(["ps", "-u", str(UID), "-o", "pid=,comm=,args="], timeout=8)
        result: list[ProcessInfo] = []
        for line in proc.stdout.splitlines():
            parts = line.strip().split(None, 2)
            if len(parts) < 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            if pid == os.getpid():
                continue
            comm, args = parts[1], (parts[2] if len(parts) > 2 else "")
            norm_comm = normalize(comm)
            exe_name = normalize(Path(args.split()[0]).name) if args else ""
            if norm_comm in names or exe_name in names:
                if norm_comm in GENERIC_PROCESS_NAMES:
                    continue
                result.append(ProcessInfo(pid, comm, args[:220]))
            if len(result) >= 20:
                break
        return result


# ---------------------------------------------------------------------------
# Residual scanner
# ---------------------------------------------------------------------------

def cancel_native_scans() -> None:
    if native is not None and native.available:
        native.cancel()


def _quick_size(path: Path, deadline_seconds: float = 2.0) -> int:
    if native is not None and native.available:
        result = native.dir_size(path, max(1, int(deadline_seconds * 1000)))
        if result is not None:
            return result
    try:
        st = path.lstat()
    except OSError:
        return 0
    if path.is_symlink():
        return st.st_size
    if not path.is_dir():
        return st.st_size
    total = 0
    deadline = time.monotonic() + deadline_seconds
    try:
        for root, dirs, files in os.walk(path, followlinks=False):
            if time.monotonic() > deadline:
                break
            for d in list(dirs):
                if Path(root, d).is_symlink():
                    dirs.remove(d)
            for f in files:
                try:
                    total += os.lstat(os.path.join(root, f)).st_size
                except OSError:
                    continue
            if len(files) > 4000:
                break
    except (OSError, PermissionError):
        pass
    return total


class ResidualScanner:
    """Conservative, home-directory-only leftover detection."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = home or HOME
        self.config = Path(os.environ.get("XDG_CONFIG_HOME", self.home / ".config"))
        self.data = Path(os.environ.get("XDG_DATA_HOME", self.home / ".local/share"))
        self.state = Path(os.environ.get("XDG_STATE_HOME", self.home / ".local/state"))
        self.cache = Path(os.environ.get("XDG_CACHE_HOME", self.home / ".cache"))
        self.roots = [
            ("配置", self.config),
            ("数据", self.data),
            ("状态", self.state),
            ("缓存", self.cache),
            ("Flatpak 数据", self.home / ".var/app"),
            ("Snap 数据", self.home / "snap"),
        ]

    def _tokens(self, app: AppInfo) -> tuple[set[str], dict[str, str]]:
        """Return normalized tokens and token -> reason."""
        tokens: dict[str, str] = {}

        def add(value: str, reason: str = "") -> None:
            n = normalize(value)
            if len(n) >= 3 and n not in SHARED_NAMES:
                tokens.setdefault(n, reason)

        candidates = [app.package, app.name, getattr(app, "icon", "")]
        for path in app.desktop_files:
            candidates.append(Path(path).stem)
        candidates.extend(app.exec_names)
        for value in app.install_paths:
            candidates.append(Path(value).name)
        if app.extra.get("local_root"):
            candidates.append(Path(app.extra["local_root"]).name)
        if app.desktop_file:
            d = _read_desktop(Path(app.desktop_file)) if Path(app.desktop_file).exists() else None
            if d:
                candidates.extend([d.get("name", ""), d.get("startup_wm_class", "")])
        for value in list(candidates):
            if not value:
                continue
            add(value, "应用标识")
            low = value.casefold()
            for alias in ALIASES.get(low, []):
                add(alias, "已知应用别名")
            if app.source == SOURCE_FLATPAK:
                for part in value.split("."):
                    if len(part) >= 4:
                        add(part, "Flatpak 应用标识")
        # Local bundle name is a useful exact residual token.
        for value in (app.package, app.name):
            base = Path(value).name
            if base:
                add(base, "安装名称")
        return set(tokens), tokens

    def _classify(self, path: Path, tokens: set[str], exact: bool) -> tuple[str, str]:
        if any(frag in str(path) for frag in SHARED_PATH_FRAGMENTS):
            return "shared", "共享目录"
        if path.name in SHARED_NAMES or path.name.casefold() in {s.casefold() for s in SHARED_NAMES}:
            return "shared", "系统共享配置"
        if not _safe_under_home(path):
            return "shared", "不在用户主目录"
        if APP_DIR in path.parents or path == APP_DIR or DATA_DIR in path.parents or path == DATA_DIR:
            return "shared", "卸载器自身数据"
        if exact:
            return "safe", "与应用标识完全匹配"
        return "review", "名称相近，需要你确认"

    def scan(self, app: AppInfo) -> ScanResult:
        tokens, token_reasons = self._tokens(app)
        found: dict[str, ResidualItem] = {}
        excluded = 0

        scan_deadline = time.monotonic() + 6.0
        for category, root in self.roots:
            if not root.is_dir():
                continue
            try:
                entries = list(root.iterdir())
            except OSError:
                continue
            for entry in entries:
                try:
                    if not entry.exists() and not entry.is_symlink():
                        continue
                except OSError:
                    continue
                base_norm = normalize(entry.name)
                if not base_norm:
                    continue
                exact = base_norm in tokens
                pref = (not exact and len(base_norm) >= 4 and
                        any(len(t) >= 4 and (base_norm.startswith(t) or t.startswith(base_norm))
                            for t in tokens))
                if not exact and not pref:
                    continue
                if category == "Flatpak 数据" and base_norm not in tokens:
                    continue
                safety, reason = self._classify(entry, tokens, exact)
                if safety == "shared":
                    excluded += 1
                    continue
                if category == "Flatpak 数据" and app.source == SOURCE_FLATPAK:
                    safety, reason = "safe", "Flatpak 沙盒数据"
                try:
                    is_link = entry.is_symlink()
                    is_dir = entry.is_dir() and not is_link
                except OSError:
                    continue
                kind = "link" if is_link else ("dir" if is_dir else "file")
                if is_link or time.monotonic() > scan_deadline:
                    size = 0
                else:
                    size = _quick_size(entry, max(0.4, min(2.0, scan_deadline - time.monotonic())))
                found[str(entry)] = ResidualItem(
                    path=str(entry), category=category, safety=safety,
                    reason=reason, size=size, selected=(safety == "safe"), kind=kind,
                )

        # User-level desktop launchers and autostart entries are app-owned.
        desktop_stems = {normalize(Path(p).stem) for p in app.desktop_files}
        startup = normalize(app.extra.get("startup_wm_class", ""))
        for folder in (self.data / "applications", self.config / "autostart"):
            if not folder.is_dir():
                continue
            try:
                files = list(folder.glob("*.desktop"))
            except OSError:
                continue
            for entry in files:
                stem = normalize(entry.stem)
                exact = stem in desktop_stems or (startup and stem == startup)
                if not exact:
                    continue
                safety, reason = "safe", "用户桌面入口"
                if app.source == SOURCE_APT:
                    safety, reason = "review", "APT 包的本地桌面覆盖文件"
                if str(entry) not in found:
                    found[str(entry)] = ResidualItem(
                        path=str(entry), category="桌面入口", safety=safety,
                        reason=reason, size=_quick_size(entry),
                        selected=(safety == "safe"), kind="file",
                    )

        # A few conventional top-level app directories (e.g. ~/.mozilla).
        for entry in self.home.iterdir() if self.home.is_dir() else []:
            if not entry.name.startswith("."):
                continue
            base = normalize(entry.name)
            if base in tokens and entry.name not in SHARED_NAMES:
                safety, reason = self._classify(entry, tokens, True)
                if safety == "shared":
                    excluded += 1
                    continue
                if str(entry) not in found:
                    found[str(entry)] = ResidualItem(
                        path=str(entry), category="主目录",
                        safety=safety, reason=reason, size=_quick_size(entry),
                        selected=(safety == "safe"),
                        kind="link" if entry.is_symlink() else ("dir" if entry.is_dir() else "file"),
                    )

        items = sorted(found.values(), key=lambda i: (
            0 if i.safety == "safe" else 1,
            ["配置", "数据", "状态", "缓存", "Flatpak 数据", "Snap 数据", "桌面入口", "主目录"].index(i.category)
            if i.category in ["配置", "数据", "状态", "缓存", "Flatpak 数据", "Snap 数据", "桌面入口", "主目录"] else 9,
            i.path.casefold(),
        ))
        return ScanResult(items=items[:80], excluded_shared=excluded,
                          tokens=sorted(tokens))


# ---------------------------------------------------------------------------
# History / quarantine
# ---------------------------------------------------------------------------

def migrate_legacy_data() -> None:
    """Move 1.1.x data to the new Miaomiao location once, without data loss."""
    if DATA_DIR.exists() or not LEGACY_DATA_DIR.exists():
        return
    try:
        DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(LEGACY_DATA_DIR), str(DATA_DIR))
    except OSError:
        pass


class HistoryStore:
    def __init__(self) -> None:
        migrate_legacy_data()
        for directory in (DATA_DIR, QUARANTINE_DIR, BACKUP_DIR):
            directory.mkdir(parents=True, exist_ok=True)
            try:
                directory.chmod(0o700)
            except OSError:
                pass
        self.records: list[dict] = self._load()

    def _load(self) -> list[dict]:
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def save(self) -> None:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = HISTORY_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.records, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(HISTORY_FILE)

    def add(self, record: dict) -> None:
        self.records.insert(0, record)
        self.records = self.records[:100]
        self.save()

    def get(self, record_id: str) -> Optional[dict]:
        return next((r for r in self.records if r.get("id") == record_id), None)

    def update(self, record_id: str, **fields) -> None:
        rec = self.get(record_id)
        if rec:
            rec.update(fields)
            self.save()

    def restore(self, record_id: str) -> tuple[int, int, list[str]]:
        rec = self.get(record_id)
        if not rec:
            return 0, 0, ["记录不存在"]
        restored = skipped = 0
        errors: list[str] = []
        for item in rec.get("residuals", []):
            src = item.get("moved_to")
            dst = Path(item.get("path", ""))
            if not src or not dst:
                continue
            source = Path(src)
            if not _safe_under_home(source) or not _safe_under_home(dst):
                skipped += 1
                continue
            if not source.exists():
                skipped += 1
                continue
            if dst.exists() or dst.is_symlink():
                skipped += 1
                errors.append(f"目标已存在：{dst}")
                continue
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(dst))
                restored += 1
            except OSError as exc:
                errors.append(f"{dst}: {exc}")
        backup = rec.get("backup")
        backup_restored = 0
        if backup and Path(backup).exists():
            restored_backup, skipped_backup, backup_errors = self._restore_backup(Path(backup))
            backup_restored += restored_backup
            skipped += skipped_backup
            errors.extend(backup_errors)
        rec["restored_at"] = utc_now()
        self.save()
        return restored + backup_restored, skipped, errors

    def _restore_backup(self, archive: Path) -> tuple[int, int, list[str]]:
        """Restore a config archive without overwriting existing files."""
        restored = skipped = 0
        errors: list[str] = []
        try:
            with tarfile.open(archive, "r:gz") as tar:
                for member in tar.getmembers():
                    name = member.name.lstrip("/")
                    parts = Path(name).parts
                    if ".." in parts or not name:
                        skipped += 1
                        continue
                    dest = Path("/") / name
                    if not _safe_under_home(dest):
                        skipped += 1
                        continue
                    try:
                        if dest.exists() or dest.is_symlink():
                            skipped += 1
                            continue
                        if member.isdir():
                            dest.mkdir(parents=True, exist_ok=True)
                            continue
                        if member.isfile():
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            src = tar.extractfile(member)
                            if src is None:
                                skipped += 1
                                continue
                            with dest.open("wb") as out:
                                shutil.copyfileobj(src, out)
                            try:
                                dest.chmod(member.mode & 0o700)
                            except OSError:
                                pass
                            restored += 1
                        else:
                            # Never restore symlinks/devices from an archive.
                            skipped += 1
                    except OSError as exc:
                        errors.append(f"{dest}: {exc}")
        except (OSError, tarfile.TarError) as exc:
            errors.append(f"备份读取失败：{exc}")
        return restored, skipped, errors

    def purge(self, record_id: str) -> tuple[int, list[str]]:
        rec = self.get(record_id)
        if not rec:
            return 0, ["记录不存在"]
        freed = 0
        errors: list[str] = []
        qdir = rec.get("quarantine_dir")
        if qdir:
            qpath = Path(qdir)
            if qpath.exists() and _safe_under_home(qpath):
                freed += _quick_size(qpath, 8)
                try:
                    shutil.rmtree(qpath)
                except OSError as exc:
                    errors.append(str(exc))
        backup = rec.get("backup")
        if backup:
            bpath = Path(backup)
            if bpath.exists() and _safe_under_home(bpath):
                freed += bpath.stat().st_size
                try:
                    bpath.unlink()
                except OSError as exc:
                    errors.append(str(exc))
        rec["purged_at"] = utc_now()
        rec["quarantine_dir"] = ""
        rec["backup"] = ""
        for item in rec.get("residuals", []):
            item["moved_to"] = ""
        self.save()
        return freed, errors


def _unique_target(root: Path, relative: Path) -> Path:
    target = root / relative
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    for i in range(2, 1000):
        candidate = target.with_name(f"{stem}-{i}{suffix}")
        if not candidate.exists():
            return candidate
    return target.with_name(f"{stem}-{uuid.uuid4().hex[:6]}{suffix}")


def _archive(paths: Iterable[Path], dest: Path) -> int:
    """Create a tar.gz containing absolute home/residual paths."""
    count = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest, "w:gz", compresslevel=3) as tar:
        for path in paths:
            if not path.exists() and not path.is_symlink():
                continue
            try:
                tar.add(path, arcname=str(path).lstrip("/"), recursive=True)
                count += 1
            except (OSError, tarfile.TarError):
                continue
    try:
        dest.chmod(0o600)
    except OSError:
        pass
    return count


# ---------------------------------------------------------------------------
# Native uninstall helpers
# ---------------------------------------------------------------------------

def _elevated_command(cmd: list[str]) -> list[str]:
    if os.geteuid() == 0:
        return cmd
    return ["pkexec", "env", "DEBIAN_FRONTEND=noninteractive", *cmd]


class UninstallWorker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    completed = pyqtSignal(dict)

    def __init__(self, app: AppInfo, options: UninstallOptions,
                 items: list[ResidualItem], reverse_deps: list[str],
                 parent=None) -> None:
        super().__init__(parent)
        self.app = app
        self.options = options
        self.items = items
        self.reverse_deps = reverse_deps
        self._cancelled = False
        self._current: Optional[subprocess.Popen] = None
        self._cleanup_errors: list[str] = []
        self.store = HistoryStore()

    def cancel(self) -> None:
        self._cancelled = True

    def _emit_log(self, text: str) -> None:
        if text:
            self.log.emit(text.rstrip())

    def _stream(self, cmd: list[str], label: str, timeout: float = 900) -> int:
        self._emit_log(f"$ {' '.join(shlex.quote(c) for c in cmd)}")
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                bufsize=1, errors="replace",
            )
            self._current = proc
            assert proc.stdout is not None
            start = time.monotonic()
            for line in proc.stdout:
                self._emit_log(line.rstrip())
                if time.monotonic() - start > timeout:
                    proc.kill()
                    self._emit_log("命令超时，已终止。")
                    break
                if self._cancelled:
                    proc.terminate()
                    self._emit_log("操作已取消。")
                    break
            code = proc.wait()
            self._current = None
            return code
        except OSError as exc:
            self._current = None
            self._emit_log(f"启动失败：{exc}")
            return 127

    def _native_remove(self) -> tuple[bool, str]:
        app = self.app
        if app.protected:
            return False, app.protection_reason or "受保护的系统组件"
        if app.source == SOURCE_APT:
            methods = [["apt-get", "-y", "purge", app.package]]
            if self.options.auto_remove:
                methods.append(["apt-get", "-y", "autoremove", "--purge"])
            for cmd in methods:
                self.progress.emit(42, "正在调用 APT")
                code = self._stream(_elevated_command(cmd), "APT")
                if code != 0:
                    if code in (126, 127):
                        return False, "授权被取消或未找到 Polkit 认证代理（pkexec 返回 %d）" % code
                    return False, f"APT 返回错误码 {code}"
            return True, "APT 软件包已卸载"
        if app.source == SOURCE_FLATPAK:
            cmd = ["flatpak", "uninstall", "-y", "--delete-data", app.package]
            if app.installation == "system":
                cmd = _elevated_command(cmd)
            self.progress.emit(42, "正在卸载 Flatpak 应用")
            code = self._stream(cmd, "Flatpak")
            return (code == 0, "Flatpak 应用与沙盒数据已移除" if code == 0
                    else f"Flatpak 返回错误码 {code}")
        if app.source == SOURCE_SNAP:
            code = self._stream(_elevated_command(["snap", "remove", "--purge", app.package]), "Snap")
            return code == 0, "Snap 已移除" if code == 0 else f"Snap 返回错误码 {code}"
        if app.source == SOURCE_LOCAL:
            return self._remove_local()
        return False, "不支持的软件来源"

    def _remove_local(self) -> tuple[bool, str]:
        app = self.app
        root = Path(app.extra.get("local_root") or app.package)
        if not _safe_under_home(root) or root in (HOME, APP_DIR) or APP_DIR in root.parents:
            return False, "拒绝删除主目录或卸载器自身"
        forbidden_roots = {
            HOME, HOME / "Downloads", HOME / "Desktop", HOME / "Documents",
            HOME / "Pictures", HOME / "Music", HOME / "Videos", HOME / "Public",
            HOME / "Templates", HOME / ".local", HOME / ".local/bin",
            HOME / ".config", HOME / ".cache", APP_DIR, DATA_DIR,
        }
        if root in forbidden_roots:
            return False, "拒绝删除用户主目录或卸载器自身"
        if not self.options.remove_install_dir:
            self._emit_log("已保留应用安装目录。")
            return True, "已保留安装文件"
        try:
            self.progress.emit(45, "正在删除本地应用")
            bundle = bool(self.app.extra.get("bundle"))
            if root.is_symlink() or root.is_file():
                root.unlink()
            elif root.is_dir() and bundle:
                shutil.rmtree(root)
            elif root.is_dir():
                # Not a self-contained bundle: only remove the registered binary.
                target = Path(self.app.extra.get("exec_path") or self.app.package)
                if not _safe_under_home(target) or target.is_dir() or not target.exists():
                    return False, "该桌面入口指向共享目录，已拒绝递归删除"
                target.unlink()
                self._emit_log(f"已删除可执行文件：{target}")
                return True, "已删除本地可执行文件"
            self._emit_log(f"已删除安装位置：{root}")
            return True, "本地应用文件已删除"
        except OSError as exc:
            return False, f"删除安装目录失败：{exc}"

    def _kill_processes(self, procs: list[ProcessInfo]) -> None:
        for proc in procs:
            try:
                os.kill(proc.pid, signal.SIGTERM)
                self._emit_log(f"已请求结束进程 {proc.pid} ({proc.name})")
            except OSError as exc:
                self._emit_log(f"结束进程 {proc.pid} 失败：{exc}")

    def _clean_residuals(self, record_id: str) -> tuple[list[dict], int, str]:
        moved: list[dict] = []
        qdir = QUARANTINE_DIR / record_id
        backup_path = ""
        selected = [i for i in self.items if i.selected and Path(i.path).exists()]
        if not selected:
            return moved, 0, backup_path

        self._cleanup_errors = []
        if self.options.mode == "permanent":
            config_items = [Path(i.path) for i in selected if i.category in ("配置", "数据", "状态", "桌面入口")]
            if config_items:
                backup_path = str(BACKUP_DIR / f"{record_id}.tar.gz")
                try:
                    count = _archive(config_items, Path(backup_path))
                    self._emit_log(f"已备份 {count} 项配置到 {backup_path}")
                except (OSError, tarfile.TarError) as exc:
                    backup_path = ""
                    self._cleanup_errors.append(f"配置备份失败，已保留残留：{exc}")
                    self._emit_log(f"备份失败，已中止永久删除：{exc}")
                    return [], 0, ""

        total = 0
        for index, item in enumerate(selected, start=1):
            src = Path(item.path)
            if not src.exists() and not src.is_symlink():
                continue
            self.progress.emit(62 + int(index / max(1, len(selected)) * 28),
                               f"清理残留 {index}/{len(selected)}")
            try:
                size = _quick_size(src) if not src.is_symlink() else 0
                if self.options.mode == "quarantine":
                    target = _unique_target(qdir / item.category, Path(item.path).relative_to(HOME)
                                            if _safe_under_home(src) else Path(src.name))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(target))
                    moved.append({**item.to_dict(), "moved_to": str(target)})
                    self._emit_log(f"已隔离：{item.path}")
                else:
                    if src.is_symlink() or src.is_file():
                        src.unlink()
                    else:
                        shutil.rmtree(src)
                    moved.append({**item.to_dict(), "moved_to": ""})
                    self._emit_log(f"已删除：{item.path}")
                total += size
            except OSError as exc:
                self._cleanup_errors.append(f"{item.path}: {exc}")
                self._emit_log(f"清理失败 {item.path}：{exc}")
        return moved, total, backup_path

    def run(self) -> None:
        record_id = uuid.uuid4().hex[:12]
        result = {
            "id": record_id, "created_at": utc_now(), "app": self.app.to_dict(),
            "status": "failed", "native_ok": False, "native_message": "",
            "residuals": [], "mode": self.options.mode, "freed": 0,
            "quarantine_dir": "", "backup": "", "log": [],
            "reverse_deps": self.reverse_deps,
        }
        logs: list[str] = []
        self.log.connect(logs.append)
        try:
            self.progress.emit(4, "准备卸载")
            self._emit_log(f"目标：{self.app.name} · {self.app.source}")
            if self.app.protected:
                raise RuntimeError(self.app.protection_reason or "该应用受保护")
            if self.options.kill_processes:
                procs = AppCatalog().find_processes(self.app)
                self._kill_processes(procs)
                time.sleep(0.8)

            self.progress.emit(18, "正在卸载应用")
            ok, message = self._native_remove()
            result["native_ok"] = ok
            result["native_message"] = message
            if not ok:
                result["status"] = "failed"
                self._emit_log(f"卸载失败：{message}")
                self.progress.emit(100, "卸载失败")
                result["log"] = logs
                self.completed.emit(result)
                return

            moved: list[dict] = []
            freed = 0
            backup = ""
            if self.options.clean_residuals and self.items:
                self.progress.emit(58, "正在清理残留")
                moved, freed, backup = self._clean_residuals(record_id)
            else:
                self.progress.emit(88, "跳过残留清理")

            # For local apps, remove user desktop launchers now that the binary is gone.
            if self.app.source == SOURCE_LOCAL:
                for d in self.app.desktop_files:
                    dp = Path(d)
                    if _safe_under_home(dp) and dp.suffix == ".desktop":
                        try:
                            dp.unlink(missing_ok=True)
                            self._emit_log(f"已删除桌面入口：{dp}")
                        except OSError:
                            pass
                for entry in (self.app.extra.get("autostart_files") or []):
                    p = Path(entry)
                    if _safe_under_home(p):
                        try:
                            p.unlink(missing_ok=True)
                        except OSError:
                            pass

            result.update({
                "status": "partial" if self._cleanup_errors else "success",
                "residuals": moved, "freed": freed,
                "quarantine_dir": str(QUARANTINE_DIR / record_id) if self.options.mode == "quarantine" and moved else "",
                "backup": backup,
                "cleanup_error": "；".join(self._cleanup_errors[:3]),
            })
            result["log"] = logs
            self.store.add(result)
            self.progress.emit(100, "完成")
            self._emit_log(f"完成。{'已隔离 ' + str(len(moved)) + ' 项残留，' if moved else ''}"
                           f"{'已处理 ' + human_size(freed) if self.options.mode == 'permanent' else '可恢复'}。")
            result["log"] = logs
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001 - report to UI instead of crashing
            result["status"] = "failed"
            result["native_message"] = str(exc)
            self._emit_log(f"错误：{exc}")
            result["log"] = logs
            self.progress.emit(100, "失败")
            self.completed.emit(result)


class CleanupWorker(QThread):
    """Cleanup-only operation used by the residuals page."""

    log = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    completed = pyqtSignal(dict)

    def __init__(self, app: AppInfo, items: list[ResidualItem], mode: str,
                 parent=None) -> None:
        super().__init__(parent)
        self.app = app
        self.items = items
        self.mode = mode
        self.store = HistoryStore()

    def run(self) -> None:
        record_id = uuid.uuid4().hex[:12]
        logs: list[str] = []
        self.log.connect(logs.append)
        result = {
            "id": record_id, "created_at": utc_now(), "app": self.app.to_dict(),
            "status": "success", "native_ok": True,
            "native_message": "仅清理残留（应用保留）",
            "residuals": [], "mode": self.mode, "freed": 0,
            "quarantine_dir": "", "backup": "", "log": [], "reverse_deps": [],
        }
        try:
            selected = [i for i in self.items if i.selected and Path(i.path).exists()]
            if not selected:
                self.completed.emit({**result, "status": "empty", "log": ["没有可清理的项目"]})
                return
            backup = ""
            if self.mode == "permanent":
                config_items = [Path(i.path) for i in selected
                                if i.category in ("配置", "数据", "状态", "桌面入口")]
                if config_items:
                    backup = str(BACKUP_DIR / f"{record_id}.tar.gz")
                    _archive(config_items, Path(backup))
            moved = []
            total = 0
            qdir = QUARANTINE_DIR / record_id
            for index, item in enumerate(selected, start=1):
                src = Path(item.path)
                self.progress.emit(int(index / max(1, len(selected)) * 90),
                                   f"清理 {index}/{len(selected)}")
                try:
                    size = _quick_size(src) if not src.is_symlink() else 0
                    if self.mode == "quarantine":
                        target = _unique_target(qdir / item.category,
                                                Path(item.path).relative_to(HOME)
                                                if _safe_under_home(src) else Path(src.name))
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src), str(target))
                        moved.append({**item.to_dict(), "moved_to": str(target)})
                        self.log.emit(f"已隔离：{item.path}")
                    else:
                        if src.is_symlink() or src.is_file():
                            src.unlink()
                        else:
                            shutil.rmtree(src)
                        moved.append({**item.to_dict(), "moved_to": ""})
                        self.log.emit(f"已删除：{item.path}")
                    total += size
                except OSError as exc:
                    self.log.emit(f"失败 {item.path}：{exc}")
                    result["status"] = "partial"
            result.update({
                "residuals": moved, "freed": total,
                "quarantine_dir": str(qdir) if self.mode == "quarantine" and moved else "",
                "backup": backup,
            })
            self.store.add(result)
            self.progress.emit(100, "完成")
            self.completed.emit({**result, "log": logs})
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"错误：{exc}")
            self.progress.emit(100, "失败")
            self.completed.emit({**result, "status": "failed", "native_message": str(exc), "log": logs})


# ---------------------------------------------------------------------------
# Plan summary
# ---------------------------------------------------------------------------

def build_plan(app: AppInfo, scan: ScanResult, options: UninstallOptions,
               reverse_deps: list[str], processes: list[ProcessInfo]) -> dict:
    selected = [i for i in scan.items if i.selected] if options.clean_residuals else []
    size = sum(i.size for i in selected)
    steps = []
    if options.kill_processes and processes:
        steps.append(f"结束 {len(processes)} 个运行中的进程")
    if app.source == SOURCE_APT:
        steps.append(f"apt-get purge {app.package}")
        if options.auto_remove:
            steps.append("apt-get autoremove --purge")
    elif app.source == SOURCE_FLATPAK:
        steps.append(f"flatpak uninstall --delete-data {app.package}")
    elif app.source == SOURCE_SNAP:
        steps.append(f"snap remove {app.package}")
    else:
        steps.append("删除本地应用文件")
    if selected:
        label = "移至隔离区" if options.mode == "quarantine" else "永久删除"
        steps.append(f"{label} {len(selected)} 项残留")
    warnings = []
    if app.protected:
        warnings.append(app.protection_reason or "受保护的系统组件")
    if reverse_deps:
        warnings.append("有已安装软件依赖此包：" + "、".join(reverse_deps[:4]))
    if processes:
        warnings.append(f"检测到 {len(processes)} 个运行中的进程")
    return {
        "steps": steps, "warnings": warnings, "selected_count": len(selected),
        "size": size, "needs_auth": app.source in (SOURCE_APT, SOURCE_SNAP) or
        (app.source == SOURCE_FLATPAK and app.installation == "system"),
        "mode": options.mode,
    }


class SelfUninstallWorker(QThread):
    """Remove the installed package and its known user-level residue.

    Package files are removed by APT first. The currently running Python
    process keeps its loaded code in memory, so it can finish the UI flow and
    then exit cleanly. User data is deleted only after the package removal
    succeeds, unless the user explicitly chose to keep recovery data.
    """

    log = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    completed = pyqtSignal(dict)

    def __init__(self, remove_data: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.remove_data = remove_data
        self._proc: Optional[subprocess.Popen] = None

    def _stream(self, cmd: list[str]) -> int:
        self.log.emit("$ " + " ".join(shlex.quote(c) for c in cmd))
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                bufsize=1, errors="replace",
            )
            self._proc = proc
            assert proc.stdout is not None
            for line in proc.stdout:
                self.log.emit(line.rstrip())
            code = proc.wait()
            self._proc = None
            return code
        except OSError as exc:
            self._proc = None
            self.log.emit(f"启动失败：{exc}")
            return 127

    def _user_paths(self) -> list[Path]:
        paths = [
            HOME / ".local/share/applications/miaomiao.desktop",
            HOME / ".local/share/applications/liquid-uninstaller.desktop",
            HOME / ".local/share/applications/GlassUninstaller.desktop",
            HOME / "Desktop/Liquid Uninstaller.desktop",
            HOME / "Desktop/GlassUninstaller.desktop",
        ]
        if self.remove_data:
            paths.extend([
                DATA_DIR,
                LEGACY_DATA_DIR,
                HOME / ".cache/miaomiao",
                HOME / ".cache/liquid-uninstaller",
                HOME / ".config/miaomiao",
                HOME / ".config/liquid-uninstaller",
            ])
        return paths

    def _remove_user_paths(self) -> tuple[list[str], list[str]]:
        removed: list[str] = []
        errors: list[str] = []
        for path in self._user_paths():
            if not path.exists() and not path.is_symlink():
                continue
            if not _safe_under_home(path):
                errors.append(f"拒绝处理主目录外路径：{path}")
                continue
            try:
                if path.is_symlink() or path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
                removed.append(str(path))
                self.log.emit(f"已清理：{path}")
            except OSError as exc:
                errors.append(f"{path}: {exc}")
                self.log.emit(f"清理失败 {path}：{exc}")
        return removed, errors

    def run(self) -> None:
        result = {
            "status": "failed", "native_message": "", "removed": [],
            "errors": [], "remove_data": self.remove_data,
            "app": {
                "id": "miaomiao", "name": SELF_APP_NAME,
                "version": "1.5.0", "source": "系统", "summary": "",
                "package": SELF_PACKAGE, "icon": "",
            },
        }
        try:
            self.progress.emit(8, "检查安装状态")
            check = subprocess.run(
                ["dpkg-query", "-W", "-f=${Status}", SELF_PACKAGE],
                capture_output=True, text=True, timeout=10,
            )
            if check.returncode != 0 or "installed" not in check.stdout:
                result["native_message"] = "未检测到已安装的 liquid-uninstaller 系统包"
                self.progress.emit(100, "无法继续")
                self.completed.emit(result)
                return

            self.progress.emit(20, "等待 Polkit 授权")
            code = self._stream(_elevated_command(
                ["apt-get", "-y", "purge", SELF_PACKAGE]))
            if code != 0:
                result["native_message"] = (
                    "授权被取消或卸载失败（返回码 %d）" % code if code in (126, 127)
                    else f"apt-get 返回错误码 {code}")
                self.progress.emit(100, "卸载失败")
                self.completed.emit(result)
                return

            self.progress.emit(74, "清理用户残留")
            removed, errors = self._remove_user_paths()
            result["removed"] = removed
            result["errors"] = errors
            result["status"] = "partial" if errors else "success"
            result["native_message"] = (
                "系统包已卸载；部分用户残留未能清理" if errors
                else "系统包与用户残留已清理" if self.remove_data
                else "系统包已卸载；用户恢复数据按选择保留")
            self.progress.emit(100, "完成")
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001
            result["native_message"] = str(exc)
            result["errors"].append(str(exc))
            self.progress.emit(100, "失败")
            self.completed.emit(result)
