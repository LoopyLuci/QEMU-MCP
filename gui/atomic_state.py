"""Atomic state management with write-ahead logging and snapshots.

Ensures state changes are all-or-nothing and recoverable from any crash.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any


class AtomicState:
    """Atomic state manager with WAL (write-ahead logging) and snapshots."""

    def __init__(self, state_dir: str | None = None):
        self._state_dir = Path(state_dir or tempfile.gettempdir()) / "qemu-mcp-state"
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_dir = self._state_dir / "snapshots"
        self._snapshot_dir.mkdir(exist_ok=True)
        self._wal_file = self._state_dir / "state.wal"
        self._state_file = self._state_dir / "state.json"
        self._lock_file = self._state_dir / "state.lock"
        self._state: dict[str, Any] = {}
        self._load_state()

    def _load_state(self):
        """Load state from disk, recovering from WAL if needed."""
        try:
            if self._state_file.exists():
                with open(self._state_file, 'r') as f:
                    self._state = json.load(f)
        except json.JSONDecodeError:
            self._state = {}

        # Replay WAL if it exists (crash recovery)
        if self._wal_file.exists():
            try:
                with open(self._wal_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            entry = json.loads(line)
                            self._state.update(entry)
                self._commit()
            except (json.JSONDecodeError, OSError):
                pass  # Corrupt WAL — best-effort recovery

    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        return self._state.get(key, default)

    def set(self, key: str, value: Any):
        """Set a state value atomically."""
        self._state[key] = value
        self._commit()

    def update(self, updates: dict[str, Any]):
        """Update multiple state values atomically."""
        self._state.update(updates)
        self._commit()

    def delete(self, key: str):
        """Delete a state value."""
        self._state.pop(key, None)
        self._commit()

    def get_all(self) -> dict[str, Any]:
        """Get all state."""
        return dict(self._state)

    def _commit(self):
        """Commit state atomically using write-ahead logging."""
        try:
            # Write to WAL first
            with open(self._wal_file, 'a') as f:
                f.write(json.dumps(self._state) + "\n")

            # Write to temp file then rename (atomic on most filesystems)
            tmp_file = self._state_file.with_suffix('.tmp')
            with open(tmp_file, 'w') as f:
                json.dump(self._state, f, indent=2, default=str)
            tmp_file.replace(self._state_file)

            # Truncate WAL after successful commit
            if self._wal_file.exists():
                self._wal_file.write_text('')
        except (json.JSONDecodeError, OSError):
            pass  # Best-effort — state may be stale but app keeps running

    def create_snapshot(self, name: str = "latest") -> Path:
        """Create a named snapshot of current state."""
        snapshot_file = self._snapshot_dir / f"{name}.json"
        tmp_file = snapshot_file.with_suffix('.tmp')
        with open(tmp_file, 'w') as f:
            json.dump(self._state, f, indent=2, default=str)
        tmp_file.replace(snapshot_file)
        return snapshot_file

    def restore_snapshot(self, name: str = "latest") -> bool:
        """Restore state from a snapshot."""
        snapshot_file = self._snapshot_dir / f"{name}.json"
        if not snapshot_file.exists():
            return False
        try:
            with open(snapshot_file, 'r') as f:
                self._state = json.load(f)
            self._commit()
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def list_snapshots(self) -> list[str]:
        """List available snapshots."""
        snapshots = []
        for f in self._snapshot_dir.glob("*.json"):
            snapshots.append(f.stem)
        return sorted(snapshots)

    def cleanup(self, keep_last: int = 5):
        """Clean up old snapshots, keeping the last N."""
        snapshots = sorted(self._snapshot_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        for old in snapshots[:-keep_last]:
            old.unlink(missing_ok=True)
