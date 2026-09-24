"""Custom tunnel backend for SSH/TLS/SOCKS5 proxying.

Provides ``CustomTunnelBackend`` which supports user-configured
tunnel types for environments where Tailscale and direct QUIC are
not viable.
"""

from __future__ import annotations

import asyncio
import base64
import enum
import json
import logging
import os
import socket
import ssl
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
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
# Tunnel type registry
# ---------------------------------------------------------------------------


class TunnelType(enum.Enum):
    """Supported tunnel types."""

    SSH = "ssh"
    TLS = "tls"
    SOCKS5 = "socks5"
    HTTP_PROXY = "http_proxy"


@dataclass
class TunnelConfig:
    """Configuration for a custom tunnel.

    Fields vary by tunnel type; unused fields are ignored.
    """

    type: TunnelType = TunnelType.SOCKS5
    host: str = ""
    port: int = 0
    username: Optional[str] = None
    password: Optional[str] = None
    ssh_key_path: Optional[Path] = None
    ssh_key_passphrase: Optional[str] = None
    remote_host: str = "127.0.0.1"
    remote_port: int = 4_433
    tls_cert_path: Optional[Path] = None
    tls_key_path: Optional[Path] = None
    tls_ca_path: Optional[Path] = None
    tls_verify: bool = True
    tls_server_name: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tunnel connections
# ---------------------------------------------------------------------------


class TunnelConnection(Connection):
    """Base for tunnel connections.  Wraps a TCP socket through a proxy."""

    def __init__(
        self,
        transport_name: str,
        target: Node,
        sock: Optional[socket.socket] = None,
    ) -> None:
        super().__init__(transport_name, target.node_id)
        self._target = target
        self._sock = sock
        self._send_lock = asyncio.Lock()
        if sock:
            self.state = TransportState.CONNECTED

    async def send(self, data: bytes) -> SendResult:
        if not self._sock:
            raise TransportError("tunnel socket not connected")
        start = time.monotonic()
        async with self._send_lock:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._sock.sendall, data)
            except OSError as exc:
                self.state = TransportState.FAILED
                raise TransportError(f"tunnel send failed: {exc}") from exc
        latency = (time.monotonic() - start) * 1_000
        self.bytes_sent += len(data)
        return SendResult(bytes_sent=len(data), latency_ms=latency,
                          transport=self.transport_name)

    async def recv(self, max_bytes: int = 65_536) -> bytes:
        if not self._sock:
            raise TransportError("tunnel socket not connected")
        loop = asyncio.get_running_loop()
        try:
            data = await loop.run_in_executor(
                None, self._sock.recv, max_bytes
            )
            if not data:
                self.state = TransportState.CLOSED
            self.bytes_received += len(data)
            return data
        except OSError as exc:
            raise TransportError(f"tunnel recv failed: {exc}") from exc

    async def recv_stream(self) -> AsyncIterator[bytes]:
        while self.state == TransportState.CONNECTED:
            try:
                payload = await asyncio.wait_for(self.recv(), timeout=30.0)
                if payload:
                    yield payload
            except asyncio.TimeoutError:
                continue
            except TransportError:
                break

    async def close(self) -> None:
        if self._sock and not self._closed:
            try:
                self._sock.close()
            except OSError:
                pass
        await super().close()


# ---------------------------------------------------------------------------
# SSH tunnel
# ---------------------------------------------------------------------------


