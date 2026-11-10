"""Locale selection and the Chinese-to-English interface catalog.

Language is selected from the system locale. MIAOMIAO_LANG can override it.
"""
from __future__ import annotations

import os
import re
from typing import Optional

_OVERRIDE = os.environ.get("MIAOMIAO_LANG", "").strip().lower()
_SYSTEM = (
    os.environ.get("LC_ALL")
    or os.environ.get("LC_MESSAGES")
    or os.environ.get("LANG")
    or ""
).strip().lower()

LANG = "zh" if (_OVERRIDE or _SYSTEM).startswith("zh") else "en"
EN = LANG == "en"


def is_en() -> bool:
    return EN


_EXACT = {
    # brand and navigation
    "喵喵": "Miaomiao",
    "应用卸载与残留清理": "Application uninstaller",
    "喵喵 · 应用卸载与残留清理": "Miaomiao · Application uninstaller",
    "应用程序": "Applications",
    "残留清理": "Residuals",
    "历史记录": "History",
    "隔离删除": "Quarantine-first",
    "残留先进入隔离区，可从历史记录恢复": "Residuals move to quarantine and can be restored from History",
    "卸载本程序": "Uninstall Miaomiao",
    "从系统中完整卸载喵喵并清理自身残留": "Remove Miaomiao and its user data",
    "应用卸载与残留清理": "Application uninstaller",
    # detail
    "选择一个应用": "Select an app",
    "从左侧选择应用，查看卸载范围与残留。": "Choose an app to inspect its removal scope and residuals.",
    "可卸载": "Removable",
    "本地": "Local",
    "系统": "System",
    "用户安装": "User install",
    "来源": "Source",
    "磁盘占用": "Disk usage",
    "版本": "Version",
    "检查中": "Checking",
    "正在检查": "Checking",
    "评估": "Assessment",
    "正在检查依赖与系统影响…": "Checking dependencies and system impact…",
    "分析依赖、运行进程与残留中": "Analyzing dependencies, processes and residuals",
    "卸载范围": "Removal scope",
    "清理配置与残留": "Clean configuration and residuals",
    "配置、本地数据、缓存": "Configuration, local data, cache",
    "移除不再需要的依赖": "Remove unneeded dependencies",
    "仅对 APT 软件包可用，由 apt 计算依赖关系": "APT packages only; apt resolves dependencies",
    "结束相关进程": "End related processes",
    "仅匹配当前用户下与该应用同名或同路径的进程": "Match same-user processes by name or path",
    "处理方式": "Handling",
    "可恢复": "Restorable",
    "移至隔离区": "Move to quarantine",
    "永久删除": "Delete permanently",
    "不保留": "No backup",
    "残留与配置": "Residuals & config",
    "等待扫描…": "Waiting for scan…",
    "正在扫描残留…": "Scanning residuals…",
    "正在扫描残留，请稍候…": "Scanning residuals. Please wait…",
    "查看全部残留与配置": "View all residuals and config",
    "卸载应用": "Uninstall app",
    "系统组件 · 已保护": "System component · Protected",
    "需要系统授权 · 由 Polkit 验证": "Polkit authorization required",
    "本地应用 · 无需系统授权": "Local app · No authorization required",
    "系统保护": "System protection",
    "需要复核": "Review required",
    "应用运行中": "App running",
    "存在依赖": "Dependencies",
    "未发现用户残留": "No user residuals found",
    "扫描失败": "Scan failed",
    "扫描失败，已关闭自动清理": "Scan failed; automatic cleanup disabled",
    "残留足迹": "Storage footprint",
    "扫描中": "Scanning",
    "已排除": "Excluded",
    "应用": "App",
    "残留": "Residual",
    "应用备份": "App backup",
    "读取应用清单": "Reading installed apps",
    "点击跳过": "Click to skip",
    "读取 / 本地软件包": "Reading / local packages",
    "需确认": "Review",
    "用户安装": "User install",
    "应用运行中": "App running",
    "系统组件 · 已保护": "System component · Protected",
    "只能卸载用户安装的本地应用": "Only user-installed local apps can be removed",
    "系统组件 · 已保护": "System component · Protected",
    # app page
    "已安装": "Installed",
    "全部": "All",
    "图形应用": "GUI apps",
    "没有匹配的应用": "No matching apps",
    "换一个来源筛选，或清除搜索关键词。": "Try another source filter or clear the search.",
    "APT · Flatpak · Snap · 本地": "APT · Flatpak · Snap · Local",
    "正在读取软件包…": "Reading packages…",
    "搜索应用或包名": "Search apps or packages",
    "重新扫描应用": "Rescan apps",
    "正在读取 APT、Flatpak 与本地应用…": "Reading APT, Flatpak and local apps…",
    "没有发现可管理的应用": "No manageable apps found",
    "读取失败，请重试": "Load failed. Try again.",
    "APT · Flatpak · Snap · 本地应用": "APT · Flatpak · Snap · Local",
    # residual page
    "精确匹配用户目录中的配置、数据与缓存": "Matches configuration, data and cache in your home folder",
    "重新扫描": "Rescan",
    "未选择应用": "No app selected",
    "返回应用页选择一个应用": "Return to Applications and select an app",
    "待扫描": "Pending scan",
    "扫描中…": "Scanning…",
    "扫描完成": "Scan complete",
    "检测到": "Detected",
    "可清理": "Cleanable",
    "共享保护": "Shared protected",
    "残留项目": "Residual items",
    "全选可清理": "Select cleanable",
    "这个应用很干净。共享目录与系统配置已自动排除。": "This app is clean. Shared folders and system configuration were excluded.",
    "共享目录、系统配置与其他应用可能共用的配置已自动排除": "Shared folders, system configuration and cross-app configuration are excluded",
    "已选择 0 项": "0 selected",
    "隔离区": "Quarantine",
    "清理所选": "Clean selected",
    "全选可清理": "Select cleanable",
    "没有发现用户残留": "No user residuals found",
    "没有需要清理的残留": "No residuals to clean",
    "共享目录、系统配置与其他应用可能共用的配置已自动排除": "Shared folders, system configuration and cross-app configuration are excluded",
    "移至隔离区后可恢复": "Restorable after quarantine",
    "删除后保留配置备份": "Configuration backup is kept",
    "返回应用页选择一个应用": "Return to Applications and select an app",
    "待扫描": "Pending scan",
    "扫描中…": "Scanning…",
    "扫描完成": "Scan complete",
    # history
    "隔离区内的文件可随时恢复": "Quarantined files can be restored at any time",
    "数据目录": "Data folder",
    "操作记录": "Operations",
    "隔离项目": "Quarantined items",
    "可恢复空间": "Recoverable space",
    "还没有卸载记录": "No removal history yet",
    "完成一次卸载后，操作记录和可恢复的隔离文件会出现在这里。": "Removal records and restorable quarantined files will appear here after the first removal.",
    "完成": "Done",
    "部分完成": "Partial",
    "失败": "Failed",
    "无项目": "Empty",
    "隔离": "Quarantined",
    "永久删除 · 备份": "Deleted · backup",
    "处理完成": "Completed",
    "应用备份": "App backup",
    "恢复": "Restore",
    "彻底删除": "Delete permanently",
    # dialogs
    "确认卸载": "Confirm removal",
    "请留意": "Note",
    "我已了解此操作的影响，并确认继续": "I understand the impact and want to continue",
    "取消": "Cancel",
    "正在处理": "Processing",
    "准备卸载": "Preparing removal",
    "请不要关闭窗口": "Do not close this window",
    "正在启动…": "Starting…",
    "操作完成后可关闭": "Close when finished",
    "准备中": "Preparing",
    "正在卸载本程序": "Removing Miaomiao",
    "正在清理残留": "Cleaning residuals",
    "请不要关闭窗口 · 正在准备授权与清理计划": "Do not close · preparing authorization and cleanup plan",
    "本程序已卸载": "Miaomiao removed",
    "部分用户残留未清理": "Some user residuals were not cleaned",
    "应用已卸载": "Application removed",
    "部分残留未清理": "Some residuals were not cleaned",
    "部分项目未能处理，请查看日志": "Some items could not be processed. Check the log.",
    "已写入历史记录，可查看详情": "Saved to History. Open it for details.",
    "操作完成": "Completed",
    "卸载完成": "Removal complete",
    "本程序已从系统中移除": "Miaomiao has been removed from the system",
    "窗口即将关闭": "This window will close",
    "清理完成": "Cleanup complete",
    "配置备份已保存，可在历史记录中恢复": "Configuration backup saved; restore it from History.",
    "隔离的文件可在历史记录中恢复": "Quarantined files can be restored from History.",
    "已写入本地历史记录": "Saved to local History.",
    "需要处理": "Action required",
    "操作未完成": "Operation incomplete",
    "请查看日志": "Check the log.",
    "未对配置做进一步删除": "No further configuration deletion was performed.",
    "清理残留": "Clean residuals",
    "我了解文件会从原位置删除，仅保留配置备份": "I understand files are deleted from their original location; only a configuration backup is kept.",
    "开始清理": "Start cleanup",
    "此操作不可撤销。": "This cannot be undone.",
    "确认永久删除隔离文件与配置备份": "Permanently delete quarantined files and configuration backup",
    "卸载喵喵": "Uninstall Miaomiao",
    "同时删除历史记录、隔离区与配置备份": "Also delete History, quarantine and configuration backups",
    "注意：隔离区和配置备份中可能包含其他应用的恢复数据，删除后不可恢复。": "Note: quarantine and backups may contain recovery data for other apps. This cannot be undone.",
    "我确认从系统中卸载喵喵": "I confirm removing Miaomiao from the system",
    "将从系统中移除喵喵、关闭当前窗口，并清理本程序写入用户目录的数据。 此操作需要 Polkit 系统授权。":
        "This removes Miaomiao, closes this window and cleans the data it wrote to your home directory. Polkit authorization is required.",
    "卸载方式": "Method",
    "清理模式": "Cleanup mode",
    "系统授权": "Authorization",
    "隔离区（可恢复）": "Quarantine (restorable)",
    "永久删除 · 保留备份": "Delete permanently · keep backup",
    "需要 · Polkit 将弹出验证": "Required · Polkit will prompt",
    "不需要": "Not required",
    "关闭": "Close",
    "永久删除隔离文件": "Delete quarantined files permanently",
    "确认永久删除隔离文件与配置备份": "Permanently delete quarantined files and configuration backups",
    "恢复文件": "Restore files",
    "卸载": "Uninstall",
    "操作完成": "Completed",
    "部分完成": "Partially complete",
    "正在准备": "Preparing",
    # window
    "该应用": "this app",
    "删除本地应用文件": "Delete local app files",
    "系统软件包": "System package",
    "系统必需软件包": "Essential system package",
    "系统关键组件": "Critical system component",
    "本地用户应用": "Local user app",
    "便携式 AppImage": "Portable AppImage",
    "Snap 软件包": "Snap package",
    "Flatpak · 仓库": "Flatpak · repository",
    "与应用标识完全匹配": "Exact app identifier match",
    "名称相近，需要你确认": "Similar name; review required",
    "共享目录": "Shared folder",
    "系统共享配置": "Shared system configuration",
    "不在用户主目录": "Outside the home folder",
    "卸载器自身数据": "Uninstaller's own data",
    "Flatpak 沙盒数据": "Flatpak sandbox data",
    "用户桌面入口": "User desktop entry",
    "APT 软件包已卸载": "APT package removed",
    "Flatpak 应用与沙盒数据已移除": "Flatpak app and sandbox data removed",
    "Snap 已移除": "Snap removed",
    "本地应用文件已删除": "Local app files removed",
    "已保留安装文件": "Installation files kept",
    "受保护的系统组件": "Protected system component",
    "不支持的软件来源": "Unsupported package source",
    "已保留应用安装目录。": "Application install directory kept.",
    "正在调用 APT": "Calling APT",
    "正在卸载 Flatpak 应用": "Uninstalling Flatpak app",
    "正在删除本地应用": "Deleting local app",
    "正在卸载应用": "Uninstalling app",
    "正在清理用户残留": "Cleaning user residuals",
    "正在删除用户配置": "Deleting user configuration",
    "正在隔离残留": "Quarantining residuals",
    "正在删除残留": "Deleting residuals",
    "正在删除应用目录": "Deleting app directory",
    "正在结束进程": "Ending processes",
    "已完成": "Done",
    "清理完成": "Cleanup complete",
    "请先选择一个应用": "Select an app first",
    "已有操作正在进行": "Another operation is already running",
    "操作进行中，请等待完成": "An operation is running. Please wait.",
    "应用已卸载，但部分残留未清理": "App removed, but some residuals were not cleaned",
    "应用已移除，但清理过程出错": "App removed, but cleanup failed",
    "卸载未完成": "Removal incomplete",
    "部分残留未清理，可重新扫描后重试": "Some residuals remain. Rescan and try again.",
    "残留清理完成": "Residual cleanup complete",
    "清理未完成": "Cleanup incomplete",
    "没有可恢复的文件": "No restorable files",
    "数据目录": "Data folder",
    "释放空间": "Space freed",
}

