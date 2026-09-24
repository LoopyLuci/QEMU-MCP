"""Node discovery via mDNS, Tailscale, and manual configuration.

Provides :class:`Node` (a lightweight descriptor for a reachable peer)
and :class:`NodeDiscovery` which aggregates multiple discovery sources
and yields a deduplicated, ranked list of candidate nodes.
"""

from __future__ import annotations

import abc
import asyncio
import enum
import ipaddress
import json
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node descriptor
# ---------------------------------------------------------------------------


class DiscoverySource(enum.Enum):
    """How a node was discovered."""

    MANUAL = "manual"
    MDNS = "mdns"
    TAILSCALE = "tailscale"
    STATIC = "static"
    QR_PAIR = "qr_pair"
    FEDERATION = "federation"


@dataclass
class Node:
    """A reachable peer in the continuum mesh.

    Only ``node_id`` and ``continuum_port`` are required.  Other fields
    are populated by discovery and used by transport backends to select
    the optimal path.
    """

    node_id: str
    continuum_port: int = 4_433
    hostname: Optional[str] = None
    tailscale_ip: Optional[str] = None
    lan_ips: List[str] = field(default_factory=list)
    wan_host: Optional[str] = None
    wan_port: Optional[int] = None
    capabilities: Set[str] = field(default_factory=set)
    tags: Dict[str, str] = field(default_factory=dict)
    source: DiscoverySource = DiscoverySource.MANUAL
    last_seen: float = 0.0
    rtt_ms: Optional[float] = None

    @property
    def tailscale_address(self) -> Optional[str]:
        if self.tailscale_ip:
            return f"{self.tailscale_ip}:{self.continuum_port}"
        return None

    @property
    def primary_address(self) -> Optional[str]:
        """Best-guess primary address for connection attempts."""
        if self.tailscale_ip:
            return self.tailscale_address
        if self.lan_ips:
            return f"{self.lan_ips[0]}:{self.continuum_port}"
        if self.wan_host and self.wan_port:
            return f"{self.wan_host}:{self.wan_port}"
        return None

    @property
    def age_seconds(self) -> float:
        if not self.last_seen:
            return float("inf")
        return time.time() - self.last_seen

    def is_stale(self, max_age: float = 300.0) -> bool:
        return self.age_seconds > max_age

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "continuum_port": self.continuum_port,
            "hostname": self.hostname,
            "tailscale_ip": self.tailscale_ip,
            "lan_ips": list(self.lan_ips),
            "wan_host": self.wan_host,
            "wan_port": self.wan_port,
            "capabilities": list(self.capabilities),
            "tags": self.tags,
            "source": self.source.value,
            "last_seen": self.last_seen,
            "rtt_ms": self.rtt_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        return cls(
            node_id=data["node_id"],
            continuum_port=data.get("continuum_port", 4_433),
            hostname=data.get("hostname"),
            tailscale_ip=data.get("tailscale_ip"),
            lan_ips=data.get("lan_ips", []),
            wan_host=data.get("wan_host"),
            wan_port=data.get("wan_port"),
            capabilities=set(data.get("capabilities", [])),
            tags=data.get("tags", {}),
            source=DiscoverySource(data.get("source", "manual")),
            last_seen=data.get("last_seen", 0.0),
            rtt_ms=data.get("rtt_ms"),
        )

    def __hash__(self) -> int:
        return hash(self.node_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return NotImplemented
        return self.node_id == other.node_id


# ---------------------------------------------------------------------------
# Discovery backends
# ---------------------------------------------------------------------------


class DiscoveryBackend(abc.ABC):
    """Abstract base for node discovery sources."""

    name: str = "abstract"

    @abc.abstractmethod
    async def discover(self) -> List[Node]:
        """Return a list of nodes found by this source."""


class ManualDiscovery(DiscoveryBackend):
    """Serve nodes from a static list (CLI flag / config file)."""

    name = "manual"

    def __init__(self, nodes: Optional[List[Node]] = None) -> None:
        self._nodes: List[Node] = nodes or []

    def add(self, node: Node) -> None:
        self._nodes = [n for n in self._nodes if n.node_id != node.node_id]
        self._nodes.append(node)

    async def discover(self) -> List[Node]:
        return list(self._nodes)


class TailscaleDiscovery(DiscoveryBackend):
    """Discover peers via Tailscale status."""

    name = "tailscale"

    def __init__(self, status_path: Optional[Path] = None) -> None:
        self._status_path = status_path
        self._api: Optional[Any] = None  # tailscale.LocalClient placeholder

    async def discover(self) -> List[Node]:
        """Query Tailscale status and convert peers into ``Node`` objects."""
        try:
            import tailscale
            client = tailscale.LocalClient()
            status = client.status()
        except Exception as exc:
            logger.debug("tailscale discovery unavailable: %s", exc)
            return []

        nodes: List[Node] = []
        self_id = status.get("Self", {}).get("ID")
        for peer_id, peer in status.get("Peer", {}).items():
            if peer_id == self_id:
                continue
            dns_name = peer.get("DNSName", "")
            tailscale_ips = peer.get("TailscaleIPs", [])
            if not tailscale_ips:
                continue
            hostname = dns_name.split(".")[0] if dns_name else None
            nodes.append(
                Node(
                    node_id=peer_id,
                    hostname=hostname,
                    tailscale_ip=tailscale_ips[0],
                    tailscale_ips=tailscale_ips,
                    last_seen=time.time(),
                    source=DiscoverySource.TAILSCALE,
                    capabilities={"tailscale", "wireguard"},
                )
            )
        return nodes


class MDNSDiscovery(DiscoveryBackend):
    """LAN mDNS discovery for continuum services.

    Uses Zeroconf/Bonjour to find ``_continuum._tcp`` services on the
    local network.  Pure-Python implementation so we avoid optional deps.
    """

    name = "mdns"
    SERVICE_TYPE = "_continuum._tcp.local."
    MULTICAST_GROUP = "224.0.0.251"
    MULTICAST_PORT = 5_353

    def __init__(self, timeout: float = 2.0, interface: Optional[str] = None) -> None:
        self._timeout = timeout
        self._interface = interface

    async def discover(self) -> List[Node]:
        """Send an mDNS query and collect responses.

        Sends a standard DNS-SD query to the multicast group and
        parses any PTR/SRV responses that arrive within ``timeout``.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(self._timeout)
        sock.bind(("", 0))

        # Build a minimal DNS query for _continuum._tcp.local.
        query = self._build_mdns_query()
        try:
            sock.sendto(query, (self.MULTICAST_GROUP, self.MULTICAST_PORT))
        except OSError as exc:
            logger.debug("mDNS send failed: %s", exc)
            return []

        nodes: Dict[str, Node] = {}
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(4_096)
            except socket.timeout:
                break
            except OSError:
                break
            parsed = self._parse_mdns_response(data, addr)
            if parsed and parsed.node_id not in nodes:
                nodes[parsed.node_id] = parsed
        return list(nodes.values())

    @staticmethod
    def _build_mdns_query() -> bytes:
        """Construct a minimal DNS query packet."""
        # Header: ID=0, flags=0x0000 (standard query), QDCOUNT=1
        header = struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0)
        # Query: _continuum._tcp.local. IN PTR
        labels = b"\x0b_continuum\x04_tcp\x05local\x00"
        qtype_ptr = struct.pack(">HH", 12, 1) # PTR, IN
        return header + labels + qtype_ptr

    @classmethod
    def _parse_mdns_response(cls, data: bytes, addr: tuple) -> Optional[Node]:
        """Parse an mDNS response into a ``Node`` (best-effort)."""
        # In a real implementation this would fully parse the DNS
        # response to extract SRV records, TXT records, etc.
        # For now we return a placeholder if the packet is large enough
        # to plausibly contain a response.
        if len(data) < 12:
            return None
        ip = addr[0]
        # Use IP-based node_id since we can't fully parse the response
        node_id = f"mdns-{ip.replace('.', '-')}"
        return Node(
            node_id=node_id,
            lan_ips=[ip],
            last_seen=time.time(),
            source=DiscoverySource.MDNS,
        )


class FederationDiscovery(DiscoveryBackend):
    """Discover nodes advertised by a federation control plane."""

    name = "federation"

    def __init__(self, control_plane_url: str, api_key: str = "") -> None:
        self._url = control_plane_url.rstrip("/")
        self._api_key = api_key
        self._client: Optional[Any] = None

    async def discover(self) -> List[Node]:
        try:
            from aiohttp import ClientSession, ClientTimeout
        except ImportError:
            logger.warning("aiohttp required for federation discovery")
            return []

        timeout = ClientTimeout(total=10)
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self._url}/api/v1/nodes", headers=headers
                ) as resp:
                    if resp.status == 200:
                        payload = await resp.json()
                        return [
                            Node.from_dict(item) for item in payload.get("nodes", [])
                        ]
        except Exception as exc:
            logger.debug("federation discovery failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Node discovery aggregator
# ---------------------------------------------------------------------------


class NodeDiscovery:
    """Aggregate multiple discovery sources into a unified view.

    Sources are queried concurrently and the results merged so that
    each ``node_id`` appears only once — the freshest :class:`Node`
    wins.
    """

    def __init__(
        self,
        sources: Optional[List[DiscoveryBackend]] = None,
        static_file: Optional[Path] = None,
    ) -> None:
        self._sources: List[DiscoveryBackend] = sources or []
        self._static_file = static_file
        self._cache: Dict[str, Node] = {}
        self._cache_time: float = 0.0
        self._cache_ttl: float = 10.0

    def add_source(self, source: DiscoveryBackend) -> None:
        self._sources.append(source)

    # -- Public API ---------------------------------------------------------

    async def discover_all(self, force: bool = False) -> List[Node]:
        """Discover nodes from all sources, merged and deduplicated."""
        if not force and (time.monotonic() - self._cache_time) < self._cache_ttl:
            return list(self._cache.values())

        results = await asyncio.gather(
            *[src.discover() for src in self._sources],
            return_exceptions=True,
        )
        merged: Dict[str, Node] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.debug("discovery source error: %s", result)
                continue
            for node in result:
                existing = merged.get(node.node_id)
                if existing is None or node.last_seen > existing.last_seen:
                    merged[node.node_id] = node

        # Merge static nodes from file
        if self._static_file and self._static_file.exists():
            static_nodes = self._load_static_nodes()
            for node in static_nodes:
                merged.setdefault(node.node_id, node)

        self._cache = merged
        self._cache_time = time.monotonic()
        return list(merged.values())

    async def find(self, node_id: str) -> Optional[Node]:
        """Look up a single node by ID (cached)."""
        if node_id in self._cache:
            return self._cache[node_id]
        await self.discover_all()
        return self._cache.get(node_id)

    async def stream_updates(self) -> AsyncIterator[List[Node]]:
        """Yield refreshed node lists at ``cache_ttl`` intervals."""
        while True:
            yield await self.discover_all(force=True)
            await asyncio.sleep(self._cache_ttl)

    # -- Persistence --------------------------------------------------------

    def _load_static_nodes(self) -> List[Node]:
        try:
            raw = json.loads(self._static_file.read_text())
            return [Node.from_dict(item) for item in raw.get("nodes", [])]
        except Exception as exc:
            logger.warning("failed to load static nodes: %s", exc)
            return []

    def save_static(self, path: Path) -> None:
        """Persist the current cache to a JSON file."""
        payload = {"nodes": [n.to_dict() for n in self._cache.values()]}
        path.write_text(json.dumps(payload, indent=2))

    # -- Mutation -----------------------------------------------------------

    def add_manual(self, node: Node) -> None:
        """Register a manually-configured node."""
        node.source = DiscoverySource.MANUAL
        self._cache[node.node_id] = node