class SSHTunnelConnection(TunnelConnection):
    """SSH local port-forward tunnel connection.

    Uses ``subprocess`` to spawn ``ssh -L`` or ``asyncssh`` when
    available for a more integrated approach.
    """

    def __init__(
        self,
        transport_name: str,
        target: Node,
        sock: socket.socket,
        ssh_host: str,
        ssh_port: int,
    ) -> None:
        super().__init__(transport_name, target, sock)
        self._ssh_host = ssh_host
        self._ssh_port = ssh_port

    @classmethod
    async def connect(
        cls,
        transport_name: str,
        target: Node,
        ssh_host: str,
        ssh_port: int = 22,
        username: Optional[str] = None,
        password: Optional[str] = None,
        key_path: Optional[Path] = None,
        remote_host: str = "127.0.0.1",
        remote_port: int = 4_433,
    ) -> "SSHTunnelConnection":
        """Establish an SSH tunnel and return a connected instance.

        If ``asyncssh`` is available it is used directly; otherwise a
        raw TCP socket to the SSH-forwarded port is returned (caller
        must have started ``ssh -L`` externally).
        """
        # Try asyncssh first
        try:
            import asyncssh  # type: ignore[import-untyped]
            return await cls._connect_asyncssh(
                transport_name, target, ssh_host, ssh_port,
                username, password, key_path, remote_host, remote_port,
            )
        except ImportError:
            logger.debug("asyncssh not available; using raw socket fallback")

        # Fallback: assume external SSH tunnel is already running locally
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(
                    None, sock.connect, ("127.0.0.1", remote_port)
                ),
                timeout=5.0,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            sock.close()
            raise TransportError(f"ssh tunnel connect failed: {exc}") from exc
        return cls(transport_name, target, sock, ssh_host, ssh_port)

    @classmethod
    async def _connect_asyncssh(
        cls,
        transport_name: str,
        target: Node,
        ssh_host: str,
        ssh_port: int,
        username: Optional[str],
        password: Optional[str],
        key_path: Optional[Path],
        remote_host: str,
        remote_port: int,
    ) -> "SSHTunnelConnection":
        import asyncssh

        client_keys = [str(key_path)] if key_path else None
        try:
            conn = await asyncssh.connect(
                ssh_host,
                port=ssh_port,
                username=username,
                password=password,
                client_keys=client_keys,
                known_hosts=None,
            )
            listener = await conn.forward_local_port(
                "127.0.0.1", 0, remote_host, remote_port
            )
            port = listener.get_port()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, sock.connect, ("127.0.0.1", port))
            return cls(transport_name, target, sock, ssh_host, ssh_port)
        except Exception as exc:
            raise TransportError(f"asyncssh connect failed: {exc}") from exc


# ---------------------------------------------------------------------------
# TLS tunnel
# ---------------------------------------------------------------------------


class TLSTunnelConnection(TunnelConnection):
    """Mutual TLS tunnel connection.

    Wraps a standard TCP socket in TLS (optionally mTLS) using the
    ``ssl`` module.
    """

    def __init__(
        self,
        transport_name: str,
        target: Node,
        sock: socket.socket,
        ssl_context: Optional[ssl.SSLContext] = None,
        server_hostname: Optional[str] = None,
    ) -> None:
        super().__init__(transport_name, target, sock)
        self._ssl_context = ssl_context
        self._server_hostname = server_hostname
        self._sslobj: Optional[ssl.SSLSocket] = None

    async def handshake(self) -> None:
        """Perform the TLS handshake."""
        if not self._ssl_context:
            self._ssl_context = ssl.create_default_context()
        loop = asyncio.get_running_loop()
        try:
            self._sslobj = self._ssl_context.wrap_socket(
                self._sock,
                server_hostname=self._server_hostname,
                do_handshake_on_connect=False,
            )
            # Complete handshake asynchronously
            while True:
                try:
                    self._sslobj.do_handshake()
                    break
                except ssl.SSLWantReadError:
                    await asyncio.sleep(0.01)
                except ssl.SSLWantWriteError:
                    await asyncio.sleep(0.01)
        except Exception as exc:
            raise TransportError(f"tls handshake failed: {exc}") from exc
        self.state = TransportState.CONNECTED

    async def send(self, data: bytes) -> SendResult:
        if not self._sslobj:
            raise TransportError("tls not handshaked")
        start = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._sslobj.sendall, data)
        except OSError as exc:
            self.state = TransportState.FAILED
            raise TransportError(f"tls send failed: {exc}") from exc
        latency = (time.monotonic() - start) * 1_000
        self.bytes_sent += len(data)
        return SendResult(bytes_sent=len(data), latency_ms=latency,
                          transport=self.transport_name)

    async def recv(self, max_bytes: int = 65_536) -> bytes:
        if not self._sslobj:
            raise TransportError("tls not handshaked")
        loop = asyncio.get_running_loop()
        try:
            data = await loop.run_in_executor(
                None, self._sslobj.recv, max_bytes
            )
            if not data:
                self.state = TransportState.CLOSED
            self.bytes_received += len(data)
            return data
        except OSError as exc:
            raise TransportError(f"tls recv failed: {exc}") from exc


