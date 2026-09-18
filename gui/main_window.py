"""Main Window for QEMU-MCP GUI.

Frameless window with custom title bar, sidebar navigation,
panel content area, and status bar.  Provides the overall
application layout and panel switching.
"""

from __future__ import annotations

import sys
import os
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

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
)
from gui.credential_store import CredentialStore


# ── Title Bar ───────────────────────────────────────────────────────────────────

class TitleBar(QWidget):
    """Custom frameless window title bar."""

    window_state_changed = pyqtSignal(int)  # Qt.WindowStates

    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self._parent = parent
        self.setFixedHeight(40)
        self.setStyleSheet("""
            TitleBar {
                background: #0f172a;
                border-bottom: 1px solid #334155;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        # App icon + name
        icon_label = QLabel()
        icon_label.setFixedSize(24, 24)
        icon_label.setStyleSheet("background: #3b82f6; border-radius: 4px;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        title_label = QLabel("QEMU-MCP")
        title_label.setStyleSheet("color: #e2e8f0; font-size: 14px; font-weight: bold;")
        title_label.setFixedHeight(24)
        layout.addWidget(title_label)

        layout.addStretch()

        # Status indicator
        self.status_dot = StatusIndicator()
        layout.addWidget(self.status_dot)

        status_text = QLabel("Disconnected")
        status_text.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(status_text)

        layout.addStretch()

        # Window controls
        self._btn_min = QPushButton("―")
        self._btn_min.setFixedSize(40, 32)
        self._btn_min.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                font-size: 16px;
                border: none;
            }
            QPushButton:hover { background: #334155; color: #e2e8f0; }
        """)
        self._btn_min.clicked.connect(lambda: self._parent.showMinimized())
        layout.addWidget(self._btn_min)

        self._btn_max = QPushButton("□")
        self._btn_max.setFixedSize(40, 32)
        self._btn_max.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover { background: #334155; color: #e2e8f0; }
        """)
        self._btn_max.clicked.connect(self._toggle_maximize)
        layout.addWidget(self._btn_max)

        self._btn_close = QPushButton("✕")
        self._btn_close.setFixedSize(40, 32)
        self._btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover { background: #ef4444; color: white; }
        """)
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
        ("VM Control", "🖥️", "vm_control"),
        ("Guest Terminal", "💻", "guest_terminal"),
        ("Telemetry", "📈", "telemetry"),
        ("Settings", "⚙️", "settings"),
        ("Security", "🔒", "security"),
        ("Logs", "📋", "logs"),
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

        # ── Build panels ───────────────────────────────────────────────────────
        self._build_panels()

        # ── Sidebar connection ─────────────────────────────────────────────────
        self.sidebar.current_panel_changed.connect(self._switch_panel)

        # ── Window drag support ────────────────────────────────────────────────
        self.title_bar.mouseMoveEvent = self._title_bar_mouse_move
        self.title_bar.mousePressEvent = self._title_bar_mouse_press

        # ── Telemetry timer ────────────────────────────────────────────────────
        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.timeout.connect(self._update_telemetry)
        self._telemetry_timer.start(2000)

        # ── Initial status ─────────────────────────────────────────────────────
        self._update_status_indicators()

    def _title_bar_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def _title_bar_mouse_move(self, event):
        if event.buttons() & Qt.LeftButton:
            self.move(self.pos() + event.globalPos() - self._drag_pos)

    def _build_panels(self):
        """Create all panels and add them to the stacked widget."""
        from gui.panels import DashboardPanel
        from gui.panels_vm_control import VMControlPanel
        from gui.panels_guest_terminal import GuestTerminalPanel
        from gui.panels_telemetry import TelemetryPanel
        from gui.panels_settings import SettingsPanel
        from gui.panels_security import SecurityPanel
        from gui.panels_logs import LogsPanel

        self.panels: dict[str, QWidget] = {}
        for panel_cls in [DashboardPanel, VMControlPanel, GuestTerminalPanel, TelemetryPanel, SettingsPanel, SecurityPanel, LogsPanel]:
            panel = panel_cls(self)
            name = panel.__class__.__name__.replace("Panel", "").lower()
            self.panels[name] = panel
            self.panel_stack.addWidget(panel)

        self._switch_panel("dashboard")

    def _switch_panel(self, name: str):
        if name in self.panels:
            self.panel_stack.setCurrentWidget(self.panels[name])
            self.status_label.setText(f"Panel: {name.replace('_', ' ').title()}")

    def _update_status_indicators(self):
        """Update the title bar status dot and text."""
        if self.qmp_client and self.qmp_client.is_connected:
            self.title_bar.status_dot.set_status(running=True, connected=True)
            self.title_bar.findChild(QLabel, None)  # refresh text if needed
        else:
            self.title_bar.status_dot.set_status(running=False, connected=False)

    def _update_telemetry(self):
        """Called by QTimer every 2 seconds to refresh telemetry charts."""
        # Placeholder — real implementation reads from QMP and guest
        panel = self.panels.get("telemetry")
        if panel and hasattr(panel, "_refresh_charts"):
            panel._refresh_charts()

    def closeEvent(self, event):
        """Clean up on close."""
        if self.qmp_client:
            # Don't disconnect — VM should keep running
            pass
        self._telemetry_timer.stop()
        event.accept()


# ── Application Entry ───────────────────────────────────────────────────────────

def main():
    """Run the QEMU-MCP GUI application."""
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("QEMU-MCP")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("QEMU-MCP")

    # Apply global dark theme
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0f172a"))
    palette.setColor(QPalette.WindowText, QColor("#e2e8f0"))
    palette.setColor(QPalette.Base, QColor("#0f172a"))
    palette.setColor(QPalette.AlternateBase, QColor("#1e293b"))
    palette.setColor(QPalette.Text, QColor("#e2e8f0"))
    palette.setColor(QPalette.Button, QColor("#1e293b"))
    palette.setColor(QPalette.ButtonText, QColor("#e2e8f0"))
    palette.setColor(QPalette.BrightText, QColor("#ef4444"))
    palette.setColor(QPalette.Link, QColor("#3b82f6"))
    palette.setColor(QPalette.Highlight, QColor("#3b82f6"))
    palette.setColor(QPalette.HighlightedText, QColor("#0f172a"))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
