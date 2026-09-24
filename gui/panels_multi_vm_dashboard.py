"""Multi-VM Dashboard Panel — shows all VMs at a glance with resource overview.

Displays:
- Global resource utilization (RAM, CPU, VM count)
- Per-VM status cards with quick actions
- Color-coded status indicators
- At-a-glance metrics for each VM
"""

from __future__ import annotations

from gui.theme import T
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QScrollArea, QSizePolicy, QProgressBar,
)

from gui.widgets import Card, StatusIndicator, SectionHeader
from gui.multi_vm import MultiVMManager


class VMCard(QFrame):
    """Compact card showing a single VM's status and metrics."""

    clicked = pyqtSignal(str)

    STATUS_COLORS = {
        "running": T.STATUS_RUNNING,
        "paused": T.STATUS_PAUSED,
        "stopped": T.STATUS_STOPPED,
        "error": T.ERROR,
        "starting": T.INFO,
        "stopping": T.WARNING,
    }

    def __init__(self, vm_summary, parent=None):
        super().__init__(parent)
        self._name = vm_summary.name
        self._status = vm_summary.status
        self.setFixedHeight(120)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet(
            "QFrame {"
            f"  background: {T.BG_SECONDARY};"
            f"  border: 1px solid {T.BG_TERTIARY};"
            f"  border-radius: 8px;"
            "}"
            f"QFrame:hover {{ border-color: {T.BRAND}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Top row: status dot + name + status
        top_row = QWidget()
        tr_layout = QHBoxLayout(top_row)
        tr_layout.setContentsMargins(0, 0, 0, 0)
        tr_layout.setSpacing(6)

        dot = StatusIndicator(QColor(self.STATUS_COLORS.get(self._status, T.TEXT_MUTED)))
        dot.set_status(running=(self._status == "running"),
                       connected=(self._status == "running"))
        tr_layout.addWidget(dot)

        name_label = QLabel(self._name)
        name_label.setStyleSheet(
            f"color: {T.TEXT_PRIMARY}; font-size: 13px; font-weight: 600;"
        )
        tr_layout.addWidget(name_label)
        tr_layout.addStretch()

        status_label = QLabel(self._status.upper())
        status_label.setStyleSheet(
            f"color: {self.STATUS_COLORS.get(self._status, T.TEXT_MUTED)};"
            f" font-size: 10px; font-weight: bold;"
        )
        tr_layout.addWidget(status_label)
        layout.addWidget(top_row)

        # Info row
        info_row = QWidget()
        ir_layout = QHBoxLayout(info_row)
        ir_layout.setContentsMargins(0, 0, 0, 0)
        ir_layout.setSpacing(12)

        cpu_label = QLabel(f"CPU: {vm_summary.cpus}")
        cpu_label.setStyleSheet(f"color: {T.TEXT_MUTED}; font-size: 11px;")
        ir_layout.addWidget(cpu_label)

        ram_label = QLabel(f"RAM: {vm_summary.ram_mb // 1024}GB")
        ram_label.setStyleSheet(f"color: {T.TEXT_MUTED}; font-size: 11px;")
        ir_layout.addWidget(ram_label)

        if vm_summary.disk_total_gb > 0:
            disk_label = QLabel(f"Disk: {vm_summary.disk_total_gb:.1f}GB")
            disk_label.setStyleSheet(f"color: {T.TEXT_MUTED}; font-size: 11px;")
            ir_layout.addWidget(disk_label)

        if vm_summary.qmp_port:
            port_label = QLabel(f"QMP: {vm_summary.qmp_port}")
            port_label.setStyleSheet(f"color: {T.TEXT_MUTED}; font-size: 11px;")
            ir_layout.addWidget(port_label)

        ir_layout.addStretch()
        layout.addWidget(info_row)

        # Bottom row: action buttons
        btn_row = QWidget()
        br_layout = QHBoxLayout(btn_row)
        br_layout.setContentsMargins(0, 0, 0, 0)
        br_layout.setSpacing(4)

        if self._status == "running":
            stop_btn = QPushButton("■ Stop")
            stop_btn.setFixedSize(56, 24)
            stop_btn.setStyleSheet(
                f"QPushButton {{ background: {T.STATUS_STOPPED}; color: white; "
                f"border: none; border-radius: 4px; font-size: 10px; }}"
                "QPushButton:hover { background: #dc2626; }"
            )
            stop_btn.clicked.connect(lambda: self.clicked.emit(f"stop:{self._name}"))
            br_layout.addWidget(stop_btn)

            pause_btn = QPushButton("⏸ Pause")
            pause_btn.setFixedSize(60, 24)
            pause_btn.setStyleSheet(
                f"QPushButton {{ background: {T.STATUS_PAUSED}; color: white; "
                f"border: none; border-radius: 4px; font-size: 10px; }}"
                "QPushButton:hover { background: #d97706; }"
            )
            pause_btn.clicked.connect(lambda: self.clicked.emit(f"pause:{self._name}"))
            br_layout.addWidget(pause_btn)

        elif self._status in ("stopped", "error"):
            start_btn = QPushButton("▶ Start")
            start_btn.setFixedSize(60, 24)
            start_btn.setStyleSheet(
                f"QPushButton {{ background: {T.STATUS_RUNNING}; color: white; "
                f"border: none; border-radius: 4px; font-size: 10px; }}"
                "QPushButton:hover { background: #16a34a; }"
            )
            start_btn.clicked.connect(lambda: self.clicked.emit(f"start:{self._name}"))
            br_layout.addWidget(start_btn)

        elif self._status == "paused":
            resume_btn = QPushButton("▶ Resume")
            resume_btn.setFixedSize(66, 24)
            resume_btn.setStyleSheet(
                f"QPushButton {{ background: {T.STATUS_RUNNING}; color: white; "
                f"border: none; border-radius: 4px; font-size: 10px; }}"
                "QPushButton:hover { background: #16a34a; }"
            )
            resume_btn.clicked.connect(lambda: self.clicked.emit(f"resume:{self._name}"))
            br_layout.addWidget(resume_btn)

        br_layout.addStretch()
        layout.addWidget(btn_row)

    def mousePressEvent(self, event):
        self.clicked.emit(f"select:{self._name}")
        super().mousePressEvent(event)


class MultiVMDashboardPanel(QWidget):
    """Dashboard showing all VMs at a glance."""

    vm_action = pyqtSignal(str, str)  # action, vm_name
    vm_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = MultiVMManager()
        self._vm_cards: dict[str, VMCard] = {}
        self._qmp_bridge = None
        self._active_vm = None
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Header ───────────────────────────────────────────────────────────
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Multi-VM Dashboard")
        title.setStyleSheet(
            f"color: {T.TEXT_PRIMARY}; font-size: 16px; font-weight: bold;"
        )
        hl.addWidget(title)
        hl.addStretch()
        layout.addWidget(header)

        # ── Global Resource Bar ──────────────────────────────────────────────
        resource_card = Card("Global Resource Allocation")
        resource_card.setFixedHeight(100)
        layout.addWidget(resource_card)

        res_grid = QGridLayout()
        res_grid.setSpacing(16)
        res_grid.setContentsMargins(0, 0, 0, 0)

        # VM count
        vm_stat = QWidget()
        vm_layout = QVBoxLayout(vm_stat)
        vm_layout.setContentsMargins(0, 0, 0, 0)
        self._vm_count_label = QLabel("0 VMs")
        self._vm_count_label.setStyleSheet(
            f"color: {T.TEXT_PRIMARY}; font-size: 18px; font-weight: bold;"
        )
        vm_layout.addWidget(self._vm_count_label)
        vm_running_label = QLabel("running")
        vm_running_label.setStyleSheet(f"color: {T.TEXT_MUTED}; font-size: 11px;")
        vm_layout.addWidget(vm_running_label)
        self._vm_running_label = vm_running_label
        res_grid.addWidget(vm_stat, 0, 0)

        # RAM bar
        ram_stat = QWidget()
        ram_layout = QVBoxLayout(ram_stat)
        ram_layout.setContentsMargins(0, 0, 0, 0)
        self._ram_label = QLabel("0 / 64 GB")
        self._ram_label.setStyleSheet(f"color: {T.TEXT_PRIMARY}; font-size: 12px;")
        ram_layout.addWidget(self._ram_label)
        self._ram_bar = QProgressBar()
        self._ram_bar.setFixedHeight(6)
        self._ram_bar.setMaximum(100)
        self._ram_bar.setValue(0)
        self._ram_bar.setTextVisible(False)
        self._ram_bar.setStyleSheet(
            f"QProgressBar {{ background: {T.BG_SECONDARY}; border: none; }}"
            f"QProgressBar::chunk {{ background: {T.CHART_RAM}; }}"
        )
        ram_layout.addWidget(self._ram_bar)
        res_grid.addWidget(ram_stat, 0, 1)

        # CPU bar
        cpu_stat = QWidget()
        cpu_layout = QVBoxLayout(cpu_stat)
        cpu_layout.setContentsMargins(0, 0, 0, 0)
        self._cpu_label = QLabel("0 / 32 vCPUs")
        self._cpu_label.setStyleSheet(f"color: {T.TEXT_PRIMARY}; font-size: 12px;")
        cpu_layout.addWidget(self._cpu_label)
        self._cpu_bar = QProgressBar()
        self._cpu_bar.setFixedHeight(6)
        self._cpu_bar.setMaximum(100)
        self._cpu_bar.setValue(0)
        self._cpu_bar.setTextVisible(False)
        self._cpu_bar.setStyleSheet(
            f"QProgressBar {{ background: {T.BG_SECONDARY}; border: none; }}"
            f"QProgressBar::chunk {{ background: {T.CHART_CPU}; }}"
        )
        cpu_layout.addWidget(self._cpu_bar)
        res_grid.addWidget(cpu_stat, 0, 2)

        res_grid.setColumnStretch(0, 1)
        res_grid.setColumnStretch(1, 2)
        res_grid.setColumnStretch(2, 2)
        resource_card.content_layout.addLayout(res_grid)

        # ── Active VM Info ───────────────────────────────────────────────────
        self._active_vm_card = Card("Active VM")
        self._active_vm_card.setFixedHeight(60)
        active_layout = QHBoxLayout()
        active_layout.setContentsMargins(0, 0, 0, 0)
        self._active_vm_label = QLabel("No VM selected")
        self._active_vm_label.setStyleSheet(
            f"color: {T.TEXT_MUTED}; font-size: 12px;"
        )
        active_layout.addWidget(self._active_vm_label)
        active_layout.addStretch()
        self._active_vm_card.content_layout.addLayout(active_layout)
        layout.addWidget(self._active_vm_card)

        # ── VM Cards Grid ────────────────────────────────────────────────────
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
        )
        self._scroll_widget = QWidget()
        self._vm_grid = QGridLayout(self._scroll_widget)
        self._vm_grid.setSpacing(8)
        self._vm_grid.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(self._scroll_widget)
        layout.addWidget(scroll_area)

        # ── Action buttons ───────────────────────────────────────────────────
        action_row = QWidget()
        al = QHBoxLayout(action_row)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(8)

        refresh_btn = QPushButton("⟳ Refresh")
        refresh_btn.setFixedSize(90, 32)
        refresh_btn.setStyleSheet(
            f"QPushButton {{ background: {T.BG_SECONDARY}; border: 1px solid {T.BG_TERTIARY};"
            f" border-radius: 6px; color: {T.TEXT_SECONDARY}; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {T.BG_TERTIARY}; }}"
        )
        refresh_btn.clicked.connect(self.refresh)
        al.addWidget(refresh_btn)

        add_btn = QPushButton("＋ Add VM")
        add_btn.setFixedSize(90, 32)
        add_btn.setStyleSheet(
            f"QPushButton {{ background: {T.STATUS_RUNNING}; border: none; border-radius: 6px;"
            f" color: white; font-size: 12px; font-weight: 600; }}"
            "QPushButton:hover { background: #16a34a; }"
        )
        add_btn.clicked.connect(self._add_vm)
        al.addWidget(add_btn)

        al.addStretch()
        layout.addWidget(action_row)

        # ── Auto-refresh ─────────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_vms)
        self._timer.start(3000)

        self.refresh()

    def refresh(self):
        """Refresh all VM cards and resource display."""
        # Poll status first
        self._manager.poll_status()
        self._manager.cleanup_exited()

        # Clear existing cards
        for card in self._vm_cards.values():
            card.deleteLater()
        self._vm_cards.clear()

        # Clear grid
        while self._vm_grid.count():
            item = self._vm_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add VM cards
        summaries = self._manager.get_all_summaries()
        for i, summary in enumerate(summaries):
            card = VMCard(summary)
            card.clicked.connect(self._on_card_action)
            row = i // 3
            col = i % 3
            self._vm_grid.addWidget(card, row, col)
            self._vm_cards[summary.name] = card

        # Update resource display
        self._update_resources()

    def _update_resources(self):
        """Update the global resource bar."""
        stats = self._manager.get_total_resources()

        self._vm_count_label.setText(f"{stats['running_vms']} / {stats['total_vms']} VMs")
        self._vm_running_label.setText(
            f"{stats['running_vms']} running • {stats['total_vms'] - stats['running_vms']} stopped"
        )

        self._ram_label.setText(
            f"{stats['total_ram_active'] // 1024} / {stats['max_ram_mb'] // 1024} GB"
        )
        self._ram_bar.setValue(int(stats['ram_usage_pct']))

        self._cpu_label.setText(f"{stats['total_cpus_active']} / {stats['max_cpus']} vCPUs")
        self._cpu_bar.setValue(int(stats['cpu_usage_pct']))

    def _poll_vms(self):
        """Periodic status poll."""
        self._manager.poll_status()
        self._manager.cleanup_exited()
        self.refresh()

    def _on_card_action(self, action_str: str):
        """Handle action from VM card (start:vmname, stop:vmname, select:vmname)."""
        parts = action_str.split(":", 1)
        if len(parts) != 2:
            return
        action, vm_name = parts

        if action == "select":
            self._active_vm = vm_name
            config = self._manager.get_vm(vm_name)
            if config:
                self._active_vm_label.setText(
                    f"{vm_name} | QMP: {config.qmp_port} | SSH: {config.ssh_port} | "
                    f"RAM: {config.ram_mb}MB | CPUs: {config.cpus}"
                )
                self._active_vm_label.setStyleSheet(
                    f"color: {T.TEXT_PRIMARY}; font-size: 12px;"
                )
            self.vm_selected.emit(vm_name)
        elif action == "start":
            self.vm_action.emit("start", vm_name)
        elif action == "stop":
            self.vm_action.emit("stop", vm_name)
        elif action == "pause":
            self.vm_action.emit("pause", vm_name)
        elif action == "resume":
            self.vm_action.emit("resume", vm_name)

    def _add_vm(self):
        """Add a new VM via the switcher panel."""
        self.vm_action.emit("add", "")

    def set_qmp_bridge(self, bridge):
        """Connect to QMP bridge for control operations."""
        self._qmp_bridge = bridge

    def get_manager(self) -> MultiVMManager:
        """Access the underlying MultiVMManager."""
        return self._manager

    def set_active_vm(self, name: str):
        """Set the active VM for context display."""
        self._active_vm = name
        config = self._manager.get_vm(name)
        if config:
            self._active_vm_label.setText(
                f"{name} | QMP: {config.qmp_port} | SSH: {config.ssh_port} | "
                f"RAM: {config.ram_mb}MB | CPUs: {config.cpus}"
            )

    def get_active_vm(self) -> str | None:
        """Get the name of the currently active VM."""
        return self._active_vm
