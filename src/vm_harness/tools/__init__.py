"""Tools package — all MCP tool extensions for vm-mcp.

Each module in this package defines an Extension subclass with tools,
resources, and methods.  The server.py builder registers them all.
"""

from __future__ import annotations

from vm_harness.tools.base import Extension

# Import all tool modules so their Extension subclasses are registered
from vm_harness.tools import vm_lifecycle  # noqa: F401
from vm_harness.tools import guest_ops  # noqa: F401

__all__ = ["vm_lifecycle", "guest_ops"]
