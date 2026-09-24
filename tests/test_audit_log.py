"""Tests for the audit logging system."""

from __future__ import annotations

import csv
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

# Ensure the project root is on the path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gui.audit_log import AuditLogger, AuditLogPanel, audit_log, DEFAULT_EVENT_TYPES, MAX_ENTRIES_PER_TYPE


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database path."""
    return str(tmp_path / "test_audit.db")


@pytest.fixture
def logger(tmp_db):
    """Create a test logger with a temporary database."""
    return AuditLogger(db_path=tmp_db, max_entries_per_type=100)


@pytest.fixture
def logger_small_rotation(tmp_path):
    """Create a logger with a very small rotation limit for testing."""
    return AuditLogger(
        db_path=str(tmp_path / "small_audit.db"),
        max_entries_per_type=5,
    )


@pytest.fixture
def logger_no_rotation(tmp_path):
    """Create a logger with no rotation for thread safety tests."""
    return AuditLogger(
        db_path=str(tmp_path / "no_rotation_audit.db"),
        max_entries_per_type=1_000_000,
    )


# ── Initialization Tests ────────────────────────────────────────────────────────

class TestAuditLoggerInit:
    """Tests for AuditLogger initialization."""

    def test_default_db_path(self):
        """Default db path should be in .audit directory."""
        logger = AuditLogger()
        assert logger._db_path.name == "audit.db"
        assert logger._db_path.parent.name == ".audit"
        logger.close()

    def test_custom_db_path(self, tmp_db):
        """Custom db path should be used."""
        logger = AuditLogger(db_path=tmp_db)
        assert str(logger._db_path) == tmp_db
        logger.close()

    def test_creates_directory(self, tmp_path):
        """Logger should create parent directory if it doesn't exist."""
        db_path = tmp_path / "subdir" / "deep" / "audit.db"
        logger = AuditLogger(db_path=str(db_path))
        assert db_path.parent.exists()
        logger.close()

    def test_creates_table(self, tmp_db):
        """Logger should create the audit_log table."""
        logger = AuditLogger(db_path=tmp_db)
        with sqlite3.connect(tmp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
            )
            assert cursor.fetchone() is not None
        logger.close()

    def test_creates_indexes(self, tmp_db):
        """Logger should create indexes on event_type, timestamp, user."""
        logger = AuditLogger(db_path=tmp_db)
        with sqlite3.connect(tmp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_audit_%'"
            )
            indexes = {row[0] for row in cursor.fetchall()}
            assert "idx_audit_event_type" in indexes
            assert "idx_audit_timestamp" in indexes
            assert "idx_audit_user" in indexes
        logger.close()

    def test_default_max_entries(self):
        """Default max entries should be 10,000."""
        logger = AuditLogger()
        assert logger._max_entries_per_type == MAX_ENTRIES_PER_TYPE
        logger.close()


# ── Logging Tests ───────────────────────────────────────────────────────────────

class TestAuditLoggerLog:
    """Tests for logging events."""

    def test_log_basic(self, logger):
        """Basic logging should succeed."""
        entry = logger.log("login", user="admin", details="Test login")
        assert entry["id"] is not None
        assert entry["event_type"] == "login"
        assert entry["user"] == "admin"
        assert entry["details"] == "Test login"
        assert entry["success"] is True
        assert entry["timestamp"].endswith("Z")

    def test_log_defaults(self, logger):
        """Default values should be system/127.0.0.1/True."""
        entry = logger.log("test_event")
        assert entry["user"] == "system"
        assert entry["source_ip"] == "127.0.0.1"
        assert entry["success"] is True
        assert entry["details"] == ""

    def test_log_failure(self, logger):
        """Logging a failed event should work."""
        entry = logger.log("login", user="admin", success=False)
        assert entry["success"] is False

    def test_log_with_ip(self, logger):
        """Logging with a source IP should work."""
        entry = logger.log("login", source_ip="192.168.1.100")
        assert entry["source_ip"] == "192.168.1.100"

    def test_log_unique_ids(self, logger):
        """Each log entry should have a unique ID."""
        entry1 = logger.log("event1")
        entry2 = logger.log("event2")
        assert entry1["id"] != entry2["id"]

    def test_log_sequential_ids(self, logger):
        """IDs should be sequential."""
        entry1 = logger.log("event1")
        entry2 = logger.log("event2")
        assert entry2["id"] == entry1["id"] + 1

    def test_log_timestamp_format(self, logger):
        """Timestamp should be valid ISO format."""
        entry = logger.log("test")
        from datetime import datetime
        ts = entry["timestamp"].rstrip("Z")
        # Should not raise
        datetime.fromisoformat(ts)

    def test_log_all_default_types(self, logger):
        """All default event types should be loggable."""
        for event_type in DEFAULT_EVENT_TYPES:
            entry = logger.log(event_type)
            assert entry["event_type"] == event_type


