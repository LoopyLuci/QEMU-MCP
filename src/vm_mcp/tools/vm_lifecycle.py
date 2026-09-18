"""VM lifecycle tools — start, stop, reset, eject, boot management.

All tools are async functions that receive a QMP client via dependency
injection (the server passes it in).  No tool ever sees raw secrets.
"""

from __future__ import annotations

from typing import Any

from mcp.types import CallToolRequestParams, CallToolResult, TextContent
from pydantic import Field

from vm_mcp.tools.base import Extension, Tool, tool


# ── VM Status ──────────────────────────────────────────────────────────────────

@tool(
    name="vm_status",
    description=(
        "Get the current status of the QEMU virtual machine: whether it is "
        "running, paused, or stopped, plus basic runtime info like PID and "
        "uptime.  Does NOT require the VM to be running — returns an error "
        "if QMP cannot connect."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def vm_status_fn(params: CallToolRequestParams) -> CallToolResult:
    """Query VM status via QMP."""
    from vm_mcp.qmp_client import get_qmp_client

    try:
        qmp = get_qmp_client()
        if qmp is None:
            return CallToolResult(
                content=[TextContent(type="text", text=(
                    "QMP client not available.  Ensure the vm-mcp server is "
                    "running and QMP is configured."
                ))],
                isError=True,
            )
        status = await qmp.send("query-status")
        return_code = status.get("return", {}).get("return", "unknown")
        return CallToolResult(
            content=[TextContent(type="text", text=(
                f"VM Status:\n"
                f"  State: {return_code}\n"
                f"  QMP connected: yes\n"
                f"  QMP URI: {qmp.uri}"
            ))],
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error querying VM status: {e}")],
            isError=True,
        )


# ── VM Start ───────────────────────────────────────────────────────────────────

@tool(
    name="vm_start",
    description=(
        "Start the QEMU virtual machine.  Uses the configured QEMU binary, "
        "disk image, and display settings.  The VM is launched with QMP "
        "control enabled so subsequent tools can manage it.  If the VM is "
        "already running, returns the current status instead."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "boot_iso": {
                "type": "boolean",
                "description": "If true, boot from the Omarchy ISO (for install/repair). "
                               "Defaults to false (boot from disk).",
            },
        },
        "required": [],
    },
)
async def vm_start_fn(params: CallToolRequestParams) -> CallToolResult:
    """Start or verify the VM."""
    from vm_mcp.setup import start_vm

    boot_iso = params.arguments.get("boot_iso", False) if params.arguments else False
    try:
        result = await start_vm(boot_iso=boot_iso)
        return CallToolResult(
            content=[TextContent(type="text", text=result)],
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error starting VM: {e}")],
            isError=True,
        )


# ── VM Stop ────────────────────────────────────────────────────────────────────

@tool(
    name="vm_stop",
    description=(
        "Gracefully shut down the running VM using QMP system_powerdown.  "
        "The guest OS receives an ACPI power button event and should shut "
        "down cleanly.  If the VM is not running, returns a message saying so."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def vm_stop_fn(params: CallToolRequestParams) -> CallToolResult:
    """Gracefully stop the VM."""
    from vm_mcp.qmp_client import get_qmp_client

    try:
        qmp = get_qmp_client()
        if qmp is None:
            return CallToolResult(
                content=[TextContent(type="text", text=(
                    "QMP client not available.  Ensure the vm-mcp server is "
                    "running and QMP is configured."
                ))],
                isError=True,
            )
        result = await qmp.send("system_powerdown")
        return CallToolResult(
            content=[TextContent(type="text", text=(
                f"VM shutdown initiated.  QMP response: {result}"
            ))],
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error stopping VM: {e}")],
            isError=True,
        )


# ── VM Reset ───────────────────────────────────────────────────────────────────

@tool(
    name="vm_reset",
    description=(
        "Hard reset the running VM using QMP system_reset.  Equivalent to "
        "pressing the reset button on a physical machine.  The guest OS will "
        "reboot immediately.  If the VM is not running, returns a message."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def vm_reset_fn(params: CallToolRequestParams) -> CallToolResult:
    """Hard reset the VM."""
    from vm_mcp.qmp_client import get_qmp_client

    try:
        qmp = get_qmp_client()
        if qmp is None:
            return CallToolResult(
                content=[TextContent(type="text", text=(
                    "QMP client not available.  Ensure the vm-mcp server is "
                    "running and QMP is configured."
                ))],
                isError=True,
            )
        result = await qmp.send("system_reset")
        return CallToolResult(
            content=[TextContent(type="text", text=(
                f"VM reset initiated.  QMP response: {result}"
            ))],
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error resetting VM: {e}")],
            isError=True,
        )


# ── VM Suspend / Resume ───────────────────────────────────────────────────────

@tool(
    name="vm_suspend",
    description=(
        "Suspend the VM to RAM using QMP 'stop'.  The VM halts all CPUs but "
        "remains in memory.  Use vm_resume to continue."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def vm_suspend_fn(params: CallToolRequestParams) -> CallToolResult:
    """Suspend the VM."""
    from vm_mcp.qmp_client import get_qmp_client

    try:
        qmp = get_qmp_client()
        if qmp is None:
            return CallToolResult(
                content=[TextContent(type="text", text="QMP client not available.")],
                isError=True,
            )
        result = await qmp.send("stop")
        return CallToolResult(
            content=[TextContent(type="text", text=f"VM suspended. QMP response: {result}")],
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error suspending VM: {e}")],
            isError=True,
        )


@tool(
    name="vm_resume",
    description=(
        "Resume a suspended VM using QMP 'cont'.  Continues execution from "
        "the suspended state."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def vm_resume_fn(params: CallToolRequestParams) -> CallToolResult:
    """Resume the VM."""
    from vm_mcp.qmp_client import get_qmp_client

    try:
        qmp = get_qmp_client()
        if qmp is None:
            return CallToolResult(
                content=[TextContent(type="text", text="QMP client not available.")],
                isError=True,
            )
        result = await qmp.send("cont")
        return CallToolResult(
            content=[TextContent(type="text", text=f"VM resumed. QMP response: {result}")],
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error resuming VM: {e}")],
            isError=True,
        )


# ── Eject CDROM ────────────────────────────────────────────────────────────────

@tool(
    name="vm_eject_cdrom",
    description=(
        "Eject the installation ISO from the virtual CDROM drive after "
        "Omarchy has been installed.  This is safe to call even if no ISO "
        "is mounted — it will just return a success message."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def vm_eject_cdrom_fn(params: CallToolRequestParams) -> CallToolResult:
    """Eject the CDROM."""
    from vm_mcp.qmp_client import get_qmp_client

    try:
        qmp = get_qmp_client()
        if qmp is None:
            return CallToolResult(
                content=[TextContent(type="text", text="QMP client not available.")],
                isError=True,
            )
        result = await qmp.send("eject", {"device": "ide0-cd0"})
        return CallToolResult(
            content=[TextContent(type="text", text=(
                f"CDROM ejected. QMP response: {result}"
            ))],
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error ejecting CDROM: {e}")],
            isError=True,
        )


# ── Boot Device ────────────────────────────────────────────────────────────────

@tool(
    name="vm_boot_device",
    description=(
        "Query the current boot order, or set a new one.  Boot order is a "
        "list of device names: ['hd', 'cdrom', 'network'].  If setting a new "
        "order, the VM must be reset for the change to take effect."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "boot_order": {
                "type": "array",
                "items": {"type": "string"},
                "description": "New boot order. Example: ['hd', 'cdrom', 'network']. "
                               "If omitted, only queries the current order.",
            },
        },
        "required": [],
    },
)
async def vm_boot_device_fn(params: CallToolRequestParams) -> CallToolResult:
    """Query or set boot order."""
    from vm_mcp.qmp_client import get_qmp_client

    boot_order = params.arguments.get("boot_order") if params.arguments else None

    try:
        qmp = get_qmp_client()
        if qmp is None:
            return CallToolResult(
                content=[TextContent(type="text", text="QMP client not available.")],
                isError=True,
            )

        if boot_order is None:
            # Query current boot order
            result = await qmp.send("query-bootindex")
            boot_index = result.get("return", {}).get("bootindex", [])
            return CallToolResult(
                content=[TextContent(type="text", text=(
                    f"Current boot order: {boot_index}"
                ))],
            )

        # Set new boot order
        result = await qmp.send("set-bootindex", {
            "device": "machine",
            "boots": [{"index": i, "dev": dev} for i, dev in enumerate(boot_order)],
        })
        return CallToolResult(
            content=[TextContent(type="text", text=(
                f"Boot order set to {boot_order}. Reset the VM for changes to take effect.\n"
                f"QMP response: {result}"
            ))],
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error managing boot device: {e}")],
            isError=True,
        )


def tools() -> list:
    """Return all VM lifecycle tools as a list."""
    return [
        vm_status_fn,
        vm_start_fn,
        vm_stop_fn,
        vm_reset_fn,
        vm_suspend_fn,
        vm_resume_fn,
        vm_eject_cdrom_fn,
        vm_boot_device_fn,
    ]
