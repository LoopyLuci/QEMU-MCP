"""QMP bridge — async QMP client → PyQt5 signals, via threading.Thread."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from PyQt5.QtCore import QObject, pyqtSignal

from vm_mcp.config import VmMCPSettings, Secrets
from vm_mcp.qmp_client import QMPClient
from vm_mcp import qmp_client as qmp_mod

logger = logging.getLogger("qmcmcp.qmp_bridge")


# ── QMPBridge ─────────────────────────────────────────────────────────────────


class QMPBridge(QObject):
    """Wraps QMPClient for PyQt5 GUI usage.

    Uses ``threading.Thread`` (NOT QThread) so ``_run_loop()`` executes
    synchronously inside the worker thread.  ``_loop`` is guaranteed to be
    set before ``start()`` returns — no Qt ``started``-signal race.
    """

    # ── Signals ──────────────────────────────────────────────────────────────
    connected = pyqtSignal(bool)
    vm_status = pyqtSignal(dict)
    error = pyqtSignal(str)
    command_result = pyqtSignal(dict)

    # ── Constructor ──────────────────────────────────────────────────────────

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        from vm_mcp.config import Secrets

        self._secrets = Secrets.from_env()
        self._qmp_uri = self._build_uri()
        self._connected = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: QMPClient | None = None
        self._ever_connected = False
        self._loop_ready = threading.Event()

    # ── URI helpers ──────────────────────────────────────────────────────────

    def _build_uri(self) -> str:
        """Build QMP connection URI from settings."""
        if self._settings.qmp_socket_path:
            return f"unix:{self._settings.qmp_socket_path}"
        return f"tcp:{self._settings.qmp_host}:{self._settings.qmp_port}"

    def _rebuild_uri(self) -> str:
        """Re-read settings and build URI (call when settings may have changed)."""
        self._qmp_uri = self._build_uri()
        return self._qmp_uri

    # ── Thread lifecycle ─────────────────────────────────────────────────────

    def start(self):
        """Start the background thread + asyncio loop.

        ``threading.Thread`` guarantees ``_run_loop()`` runs synchronously
        inside the thread — ``_loop`` is always set before this returns.
        """
        if self._thread is not None and self._thread.is_alive():
            return
        self._loop_ready.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        # Wait for the event loop to be created (up to 5s)
        if not self._loop_ready.wait(timeout=5.0):
            raise RuntimeError("QMP bridge event loop failed to start within 5s")

    def stop(self):
        """Stop the event loop and thread."""
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        if self._client is not None:
            try:
                threading.Thread(
                    target=lambda: asyncio.run(self._client.disconnect()),
                    daemon=True,
                ).start()
            except Exception:
                pass
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

    # ── Internal: client management (async, runs on bg thread) ──────────────

    async def _get_client(self) -> QMPClient:
        """Get or create the QMP client, connecting if needed."""
        if self._client is None or not self._client.is_connected:
            self._client = QMPClient(
                uri=self._build_uri(),
                password=self._secrets.get_qmp_password(),
            )
            await self._client.connect()
            self._connected = True
            self._ever_connected = True
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
            if self._client is not None:
                await self._client.disconnect()
            self._client = None
            self._connected = False
            self.connected.emit(False)
        except Exception as e:
            logger.error("QMP disconnect failed: %s", e)
            self.error.emit(f"Disconnect failed: {e}")

    def get_status(self):
        """Query VM status synchronously. Returns dict or None on failure."""
        if self._loop is None:
            self.error.emit("QMP bridge not started")
            return None
        fut = asyncio.run_coroutine_threadsafe(self._status_impl(), self._loop)
        try:
            return fut.result(timeout=3.0)
        except Exception as e:
            logger.error("QMP get_status timed out: %s", e)
            self.error.emit(f"Status query timed out: {e}")
            return None

    async def _status_impl(self):
        try:
            client = await self._get_client()
            status = await qmp_mod.query_status(client)
            self.vm_status.emit(status)
            return status
        except Exception as e:
            logger.error("QMP get_status failed: %s", e)
            self.error.emit(f"Status query failed: {e}")
            return {}

    def send_command(self, command: str):
        """Send a raw QMP command (for console use)."""
        if self._loop is None:
            self.error.emit("QMP bridge not started")
            return
        asyncio.run_coroutine_threadsafe(self._send_command_impl(command), self._loop)

    async def _send_command_impl(self, command: str):
        try:
            client = await self._get_client()
            if command.startswith("{"):
                # Raw JSON
                import json
                msg = json.loads(command)
                result = await client.send(msg["execute"], msg.get("arguments"))
            else:
                result = await client.send(command)
            self.command_result.emit({"return": result})
        except Exception as e:
            logger.error("QMP command failed: %s", e)
            self.error.emit(f"Command failed: {e}")

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

    def stop_vm(self):
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


# ── Factory ───────────────────────────────────────────────────────────────────


def create_qmp_bridge(settings: VmMCPSettings) -> QMPBridge:
    """Create and start a QMP bridge."""
    bridge = QMPBridge(settings=settings)
    bridge.start()
    return bridge