_PATTERNS = [
    (re.compile(r"^喵喵 ([0-9.]+) · C 加速$"), r"Miaomiao \1 · C acceleration"),
    (re.compile(r"^喵喵 Miaomiao ([^ ]+) · Debian 系统包$"), r"Miaomiao \1 · Debian package"),
    (re.compile(r"^卸载 (.+)$"), r"Uninstall \1"),
    (re.compile(r"^将删除应用本体，并清理 (\d+) 项用户残留。 残留会先进入隔离区，可从历史记录恢复。$"),
     r"The app will be removed and \1 user residual items cleaned. Residuals move to quarantine and can be restored from History."),
    (re.compile(r"^将删除应用本体，并保留用户配置。 残留会先进入隔离区，可从历史记录恢复。$"),
     r"The app will be removed while keeping user configuration. Residuals move to quarantine and can be restored from History."),
    (re.compile(r"^将删除应用本体，并清理 (\d+) 项用户残留。 残留将从原位置永久删除，配置会打包保存为恢复备份。$"),
     r"The app will be removed and \1 user residual items cleaned. Residuals are deleted permanently; configuration is saved as a restore backup."),
    (re.compile(r"^将删除应用本体，并保留用户配置。 残留将从原位置永久删除，配置会打包保存为恢复备份。$"),
     r"The app will be removed while keeping user configuration. Residuals are deleted permanently; configuration is saved as a restore backup."),
    (re.compile(r"^将处理 (\d+) 个项目，共 (.+)。文件会进入隔离区，可从历史记录恢复。$"),
     r"Process \1 items, total \2. Files move to quarantine and can be restored from History."),
    (re.compile(r"^将处理 (\d+) 个项目，共 (.+)。文件将从原位置永久删除，配置会保存为恢复备份。$"),
     r"Process \1 items, total \2. Files are deleted permanently; configuration is saved as a restore backup."),
    (re.compile(r"^(\d+) 个应用 · (\d+) 个可管理包$"), r"\1 apps · \2 packages"),
    (re.compile(r"^已载入 (\d+) 个可管理应用$"), r"Loaded \1 manageable apps"),
    (re.compile(r"^检测到 (\d+) 个进程：(.*)$"), r"\1 processes detected: \2"),
    (re.compile(r"^(\d+) 项 · (.+)$"), r"\1 items · \2"),
    (re.compile(r"^已选择 (\d+) 项$"), r"\1 selected"),
    (re.compile(r"^清理 (\d+) 项$"), r"Clean \1 items"),
    (re.compile(r"^(\d+) 项残留$"), r"\1 residual items"),
    (re.compile(r"^(\d+) 个残留项目，可清理 (.+)；(\d+) 个共享目录已保护$"),
     r"\1 residual items, \2 cleanable; \3 shared folders protected"),
    (re.compile(r"^已排除 (\d+) 个共享目录$"), r"Excluded \1 shared folders"),
    (re.compile(r"^已恢复 (\d+) 项(，跳过 (\d+) 项)?$"),
     lambda m: f"Restored {m.group(1)} items" + (f"; skipped {m.group(3)}" if m.group(3) else "")),
    (re.compile(r"^已卸载 (.+)$"), r"Removed \1"),
    (re.compile(r"^读取软件列表失败：(.*)$"), r"Failed to load package list: \1"),
    (re.compile(r"^残留扫描失败：(.*)$"), r"Residual scan failed: \1"),
    (re.compile(r"^正在卸载 (.+)$"), r"Removing \1"),
    (re.compile(r"^已删除可执行文件：(.+)$"), r"Deleted executable: \1"),
    (re.compile(r"^已删除安装位置：(.+)$"), r"Deleted install location: \1"),
    (re.compile(r"^已隔离：(.+)$"), r"Quarantined: \1"),
    (re.compile(r"^已删除：(.+)$"), r"Deleted: \1"),
    (re.compile(r"^清理失败 (.+)：(.+)$"), r"Cleanup failed for \1: \2"),
    (re.compile(r"^已备份 (\d+) 项配置到 (.+)$"), r"Backed up \1 configuration items to \2"),
    (re.compile(r"^正在清理残留 (\d+)/(\d+)$"), r"Cleaning residuals \1/\2"),
    (re.compile(r"^目标：(.+) · (.+)$"), r"Target: \1 · \2"),
    (re.compile(r"^(\d{4}-\d\d-\d\d  \d\d:\d\d)  ·  (.*)  ·  (\d+) 项残留 · (.+) · (隔离|永久删除 · 备份)$"),
     lambda m: f"{m.group(1)}  ·  {m.group(2)}  ·  {m.group(3)} residual items · {m.group(4)} · " +
               ("Quarantined" if m.group(5) == "隔离" else "Deleted · backup")),
    (re.compile(r"^(\d+) 个操作 · (\d+) 个隔离文件可恢复$"), r"\1 operations · \2 quarantined files restorable"),
    (re.compile(r"^(\d+) 项残留$"), r"\1 residual items"),
    (re.compile(r"^(\d+) 项$"), r"\1 items"),
    (re.compile(r"^(.*)  ·  用户安装$"), r"\1 · User install"),
    (re.compile(r"^(.*)  ·  系统安装$"), r"\1 · System install"),
    (re.compile(r"^(.*)  ·  本地$"), r"\1 · Local"),
    (re.compile(r"^(.+) 仍保留，只移除用户目录中的残留$"), r"\1 remains; only residuals in your home folder are removed"),
    (re.compile(r"^(.+) 的隔离文件与配置备份将被彻底删除，磁盘空间会被释放。$"),
     r"Quarantined files and configuration backups for \1 will be permanently deleted; disk space will be freed."),
    (re.compile(r"^(.+) · 移至隔离区后可恢复$"), r"\1 · Restorable after quarantine"),
    (re.compile(r"^(.+) · 删除后保留配置备份$"), r"\1 · Configuration backup is kept"),
    (re.compile(r"^(\d+) 次操作 · (\d+) 项隔离文件可恢复$"),
     r"\1 operations · \2 quarantined files restorable"),
    (re.compile(r"^喵喵 Miaomiao (.*)  ·  Debian 系统包$"), r"Miaomiao \1 · Debian package"),
    (re.compile(r"^以下已安装软件依赖此包：(.*)。卸载可能影响它们，请确认后再继续。$"),
     r"The following installed packages depend on this package: \1. Removing it may affect them; review before continuing."),
    (re.compile(r"^检测到 (\d+) 个相关进程。建议先退出应用，或在下方开启“结束相关进程”。$"),
     r"\1 related processes detected. Quit the app first, or enable End related processes below."),
    (re.compile(r"^未发现反向依赖或运行中的进程。系统包管理器会一并清理 /etc 中的系统配置。$"),
     r"No reverse dependencies or running processes found. The package manager will also clean system configuration under /etc."),
    (re.compile(r"^未发现反向依赖或运行中的进程。Flatpak 沙盒数据会随应用一起删除。$"),
     r"No reverse dependencies or running processes found. Flatpak sandbox data will be removed with the app."),
    (re.compile(r"^未发现反向依赖或运行中的进程。仅删除用户目录内的文件。$"),
     r"No reverse dependencies or running processes found. Only files in your home directory will be removed."),
    (re.compile(r"^(.+)。为避免系统损坏，此应用不允许在此卸载。$"),
     r"\1. This app cannot be removed here to avoid system damage."),
    (re.compile(r"^已恢复 (\d+) 项(，跳过 (\d+) 项)?$"),
     lambda m: f"Restored {m.group(1)} items" + (f"; skipped {m.group(3)}" if m.group(3) else "")),
]


