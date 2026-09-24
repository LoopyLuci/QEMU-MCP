"""Network Config Editor Panel — visual topology editor, port forwarding, MAC, adapters, bandwidth.

Features:
  1) Visual editor for NAT/Bridged/Host-only/Internal network modes
  2) Port forwarding table with add/edit/delete
  3) MAC address configuration (auto-generate, manual, copy)
  4) Adapter selection (virtio, e1000, rtl8139, etc.)
  5) Bandwidth limits (inbound/outbound rates)
  6) Live topology diagram rendered via QPainter
"""

from __future__ import annotations

from typing import Any

import re
from typing import Optional

from gui.theme import T
from PyQt5.QtCore import Qt, QRect, QPoint, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush, QFont, QFontMetrics
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QCheckBox, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QFormLayout, QLineEdit, QGroupBox,
    QAbstractItemView, QMessageBox, QInputDialog, QFileDialog,
    QDialog, QDialogButtonBox, QTextEdit, QSplitter, QSizePolicy,
    QDoubleSpinBox, QGridLayout,
)

from gui.widgets import Card


# ── Constants ─────────────────────────────────────────────────────────────────

NETWORK_MODES = ["NAT", "Bridged", "Host-only", "Internal"]
ADAPTER_TYPES = ["virtio-net-pci", "e1000", "rtl8139", "i82551", "ne2k_pci", "pcnet"]
BANDWIDTH_UNITS = ["KB/s", "MB/s", "GB/s"]


def generate_mac() -> str:
    """Generate a random locally-administered unicast MAC address."""
    import random
    mac = [0x52, 0x54, 0x00,
           random.randint(0x00, 0xFF),
           random.randint(0x00, 0xFF),
           random.randint(0x00, 0xFF)]
    return ":".join(f"{b:02x}" for b in mac)


