"""WebSocket transport fallback.

Provides ``WebSocketTransport`` as the highest-latency, most-compatible
transport option.  Used when UDP-based transports are unavailable or
blocked (e.g., restrictive corporate firewalls).

Uses the ``websockets`` package when available, otherwise falls back
to a minimal pure-Python WebSocket client implementation.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import os
import socket
import struct
import time
from typing import Any, AsyncIterator, Dict, Optional, Tuple

from .transport import (
    Connection,
    ProbeResult,
    SendResult,
    TransportBackend,
    TransportError,
    TransportState,
)
from .discovery import Node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebSocket frame codec (minimal, RFC 6455)
# ---------------------------------------------------------------------------


class WsOpcode:
    """WebSocket opcodes."""

    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    CLOSE = 0x8
    PING = 0x9
    PONG = 0xA


def _build_frame(opcode: int, payload: bytes, mask: bool = True) -> bytes:
    """Build a WebSocket frame with optional masking."""
    frame = bytearray()
    frame.append(0x80 | opcode)  # FIN + opcode
    length = len(payload)
    mask_bit = 0x80 if mask else 0x00
    if length < 126:
        frame.append(mask_bit | length)
    elif length < 65_536:
        frame.append(mask_bit | 126)
        frame.extend(struct.pack(">H", length))
    else:
        frame.append(mask_bit | 127)
        frame.extend(struct.pack(">Q", length))
    if mask:
        mask_key = os.urandom(4)
        frame.extend(mask_key)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        frame.extend(masked)
    else:
        frame.extend(payload)
    return bytes(frame)


def _parse_frame(data: bytes) -> Tuple[int, bytes, int]:
    """Parse a WebSocket frame. Returns (opcode, payload, bytes_consumed)."""
    if len(data) < 2:
        raise TransportError("ws frame too short")
    opcode = data[0] & 0x0F
    mask = data[1] & 0x80
    length = data[1] & 0x7F
    offset = 2
    if length == 126:
        if len(data) < 4:
            raise TransportError("ws frame truncated")
        length = struct.unpack(">H", data[2:4])[0]
        offset = 4
    elif length == 127:
        if len(data) < 10:
            raise TransportError("ws frame truncated")
        length = struct.unpack(">Q", data[2:10])[0]
        offset = 10
    mask_key = b""
    if mask:
        mask_key = data[offset : offset + 4]
        offset += 4
    if len(data) < offset + length:
        raise TransportError("ws frame payload truncated")
    payload = data[offset : offset + length]
    if mask:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    return opcode, payload, offset + length


# ---------------------------------------------------------------------------
# WebSocket connection
# ---------------------------------------------------------------------------


class WebSocketConnection(Connection):
    """A WebSocket connection over a TCP socket."""

    def __init__(
        self,
        transport_name: str,
        target: Node,
        sock: Optional[socket.socket] = None,
        path: str = "/continuum",
    ) -> None:
        super().__init__(transport_name, target.node_id)
        self._target = target
        self._sock = sock
        self._path = path
        self._recv_buffer = bytearray()
        self._send_lock = asyncio.Lock()
        if sock:
            self.state = TransportState.CONNECTED

    async def handshake(self, host: str) -> None:
        """Perform the WebSocket handshake."""
        if not self._sock:
            raise TransportError("ws socket not connected")
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {self._path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self._sock.sendall, request.encode())
            response = await asyncio.wait_for(
                loop.run_in_executor(None, self._sock.recv, 4_096), timeout=5.0
            )
            if b"101" not in response.split(b"\r\n")[0]:
                raise TransportError(
                    f"ws handshake failed: {response[:100]!r}"
                )
        except (OSError, asyncio.TimeoutError) as exc:
            raise TransportError(f"ws handshake failed: {exc}") from exc
        self.state = TransportState.CONNECTED

    async def send(self, data: bytes) -> SendResult:
        """Send a binary frame."""
        if not self._sock:
            raise TransportError("ws socket not connected")
        start = time.monotonic()
        frame = _build_frame(WsOpcode.BINARY, data)
        async with self._send_lock:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._sock.sendall, frame)
            except OSError as exc:
                self.state = TransportState.FAILED
                raise TransportError(f"ws send failed: {exc}") from exc
        latency = (time.monotonic() - start) * 1_000
        self.bytes_sent += len(data)
        return SendResult(bytes_sent=len(data), latency_ms=latency,
                          transport=self.transport_name)

    async def send_text(self, text: str) -> SendResult:
        """Send a text frame."""
        if not self._sock:
            raise TransportError("ws socket not connected")
        start = time.monotonic()
        frame = _build_frame(WsOpcode.TEXT, text.encode())
        async with self._send_lock:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._sock.sendall, frame)
            except OSError as exc:
                self.state = TransportState.FAILED
                raise TransportError(f"ws send_text failed: {exc}") from exc
        latency = (time.monotonic() - start) * 1_000
        self.bytes_sent += len(text)
        return SendResult(bytes_sent=len(text), latency_ms=latency,
                          transport=self.transport_name)

    async def recv(self, max_bytes: int = 65_536) -> bytes:
        """Receive the next binary frame payload."""
        if not self._sock:
            raise TransportError("ws socket not connected")
        loop = asyncio.get_running_loop()
        while True:
            # Try to parse from buffer first
            if self._recv_buffer:
                try:
                    opcode, payload, consumed = _parse_frame(
                        bytes(self._recv_buffer)
                    )
                    del self._recv_buffer[:consumed]
                    if opcode == WsOpcode.BINARY:
                        self.bytes_received += len(payload)
                        return payload
                    if opcode == WsOpcode.PING:
                        pong = _build_frame(WsOpcode.PONG, payload, mask=False)
                        await loop.run_in_executor(None, self._sock.sendall, pong)
                        continue
                    if opcode == WsOpcode.CLOSE:
                        self.state = TransportState.CLOSED
                        return b""
                    continue
                except TransportError:
                    pass
            # Need more data
            try:
                data = await loop.run_in_executor(None, self._sock.recv, max_bytes)
                if not data:
                    self.state = TransportState.CLOSED
                    return b""
                self._recv_buffer.extend(data)
            except OSError as exc:
                raise TransportError(f"ws recv failed: {exc}") from exc

    async def recv_stream(self) -> AsyncIterator[bytes]:
        """Yield payloads from incoming binary frames."""
        while self.state == TransportState.CONNECTED:
            try:
                payload = await asyncio.wait_for(self.recv(), timeout=30.0)
                if payload:
                    yield payload
            except asyncio.TimeoutError:
                continue
            except TransportError:
                break

    async def ping(self, payload: bytes = b"continuum") -> None:
        """Send a ping frame."""
        if not self._sock:
            return
        frame = _build_frame(WsOpcode.PING, payload)
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._sock.sendall, frame)
        except OSError:
            pass

    async def close(self, code: int = 1_000, reason: str = "") -> None:
        """Send a close frame and shutdown."""
        if self._sock and not self._closed:
            payload = struct.pack(">H", code) + reason.encode()
            frame = _build_frame(WsOpcode.CLOSE, payload, mask=False)
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._sock.sendall, frame)
            except OSError:
                pass
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        await super().close()


# ---------------------------------------------------------------------------
# WebSocket transport backend
# ---------------------------------------------------------------------------


class WebSocketTransport(TransportBackend):
    """WebSocket transport fallback.

    Works over any TCP connection (port 443, 8080, etc.) so it is
    the most firewall-compatible option.  Used as the last-resort
    transport when QUIC and Tailscale are unavailable.
    """

    name = "websocket_ws"
    priority = 40  # Lowest priority — highest latency

    def __init__(
        self,
        path: str = "/continuum",
        tls: bool = False,
        tls_verify: bool = True,
        port: Optional[int] = None,
    ) -> None:
        super().__init__()
        self._path = path
        self._tls = tls
        self._tls_verify = tls_verify
        self._port = port
        self._websockets_available = self._check_websockets()
        self._client: Optional[Any] = None  # websockets client placeholder

    @staticmethod
    def _check_websockets() -> bool:
        try:
            import websockets  # type: ignore[import-untyped]
            return True
        except ImportError:
            return False

    async def startup(self) -> None:
        if self._websockets_available:
            try:
                import websockets
                logger.info("using websockets library")
            except ImportError:
                pass
        self._state = TransportState.IDLE

    async def shutdown(self) -> None:
        await super().shutdown()

    # -- Probe ---------------------------------------------------------------

    async def probe(self, target: Node) -> ProbeResult:
        """Probe by attempting a TCP connection to the target."""
        port = self._port or target.continuum_port
        addr = target.wan_host or target.lan_ips[0] if target.lan_ips else target.tailscale_ip
        if not addr:
            return ProbeResult(reachable=False)

        start = time.monotonic()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            loop = asyncio.get_running_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, sock.connect, (addr, port)),
                timeout=5.0,
            )
            latency = (time.monotonic() - start) * 1_000
            sock.close()
            return ProbeResult(
                reachable=True,
                latency_ms=latency,
                jitter_ms=latency * 0.2,
                throughput_mbps=30.0,
                transport_type="websocket_tcp",
            )
        except (OSError, asyncio.TimeoutError):
            return ProbeResult(reachable=False)

    # -- Establish -----------------------------------------------------------

    async def establish(self, target: Node) -> WebSocketConnection:
        port = self._port or target.continuum_port
        addr = target.wan_host or target.lan_ips[0] if target.lan_ips else target.tailscale_ip
        if not addr:
            raise TransportError(
                f"node {target.node_id} has no address for WebSocket"
            )

        if self._websockets_available:
            return await self._establish_with_websockets(addr, port, target)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, sock.connect, (addr, port)),
                timeout=10.0,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            sock.close()
            raise TransportError(
                f"ws connect to {addr}:{port} failed: {exc}"
            ) from exc

        conn = WebSocketConnection(self.name, target, sock, self._path)
        try:
            await conn.handshake(f"{addr}:{port}")
        except TransportError:
            sock.close()
            raise
        return conn

    async def _establish_with_websockets(
        self, addr: str, port: int, target: Node
    ) -> WebSocketConnection:
        """Use the websockets library for a higher-level connection."""
        import websockets

        scheme = "wss" if self._tls else "ws"
        url = f"{scheme}://{addr}:{port}{self._path}"
        try:
            ws = await websockets.connect(
                url, ping_interval=20, ping_timeout=20
            )
        except Exception as exc:
            raise TransportError(
                f"websockets connect to {url} failed: {exc}"
            ) from exc

        # Wrap the websockets.WebSocketClientProtocol
        return _LibraryWebSocketConnection(self.name, target, ws)


class _LibraryWebSocketConnection(Connection):
    """Adapter for the ``websockets`` library connection."""

    def __init__(self, transport_name: str, target: Node, ws: Any) -> None:
        super().__init__(transport_name, target.node_id)
        self._ws = ws
        self.state = TransportState.CONNECTED

    async def send(self, data: bytes) -> SendResult:
        start = time.monotonic()
        await self._ws.send(data)
        latency = (time.monotonic() - start) * 1_000
        self.bytes_sent += len(data)
        return SendResult(bytes_sent=len(data), latency_ms=latency,
                          transport=self.transport_name)

    async def recv(self, max_bytes: int = 65_536) -> bytes:
        data = await self._ws.recv()
        if isinstance(data, str):
            data = data.encode()
        self.bytes_received += len(data)
        return data

    async def close(self) -> None:
        if not self._closed:
            try:
                await self._ws.close()
            except Exception:
                pass
        await super().close()
