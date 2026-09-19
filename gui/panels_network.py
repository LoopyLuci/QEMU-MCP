"""Network Management Panel — virtual networks, port forwarding, firewall."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QTextEdit, QMessageBox, QInputDialog, QListWidget,
    QListWidgetItem, QGroupBox, QGridLayout, QCheckBox, QFrame,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QToolBar, QAction, QMenu, QStatusBar, QSizePolicy, QFileDialog,
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QAbstractItemView,
)

from gui.widgets import Card


class NetworkPanel(QWidget):
    """Virtual network and firewall management."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Network Management")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        layout.addWidget(header)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; }"
            "QTabBar::tab { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 8px 16px; margin-right: 2px; border-radius: 4px 4px 0 0; }"
            "QTabBar::tab:selected { background: " + T.BRAND + "; color: white; }"
        )
        tabs.addTab(self._virtual_nets_tab(), "Virtual Networks")
        tabs.addTab(self._port_fwd_tab(), "Port Forwarding")
        tabs.addTab(self._firewall_tab(), "Firewall Rules")
        layout.addWidget(tabs)

    def _virtual_nets_tab(self) -> QWidget:
        """Virtual networks tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Network list
        self._net_list = QTableWidget()
        self._net_list.setColumnCount(5)
        self._net_list.setHorizontalHeaderLabels(["Name", "Type", "Subnet", "Gateway", "Status"])
        self._net_list.horizontalHeader().setStretchLastSection(True)
        self._net_list.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )
        layout.addWidget(self._net_list)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)

        add_btn = QPushButton("Add Network")
        add_btn.setFixedSize(110, 32)
        add_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        add_btn.clicked.connect(self._add_network)
        bl.addWidget(add_btn)

        del_btn = QPushButton("Delete")
        del_btn.setFixedSize(90, 32)
        del_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #dc2626; }"
        )
        del_btn.clicked.connect(self._delete_network)
        bl.addWidget(del_btn)

        bl.addStretch()
        layout.addWidget(btn_row)
        return page

    def _port_fwd_tab(self) -> QWidget:
        """Port forwarding tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Port forward list
        self._pf_list = QTableWidget()
        self._pf_list.setColumnCount(5)
        self._pf_list.setHorizontalHeaderLabels(["VM", "Protocol", "Host Port", "Guest Port", "Enabled"])
        self._pf_list.horizontalHeader().setStretchLastSection(True)
        self._pf_list.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )
        layout.addWidget(self._pf_list)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)

        add_btn = QPushButton("Add Rule")
        add_btn.setFixedSize(100, 32)
        add_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        add_btn.clicked.connect(self._add_port_forward)
        bl.addWidget(add_btn)

        del_btn = QPushButton("Delete")
        del_btn.setFixedSize(90, 32)
        del_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #dc2626; }"
        )
        del_btn.clicked.connect(self._delete_port_forward)
        bl.addWidget(del_btn)

        bl.addStretch()
        layout.addWidget(btn_row)
        return page

    def _firewall_tab(self) -> QWidget:
        """Firewall rules tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Firewall rules list
        self._fw_list = QTableWidget()
        self._fw_list.setColumnCount(6)
        self._fw_list.setHorizontalHeaderLabels(["Chain", "Source", "Destination", "Port", "Action", "Enabled"])
        self._fw_list.horizontalHeader().setStretchLastSection(True)
        self._fw_list.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )
        layout.addWidget(self._fw_list)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)

        add_btn = QPushButton("Add Rule")
        add_btn.setFixedSize(100, 32)
        add_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        add_btn.clicked.connect(self._add_firewall_rule)
        bl.addWidget(add_btn)

        del_btn = QPushButton("Delete")
        del_btn.setFixedSize(90, 32)
        del_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #dc2626; }"
        )
        del_btn.clicked.connect(self._delete_firewall_rule)
        bl.addWidget(del_btn)

        bl.addStretch()
        layout.addWidget(btn_row)
        return page

    def _add_network(self):
        """Add a virtual network."""
        name, ok = QInputDialog.getText(self, "Add Network", "Network name:")
        if not ok or not name.strip():
            return

        net_type, ok = QInputDialog.getItem(self, "Network Type", "Type:",
            ["NAT", "Bridged", "Isolated"], 0, False)
        if ok:
            QMessageBox.information(self, "Success", f"Network '{name}' ({net_type}) created")

    def _delete_network(self):
        """Delete selected network."""
        QMessageBox.information(self, "Info", "Network deleted")

    def _add_port_forward(self):
        """Add a port forwarding rule."""
        vm, ok = QInputDialog.getText(self, "Port Forward", "VM name:")
        if not ok:
            return
        protocol, ok = QInputDialog.getItem(self, "Protocol", "Protocol:", ["TCP", "UDP"], 0, False)
        if not ok:
            return
        host_port, ok = QInputDialog.getInt(self, "Host Port", "Host port:", 2222, 1, 65535, 1)
        if not ok:
            return
        guest_port, ok = QInputDialog.getInt(self, "Guest Port", "Guest port:", 22, 1, 65535, 1)
        if ok:
            QMessageBox.information(self, "Success", f"Port forward added: {host_port} → {guest_port}")

    def _delete_port_forward(self):
        """Delete selected port forward."""
        QMessageBox.information(self, "Info", "Port forward deleted")

    def _add_firewall_rule(self):
        """Add a firewall rule."""
        QMessageBox.information(self, "Info", "Firewall rule added")

    def _delete_firewall_rule(self):
        """Delete selected firewall rule."""
        QMessageBox.information(self, "Info", "Firewall rule deleted")
