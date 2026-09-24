"""Extension and Tool classes for MCP server.

Based on mcp.server.mcpserver.server.MCpServer.add_extension():

- Extension: identifier, tools(), resources(), methods(), settings()
- Tool: fn (async callable), meta (ToolMetadata), kwargs (dict)
- ToolMetadata: name, description, input_schema, annotations (ToolAnnotations)
- MCPServer.add_tool(fn, meta=ToolMetadata(...), **kwargs)
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Type

from pydantic import BaseModel, Field

from mcp.types import (
    ToolAnnotations,
    ReadResourceRequestParams,
    ReadResourceResult,
    CallToolRequestParams,
    CallToolResult,
    GetPromptRequestParams,
    GetPromptResult,
    PaginatedRequestParams,
    ListToolsResult,
    ListResourcesResult,
    ListPromptsResult,
)
from mcp.shared.uri_template import UriTemplate


# ── ToolMetadata ────────────────────────────────────────────────────────────────

class ToolMetadata(BaseModel):
    """Metadata for an MCP tool."""

    model_config = {"populate_by_name": True}

    name: str
    description: str = ""
    inputSchema: dict[str, Any] | None = None
    annotations: ToolAnnotations | None = None


# ── Tool ────────────────────────────────────────────────────────────────────────

@dataclass
class Tool:
    """A single MCP tool definition."""

    fn: Callable[[CallToolRequestParams], Awaitable[CallToolResult]]
    meta: ToolMetadata
    kwargs: dict[str, Any] = field(default_factory=dict)


# ── Resource ────────────────────────────────────────────────────────────────────

@dataclass
class Resource:
    """A single MCP resource definition."""

    resource: Any


# ── Method (MCP request handler) ────────────────────────────────────────────────

@dataclass
class Method:
    """A single MCP method (custom request handler) definition."""

    method: str
    handler: Callable[[Any], Awaitable[Any]]
    params_type: type[BaseModel] | None = None
    protocol_versions: list[str] | None = None


# ── Extension ───────────────────────────────────────────────────────────────────

class Extension:
    """Base extension for an MCP server.

    Subclass this and override tools(), resources(), methods(), settings()
    to add capabilities to the server.
    """

    identifier: str = "base"

    def tools(self) -> list[Tool]:
        """Return the tools provided by this extension."""
        return []

    def resources(self) -> list[Resource]:
        """Return the resources provided by this extension."""
        return []

    def methods(self) -> list[Method]:
        """Return the custom MCP methods provided by this extension."""
        return []

    def settings(self) -> dict[str, Any]:
        """Return extension settings (stored in server.extensions)."""
        return {}


# ── Convenience helpers ─────────────────────────────────────────────────────────

def tool(
    name: str,
    description: str = "",
    input_schema: dict[str, Any] | None = None,
    annotations: ToolAnnotations | None = None,
) -> Callable:
    """Decorator to wrap an async function as an MCP Tool."""

    def decorator(fn: Callable[[CallToolRequestParams], Awaitable[CallToolResult]]) -> Tool:
        meta = ToolMetadata(
            name=name,
            description=description,
            inputSchema=input_schema,
            annotations=annotations,
        )
        return Tool(fn=fn, meta=meta)

    return decorator


def resource(
    name: str,
    title: str = "",
    description: str = "",
    mime_type: str = "text/plain",
    uri_template: str = "",
) -> Callable:
    """Decorator to wrap as an MCP resource."""

    def decorator(fn: Callable[[ReadResourceRequestParams], Awaitable[ReadResourceResult]]) -> Resource:
        resource_data = {
            "name": name,
            "title": title,
            "description": description,
            "mimeType": mime_type,
            "uri": uri_template,
            "fn": fn,
        }
        return Resource(resource=resource_data)

    return decorator


def method(
    method_name: str,
    params_type: type[BaseModel] | None = None,
    protocol_versions: list[str] | None = None,
) -> Callable:
    """Decorator to wrap as an MCP method (custom request handler)."""

    def decorator(fn: Callable[[Any], Awaitable[Any]]) -> Method:
        return Method(
            method=method_name,
            handler=fn,
            params_type=params_type,
            protocol_versions=protocol_versions,
        )

    return decorator
