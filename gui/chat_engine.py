"""Chat Engine — agentic LLM chat with tool execution for QEMU control."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Callable, Optional

from gui.api_providers import APIProviders, APIResponse
from gui.provider_store import ProviderStore

logger = logging.getLogger("qemu-mcp.chat")


class ChatMessage:
    """A message in the chat conversation."""
    
    def __init__(
        self,
        role: str,  # "user", "assistant", "system", "tool"
        content: str,
        tool_name: str = "",
        tool_args: dict | None = None,
    ):
        self.role = role
        self.content = content
        self.tool_name = tool_name
        self.tool_args = tool_args or {}
    
    def to_dict(self) -> dict[str, Any]:
        data = {"role": self.role, "content": self.content}
        if self.tool_name:
            data["tool_name"] = self.tool_name
        if self.tool_args:
            data["tool_args"] = self.tool_args
        return data


class ChatEngine:
    """Agentic chat engine that can execute QEMU tools via LLM."""
    
    # System prompt for the agent
    SYSTEM_PROMPT = """You are an AI assistant running inside QEMU-MCP, a desktop application for controlling QEMU virtual machines.

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
                "name": "iso_list",
                "description": "List available ISO files",
                "parameters": {"type": "object", "properties": {}},
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
        providers: Optional[APIProviders] = None,
        tool_callback: Optional[Callable] = None,
    ):
        self._providers = providers or APIProviders()
        self._tool_callback = tool_callback
        self._history: list[ChatMessage] = []
    
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
        
        # Check for tool calls (simplified - would parse tool_calls in full impl)
        if "tool_calls" in response.content:
            try:
                tool_data = json.loads(response.content)
                for tool_call in tool_data.get("tool_calls", []):
                    tool_name = tool_call.get("function", {}).get("name", "")
                    tool_args = tool_call.get("function", {}).get("arguments", {})
                    
                    if self._tool_callback:
                        result = await self._tool_callback(tool_name, tool_args)
                        tool_msg = ChatMessage("tool", str(result), tool_name, tool_args)
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
        
        # Stream from LLM
        full_response = ""
        async for token in self._providers.stream_call(messages, tools=self.TOOLS):
            full_response += token
            yield token
        
        # Add complete response to history
        self.add_message(ChatMessage("user", user_input))
        self.add_message(ChatMessage("assistant", full_response))
