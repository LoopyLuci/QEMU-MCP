"""SSH bridge — async SSH client → PyQt5 signals, via threading.Thread."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from PyQt5.QtCore import QObject, pyqtSignal

from vm_mcp.config import VmMCPSettings, Secrets
from vm_mcp import ssh_client as ssh_mod

logger = logging.getLogger("qmcmcp.ssh_bridge")


class SSHBridge(QObject):
    """Wraps SSH module-level functions for PyQt5 GUI usage.

    Uses ``threading.Thread`` (NOT QThread) so the asyncio loop runs
    synchronously in the worker thread — no Qt signal race.
    """

    # ── Signals ──────────────────────────────────────────────────────────────
    command_output = pyqtSignal(str)
    connected = pyqtSignal(bool)
    connected_to = pyqtSignal(str, int, str)
    error = pyqtSignal(str)
    file_content = pyqtSignal(str)
    file_list = pyqtSignal(list)

    # ── Constructor ──────────────────────────────────────────────────────────

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._secrets = Secrets.from_env()
        self._connected = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ever_connected = False
        self._loop_ready = threading.Event()

    # ── Thread lifecycle ─────────────────────────────────────────────────────

    def start(self):
        """Start the background thread + asyncio loop."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._loop_ready.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if not self._loop_ready.wait(timeout=5.0):
            raise RuntimeError("SSH bridge event loop failed to start within 5s")

    def stop(self):
        """Stop the event loop and thread."""
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._connected = False

    def _run_loop(self):
        """Run the asyncio event loop — executes inside the worker thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        self._loop.run_forever()

    # ── Connection state ─────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Public API (called from GUI thread) ────────────────────────────────

    def connect_ssh(self):
        """Connect to the guest SSH server."""
        if self._loop is None or not self._loop.is_running():
            self.error.emit("SSH bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._connect_impl(), self._loop)

    async def _connect_impl(self):
        try:
            await ssh_mod._connect(self._secrets, self._settings)
            self._connected = True
            self._ever_connected = True
            self.connected.emit(True)
            host = self._settings.ssh_host
            port = self._settings.ssh_port
            user = self._settings.ssh_username
            self.connected_to.emit(host, port, user)
        except Exception as e:
            logger.error("SSH connect failed: %s", e)
            self._connected = False
            self.connected.emit(False)
            self.error.emit(f"SSH connection failed: {e}")

    def disconnect_ssh(self):
        """Disconnect from the guest SSH server."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._disconnect_impl(), self._loop)

    async def _disconnect_impl(self):
        try:
            await ssh_mod.disconnect()
            self._connected = False
            self.connected.emit(False)
        except Exception as e:
            logger.error("SSH disconnect failed: %s", e)
            self.error.emit(f"SSH disconnect failed: {e}")

    def run_command(self, command: str):
        """Run a command on the guest via SSH."""
        if self._loop is None:
            self.error.emit("SSH bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._run_command_impl(command), self._loop)

    async def _run_command_impl(self, command: str):
        try:
            output = await ssh_mod.run_guest_command(command, secrets=self._secrets, settings=self._settings)
            self.command_output.emit(output)
        except Exception as e:
            logger.error("SSH command failed: %s", e)
            self.error.emit(f"Command failed: {e}")

    def read_file(self, path: str):
        """Read a file from the guest via SSH."""
        if self._loop is None:
            self.error.emit("SSH bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._read_file_impl(path), self._loop)

    async def _read_file_impl(self, path: str):
        try:
            content, enc = await ssh_mod.read_guest_file(path, secrets=self._secrets, settings=self._settings)
            self.file_content.emit(content)
        except Exception as e:
            logger.error("SSH read_file failed: %s", e)
            self.error.emit(f"Read file failed: {e}")

    def write_file(self, path: str, content: str):
        """Write a file to the guest via SSH."""
        if self._loop is None:
            self.error.emit("SSH bridge not started")
            return
        asyncio.run_coroutine_threadsafe(
            self._write_file_impl(path, content), self._loop
        )

    async def _write_file_impl(self, path: str, content: str):
        try:
            await ssh_mod.write_guest_file(path, content, secrets=self._secrets, settings=self._settings)
            self.command_output.emit(f"Written: {path}")
        except Exception as e:
            logger.error("SSH write_file failed: %s", e)
            self.error.emit(f"Write file failed: {e}")

    def list_dir(self, path: str):
        """List a directory on the guest via SSH."""
        if self._loop is None:
            self.error.emit("SSH bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._list_dir_impl(path), self._loop)

    async def _list_dir_impl(self, path: str):
        try:
            entries = await ssh_mod.list_guest_directory(path, secrets=self._secrets, settings=self._settings)
            self.file_list.emit(entries)
        except Exception as e:
            logger.error("SSH list_dir failed: %s", e)
            self.error.emit(f"List dir failed: {e}")

    def remove_file(self, path: str):
        """Remove a file on the guest via SSH."""
        if self._loop is None:
            self.error.emit("SSH bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._remove_file_impl(path), self._loop)

    async def _remove_file_impl(self, path: str):
        try:
            await ssh_mod.remove_guest_path(path, secrets=self._secrets, settings=self._settings)
            self.command_output.emit(f"Removed: {path}")
        except Exception as e:
            logger.error("SSH remove_file failed: %s", e)
            self.error.emit(f"Remove file failed: {e}")


# ── Factory ───────────────────────────────────────────────────────────────────


def create_ssh_bridge(settings) -> SSHBridge:
    """Create and start an SSH bridge."""
    bridge = SSHBridge(settings=settings)
    bridge.start()
    return bridge
