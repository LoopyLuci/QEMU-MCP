"""Docker container backend using docker-py.

Provides a full implementation of ContainerBackend for Docker daemon,
supporting container lifecycle, execution, logging, stats, images,
networks, and volumes.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from docker import DockerClient
from docker.errors import (
    APIError,
    ContainerError,
    DockerException,
    ImageNotFound,
    NotFound,
)
from docker.models.containers import Container as DockerContainer

from vm_harness.container.backend import (
    CommandResult,
    Container,
    ContainerBackend,
    ContainerConfig,
    ContainerImage,
    ContainerNetwork,
    ContainerStats,
    ContainerVolume,
)


class DockerError(Exception):
    """Base exception for Docker backend errors."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cause = cause


class NotFoundError(DockerError):
    """Raised when a resource is not found."""
    pass


class ConflictError(DockerError):
    """Raised when there is a naming conflict."""
    pass


class ContainerNotRunningError(DockerError):
    """Raised when an operation requires a running container."""
    pass


class AuthenticationError(DockerError):
    """Raised when registry authentication fails."""
    pass


class DockerBackend(ContainerBackend):
    """Docker daemon backend via docker-py.

    Connects to a Docker daemon through the standard socket or TCP,
    providing full container lifecycle management.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        version: Optional[str] = None,
        timeout: int = 60,
    ):
        """
        Args:
            base_url: Docker daemon URL (e.g., 'unix:///var/run/docker.sock'
                      or 'tcp://localhost:2375'). None for default.
            version: API version to use. None for auto-negotiate.
            timeout: Default API timeout in seconds.
        """
        self._base_url = base_url
        self._version = version
        self._timeout = timeout
        self._client: Optional[DockerClient] = None

    # ── Connection management ──────────────────────────────────────────────────

    async def connect(self) -> None:
        """Initialize connection to Docker daemon."""
        try:
            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(
                None,
                lambda: DockerClient(
                    base_url=self._base_url,
                    version=self._version,
                    timeout=self._timeout,
                ),
            )
            # Verify connection
            await loop.run_in_executor(None, self._client.ping)
        except DockerException as e:
            raise DockerError(f"Failed to connect to Docker: {e}", e)

    async def disconnect(self) -> None:
        """Close connection to Docker daemon."""
        if self._client:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._client.close)
            self._client = None

    async def is_connected(self) -> bool:
        """Check if connected to Docker daemon."""
        if not self._client:
            return False
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._client.ping)
            return True
        except Exception:
            return False

    def _ensure_connected(self) -> DockerClient:
        """Ensure client is connected, raise error if not."""
        if not self._client:
            raise DockerError("Not connected to Docker daemon. Call connect() first.")
        return self._client

    # ── Container lifecycle ────────────────────────────────────────────────────

    async def list_containers(self, all: bool = True) -> List[Container]:
        """List Docker containers."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _list():
            containers = client.containers.list(all=all)
            return [self._convert_container(c) for c in containers]

        try:
            return await loop.run_in_executor(None, _list)
        except DockerException as e:
            raise DockerError(f"Failed to list containers: {e}", e)

    async def get_container(self, container_id: str) -> Container:
        """Get a Docker container by ID or name."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _get():
            try:
                c = client.containers.get(container_id)
                return self._convert_container(c)
            except NotFound:
                raise NotFoundError(f"Container '{container_id}' not found")

        try:
            return await loop.run_in_executor(None, _get)
        except NotFoundError:
            raise
        except DockerException as e:
            raise DockerError(f"Failed to get container: {e}", e)

    async def create_container(self, config: ContainerConfig) -> Container:
        """Create a new Docker container."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _create():
            kwargs: Dict[str, Any] = {
                "image": config.image,
                "detach": config.detach,
                "auto_remove": config.remove_on_exit,
            }
            if config.name:
                kwargs["name"] = config.name
            if config.command:
                kwargs["command"] = config.command
            if config.environment:
                kwargs["environment"] = config.environment
            if config.ports:
                kwargs["ports"] = config.ports
            if config.volumes:
                kwargs["volumes"] = config.volumes
            if config.network:
                kwargs["network"] = config.network
            if config.labels:
                kwargs["labels"] = config.labels
            if config.cpu_limit:
                kwargs["nano_cpus"] = int(config.cpu_limit * 1e9)
            if config.memory_limit_mb:
                kwargs["mem_limit"] = f"{config.memory_limit_mb}m"
            if config.restart_policy:
                policy_map = {
                    "no": {"Name": "no"},
                    "always": {"Name": "always"},
                    "on-failure": {"Name": "on-failure", "MaximumRetryCount": 0},
                    "unless-stopped": {"Name": "unless-stopped"},
                }
                if config.restart_policy in policy_map:
                    kwargs["restart_policy"] = policy_map[config.restart_policy]

            try:
                c = client.containers.create(**kwargs)
                return self._convert_container(c)
            except ImageNotFound:
                from vm_harness.container.backend import ContainerImage
                raise DockerError(f"Image '{config.image}' not found")
            except APIError as e:
                if "Conflict" in str(e):
                    raise ConflictError(
                        f"Container name '{config.name}' already in use"
                    )
                raise DockerError(f"Failed to create container: {e}", e)

        try:
            return await loop.run_in_executor(None, _create)
        except (DockerError, ConflictError):
            raise
        except DockerException as e:
            raise DockerError(f"Failed to create container: {e}", e)

    async def start_container(self, container_id: str) -> None:
        """Start a Docker container."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _start():
            try:
                c = client.containers.get(container_id)
                c.start()
            except NotFound:
                raise NotFoundError(f"Container '{container_id}' not found")

        try:
            await loop.run_in_executor(None, _start)
        except NotFoundError:
            raise
        except DockerException as e:
            raise DockerError(f"Failed to start container: {e}", e)

    async def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """Stop a Docker container."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _stop():
            try:
                c = client.containers.get(container_id)
                c.stop(timeout=timeout)
            except NotFound:
                raise NotFoundError(f"Container '{container_id}' not found")

        try:
            await loop.run_in_executor(None, _stop)
        except NotFoundError:
            raise
        except DockerException as e:
            raise DockerError(f"Failed to stop container: {e}", e)

    async def restart_container(self, container_id: str, timeout: int = 10) -> None:
        """Restart a Docker container."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _restart():
            try:
                c = client.containers.get(container_id)
                c.restart(timeout=timeout)
            except NotFound:
                raise NotFoundError(f"Container '{container_id}' not found")

        try:
            await loop.run_in_executor(None, _restart)
        except NotFoundError:
            raise
        except DockerException as e:
            raise DockerError(f"Failed to restart container: {e}", e)

    async def remove_container(
        self,
        container_id: str,
        force: bool = False,
        volumes: bool = False,
    ) -> None:
        """Remove a Docker container."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _remove():
            try:
                c = client.containers.get(container_id)
                c.remove(force=force, v=volumes)
            except NotFound:
                raise NotFoundError(f"Container '{container_id}' not found")

        try:
            await loop.run_in_executor(None, _remove)
        except NotFoundError:
            raise
        except DockerException as e:
            raise DockerError(f"Failed to remove container: {e}", e)

    # ── Execution & Logging ────────────────────────────────────────────────────

    async def exec_command(
        self,
        container_id: str,
        command: Union[str, List[str]],
        tty: bool = False,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """Execute a command inside a Docker container."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _exec():
            try:
                c = client.containers.get(container_id)
                if c.status != "running":
                    raise ContainerNotRunningError(
                        f"Container '{container_id}' is not running (status: {c.status})"
                    )
                result = c.exec_run(
                    cmd=command,
                    tty=tty,
                    stream=False,
                    demux=False,
                )
                return CommandResult(
                    stdout=result.output.decode("utf-8", errors="replace") if isinstance(result.output, bytes) else "",
                    stderr="",
                    returncode=result.exit_code,
                )
            except NotFound:
                raise NotFoundError(f"Container '{container_id}' not found")
            except ContainerNotRunningError:
                raise
            except DockerException as e:
                raise DockerError(f"Failed to execute command: {e}", e)

        try:
            return await loop.run_in_executor(None, _exec)
        except (NotFoundError, ContainerNotRunningError):
            raise
        except DockerException as e:
            raise DockerError(f"Failed to execute command: {e}", e)

    async def get_logs(
        self,
        container_id: str,
        tail: int = 100,
        since: Optional[str] = None,
        timestamps: bool = False,
        follow: bool = False,
    ) -> Union[str, AsyncIterator[str]]:
        """Retrieve Docker container logs."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _get_logs():
            try:
                c = client.containers.get(container_id)
                if follow:
                    return self._stream_logs(c, tail, since, timestamps)
                else:
                    kwargs: Dict[str, Any] = {
                        "tail": tail,
                        "timestamps": timestamps,
                    }
                    if since:
                        kwargs["since"] = since
                    logs = c.logs(**kwargs)
                    return logs.decode("utf-8", errors="replace")
            except NotFound:
                raise NotFoundError(f"Container '{container_id}' not found")

        try:
            result = await loop.run_in_executor(None, _get_logs)
            return result
        except NotFoundError:
            raise
        except DockerException as e:
            raise DockerError(f"Failed to get logs: {e}", e)

    async def _stream_logs(
        self,
        container: DockerContainer,
        tail: int,
        since: Optional[str],
        timestamps: bool,
    ) -> AsyncIterator[str]:
        """Stream logs from a container."""
        loop = asyncio.get_event_loop()

        def _stream():
            kwargs: Dict[str, Any] = {
                "tail": tail,
                "timestamps": timestamps,
                "stream": True,
                "follow": True,
            }
            if since:
                kwargs["since"] = since
            return container.logs(**kwargs)

        log_stream = await loop.run_in_executor(None, _stream)
        for line in log_stream:
            yield line.decode("utf-8", errors="replace").rstrip("\n")

    # ── Statistics ─────────────────────────────────────────────────────────────

    async def get_stats(self, container_id: str) -> ContainerStats:
        """Get Docker container resource statistics."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _stats():
            try:
                c = client.containers.get(container_id)
                raw = c.stats(stream=False)
                return self._parse_stats(raw)
            except NotFound:
                raise NotFoundError(f"Container '{container_id}' not found")

        try:
            return await loop.run_in_executor(None, _stats)
        except NotFoundError:
            raise
        except DockerException as e:
            raise DockerError(f"Failed to get stats: {e}", e)

    def _parse_stats(self, raw: Dict[str, Any]) -> ContainerStats:
        """Parse Docker stats response into ContainerStats."""
        # CPU calculation
        cpu_delta = (
            raw["cpu_stats"]["cpu_usage"]["total_usage"]
            - raw["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            raw["cpu_stats"]["system_cpu_usage"]
            - raw["precpu_stats"]["system_cpu_usage"]
        )
        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta > 0:
            num_cpus = raw["cpu_stats"].get("online_cpus", 1)
            cpu_percent = (cpu_delta / system_delta) * num_cpus * 100

        # Memory
        mem_usage = raw.get("memory_stats", {}).get("usage", 0)
        mem_limit = raw.get("memory_stats", {}).get("limit", 1)

        # Network
        net_rx, net_tx = 0, 0
        networks = raw.get("networks", {})
        if networks:
            for net in networks.values():
                net_rx += net.get("rx_bytes", 0)
                net_tx += net.get("tx_bytes", 0)

        # Block I/O
        blk_read, blk_write = 0, 0
        for io in raw.get("blkio_stats", {}).get("io_service_bytes_recursive", []) or []:
            if io.get("op") == "Read":
                blk_read += io.get("value", 0)
            elif io.get("op") == "Write":
                blk_write += io.get("value", 0)

        # PIDs
        pids = raw.get("pids_stats", {}).get("current", 0)

        return ContainerStats(
            cpu_percent=round(cpu_percent, 2),
            memory_used_mb=mem_usage / (1024 * 1024),
            memory_limit_mb=mem_limit / (1024 * 1024),
            network_rx_bytes=net_rx,
            network_tx_bytes=net_tx,
            block_read_bytes=blk_read,
            block_write_bytes=blk_write,
            pids=pids,
        )

    # ── Image management ──────────────────────────────────────────────────────

    async def list_images(self) -> List[ContainerImage]:
        """List Docker images."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _list():
            images = client.images.list()
            return [
                ContainerImage(
                    id=img.id,
                    tags=img.tags or [],
                    size_mb=img.attrs.get("Size", 0) / (1024 * 1024),
                    created=img.attrs.get("Created"),
                )
                for img in images
            ]

        try:
            return await loop.run_in_executor(None, _list)
        except DockerException as e:
            raise DockerError(f"Failed to list images: {e}", e)

    async def pull_image(self, image: str, tag: str = "latest") -> str:
        """Pull a Docker image from registry."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _pull():
            try:
                return client.images.pull(image, tag=tag)
            except ImageNotFound:
                raise DockerError(f"Image '{image}:{tag}' not found in registry")
            except APIError as e:
                if "unauthorized" in str(e).lower():
                    raise AuthenticationError(
                        f"Authentication failed for registry: {e}"
                    )
                raise DockerError(f"Failed to pull image: {e}", e)

        try:
            return await loop.run_in_executor(None, _pull)
        except (DockerError, AuthenticationError):
            raise
        except DockerException as e:
            raise DockerError(f"Failed to pull image: {e}", e)

    async def remove_image(self, image_id: str, force: bool = False) -> None:
        """Remove a Docker image."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _remove():
            try:
                client.images.remove(image_id, force=force)
            except NotFound:
                raise NotFoundError(f"Image '{image_id}' not found")
            except ImageNotFound:
                raise NotFoundError(f"Image '{image_id}' not found")

        try:
            await loop.run_in_executor(None, _remove)
        except NotFoundError:
            raise
        except DockerException as e:
            raise DockerError(f"Failed to remove image: {e}", e)

    # ── Network management ────────────────────────────────────────────────────

    async def list_networks(self) -> List[ContainerNetwork]:
        """List Docker networks."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _list():
            networks = client.networks.list()
            return [
                ContainerNetwork(
                    id=net.id,
                    name=net.name,
                    driver=net.attrs.get("Driver", "bridge"),
                    scope=net.attrs.get("Scope", "local"),
                    internal=net.attrs.get("Internal", False),
                )
                for net in networks
            ]

        try:
            return await loop.run_in_executor(None, _list)
        except DockerException as e:
            raise DockerError(f"Failed to list networks: {e}", e)

    async def create_network(
        self,
        name: str,
        driver: str = "bridge",
        internal: bool = False,
    ) -> ContainerNetwork:
        """Create a Docker network."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _create():
            try:
                net = client.networks.create(
                    name=name,
                    driver=driver,
                    internal=internal,
                )
                return ContainerNetwork(
                    id=net.id,
                    name=net.name,
                    driver=driver,
                    scope="local",
                    internal=internal,
                )
            except APIError as e:
                if "already exists" in str(e):
                    raise ConflictError(f"Network '{name}' already exists")
                raise DockerError(f"Failed to create network: {e}", e)

        try:
            return await loop.run_in_executor(None, _create)
        except (DockerError, ConflictError):
            raise
        except DockerException as e:
            raise DockerError(f"Failed to create network: {e}", e)

    # ── Volume management ──────────────────────────────────────────────────────

    async def list_volumes(self) -> List[ContainerVolume]:
        """List Docker volumes."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _list():
            volumes = client.volumes.list()
            return [
                ContainerVolume(
                    name=vol.name,
                    driver=vol.attrs.get("Driver", "local"),
                    mountpoint=vol.attrs.get("Mountpoint", ""),
                    labels=vol.attrs.get("Labels") or {},
                )
                for vol in volumes
            ]

        try:
            return await loop.run_in_executor(None, _list)
        except DockerException as e:
            raise DockerError(f"Failed to list volumes: {e}", e)

    async def create_volume(
        self,
        name: str,
        driver: str = "local",
        labels: Optional[Dict[str, str]] = None,
    ) -> ContainerVolume:
        """Create a Docker volume."""
        client = self._ensure_connected()
        loop = asyncio.get_event_loop()

        def _create():
            try:
                vol = client.volumes.create(
                    name=name,
                    driver=driver,
                    labels=labels,
                )
                return ContainerVolume(
                    name=vol.name,
                    driver=driver,
                    mountpoint=vol.attrs.get("Mountpoint", ""),
                    labels=labels or {},
                )
            except APIError as e:
                if "already exists" in str(e):
                    raise ConflictError(f"Volume '{name}' already exists")
                raise DockerError(f"Failed to create volume: {e}", e)

        try:
            return await loop.run_in_executor(None, _create)
        except (DockerError, ConflictError):
            raise
        except DockerException as e:
            raise DockerError(f"Failed to create volume: {e}", e)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _convert_container(self, c: DockerContainer) -> Container:
        """Convert a docker-py Container to our Container model."""
        return Container(
            id=c.id,
            name=c.name,
            status=c.status,
            image=c.image.tags[0] if c.image.tags else "unknown",
            ports=getattr(c, "ports", {}) or {},
            created=c.attrs.get("Created"),
            labels=c.attrs.get("Config", {}).get("Labels") or {},
            command=c.attrs.get("Config", {}).get("Cmd"),
        )
