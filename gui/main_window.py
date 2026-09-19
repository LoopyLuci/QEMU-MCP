"""Main Window for QEMU-MCP GUI.

Frameless window with custom title bar, sidebar navigation,
panel content area, and status bar.  Provides the overall
application layout and panel switching.
"""

from __future__ import annotations

import sys
import os
import json
import pathlib
from pathlib import Path

from PyQt5.QtCore import Qt, QSize, QTimer, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QIcon, QPalette, QColor, QPainter, QFont
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QStackedWidget,
    QStatusBar,
    QSpacerItem,
    QSizePolicy,
    QMessageBox,
)

# Ensure project root and src are on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from vm_mcp.config import VmMCPSettings, Secrets
from vm_mcp.qmp_client import QMPClient
from vm_mcp.setup import start_vm, stop_vm
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
    title_bar_style,
    button_ghost_style,
    button_red_style,
)
from gui.theme import T
from gui.credential_store import CredentialStore


# ── Title Bar ───────────────────────────────────────────────────────────────────

class TitleBar(QWidget):
    """Themed frameless window title bar with status indicator."""

    window_state_changed = pyqtSignal(int)

    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self._parent = parent
        self.setFixedHeight(40)
        self.setStyleSheet(title_bar_style())
        layout = QHBoxLayout(self)
        layout.setContentsMargins(T.SM, 0, T.SM, 0)
        layout.setSpacing(T.SM)

        # Brand icon
        icon_label = QLabel()
        icon_label.setFixedSize(T.FS_XL + 4, T.FS_XL + 4)
        icon_label.setStyleSheet(
            "background: " + T.BRAND + ";"
            "border-radius: " + str(T.R_SM) + "px;"
        )
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # App name
        title_label = QLabel("QEMU-MCP")
        title_label.setStyleSheet(
            "color: " + T.TEXT_PRIMARY + ";"
            "font-size: " + str(T.FS_LG) + "px; "
            "font-weight: bold;"
        )
        title_label.setFixedHeight(24)
        layout.addWidget(title_label)

        layout.addStretch()

        # Status indicator (themed)
        self.status_dot = StatusIndicator()
        layout.addWidget(self.status_dot)

        self._status_text = QLabel("Disconnected")
        self._status_text.setStyleSheet(
            "color: " + T.TEXT_MUTED + ";"
            "font-size: " + str(T.FS_SM) + "px;"
        )
        layout.addWidget(self._status_text)

        layout.addStretch()

        # Window controls
        self._btn_min = QPushButton("\u2014")
        self._btn_min.setFixedSize(T.MD * 3, T.LG * 2)
        self._btn_min.setCursor(Qt.PointingHandCursor)
        self._btn_min.setStyleSheet(button_ghost_style())
        self._btn_min.clicked.connect(lambda: self._parent.showMinimized())
        layout.addWidget(self._btn_min)

        self._btn_max = QPushButton("\u25A1")
        self._btn_max.setFixedSize(T.MD * 3, T.LG * 2)
        self._btn_max.setCursor(Qt.PointingHandCursor)
        self._btn_max.setStyleSheet(button_ghost_style())
        self._btn_max.clicked.connect(self._toggle_maximize)
        layout.addWidget(self._btn_max)

        self._btn_close = QPushButton("\u2715")
        self._btn_close.setFixedSize(T.MD * 3, T.LG * 2)
        self._btn_close.setCursor(Qt.PointingHandCursor)
        self._btn_close.setStyleSheet(button_red_style())
        self._btn_close.clicked.connect(self._parent.close)
        layout.addWidget(self._btn_close)

    def _toggle_maximize(self):
        if self._parent.isMaximized():
            self._parent.showNormal()
            self._btn_max.setText("□")
        else:
            self._parent.showMaximized()
            self._btn_max.setText("❐")

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._parent.move(self._parent.pos() + event.globalPos() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self._parent.frameGeometry().topLeft()
        super().mousePressEvent(event)


# ── Sidebar ─────────────────────────────────────────────────────────────────────

class Sidebar(QWidget):
    """Navigation sidebar with icon buttons."""

    current_panel_changed = pyqtSignal(str)

    PANELS = [
        ("Dashboard", "📊", "dashboard"),
        ("VM Switcher", "🔄", "vm_switcher"),
        ("VM Control", "🖥️", "vm_control"),
        ("Guest Terminal", "💻", "guest_terminal"),
        ("Guest Agent", "🤖", "guest_agent"),
        ("Telemetry", "📈", "telemetry"),
        ("QMP System Info", "📋", "sysinfo"),
        ("QMP Console", "🔧", "qmp_console"),
        ("Snapshots", "📸", "snapshots"),
        ("ISO Manager", "💿", "iso"),
        ("Create VM", "➕", "wizard"),
        ("Storage", "💾", "storage"),
        ("CPU/Memory", "🧠", "cpu"),
        ("Display", "🖥️", "display"),
        ("Advanced QEMU", "⚡", "qemu"),
        ("USB/Devices", "🔌", "usb"),
        ("Network", "🌐", "network"),
        ("Monitoring", "📊", "monitoring"),
        ("Settings", "⚙️", "settings"),
        ("Security", "🔒", "security"),
        ("Automation", "🤖", "automation"),
        ("Troubleshoot", "🔍", "troubleshoot"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = "dashboard"
        self.setFixedWidth(180)
        self.setStyleSheet("""
            Sidebar {
                background: #0f172a;
                border-right: 1px solid #334155;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        for label, icon, name in self.PANELS:
            btn = QPushButton(f"{icon}  {label}")
            btn.setObjectName(f"sidebar_{name}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setFixedHeight(40)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: #94a3b8;
                    border: none;
                    border-radius: 6px;
                    font-size: 13px;
                    padding: 0 8px;
                }}
                QPushButton:hover {{
                    background: #1e293b;
                    color: #e2e8f0;
                }}
                QPushButton:checked {{
                    background: #1e3a5f;
                    color: #60a5fa;
                }}
                #{btn.objectName()}:hover {{
                    background: #1e293b;
                    color: #e2e8f0;
                }}
            """)
            btn.clicked.connect(lambda checked, n=name: self._select_panel(n))
            layout.addWidget(btn)

        layout.addStretch()

        # Version label
        ver_label = QLabel("v1.0.0")
        ver_label.setStyleSheet("color: #475569; font-size: 10px; text-align: center;")
        ver_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(ver_label)

    def _select_panel(self, name: str):
        self._current = name
        for label, icon, panel_name in self.PANELS:
            btn = self.findChild(QPushButton, f"sidebar_{panel_name}")
            if btn:
                btn.setChecked(panel_name == name)
        self.current_panel_changed.emit(name)


# ── Main Window ─────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """QEMU-MCP main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("QEMU-MCP")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setStyleSheet("""
            QMainWindow {
                background: #0f172a;
            }
        """)

        # ── State ──────────────────────────────────────────────────────────────
        self.settings = VmMCPSettings()
        self.secrets = Secrets.from_env()
        self.secrets_dotenv = Secrets.from_dotenv()
        if self.secrets_dotenv.has_any_secret():
            self.secrets = self.secrets_dotenv

        self.qmp_client: QMPClient | None = None
        self.credential_store = CredentialStore()

        self._drag_pos: QPoint = QPoint()

        # ── Central widget ─────────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        # Main content area
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar(self)
        content_layout.addWidget(self.sidebar)

        # Panel stack
        self.panel_stack = QStackedWidget(self)
        self.panel_stack.setStyleSheet("""
            QStackedWidget {
                background: #0f172a;
            }
        """)
        content_layout.addWidget(self.panel_stack)
        content_layout.setStretchFactor(self.panel_stack, 1)

        main_layout.addWidget(content)

        # Status bar
        self.status_bar = QStatusBar(self)
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #0f172a;
                color: #64748b;
                border-top: 1px solid #334155;
                font-size: 12px;
            }
        """)
        self.status_label = QLabel("Ready")
        self.status_bar.addPermanentWidget(self.status_label)
        main_layout.addWidget(self.status_bar)

        # ── QMP Bridge (background async → PyQt5 signals) ─────────────────────
        from gui.qmp_bridge import QMPBridge
        self.qmp_bridge = QMPBridge(settings=self.settings)
        self.qmp_bridge.start()
        self.qmp_bridge.connected.connect(self._on_qmp_connected)
        self.qmp_bridge.vm_status.connect(self._on_vm_status)
        self.qmp_bridge.error.connect(self._on_qmp_error)
        self.qmp_bridge.command_result.connect(self._on_qmp_command)
        self.qmp_client = None  # legacy compat

        # ── SSH Bridge ────────────────────────────────────────────────────────
        from gui.ssh_bridge import SSHBridge
        self.ssh_bridge = SSHBridge(settings=self.settings)
        self.ssh_bridge.start()
        self.ssh_bridge.connected.connect(self._on_ssh_connected)
        self.ssh_bridge.command_output.connect(self._on_ssh_command_output)
        self.ssh_bridge.file_content.connect(self._on_ssh_file_content)
        self.ssh_bridge.file_list.connect(self._on_ssh_file_list)
        self.ssh_bridge.error.connect(self._on_ssh_error)
        self.ssh_bridge.connected_to.connect(self._on_ssh_connected_to)

        # ── Build panels ───────────────────────────────────────────────────────
        self._build_panels()

        # ── Sidebar connection ─────────────────────────────────────────────────
        self.sidebar.current_panel_changed.connect(self._switch_panel)

        # ── Window drag support ────────────────────────────────────────────────
        self.title_bar.mouseMoveEvent = self._title_bar_mouse_move
        self.title_bar.mousePressEvent = self._title_bar_mouse_press

        # ── Telemetry timer ────────────────────────────────────────────────────
        self._telemetry_timer = QTimer(self)
        # Don't connect — telemetry is handled by TelemetryPanel's own timer
        self._telemetry_timer.start(2000)

        # ── Auto-reconnect timer (polls until QMP/SSH come back) ───────────────
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.timeout.connect(self._try_auto_reconnect)
        self._reconnect_timer.start(5000)

        # ── Build panels ───────────────────────────────────────────────────────
        self._update_status_indicators()

    def _title_bar_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def _title_bar_mouse_move(self, event):
        if event.buttons() & Qt.LeftButton:
            self.move(self.pos() + event.globalPos() - self._drag_pos)

    def _build_panels(self):
        """Create all panels and add them to the stacked widget."""
        from gui.panels_vm_switcher import VMSwitcherPanel
        from gui.panels import DashboardPanel
        from gui.panels_vm_control import VMControlPanel
        from gui.panels_guest_terminal import GuestTerminalPanel
        from gui.panels_guest_agent import GuestAgentPanel
        from gui.panels_telemetry import TelemetryPanel
        from gui.panels_qmp_console import QMPConsolePanel
        from gui.panels_sysinfo import QemuSystemInfoPanel
        from gui.panels_snapshots import SnapshotPanel
        from gui.panels_iso import ISOManagerPanel
        from gui.panels_wizard import VMCreationWizard
        from gui.panels_storage import StoragePanel
        from gui.panels_usb import USBDevicePanel
        from gui.panels_network import NetworkPanel
        from gui.panels_monitoring import MonitoringPanel
        from gui.panels_cpu import CPUControlPanel
        from gui.panels_display import DisplayPanel
        from gui.panels_qemu import AdvancedQEmuPanel
        from gui.panels_automation import AutomationPanel
        from gui.panels_troubleshoot import TroubleshootPanel
        from gui.panels_settings import SettingsPanel
        from gui.panels_security import SecurityPanel
        from gui.panels_logs import LogsPanel

        self.panels: dict[str, QWidget] = {}

        panel_list = [
            (DashboardPanel, "dashboard"),
            (VMSwitcherPanel, "vm_switcher"),
            (VMControlPanel, "vm_control"),
            (GuestTerminalPanel, "guest_terminal"),
            (GuestAgentPanel, "guest_agent"),
            (TelemetryPanel, "telemetry"),
            (QMPConsolePanel, "qmp_console"),
            (QemuSystemInfoPanel, "sysinfo"),
            (SnapshotPanel, "snapshots"),
            (ISOManagerPanel, "iso"),
            (VMCreationWizard, "wizard"),
            (StoragePanel, "storage"),
            (USBDevicePanel, "usb"),
            (NetworkPanel, "network"),
            (CPUControlPanel, "cpu"),
            (DisplayPanel, "display"),
            (AdvancedQEmuPanel, "qemu"),
            (AutomationPanel, "automation"),
            (TroubleshootPanel, "troubleshoot"),
            (MonitoringPanel, "monitoring"),
            (SettingsPanel, "settings"),
            (SecurityPanel, "security"),
            (LogsPanel, "logs"),
        ]

        for panel_cls, name in panel_list:
            panel = panel_cls(self)
            self.panels[name] = panel
            self.panel_stack.addWidget(panel)

        # ── Wire bridges to panels ────────────────────────────────────────────
        if "dashboard" in self.panels:
            self.panels["dashboard"].set_qmp_bridge(self.qmp_bridge)
        if "vm_control" in self.panels:
            self.panels["vm_control"].set_qmp_bridge(self.qmp_bridge)
        if "guest_terminal" in self.panels:
            self.panels["guest_terminal"].set_ssh_bridge(self.ssh_bridge)
        if "telemetry" in self.panels:
            self.panels["telemetry"].set_qmp_bridge(self.qmp_bridge)
            self.panels["telemetry"].set_ssh_bridge(self.ssh_bridge)
        if "qmp_console" in self.panels:
            self.panels["qmp_console"].set_qmp_bridge(self.qmp_bridge)

        self._switch_panel("dashboard")

    def _switch_panel(self, name: str):
        if name in self.panels:
            self.panel_stack.setCurrentWidget(self.panels[name])
            self.status_label.setText(f"Panel: {name.replace('_', ' ').title()}")

    def _update_status_indicators(self):
        """Update the title bar status dot and text."""
        if self.qmp_bridge and self.qmp_bridge.is_connected:
            self.title_bar.status_dot.set_status(running=True, connected=True)
        elif self.ssh_bridge and self.ssh_bridge.is_connected:
            self.title_bar.status_dot.set_status(running=False, connected=True)
        else:
            self.title_bar.status_dot.set_status(running=False, connected=False)

    # ── QMP Bridge Callbacks ──────────────────────────────────────────────────

    def _on_qmp_connected(self, connected: bool):
        self._update_status_indicators()
        if connected:
            self.status_label.setText("Connected to QMP")
            self.status_label.setStyleSheet("color: #22c55e; font-size: 12px;")
            # Refresh status immediately
            self.qmp_bridge.get_status()
        else:
            self.status_label.setText("QMP connection failed")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 12px;")

    def _on_vm_status(self, status: dict):
        """Update dashboard with VM status from QMP."""
        panel = self.panels.get("dashboard")
        if panel and hasattr(panel, "update_vm_status"):
            panel.update_vm_status(status)

    def _on_qmp_error(self, message: str):
        self.status_label.setText(f"QMP: {message}")
        self.status_label.setStyleSheet("color: #ef4444; font-size: 12px;")

    def _on_qmp_command(self, result: dict):
        """Handle QMP command result."""
        self.status_label.setText(f"QMP command: {result.get('return', result.get('error', 'ok'))}")
        self.status_label.setStyleSheet("color: #38bdf8; font-size: 12px;")

    # ── SSH Bridge Callbacks ─────────────────────────────────────────────────

    def _on_ssh_connected(self, connected: bool):
        if connected:
            self.status_label.setText("Connected to guest SSH")
            self.status_label.setStyleSheet("color: #22c55e; font-size: 12px;")
        else:
            self.status_label.setText("SSH connection failed")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 12px;")

    def _on_ssh_connected_to(self, address: str):
        self.status_label.setText(f"SSH connected to {address}")
        self.status_label.setStyleSheet("color: #22c55e; font-size: 12px;")

    def _on_ssh_command_output(self, output: str):
        """Send command output to guest terminal."""
        panel = self.panels.get("guestterminal")
        if panel and hasattr(panel, "append_command_output"):
            panel.append_command_output(output)

    def _on_ssh_file_content(self, content: str):
        """Send file content to guest terminal."""
        panel = self.panels.get("guestterminal")
        if panel and hasattr(panel, "append_file_content"):
            panel.append_file_content(content)

    def _on_ssh_file_list(self, files: list):
        """Send file listing to guest terminal."""
        panel = self.panels.get("guestterminal")
        if panel and hasattr(panel, "populate_files"):
            panel.populate_files(files)

    def _on_ssh_error(self, message: str):
        panel = self.panels.get("guestterminal")
        if panel and hasattr(panel, "append_error"):
            panel.append_error(message)

    def _try_auto_reconnect(self):
        """Periodic auto-reconnect: if bridges are running but not connected,
        retry connecting.  Called every 5 seconds by _reconnect_timer.
        Only reconnects if the bridge was previously connected (not on first
        start, to avoid grabbing the sole QMP connection during tests)."""
        if self.qmp_bridge and not self.qmp_bridge.is_connected:
            if self.qmp_bridge._ever_connected:
                self.qmp_bridge.connect()
        if self.ssh_bridge and not self.ssh_bridge.is_connected:
            self.ssh_bridge.connect_ssh()

    def _save_state(self):
        """Persist window geometry and panel selection for next launch."""
        try:
            state_dir = pathlib.Path.home() / ".local" / "share" / "qmcmcp"
            state_dir.mkdir(parents=True, exist_ok=True)
            state_file = state_dir / "window_state.json"
            active_name = None
            for name, panel in self.panels.items():
                if self.panel_stack.currentWidget() is panel:
                    active_name = name
                    break
            state = {
                "geometry": self.saveGeometry().data().hex(),
                "window_state": self.saveState().data().hex(),
                "active_panel": active_name,
            }
            state_file.write_text(json.dumps(state), encoding="utf-8")
        except Exception:
            pass  # Never let state save crash the app

    def closeEvent(self, event):
        """Clean up on close."""
        # Save window state for next launch
        self._save_state()
        # Don't disconnect — VM should keep running
        self._telemetry_timer.stop()
        self._reconnect_timer.stop()
        if self.qmp_bridge:
            self.qmp_bridge.stop()
        if self.ssh_bridge:
            self.ssh_bridge.stop()
        event.accept()


# ── Application Entry ───────────────────────────────────────────────────────────

def main():
    """Run the QEMU-MCP GUI application."""
    from PyQt5.QtWidgets import QApplication
    from gui.theme import dark_palette

    app = QApplication(sys.argv)
    app.setApplicationName("QEMU-MCP")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("QEMU-MCP")

    # Apply global dark theme
    app.setStyle("Fusion")
    app.setPalette(dark_palette())

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
