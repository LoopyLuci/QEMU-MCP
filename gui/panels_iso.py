"""ISO Manager Panel — browse, import, and manage ISO files."""

from __future__ import annotations

from pathlib import Path

from gui.theme import T
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTextEdit, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QGroupBox, QGridLayout, QLineEdit, QCheckBox, QSpinBox,
    QSizePolicy, QProgressBar, QListWidget, QListWidgetItem, QFileDialog,
    QInputDialog, QAbstractItemView, QFrame, QSplitter, QToolBar,
    QAction, QMenu, QStatusBar, QSizePolicy as QSP, QDialog, QFormLayout,
    QDialogButtonBox,
)

from gui.widgets import Card
from gui.iso_manager import ISOManager, COMMON_ISOS


class ISOManagerPanel(QWidget):
    """ISO file management panel."""

    iso_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = ISOManager()
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("ISO Manager")
        title.setStyleSheet("color: " + T.TEXT_PRIMARY + "; font-size: 16px; font-weight: bold;")
        hl.addWidget(title)
        hl.addStretch()
        self._count_label = QLabel("0 ISOs found")
        self._count_label.setStyleSheet("color: " + T.TEXT_MUTED + "; font-size: 12px;")
        hl.addWidget(self._count_label)
        layout.addWidget(header)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; }"
            "QTabBar::tab { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 8px 16px; margin-right: 2px; border-radius: 4px 4px 0 0; }"
            "QTabBar::tab:selected { background: " + T.BRAND + "; color: white; }"
        )
        tabs.addTab(self._available_tab(), "Available ISOs")
        tabs.addTab(self._external_tab(), "External ISOs")
        tabs.addTab(self._sources_tab(), "Sources")
        tabs.addTab(self._common_tab(), "Common ISOs")
        layout.addWidget(tabs)

    def _available_tab(self) -> QWidget:
        """Tab showing all available ISOs."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # ISO table
        self._iso_table = QTableWidget()
        self._iso_table.setColumnCount(5)
        self._iso_table.setHorizontalHeaderLabels(["Name", "Size", "Source", "Path", "Actions"])
        self._iso_table.horizontalHeader().setStretchLastSection(True)
        self._iso_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._iso_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
            "QTableWidget::item { padding: 4px; }"
        )
        layout.addWidget(self._iso_table)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedSize(90, 32)
        refresh_btn.setStyleSheet(
            "QPushButton { background: " + T.BRAND + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: " + T.BRAND_HOVER + "; }"
        )
        refresh_btn.clicked.connect(self.refresh)
        bl.addWidget(refresh_btn)

        import_btn = QPushButton("Import ISO")
        import_btn.setFixedSize(100, 32)
        import_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        import_btn.clicked.connect(self._import_iso)
        bl.addWidget(import_btn)

        select_btn = QPushButton("Select for VM")
        select_btn.setFixedSize(110, 32)
        select_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_PAUSED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #d97706; }"
        )
        select_btn.clicked.connect(self._select_iso)
        bl.addWidget(select_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setFixedSize(90, 32)
        delete_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #dc2626; }"
        )
        delete_btn.clicked.connect(self._delete_iso)
        bl.addWidget(delete_btn)

        bl.addStretch()
        layout.addWidget(btn_row)
        return page

    def _external_tab(self) -> QWidget:
        """Tab showing external ISOs in a dedicated table."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # External ISO table
        self._external_table = QTableWidget()
        self._external_table.setColumnCount(5)
        self._external_table.setHorizontalHeaderLabels(["Filename", "Size", "Path", "Source", "Last Modified"])
        self._external_table.horizontalHeader().setStretchLastSection(True)
        self._external_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._external_table.setAlternatingRowColors(True)
        self._external_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
            "QTableWidget::item { padding: 4px; }"
        )
        layout.addWidget(self._external_table)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedSize(90, 32)
        refresh_btn.setStyleSheet(
            "QPushButton { background: " + T.BRAND + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: " + T.BRAND_HOVER + "; }"
        )
        refresh_btn.clicked.connect(self._refresh_external)
        bl.addWidget(refresh_btn)

        browse_btn = QPushButton("Browse External Folder")
        browse_btn.setFixedSize(160, 32)
        browse_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        browse_btn.clicked.connect(self._add_source)
        bl.addWidget(browse_btn)

        remove_src_btn = QPushButton("Remove Source")
        remove_src_btn.setFixedSize(120, 32)
        remove_src_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #dc2626; }"
        )
        remove_src_btn.clicked.connect(self._remove_source)
        bl.addWidget(remove_src_btn)

        select_btn = QPushButton("Select for VM")
        select_btn.setFixedSize(110, 32)
        select_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_PAUSED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #d97706; }"
        )
        select_btn.clicked.connect(self._select_external_iso)
        bl.addWidget(select_btn)

        bl.addStretch()
        layout.addWidget(btn_row)
        return page

    def _refresh_external(self):
        """Refresh the external ISOs table."""
        isos = self._manager.scan_external_isos()
        self._external_table.setRowCount(len(isos))
        for i, iso in enumerate(isos):
            self._external_table.setItem(i, 0, QTableWidgetItem(iso["name"]))
            self._external_table.setItem(i, 1, QTableWidgetItem(iso["size_human"]))
            path_item = QTableWidgetItem(iso["path"])
            path_item.setToolTip(iso["path"])
            self._external_table.setItem(i, 2, path_item)
            source_item = QTableWidgetItem(str(iso.get("source", "external")))
            source_item.setForeground(Qt.yellow)
            self._external_table.setItem(i, 3, source_item)
            modified_str = ISOManager.format_timestamp(iso["modified"])
            self._external_table.setItem(i, 4, QTableWidgetItem(modified_str))

    def _select_external_iso(self):
        """Select an external ISO for VM creation."""
        row = self._external_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Select an ISO first")
            return
        path = self._external_table.item(row, 2).text()
        self.iso_selected.emit(path)
        QMessageBox.information(self, "Selected", "ISO selected:\n" + path)

    def _sources_tab(self) -> QWidget:
        """Tab for managing ISO sources."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("ISO Source Folders")
        layout.addWidget(card)

        self._sources_list = QListWidget()
        self._sources_list.setStyleSheet(
            "QListWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; padding: 4px; }"
            "QListWidget::item { padding: 6px 8px; border-bottom: 1px solid " + T.BG_TERTIARY + "; }"
        )
        card.content_layout.addWidget(self._sources_list)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)

        add_btn = QPushButton("Add Folder")
        add_btn.setFixedSize(100, 32)
        add_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
        )
        add_btn.clicked.connect(self._add_source)
        bl.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setFixedSize(90, 32)
        remove_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
        )
        remove_btn.clicked.connect(self._remove_source)
        bl.addWidget(remove_btn)

        bl.addStretch()
        layout.addWidget(btn_row)
        layout.addStretch()
        return page

    def _common_tab(self) -> QWidget:
        """Tab showing common downloadable ISOs."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        card = Card("Common ISO Downloads")
        layout.addWidget(card)

        self._common_table = QTableWidget()
        self._common_table.setColumnCount(4)
        self._common_table.setHorizontalHeaderLabels(["Name", "Size", "URL", "Action"])
        self._common_table.horizontalHeader().setStretchLastSection(True)
        self._common_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )

        # Populate common ISOs
        self._common_table.setRowCount(len(COMMON_ISOS))
        for i, (key, info) in enumerate(COMMON_ISOS.items()):
            self._common_table.setItem(i, 0, QTableWidgetItem(info["name"]))
            self._common_table.setItem(i, 1, QTableWidgetItem("~" + str(info["size_gb"]) + " GB"))
            url_item = QTableWidgetItem(info["url"])
            url_item.setToolTip(info["url"])
            self._common_table.setItem(i, 2, url_item)
            self._common_table.setItem(i, 3, QTableWidgetItem("Open URL"))

        card.content_layout.addWidget(self._common_table)
        layout.addStretch()
        return page

    def refresh(self) -> None:
        """Refresh ISO list."""
        isos = self._manager.scan_isos()
        self._iso_table.setRowCount(len(isos))
        for i, iso in enumerate(isos):
            self._iso_table.setItem(i, 0, QTableWidgetItem(iso["name"]))
            self._iso_table.setItem(i, 1, QTableWidgetItem(iso["size_human"]))
            source_item = QTableWidgetItem(iso["source"])
            if iso["source"] == "internal":
                source_item.setForeground(Qt.green)
            else:
                source_item.setForeground(Qt.yellow)
            self._iso_table.setItem(i, 2, source_item)
            self._iso_table.setItem(i, 3, QTableWidgetItem(iso["path"]))
        self._count_label.setText(str(len(isos)) + " ISOs found")

        # Refresh sources list
        self._sources_list.clear()
        for source in self._manager.get_external_sources():
            item = QListWidgetItem(str(source))
            item.setToolTip(str(source))
            self._sources_list.addItem(item)

        # Refresh external ISOs table
        self._refresh_external()

    def _import_iso(self):
        """Import an ISO into internal folder."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import ISO", "",
            "ISO Images (*.iso);;All Files (*)"
        )
        if path:
            dest = self._manager.copy_to_internal(path)
            if dest:
                QMessageBox.information(self, "Success", "ISO imported to:\n" + str(dest))
                self.refresh()
            else:
                QMessageBox.critical(self, "Error", "Failed to import ISO")

    def _select_iso(self):
        """Select an ISO for VM creation."""
        row = self._iso_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Select an ISO first")
            return
        path = self._iso_table.item(row, 3).text()
        self.iso_selected.emit(path)
        QMessageBox.information(self, "Selected", "ISO selected:\n" + path)

    def _delete_iso(self):
        """Delete selected ISO (internal only)."""
        row = self._iso_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Select an ISO first")
            return
        path = self._iso_table.item(row, 3).text()
        source = self._iso_table.item(row, 2).text()
        if source != "internal":
            QMessageBox.warning(self, "Warning", "Can only delete internal ISOs")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Delete ISO '" + path + "'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self._manager.delete_iso(path):
                self.refresh()
            else:
                QMessageBox.critical(self, "Error", "Failed to delete ISO")

    def _add_source(self):
        """Add an external ISO source folder."""
        path = QFileDialog.getExistingDirectory(self, "Select ISO Source Folder")
        if path:
            if self._manager.add_external_source(path):
                self.refresh()
                QMessageBox.information(self, "Success", "Added source:\n" + path)
            else:
                QMessageBox.critical(self, "Error", "Failed to add source")

    def _remove_source(self):
        """Remove selected external source."""
        item = self._sources_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a source first")
            return
        path = item.text()
        if self._manager.remove_external_source(path):
            self.refresh()
