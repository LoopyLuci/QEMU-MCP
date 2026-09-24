"""Process Guardian — monitors the GUI process and auto-restarts on crash.

Keeps a backup instance ready for seamless failover.
"""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("qemu-mcp.guardian")


class ProcessGuardian:
    """Monitors GUI process, restarts on crash, keeps backup ready."""

    def __init__(
        self,
        main_script: str,
        backup_count: int = 1,
        max_restarts: int = 10,
        restart_window: int = 60,
        health_check_interval: float = 2.0,
    ):
        self._main_script = main_script
        self._backup_count = backup_count
        self._max_restarts = max_restarts
        self._restart_window = restart_window
        self._health_check_interval = health_check_interval

        self._primary_process: Optional[subprocess.Popen] = None
        self._backup_processes: list[subprocess.Popen] = []
        self._restart_times: list[float] = []
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._on_crash: Optional[Callable] = None
        self._on_restart: Optional[Callable] = None
        self._lock = threading.Lock()

    def set_crash_callback(self, callback: Callable):
        """Set callback for crash events."""
        self._on_crash = callback

    def set_restart_callback(self, callback: Callable):
        """Set callback for restart events."""
        self._on_restart = callback

    def start(self):
        """Start the guardian and primary process."""
        self._running = True
        self._start_primary()
        self._start_backups()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Process guardian started")

    def stop(self):
        """Stop the guardian and all processes."""
        self._running = False
        self._kill_primary()
        self._kill_backups()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Process guardian stopped")

    def restart_primary(self):
        """Restart the primary process."""
        with self._lock:
            self._kill_primary()
            self._start_primary()

    def _start_primary(self):
        """Start the primary GUI process."""
        try:
            env = os.environ.copy()
            env["VM_HARNESS_ROLE"] = "primary"
            self._primary_process = subprocess.Popen(
                [sys.executable, self._main_script],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.info("Primary process started (PID %d)", self._primary_process.pid)
        except Exception as e:
            logger.error("Failed to start primary: %s", e)

    def _start_backups(self):
        """Start backup processes in standby mode."""
        for i in range(self._backup_count):
            try:
                env = os.environ.copy()
                env["VM_HARNESS_ROLE"] = "backup"
                env["VM_HARNESS_BACKUP_ID"] = str(i)
                backup = subprocess.Popen(
                    [sys.executable, self._main_script, "--standby"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self._backup_processes.append(backup)
                logger.info("Backup %d started (PID %d)", i, backup.pid)
            except (RuntimeError, OSError) as e:
                logger.error("Failed to start backup %d: %s", i, e)

    def _kill_primary(self):
        """Kill the primary process."""
        if self._primary_process:
            try:
                self._primary_process.terminate()
                self._primary_process.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                self._primary_process.kill()
            self._primary_process = None

    def _kill_backups(self):
        """Kill all backup processes."""
        for backup in self._backup_processes:
            try:
                backup.terminate()
                backup.wait(timeout=3)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                backup.kill()
        self._backup_processes.clear()

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                self._check_primary()
                self._cleanup_restart_window()
                time.sleep(self._health_check_interval)
            except Exception as e:
                logger.error("Monitor error: %s", e)

    def _check_primary(self):
        """Check if primary process is alive."""
        if self._primary_process is None:
            self._handle_crash()
            return

        retcode = self._primary_process.poll()
        if retcode is not None:
            logger.warning("Primary process exited with code %d", retcode)
            self._handle_crash()

    def _handle_crash(self):
        """Handle primary process crash."""
        if self._on_crash:
            try:
                self._on_crash()
            except (RuntimeError, OSError):
                pass

        if not self._should_restart():
            logger.error("Max restarts reached, not restarting")
            return

        self._restart_times.append(time.time())

        # Promote a backup to primary
        if self._backup_processes:
            self._promote_backup()
        else:
            self._start_primary()

        if self._on_restart:
            try:
                self._on_restart()
            except (RuntimeError, OSError):
                pass

    def _promote_backup(self):
        """Promote a backup process to primary."""
        if not self._backup_processes:
            return
        backup = self._backup_processes.pop(0)
        self._primary_process = backup
        logger.info("Promoted backup (PID %d) to primary", backup.pid)

        # Start a new backup to replace the promoted one
        try:
            env = os.environ.copy()
            env["VM_HARNESS_ROLE"] = "backup"
            env["VM_HARNESS_BACKUP_ID"] = str(len(self._backup_processes))
            new_backup = subprocess.Popen(
                [sys.executable, self._main_script, "--standby"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._backup_processes.append(new_backup)
        except Exception as e:
            logger.error("Failed to start replacement backup: %s", e)

    def _should_restart(self) -> bool:
        """Check if we should restart (rate limiting)."""
        now = time.time()
        self._restart_times = [t for t in self._restart_times if now - t < self._restart_window]
        return len(self._restart_times) < self._max_restarts

    def _cleanup_restart_window(self):
        """Clean up old restart timestamps."""
        now = time.time()
        self._restart_times = [t for t in self._restart_times if now - t < self._restart_window]

    @property
    def is_healthy(self) -> bool:
        """Check if primary process is healthy."""
        return (
            self._primary_process is not None
            and self._primary_process.poll() is None
        )

    @property
    def primary_pid(self) -> Optional[int]:
        """Get primary process PID."""
        return self._primary_process.pid if self._primary_process else None
