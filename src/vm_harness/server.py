"""MCP server assembly — builds and runs the vm-mcp server.

This module creates the MCP Server, registers all tools and resources,
configures logging and auth, and starts the selected transport.

The MCP SDK's Server class uses direct registration:
    server.add_tool(fn, meta=ToolMetadata(...))
    server.add_resource(template, resource)
    server.add_prompt(fn)

Our @tool decorator wraps functions into Tool objects (fn + meta).
We extract fn and meta from each Tool to pass to the SDK.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from mcp.server.mcpserver.server import MCPServer

Server = MCPServer  # backward compat alias

from vm_harness.config import VmMCPSettings, Secrets
from vm_harness.tools import vm_lifecycle, guest_ops
from vm_harness.tools.base import Tool


# ── Logging setup ──────────────────────────────────────────────────────────────

def setup_logging(settings: VmMCPSettings) -> None:
    """Configure logging based on settings."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    fmt = logging.Formatter(settings.log_format)
    for h in handlers:
        h.setFormatter(fmt)
        h.setLevel(level)
    logging.basicConfig(level=level, handlers=handlers)

    if settings.log_file:
        p = Path(settings.log_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(p)
        fh.setFormatter(fmt)
        fh.setLevel(level)
        logging.getLogger().addHandler(fh)


# ── Server builder ──────────────────────────────────────────────────────────────

def build_server() -> tuple[Server, VmMCPSettings, Secrets]:
    """Create and configure the MCP server with all tools registered."""
    settings = VmMCPSettings()
    secrets = Secrets.from_env()
    secrets_dotenv = Secrets.from_dotenv()

    # Merge secrets (dotenv takes priority)
    if secrets_dotenv.has_any_secret():
        secrets = secrets_dotenv

    setup_logging(settings)

    logger = logging.getLogger("vm-mcp")
    logger.info(
        "Starting vm-mcp v%s (server=%s, transport=%s)",
        settings.server_version, settings.server_name, settings.transport,
    )
    logger.info(
        "Config: %s",
        settings.model_dump_json(
            exclude_none=True,
            exclude={"qmp_password", "ssh_password", "ssh_private_key", "auth_api_key"},
        ),
    )
    logger.info("Secrets loaded: %s", secrets.mask())

    # Create MCP server
    server = Server(
        name=settings.server_name,
        version=settings.server_version,
        instructions=(
            "vm-mcp controls a QEMU virtual machine running Omarchy Linux. "
            "Use vm_lifecycle tools to manage the VM (start, stop, reset, eject ISO). "
            "Use guest_ops tools to interact with the running guest (execute commands, "
            "read/write/list/remove files via SSH). "
            "Secrets (SSH password, keys) are never exposed to agents — they are used "
            "internally by the server."
        ),
    )

    # ── Register all tools ────────────────────────────────────────────────────

    for tool_wrapper in vm_lifecycle.tools():
        server.add_tool(
            tool_wrapper.fn,
            name=tool_wrapper.meta.name,
            description=tool_wrapper.meta.description,
            meta=tool_wrapper.meta.model_dump(),
        )
    for tool_wrapper in guest_ops.tools():
        server.add_tool(
            tool_wrapper.fn,
            name=tool_wrapper.meta.name,
            description=tool_wrapper.meta.description,
            meta=tool_wrapper.meta.model_dump(),
        )

    logger.info("Registered 13 tools")

    # Auth configuration
    if settings.auth_enabled and settings.auth_api_key:
        server.settings["auth"] = {
            "type": settings.auth_type,
            "api_key": settings.auth_api_key,
        }

    return server, settings, secrets


# ── Entry point ────────────────────────────────────────────────────────────────

async def main() -> None:
    """Main entry point — build server and start transport."""
    server, settings, secrets = build_server()

    if settings.transport == "stdio":
        await server.run_stdio_async()
    else:
        raise ValueError(f"Unknown transport: {settings.transport}")


if __name__ == "__main__":
    asyncio.run(main())
