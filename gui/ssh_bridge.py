"""SSH bridge — background thread async→PyQt5 signal wrapper.

Uses vm_mcp.ssh_client module-level async functions.
Runs all SSH operations on a background QThread with asyncio.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from vm_mcp.config import VmMCPSettings, Secrets
from vm_mcp import ssh_client as ssh_mod

logger = logging.getLogger("qmcmcp.ssh_bridge")


class SSHBridge(QObject):
    """Wraps vm_mcp.ssh_client for PyQt5 GUI usage.

    All operations are scheduled on a background thread's asyncio event
    loop via asyncio.run_coroutine_threadsafe().  Results come back via
    PyQt5 signals so the GUI stays responsive.
    """

    connected = pyqtSignal(bool)
    disconnected = pyqtSignal()
    command_output = pyqtSignal(str)
    command_result = pyqtSignal(dict)
    file_content = pyqtSignal(str)
    file_list = pyqtSignal(list)
    file_written = pyqtSignal(int)
    remove_result = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    connected_to = pyqtSignal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._connected = False
        self._thread: QThread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self):
        """Start the background thread and asyncio event loop."""
        if self._thread and self._thread.isRunning():
            return
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._run_loop)
        self._thread.start()

    def stop(self):
        """Stop the event loop and thread."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        self._connected = False

    def _run_loop(self):
        """Run the asyncio event loop on the thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Public API (called from GUI thread) ────────────────────────────────

    def connect(self):
        """Connect to the guest SSH.  Emits connected(True/False)."""
        if self._loop is None or not self._loop.is_running():
            self.error.emit("SSH bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._connect_impl(), self._loop)

    async def _connect_impl(self):
        try:
            result = await ssh_mod.run_guest_command(
                "echo connected",
                timeout=10,
                secrets=self._secrets,
                settings=self._settings,
            )
            ok = result.get("success", False)
            self._connected = ok
            if ok:
                host = self._settings.ssh_host
                port = self._settings.ssh_port
                user = self._settings.ssh_username
                self.connected.emit(True)
                self.connected_to.emit(f"{user}@{host}:{port}")
                self.progress.emit(f"SSH connected: {user}@{host}:{port}")
            else:
                msg = result.get("stderr", result.get("stdout", "unknown error"))
                self.connected.emit(False)
                self.error.emit(f"SSH connection failed: {msg}")
        except Exception as e:
            logger.error("SSH connect failed: %s", e)
            self._connected = False
            self.connected.emit(False)
            self.error.emit(f"SSH connection failed: {e}")

    def disconnect(self):
        """Disconnect from SSH."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._disconnect_impl(), self._loop)

    async def _disconnect_impl(self):
        try:
            await ssh_mod._close()
            self._connected = False
            self.disconnected.emit()
            self.connected.emit(False)
        except Exception as e:
            logger.error("SSH disconnect error: %s", e)

    def run_command(self, command: str, timeout: int = 30, max_output: int = 10000):
        """Run a command on the guest.  Emits command_output(stdout)."""
        if self._loop is None:
            self.error.emit("SSH bridge not started")
            return
        if not self._connected:
            self.error.emit("Not connected to SSH")
            return
        asyncio.run_coroutine_threadsafe(
            self._run_command_impl(command, timeout, max_output), self._loop
        )

    async def _run_command_impl(self, command: str, timeout: int, max_output: int):
        try:
            result = await ssh_mod.run_guest_command(
                command, timeout=timeout, secrets=self._secrets, settings=self._settings
            )
            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            if stdout and len(stdout) > max_output:
                stdout = stdout[:max_output] + "\n...[truncated]"
            self.command_output.emit(stdout)
            if stderr:
                self.command_output.emit(stderr)
            self.command_result.emit(result)
        except Exception as e:
            logger.error("SSH command '%s' failed: %s", command, e)
            self.error.emit(f"Command failed: {e}")
            self.command_result.emit({"exit_code": -1, "stdout": "", "stderr": str(e), "success": False})

    def read_file(self, path: str, max_size: int = 100000):
        """Read a file from the guest.  Emits file_content(content)."""
        if self._loop is None:
            self.error.emit("SSH bridge not started")
            return
        if not self._connected:
            self.error.emit("Not connected to SSH")
            return
        asyncio.run_coroutine_threadsafe(
            self._read_file_impl(path, max_size), self._loop
        )

    async def _read_file_impl(self, path: str, max_size: int):
        try:
            content = await ssh_mod.read_guest_file(
                path, max_bytes=max_size, secrets=self._secrets, settings=self._settings
            )
            if len(content) > max_size:
                content = content[:max_size] + "\n...[truncated]"
            self.file_content.emit(content)
        except Exception as e:
            logger.error("SSH read_file '%s' failed: %s", path, e)
            self.error.emit(f"File read failed: {e}")

    def write_file(self, path: str, content: str, create_parents: bool = False):
        """Write a file to the guest.  Emits file_written(bytes)."""
        if self._loop is None:
            self.error.emit("SSH bridge not started")
            return
        if not self._connected:
            self.error.emit("Not connected to SSH")
            return
        asyncio.run_coroutine_threadsafe(
            self._write_file_impl(path, content, create_parents), self._loop
        )

    async def _write_file_impl(self, path: str, content: str, create_parents: bool):
        try:
            bytes_written = await ssh_mod.write_guest_file(
                path, content, secrets=self._secrets, settings=self._settings
            )
            self.file_written.emit(bytes_written)
        except Exception as e:
            logger.error("SSH write_file '%s' failed: %s", path, e)
            self.error.emit(f"File write failed: {e}")

    def list_dir(self, path: str, pattern: str = ""):
        """List a directory.  Emits file_list(list)."""
        if self._loop is None:
            self.error.emit("SSH bridge not started")
            return
        if not self._connected:
            self.error.emit("Not connected to SSH")
            return
        asyncio.run_coroutine_threadsafe(
            self._list_dir_impl(path), self._loop
        )

    async def _list_dir_impl(self, path: str):
        try:
            entries = await ssh_mod.list_guest_directory(
                path, detail=True, secrets=self._secrets, settings=self._settings
            )
            result: list[dict[str, Any]] = []
            for entry in entries:
                result.append({
                    "name": entry["name"],
                    "type": entry["type"],
                    "size": entry.get("size", 0),
                    "mtime": entry.get("mtime", ""),
                    "path": f"{path.rstrip('/')}/{entry['name']}",
                })
            self.file_list.emit(result)
        except Exception as e:
            logger.error("SSH list_dir '%s' failed: %s", path, e)
            self.error.emit(f"Directory list failed: {e}")

    def remove_file(self, path: str, recursive: bool = False):
        """Remove a file/directory."""
        if self._loop is None:
            self.error.emit("SSH bridge not started")
            return
        if not self._connected:
            self.error.emit("Not connected to SSH")
            return
        asyncio.run_coroutine_threadsafe(
            self._remove_file_impl(path, recursive), self._loop
        )

    async def _remove_file_impl(self, path: str, recursive: bool):
        try:
            result = await ssh_mod.remove_guest_path(
                path, recursive=recursive, secrets=self._secrets, settings=self._settings
            )
            self.remove_result.emit(result)
        except Exception as e:
            logger.error("SSH remove_file '%s' failed: %s", path, e)
            self.error.emit(f"File remove failed: {e}")


def create_ssh_bridge(settings) -> SSHBridge:
    """Create and start an SSH bridge."""
    bridge = SSHBridge(settings=settings)
    bridge.start()
    return bridge
