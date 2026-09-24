"""Storage Management Panel — disk operations, cache, attach/detach."""

from __future__ import annotations

import subprocess
from pathlib import Path

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QProgressBar, QTextEdit, QMessageBox, QInputDialog,
    QListWidget, QListWidgetItem, QGroupBox, QGridLayout, QCheckBox,
    QFrame, QSplitter, QFileDialog, QMenu, QAction, QToolBar, QStatusBar,
    QSizePolicy,
)

from gui.widgets import Card


class StoragePanel(QWidget):
    """Disk and storage management UI."""

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
        title = QLabel("Storage Management")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        layout.addWidget(header)

        # Disk list
        self._disk_list = QListWidget()
        self._disk_list.setStyleSheet(
            "QListWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; padding: 4px; }"
            "QListWidget::item { padding: 6px 8px; border-bottom: 1px solid " + T.BG_TERTIARY + "; }"
            "QListWidget::item:selected { background: " + T.BRAND + "; color: white; }"
        )
        layout.addWidget(self._disk_list)

        # Action buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)

        create_btn = QPushButton("Create Disk")
        create_btn.setFixedSize(110, 32)
        create_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        create_btn.clicked.connect(self._create_disk)
        bl.addWidget(create_btn)

        resize_btn = QPushButton("Resize")
        resize_btn.setFixedSize(90, 32)
        resize_btn.setStyleSheet(
            "QPushButton { background: " + T.BRAND + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: " + T.BRAND_HOVER + "; }"
        )
        resize_btn.clicked.connect(self._resize_disk)
        bl.addWidget(resize_btn)

        convert_btn = QPushButton("Convert")
        convert_btn.setFixedSize(90, 32)
        convert_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_PAUSED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #d97706; }"
        )
        convert_btn.clicked.connect(self._convert_disk)
        bl.addWidget(convert_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setFixedSize(90, 32)
        delete_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #dc2626; }"
        )
        delete_btn.clicked.connect(self._delete_disk)
        bl.addWidget(delete_btn)

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

        self.refresh()

    def refresh(self) -> None:
        """Refresh disk list."""
        self._disk_list.clear()
        vm_dir = Path.home() / "Virtual Machines"
        if not vm_dir.exists():
            return

        for vm_path in vm_dir.iterdir():
            if vm_path.is_dir():
                disk = vm_path / "disk.qcow2"
                if disk.exists():
                    size = disk.stat().st_size
                    size_gb = size / (1024**3)
                    item = QListWidgetItem(f"{vm_path.name}: {size_gb:.1f} GB")
                    item.setData(Qt.UserRole, str(disk))
                    self._disk_list.addItem(item)

    def _create_disk(self):
        """Create a new virtual disk."""
        name, ok = QInputDialog.getText(self, "Create Disk", "Disk name (without extension):")
        if not ok or not name.strip():
            return

        size, ok = QInputDialog.getInt(self, "Create Disk", "Size (GB):", 40, 1, 2048, 1)
        if not ok:
            return

        fmt, ok = QInputDialog.getItem(self, "Create Disk", "Format:",
            ["qcow2", "raw", "vmdk", "vhd"], 0, False)
        if not ok:
            return

        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Disk", f"{name}.{fmt}",
                f"Disk Images (*.{fmt});;All Files (*)"
            )
            if path:
                subprocess.run(
                    ["qemu-img", "create", "-f", fmt, path, f"{size}G"],
                    check=True, capture_output=True, text=True, timeout=60
                )
                self.refresh()
                QMessageBox.information(self, "Success", f"Disk created: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create disk: {e}")

    def _resize_disk(self):
        """Resize selected disk."""
        item = self._disk_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a disk first")
            return

        disk_path = item.data(Qt.UserRole)
        new_size, ok = QInputDialog.getInt(
            self, "Resize Disk", "New size (GB):", 40, 1, 2048, 1
        )
        if ok:
            try:
                subprocess.run(
                    ["qemu-img", "resize", disk_path, f"{new_size}G"],
                    check=True, capture_output=True, text=True, timeout=60
                )
                self.refresh()
                QMessageBox.information(self, "Success", f"Resized to {new_size} GB")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to resize: {e}")

    def _convert_disk(self):
        """Convert disk format."""
        item = self._disk_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a disk first")
            return

        disk_path = item.data(Qt.UserRole)
        target_fmt, ok = QInputDialog.getItem(self, "Convert Disk", "Target format:",
            ["qcow2", "raw", "vmdk", "vhd"], 0, False)
        if not ok:
            return

        try:
            new_path = str(Path(disk_path).with_suffix(f".{target_fmt}"))
            subprocess.run(
                ["qemu-img", "convert", "-f", "qcow2", "-O", target_fmt, disk_path, new_path],
                check=True, capture_output=True, text=True, timeout=300
            )
            self.refresh()
            QMessageBox.information(self, "Success", f"Converted to: {new_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Conversion failed: {e}")

    def _delete_disk(self):
        """Delete selected disk."""
        item = self._disk_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a disk first")
            return

        disk_path = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete disk '{disk_path}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                Path(disk_path).unlink()
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
