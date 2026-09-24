
"""
Audit logging for vm-harness security events.

Records all authentication attempts, access control decisions,
credential operations, and sensitive API calls. Supports structured
JSON logging with tamper-evident chaining.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("vmharness.security.audit")


class AuditEventType(str, Enum):
    # Authentication events
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_EXPIRED = "auth.expired"
    AUTH_REVOKED = "auth.revoked"

    # Credential operations
    CREDENTIAL_CREATED = "credential.created"
    CREDENTIAL_REVOKED = "credential.revoked"
    CREDENTIAL_ROTATED = "credential.rotated"

    # Access control
    ACCESS_GRANTED = "access.granted"
    ACCESS_DENIED = "access.denied"

    # VM operations
    VM_CREATED = "vm.created"
    VM_DELETED = "vm.deleted"
    VM_STARTED = "vm.started"
    VM_STOPPED = "vm.stopped"

    # Container operations
    CONTAINER_CREATED = "container.created"
    CONTAINER_DELETED = "container.deleted"

    # Kubernetes operations
    K8S_CLUSTER_CREATED = "k8s.cluster_created"
    K8S_CLUSTER_DELETED = "k8s.cluster_deleted"
    K8S_DEPLOYMENT_CREATED = "k8s.deployment_created"

    # Federation events
    FEDERATION_JOINED = "federation.joined"
    FEDERATION_LEFT = "federation.left"

    # Security events
    PAIRING_SUCCESS = "pairing.success"
    PAIRING_FAILURE = "pairing.failure"
    RATE_LIMIT_HIT = "rate_limit.hit"
    SUSPICIOUS_ACTIVITY = "security.suspicious"


@dataclass
class AuditEntry:
    """A single audit log entry."""
    event_type: AuditEventType
    identity: str = ""
    source_ip: str = ""
    resource: str = ""
    action: str = ""
    status: str = "ok"
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    previous_hash: str = ""
    entry_hash: str = ""

    def __post_init__(self) -> None:
        if not self.entry_hash:
            self.entry_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute a tamper-evident hash for this entry."""
        data = json.dumps({
            "id": self.entry_id,
            "type": self.event_type.value,
            "identity": self.identity,
            "timestamp": self.timestamp.isoformat(),
            "previous": self.previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.entry_id,
            "type": self.event_type.value,
            "identity": self.identity,
            "source_ip": self.source_ip,
            "resource": self.resource,
            "action": self.action,
            "status": self.status,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "hash": self.entry_hash,
        }


class AuditLogger:
    """
    Structured audit logger with tamper-evident chaining.

    Each entry includes a hash of the previous entry, creating a
    chain that can be verified to detect tampering.
    """

    def __init__(
        self,
        log_dir: Path | str,
        max_entries: int = 100_000,
    ) -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._max_entries = max_entries
        self._last_hash: str = ""
        self._entry_count: int = 0
        self._current_file: Path | None = None
        self._init_chain()

    def _init_chain(self) -> None:
        """Initialize the hash chain from existing log files."""
        log_files = sorted(self._log_dir.glob("audit-*.jsonl"))
        if not log_files:
            return
        # Read the last entry from the most recent file
        last_file = log_files[-1]
        try:
            with open(last_file, "r") as f:
                lines = f.readlines()
                if lines:
                    last_entry = json.loads(lines[-1])
                    self._last_hash = last_entry.get("hash", "")
                    self._entry_count = len(lines)
                    self._current_file = last_file
        except (json.JSONDecodeError, OSError):
            pass

    def _get_current_file(self) -> Path:
        """Get the current log file, rotating if necessary."""
        if self._current_file is None:
            self._current_file = self._log_dir / f"audit-{int(time.time())}.jsonl"
        # Rotate if file is too large (>10MB)
        if self._current_file.exists() and self._current_file.stat().st_size > 10 * 1024 * 1024:
            self._current_file = self._log_dir / f"audit-{int(time.time())}.jsonl"
            self._entry_count = 0
        return self._current_file

    def log(
        self,
        event_type: AuditEventType | str,
        identity: str = "",
        source_ip: str = "",
        resource: str = "",
        action: str = "",
        status: str = "ok",
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """
        Log an audit event.

        Args:
            event_type: Type of event (enum or string).
            identity: Who performed the action.
            source_ip: Source IP address.
            resource: Resource affected.
            action: Action performed.
            status: "ok" or "error".
            details: Additional structured details.

        Returns:
            The created AuditEntry.
        """
        if isinstance(event_type, str):
            event_type = AuditEventType(event_type)

        entry = AuditEntry(
            event_type=event_type,
            identity=identity,
            source_ip=source_ip,
            resource=resource,
            action=action,
            status=status,
            details=details or {},
            previous_hash=self._last_hash,
        )

        # Write to file
        log_file = self._get_current_file()
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
            self._entry_count += 1
        except OSError as e:
            log.error("Failed to write audit log: %s", e)

        # Update chain
        self._last_hash = entry.entry_hash

        # Also log to Python logger at appropriate level
        log.log(
            logging.INFO if status == "ok" else logging.WARNING,
            "AUDIT: %s %s %s (ip=%s, status=%s)",
            event_type.value, resource, action, source_ip, status,
        )

        return entry

    def query(
        self,
        event_type: AuditEventType | None = None,
        identity: str = "",
        source_ip: str = "",
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query audit log entries with filters.

        Args:
            event_type: Filter by event type.
            identity: Filter by identity.
            source_ip: Filter by source IP.
            since: Start time filter.
            until: End time filter.
            limit: Maximum entries to return.

        Returns:
            List of matching audit entries.
        """
        results: list[dict[str, Any]] = []
        log_files = sorted(self._log_dir.glob("audit-*.jsonl"), reverse=True)

        for log_file in log_files:
            try:
                with open(log_file, "r") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                        except json.JSONDecodeError:
                            continue

                        # Apply filters
                        if event_type and entry.get("type") != event_type.value:
                            continue
                        if identity and entry.get("identity") != identity:
                            continue
                        if source_ip and entry.get("source_ip") != source_ip:
                            continue
                        if since:
                            entry_time = datetime.fromisoformat(entry["timestamp"])
                            if entry_time < since:
                                continue
                        if until:
                            entry_time = datetime.fromisoformat(entry["timestamp"])
                            if entry_time > until:
                                continue

                        results.append(entry)
                        if len(results) >= limit:
                            return results
            except OSError:
                continue

        return results

    def verify_chain(self) -> tuple[bool, str]:
        """
        Verify the integrity of the audit log chain.

        Returns:
            (is_valid, message) tuple.
        """
        log_files = sorted(self._log_dir.glob("audit-*.jsonl"))
        previous_hash = ""

        for log_file in log_files:
            try:
                with open(log_file, "r") as f:
                    for line in f:
                        entry = json.loads(line.strip())
                        # Verify chain link
                        if entry.get("previous_hash", "") != previous_hash:
                            return False, f"Chain broken in {log_file.name}"
                        # Recompute hash
                        data = json.dumps({
                            "id": entry["id"],
                            "type": entry["type"],
                            "identity": entry["identity"],
                            "timestamp": entry["timestamp"],
                            "previous": entry["previous_hash"],
                        }, sort_keys=True)
                        expected_hash = hashlib.sha256(data.encode()).hexdigest()
                        if expected_hash != entry.get("hash", ""):
                            return False, f"Hash mismatch in entry {entry.get('id')}"
                        previous_hash = entry["hash"]
            except (OSError, json.JSONDecodeError) as e:
                return False, f"Error reading {log_file.name}: {e}"

        return True, "Chain verified successfully"
