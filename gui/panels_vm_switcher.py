"""VM Switcher Panel — manage multiple VMs, switch active VM."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTextEdit, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QGroupBox, QGridLayout, QLineEdit, QCheckBox, QSpinBox,
    QSizePolicy, QProgressBar, QListWidget, QListWidgetItem,
)

from gui.widgets import Card
from gui.multi_vm import MultiVMManager, VMConfig


class VMSwitcherPanel(QWidget):
    """Switch between multiple VMs."""

    vm_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = MultiVMManager()
        self._active_vm = None
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Virtual Machine Switcher")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        layout.addWidget(header)

        # Active VM indicator
        active_row = QWidget()
        al = QHBoxLayout(active_row)
        al.setContentsMargins(0, 0, 0, 0)
        al.addWidget(QLabel("Active VM:"))
        self._active_label = QLabel("None")
        self._active_label.setStyleSheet("color: " + T.BRAND + "; font-weight: bold; font-size: 14px;")
        al.addWidget(self._active_label)
        al.addStretch()
        layout.addWidget(active_row)

        # VM List
        list_card = Card("Available Virtual Machines")
        layout.addWidget(list_card)

        self._vm_list = QListWidget()
        self._vm_list.setStyleSheet(
            "QListWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; padding: 4px; }"
            "QListWidget::item { padding: 6px 8px; border-bottom: 1px solid " + T.BG_TERTIARY + "; }"
            "QListWidget::item:selected { background: " + T.BRAND + "; color: white; }"
        )
        list_card.content_layout.addWidget(self._vm_list)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)

        add_btn = QPushButton("Add VM")
        add_btn.setFixedSize(90, 32)
        add_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        add_btn.clicked.connect(self._add_vm)
        bl.addWidget(add_btn)

        switch_btn = QPushButton("Switch To")
        switch_btn.setFixedSize(100, 32)
        switch_btn.setStyleSheet(
            "QPushButton { background: " + T.BRAND + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: " + T.BRAND_HOVER + "; }"
        )
        switch_btn.clicked.connect(self._switch_vm)
        bl.addWidget(switch_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setFixedSize(90, 32)
        remove_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #dc2626; }"
        )
        remove_btn.clicked.connect(self._remove_vm)
        bl.addWidget(remove_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedSize(90, 32)
        refresh_btn.setStyleSheet(
            "QPushButton { background: " + T.BG_SECONDARY + "; border: 1px solid " + T.BG_TERTIARY + ";"
            " border-radius: 6px; color: " + T.TEXT_SECONDARY + "; font-size: 12px; }"
            "QPushButton:hover { background: " + T.BG_TERTIARY + "; }"
        )
        refresh_btn.clicked.connect(self.refresh)
        bl.addWidget(refresh_btn)

        bl.addStretch()
        layout.addWidget(btn_row)

        # Status bar
        self._status = QLabel("No VM selected")
        self._status.setStyleSheet("color: " + T.TEXT_MUTED + "; font-size: 11px;")
        layout.addWidget(self._status)

        # Auto-refresh timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5000)

        self.refresh()

    def refresh(self):
        """Refresh the VM list."""
        self._vm_list.clear()
        for vm_name in self._manager.list_vms():
            item = QListWidgetItem(vm_name)
            if self._manager.is_running(vm_name):
                item.setText(f"● {vm_name} (Running)")
                item.setForeground(Qt.green)
            else:
                item.setText(f"○ {vm_name} (Stopped)")
                item.setForeground(Qt.gray)
            self._vm_list.addItem(item)

    def _add_vm(self):
        """Add a new VM."""
        name, ok = QInputDialog.getText(self, "Add VM", "VM name:")
        if not ok or not name.strip():
            return

        disk_path, _ = QFileDialog.getOpenFileName(
            self, "Select Disk Image", "",
            "Disk Images (*.qcow2 *.img *.vmdk *.raw);;All Files (*)"
        )
        if not disk_path:
            return

        config = {
            "name": name,
            "disk_path": disk_path,
            "cpus": 2,
            "ram_mb": 4096,
            "display": "sdl",
            "qmp_port": 4444,
            "qemu_binary": r"C:\Program Files\qemu\qemu-system-x86_64.exe",
        }

        self._manager.add_vm(name, config)
        self.refresh()
        self._status.setText(f"VM '{name}' added")

    def _switch_vm(self):
        """Switch to selected VM."""
        item = self._vm_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a VM first")
            return

        vm_name = item.text().replace("● ", "").replace("○ ", "").replace(" (Running)", "").replace(" (Stopped)", "")
        self._active_vm = vm_name
        self._active_label.setText(vm_name)
        self.vm_changed.emit(vm_name)
        self._status.setText(f"Active VM: {vm_name}")

    def _remove_vm(self):
        """Remove selected VM."""
        item = self._vm_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a VM first")
            return

        vm_name = item.text().replace("● ", "").replace("○ ", "").replace(" (Running)", "").replace(" (Stopped)", "")
        reply = QMessageBox.question(
            self, "Confirm Remove",
            f"Remove VM '{vm_name}'? Configuration will be deleted.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._manager.remove_vm(vm_name)
            if self._active_vm == vm_name:
                self._active_vm = None
                self._active_label.setText("None")
            self.refresh()
