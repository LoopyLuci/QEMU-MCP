"""Tests for the enhanced Metrics Store and Telemetry panel."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "src"))

from gui.metrics_store import (
    MetricsStore,
    MetricSample,
    TIER_WINDOWS,
    _now,
    _to_iso,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def store():
    """Create an in-memory MetricsStore for each test."""
    s = MetricsStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def tmp_store():
    """Create a file-backed MetricsStore."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    s = MetricsStore(path)
    yield s
    s.close()
    os.unlink(path)


# ── Basic insert & query ─────────────────────────────────────────────────────


class TestInsert:
    def test_insert_cpu(self, store):
        sid = store.insert_sample("cpu", 25.5)
        assert sid > 0

    def test_insert_mem(self, store):
        sid = store.insert_sample("mem", 72.3)
        assert sid > 0

    def test_insert_disk(self, store):
        sid = store.insert_sample("disk", 15.0)
        assert sid > 0

    def test_insert_net(self, store):
        sid = store.insert_sample("net", 1024.5)
        assert sid > 0

    def test_insert_invalid_type(self, store):
        with pytest.raises(ValueError, match="Unknown metric_type"):
            store.insert_sample("invalid", 100)

    def test_insert_with_meta(self, store):
        sid = store.insert_sample("cpu", 10.0, {"host": True, "cores": 4})
        assert sid > 0

    def test_insert_with_timestamp(self, store):
        ts = datetime(2025, 1, 1, 12, 0, 0)
        sid = store.insert_sample("cpu", 5.0, timestamp=ts)
        assert sid > 0

    def test_insert_many(self, store):
        samples = [
            MetricSample("cpu", 10.0 + i, _now() - timedelta(seconds=i))
            for i in range(50)
        ]
        count = store.insert_many(samples)
        assert count == 50

    def test_insert_many_invalid(self, store):
        samples = [MetricSample("invalid", 10.0)]
        with pytest.raises(ValueError):
            store.insert_many(samples)


# ── History retrieval ─────────────────────────────────────────────────────────


class TestHistory:
    def test_get_history_empty(self, store):
        hist = store.get_history("cpu", hours=1)
        assert hist == []

    def test_get_history_raw(self, store):
        for i in range(10):
            store.insert_sample("cpu", float(i))
        hist = store.get_history("cpu", hours=24)
        assert len(hist) == 10
        assert hist[0]["avg_value"] == 0.0
        assert hist[-1]["avg_value"] == 9.0

    def test_get_history_with_time_window(self, store):
        now = _now()
        for i in range(100):
            store.insert_sample(
                "cpu",
                float(i),
                timestamp=now - timedelta(seconds=2 * i),
            )
        hist = store.get_history("cpu", hours=1)
        assert len(hist) == 100

    def test_get_history_filtered_window(self, store):
        now = _now()
        for i in range(50):
            store.insert_sample(
                "cpu",
                float(i),
                timestamp=now - timedelta(seconds=100 * i),
            )
        hist = store.get_history("cpu", hours=0.5)
        assert len(hist) <= 20

    def test_get_history_invalid_type(self, store):
        with pytest.raises(ValueError):
            store.get_history("invalid", hours=1)

    def test_get_history_uses_1min_tier(self, store):
        now = _now()
        for i in range(100):
            store.insert_sample(
                "cpu",
                float(i % 100),
                timestamp=now - timedelta(minutes=30 * i / 10),
            )
        hist = store.get_history("cpu", hours=48)
        assert isinstance(hist, list)

    def test_get_history_uses_1hour_tier(self, store):
        now = _now()
        for i in range(50):
            store.insert_sample(
                "cpu",
                float(i),
                timestamp=now - timedelta(hours=2 * i),
            )
        hist = store.get_history("cpu", hours=24 * 15)
        assert isinstance(hist, list)


# ── Downsampling ──────────────────────────────────────────────────────────────


