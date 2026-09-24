"""Continuum load balancer with multi-connection striping.

Provides ``ContinuumLoadBalancer`` which distributes streams across
multiple connections for throughput, and ``MultiStream`` which
implements round-robin striping across parallel connections.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from .transport import (
    Connection,
    ProbeResult,
    SendResult,
    TransportError,
    TransportState,
)
from .discovery import Node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Striping mode
# ---------------------------------------------------------------------------


class StripeMode(enum.Enum):
    """How data is distributed across connections."""

    ROUND_ROBIN = "round_robin"
    STRIPE = "stripe"  # Fixed-size chunks
    ADAPTIVE = "adaptive"  # Based on connection quality


# ---------------------------------------------------------------------------
# Multi-stream
# ---------------------------------------------------------------------------


@dataclass
class StreamMetrics:
    """Per-stream performance metrics."""

    stream_id: int
    bytes_sent: int = 0
    bytes_received: int = 0
    latency_ms: float = 0.0
    errors: int = 0
    is_healthy: bool = True


class MultiStream:
    """Striped multi-connection stream.

    Wraps multiple :class:`Connection` objects and distributes
    writes across them for higher aggregate throughput.  Reads
    are multiplexed from all connections.
    """

    def __init__(
        self,
        connections: List[Connection],
        mode: StripeMode = StripeMode.ROUND_ROBIN,
        chunk_size: int = 16_384,
    ) -> None:
        self._connections = connections
        self._mode = mode
        self._chunk_size = chunk_size
        self._current_idx: int = 0
        self._lock = asyncio.Lock()
        self._metrics: Dict[int, StreamMetrics] = {
            i: StreamMetrics(stream_id=i) for i in range(len(connections))
        }
        self._closed: bool = False

    @property
    def num_connections(self) -> int:
        return len(self._connections)

    @property
    def healthy_connections(self) -> List[Connection]:
        return [c for c in self._connections if c.is_healthy()]

    # -- Write ---------------------------------------------------------------

    async def send(self, data: bytes) -> SendResult:
        """Send data across the striped connections."""
        if self._closed:
            raise TransportError("multistream is closed")

        if self._mode == StripeMode.ROUND_ROBIN:
            return await self._send_round_robin(data)
        if self._mode == StripeMode.STRIPE:
            return await self._send_striped(data)
        return await self._send_adaptive(data)

    async def _send_round_robin(self, data: bytes) -> SendResult:
        """Send the entire payload on the next available connection."""
        async with self._lock:
            conn = self._next_connection()
            idx = self._current_idx
        start = time.monotonic()
        try:
            result = await conn.send(data)
            self._metrics[idx].bytes_sent += result.bytes_sent
            return result
        except TransportError:
            self._metrics[idx].errors += 1
            if self._metrics[idx].errors > 3:
                self._metrics[idx].is_healthy = False
            raise

    async def _send_striped(self, data: bytes) -> SendResult:
        """Split data into chunks and send across connections."""
        chunks = [
            data[i : i + self._chunk_size]
            for i in range(0, len(data), self._chunk_size)
        ]
        total_sent = 0
        total_latency = 0.0

        async with self._lock:
            tasks = []
            for chunk in chunks:
                conn = self._next_connection()
                tasks.append(conn.send(chunk))
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                raise result
            total_sent += result.bytes_sent
            total_latency += result.latency_ms

        return SendResult(
            bytes_sent=total_sent,
            latency_ms=total_latency / max(len(results), 1),
            transport="multistream",
        )

    async def _send_adaptive(self, data: bytes) -> SendResult:
        """Send on the connection with the lowest recent latency."""
        healthy = self.healthy_connections
        if not healthy:
            raise TransportError("no healthy connections in multistream")

        # Pick the connection with the lowest RTT
        best = min(healthy, key=lambda c: getattr(c, "rtt_ms", 1_000.0))
        idx = self._connections.index(best)
        start = time.monotonic()
        result = await best.send(data)
        self._metrics[idx].bytes_sent += result.bytes_sent
        self._metrics[idx].latency_ms = result.latency_ms
        return result

    def _next_connection(self) -> Connection:
        """Round-robin selection of the next connection."""
        healthy = self.healthy_connections
        if not healthy:
            raise TransportError("no healthy connections")
        self._current_idx = (self._current_idx + 1) % len(healthy)
        return healthy[self._current_idx]

    # -- Read ----------------------------------------------------------------

    async def recv(self, max_bytes: int = 65_536) -> bytes:
        """Receive from the first connection that has data ready."""
        while not self._closed:
            for conn in self.healthy_connections:
                try:
                    data = await asyncio.wait_for(
                        conn.recv(max_bytes), timeout=0.1
                    )
                    if data:
                        return data
                except asyncio.TimeoutError:
                    continue
                except TransportError:
                    continue
            await asyncio.sleep(0.001)
        return b""

    async def recv_stream(self) -> AsyncIterator[bytes]:
        """Yield data from all connections as it arrives."""
        queue: asyncio.Queue[Tuple[int, bytes]] = asyncio.Queue()

        async def _reader(idx: int, conn: Connection) -> None:
            try:
                async for chunk in conn.recv_stream():
                    await queue.put((idx, chunk))
            except Exception:
                pass

        tasks = [
            asyncio.create_task(_reader(i, c))
            for i, c in enumerate(self._connections)
        ]
        try:
            while not self._closed:
                try:
                    idx, data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield data
                except asyncio.TimeoutError:
                    if not self.healthy_connections:
                        break
        finally:
            for task in tasks:
                task.cancel()

    # -- Health --------------------------------------------------------------

    def get_metrics(self) -> Dict[int, StreamMetrics]:
        return dict(self._metrics)

    def remove_connection(self, idx: int) -> None:
        """Remove a connection from the pool."""
        if 0 <= idx < len(self._connections):
            self._connections[idx] = _DeadConnection(self._connections[idx])

    # -- Lifecycle -----------------------------------------------------------

    async def close(self) -> None:
        """Close all underlying connections."""
        self._closed = True
        await asyncio.gather(
            *[c.close() for c in self._connections],
            return_exceptions=True,
        )


class _DeadConnection:
    """Placeholder for a removed connection that reports unhealthy."""

    def __init__(self, original: Connection) -> None:
        self.transport_name = original.transport_name
        self.target_id = original.target_id
        self.state = TransportState.FAILED
        self.bytes_sent = original.bytes_sent
        self.bytes_received = original.bytes_received
        self.created_at = original.created_at
        self._closed = True

    def is_healthy(self) -> bool:
        return False

    async def send(self, data: bytes) -> SendResult:
        raise TransportError("connection removed from pool")

    async def recv(self, max_bytes: int = 65_536) -> bytes:
        return b""

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Load balancer
# ---------------------------------------------------------------------------


class ContinuumLoadBalancer:
    """Distributes streams across multiple connections for throughput.

    The load balancer works with the :class:`ContinuumManager` to
    open multiple parallel connections to a target and stripe data
    across them.  It monitors per-connection health and can shed
    degraded connections automatically.
    """

    def __init__(
        self,
        max_connections: int = 4,
        min_connections: int = 1,
        stripe_mode: StripeMode = StripeMode.ROUND_ROBIN,
        chunk_size: int = 16_384,
        health_check_interval: float = 5.0,
    ) -> None:
        self._max_connections = max_connections
        self._min_connections = min_connections
        self._stripe_mode = stripe_mode
        self._chunk_size = chunk_size
        self._health_check_interval = health_check_interval
        self._streams: Dict[str, MultiStream] = {}
        self._health_task: Optional[asyncio.Task[None]] = None
        self._closed: bool = False

    # -- Stream management ---------------------------------------------------

    async def create_multiconn_stream(
        self,
        target: Node,
        connect_fn,  # Callable[[Node], Awaitable[Connection]]
        stream_type: str = "data",
    ) -> MultiStream:
        """Open multiple connections and stripe data across them.

        ``connect_fn`` is an async callable that returns a fresh
        :class:`Connection`` for the given target.  Typically this
        is :meth:`ContinuumManager.connect`.
        """
        num = self.recommend_connections(target)
        logger.info(
            "creating multiconn stream to %s with %d connections",
            target.node_id, num,
        )

        connections: List[Connection] = []
        errors: List[Exception] = []
        for i in range(num):
            try:
                conn = await connect_fn(target)
                connections.append(conn)
            except Exception as exc:
                errors.append(exc)
                logger.warning(
                    "connection %d/%d to %s failed: %s",
                    i + 1, num, target.node_id, exc,
                )

        if not connections:
            raise TransportError(
                f"all {num} connection attempts to {target.node_id} failed"
            )

        stream = MultiStream(
            connections,
            mode=self._stripe_mode,
            chunk_size=self._chunk_size,
        )
        self._streams[target.node_id] = stream
        return stream

    def recommend_connections(self, target: Node) -> int:
        """Recommend the number of parallel connections for a target.

        Based on available bandwidth and the number of known paths.
        """
        num_paths = 1
        if target.tailscale_ip:
            num_paths += 1
        num_paths += len(target.lan_ips)
        if target.wan_host:
            num_paths += 1

        # For high-bandwidth scenarios, use more connections
        if target.bandwidth_mbps > 100:
            recommended = 1
        elif target.bandwidth_mbps > 50:
            recommended = min(2, num_paths)
        else:
            recommended = min(self._max_connections, max(num_paths, 2))

        return max(self._min_connections, recommended)

    def get_stream(self, target_id: str) -> Optional[MultiStream]:
        """Retrieve an existing multistream by target ID."""
        return self._streams.get(target_id)

    # -- Health monitoring ---------------------------------------------------

    async def start_health_monitor(self) -> None:
        """Start the background health-check task."""
        if self._health_task is None:
            self._health_task = asyncio.create_task(self._health_loop())

    async def stop_health_monitor(self) -> None:
        """Stop the background health-check task."""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None

    async def _health_loop(self) -> None:
        """Periodically check stream health and shed dead connections."""
        while not self._closed:
            try:
                await asyncio.sleep(self._health_check_interval)
                for target_id, stream in list(self._streams.items()):
                    if not stream.healthy_connections:
                        logger.warning(
                            "stream to %s has no healthy connections",
                            target_id,
                        )
                        self._streams.pop(target_id, None)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("health check error: %s", exc)

    # -- Lifecycle -----------------------------------------------------------

    async def close(self) -> None:
        """Close all managed streams."""
        self._closed = True
        await self.stop_health_monitor()
        await asyncio.gather(
            *[s.close() for s in self._streams.values()],
            return_exceptions=True,
        )
        self._streams.clear()
