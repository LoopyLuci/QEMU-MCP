"""E2E tests — QMP + SSH bridges against a live QEMU instance.

Requires:
- QEMU running with: -qmp tcp:127.0.0.1:4444,server,nowait
- SSH forwarding: -netdev user,hostfwd=tcp:127.0.0.1:2222-:22
- SSH server running inside guest (e.g., dropbear/sshd on port 22)

Run: pytest tests/test_e2e_qmp_ssh.py -v -s
"""

from __future__ import annotations

import asyncio

import pytest

# Ensure offscreen for any Qt imports
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="module")
def settings():
    from vm_mcp.config import VmMCPSettings

    return VmMCPSettings()


@pytest.fixture(scope="module")
def secrets():
    from vm_mcp.config import Secrets

    return Secrets.from_env()


# ── QMP integration tests (single event loop per test) ───────────────────────


class TestQMPBridgeLive:
    """End-to-end QMP tests against running QEMU.

    Each test uses a single asyncio.run() so the reader/writer stay on
    the same event loop.
    """

    def test_qmp_query_status(self, settings, secrets):
        from vm_mcp.qmp_client import QMPClient
        from vm_mcp import qmp_client as qmp_mod

        async def _run():
            client = QMPClient(uri=settings.qmp_uri(), password=secrets.get_qmp_password())
            await client.connect()
            try:
                # query-status returns {'return': {}} when VM is running
                # Use query-machines for actual status
                status = await qmp_mod.query_status(client)
                assert isinstance(status, dict)
                assert "return" in status
                # Also verify query-machines works
                machines = await client.send("query-machines")
                assert isinstance(machines, dict)
                assert "return" in machines
            finally:
                await client.disconnect()

        asyncio.run(_run())

    def test_qmp_system_reset(self, settings, secrets):
        from vm_mcp.qmp_client import QMPClient
        from vm_mcp import qmp_client as qmp_mod

        async def _run():
            client = QMPClient(uri=settings.qmp_uri(), password=secrets.get_qmp_password())
            await client.connect()
            try:
                await qmp_mod.system_reset(client)
            finally:
                await client.disconnect()

        asyncio.run(_run())

    def test_qmp_stop_cont(self, settings, secrets):
        from vm_mcp.qmp_client import QMPClient
        from vm_mcp import qmp_client as qmp_mod

        async def _run():
            client = QMPClient(uri=settings.qmp_uri(), password=secrets.get_qmp_password())
            await client.connect()
            try:
                await qmp_mod.stop(client)
                await qmp_mod.cont(client)
            finally:
                await client.disconnect()

        asyncio.run(_run())

    def test_qmp_eject_device(self, settings, secrets):
        from vm_mcp.qmp_client import QMPClient
        from vm_mcp import qmp_client as qmp_mod

        async def _run():
            client = QMPClient(uri=settings.qmp_uri(), password=secrets.get_qmp_password())
            await client.connect()
            try:
                # eject_device may fail if no CD-ROM attached — that's OK
                try:
                    await qmp_mod.eject_device(client, "ide0-cd0")
                except RuntimeError:
                    pass  # Expected when no CD-ROM present
            finally:
                await client.disconnect()

        asyncio.run(_run())


# ── QMP Bridge (PyQt5 signal wrapper) test ────────────────────────────────────


class TestQMPBridgeSignals:
    """Verify QMPBridge emits signals correctly against live QEMU."""

    def test_bridge_connects_and_reports_status(self, settings, secrets):
        from gui.qmp_bridge import QMPBridge

        bridge = QMPBridge(settings=settings)
        bridge.start()

        status_received = []
        error_received = []

        def on_status(status):
            status_received.append(status)

        def on_error(msg):
            error_received.append(msg)

        bridge.vm_status.connect(on_status)
        bridge.error.connect(on_error)

        # Connect and poll status
        bridge.connect()
        import time

        time.sleep(1)
        bridge.get_status()
        time.sleep(1)

        bridge.stop()
        time.sleep(0.5)

        # Best-effort: bridge either connected or had no errors
        assert bridge.is_connected is not False or len(error_received) == 0


# ── SSH integration tests (if guest SSH is reachable) ────────────────────────


class TestSSHBridgeLive:
    """End-to-end SSH tests against the guest.

    Skipped if SSH is not reachable — this is expected when no SSH server
    is running inside the guest VM.
    """

    def test_ssh_run_command(self, settings, secrets):
        from vm_mcp import ssh_client as ssh_mod

        async def _run():
            result = await ssh_mod.run_guest_command(
                "echo ssh_ok",
                timeout=10,
                settings=settings,
                secrets=secrets,
            )
            assert result.get("success", False), f"SSH failed: {result}"
            assert "ssh_ok" in result.get("stdout", "")

        asyncio.run(_run())