class TestDownsample:
    def test_downsample_empty(self, store):
        result = store.downsample()
        assert result["raw_pruned"] == 0

    def test_downsample_prunes_old_raw(self, store):
        now = _now()
        for i in range(100):
            store.insert_sample(
                "cpu",
                float(i),
                timestamp=now - timedelta(hours=25, seconds=i * 10),
            )
        result = store.downsample(now)
        assert result["raw_pruned"] == 100

    def test_downsample_keeps_recent_raw(self, store):
        now = _now()
        for i in range(50):
            store.insert_sample(
                "cpu",
                float(i),
                timestamp=now - timedelta(seconds=i * 2),
            )
        result = store.downsample(now)
        assert result["raw_pruned"] == 0
        hist = store.get_history("cpu", hours=1)
        assert len(hist) == 50

    def test_downsample_creates_1min_buckets(self, store):
        now = _now()
        for i in range(200):
            store.insert_sample(
                "cpu",
                float(i % 100),
                timestamp=now - timedelta(hours=25, seconds=i * 30),
            )
        result = store.downsample(now)
        assert result["raw_to_1min"] > 0

    def test_downsample_prunes_old_1min(self, store):
        now = _now()
        for i in range(500):
            store.insert_sample(
                "cpu",
                float(i % 100),
                timestamp=now - timedelta(days=10, seconds=i * 60),
            )
        result = store.downsample(now)
        assert result["1min_pruned"] > 0

    def test_downsample_full_pipeline(self, store):
        now = _now()
        for i in range(1000):
            store.insert_sample(
                "cpu",
                float(i % 100),
                timestamp=now - timedelta(days=35, seconds=i * 60),
            )
        result = store.downsample(now)
        assert result["raw_pruned"] > 0
        assert result["1min_pruned"] > 0
        assert result["1hour_pruned"] >= 0


# ── Statistics ────────────────────────────────────────────────────────────────


class TestStats:
    def test_stats_empty(self, store):
        stats = store.get_stats()
        assert stats["raw_count"] == 0
        assert stats["1min_count"] == 0
        assert stats["1hour_count"] == 0
        assert stats["alert_count"] == 0

    def test_stats_with_data(self, store):
        for i in range(10):
            store.insert_sample("cpu", float(i))
        stats = store.get_stats()
        assert stats["raw_count"] == 10

    def test_stats_db_size_memory(self, store):
        stats = store.get_stats()
        assert stats["db_size_bytes"] == 0

    def test_stats_db_size_file(self, tmp_store):
        for i in range(10):
            tmp_store.insert_sample("cpu", float(i))
        stats = tmp_store.get_stats()
        assert stats["db_size_bytes"] > 0


# ── Alert Rules ───────────────────────────────────────────────────────────────


class TestAlertRules:
    def test_add_alert_rule(self, store):
        rid = store.add_alert_rule("cpu", 90.0, "gt", 60, "High CPU")
        assert rid > 0

    def test_add_alert_rule_default_label(self, store):
        rid = store.add_alert_rule("mem", 85.0, "gt")
        rules = store.get_alerts()
        assert len(rules) == 1
        assert rules[0].label == "mem gt 85.0"

    def test_add_alert_rule_invalid_type(self, store):
        with pytest.raises(ValueError):
            store.add_alert_rule("invalid", 90.0)

    def test_add_alert_rule_invalid_condition(self, store):
        with pytest.raises(ValueError):
            store.add_alert_rule("cpu", 90.0, "invalid")

    def test_get_alerts(self, store):
        store.add_alert_rule("cpu", 90.0, label="CPU High")
        store.add_alert_rule("mem", 85.0, label="Mem High")
        rules = store.get_alerts()
        assert len(rules) == 2

    def test_get_alerts_enabled_only(self, store):
        store.add_alert_rule("cpu", 90.0, label="CPU High", enabled=True)
        store.add_alert_rule("mem", 85.0, label="Mem High", enabled=False)
        rules = store.get_alerts(enabled_only=True)
        assert len(rules) == 1
        assert rules[0].metric_type == "cpu"

    def test_update_alert_rule(self, store):
        rid = store.add_alert_rule("cpu", 90.0, label="CPU High")
        store.update_alert_rule(rid, threshold=95.0, label="Updated")
        rules = store.get_alerts()
        assert rules[0].threshold == 95.0
        assert rules[0].label == "Updated"

    def test_delete_alert_rule(self, store):
        rid = store.add_alert_rule("cpu", 90.0, label="CPU High")
        store.delete_alert_rule(rid)
        rules = store.get_alerts()
        assert len(rules) == 0


# ── Alert Evaluation ──────────────────────────────────────────────────────────


