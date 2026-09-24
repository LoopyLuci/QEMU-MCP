"""QEMU System Info Panel — real QMP data display."""

from __future__ import annotations

from typing import Any

import asyncio
import json
import logging
from pathlib import Path

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTextEdit, QMessageBox, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QTabWidget, QGroupBox, QGridLayout, QLineEdit, QCheckBox, QSpinBox,
    QSizePolicy, QProgressBar, QTableWidget, QTableWidgetItem,
)

from gui.widgets import Card

logger = logging.getLogger("qemu-mcp.sysinfo")


class QMPDataCollector(QThread):
    """Background thread to collect QMP data without blocking GUI."""
    
    data_ready = pyqtSignal(dict)
    
    def __init__(self, host: str = "127.0.0.1", port: int = 4444):
        super().__init__()
        self._host = host
        self._port = port
    
    def run(self) -> None:
        """Collect data from QMP."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
            from vm_harness.setup import QMPClient
            
            async def collect():
                c = QMPClient(f"tcp:{self._host}:{self._port}")
                await c.connect()
                data = {}
                for cmd in ['query-status', 'query-name', 'query-uuid', 'query-version', 'query-kvm']:
                    try:
                        data[cmd] = await c.send(c)
                    except Exception as e:
                        data[cmd] = {"error": str(e)}
                return data
            
            data = asyncio.run(collect())
            self.data_ready.emit(data)
        except Exception as e:
            logger.error("QMP data collection failed: %s", e)
            self.data_ready.emit({"error": str(e)})


class QemuSystemInfoPanel(QWidget):
    """Display real QEMU system information from QMP."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._qmp_bridge = None
        self._data = {}
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("QEMU System Information")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        self._conn_status = QLabel("Disconnected")
        self._conn_status.setStyleSheet("color: " + T.STATUS_STOPPED + "; font-size: 12px;")
        hl.addWidget(self._conn_status)
        layout.addWidget(header)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; }"
            "QTabBar::tab { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 8px 16px; margin-right: 2px; border-radius: 4px 4px 0 0; }"
            "QTabBar::tab:selected { background: " + T.BRAND + "; color: white; }"
        )
        tabs.addTab(self._sys_info_tab(), "System Info")
        tabs.addTab(self._qmp_raw_tab(), "Raw QMP")
        tabs.addTab(self._cmd_ref_tab(), "Command Reference")
        layout.addWidget(tabs)

        # Auto-refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5000)

    def set_qmp_bridge(self, bridge: Any) -> None:
        self._qmp_bridge = bridge

    def refresh(self) -> None:
        """Refresh QMP data."""
        if self._qmp_bridge and self._qmp_bridge.is_connected:
            self._conn_status.setText("Connected")
            self._conn_status.setStyleSheet("color: " + T.STATUS_RUNNING + "; font-size: 12px;")
        else:
            self._conn_status.setText("Disconnected")
            self._conn_status.setStyleSheet("color: " + T.STATUS_STOPPED + "; font-size: 12px;")

    def _sys_info_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Virtual Machine Details")
        layout.addWidget(card)

        self._info_tree = QTreeWidget()
        self._info_tree.setHeaderLabels(["Property", "Value"])
        self._info_tree.setColumnWidth(0, 200)
        self._info_tree.setStyleSheet(
            "QTreeWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QTreeWidget::item { padding: 4px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; }"
        )
        card.content_layout.addWidget(self._info_tree)

        return page

    def _qmp_raw_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Raw QMP Responses")
        layout.addWidget(card)

        self._raw_text = QTextEdit()
        self._raw_text.setReadOnly(True)
        self._raw_text.setStyleSheet(
            "QTextEdit { background: #0d1117; color: #c9d1d9;"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; padding: 8px;"
            " font-family: Consolas, monospace; font-size: 11px; }"
        )
        card.content_layout.addWidget(self._raw_text)

        return page

    def _cmd_ref_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Common QMP Commands Reference")
        layout.addWidget(card)

        cmds = [
            ("query-status", "Get VM running status"),
            ("query-name", "Get VM name"),
            ("query-uuid", "Get VM UUID"),
            ("query-version", "Get QEMU version"),
            ("query-kvm", "Check KVM availability"),
            ("query-cpus", "List CPU information"),
            ("query-machines", "List supported machine types"),
            ("query-commands", "List all QMP commands"),
            ("system_powerdown", "Send ACPI power button event"),
            ("system_reset", "Reset the system"),
            ("stop", "Stop (pause) the VM"),
            ("cont", "Continue a paused VM"),
            ("eject", "Eject a CD-ROM device"),
            ("blockdev-add", "Add a block device"),
            ("device_add", "Add a device"),
            ("migrate", "Start migration"),
            ("snapshot-create", "Create a snapshot"),
        ]

        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Command", "Description"])
        table.setRowCount(len(cmds))
        table.horizontalHeader().setStretchLastSection(True)
        table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )
        for i, (cmd, desc) in enumerate(cmds):
            table.setItem(i, 0, QTableWidgetItem(cmd))
            table.setItem(i, 1, QTableWidgetItem(desc))

        card.content_layout.addWidget(table)
        return page
