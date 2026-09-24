"""QMP Console panel — direct QMP command input and response viewer."""

from __future__ import annotations

from typing import Any

from gui.theme import T
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTextEdit, QLabel, QComboBox,
)

from gui.widgets import Card


class QMPConsolePanel(QWidget):
    """Direct QMP command console for power users."""

    command_sent = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._qmp_bridge = None
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────────────
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("QMP Console")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        self._status_label = QLabel("Disconnected")
        self._status_label.setStyleSheet("color: " + T.STATUS_STOPPED + "; font-size: 12px;")
        hl.addWidget(self._status_label)
        layout.addWidget(header)

        # ── Response Viewer ───────────────────────────────────────────────────
        self._response_view = QTextEdit()
        self._response_view.setReadOnly(True)
        self._response_view.setFont(QFont("Consolas", 10))
        self._response_view.setStyleSheet(
            "QTextEdit {"
            "  background: #0d1117;"
            "  color: #c9d1d9;"
            "  border: 1px solid " + T.BG_TERTIARY + ";"
            "  border-radius: 6px;"
            "  padding: 8px;"
            "}"
            "QTextEdit:focus { border-color: " + T.BRAND + "; }"
        )
        layout.addWidget(self._response_view)

        # ── Preset Commands ───────────────────────────────────────────────────
        presets_row = QWidget()
        pr = QHBoxLayout(presets_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.setSpacing(8)

        presets = [
            ("query-status", "Status"),
            ("query-name", "Name"),
            ("query-kvm", "KVM Info"),
            ("query-uuid", "UUID"),
            ("query-version", "Version"),
            ("query-commands", "Commands"),
            ("query-target", "Target"),
        ]
        for cmd, label in presets:
            btn = QPushButton(label)
            btn.setFixedSize(90, 28)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: " + T.BG_SECONDARY + ";"
                "  border: 1px solid " + T.BG_TERTIARY + ";"
                "  border-radius: 4px;"
                "  color: " + T.TEXT_SECONDARY + ";"
                "  font-size: 11px;"
                "}"
                "QPushButton:hover { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_PRIMARY + "; }"
            )
            btn.clicked.connect(lambda checked, c=cmd: self._send_command(c))
            pr.addWidget(btn)
        pr.addStretch()
        layout.addWidget(presets_row)

        # ── Command Input ─────────────────────────────────────────────────────
        input_row = QWidget()
        il = QHBoxLayout(input_row)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(8)

        self._cmd_input = QLineEdit()
        self._cmd_input.setPlaceholderText('e.g., query-status or {"execute": "system_powerdown"}')
        self._cmd_input.returnPressed.connect(self._send_input)
        self._cmd_input.setStyleSheet(
            "QLineEdit {"
            "  background: " + T.BG_SECONDARY + ";"
            "  color: " + T.TEXT_PRIMARY + ";"
            "  border: 1px solid " + T.BG_TERTIARY + ";"
            "  border-radius: 6px;"
            "  font-family: Consolas, monospace;"
            "  font-size: 12px;"
            "  padding: 6px 10px;"
            "}"
            "QLineEdit:focus { border-color: " + T.BRAND + "; }"
        )
        il.addWidget(self._cmd_input)

        send_btn = QPushButton("Send")
        send_btn.setFixedSize(70, 32)
        send_btn.setStyleSheet(
            "QPushButton {"
            "  background: " + T.BRAND + ";"
            "  border: none;"
            "  border-radius: 6px;"
            "  color: white;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            "}"
            "QPushButton:hover { background: " + T.BRAND_HOVER + "; }"
        )
        send_btn.clicked.connect(self._send_input)
        il.addWidget(send_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(60, 32)
        clear_btn.setStyleSheet(
            "QPushButton {"
            "  background: " + T.BG_SECONDARY + ";"
            "  border: 1px solid " + T.BG_TERTIARY + ";"
            "  border-radius: 6px;"
            "  color: " + T.TEXT_SECONDARY + ";"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover { background: " + T.BG_TERTIARY + "; }"
        )
        clear_btn.clicked.connect(self._response_view.clear)
        il.addWidget(clear_btn)

        layout.addWidget(input_row)

    def set_qmp_bridge(self, bridge: Any) -> None:
        """Connect to QMP bridge."""
        self._qmp_bridge = bridge
        if bridge:
            bridge.connected.connect(self._on_connected)
            bridge.command_result.connect(self._on_result)

    def _on_connected(self, connected: bool):
        """Update connection status."""
        if connected:
            self._status_label.setText("Connected")
            self._status_label.setStyleSheet("color: " + T.STATUS_RUNNING + "; font-size: 12px;")
        else:
            self._status_label.setText("Disconnected")
            self._status_label.setStyleSheet("color: " + T.STATUS_STOPPED + "; font-size: 12px;")

    def _send_command(self, command: str):
        """Send a QMP command."""
        if not self._qmp_bridge:
            self._append_log("ERROR: QMP bridge not available", error=True)
            return
        self._append_log(f">>> {command}")
        # Use the bridge's send_command method
        self._qmp_bridge.send_command(command)
        self.command_sent.emit({"command": command})

    def _send_input(self):
        """Send command from input field."""
        text = self._cmd_input.text().strip()
        if text:
            self._send_command(text)
            self._cmd_input.clear()

    def _on_result(self, result: dict):
        """Display command result."""
        import json
        formatted = json.dumps(result, indent=2, default=str)
        self._append_log(f"<<< {formatted}")

    def _append_log(self, text: str, error: bool = False):
        """Append text to response viewer."""
        color = T.STATUS_STOPPED if error else T.TEXT_PRIMARY
        self._response_view.append(f'<span style="color: {color};">{text}</span>')
        self._response_view.moveCursor(QTextCursor.End)