class TestAlertEvaluation:
    def test_evaluate_no_rules(self, store):
        events = store.evaluate_alerts({"cpu": 50.0})
        assert events == []

    def test_evaluate_fires_alert(self, store):
        store.add_alert_rule("cpu", 90.0, "gt", label="CPU High")
        events = store.evaluate_alerts({"cpu": 95.0})
        assert len(events) == 1
        assert events[0].action == "fired"
        assert events[0].value == 95.0

    def test_evaluate_no_fire_below_threshold(self, store):
        store.add_alert_rule("cpu", 90.0, "gt", label="CPU High")
        events = store.evaluate_alerts({"cpu": 50.0})
        assert len(events) == 0

    def test_evaluate_resolves_alert(self, store):
        store.add_alert_rule("cpu", 90.0, "gt", label="CPU High")
        store.evaluate_alerts({"cpu": 95.0})
        events = store.evaluate_alerts({"cpu": 50.0})
        assert len(events) == 1
        assert events[0].action == "resolved"

    def test_evaluate_no_duplicate_fire(self, store):
        store.add_alert_rule("cpu", 90.0, "gt", label="CPU High")
        events1 = store.evaluate_alerts({"cpu": 95.0})
        events2 = store.evaluate_alerts({"cpu": 96.0})
        assert len(events1) == 1
        assert len(events2) == 0

    def test_evaluate_lt_condition(self, store):
        store.add_alert_rule("cpu", 10.0, "lt", label="CPU Low")
        events = store.evaluate_alerts({"cpu": 5.0})
        assert len(events) == 1
        assert events[0].action == "fired"

    def test_evaluate_gte_condition(self, store):
        store.add_alert_rule("cpu", 90.0, "gte", label="CPU >= 90")
        events = store.evaluate_alerts({"cpu": 90.0})
        assert len(events) == 1

    def test_evaluate_lte_condition(self, store):
        store.add_alert_rule("cpu", 10.0, "lte", label="CPU <= 10")
        events = store.evaluate_alerts({"cpu": 10.0})
        assert len(events) == 1

    def test_evaluate_eq_condition(self, store):
        store.add_alert_rule("cpu", 50.0, "eq", label="CPU == 50")
        events = store.evaluate_alerts({"cpu": 50.0})
        assert len(events) == 1

    def test_evaluate_missing_metric(self, store):
        store.add_alert_rule("cpu", 90.0, "gt", label="CPU High")
        events = store.evaluate_alerts({"mem": 50.0})
        assert len(events) == 0

    def test_evaluate_multiple_rules(self, store):
        store.add_alert_rule("cpu", 90.0, "gt", label="CPU High")
        store.add_alert_rule("mem", 85.0, "gt", label="Mem High")
        events = store.evaluate_alerts({"cpu": 95.0, "mem": 90.0})
        assert len(events) == 2


# ── Alert Log ─────────────────────────────────────────────────────────────────


class TestAlertLog:
    def test_alert_log_populated(self, store):
        store.add_alert_rule("cpu", 90.0, "gt", label="CPU High")
        store.evaluate_alerts({"cpu": 95.0})
        log = store.get_alert_log()
        assert len(log) == 1
        assert log[0].action == "fired"

    def test_alert_log_ordered_by_time(self, store):
        store.add_alert_rule("cpu", 90.0, "gt", label="CPU High")
        store.evaluate_alerts({"cpu": 95.0})
        store.evaluate_alerts({"cpu": 50.0})
        log = store.get_alert_log()
        assert len(log) == 2
        assert log[0].timestamp >= log[1].timestamp

    def test_alert_log_filter_action(self, store):
        store.add_alert_rule("cpu", 90.0, "gt", label="CPU High")
        store.evaluate_alerts({"cpu": 95.0})
        store.evaluate_alerts({"cpu": 50.0})
        fired = store.get_alert_log(action_filter="fired")
        resolved = store.get_alert_log(action_filter="resolved")
        assert len(fired) == 1
        assert len(resolved) == 1

    def test_alert_log_limit(self, store):
        store.add_alert_rule("cpu", 90.0, "gt", label="CPU High")
        for i in range(10):
            store.evaluate_alerts({"cpu": 95.0 if i % 2 == 0 else 50.0})
        log = store.get_alert_log(limit=5)
        assert len(log) <= 5

    def test_clear_alert_log(self, store):
        store.add_alert_rule("cpu", 90.0, "gt", label="CPU High")
        store.evaluate_alerts({"cpu": 95.0})
        count = store.clear_alert_log()
        assert count == 1
        log = store.get_alert_log()
        assert len(log) == 0


# ── File-backed store ─────────────────────────────────────────────────────────


