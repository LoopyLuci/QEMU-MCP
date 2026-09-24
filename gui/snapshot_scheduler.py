"""Snapshot Scheduler — automated snapshot management with retention policies.

Features:
    - Schedule types: interval (periodic), on-VM-stop, manual
    - Retention: keep last N snapshots per schedule
    - JSON persistence to ~/.local/share/vmharness/snapshot_schedules.json
    - PyQt5 signals for communication with other panels
    - Settings panel integration via get_settings_widget()
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
n# Suppress CLI console windows on Windows
CREATE_NO_WINDOW = 0x08000000
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QInputDialog, QFrame, QGroupBox,
    QGridLayout, QSizePolicy,
)

from gui.theme import T
from gui.widgets import Card

logger = logging.getLogger("vmharness.snapshot_scheduler")


# ── Schedule Types ──────────────────────────────────────────────────────────────

class ScheduleType(str, Enum):
    """Types of snapshot schedules."""
    INTERVAL = "interval"
    ON_VM_STOP = "on_vm_stop"
    MANUAL = "manual"


# ── Schedule Data ───────────────────────────────────────────────────────────────

@dataclass
class SnapshotSchedule:
    """Represents a single snapshot schedule configuration."""
    name: str
    schedule_type: str  # "interval", "on_vm_stop", "manual"
    enabled: bool = True
    interval_minutes: int = 60  # For interval type
    retention_count: int = 5    # Keep last N snapshots
    disk_path: str = ""
    last_run: str = ""          # ISO timestamp
    last_snapshot: str = ""     # Name of last snapshot created
    total_created: int = 0
    id: str = ""                # Unique identifier

    def __post_init__(self):
        if not self.id:
            import uuid
            self.id = str(uuid.uuid4())[:8]


# ── Snapshot Backend ────────────────────────────────────────────────────────────

class SnapshotBackend:
    """Handles actual snapshot operations via qemu-img."""

    def __init__(self, disk_path: str):
        self._disk_path = disk_path

    def create(self, name: str) -> bool:
        """Create a snapshot with the given name."""
        try:
            result = subprocess.run(
                ["qemu-img", "snapshot", "-c", name, self._disk_path],
                capture_output=True, text=True, timeout=60
            )
            return result.returncode == 0
        except Exception as e:
            logger.error("Failed to create snapshot '%s': %s", name, e)
            return False

    def delete(self, name: str) -> bool:
        """Delete a snapshot by name."""
        try:
            result = subprocess.run(
                ["qemu-img", "snapshot", "-d", name, self._disk_path],
                capture_output=True, text=True, timeout=60
            )
            return result.returncode == 0
        except Exception as e:
            logger.error("Failed to delete snapshot '%s': %s", name, e)
            return False

    def list_snapshots(self) -> list:
        """List all snapshots for this disk."""
        try:
            result = subprocess.run(
                ["qemu-img", "snapshot", "-l", self._disk_path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return []
            snapshots = []
            for line in result.stdout.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 2 and parts[0].isdigit():
                    snapshots.append({"id": parts[0], "name": parts[1]})
            return snapshots
        except Exception as e:
            logger.error("Failed to list snapshots: %s", e)
            return []


# ── Snapshot Scheduler ──────────────────────────────────────────────────────────

class SnapshotScheduler(QObject):
    """Manages automated snapshot schedules with retention.

    Signals:
        snapshot_created(str, str) — (schedule_name, snapshot_name)
        snapshot_error(str, str) — (schedule_name, error_message)
        schedule_triggered(str) — schedule_id
        vm_stop_detected() — emitted when VM stop is detected
        schedules_changed() — emitted when schedule list changes
    """

    snapshot_created = pyqtSignal(str, str)
    snapshot_error = pyqtSignal(str, str)
    schedule_triggered = pyqtSignal(str)
    vm_stop_detected = pyqtSignal()
    schedules_changed = pyqtSignal()

    def __init__(self, disk_path: str = "", parent=None):
        super().__init__(parent)
        self._disk_path = disk_path
        self._schedules: List[SnapshotSchedule] = []
        self._backend = SnapshotBackend(disk_path) if disk_path else None
        self._persistence_path = self._get_persistence_path()

        # Main timer — fires every 60 seconds to check interval schedules
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_interval_schedules)
        self._timer.setInterval(60_000)  # 60 seconds

        # VM stop detection timer — polls every 10 seconds
        self._vm_poll_timer = QTimer(self)
        self._vm_poll_timer.timeout.connect(self._poll_vm_state)
        self._vm_poll_timer.setInterval(10_000)
        self._vm_was_running = False

        # Load persisted schedules
        self._load_schedules()

    @property
    def disk_path(self) -> str:
        return self._disk_path

    @disk_path.setter
    def disk_path(self, path: str):
        self._disk_path = path
        self._backend = SnapshotBackend(path) if path else None

    @property
    def schedules(self) -> List[SnapshotSchedule]:
        return list(self._schedules)

    # ── Persistence ────────────────────────────────────────────────────────────

    @staticmethod
    def _get_persistence_path() -> Path:
        """Get the path for schedule persistence."""
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        data_dir = base / "vmharness"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "snapshot_schedules.json"

    def _load_schedules(self):
        """Load schedules from JSON file."""
        if not self._persistence_path.exists():
            self._schedules = []
            return
        try:
            data = json.loads(self._persistence_path.read_text(encoding="utf-8"))
            self._schedules = [SnapshotSchedule(**s) for s in data.get("schedules", [])]
        except Exception as e:
            logger.error("Failed to load schedules: %s", e)
            self._schedules = []

    def _save_schedules(self):
        """Persist schedules to JSON file."""
        try:
            data = {
                "version": 1,
                "updated": datetime.now().isoformat(),
                "schedules": [asdict(s) for s in self._schedules],
            }
            self._persistence_path.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.error("Failed to save schedules: %s", e)

    # ── Schedule Management ───────────────────────────────────────────────────

    def add_schedule(self, schedule: SnapshotSchedule) -> str:
        """Add a new schedule. Returns the schedule ID."""
        if not schedule.disk_path:
            schedule.disk_path = self._disk_path
        self._schedules.append(schedule)
        self._save_schedules()
        self.schedules_changed.emit()
        return schedule.id

    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule by ID."""
        for i, s in enumerate(self._schedules):
            if s.id == schedule_id:
                self._schedules.pop(i)
                self._save_schedules()
                self.schedules_changed.emit()
                return True
        return False

    def update_schedule(self, schedule_id: str, **kwargs) -> bool:
        """Update schedule fields."""
        for s in self._schedules:
            if s.id == schedule_id:
                for key, value in kwargs.items():
                    if hasattr(s, key):
                        setattr(s, key, value)
                self._save_schedules()
                self.schedules_changed.emit()
                return True
        return False

    def get_schedule(self, schedule_id: str) -> Optional[SnapshotSchedule]:
        """Get a schedule by ID."""
        for s in self._schedules:
            if s.id == schedule_id:
                return s
        return None

    # ── Timer Control ─────────────────────────────────────────────────────────

    def start(self):
        """Start the scheduler timers."""
        if not self._timer.isActive():
            self._timer.start()
        if not self._vm_poll_timer.isActive():
            self._vm_poll_timer.start()

    def stop(self):
        """Stop the scheduler timers."""
        if self._timer.isActive():
            self._timer.stop()
        if self._vm_poll_timer.isActive():
            self._vm_poll_timer.stop()

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()

    # ── Interval Schedule Logic ───────────────────────────────────────────────

    def _check_interval_schedules(self):
        """Check if any interval schedules need to run."""
        now = datetime.now()
        for schedule in self._schedules:
            if not schedule.enabled:
                continue
            if schedule.schedule_type != ScheduleType.INTERVAL:
                continue

            if not schedule.last_run:
                self._execute_schedule(schedule)
                continue

            try:
                last = datetime.fromisoformat(schedule.last_run)
                elapsed = (now - last).total_seconds() / 60.0
                if elapsed >= schedule.interval_minutes:
                    self._execute_schedule(schedule)
            except (ValueError, TypeError):
                self._execute_schedule(schedule)

    # ── VM Stop Detection ────────────────────────────────────────────────────

    def _poll_vm_state(self):
        """Poll VM state to detect stops."""
        running = self._is_vm_running()
        if self._vm_was_running and not running:
            self.vm_stop_detected.emit()
            self._handle_vm_stop()
        self._vm_was_running = running

    def _is_vm_running(self) -> bool:
        """Check if the VM is currently running."""
        try:
            result = subprocess.run(
                ["qemu-img", "info", "--output=json", self._disk_path],
                capture_output=True, text=True, timeout=10
            )
            # If we can get info, the file exists; actual VM running
            # detection would need QMP. For now, use a file-based approach.
            return result.returncode == 0 and self._check_qemu_process()
        except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
            return False

    @staticmethod
    def _check_qemu_process() -> bool:
        """Check if a QEMU process is running."""
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq qemu-system-x86_64.exe"],
                    capture_output=True, text=True, timeout=5
                )
                return "qemu-system" in result.stdout
            else:
                result = subprocess.run(
                    ["pgrep", "-x", "qemu-system-x86_64"],
                    capture_output=True, text=True, timeout=5
                )
                return result.returncode == 0
        except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
            return False

    def _handle_vm_stop(self):
        """Handle VM stop event — trigger on_vm_stop schedules."""
        for schedule in self._schedules:
            if not schedule.enabled:
                continue
            if schedule.schedule_type == ScheduleType.ON_VM_STOP:
                self._execute_schedule(schedule)

    # ── Snapshot Execution ───────────────────────────────────────────────────

    def _execute_schedule(self, schedule: SnapshotSchedule):
        """Execute a schedule — create snapshot and enforce retention."""
        self.schedule_triggered.emit(schedule.id)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snap_name = f"sched_{schedule.name}_{timestamp}"

        backend = SnapshotBackend(schedule.disk_path) if schedule.disk_path else self._backend
        if not backend:
            self.snapshot_error.emit(schedule.name, "No disk path configured")
            return

        success = backend.create(snap_name)
        if success:
            schedule.last_run = datetime.now().isoformat()
            schedule.last_snapshot = snap_name
            schedule.total_created += 1
            self._save_schedules()
            self.snapshot_created.emit(schedule.name, snap_name)
            self._enforce_retention(schedule, backend)
            logger.info("Schedule '%s' created snapshot '%s'", schedule.name, snap_name)
        else:
            self.snapshot_error.emit(schedule.name, "Failed to create snapshot")
            logger.error("Schedule '%s' failed to create snapshot", schedule.name)

    def _enforce_retention(self, schedule: SnapshotSchedule, backend: SnapshotBackend):
        """Enforce retention policy — keep only last N snapshots."""
        snapshots = backend.list_snapshots()
        # Filter snapshots belonging to this schedule
        prefix = f"sched_{schedule.name}_"
        sched_snaps = [s for s in snapshots if s["name"].startswith(prefix)]
        sched_snaps.sort(key=lambda s: s["name"], reverse=True)

        if len(sched_snaps) > schedule.retention_count:
            to_delete = sched_snaps[schedule.retention_count:]
            for snap in to_delete:
                backend.delete(snap["name"])
                logger.info("Retention: deleted snapshot '%s'", snap["name"])

    def trigger_manual(self, schedule_id: str) -> bool:
        """Manually trigger a schedule."""
        schedule = self.get_schedule(schedule_id)
        if schedule:
            self._execute_schedule(schedule)
            return True
        return False

    # ── Settings Panel Integration ───────────────────────────────────────────

    def get_settings_widget(self) -> QWidget:
        """Create and return a settings widget for the settings panel."""
        return SnapshotSchedulerSettingsWidget(self)


