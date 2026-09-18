"""QMP bridge — background thread async→PyQt5 signal wrapper.

Uses vm_mcp.qmp_client QMPClient + module-level helpers.
Runs all QMP operations on a background QThread with asyncio.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from vm_mcp.config import VmMCPSettings, Secrets
from vm_mcp.qmp_client import QMPClient
from vm_mcp import qmp_client as qmp_mod

logger = logging.getLogger("qmcmcp.qmp_bridge")


class QMPBridge(QObject):
    """Wraps QMPClient for PyQt5 GUI usage.

    All operations are scheduled on a background thread's asyncio event
    loop via asyncio.run_coroutine_threadsafe().  Results come back via
    PyQt5 signals so the GUI stays responsive.
    """

    connected = pyqtSignal(bool)
    vm_status = pyqtSignal(dict)
    error = pyqtSignal(str)
    command_result = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client: QMPClient | None = None
        self._thread: QThread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._settings = VmMCPSettings()
        self._secrets = Secrets.from_env()
        self._secrets_dotenv = Secrets.from_dotenv()
        if self._secrets_dotenv.has_any_secret():
            self._secrets = self._secrets_dotenv
        self._qmp_uri = self._build_uri()
        self._connected = False

    def _build_uri(self) -> str:
        """Build QMP connection URI from settings."""
        if self._settings.qmp_socket_path:
            return f"unix:{self._settings.qmp_socket_path}"
        return f"tcp:{self._settings.qmp_host}:{self._settings.qmp_port}"

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
        if self._client:
            try:
                asyncio.run(self._client.disconnect())
            except Exception:
                pass
        self._connected = False

    def _run_loop(self):
        """Run the asyncio event loop on the thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Internal: client management (async, runs on bg thread) ─────────────

    async def _get_client(self) -> QMPClient:
        """Get or create the QMP client, connecting if needed."""
        if self._client is None or not self._client.is_connected:
            self._client = QMPClient(uri=self._qmp_uri, password=self._secrets.get_qmp_password())
            await self._client.connect()
            self._connected = True
            self.connected.emit(True)
        return self._client

    # ── Public API (called from GUI thread) ────────────────────────────────

    def connect(self):
        """Connect to QMP.  Emits connected(True/False)."""
        if self._loop is None or not self._loop.is_running():
            self.error.emit("QMP bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._connect_impl(), self._loop)

    async def _connect_impl(self):
        try:
            await self._get_client()
        except Exception as e:
            logger.error("QMP connect failed: %s", e)
            self._connected = False
            self.connected.emit(False)
            self.error.emit(f"Connection failed: {e}")

    def disconnect(self):
        """Disconnect from QMP."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._disconnect_impl(), self._loop)

    async def _disconnect_impl(self):
        try:
            if self._client:
                await self._client.disconnect()
            self._client = None
            self._connected = False
            self.connected.emit(False)
        except Exception as e:
            logger.error("QMP disconnect failed: %s", e)
            self.error.emit(f"Disconnect failed: {e}")

    def get_status(self):
        """Query VM status.  Emits vm_status(dict)."""
        if self._loop is None:
            self.error.emit("QMP bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._status_impl(), self._loop)

    async def _status_impl(self):
        try:
            client = await self._get_client()
            status = await qmp_mod.query_status(client)
            self.vm_status.emit(status)
        except Exception as e:
            logger.error("QMP get_status failed: %s", e)
            self.error.emit(f"Status query failed: {e}")

    def system_reset(self):
        """Reset the VM (warm reboot)."""
        if self._loop is None:
            self.error.emit("QMP bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._system_reset_impl(), self._loop)

    async def _system_reset_impl(self):
        try:
            client = await self._get_client()
            await qmp_mod.system_reset(client)
            self.command_result.emit({"return": "reset issued"})
        except Exception as e:
            logger.error("QMP reset failed: %s", e)
            self.error.emit(f"Reset failed: {e}")

    def system_powerdown(self):
        """Power down the VM (graceful shutdown)."""
        if self._loop is None:
            self.error.emit("QMP bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._powerdown_impl(), self._loop)

    async def _powerdown_impl(self):
        try:
            client = await self._get_client()
            await qmp_mod.system_powerdown(client)
            self.command_result.emit({"return": "powerdown issued"})
        except Exception as e:
            logger.error("QMP powerdown failed: %s", e)
            self.error.emit(f"Powerdown failed: {e}")

    def cont(self):
        """Continue a suspended VM (resume)."""
        if self._loop is None:
            self.error.emit("QMP bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._cont_impl(), self._loop)

    async def _cont_impl(self):
        try:
            client = await self._get_client()
            await qmp_mod.cont(client)
            self.command_result.emit({"return": "cont issued"})
        except Exception as e:
            logger.error("QMP cont failed: %s", e)
            self.error.emit(f"Resume failed: {e}")

    def stop(self):
        """Stop the VM (suspend CPU)."""
        if self._loop is None:
            self.error.emit("QMP bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._stop_impl(), self._loop)

    async def _stop_impl(self):
        try:
            client = await self._get_client()
            await qmp_mod.stop(client)
            self.command_result.emit({"return": "stop issued"})
        except Exception as e:
            logger.error("QMP stop failed: %s", e)
            self.error.emit(f"Stop failed: {e}")

    def eject_cdrom(self):
        """Eject the CD-ROM device."""
        if self._loop is None:
            self.error.emit("QMP bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._eject_impl(), self._loop)

    async def _eject_impl(self):
        try:
            client = await self._get_client()
            await qmp_mod.eject_device(client, "ide0-cd0")
            self.command_result.emit({"return": "eject issued"})
        except Exception as e:
            logger.error("QMP eject failed: %s", e)
            self.error.emit(f"Eject failed: {e}")


def create_qmp_bridge() -> QMPBridge:
    """Create and start a QMP bridge."""
    bridge = QMPBridge()
    bridge.start()
    return bridge
