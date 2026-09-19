"""Advanced QEMU Features Panel — QMP console, monitor, machine config."""

from __future__ import annotations

from gui.theme import T
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QTextEdit, QMessageBox, QTabWidget, QGroupBox,
    QGridLayout, QCheckBox, QSpinBox, QSizePolicy,
)

from gui.widgets import Card


class AdvancedQEmuPanel(QWidget):
    """Advanced QEMU configuration and QMP interaction."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._qmp_bridge = None
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Advanced QEMU Configuration")
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
        tabs.addTab(self._machine_tab(), "Machine")
        tabs.addTab(self._boot_tab(), "Boot")
        tabs.addTab(self._smbios_tab(), "SMBIOS")
        tabs.addTab(self._qmp_log_tab(), "QMP Log")
        layout.addWidget(tabs)

    def set_qmp_bridge(self, bridge):
        self._qmp_bridge = bridge

    def _machine_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Machine Configuration")
        layout.addWidget(card)

        form = QGridLayout()
        form.setSpacing(10)

        form.addWidget(QLabel("Machine Type:"), 0, 0)
        self._machine_type = QComboBox()
        self._machine_type.addItems(["q35", "pc", "virt", "virt-2.0", "isapc"])
        self._machine_type.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addWidget(self._machine_type, 0, 1)

        form.addWidget(QLabel("CPU Model:"), 1, 0)
        self._cpu_model = QComboBox()
        self._cpu_model.addItems(["host", "qemu64", "kvm64", "Broadwell", "Skylake"])
        self._cpu_model.setEditable(True)
        self._cpu_model.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addWidget(self._cpu_model, 1, 1)

        form.addWidget(QLabel("Firmware:"), 2, 0)
        self._firmware = QComboBox()
        self._firmware.addItems(["OVMF (UEFI)", "SeaBIOS (Legacy)", "AAVMF (ARM UEFI)"])
        self._firmware.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addWidget(self._firmware, 2, 1)

        card.content_layout.addLayout(form)
        layout.addStretch()
        return page

    def _boot_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Boot Configuration")
        layout.addWidget(card)

        form = QGridLayout()
        form.setSpacing(10)

        form.addWidget(QLabel("Boot Order:"), 0, 0)
        self._boot_order = QTextEdit()
        self._boot_order.setPlainText("c d n")
        self._boot_order.setMaximumHeight(50)
        self._boot_order.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        form.addWidget(self._boot_order, 0, 1)

        self._pxe_boot = QCheckBox("Enable PXE boot")
        self._pxe_boot.setStyleSheet("color: " + T.TEXT_SECONDARY + "; font-size: 12px;")
        form.addWidget(self._pxe_boot, 1, 0, 1, 2)

        card.content_layout.addLayout(form)
        layout.addStretch()
        return page

    def _smbios_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("SMBIOS System Information")
        layout.addWidget(card)

        form = QGridLayout()
        form.setSpacing(10)

        fields = [
            ("Manufacturer", "QEMU"),
            ("Product", "Standard PC"),
            ("Version", "pc-q35-7.2"),
            ("Serial", "1234567890"),
            ("UUID", "a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        ]
        self._smbios = {}
        for i, (label, default) in enumerate(fields):
            form.addWidget(QLabel(label + ":"), i, 0)
            edit = QLineEdit(default)
            edit.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
            form.addWidget(edit, i, 1)
            self._smbios[label] = edit

        card.content_layout.addLayout(form)
        layout.addStretch()
        return page

    def _qmp_log_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("QMP Communication Log")
        layout.addWidget(card)

        self._qmp_log = QTextEdit()
        self._qmp_log.setReadOnly(True)
        self._qmp_log.setStyleSheet("QTextEdit { background: #0d1117; color: #c9d1d9; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; padding: 8px; font-family: Consolas, monospace; font-size: 11px; }")
        card.content_layout.addWidget(self._qmp_log)

        # Send command row
        cmd_row = QWidget()
        cl = QHBoxLayout(cmd_row)
        cl.setContentsMargins(0, 0, 0, 0)
        self._qmp_cmd = QLineEdit()
        self._qmp_cmd.setPlaceholderText("Enter QMP command (e.g., query-status)")
        self._qmp_cmd.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + "; border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 6px;")
        cl.addWidget(self._qmp_cmd)
        send_btn = QPushButton("Send")
        send_btn.setFixedSize(70, 28)
        send_btn.setStyleSheet("background: " + T.BRAND + "; border: none; border-radius: 4px; color: white; font-weight: 600;")
        cl.addWidget(send_btn)
        card.content_layout.addWidget(cmd_row)

        return page
