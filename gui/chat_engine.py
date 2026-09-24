"""Chat Engine — agentic LLM chat with tool execution for QEMU control."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Optional

from PyQt5.QtCore import QObject, pyqtSignal

from gui.api_providers import APIProviders, APIResponse
from gui.iso_manager import ISOManager
from gui.provider_store import ProviderStore
from gui.qmp_bridge import QMPBridge
from gui.ssh_bridge import SSHBridge

logger = logging.getLogger("qemu-mcp.chat")


class ChatMessage:
    """A message in the chat conversation."""

    def __init__(
        self,
        role: str,  # "user", "assistant", "system", "tool"
        content: str,
        tool_name: str = "",
        tool_args: dict | None = None,
        tool_result: str = "",
        finished: bool = False,
    ):
        self.role = role
        self.content = content
        self.tool_name = tool_name
        self.tool_args = tool_args or {}
        self.tool_result = tool_result
        self.finished = finished

    def to_dict(self) -> dict[str, Any]:
        data = {"role": self.role, "content": self.content}
        if self.tool_name:
            data["tool_name"] = self.tool_name
        if self.tool_args:
            data["tool_args"] = self.tool_args
        return data


class ToolResult:
    """Result of a tool execution."""

    def __init__(self, success: bool, output: str, data: dict | None = None):
        self.success = success
        self.output = output
        self.data = data or {}

    def __str__(self) -> str:
        return self.output


class ToolExecutor(QObject):
    """Executes chat tools by bridging to QMP, SSH, and ISO manager.

    Lives on the GUI thread and calls into ``QMPBridge`` / ``SSHBridge``
    which marshal work onto their own background asyncio loops.
    """

    # ── Signals for streaming results to the UI ──────────────────────────────
    tool_started = pyqtSignal(str, dict)          # name, args
    tool_finished = pyqtSignal(str, dict, str)    # name, args, result
    tool_failed = pyqtSignal(str, str, str)        # name, error, detail

    def __init__(
        self,
        qmp_bridge: QMPBridge | None = None,
        ssh_bridge: SSHBridge | None = None,
        iso_manager: ISOManager | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._qmp = qmp_bridge
        self._ssh = ssh_bridge
        self._iso = iso_manager or ISOManager()

        # Connect bridge signals so async results stream to the UI
        if self._qmp:
            self._qmp.command_result.connect(self._on_qmp_result)
            self._qmp.error.connect(self._on_qmp_error)
        if self._ssh:
            self._ssh.command_output.connect(self._on_ssh_output)
            self._ssh.error.connect(self._on_ssh_error)

        # Pending tool tracking
        self._pending: dict[str, asyncio.Future] = {}
        self._tool_id = 0

    # ── QMP signal handlers ──────────────────────────────────────────────────
    def _on_qmp_result(self, result: dict):
        self._resolve_pending("qmp", str(result))

    def _on_qmp_error(self, error: str):
        self._resolve_pending("qmp", f"Error: {error}", success=False)

    def _on_ssh_output(self, output: str):
        self._resolve_pending("ssh", output)

    def _on_ssh_error(self, error: str):
        self._resolve_pending("ssh", f"Error: {error}", success=False)

    def _resolve_pending(self, prefix: str, result: str, success: bool = True):
        """Resolve a pending future for a QMP/SSH call."""
        for key in list(self._pending.keys()):
            if key.startswith(prefix):
                fut = self._pending.pop(key)
                if not fut.done():
                    fut.set_result(ToolResult(success, result))
                break

    def _next_id(self, prefix: str) -> str:
        self._tool_id += 1
        return f"{prefix}_{self._tool_id}"

    # ── Public API ───────────────────────────────────────────────────────────

    def set_qmp_bridge(self, bridge: QMPBridge):
        self._qmp = bridge
        if self._qmp:
            self._qmp.command_result.connect(self._on_qmp_result)
            self._qmp.error.connect(self._on_qmp_error)

    def set_ssh_bridge(self, bridge: SSHBridge):
        self._ssh = bridge
        if self._ssh:
            self._ssh.command_output.connect(self._on_ssh_output)
            self._ssh.error.connect(self._on_ssh_error)

    def set_iso_manager(self, manager: ISOManager):
        self._iso = manager

    async def execute(self, name: str, args: dict | None = None) -> ToolResult:
        """Execute a tool by name with given arguments."""
        args = args or {}
        method = getattr(self, f"tool_{name}", None)
        if method is None:
            return ToolResult(False, f"Unknown tool: {name}")

        self.tool_started.emit(name, args)
        try:
            result = await method(args)
        except Exception as e:
            logger.exception("Tool %s failed", name)
            result = ToolResult(False, str(e))
            self.tool_failed.emit(name, str(e), "")

        status = "success" if result.success else "failed"
        self.tool_finished.emit(name, args, f"[{status}] {result.output}")
        return result

    # ── Tool: snapshot_restore ────────────────────────────────────────────────
    async def tool_snapshot_restore(self, args: dict) -> ToolResult:
        name = args.get("name", "")
        if not name:
            return ToolResult(False, "Missing required parameter: name")
        disk_path = os.environ.get("QEMU_DISK_PATH", "")
        if not disk_path:
            return ToolResult(
                False,
                "QEMU_DISK_PATH not set. Set environment variable to restore snapshots.",
            )
        qemu_img = os.environ.get("QEMU_IMG_PATH", "qemu-img")
        cmd = [qemu_img, "snapshot", "-a", name, disk_path]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return ToolResult(
                    True,
                    f"Snapshot '{name}' restored on {disk_path}",
                    {"name": name, "disk": disk_path},
                )
            return ToolResult(
                False,
                f"Snapshot restore failed: {stderr.decode().strip()}",
            )
        except Exception as e:
            return ToolResult(False, f"Error restoring snapshot: {e}")

    # ── Tool: vm_status ──────────────────────────────────────────────────────
    async def tool_vm_status(self, args: dict) -> ToolResult:
        if not self._qmp:
            return ToolResult(False, "QMP bridge not connected")
        status = self._qmp.get_status()
        if status is None:
            return ToolResult(False, "Could not retrieve VM status (QMP may not be connected)")
        return ToolResult(True, json.dumps(status, indent=2), status)

    # ── Tool: vm_start ───────────────────────────────────────────────────────
    async def tool_vm_start(self, args: dict) -> ToolResult:
        if not self._qmp:
            return ToolResult(False, "QMP bridge not connected")
        # vm_start via QMP is a no-op if already running; the actual
        # VM launch is handled by multi_vm or external process.
        status = self._qmp.get_status()
        running = status and status.get("running", False)
        if running:
            return ToolResult(True, "VM is already running")
        return ToolResult(
            True,
            "VM start requested. Use multi_vm Manager or start QEMU with -qmp flag.",
        )

    # ── Tool: vm_stop ────────────────────────────────────────────────────────
    async def tool_vm_stop(self, args: dict) -> ToolResult:
        if not self._qmp:
            return ToolResult(False, "QMP bridge not connected")
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        tag = self._next_id("qmp")
        self._pending[tag] = fut
        self._qmp.system_powerdown()
        result = await asyncio.wait_for(fut, timeout=10.0)
        return result

    # ── Tool: vm_reset ───────────────────────────────────────────────────────
    async def tool_vm_reset(self, args: dict) -> ToolResult:
        if not self._qmp:
            return ToolResult(False, "QMP bridge not connected")
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        tag = self._next_id("qmp")
        self._pending[tag] = fut
        self._qmp.system_reset()
        result = await asyncio.wait_for(fut, timeout=10.0)
        return result

    # ── Tool: vm_suspend ─────────────────────────────────────────────────────
    async def tool_vm_suspend(self, args: dict) -> ToolResult:
        if not self._qmp:
            return ToolResult(False, "QMP bridge not connected")
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        tag = self._next_id("qmp")
        self._pending[tag] = fut
        self._qmp.stop_vm()
        result = await asyncio.wait_for(fut, timeout=10.0)
        return result

    # ── Tool: vm_resume ──────────────────────────────────────────────────────
    async def tool_vm_resume(self, args: dict) -> ToolResult:
        if not self._qmp:
            return ToolResult(False, "QMP bridge not connected")
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        tag = self._next_id("qmp")
        self._pending[tag] = fut
        self._qmp.cont()
        result = await asyncio.wait_for(fut, timeout=10.0)
        return result

    # ── Tool: guest_exec ─────────────────────────────────────────────────────
    async def tool_guest_exec(self, args: dict) -> ToolResult:
        command = args.get("command", "")
        if not command:
            return ToolResult(False, "Missing required parameter: command")
        timeout = args.get("timeout", 30)

        if not self._ssh:
            return ToolResult(False, "SSH bridge not connected")
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        tag = self._next_id("ssh")
        self._pending[tag] = fut
        self._ssh.run_command(command, timeout=timeout)
        result = await asyncio.wait_for(fut, timeout=float(timeout) + 5)
        return result

    # ── Tool: snapshot_create ────────────────────────────────────────────────
    async def tool_snapshot_create(self, args: dict) -> ToolResult:
        name = args.get("name", f"snapshot_{int(time.time())}")
        # Use qemu-img for snapshot creation
        disk_path = os.environ.get("QEMU_DISK_PATH", "")
        if not disk_path:
            return ToolResult(
                False,
                "QEMU_DISK_PATH not set. Set environment variable or pass disk path.",
            )
        qemu_img = os.environ.get("QEMU_IMG_PATH", "qemu-img")
        cmd = [qemu_img, "snapshot", "-c", name, disk_path]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return ToolResult(
                    True,
                    f"Snapshot '{name}' created on {disk_path}",
                    {"name": name, "disk": disk_path},
                )
            return ToolResult(
                False,
                f"Snapshot creation failed: {stderr.decode().strip()}",
            )
        except Exception as e:
            return ToolResult(False, f"Error creating snapshot: {e}")

    # ── Tool: snapshot_list ──────────────────────────────────────────────────
    async def tool_snapshot_list(self, args: dict) -> ToolResult:
        disk_path = os.environ.get("QEMU_DISK_PATH", "")
        if not disk_path:
            # Fallback: list ISO-related snapshots from iso manager
            snapshots = self._get_qemu_snapshots_fallback()
            return ToolResult(
                True,
                json.dumps({"snapshots": snapshots, "note": "Fallback mode (no QEMU_DISK_PATH)"}, indent=2),
                {"snapshots": snapshots},
            )
        qemu_img = os.environ.get("QEMU_IMG_PATH", "qemu-img")
        cmd = [qemu_img, "snapshot", "-l", disk_path]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode().strip()
            if proc.returncode == 0:
                snapshots = self._parse_snapshot_list(output)
                return ToolResult(
                    True,
                    json.dumps({"snapshots": snapshots, "disk": disk_path}, indent=2),
                    {"snapshots": snapshots},
                )
            return ToolResult(
                False,
                f"Snapshot list failed: {stderr.decode().strip()}",
            )
        except Exception as e:
            return ToolResult(False, f"Error listing snapshots: {e}")

    def _get_qemu_snapshots_fallback(self) -> list[dict]:
        """Fallback snapshot listing via AtomicState snapshots."""
        state_dir = Path.home() / ".qemu-mcp" / "state" / "snapshots"
        if not state_dir.exists():
            return []
        snapshots = []
        for f in sorted(state_dir.glob("*.json")):
            snapshots.append(
                {
                    "name": f.stem,
                    "path": str(f),
                    "modified": f.stat().st_mtime,
                }
            )
        return snapshots

    @staticmethod
    def _parse_snapshot_list(output: str) -> list[dict]:
        """Parse qemu-img snapshot -l output."""
        snapshots = []
        for line in output.split("\n"):
            parts = line.split()
            if len(parts) >= 2:
                snapshots.append(
                    {
                        "id": parts[0],
                        "name": parts[1],
                        "size_info": " ".join(parts[2:]) if len(parts) > 2 else "",
                    }
                )
        return snapshots

    # ── Tool: iso_list ───────────────────────────────────────────────────────
    async def tool_iso_list(self, args: dict) -> ToolResult:
        isos = self._iso.scan_isos()
        if not isos:
            return ToolResult(
                True,
                "No ISO files found. Use iso_import to add ISOs.",
                {"isos": []},
            )
        lines = ["Available ISOs:"]
        for iso in isos:
            lines.append(
                f"  {iso['name']:<30} {iso['size_human']:>10}  [{iso['source']}]"
            )
        return ToolResult(True, "\n".join(lines), {"isos": isos})

    # ── Tool: iso_import ─────────────────────────────────────────────────────
    async def tool_iso_import(self, args: dict) -> ToolResult:
        source = args.get("source", "")
        if not source:
            return ToolResult(False, "Missing required parameter: source (file path)")
        from pathlib import Path
        src = Path(source)
        if not src.exists():
            return ToolResult(False, f"Source file not found: {source}")
        dest = self._iso.copy_to_internal(src)
        if dest:
            return ToolResult(
                True,
                f"Imported '{src.name}' → {dest}",
                {"path": str(dest), "name": src.stem},
            )
        return ToolResult(False, f"Failed to import {source}")

    # ── Tool: get_usage ──────────────────────────────────────────────────────
    async def tool_get_usage(self, args: dict) -> ToolResult:
        store = ProviderStore()
        summary = store.get_usage_summary()
        return ToolResult(
            True,
            json.dumps(summary, indent=2),
            summary,
        )


class ChatEngine(QObject):
    """Agentic chat engine that can execute QEMU tools via LLM."""

    # ── Signals for streaming ────────────────────────────────────────────────
    message_received = pyqtSignal(object)       # ChatMessage
    token_received = pyqtSignal(str)            # token text
    tool_call_started = pyqtSignal(str, dict)   # name, args
    tool_call_finished = pyqtSignal(str, str)   # name, result

    # System prompt for the agent
    SYSTEM_PROMPT = """You are an AI assistant running inside VM-Harness, a desktop application for controlling QEMU virtual machines.

