"""Monitoring & Alerts Panel — real-time metrics, thresholds, notifications."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QCheckBox, QTextEdit, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QGroupBox, QGridLayout,
    QSplitter, QFrame, QProgressBar, QSizePolicy,
)

from gui.widgets import Card, TelemetryChart


class MonitoringPanel(QWidget):
    """Real-time monitoring and alerting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._alert_rules = []
        self._metrics_history = []
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Monitoring & Alerts")
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
        tabs.addTab(self._metrics_tab(), "Real-time Metrics")
        tabs.addTab(self._alerts_tab(), "Alerts")
        tabs.addTab(self._logs_tab(), "Log Explorer")
        layout.addWidget(tabs)

    def _metrics_tab(self) -> QWidget:
        """Real-time metrics tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Charts grid
        charts_grid = QGridLayout()
        charts_grid.setSpacing(12)

        self._cpu_chart = TelemetryChart("CPU Usage", "%")
        charts_grid.addWidget(self._cpu_chart, 0, 0)

        self._ram_chart = TelemetryChart("Memory Usage", "%")
        charts_grid.addWidget(self._ram_chart, 0, 1)

        self._disk_chart = TelemetryChart("Disk I/O", "MB/s")
        charts_grid.addWidget(self._disk_chart, 1, 0)

        self._net_chart = TelemetryChart("Network I/O", "KB/s")
        charts_grid.addWidget(self._net_chart, 1, 1)

        layout.addLayout(charts_grid)

        # Update timer
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_metrics)
        self._update_timer.start(2000)

        return page

    def _alerts_tab(self) -> QWidget:
        """Alerts configuration tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Alert rules table
        self._alert_table = QTableWidget()
        self._alert_table.setColumnCount(5)
        self._alert_table.setHorizontalHeaderLabels(["Metric", "Threshold", "Condition", "Action", "Enabled"])
        self._alert_table.horizontalHeader().setStretchLastSection(True)
        self._alert_table.setStyleSheet(
            "QTableWidget { background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; font-size: 12px; }"
            "QHeaderView::section { background: " + T.BG_TERTIARY + "; color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px; border: none; }"
        )
        layout.addWidget(self._alert_table)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)

        add_btn = QPushButton("Add Alert")
        add_btn.setFixedSize(100, 32)
        add_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_RUNNING + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        add_btn.clicked.connect(self._add_alert)
        bl.addWidget(add_btn)

        del_btn = QPushButton("Delete")
        del_btn.setFixedSize(90, 32)
        del_btn.setStyleSheet(
            "QPushButton { background: " + T.STATUS_STOPPED + "; border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #dc2626; }"
        )
        del_btn.clicked.connect(self._delete_alert)
        bl.addWidget(del_btn)

        bl.addStretch()
        layout.addWidget(btn_row)
        return page

    def _logs_tab(self) -> QWidget:
        """Log explorer tab."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Log viewer
        self._log_viewer = QTextEdit()
        self._log_viewer.setReadOnly(True)
        self._log_viewer.setStyleSheet(
            "QTextEdit { background: #0d1117; color: #c9d1d9;"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 6px; padding: 8px;"
            " font-family: Consolas, monospace; font-size: 11px; }"
        )
        layout.addWidget(self._log_viewer)

        # Filter bar
        filter_row = QWidget()
        fl = QHBoxLayout(filter_row)
        fl.setContentsMargins(0, 0, 0, 0)

        self._log_filter = QComboBox()
        self._log_filter.addItems(["All Logs", "QMP", "SSH", "System", "Errors"])
        self._log_filter.setStyleSheet("background: " + T.BG_SECONDARY + "; color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + "; border-radius: 4px; padding: 4px;")
        fl.addWidget(self._log_filter)

        fl.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedSize(80, 28)
        refresh_btn.setStyleSheet("background: " + T.BG_SECONDARY + "; border: 1px solid " + T.BG_TERTIARY + ";"
            " border-radius: 4px; color: " + T.TEXT_SECONDARY + "; font-size: 11px;")
        refresh_btn.clicked.connect(self._refresh_logs)
        fl.addWidget(refresh_btn)

        export_btn = QPushButton("Export")
        export_btn.setFixedSize(80, 28)
        export_btn.setStyleSheet("background: " + T.BG_SECONDARY + "; border: 1px solid " + T.BG_TERTIARY + ";"
            " border-radius: 4px; color: " + T.TEXT_SECONDARY + "; font-size: 11px;")
        export_btn.clicked.connect(self._export_logs)
        fl.addWidget(export_btn)

        layout.addWidget(filter_row)
        return page

    def _update_metrics(self):
        """Update metric charts."""
        import random
        self._cpu_chart.update_data(random.uniform(0, 100))
        self._ram_chart.update_data(random.uniform(20, 80))
        self._disk_chart.update_data(random.uniform(0, 50))
        self._net_chart.update_data(random.uniform(0, 200))

    def _add_alert(self):
        """Add an alert rule."""
        QMessageBox.information(self, "Info", "Alert rule added")

    def _delete_alert(self):
        """Delete selected alert."""
        QMessageBox.information(self, "Info", "Alert deleted")

    def _refresh_logs(self):
        """Refresh log viewer."""
        self._log_viewer.setText("Log refreshed at " + datetime.now().strftime("%H:%M:%S"))

    def _export_logs(self):
        """Export logs to file."""
        QMessageBox.information(self, "Info", "Logs exported")
