"""Guest interaction tools — command execution, file operations.

All tools use SSH to interact with the guest VM.  SSH credentials are
loaded server-side from Secrets and never exposed to tool callers.
The raw password or key is used internally to establish the connection.
"""

from __future__ import annotations

from typing import Any

from mcp.types import CallToolRequestParams, CallToolResult, TextContent
from pydantic import Field

from vm_mcp.tools.base import Extension, Tool, tool


# ── Command Execution ──────────────────────────────────────────────────────────

@tool(
    name="guest_exec",
    description=(
        "Run a shell command inside the Omarchy guest VM via SSH and return "
        "the stdout, stderr, and exit code.  The command runs as the configured "
        "SSH user (vmharness).  Non-interactive commands only — use 'command "
        "&& command' or a script for complex workflows.  Returns a JSON object "
        "with stdout, stderr, exit_code, and success fields."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute in the guest VM.",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Maximum time to wait for the command to complete. "
                               "Defaults to 30 seconds.",
                "minimum": 1,
                "default": 30,
            },
            "env": {
                "type": "object",
                "description": "Optional environment variables to set for the command.",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["command"],
    },
)
async def guest_exec_fn(params: CallToolRequestParams) -> CallToolResult:
    """Execute a command in the guest via SSH."""
    from vm_mcp.ssh_client import run_guest_command

    command = params.arguments.get("command", "")
    timeout = params.arguments.get("timeout_seconds", 30) if params.arguments else 30
    env = params.arguments.get("env") if params.arguments else None

    if not command:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: 'command' is required.")],
            isError=True,
        )

    try:
        result = await run_guest_command(command, timeout=timeout, env=env)
        text = (
            f"Exit code: {result['exit_code']}\n"
            f"Success: {result['success']}\n\n"
            f"--- stdout ---\n{result['stdout']}\n\n"
            f"--- stderr ---\n{result['stderr']}"
        )
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            isError=not result["success"] and result["exit_code"] != 0,
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error executing command: {e}")],
            isError=True,
        )


# ── File Read ──────────────────────────────────────────────────────────────────

@tool(
    name="guest_file_read",
    description=(
        "Read a text file from the guest VM filesystem via SSH/SFTP and return "
        "its contents.  The file path is relative to the guest's filesystem.  "
        "Only text files are supported; binary files will produce garbled output. "
        "Use guest_file_list to discover paths first.  Max 10 MB per read."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file in the guest VM.",
            },
            "max_bytes": {
                "type": "integer",
                "description": "Maximum number of bytes to read.  Defaults to 1 MB. "
                               "Files larger than this are truncated.",
                "minimum": 1,
                "default": 1048576,
            },
        },
        "required": ["path"],
    },
)
async def guest_file_read_fn(params: CallToolRequestParams) -> CallToolResult:
    """Read a file from the guest."""
    from vm_mcp.ssh_client import read_guest_file

    path = params.arguments.get("path", "")
    max_bytes = params.arguments.get("max_bytes", 1048576) if params.arguments else 1048576

    if not path:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: 'path' is required.")],
            isError=True,
        )

    try:
        content, encoding = await read_guest_file(path, max_bytes=max_bytes)
        return CallToolResult(
            content=[TextContent(type="text", text=f"File: {path}\nEncoding: {encoding}\n\n{content}")],
        )
    except FileNotFoundError:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: File not found: {path}")],
            isError=True,
        )
    except PermissionError:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: Permission denied: {path}")],
            isError=True,
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error reading file: {e}")],
            isError=True,
        )


# ── File Write ─────────────────────────────────────────────────────────────────