# ── Query Tests ─────────────────────────────────────────────────────────────────

class TestAuditLoggerQuery:
    """Tests for querying audit log entries."""

    def test_query_all(self, logger):
        """Query with no filters should return all entries."""
        logger.log("event1")
        logger.log("event2")
        entries = logger.query()
        assert len(entries) == 2

    def test_query_by_event_type(self, logger):
        """Query by event type should filter correctly."""
        logger.log("login")
        logger.log("login")
        logger.log("logout")
        entries = logger.query(event_type="login")
        assert len(entries) == 2
        assert all(e["event_type"] == "login" for e in entries)

    def test_query_by_user(self, logger):
        """Query by user should filter correctly."""
        logger.log("event", user="alice")
        logger.log("event", user="bob")
        entries = logger.query(user="alice")
        assert len(entries) == 1
        assert entries[0]["user"] == "alice"

    def test_query_by_user_partial(self, logger):
        """Query by user should support partial matches."""
        logger.log("event", user="alice_admin")
        logger.log("event", user="bob")
        entries = logger.query(user="alice")
        assert len(entries) == 1

    def test_query_by_source_ip(self, logger):
        """Query by source IP should filter correctly."""
        logger.log("event", source_ip="192.168.1.1")
        logger.log("event", source_ip="10.0.0.1")
        entries = logger.query(source_ip="192.168")
        assert len(entries) == 1
        assert entries[0]["source_ip"] == "192.168.1.1"

    def test_query_by_success(self, logger):
        """Query by success status should filter correctly."""
        logger.log("event", success=True)
        logger.log("event", success=True)
        logger.log("event", success=False)
        entries = logger.query(success=True)
        assert len(entries) == 2
        assert all(e["success"] for e in entries)

    def test_query_by_search(self, logger):
        """Query by search term should match details."""
        logger.log("event", details="User logged in via SSH")
        logger.log("event", details="VM started")
        entries = logger.query(search="SSH")
        assert len(entries) == 1

    def test_query_by_date_range(self, logger):
        """Query by date range should filter correctly."""
        logger.log("event")
        entries = logger.query(
            start_date="2000-01-01T00:00:00Z",
            end_date="2099-12-31T23:59:59Z",
        )
        assert len(entries) == 1

    def test_query_ordered_by_id_desc(self, logger):
        """Query results should be ordered by ID descending."""
        logger.log("event1")
        logger.log("event2")
        logger.log("event3")
        entries = logger.query()
        assert entries[0]["id"] > entries[1]["id"] > entries[2]["id"]

    def test_query_limit(self, logger):
        """Query limit should work."""
        for i in range(10):
            logger.log("event")
        entries = logger.query(limit=5)
        assert len(entries) == 5

    def test_query_offset(self, logger):
        """Query offset should work."""
        for i in range(10):
            logger.log("event")
        entries = logger.query(limit=5, offset=5)
        assert len(entries) == 5

    def test_query_combined_filters(self, logger):
        """Multiple filters should work together."""
        logger.log("login", user="alice", success=True)
        logger.log("login", user="bob", success=False)
        logger.log("logout", user="alice", success=True)
        entries = logger.query(event_type="login", user="alice")
        assert len(entries) == 1
        assert entries[0]["user"] == "alice"
        assert entries[0]["event_type"] == "login"

    def test_query_empty_result(self, logger):
        """Query with no matches should return empty list."""
        logger.log("event")
        entries = logger.query(event_type="nonexistent")
        assert entries == []


# ── Count Tests ─────────────────────────────────────────────────────────────────

class TestAuditLoggerCount:
    """Tests for counting entries."""

    def test_count_all(self, logger):
        """Count with no filters should return total."""
        logger.log("event1")
        logger.log("event2")
        assert logger.count() == 2

    def test_count_by_type(self, logger):
        """Count by type should filter correctly."""
        logger.log("login")
        logger.log("login")
        logger.log("logout")
        assert logger.count(event_type="login") == 2

    def test_count_by_user(self, logger):
        """Count by user should filter correctly."""
        logger.log("event", user="alice")
        logger.log("event", user="bob")
        assert logger.count(user="alice") == 1

    def test_count_by_success(self, logger):
        """Count by success should filter correctly."""
        logger.log("event", success=True)
        logger.log("event", success=False)
        assert logger.count(success=True) == 1


# ── Metadata Tests ──────────────────────────────────────────────────────────────

