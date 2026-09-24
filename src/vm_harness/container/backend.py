"""Abstract container backend interface.

Defines the contract that all container orchestration backends must implement,
providing a unified API for Docker, Kubernetes, Podman, and other runtimes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, Union


# ── Data types ────────────────────────────────────────────────────────────────

class Container:
    """Represents a running or stopped container."""

    def __init__(
        self,
        id: str,
        name: str,
        status: str,
        image: str,
        ports: Optional[Dict[str, Any]] = None,
        created: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        command: Optional[str] = None,
    ):
        self.id = id
        self.name = name
        self.status = status
        self.image = image
        self.ports = ports or {}
        self.created = created
        self.labels = labels or {}
        self.command = command

    def __repr__(self) -> str:
        return f"Container(id={self.id!r}, name={self.name!r}, status={self.status!r})"


class ContainerConfig:
    """Configuration for creating a new container."""

    def __init__(
        self,
        image: str,
        name: Optional[str] = None,
        command: Optional[Union[str, List[str]]] = None,
        environment: Optional[Dict[str, str]] = None,
        ports: Optional[Dict[str, Any]] = None,
        volumes: Optional[Dict[str, Any]] = None,
        network: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        detach: bool = True,
        remove_on_exit: bool = False,
        cpu_limit: Optional[float] = None,
        memory_limit_mb: Optional[int] = None,
        restart_policy: Optional[str] = None,
    ):
        self.image = image
        self.name = name
        self.command = command
        self.environment = environment or {}
        self.ports = ports or {}
        self.volumes = volumes or {}
        self.network = network
        self.labels = labels or {}
        self.detach = detach
        self.remove_on_exit = remove_on_exit
        self.cpu_limit = cpu_limit
        self.memory_limit_mb = memory_limit_mb
        self.restart_policy = restart_policy


class ContainerStats:
    """Real-time resource usage statistics for a container."""

    def __init__(
        self,
        cpu_percent: float = 0.0,
        memory_used_mb: float = 0.0,
        memory_limit_mb: float = 0.0,
        network_rx_bytes: int = 0,
        network_tx_bytes: int = 0,
        block_read_bytes: int = 0,
        block_write_bytes: int = 0,
        pids: int = 0,
    ):
        self.cpu_percent = cpu_percent
        self.memory_used_mb = memory_used_mb
        self.memory_limit_mb = memory_limit_mb
        self.network_rx_bytes = network_rx_bytes
        self.network_tx_bytes = network_tx_bytes
        self.block_read_bytes = block_read_bytes
        self.block_write_bytes = block_write_bytes
        self.pids = pids

    @property
    def memory_percent(self) -> float:
        if self.memory_limit_mb > 0:
            return (self.memory_used_mb / self.memory_limit_mb) * 100
        return 0.0

    def __repr__(self) -> str:
        return (
            f"ContainerStats(cpu={self.cpu_percent:.1f}%, "
            f"mem={self.memory_used_mb:.0f}/{self.memory_limit_mb:.0f}MB)"
        )


class CommandResult:
    """Result of executing a command inside a container."""

    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    @property
    def success(self) -> bool:
        return self.returncode == 0

    def __repr__(self) -> str:
        return f"CommandResult(rc={self.returncode}, stdout={len(self.stdout)}B)"


class ContainerImage:
    """Represents a container image."""

    def __init__(
        self,
        id: str,
        tags: Optional[List[str]] = None,
        size_mb: float = 0.0,
        created: Optional[str] = None,
    ):
        self.id = id
        self.tags = tags or []
        self.size_mb = size_mb
        self.created = created

    def __repr__(self) -> str:
        return f"Image(id={self.id!r}, tags={self.tags})"


class ContainerNetwork:
    """Represents a container network."""

    def __init__(
        self,
        id: str,
        name: str,
        driver: str = "bridge",
        scope: str = "local",
        internal: bool = False,
    ):
        self.id = id
        self.name = name
        self.driver = driver
        self.scope = scope
        self.internal = internal

    def __repr__(self) -> str:
        return f"Network(id={self.id!r}, name={self.name!r})"


class ContainerVolume:
    """Represents a container volume."""

    def __init__(
        self,
        name: str,
        driver: str = "local",
        mountpoint: str = "",
        labels: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.driver = driver
        self.mountpoint = mountpoint
        self.labels = labels or {}

    def __repr__(self) -> str:
        return f"Volume(name={self.name!r})"


# ── Backend ABC ───────────────────────────────────────────────────────────────

class ContainerBackend(ABC):
    """Abstract base for container runtime backends.

    Implementations must provide lifecycle management, execution, logging,
    and statistics for containers. All methods are async to support
    non-blocking I/O operations.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to the container runtime."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the container runtime."""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if the backend is connected to the runtime."""
        ...

    # ── Container lifecycle ────────────────────────────────────────────────────

    @abstractmethod
    async def list_containers(self, all: bool = True) -> List[Container]:
        """List containers.

        Args:
            all: If True, include stopped containers.
        
        Returns:
            List of Container objects.
        """
        ...

    @abstractmethod
    async def get_container(self, container_id: str) -> Container:
        """Get a specific container by ID or name.

        Args:
            container_id: Container ID or name.
        
        Returns:
            Container details.
        
        Raises:
            NotFoundError: If container does not exist.
        """
        ...

    @abstractmethod
    async def create_container(self, config: ContainerConfig) -> Container:
        """Create a new container from a configuration.

        Args:
            config: Container creation parameters.
        
        Returns:
            The newly created Container.
        
        Raises:
            ImageNotFoundError: If the image is not available.
            ConflictError: If a container with the name already exists.
        """
        ...

    @abstractmethod
    async def start_container(self, container_id: str) -> None:
        """Start a stopped container.

        Args:
            container_id: Container ID or name.
        
        Raises:
            NotFoundError: If container does not exist.
        """
        ...

    @abstractmethod
    async def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """Stop a running container gracefully.

        Args:
            container_id: Container ID or name.
            timeout: Seconds to wait before killing.
        
        Raises:
            NotFoundError: If container does not exist.
        """
        ...

    @abstractmethod
    async def restart_container(self, container_id: str, timeout: int = 10) -> None:
        """Restart a container.

        Args:
            container_id: Container ID or name.
            timeout: Seconds to wait before killing.
        
        Raises:
            NotFoundError: If container does not exist.
        """
        ...

    @abstractmethod
    async def remove_container(
        self,
        container_id: str,
        force: bool = False,
        volumes: bool = False,
    ) -> None:
        """Remove a container.

        Args:
            container_id: Container ID or name.
            force: Kill container if running.
            volumes: Remove associated volumes.
        
        Raises:
            NotFoundError: If container does not exist.
        """
        ...

    # ── Execution & Logging ────────────────────────────────────────────────────

    @abstractmethod
    async def exec_command(
        self,
        container_id: str,
        command: Union[str, List[str]],
        tty: bool = False,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """Execute a command inside a running container.

        Args:
            container_id: Container ID or name.
            command: Command string or argv list.
            tty: Allocate a pseudo-TTY.
            timeout: Execution timeout in seconds.
        
        Returns:
            CommandResult with stdout, stderr, and return code.
        
        Raises:
            NotFoundError: If container does not exist.
            ContainerNotRunningError: If container is not running.
        """
        ...

    @abstractmethod
    async def get_logs(
        self,
        container_id: str,
        tail: int = 100,
        since: Optional[str] = None,
        timestamps: bool = False,
        follow: bool = False,
    ) -> Union[str, AsyncIterator[str]]:
        """Retrieve container logs.

        Args:
            container_id: Container ID or name.
            tail: Number of lines from the end.
            since: Show logs since timestamp.
            timestamps: Include timestamps in output.
            follow: Stream logs (returns AsyncIterator).
        
        Returns:
            Log string, or AsyncIterator if follow=True.
        
        Raises:
            NotFoundError: If container does not exist.
        """
        ...

    # ── Statistics ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def get_stats(self, container_id: str) -> ContainerStats:
        """Get real-time resource usage statistics.

        Args:
            container_id: Container ID or name.
        
        Returns:
            ContainerStats with CPU, memory, network, and I/O metrics.
        
        Raises:
            NotFoundError: If container does not exist.
        """
        ...

    # ── Image management ──────────────────────────────────────────────────────

    @abstractmethod
    async def list_images(self) -> List[ContainerImage]:
        """List available container images."""
        ...

    @abstractmethod
    async def pull_image(self, image: str, tag: str = "latest") -> None:
        """Pull an image from a registry.

        Args:
            image: Image name.
            tag: Image tag.
        
        Raises:
            ImageNotFoundError: If image not found in registry.
            AuthenticationError: If registry auth fails.
        """
        ...

    @abstractmethod
    async def remove_image(self, image_id: str, force: bool = False) -> None:
        """Remove a container image.

        Args:
            image_id: Image ID or name.
            force: Force removal even if in use.
        
        Raises:
            NotFoundError: If image does not exist.
        """
        ...

    # ── Network management ────────────────────────────────────────────────────

    @abstractmethod
    async def list_networks(self) -> List[ContainerNetwork]:
        """List container networks."""
        ...

    @abstractmethod
    async def create_network(
        self,
        name: str,
        driver: str = "bridge",
        internal: bool = False,
    ) -> ContainerNetwork:
        """Create a new container network.

        Args:
            name: Network name.
            driver: Network driver (bridge, overlay, host, none).
            internal: Restrict external access.
        
        Returns:
            The created ContainerNetwork.
        """
        ...

    # ── Volume management ──────────────────────────────────────────────────────

    @abstractmethod
    async def list_volumes(self) -> List[ContainerVolume]:
        """List container volumes."""
        ...

    @abstractmethod
    async def create_volume(
        self,
        name: str,
        driver: str = "local",
        labels: Optional[Dict[str, str]] = None,
    ) -> ContainerVolume:
        """Create a new container volume.

        Args:
            name: Volume name.
            driver: Volume driver.
            labels: Volume labels.
        
        Returns:
            The created ContainerVolume.
        """
        ...
