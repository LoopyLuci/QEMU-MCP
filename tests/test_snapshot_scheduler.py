"""Tests for SnapshotScheduler — persistence, schedule logic, retention, signals."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("GUI_MASTER_PASSWORD", "test-master-password")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temp data directory for persistence."""
    data_dir = tmp_path / "vmharness"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def sample_disk(tmp_path):
    """Create a dummy disk file path for testing."""
    disk = tmp_path / "test.qcow2"
    disk.touch()
    return str(disk)


@pytest.fixture
def scheduler(tmp_data_dir, sample_disk, qtbot):
    """Create a SnapshotScheduler with mocked persistence path."""
    from gui.snapshot_scheduler import SnapshotScheduler

    s = SnapshotScheduler(disk_path=sample_disk)
    s._persistence_path = tmp_data_dir / "snapshot_schedules.json"
    s._save_schedules  # Ensure path is set
    return s


# ── Schedule Type Tests ────────────────────────────────────────────────────────


class TestScheduleType:
    def test_enum_values(self):
        from gui.snapshot_scheduler import ScheduleType

        assert ScheduleType.INTERVAL == "interval"
        assert ScheduleType.ON_VM_STOP == "on_vm_stop"
        assert ScheduleType.MANUAL == "manual"

    def test_enum_membership(self):
        from gui.snapshot_scheduler import ScheduleType

        assert ScheduleType("interval") in ScheduleType
        assert ScheduleType("on_vm_stop") in ScheduleType
        assert ScheduleType("manual") in ScheduleType


# ── SnapshotSchedule Dataclass Tests ──────────────────────────────────────────


class TestSnapshotSchedule:
    def test_creation_with_defaults(self):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(name="test", schedule_type="interval")
        assert s.name == "test"
        assert s.schedule_type == "interval"
        assert s.enabled is True
        assert s.interval_minutes == 60
        assert s.retention_count == 5
        assert s.id != ""  # Auto-generated

    def test_creation_with_custom_values(self):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(
            name="custom",
            schedule_type="on_vm_stop",
            interval_minutes=120,
            retention_count=10,
            disk_path="/path/to/disk.qcow2",
        )
        assert s.name == "custom"
        assert s.retention_count == 10
        assert s.disk_path == "/path/to/disk.qcow2"

    def test_uuid_generation(self):
        from gui.snapshot_scheduler import SnapshotSchedule

        s1 = SnapshotSchedule(name="a", schedule_type="interval")
        s2 = SnapshotSchedule(name="b", schedule_type="interval")
        assert s1.id != s2.id
        assert len(s1.id) == 8


# ── SnapshotBackend Tests ──────────────────────────────────────────────────────


class TestSnapshotBackend:
    def test_init(self):
        from gui.snapshot_scheduler import SnapshotBackend

        b = SnapshotBackend("/path/to/disk.qcow2")
        assert b._disk_path == "/path/to/disk.qcow2"

    @patch("subprocess.run")
    def test_create_success(self, mock_run):
        from gui.snapshot_scheduler import SnapshotBackend

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        b = SnapshotBackend("/path/to/disk.qcow2")
        assert b.create("test_snap") is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_create_failure(self, mock_run):
        from gui.snapshot_scheduler import SnapshotBackend

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        b = SnapshotBackend("/path/to/disk.qcow2")
        assert b.create("test_snap") is False

    @patch("subprocess.run")
    def test_delete_success(self, mock_run):
        from gui.snapshot_scheduler import SnapshotBackend

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        b = SnapshotBackend("/path/to/disk.qcow2")
        assert b.delete("test_snap") is True

    @patch("subprocess.run")
    def test_list_snapshots(self, mock_run):
        from gui.snapshot_scheduler import SnapshotBackend

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="1 snap1 1024K\n2 snap2 2048K\n",
            stderr="",
        )
        b = SnapshotBackend("/path/to/disk.qcow2")
        snaps = b.list_snapshots()
        assert len(snaps) == 2
        assert snaps[0]["name"] == "snap1"

    @patch("subprocess.run")
    def test_list_snapshots_failure(self, mock_run):
        from gui.snapshot_scheduler import SnapshotBackend

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="err")
        b = SnapshotBackend("/path/to/disk.qcow2")
        assert b.list_snapshots() == []


