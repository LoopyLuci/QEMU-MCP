"""vm_harness — Secure MCP server for QEMU/Omarchy VM control.

Purpose: Let AI agents control a QEMU virtual machine running Omarchy Linux
via the Model Context Protocol (MCP), without agents seeing passwords,
SSH keys, or other secrets.  Secrets are loaded server-side from .env and
only used internally when establishing SSH or QMP connections.

Quick start:
    pip install -e "vm-harness[dev]"
    cp .env.example .env          # Edit with your values
    vm-harness                    # Starts MCP server on stdin/stdout

Or pipe to an MCP client:
    vm-harness | your-mcp-client

For SSE transport (remote agents):
    # Set TRANSPORT=sse in .env, then:
    vm-harness

Project: https://github.com/omacom/try-omarchy-windows
"""

from __future__ import annotations

from vm_harness.config import VmMCPSettings, Secrets
from vm_harness.qmp_client import QMPClient, connect_qmp_with_retry
from vm_harness.ssh_client import (
    run_guest_command,
    read_guest_file,
    write_guest_file,
    list_guest_directory,
    remove_guest_path,
)
from vm_harness.tools import vm_lifecycle, guest_ops
from vm_harness.tools.base import Tool, ToolMetadata, Extension, tool, resource, method
from vm_harness.skills import SKILLS, get_skill, list_skills
from vm_harness.setup import build_qemu_args, start_vm, stop_vm, get_qmp_client, set_qmp_client

__all__ = [
    "VmMCPSettings",
    "Secrets",
    "QMPClient",
    "connect_qmp_with_retry",
    "run_guest_command",
    "read_guest_file",
    "write_guest_file",
    "list_guest_directory",
    "remove_guest_path",
    "vm_lifecycle",
    "guest_ops",
    "Tool",
    "ToolMetadata",
    "Extension",
    "tool",
    "resource",
    "method",
    "SKILLS",
    "get_skill",
    "list_skills",
    "build_qemu_args",
    "start_vm",
    "stop_vm",
    "get_qmp_client",
    "set_qmp_client",
]