# ── Settings Widget ────────────────────────────────────────────────────────────

class SnapshotSchedulerSettingsWidget(QWidget):
    """Widget for configuring snapshot schedules in the settings panel."""

    def __init__(self, scheduler: SnapshotScheduler, parent=None):
        super().__init__(parent)
        self._scheduler = scheduler
        self.setStyleSheet("background: " + T.BG_PRIMARY + ";")
        self._build_ui()
        self._scheduler.schedules_changed.connect(self._refresh_table)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Snapshot Scheduler")
        title.setStyleSheet(
            "color: " + T.TEXT_PRIMARY + "; font-size: 14px; font-weight: bold;"
        )
        hl.addWidget(title)
        hl.addStretch()

        self._status_label = QLabel(
            "● Running" if self._scheduler.is_running else "● Stopped"
        )
        self._status_label.setStyleSheet(
            "color: " + (T.SUCCESS if self._scheduler.is_running else T.ERROR) + ";"
            " font-size: 11px;"
        )
        hl.addWidget(self._status_label)
        layout.addWidget(header)

        # Schedule table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "Name", "Type", "Interval", "Retention", "Enabled", "Last Run"
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setStyleSheet(
            "QTableWidget {"
            " background: " + T.BG_SECONDARY + ";"
            " color: " + T.TEXT_PRIMARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + ";"
            " border-radius: 6px;"
            " font-size: 12px;"
            "}"
            "QHeaderView::section {"
            " background: " + T.BG_TERTIARY + ";"
            " color: " + T.TEXT_SECONDARY + ";"
            " padding: 6px;"
            " border: none;"
            " font-size: 11px;"
            "}"
        )
        self._table.setMinimumHeight(150)
        layout.addWidget(self._table)

        # Buttons
        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)

        add_btn = QPushButton("Add Schedule")
        add_btn.setFixedSize(110, 32)
        add_btn.setStyleSheet(
            "QPushButton {"
            " background: " + T.SUCCESS + ";"
            " border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600;"
            "}"
            "QPushButton:hover { background: #16a34a; }"
        )
        add_btn.clicked.connect(self._add_schedule)
        bl.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setFixedSize(80, 32)
        remove_btn.setStyleSheet(
            "QPushButton {"
            " background: " + T.ERROR + ";"
            " border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600;"
            "}"
            "QPushButton:hover { background: #dc2626; }"
        )
        remove_btn.clicked.connect(self._remove_schedule)
        bl.addWidget(remove_btn)

        trigger_btn = QPushButton("Trigger Now")
        trigger_btn.setFixedSize(90, 32)
        trigger_btn.setStyleSheet(
            "QPushButton {"
            " background: " + T.BRAND + ";"
            " border: none; border-radius: 6px;"
            " color: white; font-size: 12px; font-weight: 600;"
            "}"
            "QPushButton:hover { background: " + T.BRAND_HOVER + "; }"
        )
        trigger_btn.clicked.connect(self._trigger_schedule)
        bl.addWidget(trigger_btn)

        bl.addStretch()

        self._toggle_btn = QPushButton(
            "Stop Scheduler" if self._scheduler.is_running else "Start Scheduler"
        )
        self._toggle_btn.setFixedSize(110, 32)
        self._toggle_btn.setStyleSheet(
            "QPushButton {"
            " background: " + T.BG_SECONDARY + ";"
            " border: 1px solid " + T.BG_TERTIARY + ";"
            " border-radius: 6px;"
            " color: " + T.TEXT_SECONDARY + ";"
            " font-size: 12px;"
            "}"
            "QPushButton:hover { background: " + T.BG_TERTIARY + "; }"
        )
        self._toggle_btn.clicked.connect(self._toggle_scheduler)
        bl.addWidget(self._toggle_btn)

        layout.addWidget(btn_row)
        self._refresh_table()

    def _refresh_table(self):
        """Refresh the schedule table."""
        schedules = self._scheduler.schedules
        self._table.setRowCount(len(schedules))
        for i, s in enumerate(schedules):
            self._table.setItem(i, 0, QTableWidgetItem(s.name))
            self._table.setItem(i, 1, QTableWidgetItem(s.schedule_type))
            interval_text = f"{s.interval_minutes} min" if s.schedule_type == "interval" else "—"
            self._table.setItem(i, 2, QTableWidgetItem(interval_text))
            self._table.setItem(i, 3, QTableWidgetItem(str(s.retention_count)))
            enabled_text = "Yes" if s.enabled else "No"
            self._table.setItem(i, 4, QTableWidgetItem(enabled_text))
            last_run = s.last_run[:19] if s.last_run else "Never"
            self._table.setItem(i, 5, QTableWidgetItem(last_run))

    def _add_schedule(self):
        """Add a new schedule via dialog."""
        name, ok = QInputDialog.getText(self, "New Schedule", "Schedule name:")
        if not ok or not name.strip():
            return

        type_combo = QComboBox()
        type_combo.addItems(["interval", "on_vm_stop", "manual"])
        # Simple approach: use input dialog
        items = ["interval", "on_vm_stop", "manual"]
        schedule_type, ok = QInputDialog.getItem(
            self, "Schedule Type", "Type:", items, 0, False
        )
        if not ok:
            return

        interval = 60
        if schedule_type == "interval":
            interval, ok = QInputDialog.getInt(
                self, "Interval", "Interval (minutes):", 60, 1, 10080
            )
            if not ok:
                return

        retention, ok = QInputDialog.getInt(
            self, "Retention", "Keep last N snapshots:", 5, 1, 100
        )
        if not ok:
            return

        schedule = SnapshotSchedule(
            name=name.strip(),
            schedule_type=schedule_type,
            interval_minutes=interval,
            retention_count=retention,
            disk_path=self._scheduler.disk_path,
        )
        self._scheduler.add_schedule(schedule)

    def _remove_schedule(self):
        """Remove selected schedule."""
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Select a schedule first")
            return
        schedules = self._scheduler.schedules
        if row < len(schedules):
            reply = QMessageBox.question(
                self, "Confirm",
                f"Remove schedule '{schedules[row].name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._scheduler.remove_schedule(schedules[row].id)

    def _trigger_schedule(self):
        """Manually trigger selected schedule."""
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Select a schedule first")
            return
        schedules = self._scheduler.schedules
        if row < len(schedules):
            self._scheduler.trigger_manual(schedules[row].id)

    def _toggle_scheduler(self):
        """Start/stop the scheduler."""
        if self._scheduler.is_running:
            self._scheduler.stop()
            self._toggle_btn.setText("Start Scheduler")
            self._status_label.setText("● Stopped")
            self._status_label.setStyleSheet("color: " + T.ERROR + "; font-size: 11px;")
        else:
            self._scheduler.start()
            self._toggle_btn.setText("Stop Scheduler")
            self._status_label.setText("● Running")
            self._status_label.setStyleSheet("color: " + T.SUCCESS + "; font-size: 11px;")


# ── Factory ────────────────────────────────────────────────────────────────────

def create_snapshot_scheduler(disk_path: str = "") -> SnapshotScheduler:
    """Create and return a SnapshotScheduler instance."""
    return Scheduler(disk_path=disk_path)


# Alias for backward compat
Scheduler = SnapshotScheduler