# ---------------------------------------------------------------------------
# SOCKS5 tunnel
# ---------------------------------------------------------------------------


class SOCKS5TunnelConnection(TunnelConnection):
    """SOCKS5 proxy tunnel connection."""

    def __init__(
        self,
        transport_name: str,
        target: Node,
        sock: socket.socket,
    ) -> None:
        super().__init__(transport_name, target, sock)

    async def handshake(
        self,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """Perform SOCKS5 authentication and connect to target."""
        loop = asyncio.get_running_loop()
        try:
            # Method negotiation
            if username and password:
                auth_methods = bytes([0x02, 0x00, 0x02])  # No-auth + username/pw
            else:
                auth_methods = bytes([0x01, 0x00])  # No-auth only
            await loop.run_in_executor(None, self._sock.sendall, auth_methods)

            response = await asyncio.wait_for(
                loop.run_in_executor(None, self._sock.recv, 2), timeout=5.0
            )
            if response[0] != 0x05:
                raise TransportError(f"invalid SOCKS version: {response[0]}")

            chosen_auth = response[1]
            if chosen_auth == 0x02:
                # Username/password auth
                auth = (
                    bytes([0x01, len(username or "")])
                    + (username or "").encode()
                    + bytes([len(password or "")])
                    + (password or "").encode()
                )
                await loop.run_in_executor(None, self._sock.sendall, auth)
                auth_resp = await asyncio.wait_for(
                    loop.run_in_executor(None, self._sock.recv, 2), timeout=5.0
                )
                if auth_resp[1] != 0x00:
                    raise TransportError("socks5 authentication failed")

            # Connect request
            try:
                addr_bytes = socket.inet_aton(host)
                atype = 0x01  # IPv4
            except OSError:
                addr_bytes = socket.inet_pton(socket.AF_INET6, host)
                atype = 0x04  # IPv6
            req = (
                bytes([0x05, 0x01, 0x00, atype])
                + addr_bytes
                + struct.pack(">H", port)
            )
            await loop.run_in_executor(None, self._sock.sendall, req)
            connect_resp = await asyncio.wait_for(
                loop.run_in_executor(None, self._sock.recv, 256), timeout=10.0
            )
            if connect_resp[1] != 0x00:
                raise TransportError(
                    f"socks5 connect failed with code {connect_resp[1]}"
                )
        except (OSError, asyncio.TimeoutError) as exc:
            raise TransportError(f"socks5 handshake failed: {exc}") from exc
        self.state = TransportState.CONNECTED


# ---------------------------------------------------------------------------
# Custom tunnel backend
# ---------------------------------------------------------------------------


class CustomTunnelBackend(TransportBackend):
    """User-configured tunnel backend (SSH/TLS/SOCKS5/HTTP_PROXY).

    This transport is used when Tailscale is unavailable and QUIC
    cannot be established.  The user provides a :class:`TunnelConfig`
    describing how to reach the target via an intermediary proxy or
    tunnel.
    """

    name = "custom_tunnel"
    priority = 30

    def __init__(self, config: Optional[TunnelConfig] = None) -> None:
        super().__init__()
        self._config = config or TunnelConfig()

    async def startup(self) -> None:
        self._state = TransportState.IDLE

    async def shutdown(self) -> None:
        await super().shutdown()

    # -- Probe ---------------------------------------------------------------

    async def probe(self, target: Node) -> ProbeResult:
        """Check whether the tunnel endpoint is reachable."""
        if not self._config.host:
            return ProbeResult(reachable=False)

        start = time.monotonic()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            loop = asyncio.get_running_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None, sock.connect, (self._config.host, self._config.port)
                ),
                timeout=5.0,
            )
            latency = (time.monotonic() - start) * 1_000
            sock.close()
            return ProbeResult(
                reachable=True,
                latency_ms=latency,
                jitter_ms=latency * 0.3,
                throughput_mbps=20.0,
                transport_type=self._config.type.value,
            )
        except (OSError, asyncio.TimeoutError):
            return ProbeResult(reachable=False)

    # -- Establish -----------------------------------------------------------

    async def establish(self, target: Node) -> TunnelConnection:
        """Establish the tunnel based on the configured type."""
        if self._config.type == TunnelType.SSH:
            return await self._establish_ssh(target)
        if self._config.type == TunnelType.TLS:
            return await self._establish_tls(target)
        if self._config.type == TunnelType.SOCKS5:
            return await self._establish_socks5(target)
        if self._config.type == TunnelType.HTTP_PROXY:
            return await self._establish_http_proxy(target)
        raise TransportError(f"unsupported tunnel type: {self._config.type}")

    async def _establish_ssh(self, target: Node) -> SSHTunnelConnection:
        return await SSHTunnelConnection.connect(
            transport_name=self.name,
            target=target,
            ssh_host=self._config.host,
            ssh_port=self._config.port,
            username=self._config.username,
            password=self._config.password,
            key_path=self._config.ssh_key_path,
            remote_host=self._config.remote_host,
            remote_port=self._config.remote_port or target.continuum_port,
        )

    async def _establish_tls(self, target: Node) -> TLSTunnelConnection:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(
                    None, sock.connect, (self._config.host, self._config.port)
                ),
                timeout=10.0,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            sock.close()
            raise TransportError(f"tls tunnel connect failed: {exc}") from exc

        ctx: Optional[ssl.SSLContext] = None
        if self._config.tls_cert_path:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.load_cert_chain(
                certfile=str(self._config.tls_cert_path),
                keyfile=(
                    str(self._config.tls_key_path)
                    if self._config.tls_key_path
                    else None
                ),
            )
            if self._config.tls_ca_path:
                ctx.load_verify_locations(cafile=str(self._config.tls_ca_path))
            ctx.check_hostname = self._config.tls_verify
            ctx.verify_mode = ssl.CERT_REQUIRED if self._config.tls_verify else ssl.CERT_NONE
        else:
            ctx = ssl.create_default_context()
            if not self._config.tls_verify:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

        conn = TLSTunnelConnection(
            self.name, target, sock, ctx, self._config.tls_server_name
        )
        await conn.handshake()
        return conn

    async def _establish_socks5(self, target: Node) -> SOCKS5TunnelConnection:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(
                    None, sock.connect, (self._config.host, self._config.port)
                ),
                timeout=10.0,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            sock.close()
            raise TransportError(f"socks5 connect failed: {exc}") from exc

        remote_host = self._config.remote_host or (
            target.lan_ips[0] if target.lan_ips else target.tailscale_ip or "127.0.0.1"
        )
        remote_port = self._config.remote_port or target.continuum_port
        conn = SOCKS5TunnelConnection(self.name, target, sock)
        await conn.handshake(
            remote_host,
            remote_port,
            self._config.username,
            self._config.password,
        )
        return conn

    async def _establish_http_proxy(self, target: Node) -> TunnelConnection:
        """HTTP CONNECT proxy tunnel."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(
                    None, sock.connect, (self._config.host, self._config.port)
                ),
                timeout=10.0,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            sock.close()
            raise TransportError(f"http proxy connect failed: {exc}") from exc

        remote_host = self._config.remote_host or (
            target.lan_ips[0] if target.lan_ips else target.tailscale_ip or "127.0.0.1"
        )
        remote_port = self._config.remote_port or target.continuum_port

        # HTTP CONNECT request
        connect_req = (
            f"CONNECT {remote_host}:{remote_port} HTTP/1.1\r\n"
            f"Host: {remote_host}:{remote_port}\r\n"
        )
        if self._config.username and self._config.password:
            auth = base64.b64encode(
                f"{self._config.username}:{self._config.password}".encode()
            ).decode()
            connect_req += f"Proxy-Authorization: Basic {auth}\r\n"
        connect_req += "\r\n"

        try:
            await loop.run_in_executor(
                None, sock.sendall, connect_req.encode()
            )
            response = await asyncio.wait_for(
                loop.run_in_executor(None, sock.recv, 4_096), timeout=10.0
            )
            if b"200" not in response.split(b"\r\n")[0]:
                raise TransportError(
                    f"http proxy CONNECT failed: {response[:100]!r}"
                )
        except (OSError, asyncio.TimeoutError) as exc:
            sock.close()
            raise TransportError(f"http proxy connect failed: {exc}") from exc

        return TunnelConnection(self.name, target, sock)