# ── SnapshotScheduler Core Tests ───────────────────────────────────────────────


class TestSnapshotScheduler:
    def test_init(self, sample_disk):
        from gui.snapshot_scheduler import SnapshotScheduler

        s = SnapshotScheduler(disk_path=sample_disk)
        assert s.disk_path == sample_disk
        assert s._schedules == []
        assert s._backend is not None

    def test_init_empty_path(self):
        from gui.snapshot_scheduler import SnapshotScheduler

        s = SnapshotScheduler()
        assert s.disk_path == ""
        assert s._backend is None

    def test_disk_path_setter(self, sample_disk):
        from gui.snapshot_scheduler import SnapshotScheduler

        s = SnapshotScheduler()
        s.disk_path = sample_disk
        assert s.disk_path == sample_disk
        assert s._backend is not None

    @patch("gui.snapshot_scheduler.SnapshotScheduler._get_persistence_path")
    def test_persistence_path_generation(self, mock_path, tmp_data_dir):
        from gui.snapshot_scheduler import SnapshotScheduler

        mock_path.return_value = tmp_data_dir / "snapshot_schedules.json"
        s = SnapshotScheduler(disk_path="/tmp/test.qcow2")
        assert s._persistence_path == tmp_data_dir / "snapshot_schedules.json"


# ── Schedule Management Tests ──────────────────────────────────────────────────


