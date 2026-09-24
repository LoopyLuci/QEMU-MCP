"""Plugin API base classes for VM-Harness.

Defines the plugin interfaces (PanelPlugin, BackendPlugin, MiddlewarePlugin),
the VMHarnessPlugin base class, and supporting dataclasses (PluginMetadata,
PluginContext).

Plugins are discovered and managed by gui.plugin_manager.PluginManager.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Data Classes ──────────────────────────────────────────────────────────────


@dataclass
class PluginMetadata:
    """Plugin descriptor returned by every plugin's ``metadata`` property."""

    name: str
    version: str
    description: str
    author: str
    category: str  # "panel", "backend", "middleware", "bridge"
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginContext:
    """Context object passed to plugins during ``initialize()``.

    Attributes:
        settings: Application settings dict (VmMCPSettings fields).
        event_loop: The asyncio event loop used by AsyncAdapter.
        bridge_registry: Access to QMP/SSH bridges (may be None before GUI init).
        api_app: The aiohttp Application instance (for middleware plugins).
    """

    settings: Dict[str, Any] = field(default_factory=dict)
    event_loop: Optional[asyncio.AbstractEventLoop] = None
    bridge_registry: Any = None
    api_app: Any = None


# ── Base Plugin ───────────────────────────────────────────────────────────────


class VMHarnessPlugin(ABC):
    """Base class for all VM-Harness plugins.

    Every plugin must implement ``metadata``, ``initialize()``, and
    ``shutdown()``.  Specialised subclasses (PanelPlugin, BackendPlugin,
    MiddlewarePlugin) add their own factory methods.
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata (name, version, category, etc.)."""
        ...

    @abstractmethod
    async def initialize(self, context: PluginContext) -> None:
        """Initialize the plugin with the given context.

        Called once after the plugin is loaded.  Use this to store references
        to bridges, settings, or any resources the plugin needs.
        """
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up plugin resources.

        Called when the plugin is unloaded or the application exits.
        """
        ...


# ── Panel Plugin ──────────────────────────────────────────────────────────────


class PanelPlugin(VMHarnessPlugin):
    """Plugin that provides a GUI panel.

    The returned QWidget is added to the main window's QStackedWidget and
    appears in the sidebar navigation.
    """

    @abstractmethod
    def create_panel(self, parent) -> Any:
        """Create and return the panel widget.

        Args:
            parent: The parent QWidget (usually the MainWindow).

        Returns:
            A QWidget instance to be added to the panel stack.
        """
        ...


# ── Backend Plugin ────────────────────────────────────────────────────────────


class BackendPlugin(VMHarnessPlugin):
    """Plugin that provides a new backend implementation.

    The returned backend must implement the HypervisorBackend or
    ContainerBackend ABC.
    """

    @abstractmethod
    def create_backend(self) -> Any:
        """Create and return a backend instance.

        Returns:
            An instance implementing HypervisorBackend or ContainerBackend.
        """
        ...


# ── Middleware Plugin ─────────────────────────────────────────────────────────


class MiddlewarePlugin(VMHarnessPlugin):
    """Plugin that provides aiohttp middleware.

    The middleware is applied to the headless REST API server.
    """

    @abstractmethod
    def create_middleware(self) -> Any:
        """Create and return an aiohttp middleware callable.

        Returns:
            An async middleware handler ``async def middleware(request, handler)``.
        """
        ...


# ── Convenience re-exports ────────────────────────────────────────────────────

__all__ = [
    "PluginMetadata",
    "PluginContext",
    "VMHarnessPlugin",
    "PanelPlugin",
    "BackendPlugin",
    "MiddlewarePlugin",
]
