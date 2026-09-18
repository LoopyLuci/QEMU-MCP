"""Telemetry Panel — real-time CPU, RAM, disk, and network charts.

Uses matplotlib for live charting of VM and host resource usage.
Updated every 2 seconds via QTimer.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QGridLayout,
    QSizePolicy,
)

from gui.widgets import Card, TelemetryChart


class TelemetryPanel(QWidget):
    """Real-time resource usage charts for VM and host."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #0f172a;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── VM Telemetry Section ──────────────────────────────────────────────
        vm_card = Card("VM Resource Usage")
        layout.addWidget(vm_card)

        vm_grid = QGridLayout()
        vm_grid.setContentsMargins(0, 0, 0, 0)
        vm_grid.setSpacing(10)
        vm_grid.setColumnStretch(0, 1)
        vm_grid.setColumnStretch(1, 0)

        self.cpu_chart = TelemetryChart("VM CPU Usage (%)", "percent", self)
        vm_grid.addWidget(self.cpu_chart, 0, 0)

        self.ram_chart = TelemetryChart("VM RAM Usage (%)", "percent", self)
        vm_grid.addWidget(self.ram_chart, 1, 0)

        self.disk_chart = TelemetryChart("VM Disk I/O (MB/s)", "MB/s", self)
        vm_grid.addWidget(self.disk_chart, 2, 0)

        self.net_chart = TelemetryChart("VM Network (KB/s)", "KB/s", self)
        vm_grid.addWidget(self.net_chart, 3, 0)

        vm_card.content_layout.addLayout(vm_grid)
        vm_card.content_layout.addStretch()

        # ── Host Telemetry Section ─────────────────────────────────────────────
        host_card = Card("Host System Resource Usage")
        layout.addWidget(host_card)

        host_grid = QGridLayout()
        host_grid.setContentsMargins(0, 0, 0, 0)
        host_grid.setSpacing(10)
        host_grid.setColumnStretch(0, 1)

        self.host_cpu = TelemetryChart("Host CPU (%)", "percent", self)
        host_grid.addWidget(self.host_cpu, 0, 0)

        self.host_ram = TelemetryChart("Host RAM (%)", "percent", self)
        host_grid.addWidget(self.host_ram, 1, 0)

        self.host_disk = TelemetryChart("Host Disk Usage (%)", "percent", self)
        host_grid.addWidget(self.host_disk, 2, 0)

        host_card.content_layout.addLayout(host_grid)
        host_card.content_layout.addStretch()

        # ── Summary Statistics ──────────────────────────────────────────────────
        stats_card = Card("Current Snapshot")
        layout.addWidget(stats_card)

        stats_row = QWidget()
        stats_row_layout = QHBoxLayout(stats_row)
        stats_row_layout.setContentsMargins(0, 0, 0, 0)
        stats_row_layout.setSpacing(16)

        for label, value, color in [
            ("VM CPU", "0.0%", "#38bdf8"),
            ("VM RAM", "0.0%", "#38bdf8"),
            ("Host CPU", "0.0%", "#f59e0b"),
            ("Host RAM", "0.0%", "#f59e0b"),
            ("VM Disk Read", "0.0 MB/s", "#22c55e"),
            ("VM Net In", "0.0 KB/s", "#a78bfa"),
        ]:
            stat = QWidget()
            sl = QHBoxLayout(stat)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(4)
            sl_label = QLabel(label)
            sl_label.setStyleSheet("color: #64748b; font-size: 11px;")
            sl_value = QLabel(value)
            sl_value.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600;")
            sl.addWidget(sl_label)
            sl.addWidget(sl_value)
            stats_row_layout.addWidget(stat)

        stats_row_layout.addStretch()
        stats_card.content_layout.addWidget(stats_row)
        stats_card.content_layout.addStretch()

        # ── Controls ───────────────────────────────────────────────────────────
        ctrl_card = Card("Chart Controls")
        layout.addWidget(ctrl_card)

        ctrl_row = QWidget()
        ctrl_row_layout = QHBoxLayout(ctrl_row)
        ctrl_row_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_row_layout.setSpacing(8)

        self.auto_scale_cb = QCheckBox("Auto-scale Y-axis")
        self.auto_scale_cb.setStyleSheet("color: #e2e8f0; font-size: 12px;")
        self.auto_scale_cb.setChecked(True)
        ctrl_row_layout.addWidget(self.auto_scale_cb)

        ctrl_row_layout.addStretch()

        clear_btn = QPushButton("Clear All Charts")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #334155;
                color: #e2e8f0;
                border: 1px solid #475569;
                border-radius: 4px;
                font-size: 11px;
                padding: 4px 12px;
            }
            QPushButton:hover { background: #475569; }
        """)
        ctrl_row_layout.addWidget(clear_btn)
        clear_btn.clicked.connect(self._clear_all)

        ctrl_card.content_layout.addWidget(ctrl_row)
        ctrl_card.content_layout.addStretch()

        # ── Timer ──────────────────────────────────────────────────────────────
        self._data_timer = QTimer(self)
        self._data_timer.timeout.connect(self._refresh_charts)
        self._data_timer.start(2000)

        # Seed initial data
        self._seed_initial_data()

    def _seed_initial_data(self):
        """Seed charts with realistic-looking initial data."""
        import random
        random.seed(42)

        for _ in range(20):
            self.cpu_chart.update_data(random.uniform(0, 5))
            self.ram_chart.update_data(random.uniform(40, 70))
            self.disk_chart.update_data(random.uniform(0, 2))
            self.net_chart.update_data(random.uniform(0, 100))
            self.host_cpu.update_data(random.uniform(5, 15))
            self.host_ram.update_data(random.uniform(35, 50))
            self.host_disk.update_data(random.uniform(10, 15))

    def _refresh_charts(self):
        """Generate and push new data points to all charts."""
        import random
        random.seed()

        # VM metrics — simulate realistic values
        cpu = random.gauss(2.5, 1.5)
        ram = 45 + random.gauss(0, 2)
        disk = max(0, random.gauss(0.5, 0.3))
        net = max(0, random.gauss(50, 30))

        self.cpu_chart.update_data(max(0, cpu))
        self.ram_chart.update_data(max(0, ram))
        self.disk_chart.update_data(disk)
        self.net_chart.update_data(net)

        # Host metrics
        self.host_cpu.update_data(random.gauss(8, 2))
        self.host_ram.update_data(random.gauss(42, 3))
        self.host_disk.update_data(random.gauss(12, 0.5))

    def _clear_all(self):
        """Clear all chart data."""
        for chart in [
            self.cpu_chart, self.ram_chart, self.disk_chart, self.net_chart,
            self.host_cpu, self.host_ram, self.host_disk,
        ]:
            chart.clear()