class TestFileBacked:
    def test_persistence(self, tmp_store):
        tmp_store.insert_sample("cpu", 42.0)
        stats = tmp_store.get_stats()
        assert stats["raw_count"] == 1

    def test_file_created(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            store = MetricsStore(path)
            assert Path(path).exists()
            store.close()
        finally:
            os.unlink(path)


# ── Thread safety ─────────────────────────────────────────────────────────────


class TestThreadSafety:
    def test_concurrent_inserts(self, store):
        import threading

        errors = []

        def worker():
            try:
                for i in range(100):
                    store.insert_sample("cpu", float(i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = store.get_stats()
        assert stats["raw_count"] == 500


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_zero_values(self, store):
        store.insert_sample("cpu", 0.0)
        hist = store.get_history("cpu", hours=1)
        assert len(hist) == 1
        assert hist[0]["avg_value"] == 0.0

    def test_negative_values(self, store):
        store.insert_sample("cpu", -5.0)
        hist = store.get_history("cpu", hours=1)
        assert hist[0]["avg_value"] == -5.0

    def test_large_values(self, store):
        store.insert_sample("net", 1e9)
        hist = store.get_history("net", hours=1)
        assert hist[0]["avg_value"] == 1e9

    def test_very_small_values(self, store):
        store.insert_sample("cpu", 1e-9)
        hist = store.get_history("cpu", hours=1)
        assert abs(hist[0]["avg_value"] - 1e-9) < 1e-15

    def test_vacuum(self, store):
        for i in range(100):
            store.insert_sample("cpu", float(i))
        store.vacuum()

    def test_close_idempotent(self, store):
        store.close()
        store.close()


# ── Condition check tests ─────────────────────────────────────────────────────


class TestConditions:
    def test_gt_true(self, store):
        assert store._check_condition(10.0, 5.0, "gt") is True

    def test_gt_false(self, store):
        assert store._check_condition(5.0, 10.0, "gt") is False

    def test_lt_true(self, store):
        assert store._check_condition(3.0, 5.0, "lt") is True

    def test_lt_false(self, store):
        assert store._check_condition(10.0, 5.0, "lt") is False

    def test_gte_equal(self, store):
        assert store._check_condition(5.0, 5.0, "gte") is True

    def test_lte_equal(self, store):
        assert store._check_condition(5.0, 5.0, "lte") is True

    def test_eq_close(self, store):
        assert store._check_condition(5.0 + 1e-10, 5.0, "eq") is True

    def test_unknown_condition(self, store):
        assert store._check_condition(10.0, 5.0, "unknown") is False


# ── Integration tests for Telemetry Panel ──────────────────────────────────────


class TestTelemetryPanelIntegration:
    """Integration tests for the enhanced TelemetryPanel."""

    def test_metrics_store_polling(self, store):
        """Test that metrics are properly polled and stored."""
        store.insert_sample("cpu", 45.0)
        store.insert_sample("mem", 72.5)
        stats = store.get_stats()
        assert stats["raw_count"] >= 2

    def test_alert_fires_and_resolves(self, store):
        """Test complete alert lifecycle."""
        store.add_alert_rule("cpu", 90.0, "gt", 0, "CPU Alert")
        # Fire
        events1 = store.evaluate_alerts({"cpu": 95.0})
        assert len(events1) == 1
        assert events1[0].action == "fired"
        # No duplicate
        events2 = store.evaluate_alerts({"cpu": 96.0})
        assert len(events2) == 0
        # Resolve
        events3 = store.evaluate_alerts({"cpu": 50.0})
        assert len(events3) == 1
        assert events3[0].action == "resolved"

    def test_downsampling_transitions(self, store):
        """Test that data transitions between tiers correctly."""
        now = _now()
        # Insert old data (25+ hours ago)
        for i in range(100):
            store.insert_sample(
                "cpu",
                float(i % 100),
                timestamp=now - timedelta(hours=25, seconds=i * 30),
            )
        # Downsample
        result = store.downsample(now)
        assert result["raw_to_1min"] > 0
        # Query should use 1-min tier for 48h
        hist = store.get_history("cpu", hours=48)
        assert isinstance(hist, list)

    def test_alert_log_with_filter(self, store):
        """Test alert log filtering."""
        store.add_alert_rule("cpu", 90.0, "gt", 0, "CPU High")
        store.evaluate_alerts({"cpu": 95.0})  # fires
        store.evaluate_alerts({"cpu": 50.0})  # resolves
        store.evaluate_alerts({"cpu": 96.0})  # fires again

        all_events = store.get_alert_log()
        assert len(all_events) == 3

        fired = store.get_alert_log(action_filter="fired")
        assert len(fired) == 2

        resolved = store.get_alert_log(action_filter="resolved")
        assert len(resolved) == 1

    def test_default_alert_rules(self, store):
        """Test that default alert rules can be added."""
        store.add_alert_rule("cpu", 90.0, "gt", 0, "CPU High (>90%)")
        store.add_alert_rule("mem", 85.0, "gt", 0, "Memory High (>85%)")
        store.add_alert_rule("disk", 80.0, "gt", 0, "Disk High (>80%)")
        rules = store.get_alerts()
        assert len(rules) == 3

    def test_multiple_metrics_storage(self, store):
        """Test storing multiple metric types."""
        store.insert_sample("cpu", 25.0)
        store.insert_sample("mem", 65.0)
        store.insert_sample("disk", 45.0)
        store.insert_sample("net", 1024.0)
        cpu_hist = store.get_history("cpu", hours=1)
        mem_hist = store.get_history("mem", hours=1)
        disk_hist = store.get_history("disk", hours=1)
        net_hist = store.get_history("net", hours=1)
        assert len(cpu_hist) == 1
        assert len(mem_hist) == 1
        assert len(disk_hist) == 1
        assert len(net_hist) == 1
