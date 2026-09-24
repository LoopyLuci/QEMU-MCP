"""VM-Harness Resilience System — crash-proof, self-healing, atomic, hot-reload.

Components:
- CrashHandler: sys.excepthook + signal handlers + structured crash logs
- AtomicState: write-ahead logging for crash recovery
- ProcessGuardian: monitors main process, auto-restarts on crash
- HotReloader: watches source files for development-time code reloading
- FailoverManager: live backup process for zero-downtime failover
- HealthChecker: periodic health verification with auto-recovery
"""

from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import shutil
import signal
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("vmharness.resilience")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / ".vmharness_state"
LOG_DIR = PROJECT_ROOT / "logs"
BACKUP_DIR = PROJECT_ROOT / ".vmharness_backup"

# Ensure directories exist
STATE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Crash Handler
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CrashReport:
    """Structured crash report."""
    timestamp: str
    exception_type: str
    exception_message: str
    traceback: str
    pid: int
    thread: str
    memory_mb: float
    state_file: str = ""


class CrashHandler:
    """Global exception handler — catches all unhandled exceptions."""

    _instance: Optional["CrashHandler"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._crash_count = 0
        self._max_crashes = 5
        self._crash_window = 60  # seconds
        self._crash_timestamps: list[float] = []
        self._recovery_callbacks: list[Callable] = []
        self._original_excepthook = sys.excepthook

        # Install handlers
        sys.excepthook = self._handle_exception
        self._setup_signal_handlers()

        logger.info("CrashHandler initialized")

    def _setup_signal_handlers(self):
        """Install signal handlers for graceful shutdown."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._signal_handler)
            except (OSError, ValueError):
                pass

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info("Received signal %d — graceful shutdown", signum)
        self._run_recovery_callbacks()
        sys.exit(0)

    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """Handle unhandled exceptions — log crash report and attempt recovery."""
        self._crash_count += 1
        now = time.time()
        self._crash_timestamps.append(now)
        self._crash_timestamps = [t for t in self._crash_timestamps if now - t < self._crash_window]

        # Create crash report
        report = CrashReport(
            timestamp=datetime.now().isoformat(),
            exception_type=exc_type.__name__,
            exception_message=str(exc_value),
            traceback="".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            pid=os.getpid(),
            thread=threading.current_thread().name,
            memory_mb=self._get_memory_mb(),
        )

        # Save crash report
        self._save_crash_report(report)

        # Log crash
        logger.error("CRASH #%d: %s: %s", self._crash_count, exc_type.__name__, exc_value)
        logger.error("Crash report saved to: %s", report.state_file)

        # Run recovery callbacks
        self._run_recovery_callbacks()

        # If too many crashes, exit cleanly
        if self._crash_count >= self._max_crashes:
            logger.critical("Too many crashes (%d) — exiting", self._crash_count)
            sys.exit(1)

    def _save_crash_report(self, report: CrashReport):
        """Save crash report to disk."""
        crash_file = LOG_DIR / f"crash_{report.timestamp.replace(':', '-').replace('.', '-')}.json"
        report.state_file = str(crash_file)
        with open(crash_file, "w") as f:
            json.dump(asdict(report), f, indent=2, default=str)

    def _get_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0

    def _run_recovery_callbacks(self):
        """Run all registered recovery callbacks."""
        for callback in self._recovery_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error("Recovery callback failed: %s", e)

    def register_recovery(self, callback: Callable):
        """Register a recovery callback."""
        self._recovery_callbacks.append(callback)


# ═══════════════════════════════════════════════════════════════════════════════
# Atomic State (Write-Ahead Logging)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class VMState:
    """Atomic VM state for crash recovery."""
    name: str
    status: str  # "running", "stopped", "paused", "error"
    pid: Optional[int] = None
    config: dict = field(default_factory=dict)
    last_updated: str = ""
    checksum: str = ""

    def compute_checksum(self) -> str:
        """Compute checksum for integrity verification."""
        data = json.dumps(asdict(self), sort_keys=True, default=str)
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class AtomicState:
    """Atomic state management with write-ahead logging."""

    def __init__(self):
        self._state_file = STATE_DIR / "vm_state.json"
        self._wal_file = STATE_DIR / "vm_state.wal"
        self._lock = threading.Lock()
        self._states: dict[str, VMState] = {}
        self._load()

    def _load(self):
        """Load state from disk, replaying WAL if needed."""
        # First, try the main state file
        if self._state_file.exists():
            try:
                with open(self._state_file) as f:
                    data = json.load(f)
                for name, state_data in data.items():
                    self._states[name] = VMState(**state_data)
                logger.info("Loaded %d VM states from %s", len(self._states), self._state_file)
            except Exception as e:
                logger.warning("Failed to load state file: %s", e)

        # Replay WAL if it exists
        if self._wal_file.exists():
            try:
                with open(self._wal_file) as f:
                    for line in f:
                        if line.strip():
                            entry = json.loads(line)
                            vm_state = VMState(**entry)
                            self._states[vm_state.name] = vm_state
                logger.info("Replayed WAL: %d states", len(self._states))
                self._wal_file.unlink()  # Clear WAL after replay
            except Exception as e:
                logger.warning("Failed to replay WAL: %s", e)

    def save(self, vm_state: VMState):
        """Save state atomically (write to WAL, then commit)."""
        with self._lock:
            vm_state.last_updated = datetime.now().isoformat()
            vm_state.checksum = vm_state.compute_checksum()

            # Write to WAL first (atomic append)
            with open(self._wal_file, "a") as f:
                f.write(json.dumps(asdict(vm_state), default=str) + "\n")
                f.flush()
                os.fsync(f.fileno())

            # Update in-memory state
            self._states[vm_state.name] = vm_state

            # Commit to main state file
            self._commit()

    def _commit(self):
        """Commit all states to the main state file."""
        try:
            # Write to temp file first
            temp_file = STATE_DIR / "vm_state.tmp"
            data = {name: asdict(state) for name, state in self._states.items()}
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            temp_file.replace(self._state_file)

            # Clear WAL
            if self._wal_file.exists():
                self._wal_file.unlink()

        except Exception as e:
            logger.error("Failed to commit state: %s", e)

    def get(self, name: str) -> Optional[VMState]:
        """Get VM state by name."""
        return self._states.get(name)

    def get_all(self) -> dict[str, VMState]:
        """Get all VM states."""
        return dict(self._states)

    def verify_integrity(self) -> list[str]:
        """Verify checksums of all states. Returns list of corrupted states."""
        corrupted = []
        for name, state in self._states.items():
            expected = state.compute_checksum()
            if state.checksum and state.checksum != expected:
                corrupted.append(name)
        return corrupted

    def recover(self):
        """Recover from corrupted state using WAL."""
        corrupted = self.verify_integrity()
        if corrupted:
            logger.warning("Corrupted states detected: %s", corrupted)
            for name in corrupted:
                self._states.pop(name, None)
            self._load()  # Reload from WAL
            self._commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Process Guardian
# ═══════════════════════════════════════════════════════════════════════════════

class ProcessGuardian:
    """Monitors the main process and auto-restarts on crash."""

    def __init__(self, check_interval: float = 5.0):
        self._check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._restart_count = 0
        self._max_restarts = 3
        self._last_restart = 0.0
        self._restart_window = 300  # 5 minutes
        self._health_callback: Optional[Callable[[], bool]] = None
        self._restart_callback: Optional[Callable[[], None]] = None

    def start(self):
        """Start the guardian thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._guard_loop, daemon=True)
        self._thread.start()
        logger.info("ProcessGuardian started")

    def stop(self):
        """Stop the guardian thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("ProcessGuardian stopped")

    def set_health_callback(self, callback: Callable[[], bool]):
        """Set health check callback. Returns True if healthy."""
        self._health_callback = callback

    def set_restart_callback(self, callback: Callable[[], None]):
        """Set restart callback."""
        self._restart_callback = callback

    def _guard_loop(self):
        """Main guardian loop."""
        while self._running:
            try:
                if self._health_callback and not self._health_callback():
                    logger.warning("Health check failed — initiating recovery")
                    self._handle_failure()
            except Exception as e:
                logger.error("Guardian health check error: %s", e)

            time.sleep(self._check_interval)

    def _handle_failure(self):
        """Handle a health check failure."""
        now = time.time()
        if now - self._last_restart > self._restart_window:
            self._restart_count = 0

        if self._restart_count >= self._max_restarts:
            logger.critical("Max restarts reached — giving up")
            self._running = False
            return

        self._restart_count += 1
        self._last_restart = now

        logger.info("Restarting process (attempt %d/%d)", self._restart_count, self._max_restarts)

        if self._restart_callback:
            try:
                self._restart_callback()
            except Exception as e:
                logger.error("Restart callback failed: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# Hot Reloader
# ═══════════════════════════════════════════════════════════════════════════════

class HotReloader:
    """Watches source files for changes and triggers reload."""

    def __init__(self, watch_paths: Optional[list[Path]] = None, debounce: float = 1.0):
        self._watch_paths = watch_paths or [
            PROJECT_ROOT / "gui",
            PROJECT_ROOT / "src",
        ]
        self._debounce = debounce
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._file_hashes: dict[Path, str] = {}
        self._reload_callback: Optional[Callable[[list[Path]], None]] = None
        self._last_reload = 0.0

    def start(self):
        """Start watching for file changes."""
        if self._running:
            return
        self._running = True
        self._scan_files()  # Initial scan
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("HotReloader started (watching %d paths)", len(self._watch_paths))

    def stop(self):
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("HotReloader stopped")

    def set_reload_callback(self, callback: Callable[[list[Path]], None]):
        """Set callback for file changes. Receives list of changed files."""
        self._reload_callback = callback

    def _scan_files(self) -> dict[Path, str]:
        """Scan all watched files and return their hashes."""
        hashes = {}
        for path in self._watch_paths:
            if path.is_file():
                hashes[path] = self._file_hash(path)
            elif path.is_dir():
                for f in path.rglob("*.py"):
                    hashes[f] = self._file_hash(f)
        return hashes

    def _file_hash(self, path: Path) -> str:
        """Compute file hash."""
        try:
            return hashlib.md5(path.read_bytes()).hexdigest()
        except Exception:
            return ""

    def _watch_loop(self):
        """Main watch loop."""
        while self._running:
            try:
                current_hashes = self._scan_files()
                changed = []

                for path, hash_val in current_hashes.items():
                    old_hash = self._file_hashes.get(path, "")
                    if old_hash and old_hash != hash_val:
                        changed.append(path)

                # Check for new files
                new_files = set(current_hashes.keys()) - set(self._file_hashes.keys())
                for path in new_files:
                    changed.append(path)

                if changed and time.time() - self._last_reload > self._debounce:
                    self._last_reload = time.time()
                    logger.info("Hot reload: %d files changed", len(changed))
                    if self._reload_callback:
                        try:
                            self._reload_callback(changed)
                        except Exception as e:
                            logger.error("Reload callback failed: %s", e)

                self._file_hashes = current_hashes

            except Exception as e:
                logger.error("HotReloader error: %s", e)

            time.sleep(1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Failover Manager
# ═══════════════════════════════════════════════════════════════════════════════

class FailoverManager:
    """Manages live backup process for zero-downtime failover."""

    def __init__(self):
        self._primary_pid: Optional[int] = None
        self._backup_pid: Optional[int] = None
        self._is_backup = False
        self._failover_event = threading.Event()
        self._lock = threading.Lock()

    def register_primary(self, pid: int):
        """Register the primary process PID."""
        with self._lock:
            self._primary_pid = pid

    def register_backup(self, pid: int):
        """Register the backup process PID."""
        with self._lock:
            self._backup_pid = pid

    def promote_backup(self):
        """Promote backup to primary."""
        with self._lock:
            if self._backup_pid:
                logger.info("Promoting backup (PID %d) to primary", self._backup_pid)
                self._primary_pid = self._backup_pid
                self._backup_pid = None
                self._is_backup = False
                self._failover_event.set()

    def trigger_failover(self):
        """Trigger a failover to the backup process."""
        with self._lock:
            if self._backup_pid is None:
                logger.warning("No backup process available for failover")
                return False

            logger.info("FAILOVER: primary (PID %d) -> backup (PID %d)", self._primary_pid, self._backup_pid)
            self.promote_backup()
            return True

    def get_primary(self) -> Optional[int]:
        """Get current primary PID."""
        with self._lock:
            return self._primary_pid

    def is_healthy(self) -> bool:
        """Check if primary process is healthy."""
        with self._lock:
            if self._primary_pid is None:
                return False
            try:
                import psutil
                return psutil.pid_exists(self._primary_pid)
            except Exception:
                return False


# ═══════════════════════════════════════════════════════════════════════════════
# Health Checker
# ═══════════════════════════════════════════════════════════════════════════════

class HealthChecker:
    """Periodic health checks with auto-recovery."""

    def __init__(self, check_interval: float = 10.0):
        self._check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._checks: list[Callable[[], bool]] = []
        self._recovery_actions: list[Callable[[], None]] = []
        self._consecutive_failures = 0
        self._max_failures = 3

    def start(self):
        """Start health checking."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._health_loop, daemon=True)
        self._thread.start()
        logger.info("HealthChecker started")

    def stop(self):
        """Stop health checking."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("HealthChecker stopped")

    def add_check(self, callback: Callable[[], bool]):
        """Add a health check. Returns True if healthy."""
        self._checks.append(callback)

    def add_recovery(self, callback: Callable[[], None]):
        """Add a recovery action to run on failure."""
        self._recovery_actions.append(callback)

    def _health_loop(self):
        """Main health check loop."""
        while self._running:
            try:
                all_healthy = True
                for check in self._checks:
                    try:
                        if not check():
                            all_healthy = False
                            break
                    except Exception as e:
                        logger.error("Health check error: %s", e)
                        all_healthy = False
                        break

                if not all_healthy:
                    self._consecutive_failures += 1
                    logger.warning("Health check failed (%d/%d)", self._consecutive_failures, self._max_failures)

                    if self._consecutive_failures >= self._max_failures:
                        logger.error("Max health failures reached — running recovery")
                        self._run_recovery()
                        self._consecutive_failures = 0
                else:
                    self._consecutive_failures = 0

            except Exception as e:
                logger.error("Health check loop error: %s", e)

            time.sleep(self._check_interval)

    def _run_recovery(self):
        """Run all recovery actions."""
        for action in self._recovery_actions:
            try:
                action()
            except Exception as e:
                logger.error("Recovery action failed: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# Self-Healing Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

class SelfHealingOrchestrator:
    """Orchestrates all resilience components."""

    def __init__(self):
        self.crash_handler = CrashHandler()
        self.atomic_state = AtomicState()
        self.guardian = ProcessGuardian()
        self.hot_reloader = HotReloader()
        self.failover = FailoverManager()
        self.health = HealthChecker()

        # Wire up components
        self._wire_components()

    def _wire_components(self):
        """Wire resilience components together."""
        # Crash handler recovery → atomic state recovery
        self.crash_handler.register_recovery(self._on_crash_recovery)

        # Guardian health check → health checker
        self.guardian.set_health_callback(self._health_check)
        self.guardian.set_restart_callback(self._restart)

        # Health checker → atomic state recovery
        self.health.add_recovery(self._on_health_recovery)

    def _on_crash_recovery(self):
        """Recovery action after crash."""
        logger.info("Running crash recovery")
        self.atomic_state.recover()

    def _health_check(self) -> bool:
        """Check if the process is healthy."""
        try:
            # Check if main window is visible
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, "VM-Harness")
            if hwnd:
                return True
            return False
        except Exception:
            return True  # Assume healthy if check fails

    def _restart(self):
        """Restart the process."""
        logger.info("Restarting process")
        # Signal for restart
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _on_health_recovery(self):
        """Recovery action for health check failure."""
        logger.info("Running health recovery")
        self.atomic_state.recover()

    def start(self):
        """Start all resilience components."""
        logger.info("Starting SelfHealingOrchestrator")
        self.guardian.start()
        self.health.start()

        # Hot reloader only in dev mode
        if os.environ.get("VM_HARNESS_DEV"):
            self.hot_reloader.start()

    def stop(self):
        """Stop all resilience components."""
        logger.info("Stopping SelfHealingOrchestrator")
        self.guardian.stop()
        self.health.stop()
        self.hot_reloader.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience: get global orchestrator instance
# ═══════════════════════════════════════════════════════════════════════════════

_orchestrator: Optional[SelfHealingOrchestrator] = None


def get_orchestrator() -> SelfHealingOrchestrator:
    """Get the global self-healing orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SelfHealingOrchestrator()
    return _orchestrator
