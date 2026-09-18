"""QEMU-MCP GUI — PyQt5 desktop application for QEMU/VM control.

Provides a polished, professional graphical interface for managing
QEMU virtual machines, monitoring telemetry, interacting with guest
systems, configuring settings, and securely managing credentials.

Architecture:
    MainWindow (frameless) → Sidebar + StackedPanel
    Panel classes handle their own state; shared state lives in
    MainWindow._qmp_client, _settings, _secrets, _credential_store.

Usage:
    python -m vm_mcp.gui
    python -m gui  (when installed as package)

Requires:
    PyQt5 >= 5.15
    matplotlib >= 3.8
    cryptography >= 42.0
    psutil >= 5.9
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "QEMU-MCP Team"

from gui.main_window import MainWindow, main as gui_main
from gui.widgets import (
    StatusIndicator,
    IconButton,
    Card,
    TextInput,
    PasswordInput,
    TerminalOutput,
    TelemetryChart,
    LogEntry,
    CredentialTreeItem,
    FileTree,
)
from gui.credential_store import CredentialStore
from gui.panels import DashboardPanel
from gui.panels_vm_control import VMControlPanel
from gui.panels_guest_terminal import GuestTerminalPanel
from gui.panels_telemetry import TelemetryPanel
from gui.panels_settings import SettingsPanel
from gui.panels_security import SecurityPanel, CredentialDialog
from gui.panels_logs import LogsPanel

__all__ = [
    "MainWindow",
    "gui_main",
    "DashboardPanel",
    "VMControlPanel",
    "GuestTerminalPanel",
    "TelemetryPanel",
    "SettingsPanel",
    "SecurityPanel",
    "LogsPanel",
    "CredentialDialog",
    "CredentialStore",
    "StatusIndicator",
    "IconButton",
    "Card",
    "TextInput",
    "PasswordInput",
    "TerminalOutput",
    "TelemetryChart",
    "LogEntry",
    "FileTree",
]
