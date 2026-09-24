"""Abstract transport backend interface.

All concrete transports (QUIC, Tailscale, WebSocket, Custom Tunnel)
implement the ``TransportBackend`` ABC so that ``ContinuumManager``
can probe, select, and fail over between them uniformly.
"""

from __future__ import annotations

import abc
import asyncio
import enum
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional


class TransportState(enum.Enum):
    """Lifecycle state of a transport connection."""

    IDLE = "idle"
    PROBING = "probing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    FAILED = "failed"
    CLOSED = "closed"


@dataclass
class ProbeResult:
    """Result of probing a target through a transport.

    ``reachable`` must be ``True`` for ``establish`` to be considered.
    Lower ``score`` is better (manager selects the minimum).
    """

    reachable: bool = False
    latency_ms: float = 1_000.0
    jitter_ms: float = 0.0
    throughput_mbps: float = 0.0
    transport_type: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        """Composite ranking — latency + jitter penalty − throughput bonus."""
        if not self.reachable:
            return float("inf")
        return self.latency_ms + self.jitter_ms * 2 - min(self.throughput_mbps, 100) * 0.5


@dataclass
class SendResult:
    """Acknowledgement returned after sending data over a connection."""

    bytes_sent: int
    latency_ms: float
    transport: str


class TransportError(Exception):
    """Raised when a transport operation cannot complete."""


class Connection:
    """Handle to an active transport-level connection.

    Concrete backends subclass this to expose their native I/O while
    sharing a common interface with the manager.
    """

    def __init__(self, transport_name: str, target_id: str) -> None:
        self.transport_name = transport_name
        self.target_id = target_id
        self.state: TransportState = TransportState.CONNECTING
        self.created_at: float = time.monotonic()
        self.bytes_sent: int = 0
        self.bytes_received: int = 0
        self._closed: bool = False

    # -- I/O -----------------------------------------------------------------

    async def send(self, data: bytes) -> SendResult:
        """Send *data* to the target.  Must be implemented by subclass."""
        raise NotImplementedError

    async def recv(self, max_bytes: int = 65_536) -> bytes:
        """Receive up to *max_bytes* from the target."""
        raise NotImplementedError

    async def recv_stream(self) -> AsyncIterator[bytes]:
        """Yield an asynchronous stream of message frames."""
        raise NotImplementedError

    # -- Health --------------------------------------------------------------

    def is_healthy(self) -> bool:
        """Return ``True`` if the connection is usable."""
        return self.state in (TransportState.CONNECTED, TransportState.DEGRADED)

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.created_at

    # -- Lifecycle -----------------------------------------------------------

    async def close(self) -> None:
        """Gracefully tear down the connection."""
        self._closed = True
        self.state = TransportState.CLOSED

    def __repr__(self) -> str:
        return (
            f"<Connection transport={self.transport_name!r} "
            f"target={self.target_id!r} state={self.state.value}>"
        )


class TransportBackend(abc.ABC):
    """Abstract base for continuum transport backends.

    Subclasses must implement :meth:`probe` and :meth:`establish`.
    Optional hooks ``startup`` / ``shutdown`` let transports hold
    long-lived resources (background tasks, sockets, child processes).
    """

    #: Stable identifier used by the manager for priority routing.
    name: str = "abstract"

    #: Relative priority — lower wins when scores are equal.
    priority: int = 100

    def __init__(self) -> None:
        self._state: TransportState = TransportState.IDLE

    # -- Abstract interface --------------------------------------------------

    @abc.abstractmethod
    async def probe(self, target: Any) -> ProbeResult:
        """Check whether *target* is reachable and estimate quality."""

    @abc.abstractmethod
    async def establish(self, target: Any) -> Connection:
        """Open and return a live :class:`Connection` to *target*."""

    # -- Optional lifecycle --------------------------------------------------

    async def startup(self) -> None:
        """Called once before the transport is first used."""
        self._state = TransportState.IDLE

    async def shutdown(self) -> None:
        """Release all resources held by the transport."""
        self._state = TransportState.CLOSED

    # -- Convenience ---------------------------------------------------------

    @property
    def state(self) -> TransportState:
        return self._state