def validate_mac(mac: str) -> bool:
    """Validate a MAC address format (XX:XX:XX:XX:XX:XX)."""
    return bool(re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$', mac))


# ── Topology Diagram Widget ────────────────────────────────────────────────────

class TopologyDiagram(QWidget):
    """Visual network topology diagram rendered with QPainter.

    Shows the host, VM, adapter, and connection type with color-coded
    indicators for the selected network mode.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._mode = "NAT"
        self._adapter = "virtio-net-pci"
        self._mac = generate_mac()
        self._bandwidth_in = 0
        self._bandwidth_out = 0
        self._port_forwards: list[dict] = []

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.update()

    def set_adapter(self, adapter: str) -> None:
        self._adapter = adapter
        self.update()

    def set_mac(self, mac: str) -> None:
        self._mac = mac
        self.update()

    def set_bandwidth(self, inbound: int, outbound: int) -> None:
        self._bandwidth_in = inbound
        self._bandwidth_out = outbound
        self.update()

    def set_port_forwards(self, forwards: list[dict]) -> None:
        self._port_forwards = forwards
        self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor(T.BG_SECONDARY))

        # Mode color mapping
        mode_colors = {
            "NAT": QColor(T.INFO),
            "Bridged": QColor(T.SUCCESS),
            "Host-only": QColor(T.WARNING),
            "Internal": QColor(T.ACCENT),
        }
        mode_color = mode_colors.get(self._mode, QColor(T.BRAND))

        # Draw host box (top center)
        host_x = w // 2 - 60
        host_y = 20
        host_w = 120
        host_h = 50
        painter.setPen(QPen(QColor(T.BG_TERTIARY), 2))
        painter.setBrush(QColor(T.BG_PRIMARY))
        painter.drawRoundedRect(host_x, host_y, host_w, host_h, 8, 8)
        painter.setPen(QPen(QColor(T.TEXT_PRIMARY)))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(host_x, host_y, host_w, host_h, Qt.AlignCenter, "Host")

        # Draw VM box (bottom center)
        vm_x = w // 2 - 60
        vm_y = h - 70
        vm_w = 120
        vm_h = 50
        painter.setPen(QPen(QColor(T.BG_TERTIARY), 2))
        painter.setBrush(QColor(T.BG_PRIMARY))
        painter.drawRoundedRect(vm_x, vm_y, vm_w, vm_h, 8, 8)
        painter.setPen(QPen(QColor(T.TEXT_PRIMARY)))
        painter.drawText(vm_x, vm_y, vm_w, vm_h, Qt.AlignCenter, "VM")

        # Draw adapter chip (middle)
        adapter_x = w // 2 - 50
        adapter_y = h // 2 - 20
        adapter_w = 100
        adapter_h = 40
        painter.setPen(QPen(mode_color, 2))
        painter.setBrush(QColor(T.BG_TERTIARY))
        painter.drawRoundedRect(adapter_x, adapter_y, adapter_w, adapter_h, 6, 6)
        painter.setPen(QPen(mode_color))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(adapter_x, adapter_y, adapter_w, adapter_h, Qt.AlignCenter, "NIC")

        # Draw connection lines
        painter.setPen(QPen(mode_color, 2, Qt.DashLine))
        # Host to adapter
        painter.drawLine(w // 2, host_y + host_h, w // 2, adapter_y)
        # Adapter to VM
        painter.drawLine(w // 2, adapter_y + adapter_h, w // 2, vm_y)

        # Draw mode label
        painter.setPen(QPen(mode_color, 2))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        mode_text = f"Mode: {self._mode}"
        painter.drawText(10, 20, mode_text)

        # Draw MAC
        painter.setPen(QPen(QColor(T.TEXT_SECONDARY)))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(10, h - 40, f"MAC: {self._mac}")

        # Draw adapter type
        painter.drawText(10, h - 25, f"Adapter: {self._adapter}")

        # Draw bandwidth info
        bw_text = f"↑{self._bandwidth_out} ↓{self._bandwidth_in}"
        painter.drawText(10, h - 10, bw_text)

        # Draw port forward count on the right side
        if self._port_forwards:
            pf_count = len(self._port_forwards)
            painter.setPen(QPen(QColor(T.TEXT_SECONDARY)))
            painter.setFont(QFont("Segoe UI", 8))
            pf_text = f"Port Forwards: {pf_count}"
            painter.drawText(w - 120, 20, pf_text)

        # Draw cloud icon for NAT/Bridged (right side)
        if self._mode in ("NAT", "Bridged"):
            cloud_x = w - 80
            cloud_y = h // 2 - 25
            painter.setPen(QPen(QColor(T.TEXT_MUTED), 1))
            painter.setBrush(QColor(T.BG_TERTIARY))
            # Simple cloud shape
            path = QPainterPath()
            path.addEllipse(cloud_x, cloud_y + 10, 30, 25)
            path.addEllipse(cloud_x + 15, cloud_y, 35, 30)
            path.addEllipse(cloud_x + 40, cloud_y + 10, 30, 25)
            path.addEllipse(cloud_x + 10, cloud_y + 20, 50, 20)
            painter.drawPath(path)
            painter.setPen(QPen(QColor(T.TEXT_MUTED)))
            painter.setFont(QFont("Segoe UI", 7))
            painter.drawText(cloud_x, cloud_y + 55, 70, 15, Qt.AlignCenter,
                             "Internet" if self._mode == "Bridged" else "NAT")


# ── Port Forward Dialog ────────────────────────────────────────────────────────

class PortForwardDialog(QDialog):
    """Dialog for adding/editing a port forward rule."""

    def __init__(self, parent=None, rule: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("Port Forward Rule")
        self.setMinimumWidth(350)
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")

        layout = QFormLayout(self)
        layout.setSpacing(10)

        self._name = QLineEdit()
        self._name.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        layout.addRow("Name:", self._name)

        self._protocol = QComboBox()
        self._protocol.addItems(["TCP", "UDP"])
        self._protocol.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 4px;")
        layout.addRow("Protocol:", self._protocol)

        self._host_port = QSpinBox()
        self._host_port.setRange(1, 65535)
        self._host_port.setValue(2222)
        self._host_port.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 4px;")
        layout.addRow("Host Port:", self._host_port)

        self._guest_port = QSpinBox()
        self._guest_port.setRange(1, 65535)
        self._guest_port.setValue(22)
        self._guest_port.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 4px;")
        layout.addRow("Guest Port:", self._guest_port)

        self._guest_ip = QLineEdit()
        self._guest_ip.setPlaceholderText("optional (e.g. 10.0.2.15)")
        self._guest_ip.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        layout.addRow("Guest IP:", self._guest_ip)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.setStyleSheet("QPushButton { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px 16px; }")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        # Pre-fill if editing
        if rule:
            self._name.setText(rule.get("name", ""))
            self._protocol.setCurrentText(rule.get("protocol", "TCP"))
            self._host_port.setValue(rule.get("host_port", 2222))
            self._guest_port.setValue(rule.get("guest_port", 22))
            self._guest_ip.setText(rule.get("guest_ip", ""))

    def get_rule(self) -> dict:
        return {
            "name": self._name.text(),
            "protocol": self._protocol.currentText(),
            "host_port": self._host_port.value(),
            "guest_port": self._guest_port.value(),
            "guest_ip": self._guest_ip.text(),
        }


# ── Main Panel ─────────────────────────────────────────────────────────────────

class NetworkConfigEditor(QWidget):
    """Network Configuration Editor panel.

    Provides a visual editor for network configuration including:
    - Network mode selection (NAT/Bridged/Host-only/Internal)
    - Port forwarding table
    - MAC address configuration
    - Adapter type selection
    - Bandwidth limits
    - Live topology diagram
    """

    config_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        self._port_forwards: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Network Config Editor")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        layout.addWidget(header)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: " + T.BG_TERTIARY + "; }")

        # Left side: config tabs
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; }"
            "QTabBar::tab { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 8px 16px; margin-right: 2px; border-radius: 4px 4px 0 0; }"
            "QTabBar::tab:selected { background: " + T.BRAND + "; color: white; }"
        )
        tabs.addTab(self._mode_tab(), "Network Mode")
        tabs.addTab(self._port_fwd_tab(), "Port Forwarding")
        tabs.addTab(self._adapter_tab(), "Adapter & MAC")
        tabs.addTab(self._bandwidth_tab(), "Bandwidth")
        left_layout.addWidget(tabs)

        # Apply button
        apply_btn = QPushButton("Apply Configuration")
        apply_btn.setFixedHeight(36)
        apply_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        apply_btn.clicked.connect(self._apply_config)
        left_layout.addWidget(apply_btn)

        splitter.addWidget(left_widget)

        # Right side: diagram
        diagram_card = Card("Topology Diagram")
        self._diagram = TopologyDiagram()
        self._diagram.setMinimumWidth(350)
        diagram_card.content_layout.addWidget(self._diagram)
        splitter.addWidget(diagram_card)

        splitter.setSizes([500, 400])
        layout.addWidget(splitter)

    def _mode_tab(self) -> QWidget:
        """Network mode selection tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Network Mode")
        form = QFormLayout()
        form.setSpacing(10)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(NETWORK_MODES)
        self._mode_combo.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        form.addRow("Mode:", self._mode_combo)

        self._mode_desc = QLabel()
        self._mode_desc.setWordWrap(True)
        self._mode_desc.setStyleSheet("color: " + T.TEXT_MUTED + "; font-size: 11px;")
        form.addRow("", self._mode_desc)

        card.content_layout.addLayout(form)
        layout.addWidget(card)

        # Mode-specific options
        self._mode_options_card = Card("Mode Options")
        self._mode_options_layout = QFormLayout()
        self._mode_options_layout.setSpacing(8)
        self._mode_options_card.content_layout.addLayout(self._mode_options_layout)
        layout.addWidget(self._mode_options_card)

        # Bridged interface selector
        self._bridge_iface = QComboBox()
        self._bridge_iface.addItems(["eth0", "wlan0", "enp0s3", "br0"])
        self._bridge_iface.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 4px;")

        # Host-only network selector
        self._hostonly_net = QComboBox()
        self._hostonly_net.addItems(["vnet0", "vnet1", "vnet2"])
        self._hostonly_net.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 4px;")

        # Internal network name
        self._internal_name = QLineEdit()
        self._internal_name.setPlaceholderText("Network name (e.g. 'isolated')")
        self._internal_name.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")

        # NAT options
        self._nat_ipv4 = QCheckBox("Enable IPv4 forwarding")
        self._nat_ipv4.setChecked(True)
        self._nat_ipv4.setStyleSheet("color: " + T.TEXT_SECONDARY + "; font-size: 12px;")
        self._nat_ipv6 = QCheckBox("Enable IPv6 forwarding")
        self._nat_ipv6.setStyleSheet("color: " + T.TEXT_SECONDARY + "; font-size: 12px;")

        self._update_mode_options()
        layout.addStretch()
        return page

    def _update_mode_options(self):
        """Update mode-specific options based on selected mode."""
        # Clear existing options
        while self._mode_options_layout.count():
            item = self._mode_options_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        mode = self._mode_combo.currentText()
        descriptions = {
            "NAT": "VM shares host's IP. Outbound only — no direct inbound access without port forwards.",
            "Bridged": "VM appears as a separate device on the physical network. Gets its own IP from DHCP.",
            "Host-only": "VM can communicate with host and other VMs, but has no external network access.",
            "Internal": "Fully isolated network — VMs can only talk to each other, no host access.",
        }
        self._mode_desc.setText(descriptions.get(mode, ""))

        if mode == "Bridged":
            self._mode_options_layout.addRow("Bridge Interface:", self._bridge_iface)
        elif mode == "Host-only":
            self._mode_options_layout.addRow("Host-only Network:", self._hostonly_net)
        elif mode == "Internal":
            self._mode_options_layout.addRow("Network Name:", self._internal_name)
        elif mode == "NAT":
            self._mode_options_layout.addRow(self._nat_ipv4)
            self._mode_options_layout.addRow(self._nat_ipv6)

    def _on_mode_changed(self, mode: str):
        self._update_mode_options()
        self._diagram.set_mode(mode)

    def _port_fwd_tab(self) -> QWidget:
        """Port forwarding table tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Port Forward Rules")
        card_layout = QVBoxLayout()
        card_layout.setSpacing(8)

        # Table
        self._pf_table = QTableWidget()
        self._pf_table.setColumnCount(5)
        self._pf_table.setHorizontalHeaderLabels(["Name", "Protocol", "Host Port", "Guest Port", "Guest IP"])
        self._pf_table.horizontalHeader().setStretchLastSection(True)
        self._pf_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._pf_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._pf_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._pf_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
            "QTableWidget::item { padding: 4px; }"
            "QTableWidget::item:selected { background: " + T.BRAND + "; color: white; }"
        )
        card_layout.addWidget(self._pf_table)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)

        add_btn = QPushButton("Add Rule")
        add_btn.setFixedSize(90, 30)
        add_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        add_btn.clicked.connect(self._add_port_forward)
        bl.addWidget(add_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(70, 30)
        edit_btn.setStyleSheet(
            "QPushButton { background: " + T.BRAND + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: " + T.BRAND_HOVER + "; }"
        )
        edit_btn.clicked.connect(self._edit_port_forward)
        bl.addWidget(edit_btn)

        del_btn = QPushButton("Delete")
        del_btn.setFixedSize(80, 30)
        del_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #dc2626; }"
        )
        del_btn.clicked.connect(self._delete_port_forward)
        bl.addWidget(del_btn)

        bl.addStretch()
        card_layout.addWidget(btn_row)
        card.content_layout.addLayout(card_layout)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _adapter_tab(self) -> QWidget:
        """Adapter and MAC configuration tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Adapter selection
        adapter_card = Card("Adapter Type")
        form = QFormLayout()
        form.setSpacing(10)

        self._adapter_combo = QComboBox()
        self._adapter_combo.addItems(ADAPTER_TYPES)
        self._adapter_combo.setCurrentText("virtio-net-pci")
        self._adapter_combo.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        self._adapter_combo.currentTextChanged.connect(self._on_adapter_changed)
        form.addRow("Type:", self._adapter_combo)

        adapter_info = QLabel("virtio-net-paravirtualized — best performance with drivers")
        adapter_info.setStyleSheet("color: " + T.TEXT_MUTED + "; font-size: 11px;")
        adapter_info.setWordWrap(True)
        form.addRow("", adapter_info)
        self._adapter_info = adapter_info

        adapter_card.content_layout.addLayout(form)
        layout.addWidget(adapter_card)

        # MAC configuration
        mac_card = Card("MAC Address")
        mac_layout = QVBoxLayout()
        mac_layout.setSpacing(8)

        mac_input_row = QWidget()
        mil = QHBoxLayout(mac_input_row)
        mil.setContentsMargins(0, 0, 0, 0)

        self._mac_input = QLineEdit()
        self._mac_input.setText(generate_mac())
        self._mac_input.setInputMask("HH:HH:HH:HH:HH:HH;_")
        self._mac_input.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px; font-family: Consolas, monospace;")
        mil.addWidget(self._mac_input)

        gen_btn = QPushButton("Generate")
        gen_btn.setFixedSize(80, 28)
        gen_btn.setStyleSheet(
            "QPushButton { background: " + T.BG_TERTIARY + "; border: none; border-radius: 4px;"
            " color: " + T.TEXT_PRIMARY + "; font-size: 11px; }"
            "QPushButton:hover { background: " + T.BRAND + "; color: white; }"
        )
        gen_btn.clicked.connect(self._generate_mac)
        mil.addWidget(gen_btn)

        mac_layout.addWidget(mac_input_row)

        # MAC validation label
        self._mac_status = QLabel("✓ Valid MAC address")
        self._mac_status.setStyleSheet("color: " + T.SUCCESS + "; font-size: 11px;")
        mac_layout.addWidget(self._mac_status)

        self._mac_input.textChanged.connect(self._validate_mac_input)

        mac_card.content_layout.addLayout(mac_layout)
        layout.addWidget(mac_card)

        # Adapter count
        count_card = Card("Adapter Count")
        count_form = QFormLayout()
        count_form.setSpacing(8)

        self._adapter_count = QSpinBox()
        self._adapter_count.setRange(1, 8)
        self._adapter_count.setValue(1)
        self._adapter_count.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 4px;")
        count_form.addRow("Number of NICs:", self._adapter_count)

        count_card.content_layout.addLayout(count_form)
        layout.addWidget(count_card)

        layout.addStretch()
        return page

    def _bandwidth_tab(self) -> QWidget:
        """Bandwidth limits tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Bandwidth Limits")
        form = QFormLayout()
        form.setSpacing(10)

        # Inbound
        self._bw_inbound = QSpinBox()
        self._bw_inbound.setRange(0, 100000)
        self._bw_inbound.setValue(0)
        self._bw_inbound.setSpecialValueText("Unlimited")
        self._bw_inbound.setSuffix(" KB/s")
        self._bw_inbound.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 4px;")
        form.addRow("Inbound Rate:", self._bw_inbound)

        # Outbound
        self._bw_outbound = QSpinBox()
        self._bw_outbound.setRange(0, 100000)
        self._bw_outbound.setValue(0)
        self._bw_outbound.setSpecialValueText("Unlimited")
        self._bw_outbound.setSuffix(" KB/s")
        self._bw_outbound.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 4px;")
        form.addRow("Outbound Rate:", self._bw_outbound)

        # Burst
        self._bw_burst = QSpinBox()
        self._bw_burst.setRange(0, 1000000)
        self._bw_burst.setValue(0)
        self._bw_burst.setSpecialValueText("Default")
        self._bw_burst.setSuffix(" KB")
        self._bw_burst.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 4px;")
        form.addRow("Burst Size:", self._bw_burst)

        # Enable checkbox
        self._bw_enable = QCheckBox("Enable bandwidth limiting")
        self._bw_enable.setStyleSheet("color: " + T.TEXT_SECONDARY + "; font-size: 12px;")
        self._bw_enable.toggled.connect(self._on_bw_toggled)
        form.addRow("", self._bw_enable)

        # Connect bandwidth value changes to diagram
        self._bw_inbound.valueChanged.connect(self._on_bandwidth_changed)
        self._bw_outbound.valueChanged.connect(self._on_bandwidth_changed)

        card.content_layout.addLayout(form)
        layout.addWidget(card)

        # Info
        info_card = Card("Info")
        info_text = QLabel(
            "Bandwidth limits apply to the virtual NIC using QEMU's QOS system.\n"
            "0 = unlimited. Limits are applied per-adapter.\n\n"
            "Note: Actual throughput may vary based on host load and virtio settings."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: " + T.TEXT_MUTED + "; font-size: 11px;")
        info_card.content_layout.addWidget(info_text)
        layout.addWidget(info_card)

        layout.addStretch()
        return page

    def _on_bw_toggled(self, enabled: bool):
        self._bw_inbound.setEnabled(enabled)
        self._bw_outbound.setEnabled(enabled)
        self._bw_burst.setEnabled(enabled)

    def _on_bandwidth_changed(self, value):
        self._diagram.set_bandwidth(
            self._bw_inbound.value(),
            self._bw_outbound.value(),
        )

    def _on_adapter_changed(self, adapter: str):
        descriptions = {
            "virtio-net-pci": "Paravirtualized — best performance with virtio drivers",
            "e1000": "Intel PRO/1000 — widely supported, good compatibility",
            "rtl8139": "Realtek 8139 — legacy, broad guest OS support",
            "i82551": "Intel 82551 — older Intel emulated NIC",
            "ne2k_pci": "NE2000 PCI — very legacy, minimal overhead",
            "pcnet": "AMD PCnet — legacy, good for older OS",
        }
        self._adapter_info.setText(descriptions.get(adapter, ""))
        self._diagram.set_adapter(adapter)

    def _generate_mac(self):
        mac = generate_mac()
        self._mac_input.setText(mac)
        self._diagram.set_mac(mac)

    def _validate_mac_input(self, text: str):
        if validate_mac(text):
            self._mac_status.setText("✓ Valid MAC address")
            self._mac_status.setStyleSheet("color: " + T.SUCCESS + "; font-size: 11px;")
            self._diagram.set_mac(text)
        else:
            self._mac_status.setText("✗ Invalid MAC format (use XX:XX:XX:XX:XX:XX)")
            self._mac_status.setStyleSheet("color: " + T.ERROR + "; font-size: 11px;")

    def _add_port_forward(self):
        dialog = PortForwardDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            rule = dialog.get_rule()
            self._port_forwards.append(rule)
            self._refresh_pf_table()

    def _edit_port_forward(self):
        row = self._pf_table.currentRow()
        if row < 0 or row >= len(self._port_forwards):
            QMessageBox.warning(self, "Warning", "Select a rule to edit")
            return
        dialog = PortForwardDialog(self, self._port_forwards[row])
        if dialog.exec_() == QDialog.Accepted:
            self._port_forwards[row] = dialog.get_rule()
            self._refresh_pf_table()

    def _delete_port_forward(self):
        row = self._pf_table.currentRow()
        if row < 0 or row >= len(self._port_forwards):
            QMessageBox.warning(self, "Warning", "Select a rule to delete")
            return
        del self._port_forwards[row]
        self._refresh_pf_table()

    def _refresh_pf_table(self):
        self._pf_table.setRowCount(len(self._port_forwards))
        for i, rule in enumerate(self._port_forwards):
            self._pf_table.setItem(i, 0, QTableWidgetItem(rule.get("name", "")))
            self._pf_table.setItem(i, 1, QTableWidgetItem(rule.get("protocol", "TCP")))
            self._pf_table.setItem(i, 2, QTableWidgetItem(str(rule.get("host_port", ""))))
            self._pf_table.setItem(i, 3, QTableWidgetItem(str(rule.get("guest_port", ""))))
            self._pf_table.setItem(i, 4, QTableWidgetItem(rule.get("guest_ip", "")))
        self._diagram.set_port_forwards(self._port_forwards)

    def _apply_config(self):
        config = self.get_config()
        self.config_changed.emit(config)
        QMessageBox.information(self, "Applied", "Network configuration applied successfully.")

    def get_config(self) -> dict:
        """Return the current network configuration as a dict."""
        return {
            "mode": self._mode_combo.currentText(),
            "adapter": self._adapter_combo.currentText(),
            "mac": self._mac_input.text(),
            "adapter_count": self._adapter_count.value(),
            "port_forwards": list(self._port_forwards),
            "bandwidth": {
                "enabled": self._bw_enable.isChecked(),
                "inbound_kbps": self._bw_inbound.value(),
                "outbound_kbps": self._bw_outbound.value(),
                "burst_kb": self._bw_burst.value(),
            },
            "mode_options": self._get_mode_options(),
        }

    def _get_mode_options(self) -> dict:
        mode = self._mode_combo.currentText()
        if mode == "Bridged":
            return {"bridge_iface": self._bridge_iface.currentText()}
        elif mode == "Host-only":
            return {"network": self._hostonly_net.currentText()}
        elif mode == "Internal":
            return {"name": self._internal_name.text()}
        elif mode == "NAT":
            return {
                "ipv4_forward": self._nat_ipv4.isChecked(),
                "ipv6_forward": self._nat_ipv6.isChecked(),
            }
        return {}

    def set_config(self, config: dict) -> None:
        """Set the panel state from a config dict."""
        if "mode" in config:
            idx = self._mode_combo.findText(config["mode"])
            if idx >= 0:
                self._mode_combo.setCurrentIndex(idx)
        if "adapter" in config:
            idx = self._adapter_combo.findText(config["adapter"])
            if idx >= 0:
                self._adapter_combo.setCurrentIndex(idx)
        if "mac" in config:
            self._mac_input.setText(config["mac"])
        if "adapter_count" in config:
            self._adapter_count.setValue(config["adapter_count"])
        if "port_forwards" in config:
            self._port_forwards = list(config["port_forwards"])
            self._refresh_pf_table()
        if "bandwidth" in config:
            bw = config["bandwidth"]
            self._bw_enable.setChecked(bw.get("enabled", False))
            self._bw_inbound.setValue(bw.get("inbound_kbps", 0))
            self._bw_outbound.setValue(bw.get("outbound_kbps", 0))
            self._bw_burst.setValue(bw.get("burst_kb", 0))
