"""Continuum hybrid networking transport backend.

The continuum package provides multi-transport networking with automatic
selection, load balancing, and failover for the VM-Harness platform.

Transport priority:
    1. quic_direct — QUIC over UDP (lowest latency, 0-RTT)
    2. tailscale_wg — Tailscale WireGuard tunnel
    3. custom_tunnel — SSH/TLS/SOCKS5 proxy tunnels
    4. websocket_ws — WebSocket fallback
    5. http3 — HTTP/3 (QUIC over web ports)
"""

from .manager import ContinuumManager, Route, ConnectionState
from .transport import (
    TransportBackend,
    ProbeResult,
    Connection,
    SendResult,
    TransportError,
)
from .discovery import (
    NodeDiscovery,
    Node,
    DiscoverySource,
)
from .security import (
    SecurityPolicy,
    CertificateBundle,
    NoiseSession,
)
from .load_balancer import ContinuumLoadBalancer, MultiStream

__all__ = [
    # Manager
    "ContinuumManager",
    "Route",
    "ConnectionState",
    # Transport
    "TransportBackend",
    "ProbeResult",
    "Connection",
    "SendResult",
    "TransportError",
    # Discovery
    "NodeDiscovery",
    "Node",
    "DiscoverySource",
    # Security
    "SecurityPolicy",
    "CertificateBundle",
    "NoiseSession",
    # Load Balancer
    "ContinuumLoadBalancer",
    "MultiStream",
]
