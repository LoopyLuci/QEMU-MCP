"""Dashboard panel — VM status overview and quick actions.

Shows a comprehensive status card with VM state, resource usage,
quick action buttons, recent activity log, and skills summary.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPixmap, QIcon
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QGroupBox,
    QSpacerItem,
    QSizePolicy,
)

from gui.widgets import Card, StatusIndicator, IconButton


class DashboardPanel(QWidget):
    """Main dashboard — VM status overview and quick actions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._qmp_bridge = None
        self._vm_state = "unknown"
        self._vm_running = False
        self._vm_pid = "—"
        self._vm_ram = "—"
        self._vm_cpus = "—"
        self._vm_disk_used = "—"
        self._vm_disk_total = "—"
        self._vm_uptime = "0:00:00"
        self.setStyleSheet("background: #0f172a;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── VM Status Card ─────────────────────────────────────────────────────
        status_card = Card("Virtual Machine Status", self)
        status_card.setFixedHeight(200)
        layout.addWidget(status_card)

        # Status indicator + state
        status_row = QWidget()
        status_row_layout = QHBoxLayout(status_row)
        status_row_layout.setContentsMargins(0, 0, 0, 0)
        status_row_layout.setSpacing(12)

        self.status_dot = StatusIndicator(QColor("#555555"))
        status_row_layout.addWidget(self.status_dot, alignment=Qt.AlignVCenter)

        state_layout = QVBoxLayout()
        state_layout.setSpacing(2)
        state_label = QLabel("Stopped")
        state_label.setStyleSheet("color: #94a3b8; font-size: 14px; font-weight: 600;")
        state_label.setFixedHeight(20)
        state_layout.addWidget(state_label)

        vm_name_label = QLabel("omarchy-vm")
        vm_name_label.setStyleSheet("color: #64748b; font-size: 12px;")
        state_layout.addWidget(vm_name_label)
        state_layout.addStretch()

        status_row_layout.addWidget(status_row, alignment=Qt.AlignVCenter)
        status_row_layout.addStretch()

        # Quick stats row
        stats_row = QWidget()
        stats_row_layout = QHBoxLayout(stats_row)
        stats_row_layout.setContentsMargins(0, 0, 0, 0)
        stats_row_layout.setSpacing(16)

        for label, value, color in [
            ("PID", "—", "#64748b"),
            ("RAM", "8.0 GB", "#38bdf8"),
            ("vCPUs", "4", "#a78bfa"),
            ("Disk", "6.6 GB / 64 GB", "#22c55e"),
            ("Uptime", "0:00:00", "#f59e0b"),
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
        status_card.content_layout.addWidget(status_row)
        status_card.content_layout.addWidget(stats_row)
        status_card.content_layout.addStretch()

        # ── Quick Actions ──────────────────────────────────────────────────────
        actions_card = Card("Quick Actions")
        layout.addWidget(actions_card)

        actions_row = QWidget()
        actions_row_layout = QHBoxLayout(actions_row)
        actions_row_layout.setContentsMargins(0, 0, 0, 0)
        actions_row_layout.setSpacing(12)

        # Start VM
        start_btn = IconButton(text="Start VM")
        start_btn.setFixedSize(180, 48)
        start_btn.setStyleSheet("""
            IconButton {
                background: #22c55e;
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: 600;
                padding: 0 16px;
            }
            IconButton:hover { background: #16a34a; }
            IconButton:disabled { background: #22c55e20; color: #64748b; }
        """)
        actions_row_layout.addWidget(start_btn)

        # Stop VM
        stop_btn = IconButton(text="Stop VM")
        stop_btn.setFixedSize(180, 48)
        stop_btn.setStyleSheet("""
            IconButton {
                background: #ef4444;
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: 600;
                padding: 0 16px;
            }
            IconButton:hover { background: #dc2626; }
            IconButton:disabled { background: #ef444420; color: #64748b; }
        """)
        actions_row_layout.addWidget(stop_btn)

        # Reset VM
        reset_btn = IconButton(text="Reset VM")
        reset_btn.setFixedSize(180, 48)
        reset_btn.setStyleSheet("""
            IconButton {
                background: #f59e0b;
                border: none;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: 600;
                padding: 0 16px;
            }
            IconButton:hover { background: #d97706; }
            IconButton:disabled { background: #f59e0b20; color: #64748b; }
        """)
        actions_row_layout.addWidget(reset_btn)

        actions_row_layout.addStretch()
        actions_card.content_layout.addWidget(actions_row)

        # ── Recent Activity ─────────────────────────────────────────────────────
        activity_card = Card("Recent Activity")
        layout.addWidget(activity_card)

        self.activity_list = QListWidget()
        self.activity_list.setStyleSheet("""
            QListWidget {
                background: #0f172a;
                color: #e2e8f0;
                border: none;
                font-size: 12px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #1e293b;
            }
            QListWidget::item:selected { background: #1e3a5f; }
            QListWidget::item:selected:!active { background: #1e3a5f; }
        """)
        for i in range(1, 11):
            item = QListWidgetItem(f"[{i:02d}] VM operation logged")
            self.activity_list.addItem(item)
        self.activity_list.setMaximumHeight(160)
        activity_card.content_layout.addWidget(self.activity_list)

        # ── Skills Summary ─────────────────────────────────────────────────────
        skills_card = Card("Available Skills (Agent Reference)")
        layout.addWidget(skills_card)

        skills_text = QLabel(
            "• vm_lifecycle — Start, stop, reset, suspend, resume, eject ISO, configure boot\n"
            "• guest_interaction — Execute commands, read/write/list/remove files via SSH\n"
            "• vm_monitoring — Monitor VM health with status + guest commands\n"
            "• iso_management — Boot from ISO, eject, manage boot order"
        )
        skills_text.setStyleSheet("color: #94a3b8; font-size: 12px;")
        skills_text.setWordWrap(True)
        skills_text.setMargin(8)
        skills_card.content_layout.addWidget(skills_text)

        # ── Timers ──────────────────────────────────────────────────────────────
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(3000)

    def _refresh_status(self):
        """Refresh status indicators from current VM state."""
        # In a real app, this would query QMP
        pass

    def add_activity(self, message: str):
        """Add an activity log entry."""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        item = QListWidgetItem(f"[{ts}] {message}")
        self.activity_list.insertItem(0, item)
        if self.activity_list.count() > 20:
            self.activity_list.takeItem(self.activity_list.count() - 1)

    def set_qmp_bridge(self, bridge):
        """Connect to QMP bridge for live status updates."""
        self._qmp_bridge = bridge
        bridge.vm_status.connect(self.update_vm_status)

    def update_vm_status(self, status: dict):
        """Update the dashboard display with VM status from QMP."""
        state = status.get("state", "unknown")
        self._vm_state = state
        self._vm_running = state in ("running", "prelaunch", "inmigrate")

        # Update status dot
        if self._vm_running:
            self.status_dot.set_status(running=True, connected=True)
            state_label = self.findChild(QLabel, None)
            for child in self.findChildren(QLabel):
                if child.styleSheet().startswith("color: #94a3b8") and "font-size: 14px" in child.styleSheet():
                    child.setText(state.title())
                    child.setStyleSheet("color: #22c55e; font-size: 14px; font-weight: 600;")
                    break
        else:
            self.status_dot.set_status(running=False, connected=False)

        # Try to extract PID from status
        pid = status.get("pid", status.get("pid", "—"))
        if isinstance(pid, int):
            self._vm_pid = str(pid)

        # Update stats
        self._update_stats_display()

        # Query more data if running
        if self._vm_running and self._qmp_bridge:
            self._qmp_bridge.get_status()  # Refresh

    def _update_stats_display(self):
        """Refresh the stat labels in the dashboard."""
        stats = self.findChildren(QLabel)
        # Find and update stat value labels by matching text
        for lbl in stats:
            txt = lbl.text()
            if txt == "—" and self._vm_pid != "—":
                lbl.setText(self._vm_pid)
                lbl.setStyleSheet("color: #64748b; font-size: 13px; font-weight: 600;")