@tool(
    name="guest_file_write",
    description=(
        "Write content to a file in the guest VM filesystem via SSH/SFTP.  "
        "Creates parent directories if they don't exist.  Overwrites the file "
        "if it already exists.  Use with caution — there is no backup or undo."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path where the file will be written.",
            },
            "content": {
                "type": "string",
                "description": "The text content to write to the file.",
            },
            "encoding": {
                "type": "string",
                "description": "Text encoding for the content. Defaults to utf-8.",
                "default": "utf-8",
            },
        },
        "required": ["path", "content"],
    },
)
async def guest_file_write_fn(params: CallToolRequestParams) -> CallToolResult:
    """Write a file to the guest."""
    from vm_mcp.ssh_client import write_guest_file

    path = params.arguments.get("path", "")
    content = params.arguments.get("content", "")
    encoding = params.arguments.get("encoding", "utf-8") if params.arguments else "utf-8"

    if not path:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: 'path' is required.")],
            isError=True,
        )
    if content is None:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: 'content' is required.")],
            isError=True,
        )

    try:
        written = await write_guest_file(path, content, encoding=encoding)
        return CallToolResult(
            content=[TextContent(type="text", text=(
                f"File written: {path}\n"
                f"Bytes written: {written}\n"
                f"Encoding: {encoding}"
            ))],
        )
    except PermissionError:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: Permission denied writing to: {path}")],
            isError=True,
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error writing file: {e}")],
            isError=True,
        )


# ── File List ──────────────────────────────────────────────────────────────────

@tool(
    name="guest_file_list",
    description=(
        "List the contents of a directory in the guest VM filesystem via SSH/SFTP. "
        "Returns a table of files and directories with name, type, size, and "
        "modification time.  Use this to discover paths before reading or writing files."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to list in the guest VM.",
            },
            "detail": {
                "type": "boolean",
                "description": "If true, include file size and modification time.",
                "default": True,
            },
        },
        "required": ["path"],
    },
)
async def guest_file_list_fn(params: CallToolRequestParams) -> CallToolResult:
    """List a directory in the guest."""
    from vm_mcp.ssh_client import list_guest_directory

    path = params.arguments.get("path", "")
    detail = params.arguments.get("detail", True) if params.arguments else True

    if not path:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: 'path' is required.")],
            isError=True,
        )

    try:
        entries = await list_guest_directory(path, detail=detail)
        if not entries:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Directory is empty: {path}")],
            )

        lines = [f"Contents of {path}:", ""]
        for entry in entries:
            if detail:
                lines.append(
                    f"  {entry['name']:<40} "
                    f"{entry['type']:<5} "
                    f"{entry['size']:>12} bytes  "
                    f"{entry['mtime']}"
                )
            else:
                lines.append(f"  {entry['name']} ({entry['type']})")
        return CallToolResult(
            content=[TextContent(type="text", text="\n".join(lines))],
        )
    except FileNotFoundError:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: Directory not found: {path}")],
            isError=True,
        )
    except PermissionError:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: Permission denied: {path}")],
            isError=True,
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error listing directory: {e}")],
            isError=True,
        )


# ── File Remove ────────────────────────────────────────────────────────────────

@tool(
    name="guest_file_remove",
    description=(
        "Remove a file or directory from the guest VM filesystem via SSH/SFTP.  "
        "For directories, set recursive=true to remove the directory and all its "
        "contents.  This operation is irreversible — there is no trash or undo."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file or directory to remove.",
            },
            "recursive": {
                "type": "boolean",
                "description": "If true and the path is a directory, remove it recursively.",
                "default": False,
            },
        },
        "required": ["path"],
    },
)
async def guest_file_remove_fn(params: CallToolRequestParams) -> CallToolResult:
    """Remove a file or directory from the guest."""
    from vm_mcp.ssh_client import remove_guest_path

    path = params.arguments.get("path", "")
    recursive = params.arguments.get("recursive", False) if params.arguments else False

    if not path:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: 'path' is required.")],
            isError=True,
        )

    try:
        removed = await remove_guest_path(path, recursive=recursive)
        return CallToolResult(
            content=[TextContent(type="text", text=(
                f"Removed: {path}\n"
                f"Recursively: {recursive}\n"
                f"Type: {removed['type']}\n"
                f"Size: {removed['size']} bytes"
            ))],
        )
    except FileNotFoundError:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: Path not found: {path}")],
            isError=True,
        )
    except PermissionError:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: Permission denied: {path}")],
            isError=True,
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error removing: {e}")],
            isError=True,
        )


def tools() -> list:
    """Return all guest ops tools as a list."""
    return [
        guest_exec_fn,
        guest_file_read_fn,
        guest_file_write_fn,
        guest_file_list_fn,
        guest_file_remove_fn,
    ]
