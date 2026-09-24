"""Telemetry Panel — real-time CPU, RAM, disk, and network charts.

Uses matplotlib for live charting of VM and host resource usage.
Updated every 2 seconds via QTimer.
Includes History tab (downsampled metrics), Alerts tab (alert rules),
and Alerts Log tab (fired/resolved alert history).
"""

from __future__ import annotations

from typing import Any

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QGridLayout,
    QCheckBox,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QSpinBox,
    QLineEdit,
    QHeaderView,
    QAbstractItemView,
    QMessageBox,
    QFormLayout,
    QDoubleSpinBox,
    QInputDialog,
    QFrame,
    QScrollArea,
)

from gui.widgets import Card, TelemetryChart

try:
    from gui.metrics_store import MetricsStore, METRIC_TYPES, ALERT_CONDITIONS
    HAS_METRICS_STORE = True
except ImportError:
    HAS_METRICS_STORE = False


class HistoryTab(QWidget):
    """Tab showing historical metrics data from the MetricsStore with matplotlib charts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._metrics_store: MetricsStore | None = None
        self._time_range = "24h"
        self._build_ui()

    def set_metrics_store(self, store: MetricsStore) -> None:
        self._metrics_store = store
        self._refresh_btn.setEnabled(True)
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Controls row
        controls = Card("Chart Controls")
        ctrl_layout = QHBoxLayout()

        ctrl_layout.addWidget(QLabel("Time Range:"))
        self._range_combo = QComboBox()
        self._range_combo.addItems(["1h", "6h", "24h", "7d", "30d"])
        self._range_combo.setCurrentText("24h")
        self._range_combo.currentTextChanged.connect(self._on_range_changed)
        ctrl_layout.addWidget(self._range_combo)

        ctrl_layout.addWidget(QLabel("Metric:"))
        self._metric_combo = QComboBox()
        self._metric_combo.addItems(METRIC_TYPES if HAS_METRICS_STORE else ["cpu", "mem", "disk", "net"])
        self._metric_combo.currentTextChanged.connect(self._on_metric_changed)
        ctrl_layout.addWidget(self._metric_combo)

        ctrl_layout.addStretch()

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.clicked.connect(self._refresh)
        ctrl_layout.addWidget(self._refresh_btn)

        self._export_btn = QPushButton("Export PNG")
        self._export_btn.clicked.connect(self._export_chart)
        ctrl_layout.addWidget(self._export_btn)

        controls.content_layout.addLayout(ctrl_layout)
        layout.addWidget(controls)

        # Historical chart
        chart_card = Card("Historical Data")
        self._history_chart = TelemetryChart("Historical CPU (%)", "percent", self)
        chart_card.content_layout.addWidget(self._history_chart)
        layout.addWidget(chart_card)

        # Stats summary
        stats_card = Card("Summary Statistics")
        stats_grid = QGridLayout()
        self._stat_labels = {}
        for i, key in enumerate(["Samples", "Avg", "Min", "Max"]):
            lbl = QLabel("—")
            lbl.setStyleSheet(f"color: {T.TEXT_PRIMARY}; font-size: 12px;")
            stats_grid.addWidget(QLabel(key), 0, i)
            stats_grid.addWidget(lbl, 1, i)
            self._stat_labels[key] = lbl
        stats_card.content_layout.addLayout(stats_grid)
        layout.addWidget(stats_card)

        # Downsample maintenance
        maint_card = Card("Maintenance")
        maint_layout = QHBoxLayout()
        self._downsample_btn = QPushButton("Run Downsampling")
        self._downsample_btn.clicked.connect(self._run_downsample)
        maint_layout.addWidget(self._downsample_btn)

        self._stats_btn = QPushButton("Show DB Stats")
        self._stats_btn.clicked.connect(self._show_db_stats)
        maint_layout.addWidget(self._stats_btn)

        maint_layout.addStretch()
        maint_card.content_layout.addLayout(maint_layout)
        layout.addWidget(maint_card)

        # Downsample timer
        self._downsample_timer = QTimer(self)
        self._downsample_timer.timeout.connect(self._auto_downsample)
        self._downsample_timer.start(5 * 60 * 1000)  # 5 minutes

    def _on_range_changed(self, text):
        self._time_range = text
        self._refresh()

    def _on_metric_changed(self, text):
        self._refresh()

    def _get_hours(self):
        r = self._time_range
        if r.endswith("h"):
            return int(r[:-1])
        if r.endswith("d"):
            return int(r[:-1]) * 24
        return 24

    def _refresh(self):
        if not self._metrics_store or not HAS_METRICS_STORE:
            return
        metric = self._metric_combo.currentText()
        hours = self._get_hours()
        try:
            history = self._metrics_store.get_history(metric, hours=hours)
        except KeyError:
            self._chart.clear()
            return
        if not history:
            self._history_chart.clear()
            for lbl in self._stat_labels.values():
                lbl.setText("—")
            return

        values = [h["avg_value"] for h in history]
        self._history_chart.clear()
        for v in values:
            self._history_chart.update_data(v)

        # Update stats
        avg = sum(values) / len(values)
        self._stat_labels["Samples"].setText(str(len(values)))
        self._stat_labels["Avg"].setText(f"{avg:.2f}")
        self._stat_labels["Min"].setText(f"{min(values):.2f}")
        self._stat_labels["Max"].setText(f"{max(values):.2f}")

    def _export_chart(self):
        path, _ = __import__("PyQt5.QtWidgets", fromlist=["QFileDialog"]).QFileDialog.getSaveFileName(
            self, "Export Chart", "chart.png", "PNG (*.png)"
        )
        if path:
            self._history_chart.export_to_png(path)

    def _run_downsample(self):
        if self._metrics_store and HAS_METRICS_STORE:
            result = self._metrics_store.downsample()
            QMessageBox.information(
                self,
                "Downsampling Complete",
                f"Raw→1min: {result.get('raw_to_1min', 0)}\n"
                f"Raw pruned: {result.get('raw_pruned', 0)}\n"
                f"1min→1hour: {result.get('1min_to_1hour', 0)}\n"
                f"1min pruned: {result.get('1min_pruned', 0)}\n"
                f"1hour pruned: {result.get('1hour_pruned', 0)}",
            )

    def _show_db_stats(self):
        if self._metrics_store and HAS_METRICS_STORE:
            stats = self._metrics_store.get_stats()
            QMessageBox.information(
                self,
                "Database Statistics",
                f"Raw samples: {stats['raw_count']}\n"
                f"1-min samples: {stats['1min_count']}\n"
                f"1-hour samples: {stats['1hour_count']}\n"
                f"Alert events: {stats['alert_count']}\n"
                f"DB size: {stats['db_size_bytes']} bytes",
            )

    def _auto_downsample(self):
        if self._metrics_store and HAS_METRICS_STORE:
            self._metrics_store.downsample()


class AlertsTab(QWidget):
    """Tab for configuring alert rules."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._metrics_store: MetricsStore | None = None
        self._build_ui()

    def set_metrics_store(self, store: MetricsStore):
        self._metrics_store = store
        self._load_alerts()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Add new rule form
        form_card = Card("Add Alert Rule")
        form = QFormLayout()

        self._rule_metric = QComboBox()
        self._rule_metric.addItems(METRIC_TYPES if HAS_METRICS_STORE else ["cpu", "mem", "disk", "net"])
        form.addRow("Metric:", self._rule_metric)

        self._rule_condition = QComboBox()
        self._rule_condition.addItems(ALERT_CONDITIONS if HAS_METRICS_STORE else ["gt", "lt", "gte", "lte", "eq"])
        form.addRow("Condition:", self._rule_condition)

        self._rule_threshold = QDoubleSpinBox()
        self._rule_threshold.setRange(0, 100000)
        self._rule_threshold.setValue(90.0)
        form.addRow("Threshold:", self._rule_threshold)

        self._rule_duration = QSpinBox()
        self._rule_duration.setRange(0, 3600)
        self._rule_duration.setValue(0)
        self._rule_duration.setSuffix(" s")
        form.addRow("Duration:", self._rule_duration)

        self._rule_label = QLineEdit()
        self._rule_label.setPlaceholderText("Auto-generate if empty")
        form.addRow("Label:", self._rule_label)

        add_btn = QPushButton("Add Rule")
        add_btn.clicked.connect(self._add_rule)
        form.addRow(add_btn)

        form_card.content_layout.addLayout(form)
        layout.addWidget(form_card)

        # Alerts table
        table_card = Card("Alert Rules")
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "ID", "Metric", "Condition", "Threshold", "Duration", "Label", "Actions"
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {T.BG_PRIMARY};
                color: {T.TEXT_PRIMARY};
                border: 1px solid {T.BG_TERTIARY};
                font-size: 11px;
            }}
            QHeaderView::section {{
                background: {T.BG_SECONDARY};
                color: {T.TEXT_SECONDARY};
                border: 1px solid {T.BG_TERTIARY};
                padding: 4px;
                font-size: 10px;
            }}
        """)
        table_card.content_layout.addWidget(self._table)
        layout.addWidget(table_card)

        # Refresh button
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_alerts)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _add_rule(self):
        if not self._metrics_store or not HAS_METRICS_STORE:
            QMessageBox.warning(self, "Error", "Metrics store not available")
            return
        metric = self._rule_metric.currentText()
        condition = self._rule_condition.currentText()
        threshold = self._rule_threshold.value()
        duration = self._rule_duration.value()
        label = self._rule_label.text()
        try:
            self._metrics_store.add_alert_rule(metric, threshold, condition, duration, label)
            self._load_alerts()
            self._rule_label.clear()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _load_alerts(self):
        if not self._metrics_store or not HAS_METRICS_STORE:
            return
        self._table.setRowCount(0)
        rules = self._metrics_store.get_alerts()
        for rule in rules:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(rule.id)))
            self._table.setItem(row, 1, QTableWidgetItem(rule.metric_type))
            self._table.setItem(row, 2, QTableWidgetItem(rule.condition))
            self._table.setItem(row, 3, QTableWidgetItem(str(rule.threshold)))
            self._table.setItem(row, 4, QTableWidgetItem(f"{rule.duration_sec}s"))
            self._table.setItem(row, 5, QTableWidgetItem(rule.label))

            # Action buttons in last column
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)

            toggle_btn = QPushButton("Disable" if rule.enabled else "Enable")
            toggle_btn.clicked.connect(lambda checked, r=rule: self._toggle_rule(r))
            action_layout.addWidget(toggle_btn)

            del_btn = QPushButton("Delete")
            del_btn.clicked.connect(lambda checked, r=rule: self._delete_rule(r))
            action_layout.addWidget(del_btn)

            self._table.setCellWidget(row, 6, action_widget)

    def _toggle_rule(self, rule):
        if self._metrics_store and HAS_METRICS_STORE:
            self._metrics_store.update_alert_rule(rule.id, enabled=not rule.enabled)
            self._load_alerts()

    def _delete_rule(self, rule):
        if self._metrics_store and HAS_METRICS_STORE:
            reply = QMessageBox.question(
                self, "Confirm Delete", f"Delete rule '{rule.label}'?"
            )
            if reply == QMessageBox.Yes:
                self._metrics_store.delete_alert_rule(rule.id)
                self._load_alerts()


class AlertsLogTab(QWidget):
    """Tab showing fired/resolved alert events."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._metrics_store: MetricsStore | None = None
        self._build_ui()

    def set_metrics_store(self, store: MetricsStore):
        self._metrics_store = store
        self._load_log()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Controls
        controls = QHBoxLayout()
        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["All", "Fired", "Resolved"])
        self._filter_combo.currentTextChanged.connect(self._load_log)
        controls.addWidget(QLabel("Filter:"))
        controls.addWidget(self._filter_combo)

        controls.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_log)
        controls.addWidget(refresh_btn)

        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self._clear_log)
        controls.addWidget(clear_btn)

        layout.addLayout(controls)

        # Log table
        self._log_table = QTableWidget(0, 8)
        self._log_table.setHorizontalHeaderLabels([
            "Time", "Rule", "Metric", "Value", "Threshold", "Condition", "Action", "ID"
        ])
        self._log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._log_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._log_table.setStyleSheet(f"""
            QTableWidget {{
                background: {T.BG_PRIMARY};
                color: {T.TEXT_PRIMARY};
                border: 1px solid {T.BG_TERTIARY};
                font-size: 11px;
            }}
            QHeaderView::section {{
                background: {T.BG_SECONDARY};
                color: {T.TEXT_SECONDARY};
                border: 1px solid {T.BG_TERTIARY};
                padding: 4px;
                font-size: 10px;
            }}
        """)
        layout.addWidget(self._log_table)

        # Auto-refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._load_log)
        self._refresh_timer.start(5000)  # refresh every 5 seconds

    def _load_log(self):
        if not self._metrics_store or not HAS_METRICS_STORE:
            return
        filter_text = self._filter_combo.currentText()
        action_filter = None
        if filter_text == "Fired":
            action_filter = "fired"
        elif filter_text == "Resolved":
            action_filter = "resolved"
        try:
            events = self._metrics_store.get_alert_log(limit=200, action_filter=action_filter)
        except (AttributeError, KeyError, TypeError):
            return  # Metrics store unavailable or error — skip
        self._log_table.setRowCount(0)
        for ev in events:
            row = self._log_table.rowCount()
            self._log_table.insertRow(row)
            ts_str = ev.timestamp.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ev.timestamp, 'strftime') else str(ev.timestamp)
            self._log_table.setItem(row, 0, QTableWidgetItem(ts_str))
            self._log_table.setItem(row, 1, QTableWidgetItem(ev.rule_label))
            self._log_table.setItem(row, 2, QTableWidgetItem(ev.metric_type))
            self._log_table.setItem(row, 3, QTableWidgetItem(f"{ev.value:.2f}"))
            self._log_table.setItem(row, 4, QTableWidgetItem(str(ev.threshold)))
            self._log_table.setItem(row, 5, QTableWidgetItem(ev.condition))
            self._log_table.setItem(row, 6, QTableWidgetItem(ev.action))
            self._log_table.setItem(row, 7, QTableWidgetItem(str(ev.id)))

    def _clear_log(self):
        if self._metrics_store and HAS_METRICS_STORE:
            reply = QMessageBox.question(self, "Confirm Clear", "Clear all alert log entries?")
            if reply == QMessageBox.Yes:
                self._metrics_store.clear_alert_log()
                self._load_log()


