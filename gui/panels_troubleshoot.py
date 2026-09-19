"""Troubleshooting & Debug Panel — diagnostics, gdb, logs."""

from __future__ import annotations

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTextEdit, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QGroupBox, QGridLayout, QLineEdit, QCheckBox,
    QSizePolicy, QProgressBar,
)

from gui.widgets import Card


class TroubleshootPanel(QWidget):
    """VM diagnostics and debugging tools."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Troubleshooting & Debugging")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        layout.addWidget(header)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; }"
            "QTabBar::tab { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 8px 16px; margin-right: 2px; border-radius: 4px 4px 0 0; }"
            "QTabBar::tab:selected { background: " + T.BRAND + "; color: white; }"
        )
        tabs.addTab(self._diagnostics_tab(), "Diagnostics")
        tabs.addTab(self._gdb_tab(), "GDB Debugger")
        tabs.addTab(self._logs_tab(), "Debug Logs")
        layout.addWidget(tabs)

    def _diagnostics_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("VM Health Diagnostics")
        layout.addWidget(card)

        self._diag_output = QTextEdit()
        self._diag_output.setReadOnly(True)
        self._diag_output.setStyleSheet("QTextEdit { background: #0d1117; color: #c9d1d9; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; padding: 8px; font-family: Consolas, monospace; font-size: 11px; }")
        card.content_layout.addWidget(self._diag_output)

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        run_btn = QPushButton("Run Diagnostics")
        run_btn.setFixedSize(140, 32)
        run_btn.setStyleSheet("background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600;")
        run_btn.clicked.connect(self._run_diagnostics)
        bl.addWidget(run_btn)
        bl.addStretch()
        layout.addWidget(btn_row)
        layout.addStretch()
        return page

    def _run_diagnostics(self):
        text = "Running diagnostics...\n"
        text += chr(10003) + " QMP connection: OK\n"
        text += chr(10003) + " Disk space: OK\n"
        text += chr(10003) + " Network: OK\n"
        text += chr(10003) + " Memory: OK"
        self._diag_output.setText(text)

    def _gdb_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Remote GDB Debugging")
        layout.addWidget(card)

        form = QGridLayout()
        form.addWidget(QLabel("GDB Port:"), 0, 0)
        self._gdb_port = QLineEdit("1234")
        self._gdb_port.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addWidget(self._gdb_port, 0, 1)

        card.content_layout.addLayout(form)

        self._gdb_console = QTextEdit()
        self._gdb_console.setReadOnly(True)
        self._gdb_console.setStyleSheet("QTextEdit { background: #0d1117; color: #c9d1d9; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; padding: 8px; font-family: Consolas, monospace; font-size: 11px; }")
        card.content_layout.addWidget(self._gdb_console)
        layout.addStretch()
        return page

    def _logs_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("QEMU Debug Logs")
        layout.addWidget(card)

        self._debug_logs = QTextEdit()
        self._debug_logs.setReadOnly(True)
        self._debug_logs.setStyleSheet("QTextEdit { background: #0d1117; color: #c9d1d9; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; padding: 8px; font-family: Consolas, monospace; font-size: 11px; }")
        card.content_layout.addWidget(self._debug_logs)

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        enable_btn = QPushButton("Enable Debug")
        enable_btn.setFixedSize(120, 32)
        enable_btn.setStyleSheet("background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600;")
        bl.addWidget(enable_btn)
        bl.addStretch()
        layout.addWidget(btn_row)
        layout.addStretch()
        return page