class TestAuditLoggerMetadata:
    """Tests for metadata methods."""

    def test_get_event_types(self, logger):
        """Get event types should return distinct types."""
        logger.log("login")
        logger.log("logout")
        logger.log("login")
        types = logger.get_event_types()
        assert set(types) == {"login", "logout"}

    def test_get_event_types_empty(self, logger):
        """Get event types should return empty list when no entries."""
        assert logger.get_event_types() == []

    def test_get_users(self, logger):
        """Get users should return distinct users."""
        logger.log("event", user="alice")
        logger.log("event", user="bob")
        logger.log("event", user="alice")
        users = logger.get_users()
        assert set(users) == {"alice", "bob"}

    def test_get_users_empty(self, logger):
        """Get users should return empty list when no entries."""
        assert logger.get_users() == []


# ── Rotation Tests ──────────────────────────────────────────────────────────────

class TestAuditLoggerRotation:
    """Tests for log rotation."""

    def test_rotation_triggers(self, logger_small_rotation):
        """Rotation should trigger when limit is exceeded."""
        for i in range(6):
            logger_small_rotation.log("test_event")
        # Should have 5 entries (1 rotated out)
        assert logger_small_rotation.count(event_type="test_event") == 5

    def test_rotation_removes_oldest(self, logger_small_rotation):
        """Rotation should remove the oldest entries first."""
        for i in range(6):
            logger_small_rotation.log("test_event", details=f"event_{i}")
        entries = logger_small_rotation.query(event_type="test_event")
        # Oldest (event_0) should be removed
        details = [e["details"] for e in entries]
        assert "event_0" not in details
        assert "event_1" in details

    def test_rotation_per_type(self, logger_small_rotation):
        """Rotation should be per-event-type."""
        for i in range(6):
            logger_small_rotation.log("type_a")
        for i in range(3):
            logger_small_rotation.log("type_b")
        assert logger_small_rotation.count(event_type="type_a") == 5
        assert logger_small_rotation.count(event_type="type_b") == 3

    def test_rotation_preserves_other_types(self, logger_small_rotation):
        """Rotation of one type should not affect other types."""
        for i in range(10):
            logger_small_rotation.log("type_a")
        logger_small_rotation.log("type_b")
        assert logger_small_rotation.count(event_type="type_b") == 1

    def test_no_rotation_under_limit(self, logger_small_rotation):
        """No rotation should occur when under the limit."""
        for i in range(5):
            logger_small_rotation.log("test_event")
        assert logger_small_rotation.count(event_type="test_event") == 5


# ── CSV Export Tests ────────────────────────────────────────────────────────────

class TestAuditLoggerExportCSV:
    """Tests for CSV export."""

    def test_export_basic(self, logger, tmp_path):
        """Basic export should work."""
        logger.log("login", user="admin", details="Login")
        filepath = tmp_path / "export.csv"
        count = logger.export_csv(filepath)
        assert count == 1
        assert filepath.exists()

    def test_export_format(self, logger, tmp_path):
        """Exported CSV should have correct format."""
        logger.log("login", user="admin", details="Test login", source_ip="10.0.0.1", success=True)
        filepath = tmp_path / "export.csv"
        logger.export_csv(filepath)

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["id", "timestamp", "event_type", "user", "details", "source_ip", "success"]
            row = next(reader)
            assert row[2] == "login"
            assert row[3] == "admin"
            assert row[4] == "Test login"
            assert row[5] == "10.0.0.1"
            assert row[6] == "True"

    def test_export_empty(self, logger, tmp_path):
        """Export with no entries should create file with header only."""
        filepath = tmp_path / "export.csv"
        count = logger.export_csv(filepath)
        assert count == 0
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["id", "timestamp", "event_type", "user", "details", "source_ip", "success"]

    def test_export_with_filter(self, logger, tmp_path):
        """Export should respect event_type filter."""
        logger.log("login", user="alice")
        logger.log("logout", user="bob")
        filepath = tmp_path / "export.csv"
        count = logger.export_csv(filepath, event_type="login")
        assert count == 1

    def test_export_creates_directory(self, logger, tmp_path):
        """Export should create parent directories."""
        filepath = tmp_path / "subdir" / "deep" / "export.csv"
        logger.log("event")
        logger.export_csv(filepath)
        assert filepath.exists()


# ── Clear Tests ─────────────────────────────────────────────────────────────────