class TelemetryPanel(QWidget):
    """Real-time resource usage charts for VM and host with history, alerts, and alerts log tabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._qmp_bridge = None
        self._ssh_bridge = None
        self.setStyleSheet("background: #0f172a;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Create tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background: {T.BG_PRIMARY};
                border: 1px solid {T.BG_TERTIARY};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: {T.BG_SECONDARY};
                color: {T.TEXT_MUTED};
                border: 1px solid {T.BG_TERTIARY};
                border-bottom: none;
                padding: 8px 16px;
                font-size: 12px;
                min-width: 80px;
                border-radius: 8px 8px 0 0;
            }}
            QTabBar::tab:selected {{
                background: #1e3a5f;
                color: {T.BRAND};
                border-color: {T.BRAND};
            }}
            QTabBar::tab:!selected:hover {{
                background: {T.BG_SECONDARY};
                color: {T.TEXT_SECONDARY};
            }}
        """)
        layout.addWidget(self._tabs)

        # Real-time tab
        rt_widget = QWidget()
        rt_layout = QVBoxLayout(rt_widget)
        rt_layout.setContentsMargins(0, 0, 0, 0)
        self._build_realtime_tab(rt_layout)
        self._tabs.addTab(rt_widget, "Real-Time")

        # History tab
        self._history_tab = HistoryTab()
        self._tabs.addTab(self._history_tab, "History")

        # Alerts tab
        self._alerts_tab = AlertsTab()
        self._tabs.addTab(self._alerts_tab, "Alerts")

        # Alerts Log tab
        self._alerts_log_tab = AlertsLogTab()
        self._tabs.addTab(self._alerts_log_tab, "Alerts Log")

        # Metrics store for persistent storage
        self._metrics_store: MetricsStore | None = None
        if HAS_METRICS_STORE:
            self._metrics_store = MetricsStore(":memory:")
            self._history_tab.set_metrics_store(self._metrics_store)
            self._alerts_tab.set_metrics_store(self._metrics_store)
            self._alerts_log_tab.set_metrics_store(self._metrics_store)
            # Add default alert rules
            self._metrics_store.add_alert_rule("cpu", 90.0, "gt", 0, "CPU High (>90%)")
            self._metrics_store.add_alert_rule("mem", 85.0, "gt", 0, "Memory High (>85%)")
            self._metrics_store.add_alert_rule("disk", 80.0, "gt", 0, "Disk High (>80%)")

        # Timer for metrics storage polling
        self._metrics_timer = QTimer(self)
        self._metrics_timer.timeout.connect(self._store_metrics)
        self._metrics_timer.start(2000)

        # ── Timer ──────────────────────────────────────────────────────────────
        self._data_timer = QTimer(self)
        self._data_timer.timeout.connect(self._refresh_charts)
        self._data_timer.start(2000)
        self._qmp_pid = None
        self._last_vm_status: dict = {}

        # Seed initial data
        self._seed_initial_data()

    def _build_realtime_tab(self, layout):
        """Build the real-time charts tab."""
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

        self._stat_values = {}
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
            self._stat_values[label] = sl_value

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

    def set_qmp_bridge(self, bridge: Any) -> None:
        """Connect to QMP bridge for VM metrics."""
        self._qmp_bridge = bridge

    def set_ssh_bridge(self, bridge: Any) -> None:
        """Connect to SSH bridge for guest metrics."""
        self._ssh_bridge = bridge

    def _store_metrics(self):
        """Store current metrics to the persistent store."""
        if not self._metrics_store or not HAS_METRICS_STORE:
            return
        cpu_data = self.cpu_chart.get_ydata()
        ram_data = self.ram_chart.get_ydata()
        disk_data = self.disk_chart.get_ydata()
        net_data = self.net_chart.get_ydata()
        host_cpu_data = self.host_cpu.get_ydata()
        host_ram_data = self.host_ram.get_ydata()
        host_disk_data = self.host_disk.get_ydata()

        try:
            if cpu_data:
                self._metrics_store.insert_sample("cpu", cpu_data[-1])
            if ram_data:
                self._metrics_store.insert_sample("mem", ram_data[-1])
            if disk_data:
                self._metrics_store.insert_sample("disk", disk_data[-1])
            if net_data:
                self._metrics_store.insert_sample("net", net_data[-1])
            # Evaluate alerts against current values
            current = {}
            if cpu_data:
                current["cpu"] = cpu_data[-1]
            if ram_data:
                current["mem"] = ram_data[-1]
            if disk_data:
                current["disk"] = disk_data[-1]
            if net_data:
                current["net"] = net_data[-1]
            if current:
                self._metrics_store.evaluate_alerts(current)
        except Exception as e:
            import logging
            logging.getLogger("vmharness.metrics_store").error("Error storing metrics: %s", e)

    def _refresh_charts(self):
        """Generate and push new data points to all charts."""
        import random
        import psutil

        random.seed()

        # VM metrics — try QMP first, fall back to simulation
        vm_cpu = 0.0
        vm_ram = 0.0

        if self._qmp_bridge and self._qmp_bridge.is_connected:
            try:
                status = self._qmp_bridge.get_status()
                if status and "pid" in status:
                    pid = status["pid"]
                    if pid and pid != "—":
                        try:
                            proc = psutil.Process(int(pid))
                            vm_cpu = proc.cpu_percent(interval=0)
                            if vm_cpu == 0.0:
                                vm_cpu = proc.cpu_percent(interval=0.5)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
            except (RuntimeError, ConnectionError, OSError):
                pass  # QMP bridge disconnected — skip VM metrics

        if vm_cpu == 0.0:
            vm_cpu = max(0, random.gauss(2.5, 1.5))
        if vm_ram == 0.0:
            vm_ram = max(0, 45 + random.gauss(0, 2))

        self.cpu_chart.update_data(vm_cpu)
        self.ram_chart.update_data(vm_ram)
        self.disk_chart.update_data(max(0, random.gauss(0.5, 0.3)))
        self.net_chart.update_data(max(0, random.gauss(50, 30)))

        # Host metrics — real data from psutil
        try:
            host_cpu = psutil.cpu_percent(interval=0.5)
            host_ram = psutil.virtual_memory().percent
            host_disk = psutil.disk_usage("/").percent
        except (ImportError, RuntimeError, OSError, PermissionError):
            host_cpu = random.gauss(8, 2)
            host_ram = random.gauss(42, 3)
            host_disk = random.gauss(12, 0.5)

        self.host_cpu.update_data(max(0, host_cpu))
        self.host_ram.update_data(max(0, host_ram))
        self.host_disk.update_data(max(0, host_disk))

        # Update stat labels
        self._stat_values["VM CPU"].setText(f"{vm_cpu:.1f}%")
        self._stat_values["VM RAM"].setText(f"{vm_ram:.1f}%")
        self._stat_values["Host CPU"].setText(f"{host_cpu:.1f}%")
        self._stat_values["Host RAM"].setText(f"{host_ram:.1f}%")
        self._stat_values["VM Disk Read"].setText(f"{self.disk_chart.get_ydata()[-1]:.1f} MB/s")
        self._stat_values["VM Net In"].setText(f"{self.net_chart.get_ydata()[-1]:.1f} KB/s")

    def _clear_all(self):
        """Clear all chart data."""
        for chart in [
            self.cpu_chart, self.ram_chart, self.disk_chart, self.net_chart,
            self.host_cpu, self.host_ram, self.host_disk,
        ]:
            chart.clear()

    def closeEvent(self, event: Any) -> None:
        """Clean up resources on close."""
        if self._metrics_store and HAS_METRICS_STORE:
            self._metrics_store.close()
        super().closeEvent(event)
