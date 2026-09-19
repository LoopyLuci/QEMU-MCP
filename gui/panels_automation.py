"""Automation & Scripting Panel — macros, schedules, hooks, API."""

from __future__ import annotations

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTextEdit, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QGroupBox, QGridLayout, QLineEdit, QCheckBox, QSpinBox,
    QSizePolicy, QFileDialog, QInputDialog,
)

from gui.widgets import Card


class AutomationPanel(QWidget):
    """Automation, scripting, and scheduling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Automation & Scripting")
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
        tabs.addTab(self._macros_tab(), "Macros")
        tabs.addTab(self._schedules_tab(), "Schedules")
        tabs.addTab(self._hooks_tab(), "Hooks")
        layout.addWidget(tabs)

    def _macros_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        self._macro_table = QTableWidget()
        self._macro_table.setColumnCount(4)
        self._macro_table.setHorizontalHeaderLabels(["Name", "Commands", "Last Run", "Status"])
        self._macro_table.horizontalHeader().setStretchLastSection(True)
        self._macro_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )

        macros = [
            ["Daily Backup", "snapshot create daily", "Never", "Ready"],
            ["Cleanup", "snapshot delete old", "Never", "Ready"],
        ]
        self._macro_table.setRowCount(len(macros))
        for i, m in enumerate(macros):
            for j, val in enumerate(m):
                self._macro_table.setItem(i, j, QTableWidgetItem(val))

        layout.addWidget(self._macro_table)

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        add_btn = QPushButton("Add Macro")
        add_btn.setFixedSize(100, 32)
        add_btn.setStyleSheet("background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600;")
        bl.addWidget(add_btn)
        run_btn = QPushButton("Run")
        run_btn.setFixedSize(80, 32)
        run_btn.setStyleSheet("background: " + T.BRAND + "; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: 600;")
        bl.addWidget(run_btn)
        bl.addStretch()
        layout.addWidget(btn_row)
        return page

    def _schedules_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        self._sched_table = QTableWidget()
        self._sched_table.setColumnCount(5)
        self._sched_table.setHorizontalHeaderLabels(["Name", "Schedule", "Action", "Enabled", "Next Run"])
        self._sched_table.horizontalHeader().setStretchLastSection(True)
        self._sched_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )
        layout.addWidget(self._sched_table)
        return page

    def _hooks_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        self._hook_table = QTableWidget()
        self._hook_table.setColumnCount(4)
        self._hook_table.setHorizontalHeaderLabels(["Event", "Script", "Enabled", "Last Triggered"])
        self._hook_table.horizontalHeader().setStretchLastSection(True)
        self._hook_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )

        hooks = [
            ["VM Start", "/scripts/vm-start.sh", "Yes", "Never"],
            ["VM Stop", "/scripts/vm-stop.sh", "Yes", "Never"],
        ]
        self._hook_table.setRowCount(len(hooks))
        for i, h in enumerate(hooks):
            for j, val in enumerate(h):
                self._hook_table.setItem(i, j, QTableWidgetItem(val))

        layout.addWidget(self._hook_table)
        return page