class TestAuditLoggerClear:
    """Tests for clearing entries."""

    def test_clear_all(self, logger):
        """Clear without filter should remove all entries."""
        logger.log("event1")
        logger.log("event2")
        deleted = logger.clear()
        assert deleted == 2
        assert logger.count() == 0

    def test_clear_by_type(self, logger):
        """Clear with type filter should only remove matching entries."""
        logger.log("login")
        logger.log("login")
        logger.log("logout")
        deleted = logger.clear(event_type="login")
        assert deleted == 2
        assert logger.count() == 1

    def test_clear_empty(self, logger):
        """Clear on empty log should return 0."""
        deleted = logger.clear()
        assert deleted == 0

    def test_clear_specific_type_only(self, logger):
        """Clear should not affect other types."""
        logger.log("type_a")
        logger.log("type_b")
        logger.clear(event_type="type_a")
        assert logger.count(event_type="type_b") == 1


# ── Singleton Tests ─────────────────────────────────────────────────────────────

class TestGlobalSingleton:
    """Tests for the global audit_log singleton."""

    def test_singleton_exists(self):
        """The global singleton should be an AuditLogger."""
        assert isinstance(audit_log, AuditLogger)

    def test_singleton_log(self):
        """Singleton should be able to log. Idempotent across runs."""
        entry = audit_log.log("test_singleton", details="test")
        assert entry["event_type"] == "test_singleton"

    def test_singleton_query(self):
        """Singleton should be able to query."""
        audit_log.log("test_query", details="query_test")
        entries = audit_log.query(event_type="test_query")
        assert len(entries) >= 1


# ── Signal Tests ────────────────────────────────────────────────────────────────

class TestAuditLoggerSignals:
    """Tests for PyQt5 signals."""

    def test_entry_logged_signal(self, logger):
        """entry_logged signal should be emitted on log."""
        received = []
        logger.entry_logged.connect(lambda entry: received.append(entry))
        logger.log("test_signal")
        assert len(received) == 1
        assert received[0]["event_type"] == "test_signal"

    def test_entry_logged_signal_data(self, logger):
        """entry_logged signal should emit correct data."""
        received = []
        logger.entry_logged.connect(lambda entry: received.append(entry))
        logger.log("test", user="alice", details="test details")
        assert received[0]["user"] == "alice"
        assert received[0]["details"] == "test details"


# ── Thread Safety Tests ────────────────────────────────────────────────────────

class TestAuditLoggerThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_logging(self, logger_no_rotation):
        """Concurrent logging from multiple threads should work."""
        import threading

        errors = []
        logger = logger_no_rotation

        def log_events():
            try:
                for _ in range(50):
                    logger.log("concurrent_event")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=log_events) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert logger.count(event_type="concurrent_event") == 200

    def test_concurrent_log_and_query(self, logger):
        """Concurrent logging and querying should work."""
        import threading

        errors = []

        def log_events():
            try:
                for _ in range(50):
                    logger.log("concurrent_event")
            except Exception as e:
                errors.append(e)

        def query_events():
            try:
                for _ in range(50):
                    logger.query(event_type="concurrent_event")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=log_events)
        t2 = threading.Thread(target=query_events)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors


# ── Edge Case Tests ────────────────────────────────────────────────────────────

class TestAuditLoggerEdgeCases:
    """Tests for edge cases."""

    def test_empty_string_fields(self, logger):
        """Empty string fields should be stored correctly."""
        entry = logger.log("event", user="", details="")
        assert entry["user"] == ""
        assert entry["details"] == ""

    def test_unicode_fields(self, logger):
        """Unicode characters should be handled."""
        entry = logger.log("event", user="用户", details="测试日志")
        assert entry["user"] == "用户"
        assert entry["details"] == "测试日志"

    def test_long_details(self, logger):
        """Very long details should be stored."""
        long_text = "x" * 10000
        entry = logger.log("event", details=long_text)
        assert len(entry["details"]) == 10000

    def test_special_characters(self, logger):
        """Special characters in fields should be stored correctly."""
        entry = logger.log(
            "event",
            details="Special: !@#$%^&*()_+-=[]{}|;':\",./<>?"
        )
        assert "!@#$%^&*()" in entry["details"]

    def test_sql_injection_prevention(self, logger):
        """SQL injection in fields should be safely handled."""
        entry = logger.log("event", details="'; DROP TABLE audit_log; --")
        # Table should still exist
        assert logger.count() == 1

    def test_boolean_success_conversion(self, logger):
        """Success field should be converted to boolean."""
        entry = logger.log("event", success=True)
        assert entry["success"] is True
        entry = logger.log("event", success=False)
        assert entry["success"] is False

    def test_none_success_not_filtered(self, logger):
        """Query with success=None should not filter."""
        logger.log("event", success=True)
        logger.log("event", success=False)
        entries = logger.query(success=None)
        assert len(entries) == 2
