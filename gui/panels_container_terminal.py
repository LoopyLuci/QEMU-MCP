"""Container Terminal Panel — in-browser terminal via WebSocket.

Provides a Portainer-like terminal experience for Docker containers.
Connects to ws://127.0.0.1:8445/terminal/{container_name}
"""

from __future__ import annotations

import json
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QTextCursor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextBrowser, QLineEdit, QMessageBox, QTabWidget,
    QSizePolicy,
)

from gui.theme import T
from gui.widgets import Card, StatusIndicator


class ContainerTerminalPanel(QWidget):
    """In-browser terminal for Docker containers via WebSocket."""

    terminal_event = pyqtSignal(str, str)  # container_name, event_type

    def __init__(self, parent=None):
        super().__init__(parent)
        self._adapter = None
        self._ws_clients: dict[str, any] = {}
        self._current_container: str | None = None
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)

        # ── Connection Status ──────────────────────────────────────────────
        status_card = Card("Terminal Connection")
        status_card.setFixedHeight(50)
        layout.addWidget(status_card)

        status_row = QWidget()
        sr_layout = QHBoxLayout(status_row)
        sr_layout.setContentsMargins(0, 0, 0, 0)
        sr_layout.setSpacing(12)

        self._status_indicator = StatusIndicator(QColor("#ef4444"))
        sr_layout.addWidget(self._status_indicator)
        sr_layout.addWidget(QLabel("WebSocket"))

        self._container_combo = QComboBox()
        self._container_combo.setMinimumWidth(200)
        self._container_combo.currentTextChanged.connect(self._on_container_changed)
        sr_layout.addWidget(self._container_combo)

        sr_layout.addStretch()

        self._btn_connect = QPushButton("Connect")
        self._btn_connect.setStyleSheet(
            f"background: {T.BRAND}; color: {T.TEXT_PRIMARY}; border: none;"
            "border-radius: 6px; padding: 6px 16px; font-weight: bold;"
        )
        self._btn_connect.clicked.connect(self._connect)
        sr_layout.addWidget(self._btn_connect)

        self._btn_disconnect = QPushButton("Disconnect")
        self._btn_disconnect.setStyleSheet(
            f"background: {T.BG_TERTIARY}; color: {T.TEXT_PRIMARY}; border: 1px solid {T.BG_TERTIARY};"
            "border-radius: 6px; padding: 6px 16px;"
        )
        self._btn_disconnect.clicked.connect(self._disconnect)
        sr_layout.addWidget(self._btn_disconnect)

        self._btn_clear = QPushButton("Clear")
        self._btn_clear.setStyleSheet(
            f"background: {T.BG_TERTIARY}; color: {T.TEXT_PRIMARY}; border: 1px solid {T.BG_TERTIARY};"
            "border-radius: 6px; padding: 6px 16px;"
        )
        self._btn_clear.clicked.connect(self._clear_terminal)
        sr_layout.addWidget(self._btn_clear)

        status_card.content_layout.addWidget(status_row)

        # ── Terminal Output ────────────────────────────────────────────────
        self._terminal = QTextBrowser()
        self._terminal.setFont(QFont("Consolas", 10))
        self._terminal.setStyleSheet(
            f"QTextBrowser {{ background: #0d1117; color: #c9d1d9; border: 1px solid {T.BG_TERTIARY}; border-radius: 8px; padding: 8px; }}"
        )
        self._terminal.setMinimumHeight(300)
        layout.addWidget(self._terminal)

        # ── Command Input ──────────────────────────────────────────────────
        input_row = QWidget()
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        self._prompt_label = QLabel("$")
        self._prompt_label.setStyleSheet(f"color: {T.BRAND}; font-family: Consolas; font-size: 12px;")
        input_layout.addWidget(self._prompt_label)

        self._cmd_input = QLineEdit()
        self._cmd_input.setStyleSheet(
            f"QLineEdit {{ background: #0d1117; color: #c9d1d9; border: 1px solid {T.BG_TERTIARY}; border-radius: 6px; padding: 8px; font-family: Consolas; font-size: 12px; }}"
        )
        self._cmd_input.setPlaceholderText("Type command and press Enter...")
        self._cmd_input.returnPressed.connect(self._send_command)
        self._cmd_input.setEnabled(False)
        input_layout.addWidget(self._cmd_input)

        self._btn_send = QPushButton("Send")
        self._btn_send.setStyleSheet(
            f"background: {T.BRAND}; color: {T.TEXT_PRIMARY}; border: none;"
            "border-radius: 6px; padding: 6px 16px; font-weight: bold;"
        )
        self._btn_send.clicked.connect(self._send_command)
        self._btn_send.setEnabled(False)
        input_layout.addWidget(self._btn_send)

        layout.addWidget(input_row)

        # ── Quick Commands ─────────────────────────────────────────────────
        quick_card = Card("Quick Commands")
        layout.addWidget(quick_card)

        quick_row = QWidget()
        quick_layout = QHBoxLayout(quick_row)
        quick_layout.setContentsMargins(0, 0, 0, 0)
        quick_layout.setSpacing(8)

        for cmd in ["ls", "pwd", "ps aux", "df -h", "free -m", "uname -a", "cat /etc/os-release"]:
            btn = QPushButton(cmd)
            btn.setStyleSheet(
                f"background: {T.BG_TERTIARY}; color: {T.TEXT_PRIMARY}; border: 1px solid {T.BG_TERTIARY};"
                "border-radius: 6px; padding: 4px 12px;"
            )
            btn.clicked.connect(lambda checked, c=cmd: self._run_quick_command(c))
            quick_layout.addWidget(btn)

        quick_card.content_layout.addWidget(quick_row)

        # ── Container List Refresh ─────────────────────────────────────────
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._load_containers)
        self._refresh_timer.start(10000)

        self._load_containers()

    def _load_containers(self):
        """Load container list."""
        try:
            from gui.async_adapter import get_adapter
            adapter = get_adapter()
            containers = adapter.docker.list_containers()
            self._container_combo.clear()
            for c in containers:
                name = c.get("name", "")
                status = c.get("status", "")
                self._container_combo.addItem(f"{name} ({status})")
        except Exception:
            pass

    def _on_container_changed(self, text: str):
        """Handle container selection change."""
        if "(" in text:
            self._current_container = text.split("(")[0].strip()
        else:
            self._current_container = text.strip()

    def _connect(self):
        """Connect to WebSocket terminal."""
        if not self._current_container:
            QMessageBox.warning(self, "No Container", "Please select a container first.")
            return

        try:
            import websocket
            ws_url = f"ws://127.0.0.1:8445/terminal/{self._current_container}"
            ws = websocket.create_connection(ws_url, timeout=10)
            self._ws_clients[self._current_container] = ws
            self._status_indicator.set_status(True)
            self._cmd_input.setEnabled(True)
            self._btn_send.setEnabled(True)
            self._terminal.append(f"Connected to {self._current_container}")

            # Start receive loop
            self._receive_timer = QTimer(self)
            self._receive_timer.timeout.connect(self._receive_output)
            self._receive_timer.start(100)

        except Exception as e:
            self._status_indicator.set_status(False)
            self._terminal.append(f"Connection failed: {e}")
            QMessageBox.critical(self, "Connection Failed", f"Could not connect to terminal: {e}")

    def _disconnect(self):
        """Disconnect from WebSocket."""
        if self._current_container in self._ws_clients:
            try:
                self._ws_clients[self._current_container].close()
            except Exception:
                pass
            del self._ws_clients[self._current_container]

        self._status_indicator.set_status(False)
        self._cmd_input.setEnabled(False)
        self._btn_send.setEnabled(False)
        self._terminal.append("Disconnected")

    def _send_command(self):
        """Send command to container."""
        if not self._current_container:
            return
        cmd = self._cmd_input.text()
        if not cmd:
            return

        self._terminal.append(f"$ {cmd}")
        self._cmd_input.clear()

        try:
            if self._current_container in self._ws_clients:
                ws = self._ws_clients[self._current_container]
                ws.send(json.dumps({"command": cmd}))
            else:
                self._terminal.append("Not connected")
        except Exception as e:
            self._terminal.append(f"Send failed: {e}")

    def _receive_output(self):
        """Receive output from WebSocket."""
        if not self._current_container:
            return
        try:
            if self._current_container in self._ws_clients:
                ws = self._ws_clients[self._current_container]
                ws.settimeout(0.1)
                try:
                    result = ws.recv()
                    if result:
                        data = json.loads(result)
                        output = data.get("output", "")
                        self._terminal.append(output)
                except Exception:
                    pass
        except Exception:
            pass

    def _run_quick_command(self, cmd: str):
        """Run a quick command."""
        self._cmd_input.setText(cmd)
        self._send_command()

    def _clear_terminal(self):
        """Clear terminal output."""
        self._terminal.clear()
