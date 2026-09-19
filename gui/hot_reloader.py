"""Hot reload — watches source files and reloads without losing state.

For PyQt5 GUI: since Qt objects can't be hot-reloaded directly, this
manages state persistence and component-level restart.
"""

from __future__ import annotations

import hashlib
import importlib
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("qemu-mcp.hotreload")


class HotReloader:
    """Watches source files and triggers reload on change."""

    def __init__(
        self,
        watch_dirs: list[str],
        on_reload: Callable,
        interval: float = 1.0,
        enabled: bool = True,
    ):
        self._watch_dirs = [Path(d) for d in watch_dirs]
        self._on_reload = on_reload
        self._interval = interval
        self._enabled = enabled
        self._file_hashes: dict[str, str] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._scan_files()

    def _scan_files(self) -> dict[str, str]:
        """Scan all watched files and compute hashes."""
        hashes = {}
        for watch_dir in self._watch_dirs:
            if not watch_dir.exists():
                continue
            for py_file in watch_dir.rglob("*.py"):
                try:
                    content = py_file.read_bytes()
                    rel_path = str(py_file.relative_to(watch_dir.parent))
                    hashes[rel_path] = hashlib.md5(content).hexdigest()
                except Exception:
                    pass
        return hashes

    def start(self):
        """Start watching for file changes."""
        if not self._enabled:
            logger.info("Hot reload disabled")
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("Hot reload started")

    def stop(self):
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _watch_loop(self):
        """Main watch loop."""
        while self._running:
            try:
                new_hashes = self._scan_files()
                changed = []

                for path, new_hash in new_hashes.items():
                    old_hash = self._file_hashes.get(path)
                    if old_hash and old_hash != new_hash:
                        changed.append(path)

                if changed:
                    logger.info("Detected changes in: %s", ", ".join(changed))
                    self._file_hashes = new_hashes
                    try:
                        self._on_reload(changed)
                    except Exception as e:
                        logger.error("Reload handler error: %s", e)
                else:
                    self._file_hashes = new_hashes

                time.sleep(self._interval)
            except Exception as e:
                logger.error("Watch error: %s", e)
                time.sleep(self._interval)

    def trigger_reload(self, changed_files: list[str] | None = None):
        """Manually trigger a reload."""
        if changed_files is None:
            changed_files = ["manual"]
        self._on_reload(changed_files)