You have access to tools that allow you to:
- Control VM lifecycle (start, stop, reset, suspend, resume)
- Execute commands on the guest VM via SSH
- Manage VM snapshots
- Manage ISO files
- Configure VM settings
- Monitor VM resources

When the user asks you to perform an action, use the appropriate tool. When you need information, ask clarifying questions if needed.

Available tools:
- vm_status: Get current VM running status
- vm_start: Start the VM
- vm_stop: Stop the VM gracefully
- vm_reset: Hard reset the VM
- vm_suspend: Suspend the VM
- vm_resume: Resume the VM
- guest_exec: Execute a command on the guest VM
- snapshot_create: Create a VM snapshot
- snapshot_list: List VM snapshots
- snapshot_restore: Restore a VM snapshot
- iso_list: List available ISO files
- iso_import: Import an ISO file
- get_usage: Get API usage statistics

Always explain what you're doing before executing a tool. If a tool fails, explain the error and suggest alternatives."""

    # Tool definitions for LLM function calling
    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "vm_status",
                "description": "Get current VM running status (running/stopped, PID, resources)",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vm_start",
                "description": "Start the VM",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vm_stop",
                "description": "Stop the VM gracefully",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vm_reset",
                "description": "Hard reset the VM",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vm_suspend",
                "description": "Suspend the VM to RAM",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vm_resume",
                "description": "Resume a suspended VM",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "guest_exec",
                "description": "Execute a command on the guest VM via SSH",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds"},
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "snapshot_create",
                "description": "Create a VM snapshot",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Snapshot name"},
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "snapshot_list",
                "description": "List VM snapshots",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "snapshot_restore",
                "description": "Restore a VM snapshot",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Snapshot name to restore"},
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "iso_list",
                "description": "List available ISO files",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "iso_import",
                "description": "Import an ISO file into internal storage",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Path to the ISO file"},
                    },
                    "required": ["source"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_usage",
                "description": "Get API usage statistics",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]

    def __init__(
        self,
        providers: APIProviders | None = None,
        executor: ToolExecutor | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._providers = providers or APIProviders()
        self._executor = executor or ToolExecutor()
        self._history: list[ChatMessage] = []

        # Forward executor signals
        self._executor.tool_started.connect(self._on_tool_started)
        self._executor.tool_finished.connect(self._on_tool_finished)

    def set_executor(self, executor: ToolExecutor):
        """Attach a tool executor (e.g. after bridges are ready)."""
        self._executor = executor
        self._executor.tool_started.connect(self._on_tool_started)
        self._executor.tool_finished.connect(self._on_tool_finished)

    def _on_tool_started(self, name: str, args: dict):
        self.tool_call_started.emit(name, args)

    def _on_tool_finished(self, name: str, args: dict, result: str):
        self.tool_call_finished.emit(name, result)

    def add_message(self, message: ChatMessage):
        """Add a message to the conversation history."""
        self._history.append(message)

    def clear_history(self):
        """Clear conversation history."""
        self._history.clear()

    async def send_message(self, user_input: str) -> AsyncGenerator[ChatMessage, None]:
        """Send a user message and stream the response."""
        # Add user message
        self.add_message(ChatMessage("user", user_input))
        yield ChatMessage("user", user_input)

        # Build messages for API
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        for msg in self._history:
            messages.append({"role": msg.role, "content": msg.content})

        # Call LLM
        response = await self._providers.call(messages, tools=self.TOOLS)

        if not response.success:
            error_msg = ChatMessage("assistant", f"Error: {response.error}")
            self.add_message(error_msg)
            yield error_msg
            return

        # Yield assistant response
        assistant_msg = ChatMessage("assistant", response.content)
        self.add_message(assistant_msg)
        yield assistant_msg

        # Check for tool calls
        if response.content and "tool_calls" in response.content:
            try:
                tool_data = json.loads(response.content)
                for tool_call in tool_data.get("tool_calls", []):
                    tool_name = tool_call.get("function", {}).get("name", "")
                    tool_args_raw = tool_call.get("function", {}).get("arguments", "{}")
                    if isinstance(tool_args_raw, str):
                        tool_args = json.loads(tool_args_raw)
                    else:
                        tool_args = tool_args_raw

                    # Execute the tool
                    result = await self._executor.execute(tool_name, tool_args)
                    tool_msg = ChatMessage(
                        "tool",
                        result.output,
                        tool_name,
                        tool_args,
                        result.output,
                        finished=True,
                    )
                    self.add_message(tool_msg)
                    yield tool_msg
            except json.JSONDecodeError:
                pass

    async def stream_message(self, user_input: str) -> AsyncGenerator[str, None]:
        """Send a user message and stream the response tokens."""
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        for msg in self._history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_input})

        full_response = ""
        async for token in self._providers.stream_call(messages, tools=self.TOOLS):
            full_response += token
            yield token

        # Add complete response to history
        self.add_message(ChatMessage("user", user_input))
        self.add_message(ChatMessage("assistant", full_response))