class TestScheduleManagement:
    def test_add_schedule(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(name="test", schedule_type="interval")
        sid = scheduler.add_schedule(s)
        assert sid == s.id
        assert len(scheduler.schedules) == 1
        assert scheduler.schedules[0].name == "test"

    def test_add_schedule_with_empty_disk_path(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(name="test", schedule_type="interval", disk_path="")
        scheduler.add_schedule(s)
        assert scheduler.schedules[0].disk_path == scheduler.disk_path

    def test_remove_schedule(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(name="test", schedule_type="interval")
        sid = scheduler.add_schedule(s)
        assert scheduler.remove_schedule(sid) is True
        assert len(scheduler.schedules) == 0

    def test_remove_nonexistent_schedule(self, scheduler):
        assert scheduler.remove_schedule("nonexistent") is False

    def test_update_schedule(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(name="test", schedule_type="interval")
        sid = scheduler.add_schedule(s)
        assert scheduler.update_schedule(sid, name="updated", retention_count=10) is True
        assert scheduler.schedules[0].name == "updated"
        assert scheduler.schedules[0].retention_count == 10

    def test_update_nonexistent_schedule(self, scheduler):
        assert scheduler.update_schedule("nope", name="x") is False

    def test_get_schedule(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(name="test", schedule_type="interval")
        sid = scheduler.add_schedule(s)
        result = scheduler.get_schedule(sid)
        assert result is not None
        assert result.name == "test"

    def test_get_schedule_nonexistent(self, scheduler):
        assert scheduler.get_schedule("nope") is None


# ── JSON Persistence Tests ──────────────────────────────────────────────────────


class TestPersistence:
    def test_save_schedules(self, scheduler, tmp_data_dir):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(name="persist_test", schedule_type="interval")
        scheduler.add_schedule(s)

        # Verify file was created
        path = tmp_data_dir / "snapshot_schedules.json"
        assert path.exists()

        # Verify contents
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "version" in data
        assert "updated" in data
        assert "schedules" in data
        assert len(data["schedules"]) == 1
        assert data["schedules"][0]["name"] == "persist_test"

    def test_load_schedules(self, tmp_data_dir, sample_disk):
        from gui.snapshot_scheduler import SnapshotScheduler, SnapshotSchedule

        # Pre-write a schedule file
        path = tmp_data_dir / "snapshot_schedules.json"
        data = {
            "version": 1,
            "updated": "2024-01-01T00:00:00",
            "schedules": [
                {
                    "name": "loaded",
                    "schedule_type": "on_vm_stop",
                    "enabled": True,
                    "interval_minutes": 30,
                    "retention_count": 3,
                    "disk_path": sample_disk,
                    "last_run": "",
                    "last_snapshot": "",
                    "total_created": 0,
                    "id": "abc12345",
                }
            ],
        }
        path.write_text(json.dumps(data), encoding="utf-8")

        # Create scheduler with the same persistence path
        s = SnapshotScheduler(disk_path=sample_disk)
        s._persistence_path = path
        s._load_schedules()

        assert len(s.schedules) == 1
        assert s.schedules[0].name == "loaded"
        assert s.schedules[0].schedule_type == "on_vm_stop"
        assert s.schedules[0].retention_count == 3

    def test_load_empty_file(self, scheduler, tmp_data_dir):
        # No file exists — should start with empty list
        scheduler._load_schedules()
        assert scheduler.schedules == []

    def test_load_corrupt_file(self, tmp_data_dir, sample_disk):
        from gui.snapshot_scheduler import SnapshotScheduler

        path = tmp_data_dir / "snapshot_schedules.json"
        path.write_text("not valid json {{{", encoding="utf-8")

        s = SnapshotScheduler(disk_path=sample_disk)
        s._persistence_path = path
        s._load_schedules()
        assert s.schedules == []


# ── Timer Control Tests ─────────────────────────────────────────────────────────


class TestTimerControl:
    def test_start_stop(self, scheduler):
        scheduler.start()
        assert scheduler.is_running is True
        scheduler.stop()
        assert scheduler.is_running is False

    def test_start_idempotent(self, scheduler):
        scheduler.start()
        scheduler.start()  # Should not crash
        assert scheduler.is_running is True


# ── Interval Schedule Logic Tests ──────────────────────────────────────────────


class TestIntervalSchedule:
    def test_check_triggers_new_schedule(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(
            name="new_interval",
            schedule_type="interval",
            interval_minutes=60,
            retention_count=3,
        )
        scheduler.add_schedule(s)

        # Mock SnapshotBackend.create at class level since _execute_schedule
        # creates a new backend instance
        with patch("gui.snapshot_scheduler.SnapshotBackend.create", return_value=True):
            scheduler._check_interval_schedules()

        # Should have updated last_run
        assert scheduler.schedules[0].last_run != ""

    def test_check_skips_disabled(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(
            name="disabled",
            schedule_type="interval",
            enabled=False,
        )
        scheduler.add_schedule(s)

        with patch.object(scheduler._backend, "create") as mock_create:
            scheduler._check_interval_schedules()
            mock_create.assert_not_called()

    def test_check_skips_non_interval(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(
            name="manual_sched",
            schedule_type="manual",
        )
        scheduler.add_schedule(s)

        with patch.object(scheduler._backend, "create") as mock_create:
            scheduler._check_interval_schedules()
            mock_create.assert_not_called()


# ── VM Stop Detection Tests ─────────────────────────────────────────────────────


class TestVMStopDetection:
    def test_handle_vm_stop_triggers_schedules(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(
            name="stop_triggered",
            schedule_type="on_vm_stop",
            retention_count=3,
        )
        scheduler.add_schedule(s)

        with patch("gui.snapshot_scheduler.SnapshotBackend.create", return_value=True):
            scheduler._handle_vm_stop()

        assert scheduler.schedules[0].last_run != ""

    def test_vm_stop_skips_disabled(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(
            name="disabled_stop",
            schedule_type="on_vm_stop",
            enabled=False,
        )
        scheduler.add_schedule(s)

        with patch.object(scheduler._backend, "create") as mock_create:
            scheduler._handle_vm_stop()
            mock_create.assert_not_called()


# ── Retention Tests ─────────────────────────────────────────────────────────────


class TestRetention:
    def test_enforce_retention_keeps_n(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule, SnapshotBackend

        s = SnapshotSchedule(
            name="ret_test",
            schedule_type="interval",
            retention_count=2,
        )
        scheduler.add_schedule(s)

        # Mock backend with 4 snapshots (should delete 2)
        mock_backend = MagicMock(spec=SnapshotBackend)
        mock_backend.list_snapshots.return_value = [
            {"id": "4", "name": "sched_ret_test_20240101_120000"},
            {"id": "3", "name": "sched_ret_test_20240101_110000"},
            {"id": "2", "name": "sched_ret_test_20240101_100000"},
            {"id": "1", "name": "sched_ret_test_20240101_090000"},
        ]

        scheduler._enforce_retention(s, mock_backend)
        assert mock_backend.delete.call_count == 2

    def test_enforce_retention_within_limit(self, scheduler):
        from gui.snapshot_scheduler import SnapshotSchedule, SnapshotBackend

        s = SnapshotSchedule(
            name="ret_ok",
            schedule_type="interval",
            retention_count=5,
        )
        scheduler.add_schedule(s)

        mock_backend = MagicMock(spec=SnapshotBackend)
        mock_backend.list_snapshots.return_value = [
            {"id": "2", "name": "sched_ret_ok_20240101_120000"},
            {"id": "1", "name": "sched_ret_ok_20240101_110000"},
        ]

        scheduler._enforce_retention(s, mock_backend)
        mock_backend.delete.assert_not_called()


# ── Signal Tests ────────────────────────────────────────────────────────────────


class TestSignals:
    def test_snapshot_created_signal(self, scheduler, qtbot):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(name="sig_test", schedule_type="interval")
        scheduler.add_schedule(s)

        with qtbot.waitSignal(scheduler.snapshot_created, timeout=1000):
            with patch("gui.snapshot_scheduler.SnapshotBackend.create", return_value=True):
                scheduler._execute_schedule(s)

    def test_schedule_triggered_signal(self, scheduler, qtbot):
        from gui.snapshot_scheduler import SnapshotSchedule

        s = SnapshotSchedule(name="trigger_test", schedule_type="interval")
        scheduler.add_schedule(s)

        with qtbot.waitSignal(scheduler.schedule_triggered, timeout=1000):
            with patch.object(scheduler._backend, "create", return_value=True):
                scheduler._execute_schedule(s)

    def test_schedules_changed_signal_on_add(self, scheduler, qtbot):
        from gui.snapshot_scheduler import SnapshotSchedule

        with qtbot.waitSignal(scheduler.schedules_changed, timeout=1000):
            s = SnapshotSchedule(name="add_sig", schedule_type="interval")
            scheduler.add_schedule(s)


# ── Settings Widget Tests ───────────────────────────────────────────────────────


class TestSettingsWidget:
    def test_widget_creation(self, scheduler, qtbot):
        from gui.snapshot_scheduler import SnapshotSchedulerSettingsWidget

        w = SnapshotSchedulerSettingsWidget(scheduler)
        qtbot.addWidget(w)
        assert w is not None
        assert w._scheduler is scheduler

    def test_widget_has_table(self, scheduler, qtbot):
        from gui.snapshot_scheduler import SnapshotSchedulerSettingsWidget

        w = SnapshotSchedulerSettingsWidget(scheduler)
        qtbot.addWidget(w)
        assert w._table is not None
        assert w._table.columnCount() == 6


# ── Factory Test ────────────────────────────────────────────────────────────────


class TestFactory:
    def test_create_snapshot_scheduler(self):
        from gui.snapshot_scheduler import create_snapshot_scheduler, SnapshotScheduler

        s = create_snapshot_scheduler(disk_path="/tmp/test.qcow2")
        assert isinstance(s, SnapshotScheduler)
        assert s.disk_path == "/tmp/test.qcow2"

    def test_create_with_default_path(self):
        from gui.snapshot_scheduler import create_snapshot_scheduler, SnapshotScheduler

        s = create_snapshot_scheduler()
        assert isinstance(s, SnapshotScheduler)
