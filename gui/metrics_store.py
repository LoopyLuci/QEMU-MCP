"""Metrics Store — SQLite-backed persistent storage for VM and host metrics.

Features:
    - Raw metric samples for CPU, memory, disk, and network.
    - Automatic downsampling: raw for 24h, 1-minute aggregates for 7d,
      1-hour aggregates for 30d.
    - Alert rules with configurable thresholds and conditions.
    - Alert log (fired alerts with timestamps).
    - QTimer-based polling helper for GUI integration.

Usage::

    store = MetricsStore(":memory:")   # or a path for persistence
    store.insert_sample("cpu", 23.5, {"host": True})
    history = store.get_history("cpu", hours=6)
    rules = store.get_alerts()
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("vmharness.metrics_store")


# ── Downsampling tiers ────────────────────────────────────────────────────────
# Tier name  →  retention window   →  bucket size
TIER_RAW = "raw"      # 24 hours        →  per-sample (≈2s poll)
TIER_1MIN = "1min"    # 7 days (168h)   →  60-second buckets
TIER_1HOUR = "1hour"  # 30 days (720h)  →  3600-second buckets

TIER_WINDOWS: Dict[str, int] = {
    TIER_RAW:   24 * 3600,         # seconds
    TIER_1MIN:  7 * 24 * 3600,
    TIER_1HOUR: 30 * 24 * 3600,
}

TIER_BUCKETS: Dict[str, int] = {
    TIER_RAW:   1,
    TIER_1MIN:  60,
    TIER_1HOUR: 3600,
}

METRIC_TYPES = ("cpu", "mem", "disk", "net")
ALERT_CONDITIONS = ("gt", "lt", "gte", "lte", "eq")
ALERT_STATUSES = ("ok", "firing", "muted")


@dataclass
class MetricSample:
    """A single recorded metric data point."""
    metric_type: str
    value: float
    timestamp: datetime = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = _now()


@dataclass
class AlertRule:
    """An alert threshold rule."""
    id: Optional[int]
    metric_type: str
    threshold: float
    condition: str  # gt, lt, gte, lte, eq
    duration_sec: int  # how long the condition must hold before firing
    label: str
    enabled: bool = True
    last_state: str = "ok"
    last_fired: Optional[datetime] = None


@dataclass
class AlertEvent:
    """A recorded alert firing / resolution."""
    id: Optional[int]
    rule_id: int
    rule_label: str
    metric_type: str
    value: float
    threshold: float
    condition: str
    action: str  # "fired" or "resolved"
    timestamp: datetime


# ── Helpers ────────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.utcnow()


def _to_iso(dt: datetime) -> str:
    return dt.isoformat() + "Z"


def _from_iso(s: str) -> datetime:
    """Parse ISO-8601 string returned by SQLite."""
    s = s.rstrip("Z")
    if "." in s:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f")
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


# ── Metrics Store ──────────────────────────────────────────────────────────────


class MetricsStore:
    """SQLite-backed metric storage with automatic tiering & downsampling.

    Thread-safe via an internal lock for all DB operations.
    """

    def __init__(self, db_path: str | Path = ":memory:"):
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._local = threading.local()
        self._is_memory = self._db_path == ":memory:"
        # Use shared-cache for in-memory DB so all threads see same data
        # Use a unique name per instance so each MetricsStore(":memory:") is isolated
        if self._is_memory:
            self._db_path = f"file:memdb_{id(self)}?mode=memory&cache=shared"
            self._uri = True
        else:
            self._uri = False
        self._init_schema()

    # ── Connection handling ─────────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        """Yield a sqlite3 connection with row_factory=dict-like access."""
        if not hasattr(self._local, "cx") or self._local.cx is None:
            self._local.cx = sqlite3.connect(
                self._db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=False,
                uri=self._uri,
            )
            self._local.cx.row_factory = sqlite3.Row
            self._local.cx.execute("PRAGMA journal_mode=WAL")
            self._local.cx.execute("PRAGMA synchronous=NORMAL")
        try:
            yield self._local.cx
        except Exception:
            self._local.cx.rollback()
            raise  # Re-raise after rollback — caller handles the error

    def _init_schema(self):
        """Create all tables if they don't exist."""
        with self._lock, self._conn() as cx:
            cx.executescript(
                """
                CREATE TABLE IF NOT EXISTS metrics_raw (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_type TEXT    NOT NULL,
                    value       REAL    NOT NULL,
                    timestamp   TEXT    NOT NULL,
                    meta        TEXT    DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_metrics_raw_ts
                    ON metrics_raw (metric_type, timestamp);

                CREATE TABLE IF NOT EXISTS metrics_1min (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_type TEXT    NOT NULL,
                    avg_value   REAL    NOT NULL,
                    min_value   REAL    NOT NULL,
                    max_value   REAL    NOT NULL,
                    count       INTEGER NOT NULL,
                    timestamp   TEXT    NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_metrics_1min_ts
                    ON metrics_1min (metric_type, timestamp);

                CREATE TABLE IF NOT EXISTS metrics_1hour (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_type TEXT    NOT NULL,
                    avg_value   REAL    NOT NULL,
                    min_value   REAL    NOT NULL,
                    max_value   REAL    NOT NULL,
                    count       INTEGER NOT NULL,
                    timestamp   TEXT    NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_metrics_1hour_ts
                    ON metrics_1hour (metric_type, timestamp);

                CREATE TABLE IF NOT EXISTS alert_rules (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_type   TEXT    NOT NULL,
                    threshold     REAL    NOT NULL,
                    condition     TEXT    NOT NULL DEFAULT 'gt',
                    duration_sec  INTEGER NOT NULL DEFAULT 0,
                    label         TEXT    NOT NULL,
                    enabled       INTEGER NOT NULL DEFAULT 1,
                    last_state    TEXT    NOT NULL DEFAULT 'ok',
                    last_fired    TEXT,
                    created_at    TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alert_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_id     INTEGER NOT NULL,
                    rule_label  TEXT    NOT NULL,
                    metric_type TEXT    NOT NULL,
                    value       REAL    NOT NULL,
                    threshold   REAL    NOT NULL,
                    condition   TEXT    NOT NULL,
                    action      TEXT    NOT NULL,
                    timestamp   TEXT    NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_alert_log_ts
                    ON alert_log (timestamp);
                """
            )
            cx.commit()

    # ── Inserting samples ───────────────────────────────────────────────────

    def insert_sample(
        self,
        metric_type: str,
        value: float,
        meta: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> int:
        """Insert a raw metric sample. Returns the row id."""
        if metric_type not in METRIC_TYPES:
            raise ValueError(f"Unknown metric_type: {metric_type}")
        if timestamp is None:
            timestamp = _now()
        meta_json = _json_dumps(meta or {})
        with self._lock, self._conn() as cx:
            cur = cx.execute(
                "INSERT INTO metrics_raw (metric_type, value, timestamp, meta) VALUES (?, ?, ?, ?)",
                (metric_type, value, _to_iso(timestamp), meta_json),
            )
            cx.commit()
            return cur.lastrowid

    def insert_many(self, samples: List[MetricSample]) -> int:
        """Bulk insert samples. Returns the number inserted."""
        rows = []
        for s in samples:
            if s.metric_type not in METRIC_TYPES:
                raise ValueError(f"Unknown metric_type: {s.metric_type}")
            ts = s.timestamp or _now()
            rows.append(
                (
                    s.metric_type,
                    s.value,
                    _to_iso(ts),
                    _json_dumps(s.meta),
                )
            )
        with self._lock, self._conn() as cx:
            cx.executemany(
                "INSERT INTO metrics_raw (metric_type, value, timestamp, meta) VALUES (?, ?, ?, ?)",
                rows,
            )
            cx.commit()
        return len(rows)

    # ── Querying history ────────────────────────────────────────────────────

    def get_history(
        self,
        metric_type: str,
        hours: float = 24,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Return downsampled history for *metric_type* over the given window.

        Automatically selects the appropriate tier:
        - ≤24h  → raw samples
        - ≤168h (7d) → 1-min aggregates
        - ≤720h (30d) → 1-hour aggregates

        Each dict has keys: timestamp, avg_value, min_value, max_value, count.
        """
        if metric_type not in METRIC_TYPES:
            raise ValueError(f"Unknown metric_type: {metric_type}")

        if end is None:
            end = _now()
        start = end - timedelta(hours=hours)
        window_sec = hours * 3600

        if window_sec <= TIER_WINDOWS[TIER_RAW]:
            return self._query_raw(metric_type, start, end)
        elif window_sec <= TIER_WINDOWS[TIER_1MIN]:
            return self._query_tier("metrics_1min", metric_type, start, end)
        else:
            return self._query_tier("metrics_1hour", metric_type, start, end)

    def _query_raw(
        self, metric_type: str, start: datetime, end: datetime
    ) -> List[Dict[str, Any]]:
        with self._lock, self._conn() as cx:
            rows = cx.execute(
                """SELECT value, timestamp FROM metrics_raw
                   WHERE metric_type = ? AND timestamp >= ? AND timestamp <= ?
                   ORDER BY timestamp ASC""",
                (metric_type, _to_iso(start), _to_iso(end)),
            ).fetchall()
        return [
            {
                "timestamp": _from_iso(r["timestamp"]),
                "avg_value": r["value"],
                "min_value": r["value"],
                "max_value": r["value"],
                "count": 1,
            }
            for r in rows
        ]

    def _query_tier(
        self, table: str, metric_type: str, start: datetime, end: datetime
    ) -> List[Dict[str, Any]]:
        with self._lock, self._conn() as cx:
            rows = cx.execute(
                f"""SELECT avg_value, min_value, max_value, count, timestamp
                    FROM {table}
                    WHERE metric_type = ? AND timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp ASC""",
                (metric_type, _to_iso(start), _to_iso(end)),
            ).fetchall()
        return [
            {
                "timestamp": _from_iso(r["timestamp"]),
                "avg_value": r["avg_value"],
                "min_value": r["min_value"],
                "max_value": r["max_value"],
                "count": r["count"],
            }
            for r in rows
        ]

    # ── Downsampling maintenance ────────────────────────────────────────────

    def downsample(self, now: Optional[datetime] = None) -> Dict[str, int]:
        """Aggregate raw samples into 1-min buckets and 1-min into 1-hour.

        Prunes raw data older than 24h, 1-min data older than 7d,
        1-hour data older than 30d.

        Returns a dict with counts of rows downsampled/pruned per tier.
        """
        if now is None:
            now = _now()
        result: Dict[str, int] = {}

        with self._lock, self._conn() as cx:
            # ── Raw → 1-min ─────────────────────────────────────────────
            cutoff_raw = _to_iso(now - timedelta(seconds=TIER_WINDOWS[TIER_RAW]))

            # First aggregate old raw rows into 1-min buckets
            cx.execute(
                """INSERT INTO metrics_1min
                    (metric_type, avg_value, min_value, max_value, count, timestamp)
                   SELECT
                    metric_type,
                    AVG(value),
                    MIN(value),
                    MAX(value),
                    COUNT(*),
                    strftime('%Y-%m-%dT%H:%M:00', timestamp)
                   FROM metrics_raw
                   WHERE timestamp < ?
                   GROUP BY metric_type, strftime('%Y-%m-%dT%H:%M', timestamp)""",
                (cutoff_raw,),
            )
            result["raw_to_1min"] = cx.execute("SELECT changes()").fetchone()[0]

            # Then prune the old raw rows
            row = cx.execute(
                """SELECT COUNT(*) AS c FROM metrics_raw
                   WHERE timestamp < ?""",
                (cutoff_raw,),
            ).fetchone()
            result["raw_pruned"] = row["c"]
            cx.execute(
                """DELETE FROM metrics_raw WHERE timestamp < ?""",
                (cutoff_raw,),
            )

            # ── 1-min → 1-hour ──────────────────────────────────────────
            cutoff_1min = _to_iso(now - timedelta(seconds=TIER_WINDOWS[TIER_1MIN]))

            # Aggregate old 1-min into 1-hour
            cx.execute(
                """INSERT INTO metrics_1hour
                    (metric_type, avg_value, min_value, max_value, count, timestamp)
                   SELECT
                    metric_type,
                    AVG(avg_value),
                    MIN(min_value),
                    MAX(max_value),
                    SUM(count),
                    strftime('%Y-%m-%dT%H:00:00', timestamp)
                   FROM metrics_1min
                   WHERE timestamp < ?
                   GROUP BY metric_type, strftime('%Y-%m-%dT%H', timestamp)""",
                (cutoff_1min,),
            )
            result["1min_to_1hour"] = cx.execute("SELECT changes()").fetchone()[0]

            # Then prune old 1-min
            row = cx.execute(
                """SELECT COUNT(*) AS c FROM metrics_1min
                   WHERE timestamp < ?""",
                (cutoff_1min,),
            ).fetchone()
            result["1min_pruned"] = row["c"]
            cx.execute(
                """DELETE FROM metrics_1min WHERE timestamp < ?""",
                (cutoff_1min,),
            )

            # Prune 1-hour older than 30d
            cutoff_1hour = _to_iso(now - timedelta(seconds=TIER_WINDOWS[TIER_1HOUR]))
            row = cx.execute(
                """SELECT COUNT(*) AS c FROM metrics_1hour
                   WHERE timestamp < ?""",
                (cutoff_1hour,),
            ).fetchone()
            result["1hour_pruned"] = row["c"]
            cx.execute(
                """DELETE FROM metrics_1hour WHERE timestamp < ?""",
                (cutoff_1hour,),
            )

            cx.commit()

        logger.debug("downsample complete: %s", result)
        return result

    # ── Statistics ──────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return a dict with sample counts per tier and total DB size."""
        with self._lock, self._conn() as cx:
            raw_count = cx.execute("SELECT COUNT(*) FROM metrics_raw").fetchone()[0]
            min_count = cx.execute("SELECT COUNT(*) FROM metrics_1min").fetchone()[0]
            hr_count = cx.execute("SELECT COUNT(*) FROM metrics_1hour").fetchone()[0]
            alert_count = cx.execute("SELECT COUNT(*) FROM alert_log").fetchone()[0]

        db_size = 0
        if not self._is_memory:
            db_path = Path(self._db_path)
            if db_path.exists():
                db_size = db_path.stat().st_size

        return {
            "raw_count": raw_count,
            "1min_count": min_count,
            "1hour_count": hr_count,
            "alert_count": alert_count,
            "db_size_bytes": db_size,
        }

    # ── Alert Rules ────────────────────────────────────────────────────────

    def add_alert_rule(
        self,
        metric_type: str,
        threshold: float,
        condition: str = "gt",
        duration_sec: int = 0,
        label: str = "",
        enabled: bool = True,
    ) -> int:
        """Create an alert rule. Returns the new rule id."""
        if metric_type not in METRIC_TYPES:
            raise ValueError(f"Unknown metric_type: {metric_type}")
        if condition not in ALERT_CONDITIONS:
            raise ValueError(f"Unknown condition: {condition}")
        if not label:
            label = f"{metric_type} {condition} {threshold}"

        with self._lock, self._conn() as cx:
            cur = cx.execute(
                """INSERT INTO alert_rules
                    (metric_type, threshold, condition, duration_sec, label, enabled, last_state, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'ok', ?)""",
                (metric_type, threshold, condition, duration_sec, label, int(enabled), _to_iso(_now())),
            )
            cx.commit()
            return cur.lastrowid

    def update_alert_rule(self, rule_id: int, **kwargs) -> bool:
        """Update fields on an alert rule."""
        allowed = {"threshold", "condition", "duration_sec", "label", "enabled", "last_state", "last_fired"}
        sets = []
        vals = []
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            if k == "enabled":
                v = int(v)
            if k == "last_fired" and isinstance(v, datetime):
                v = _to_iso(v)
            sets.append(f"{k} = ?")
            vals.append(v)
        if not sets:
            return False
        vals.append(rule_id)
        with self._lock, self._conn() as cx:
            cx.execute(
                f"UPDATE alert_rules SET {', '.join(sets)} WHERE id = ?",
                vals,
            )
            cx.commit()
        return True

    def delete_alert_rule(self, rule_id: int) -> bool:
        with self._lock, self._conn() as cx:
            cx.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
            cx.commit()
        return True

    def get_alerts(self, enabled_only: bool = False) -> List[AlertRule]:
        with self._lock, self._conn() as cx:
            q = "SELECT * FROM alert_rules"
            if enabled_only:
                q += " WHERE enabled = 1"
            rows = cx.execute(q).fetchall()
        return [
            AlertRule(
                id=r["id"],
                metric_type=r["metric_type"],
                threshold=r["threshold"],
                condition=r["condition"],
                duration_sec=r["duration_sec"],
                label=r["label"],
                enabled=bool(r["enabled"]),
                last_state=r["last_state"],
                last_fired=_from_iso(r["last_fired"]) if r["last_fired"] else None,
            )
            for r in rows
        ]

    # ── Alert evaluation & logging ──────────────────────────────────────────

    def evaluate_alerts(self, current_values: Dict[str, float]) -> List[AlertEvent]:
        """Evaluate all enabled alert rules against *current_values*.

        Returns a list of AlertEvent objects for any state changes
        (fired or resolved).
        """
        rules = self.get_alerts(enabled_only=True)
        events: List[AlertEvent] = []
        now = _now()

        for rule in rules:
            value = current_values.get(rule.metric_type)
            if value is None:
                continue

            triggered = self._check_condition(value, rule.threshold, rule.condition)

            if triggered and rule.last_state != "firing":
                # Fire the alert
                event = AlertEvent(
                    id=None,
                    rule_id=rule.id,
                    rule_label=rule.label,
                    metric_type=rule.metric_type,
                    value=value,
                    threshold=rule.threshold,
                    condition=rule.condition,
                    action="fired",
                    timestamp=now,
                )
                self._log_alert(event)
                self.update_alert_rule(rule.id, last_state="firing", last_fired=now)
                events.append(event)

            elif not triggered and rule.last_state == "firing":
                # Resolve the alert
                event = AlertEvent(
                    id=None,
                    rule_id=rule.id,
                    rule_label=rule.label,
                    metric_type=rule.metric_type,
                    value=value,
                    threshold=rule.threshold,
                    condition=rule.condition,
                    action="resolved",
                    timestamp=now,
                )
                self._log_alert(event)
                self.update_alert_rule(rule.id, last_state="ok")
                events.append(event)

        return events

    @staticmethod
    def _check_condition(value: float, threshold: float, condition: str) -> bool:
        if condition == "gt":
            return value > threshold
        if condition == "lt":
            return value < threshold
        if condition == "gte":
            return value >= threshold
        if condition == "lte":
            return value <= threshold
        if condition == "eq":
            return abs(value - threshold) < 1e-9
        return False

    def _log_alert(self, event: AlertEvent) -> int:
        with self._lock, self._conn() as cx:
            cur = cx.execute(
                """INSERT INTO alert_log
                    (rule_id, rule_label, metric_type, value, threshold, condition, action, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.rule_id,
                    event.rule_label,
                    event.metric_type,
                    event.value,
                    event.threshold,
                    event.condition,
                    event.action,
                    _to_iso(event.timestamp),
                ),
            )
            cx.commit()
            return cur.lastrowid

    def get_alert_log(
        self,
        limit: int = 100,
        action_filter: Optional[str] = None,
    ) -> List[AlertEvent]:
        with self._lock, self._conn() as cx:
            q = "SELECT * FROM alert_log"
            params: list = []
            if action_filter:
                q += " WHERE action = ?"
                params.append(action_filter)
            q += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = cx.execute(q, params).fetchall()
        return [
            AlertEvent(
                id=r["id"],
                rule_id=r["rule_id"],
                rule_label=r["rule_label"],
                metric_type=r["metric_type"],
                value=r["value"],
                threshold=r["threshold"],
                condition=r["condition"],
                action=r["action"],
                timestamp=_from_iso(r["timestamp"]),
            )
            for r in rows
        ]

    def clear_alert_log(self) -> int:
        with self._lock, self._conn() as cx:
            cur = cx.execute("DELETE FROM alert_log")
            cx.commit()
            return cur.rowcount

    # ── Maintenance ─────────────────────────────────────────────────────────

    def vacuum(self):
        """Reclaim disk space."""
        with self._lock, self._conn() as cx:
            cx.execute("VACUUM")

    def close(self):
        """Close the per-thread connection."""
        if hasattr(self._local, "cx") and self._local.cx is not None:
            self._local.cx.close()
            self._local.cx = None


# ── JSON helper (stdlib only) ─────────────────────────────────────────────────


def _json_dumps(obj: Any) -> str:
    """Minimal JSON encoder for metadata dicts."""
    import json
    return json.dumps(obj, default=str)


def _json_loads(s: str) -> Any:
    import json
    return json.loads(s)
