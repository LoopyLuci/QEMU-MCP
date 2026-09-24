"""Snapshot management panel — list, create, restore, delete VM snapshots."""

from __future__ import annotations

import subprocess

from gui.theme import T
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QInputDialog,
    QMessageBox, QLabel, QListWidget, QListWidgetItem,
)


class SnapshotPanel(QWidget):
    """VM snapshot management UI."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._disk_path = r"C:\Users\Server\Virtual Machines\omarchy-vm\disk.qcow2"
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("VM Snapshots")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        self._count_label = QLabel("0 snapshots")
        self._count_label.setStyleSheet("color: " + T.TEXT_MUTED + "; font-size: 12px;")
        hl.addWidget(self._count_label)
        layout.addWidget(header)

        # Snapshot list
        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; padding: 4px; }"
            "QListWidget::item { padding: 6px 8px; border-bottom: 1px solid " + T.BG_TERTIARY + "; }"
            "QListWidget::item:selected { background: " + T.BRAND + "; color: white; }"
        )
        layout.addWidget(self._list)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)

        create_btn = QPushButton("Create")
        create_btn.setFixedSize(90, 32)
        create_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        create_btn.clicked.connect(self._create_snapshot)
        bl.addWidget(create_btn)

        restore_btn = QPushButton("Restore")
        restore_btn.setFixedSize(90, 32)
        restore_btn.setStyleSheet(
            "QPushButton { background: " + T.BRAND + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: " + T.BRAND_HOVER + "; }"
        )
        restore_btn.clicked.connect(self._restore_snapshot)
        bl.addWidget(restore_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setFixedSize(90, 32)
        delete_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #dc2626; }"
        )
        delete_btn.clicked.connect(self._delete_snapshot)
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

    def refresh(self) -> None:
        """Load snapshot list from qcow2 image."""
        self._list.clear()
        try:
            result = subprocess.run(
                ["qemu-img", "snapshot", "-l", self._disk_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                count = 0
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2 and parts[0].isdigit():
                        snap_id = parts[0]
                        name = parts[1]
                        size_info = " ".join(parts[2:]) if len(parts) > 2 else ""
                        item = QListWidgetItem(f"{snap_id}: {name} {size_info}")
                        item.setData(Qt.UserRole, name)
                        self._list.addItem(item)
                        count += 1
                self._count_label.setText(f"{count} snapshot{'s' if count != 1 else ''}")
            else:
                self._count_label.setText("No snapshots")
        except Exception as e:
            self._count_label.setText(f"Error: {e}")

    def _create_snapshot(self):
        """Create a new snapshot."""
        name, ok = QInputDialog.getText(self, "Create Snapshot", "Snapshot name:")
        if ok and name.strip():
            try:
                subprocess.run(
                    ["qemu-img", "snapshot", "-c", name.strip(), self._disk_path],
                    check=True, capture_output=True, text=True, timeout=30
                )
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create snapshot: {e}")

    def _restore_snapshot(self):
        """Restore selected snapshot."""
        item = self._list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a snapshot first")
            return
        name = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Confirm Restore",
            f"Restore snapshot '{name}'? Current state will be lost.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                subprocess.run(
                    ["qemu-img", "snapshot", "-a", name, self._disk_path],
                    check=True, capture_output=True, text=True, timeout=30
                )
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to restore snapshot: {e}")

    def _delete_snapshot(self):
        """Delete selected snapshot."""
        item = self._list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a snapshot first")
            return
        name = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete snapshot '{name}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                subprocess.run(
                    ["qemu-img", "snapshot", "-d", name, self._disk_path],
                    check=True, capture_output=True, text=True, timeout=30
                )
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete snapshot: {e}")
