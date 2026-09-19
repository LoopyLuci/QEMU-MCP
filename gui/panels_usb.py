"""USB & Device Management Panel."""

from __future__ import annotations

from gui.theme import T
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QCheckBox, QMessageBox,
)

from gui.widgets import Card


class USBDevicePanel(QWidget):
    """USB device passthrough and management."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("USB & Device Management")
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
        tabs.addTab(self._usb_devices_tab(), "USB Devices")
        tabs.addTab(self._pci_devices_tab(), "PCI Passthrough")
        tabs.addTab(self._tpm_tab(), "TPM / Secure Boot")
        layout.addWidget(tabs)

    def _usb_devices_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        self._usb_table = QTableWidget()
        self._usb_table.setColumnCount(6)
        self._usb_table.setHorizontalHeaderLabels(["Vendor", "Product", "Serial", "Bus", "Device", "Assigned"])
        self._usb_table.horizontalHeader().setStretchLastSection(True)
        self._usb_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )

        usb_devices = [
            ["046d", "c52b", "12345678", "001", "003", "No"],
            ["0781", "5567", "ABC123", "002", "001", "No"],
            ["05ac", "12a8", "iPhone", "001", "005", "No"],
        ]
        self._usb_table.setRowCount(len(usb_devices))
        for i, dev in enumerate(usb_devices):
            for j, val in enumerate(dev):
                self._usb_table.setItem(i, j, QTableWidgetItem(val))

        layout.addWidget(self._usb_table)

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        attach_btn = QPushButton("Attach to VM")
        attach_btn.setFixedSize(120, 32)
        attach_btn.setStyleSheet("background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600;")
        bl.addWidget(attach_btn)
        detach_btn = QPushButton("Detach")
        detach_btn.setFixedSize(90, 32)
        detach_btn.setStyleSheet("background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600;")
        bl.addWidget(detach_btn)
        bl.addStretch()
        layout.addWidget(btn_row)
        return page

    def _pci_devices_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        self._pci_table = QTableWidget()
        self._pci_table.setColumnCount(5)
        self._pci_table.setHorizontalHeaderLabels(["Address", "Vendor", "Device", "Class", "Status"])
        self._pci_table.horizontalHeader().setStretchLastSection(True)
        self._pci_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )

        pci_devices = [
            ["00:02.0", "Intel", "HD Graphics 630", "VGA", "Host"],
            ["01:00.0", "NVIDIA", "RTX 3080", "3D Controller", "Available"],
            ["02:00.0", "Intel", "NVMe SSD", "Storage", "Host"],
        ]
        self._pci_table.setRowCount(len(pci_devices))
        for i, dev in enumerate(pci_devices):
            for j, val in enumerate(dev):
                self._pci_table.setItem(i, j, QTableWidgetItem(val))

        layout.addWidget(self._pci_table)

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        passthrough_btn = QPushButton("Passthrough to VM")
        passthrough_btn.setFixedSize(150, 32)
        passthrough_btn.setStyleSheet("background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600;")
        bl.addWidget(passthrough_btn)
        release_btn = QPushButton("Release")
        release_btn.setFixedSize(90, 32)
        release_btn.setStyleSheet("background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600;")
        bl.addWidget(release_btn)
        bl.addStretch()
        layout.addWidget(btn_row)
        return page

    def _tpm_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("TPM & Secure Boot Configuration")
        layout.addWidget(card)

        form_widget = QWidget()
        fl = QVBoxLayout(form_widget)

        self._tpm_enable = QCheckBox("Enable vTPM 2.0 (required for Windows 11)")
        self._tpm_enable.setStyleSheet("color: " + T.TEXT_SECONDARY + "; font-size: 12px;")
        fl.addWidget(self._tpm_enable)

        self._secure_boot = QCheckBox("Enable UEFI Secure Boot")
        self._secure_boot.setStyleSheet("color: " + T.TEXT_SECONDARY + "; font-size: 12px;")
        fl.addWidget(self._secure_boot)

        card.content_layout.addWidget(form_widget)
        layout.addStretch()
        return page
