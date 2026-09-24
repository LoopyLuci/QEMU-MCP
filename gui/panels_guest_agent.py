"""Guest Agent & Integration Panel — QEMU guest agent operations."""

from __future__ import annotations

from typing import Any

import json
from pathlib import Path

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTextEdit, QMessageBox, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QTabWidget, QGroupBox, QGridLayout, QLineEdit, QSpinBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QSplitter, QFrame, QProgressBar,
    QSizePolicy, QFileDialog, QInputDialog, QAbstractItemView, QApplication,
)

from gui.widgets import Card


class GuestAgentPanel(QWidget):
    """QEMU guest agent management and guest introspection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._qmp_bridge = None
        self._ssh_bridge = None
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Guest Agent & Integration")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        self._agent_status = QLabel("Agent: Unknown")
        self._agent_status.setStyleSheet("color: " + T.WARNING + "; font-size: 12px;")
        hl.addWidget(self._agent_status)
        layout.addWidget(header)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; }"
            "QTabBar::tab { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 8px 16px; margin-right: 2px; border-radius: 4px 4px 0 0; }"
            "QTabBar::tab:selected { background: " + T.BRAND + "; color: white; }"
        )
        tabs.addTab(self._guest_info_tab(), "Guest Info")
        tabs.addTab(self._processes_tab(), "Processes")
        tabs.addTab(self._services_tab(), "Services")
        tabs.addTab(self._files_tab(), "File Browser")
        tabs.addTab(self._network_tab(), "Network")
        layout.addWidget(tabs)

    def set_qmp_bridge(self, bridge: Any) -> None:
        """Connect to QMP bridge."""
        self._qmp_bridge = bridge

    def set_ssh_bridge(self, bridge: Any) -> None:
        """Connect to SSH bridge for real guest data."""
        self._ssh_bridge = bridge
        if bridge:
            bridge.command_output.connect(self._on_command_output)
            bridge.file_list.connect(self._on_file_list)
            bridge.error.connect(self._on_ssh_error)
            bridge.connected.connect(self._on_ssh_connected)
            # Fetch real data when connected
            self._refresh_all()

    def _refresh_all(self):
        """Refresh all guest data via SSH."""
        if not self._ssh_bridge:
            return
        # Fetch processes
        self._ssh_bridge.run_command("ps aux --no-headers | head -20")
        # Fetch services
        self._ssh_bridge.run_command("systemctl list-units --type=service --state=running --no-pager | head -10")
        # Fetch network
        self._ssh_bridge.run_command("ip addr show")
        # Fetch files
        self._ssh_bridge.list_dir("/home/omarchyvm")

    def _on_ssh_connected(self, connected: bool):
        """Handle SSH connection."""
        if connected:
            self._agent_status.setText("Agent: Connected (SSH)")
            self._agent_status.setStyleSheet("color: " + T.STATUS_RUNNING + "; font-size: 12px;")
        else:
            self._agent_status.setText("Agent: Disconnected")
            self._agent_status.setStyleSheet("color: " + T.STATUS_STOPPED + "; font-size: 12px;")

    def _on_command_output(self, output: str):
        """Handle command output from SSH."""
        # Parse process list or service list based on content
        if "ps aux" in output or "PID" in output:
            self._parse_processes(output)
        elif "systemctl" in output or "LOAD" in output:
            self._parse_services(output)
        elif "ip addr" in output or "inet " in output:
            self._parse_network(output)

    def _on_file_list(self, files: list):
        """Handle file list from SSH."""
        self._populate_file_tree(files)

    def _on_ssh_error(self, message: str):
        """Handle SSH error."""
        self._agent_status.setText("Agent: Error")
        self._agent_status.setStyleSheet("color: " + T.ERROR + "; font-size: 12px;")

    def _parse_processes(self, output: str):
        """Parse ps aux output into process table."""
        lines = output.strip().split("\n")[1:]  # Skip header
        self._proc_table.setRowCount(0)
        for i, line in enumerate(lines[:50]):  # Limit to 50 processes
            parts = line.split(None, 10)
            if len(parts) >= 11:
                row = self._proc_table.rowCount()
                self._proc_table.insertRow(row)
                self._proc_table.setItem(row, 0, QTableWidgetItem(parts[1]))  # PID
                self._proc_table.setItem(row, 1, QTableWidgetItem(parts[10]))  # Command
                self._proc_table.setItem(row, 2, QTableWidgetItem(parts[2]))  # CPU%
                self._proc_table.setItem(row, 3, QTableWidgetItem(parts[3]))  # MEM%
                self._proc_table.setItem(row, 4, QTableWidgetItem("Running"))

    def _parse_services(self, output: str):
        """Parse systemctl output into services table."""
        lines = output.strip().split("\n")[1:]  # Skip header
        self._svc_table.setRowCount(0)
        for i, line in enumerate(lines[:20]):  # Limit to 20 services
            parts = line.split(None, 4)
            if len(parts) >= 4:
                row = self._svc_table.rowCount()
                self._svc_table.insertRow(row)
                self._svc_table.setItem(row, 0, QTableWidgetItem(parts[0]))  # Unit
                self._svc_table.setItem(row, 1, QTableWidgetItem(parts[3]))  # Sub
                self._svc_table.setItem(row, 2, QTableWidgetItem("Yes" if parts[3] == "running" else "No"))
                self._svc_table.setItem(row, 3, QTableWidgetItem(parts[4] if len(parts) > 4 else ""))

    def _populate_file_tree(self, files: list):
        """Populate file tree from SSH directory listing."""
        self._file_tree.clear()
        for f in files:
            path = f.get("path", f.get("name", ""))
            name = f.get("name", path.split("/")[-1])
            size = f.get("size", "")
            mtime = f.get("mtime", "")
            is_dir = f.get("type") == "dir"
            item = QTreeWidgetItem(self._file_tree, [name, str(size), mtime, "Directory" if is_dir else "File"])
            item.setData(0, Qt.UserRole, path)

    def _parse_network(self, output: str):
        """Parse ip addr output into network info."""
        self._net_info.setText(output)

    def _guest_info_tab(self) -> QWidget:
        """Guest information dashboard."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

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
        
        # Seed sample info
        info = {
            "Operating System": "Omarchy Linux",
            "Kernel": "6.1.0-arch1-1",
            "Hostname": "omarchy-vm",
            "Uptime": "2 days, 4 hours",
            "IP Addresses": "192.168.122.100 (eth0)",
            "Disk Usage": "2.1 GB / 40 GB (5%)",
            "Memory": "1.2 GB / 4.0 GB (30%)",
            "Load Average": "0.15, 0.08, 0.02",
            "QEMU Guest Agent": "Connected",
        }
        for key, val in info.items():
            QTreeWidgetItem(self._info_tree, [key, val])
        
        layout.addWidget(self._info_tree)

        # Refresh button
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        refresh_btn = QPushButton("Refresh Info")
        refresh_btn.setFixedSize(110, 32)
        refresh_btn.setStyleSheet(
            "QPushButton { background: " + T.BRAND + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: " + T.BRAND_HOVER + "; }"
        )
        bl.addWidget(refresh_btn)
        bl.addStretch()
        layout.addWidget(btn_row)
        return page

    def _processes_tab(self) -> QWidget:
        """Process manager."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        self._proc_table = QTableWidget()
        self._proc_table.setColumnCount(5)
        self._proc_table.setHorizontalHeaderLabels(["PID", "Name", "CPU %", "Memory %", "Status"])
        self._proc_table.horizontalHeader().setStretchLastSection(True)
        self._proc_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )
        
        # Sample processes
        sample_procs = [
            ["1", "systemd", "0.0", "0.1", "Running"],
            ["245", "qemu-ga", "0.0", "0.1", "Running"],
            ["1024", "bash", "0.1", "0.2", "Running"],
            ["2048", "firefox", "12.5", "8.3", "Running"],
        ]
        self._proc_table.setRowCount(len(sample_procs))
        for i, proc in enumerate(sample_procs):
            for j, val in enumerate(proc):
                self._proc_table.setItem(i, j, QTableWidgetItem(val))
        
        layout.addWidget(self._proc_table)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        
        kill_btn = QPushButton("Kill Process")
        kill_btn.setFixedSize(110, 32)
        kill_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #dc2626; }"
        )
        bl.addWidget(kill_btn)
        bl.addStretch()
        layout.addWidget(btn_row)
        return page

    def _services_tab(self) -> QWidget:
        """Service manager."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        self._svc_table = QTableWidget()
        self._svc_table.setColumnCount(4)
        self._svc_table.setHorizontalHeaderLabels(["Service", "Status", "Enabled", "Description"])
        self._svc_table.horizontalHeader().setStretchLastSection(True)
        self._svc_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )
        
        services = [
            ["sshd", "Running", "Yes", "OpenSSH server"],
            ["nginx", "Stopped", "No", "Web server"],
            ["docker", "Running", "Yes", "Container runtime"],
            ["firewalld", "Running", "Yes", "Firewall daemon"],
        ]
        self._svc_table.setRowCount(len(services))
        for i, svc in enumerate(services):
            for j, val in enumerate(svc):
                self._svc_table.setItem(i, j, QTableWidgetItem(val))
        
        layout.addWidget(self._svc_table)
        return page

    def _files_tab(self) -> QWidget:
        """File browser."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Path bar
        path_row = QWidget()
        pl = QHBoxLayout(path_row)
        pl.setContentsMargins(0, 0, 0, 0)
        self._path_input = QLineEdit("/home/omarchyvm")
        self._path_input.setStyleSheet(
            "QLineEdit { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px; }"
        )
        pl.addWidget(self._path_input)
        go_btn = QPushButton("Go")
        go_btn.setFixedSize(50, 28)
        go_btn.setStyleSheet("background: " + T.BRAND + "; border: none; border-radius: 4px; color: white;")
        pl.addWidget(go_btn)
        layout.addWidget(path_row)

        # File tree
        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderLabels(["Name", "Size", "Modified", "Type"])
        self._file_tree.setColumnWidth(0, 250)
        self._file_tree.setStyleSheet(
            "QTreeWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; }"
        )
        
        # Sample files
        root = self._file_tree.invisibleRootItem()
        QTreeWidgetItem(root, ["Documents", "--", "2024-01-15", "Directory"])
        QTreeWidgetItem(root, ["Downloads", "--", "2024-01-14", "Directory"])
        QTreeWidgetItem(root, ["notes.txt", "2.4 KB", "2024-01-15", "Text"])
        QTreeWidgetItem(root, ["backup.tar.gz", "45 MB", "2024-01-10", "Archive"])
        
        layout.addWidget(self._file_tree)
        return page

    def _network_tab(self) -> QWidget:
        """Guest network info."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        self._net_info = QTextEdit()
        self._net_info.setReadOnly(True)
        self._net_info.setStyleSheet(
            "QTextEdit { background: #0d1117; color: #c9d1d9;"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; padding: 8px;"
            " font-family: Consolas, monospace; font-size: 11px; }"
        )
        self._net_info.setText("""Network Interfaces:
  eth0: 192.168.122.100/24 (DHCP)
  lo: 127.0.0.1/8

Routing:
  default via 192.168.122.1 dev eth0

DNS:
  8.8.8.8
  8.8.4.4

Open Ports:
  22/tcp  sshd
  80/tcp  nginx
""")
        layout.addWidget(self._net_info)
        return page