def tr(text: str) -> str:
    if not EN or not isinstance(text, str) or not text:
        return text
    if text in _EXACT:
        return _EXACT[text]
    for pattern, repl in _PATTERNS:
        if pattern.match(text):
            return pattern.sub(repl, text)
    return text


def install() -> None:
    """Translate labels at creation/set time, including dynamic status text."""
    if not EN:
        return
    from PyQt6.QtWidgets import (
        QAbstractButton, QLabel, QLineEdit, QPlainTextEdit, QWidget,
    )

    orig_label_init = QLabel.__init__
    orig_label_set = QLabel.setText
    orig_button_set = QAbstractButton.setText
    orig_placeholder = QLineEdit.setPlaceholderText
    orig_tooltip = QWidget.setToolTip
    orig_title = QWidget.setWindowTitle
    orig_plain_set = QPlainTextEdit.setPlainText
    orig_plain_append = QPlainTextEdit.appendPlainText

    def label_init(self, text="", *args, **kwargs):
        orig_label_init(self, tr(text), *args, **kwargs)

    def label_set(self, text):
        orig_label_set(self, tr(text))

    def button_set(self, text):
        orig_button_set(self, tr(text))

    def placeholder(self, text):
        orig_placeholder(self, tr(text))

    def tooltip(self, text):
        orig_tooltip(self, tr(text))

    def window_title(self, text):
        orig_title(self, tr(text))

    def plain_set(self, text):
        orig_plain_set(self, tr(text))

    def plain_append(self, text):
        orig_plain_append(self, tr(text))

    QLabel.__init__ = label_init
    QLabel.setText = label_set
    QAbstractButton.setText = button_set
    QLineEdit.setPlaceholderText = placeholder
    QWidget.setToolTip = tooltip
    QWidget.setWindowTitle = window_title
    QPlainTextEdit.setPlainText = plain_set
    QPlainTextEdit.appendPlainText = plain_append
