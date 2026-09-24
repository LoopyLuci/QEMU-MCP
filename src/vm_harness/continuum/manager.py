"""Continuum manager — transport selection, routing, and failover.

The :class:`ContinuumManager` is the primary entry point for the
continuum networking layer.  It coordinates:

* Transport backends (:class:`TransportBackend` subclasses) with
  automatic priority-ordered probing and selection.
* Node discovery via :class:`NodeDiscovery`.
* Security policy enforcement via :class:`SecurityPolicy`.
* Load-balanced multi-connection streaming via
  :class:`ContinuumLoadBalancer`.

Typical usage::

    manager = ContinuumManager()
    manager.add_transport(QUICTransport())
    manager.add_transport(TailscaleBackend())
    manager.add_transport(WebSocketTransport())

    await manager.startup()

    # Discover and connect
    nodes = await manager.discovery.discover_all()
    conn = await manager.connect(nodes[0])

    # Send/receive
    result = await conn.send(b"hello")
    data = await conn.recv()

    await manager.shutdown()
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

from .transport import (
    Connection,
    ProbeResult,
    SendResult,
    TransportBackend,
    TransportError,
    TransportState,
)
from .discovery import Node, NodeDiscovery
from .security import SecurityPolicy, CertificateBundle
from .load_balancer import ContinuumLoadBalancer, MultiStream

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection state & route
# ---------------------------------------------------------------------------


class ConnectionState(enum.Enum):
    """High-level connection state for the auto-fallback state machine."""

    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    FALLING_BACK = "falling_back"
    RETRY_WAIT = "retry_wait"
    CLOSED = "closed"


@dataclass
class Route:
    """An active route to a destination node."""

    node_id: str
    transport_name: str
    connection: Connection
    state: ConnectionState = ConnectionState.CONNECTING
    created_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)
    bytes_sent: int = 0
    bytes_received: int = 0
    errors: int = 0

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.created_at

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_activity

    def is_healthy(self) -> bool:
        return self.state in (
            ConnectionState.CONNECTED,
            ConnectionState.DEGRADED,
        ) and self.connection.is_healthy()

    def touch(self) -> None:
        self.last_activity = time.monotonic()


# ---------------------------------------------------------------------------
# Continuum manager
# ---------------------------------------------------------------------------


class ContinuumManager:
    """Manages all network transports with automatic selection and fallback.

    The manager maintains a priority-ordered list of transport backends,
    probes them in parallel when connecting to a target, and selects
    the best-scoring transport.  It monitors active routes and can
    seamlessly fail over to a backup transport when the primary
    degrades.
    """

    #: Default transport priority order (lower = tried first).
    DEFAULT_PRIORITY = [
        "quic_direct",
        "tailscale_wg",
        "custom_tunnel",
        "websocket_ws",
        "http3",
    ]

    def __init__(
        self,
        discovery: Optional[NodeDiscovery] = None,
        security_policy: Optional[SecurityPolicy] = None,
        load_balancer: Optional[ContinuumLoadBalancer] = None,
        max_retries: int = 3,
        retry_base_delay: float = 0.1,
        route_max_age: float = 3_600.0,
        route_max_idle: float = 600.0,
        enable_health_monitor: bool = True,
    ) -> None:
        self._transports: Dict[str, TransportBackend] = {}
        self._transport_order: List[str] = []
        self._active_routes: Dict[str, Route] = {}
        self._route_lock = asyncio.Lock()

        # Subsystems
        self.discovery = discovery or NodeDiscovery()
        self.security_policy = security_policy
        self.load_balancer = load_balancer or ContinuumLoadBalancer()

        # Configuration
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._route_max_age = route_max_age
        self._route_max_idle = route_max_idle
        self._enable_health_monitor = enable_health_monitor

        # Background tasks
        self._health_task: Optional[asyncio.Task[None]] = None
        self._cleanup_task: Optional[asyncio.Task[None]] = None
        self._started: bool = False

    # -- Transport management ------------------------------------------------

    def add_transport(self, transport: TransportBackend) -> None:
        """Register a transport backend.

        Transports are automatically sorted by their ``priority``
        attribute (lower = higher priority).
        """
        self._transports[transport.name] = transport
        self._sort_transports()
        logger.debug("transport registered: %s (priority=%d)",
                     transport.name, transport.priority)

    def remove_transport(self, name: str) -> Optional[TransportBackend]:
        """Remove and return a transport by name."""
        transport = self._transports.pop(name, None)
        if transport:
            self._transport_order = [
                n for n in self._transport_order if n != name
            ]
        return transport

    def get_transport(self, name: str) -> Optional[TransportBackend]:
        return self._transports.get(name)

    def list_transports(self) -> List[str]:
        return list(self._transport_order)

    def _sort_transports(self) -> None:
        """Sort transports by priority (ascending)."""
        self._transport_order = sorted(
            self._transports.keys(),
            key=lambda n: self._transports[n].priority,
        )

    # -- Lifecycle -----------------------------------------------------------

    async def startup(self) -> None:
        """Start all transports and background tasks."""
        if self._started:
            return
        logger.info("starting continuum manager with %d transports",
                     len(self._transports))

        # Start transports
        results = await asyncio.gather(
            *[t.startup() for t in self._transports.values()],
            return_exceptions=True,
        )
        for name, result in zip(self._transport_order, results):
            if isinstance(result, Exception):
                logger.warning("transport %s startup failed: %s", name, result)

        # Start load balancer health monitor
        if self._enable_health_monitor:
            await self.load_balancer.start_health_monitor()

        # Start background tasks
        self._health_task = asyncio.create_task(self._health_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        self._started = True
        logger.info("continuum manager started")

    async def shutdown(self) -> None:
        """Gracefully shut down all transports and background tasks."""
        if not self._started:
            return
        logger.info("shutting down continuum manager")

        # Cancel background tasks
        for task in (self._health_task, self._cleanup_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._health_task = None
        self._cleanup_task = None

        # Close all active routes
        async with self._route_lock:
            for route in list(self._active_routes.values()):
                await self._close_route(route)
            self._active_routes.clear()

        # Shut down load balancer
        await self.load_balancer.close()

        # Shut down transports
        await asyncio.gather(
            *[t.shutdown() for t in self._transports.values()],
            return_exceptions=True,
        )

        self._started = False
        logger.info("continuum manager shut down")

    # -- Connection ---------------------------------------------------------

    async def connect(self, target: Node) -> Connection:
        """Connect to *target* using the best available transport.

        Tries all transports in parallel, selects the one with the
        lowest probe score, and establishes a connection.  Falls back
        to lower-priority transports on failure.
        """
        # Check for existing healthy route
        existing = self._active_routes.get(target.node_id)
        if existing and existing.is_healthy():
            existing.touch()
            return existing.connection

        # Probe all transports concurrently
        probes = await self._probe_all(target)

        # Sort by score (lower is better)
        reachable = [
            (name, result) for name, result in probes.items()
            if result.reachable
        ]
        if not reachable:
            raise TransportError(
                f"node {target.node_id} is unreachable via any transport"
            )

        reachable.sort(key=lambda x: x[1].score)

        # Try each transport in order until one succeeds
        last_error: Optional[Exception] = None
        for name, probe_result in reachable:
            for attempt in range(self._max_retries):
                try:
                    transport = self._transports[name]
                    conn = await transport.establish(target)
                    route = Route(
                        node_id=target.node_id,
                        transport_name=name,
                        connection=conn,
                        state=ConnectionState.CONNECTED,
                    )
                    async with self._route_lock:
                        # Close old route if any
                        old = self._active_routes.get(target.node_id)
                        if old:
                            await self._close_route(old)
                        self._active_routes[target.node_id] = route
                    logger.info(
                        "connected to %s via %s (score=%.1f, attempt=%d)",
                        target.node_id, name, probe_result.score, attempt + 1,
                    )
                    return conn
                except Exception as exc:
                    last_error = exc
                    logger.debug(
                        "transport %s attempt %d to %s failed: %s",
                        name, attempt + 1, target.node_id, exc,
                    )
                    delay = self._retry_base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)

        raise TransportError(
            f"all transports failed to reach {target.node_id}: {last_error}"
        )

    async def disconnect(self, node_id: str) -> None:
        """Close the active route to *node_id*."""
        route = self._active_routes.pop(node_id, None)
        if route:
            await self._close_route(route)

    async def send_to(self, target: Node, data: bytes) -> SendResult:
        """Send data to *target* with automatic retry on failure."""
        for attempt in range(self._max_retries):
            route = self._active_routes.get(target.node_id)
            if not route or not route.is_healthy():
                route = await self._reconnect_route(target)
            try:
                result = await route.connection.send(data)
                route.bytes_sent += result.bytes_sent
                route.touch()
                return result
            except TransportError:
                route.errors += 1
                route.state = ConnectionState.FALLING_BACK
                async with self._route_lock:
                    self._active_routes.pop(target.node_id, None)
                delay = self._retry_base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
        raise TransportError(
            f"send to {target.node_id} failed after {self._max_retries} attempts"
        )

    async def recv_from(self, target: Node, max_bytes: int = 65_536) -> bytes:
        """Receive data from *target*."""
        route = self._active_routes.get(target.node_id)
        if not route or not route.is_healthy():
            route = await self._reconnect_route(target)
        data = await route.connection.recv(max_bytes)
        route.bytes_received += len(data)
        route.touch()
        return data

    # -- Streaming ----------------------------------------------------------

    async def stream(
        self,
        target: Node,
        stream_type: str = "data",
    ) -> Connection:
        """Establish a media stream over the best available transport.

        ``stream_type`` can be ``"video"``, ``"audio"``, ``"input"``,
        or ``"data"``.  Higher-priority streams get lower QUIC stream
        IDs.
        """
        priority_map = {"video": 0, "input": 1, "audio": 2, "data": 3}
        priority = priority_map.get(stream_type, 3)

        conn = await self.connect(target)
        # If the connection supports stream multiplexing, open a sub-stream
        if hasattr(conn, "open_stream"):
            return conn.open_stream(priority=priority)
        return conn

    async def create_multiconn_stream(
        self,
        target: Node,
        stream_type: str = "data",
    ) -> MultiStream:
        """Create a load-balanced multi-connection stream."""
        return await self.load_balancer.create_multiconn_stream(
            target=target,
            connect_fn=self.connect,
            stream_type=stream_type,
        )

    # -- Internals -----------------------------------------------------------

    async def _probe_all(self, target: Node) -> Dict[str, ProbeResult]:
        """Probe all transports concurrently and return results."""
        async def _safe_probe(
            name: str, transport: TransportBackend
        ) -> Tuple[str, ProbeResult]:
            try:
                result = await asyncio.wait_for(
                    transport.probe(target), timeout=5.0
                )
                return name, result
            except Exception as exc:
                logger.debug("probe %s failed: %s", name, exc)
                return name, ProbeResult(reachable=False)

        results = await asyncio.gather(
            *[
                _safe_probe(name, transport)
                for name, transport in self._transports.items()
            ]
        )
        return dict(results)

    async def _reconnect_route(self, target: Node) -> Route:
        """Reconnect to *target* and return the new route."""
        conn = await self.connect(target)
        route = Route(
            node_id=target.node_id,
            transport_name=conn.transport_name,
            connection=conn,
            state=ConnectionState.CONNECTED,
        )
        async with self._route_lock:
            self._active_routes[target.node_id] = route
        return route

    async def _close_route(self, route: Route) -> None:
        """Close a route and update its state."""
        route.state = ConnectionState.CLOSED
        try:
            await route.connection.close()
        except Exception as exc:
            logger.debug("error closing route to %s: %s", route.node_id, exc)

    # -- Background loops ---------------------------------------------------

    async def _health_loop(self) -> None:
        """Periodically check route health and trigger failover."""
        while self._started:
            try:
                await asyncio.sleep(5.0)
                async with self._route_lock:
                    for node_id, route in list(self._active_routes.items()):
                        if route.state == ConnectionState.DEGRADED:
                            # Attempt failover
                            logger.info(
                                "route to %s degraded; attempting failover",
                                node_id,
                            )
                            asyncio.create_task(self._failover(route))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("health loop error: %s", exc)

    async def _failover(self, route: Route) -> None:
        """Attempt to fail over a degraded route to a new transport."""
        route.state = ConnectionState.FALLING_BACK
        try:
            # Find the node
            node = await self.discovery.find(route.node_id)
            if not node:
                logger.warning("cannot failover: node %s not found", route.node_id)
                return
            # Close old connection
            await route.connection.close()
            # Establish new connection (will use next-best transport)
            new_conn = await self.connect(node)
            route.connection = new_conn
            route.state = ConnectionState.CONNECTED
            route.errors = 0
            logger.info("failover to %s complete via %s",
                        route.node_id, new_conn.transport_name)
        except Exception as exc:
            logger.warning("failover to %s failed: %s", route.node_id, exc)
            route.state = ConnectionState.CLOSED

    async def _cleanup_loop(self) -> None:
        """Periodically clean up stale routes."""
        while self._started:
            try:
                await asyncio.sleep(60.0)
                async with self._route_lock:
                    stale = [
                        nid for nid, route in self._active_routes.items()
                        if route.age_seconds > self._route_max_age
                        or route.idle_seconds > self._route_max_idle
                    ]
                    for nid in stale:
                        route = self._active_routes.pop(nid)
                        await self._close_route(route)
                        logger.debug("cleaned up stale route to %s", nid)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("cleanup loop error: %s", exc)

    # -- Status --------------------------------------------------------------

    def get_route(self, node_id: str) -> Optional[Route]:
        """Return the active route to *node_id*, if any."""
        return self._active_routes.get(node_id)

    def list_routes(self) -> List[Route]:
        """Return all active routes."""
        return list(self._active_routes.values())

    @property
    def is_started(self) -> bool:
        return self._started

    def __repr__(self) -> str:
        return (
            f"<ContinuumManager transports={len(self._transports)} "
            f"routes={len(self._active_routes)} "
            f"started={self._started}>"
        )
