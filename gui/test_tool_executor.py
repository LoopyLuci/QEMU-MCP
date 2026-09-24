"""Tests for the ToolExecutor — verifies all tool methods exist and handle basic cases."""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

import PyQt5.QtWidgets as qw
app = qw.QApplication.instance() or qw.QApplication(sys.argv)

from gui.chat_engine import ToolExecutor, ToolResult


class TestToolExecutor(unittest.TestCase):
    """Test suite for ToolExecutor class."""

    def setUp(self):
        self.executor = ToolExecutor()

    def test_all_tools_registered(self):
        """All 12 tool methods must exist."""
        tools = [
            "vm_status", "vm_start", "vm_stop", "vm_reset",
            "vm_suspend", "vm_resume",
            "guest_exec", "snapshot_create", "snapshot_list", "snapshot_restore",
            "iso_list", "iso_import", "get_usage",
        ]
        for tool in tools:
            self.assertTrue(
                hasattr(self.executor, f"tool_{tool}"),
                f"Missing tool: {tool}",
            )

    def test_unknown_tool(self):
        """execute() returns failure for unknown tool."""
        async def _run():
            result = await self.executor.execute("nonexistent_tool", {})
            self.assertFalse(result.success)
            self.assertIn("Unknown tool", result.output)

        asyncio.get_event_loop().run_until_complete(_run())

    def test_vm_status_no_bridge(self):
        """vm_status fails gracefully when no QMP bridge attached."""
        async def _run():
            result = await self.executor.tool_vm_status({})
            self.assertFalse(result.success)
            self.assertIn("not connected", result.output.lower())

        asyncio.get_event_loop().run_until_complete(_run())

    def test_vm_start_no_bridge(self):
        """vm_start fails gracefully when no QMP bridge attached."""
        async def _run():
            result = await self.executor.tool_vm_start({})
            self.assertFalse(result.success)
            self.assertIn("not connected", result.output.lower())

        asyncio.get_event_loop().run_until_complete(_run())

    def test_guest_exec_no_command(self):
        """guest_exec rejects missing command argument."""
        async def _run():
            result = await self.executor.tool_guest_exec({})
            self.assertFalse(result.success)
            self.assertIn("command", result.output.lower())

        asyncio.get_event_loop().run_until_complete(_run())

    def test_guest_exec_no_bridge(self):
        """guest_exec fails gracefully when no SSH bridge attached."""
        async def _run():
            result = await self.executor.tool_guest_exec({"command": "ls"})
            self.assertFalse(result.success)
            self.assertIn("not connected", result.output.lower())

        asyncio.get_event_loop().run_until_complete(_run())

    def test_iso_list_returns_result(self):
        """iso_list should succeed (may return empty list)."""
        async def _run():
            result = await self.executor.tool_iso_list({})
            self.assertTrue(result.success)
            self.assertIsInstance(result.data.get("isos"), list)

        asyncio.get_event_loop().run_until_complete(_run())

    def test_iso_import_missing_source(self):
        """iso_import rejects missing source argument."""
        async def _run():
            result = await self.executor.tool_iso_import({})
            self.assertFalse(result.success)
            self.assertIn("source", result.output.lower())

        asyncio.get_event_loop().run_until_complete(_run())

    def test_iso_import_nonexistent_file(self):
        """iso_import fails for nonexistent file."""
        async def _run():
            result = await self.executor.tool_iso_import({"source": "/nonexistent/path/file.iso"})
            self.assertFalse(result.success)
            self.assertIn("not found", result.output.lower())

        asyncio.get_event_loop().run_until_complete(_run())

    def test_snapshot_create_no_disk_path(self):
        """snapshot_create fails gracefully without QEMU_DISK_PATH."""
        # Ensure env var is unset
        old_val = os.environ.pop("QEMU_DISK_PATH", None)
        try:
            async def _run():
                result = await self.executor.tool_snapshot_create({"name": "test"})
                self.assertFalse(result.success)
                self.assertIn("QEMU_DISK_PATH", result.output)

            asyncio.get_event_loop().run_until_complete(_run())
        finally:
            if old_val is not None:
                os.environ["QEMU_DISK_PATH"] = old_val

    def test_snapshot_list_no_disk_path(self):
        """snapshot_list returns fallback without QEMU_DISK_PATH."""
        old_val = os.environ.pop("QEMU_DISK_PATH", None)
        try:
            async def _run():
                result = await self.executor.tool_snapshot_list({})
                # Should still succeed with fallback
                self.assertTrue(result.success)

            asyncio.get_event_loop().run_until_complete(_run())
        finally:
            if old_val is not None:
                os.environ["QEMU_DISK_PATH"] = old_val

    def test_snapshot_restore_missing_name(self):
        """snapshot_restore rejects missing name."""
        async def _run():
            result = await self.executor.tool_snapshot_restore({})
            self.assertFalse(result.success)
            self.assertIn("name", result.output.lower())

        asyncio.get_event_loop().run_until_complete(_run())

    def test_get_usage(self):
        """get_usage returns valid summary."""
        async def _run():
            result = await self.executor.tool_get_usage({})
            self.assertTrue(result.success)
            self.assertIn("total_requests", result.data)

        asyncio.get_event_loop().run_until_complete(_run())

    def test_tool_result_str(self):
        """ToolResult.__str__ returns output."""
        r = ToolResult(True, "ok")
        self.assertEqual(str(r), "ok")

    def test_qmp_bridge_setter(self):
        """set_qmp_bridge updates the bridge reference."""
        mock_bridge = MagicMock()
        self.executor.set_qmp_bridge(mock_bridge)
        self.assertIs(self.executor._qmp, mock_bridge)

    def test_ssh_bridge_setter(self):
        """set_ssh_bridge updates the bridge reference."""
        mock_bridge = MagicMock()
        self.executor.set_ssh_bridge(mock_bridge)
        self.assertIs(self.executor._ssh, mock_bridge)

    def test_iso_manager_setter(self):
        """set_iso_manager updates the ISO manager reference."""
        mock_manager = MagicMock()
        self.executor.set_iso_manager(mock_manager)
        self.assertIs(self.executor._iso, mock_manager)

    def test_emit_signals(self):
        """Signals fire on tool execution."""
        received = []

        def on_start(name, args):
            received.append(("start", name))

        def on_finish(name, args, result):
            received.append(("finish", name))

        self.executor.tool_started.connect(on_start)
        self.executor.tool_finished.connect(on_finish)

        async def _run():
            # Use execute() which emits signals, not tool_get_usage() directly
            await self.executor.execute("get_usage", {})

        asyncio.get_event_loop().run_until_complete(_run())

        self.assertEqual(len(received), 2)
        self.assertEqual(received[0], ("start", "get_usage"))
        self.assertEqual(received[1][0], "finish")
        self.assertEqual(received[1][1], "get_usage")


if __name__ == "__main__":
    unittest.main()
