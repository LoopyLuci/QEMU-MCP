"""HypervisorBackend ABC — abstract base class for all hypervisor backends.

Defines the full VM lifecycle interface: create, destroy, start, stop, pause,
resume, reset, reboot, snapshot, restore, migrate, display, guest interaction,
monitoring, and management.  Concrete backends implement these methods using
the appropriate mechanism (QMP, vmrun, VBoxManage, WSL, PowerShell, libvirt).

Design principles:
- All methods are async where I/O-bound.
- Errors are raised as typed exceptions (see ``HypervisorError`` hierarchy).
- Return values are plain dicts / dataclasses (no backend-specific objects).
- Backends are stateless with respect to VM identity — the caller tracks VM
  names/UUIDs and passes them to each method.
- Connection/reconnection is handled internally by the backend.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


# ── Exceptions ─────────────────────────────────────────────────────────────────

class HypervisorError(Exception):
    """Base exception for all hypervisor backend errors."""
    pass


class VMNotFoundError(HypervisorError):
    """A referenced VM does not exist."""
    pass


class VMAlreadyRunningError(HypervisorError):
    """Attempted to start a VM that is already running."""
    pass


class VMNotRunningError(HypervisorError):
    """An operation requires a running VM, but the VM is stopped."""
    pass


class BackendNotAvailableError(HypervisorError):
    """The backend binary/daemon is not installed or not reachable."""
    pass


class OperationNotSupportedError(HypervisorError):
    """The backend does not support the requested operation."""
    pass


class VMMigrationError(HypervisorError):
    """Live/cold migration failed."""
    pass


# ── Enums ──────────────────────────────────────────────────────────────────────

class VMState(str, Enum):
    """High-level VM state (backend-independent)."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    ERROR = "error"
    STARTING = "starting"
    STOPPING = "stopping"
    SAVING = "saving"
    RESTORING = "restoring"
    UNKNOWN = "unknown"


class DisplayType(str, Enum):
    """Display protocol type."""
    SPICE = "spice"
    VNC = "vnc"
    SDL = "sdl"
    GTK = "gtk"
    HEADLESS = "headless"
    RDP = "rdp"
    CONSOLE = "console"


# Alias used by backend implementations
VMDisplayType = DisplayType


class NetworkMode(str, Enum):
    """Network attachment mode."""
    NAT = "nat"
    BRIDGED = "bridged"
    HOST_ONLY = "host_only"
    INTERNAL = "internal"
    NONE = "none"


# Alias used by backend implementations
VMNetworkMode = NetworkMode


class SnapshotMode(str, Enum):
    """Snapshot storage mode."""
    INTERNAL = "internal"       # Stored in the disk image
    EXTERNAL = "external"       # Separate file


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class VMConfig:
    """Configuration for creating a new VM.

    Backends read what they understand and silently ignore the rest.
    """
    name: str
    ram_mb: int = 2048
    cpus: int = 2
    cores_per_socket: int = 0
    threads_per_core: int = 1
    description: str = ""
    tags: list[str] = field(default_factory=list)
    # Storage
    disk_path: str = ""
    disk_size_gb: int = 0
    disk_format: str = "qcow2"  # qcow2, vmdk, vhdx, vdi, raw
    iso_path: str = ""
    additional_disks: list[dict[str, Any]] = field(default_factory=list)
    # Network
    network_mode: NetworkMode = NetworkMode.NAT
    network_bridge: str = ""
    mac_address: str = ""
    port_forwards: list[dict[str, Any]] = field(default_factory=list)
    # Display
    display_type: DisplayType = DisplayType.SPICE
    display_port: int = 0
    display_bind: str = "127.0.0.1"
    display_password: str = ""
    # Boot
    boot_order: list[str] = field(default_factory=lambda: ["hd", "cdrom", "network"])
    boot_firmware: str = "bios"  # bios, uefi, uefi-secure
    # Management
    management_port: int = 0
    management_type: str = "qmp"  # qmp, vmware-rdp, hyperv-ps, wsl
    management_password: str = ""
    # Advanced
    enable_kvm: bool = False
    enable_nested_virt: bool = False
    cpu_model: str = ""
    machine_type: str = ""
    extra_args: list[str] = field(default_factory=list)
    # Metadata
    custom_data: dict[str, str] = field(default_factory=dict)


@dataclass
class VMStatus:
    """Snapshot of a VM's current state."""
    name: str
    state: VMState = VMState.UNKNOWN
    pid: int = 0
    uptime_seconds: int = 0
    started_at: str = ""
    host_ip: str = ""
    management_uri: str = ""
    last_error: str = ""
    cpu_usage_pct: float = 0.0
    ram_usage_mb: int = 0
    ram_allocated_mb: int = 0
    cpus_allocated: int = 0
    disk_usage_gb: float = 0.0
    disk_allocated_gb: float = 0.0
    ip_address: str = ""
    network_interfaces: list[dict[str, Any]] = field(default_factory=list)
    snapshots: list[str] = field(default_factory=list)
    display_connected: bool = False
    display_uri: str = ""
    backend_name: str = ""


@dataclass
class VMMetrics:
    """Real-time VM metrics."""
    timestamp: str = ""
    cpu_usage_pct: float = 0.0
    cpu_system_pct: float = 0.0
    cpu_user_pct: float = 0.0
    ram_usage_mb: int = 0
    ram_available_mb: int = 0
    ram_balloon_mb: int = 0
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    disk_read_iops: float = 0.0
    disk_write_iops: float = 0.0
    net_rx_bytes: int = 0
    net_tx_bytes: int = 0
    net_rx_packets: int = 0
    net_tx_packets: int = 0
    net_rx_errors: int = 0
    net_tx_errors: int = 0
    gpu_usage_pct: float = 0.0


@dataclass
class VMDisplay:
    """Display connection details."""
    display_type: DisplayType = DisplayType.SPICE
    host: str = ""
    port: int = 0
    password: str = ""
    uri: str = ""
    websocket_port: int = 0
    ca_cert: str = ""
    ticket: str = ""


@dataclass
class VMNetwork:
    """Network interface configuration."""
    name: str = ""
    mode: NetworkMode = NetworkMode.NAT
    bridge: str = ""
    mac_address: str = ""
    ip_address: str = ""
    netmask: str = ""
    connected: bool = True
    adapter_type: str = "virtio"


@dataclass
class VMSnapshot:
    """Snapshot metadata."""
    name: str = ""
    description: str = ""
    created_at: str = ""
    is_current: bool = False
    parent: str = ""
    children: list[str] = field(default_factory=list)
    size_bytes: int = 0
    state_at_snapshot: VMState = VMState.UNKNOWN


@dataclass
class VMConsole:
    """Console/terminal access details."""
    protocol: str = ""   # spice-agent, vnc, serial, ssh
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    uri: str = ""
    command: str = ""


@dataclass
class VMGuestInfo:
    """Information gathered from inside the guest OS (via guest agent)."""
    hostname: str = ""
    os_name: str = ""
    os_version: str = ""
    timezone: str = ""
    ip_addresses: list[dict[str, str]] = field(default_factory=list)
    uptime_seconds: int = 0
    logged_in_users: list[str] = field(default_factory=list)
    filesystem_info: list[dict[str, Any]] = field(default_factory=list)
    load_average: tuple[float, float, float] = (0.0, 0.0, 0.0)


# ── ABC ────────────────────────────────────────────────────────────────────────

class HypervisorBackend(ABC):
    """Abstract base class for hypervisor backends.

    A backend is a stateless service object that provides VM lifecycle
    operations.  It holds internal connection state (process handles,
    client sessions) but never tracks VM identity — the caller is
    responsible for maintaining the canonical list of VMs.

    Lifecycle of a backend instance:
    1. ``__init__(config)`` — set up paths, validate binary presence.
    2. ``async initialize()`` — connect to daemon, load existing VMs.
    3. Use the API (start, stop, create, snapshot, etc.).
    4. ``async shutdown()`` — clean up connections.

    The ``is_available`` property must return True only when the backend's
    prerequisites are met (binary installed, daemon running, permissions OK).
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the backend.

        Args:
            config: Backend-specific configuration dict. Keys vary by backend.
                Common keys:
                - name: Logical name for this backend instance.
                - log_level: Python logging level string.
                - extra_args: Additional command-line args for subprocess calls.
        """
        self._config = config or {}
        self._initialized = False
        self._name = self._config.get("name", self.default_name)

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def default_name(self) -> str:
        """Human-readable backend identifier (e.g. ``"qemu"``, ``"vmware"``)."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Long-form name for UI display (e.g. ``"QEMU/KVM"``)."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Version string of the backend runtime."""
        ...

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend can be used on the current host.

        Should be fast (no subprocess calls).  Call ``probe_availability()``
        for a thorough check.
        """
        ...

    @property
    def supported_features(self) -> set[str]:
        """Set of feature strings this backend supports.

        Override in subclasses to declare capabilities like:
        "live_migration", "gpu_passthrough", "nested_virt", "uefi",
        "snapshots", "guest_agent", "spice", "vnc", "rdp".
        """
        return {"create", "destroy", "start", "stop", "pause", "resume",
                "reset", "reboot", "status", "list"}

    # ── Initialization / Teardown ────────────────────────────────────────────

    async def initialize(self) -> None:
        """Connect to the backend daemon (if any), validate state.

        Called once after construction.  Sets ``_initialized = True`` on success.
        """
        self._initialized = True

    async def shutdown(self) -> None:
        """Close connections, clean up resources."""
        self._initialized = False

    async def probe_availability(self) -> bool:
        """Thoroughly check if the backend is usable.

        May invoke subprocesses.  Returns True if available.
        """
        return self.is_available

    # ── Discovery ────────────────────────────────────────────────────────────

    @abstractmethod
    async def list_vms(self) -> list[str]:
        """Return names of all VMs known to this backend."""
        ...

    async def find_vm(self, name: str) -> bool:
        """Check if a VM with the given name exists."""
        return name in await self.list_vms()

    # ── VM Lifecycle ─────────────────────────────────────────────────────────

    @abstractmethod
    async def create_vm(self, config: VMConfig) -> str:
        """Create a new VM from the given configuration.

        Returns:
            The canonical name/ID assigned to the VM.

        Raises:
            HypervisorError: If the VM cannot be created.
            VMAlreadyRunningError: If a VM with this name already exists.
        """
        ...

    @abstractmethod
    async def destroy_vm(self, name: str) -> None:
        """Permanently delete a VM and its disks.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMAlreadyRunningError: If the VM is running and ``force`` is False.
        """
        ...

    @abstractmethod
    async def start_vm(self, name: str, headless: bool = False) -> None:
        """Start a VM.

        Args:
            name: VM name.
            headless: If True, do not open a display window.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMAlreadyRunningError: If the VM is already running.
        """
        ...

    @abstractmethod
    async def stop_vm(self, name: str, force: bool = False) -> None:
        """Stop a running VM.

        Args:
            name: VM name.
            force: If True, power-off immediately (kill the process).
                   If False, attempt graceful shutdown first.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
        """
        ...

    @abstractmethod
    async def pause_vm(self, name: str) -> None:
        """Pause a running VM (suspend CPU, keep RAM).

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
        """
        ...

    @abstractmethod
    async def resume_vm(self, name: str) -> None:
        """Resume a paused VM.

        Raises:
            VMNotFoundError: If the VM does not exist.
        """
        ...

    @abstractmethod
    async def reset_vm(self, name: str) -> None:
        """Hard reset a running VM (warm reboot).

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
        """
        ...

    @abstractmethod
    async def reboot_vm(self, name: str, graceful: bool = True) -> None:
        """Reboot a running VM.

        Args:
            name: VM name.
            graceful: If True, send ACPI reboot signal (guest agent).
                      If False, hard reset.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
        """
        ...

    async def shutdown_guest(self, name: str, timeout: int = 30) -> None:
        """Gracefully shut down the guest OS.

        Default implementation sends ACPI power button event. Backends with
        guest-agent integration may override for better reliability.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
        """
        await self.stop_vm(name, force=False)

    # ── Status / Info ────────────────────────────────────────────────────────

    @abstractmethod
    async def get_status(self, name: str) -> VMStatus:
        """Get the current status of a VM.

        Raises:
            VMNotFoundError: If the VM does not exist.
        """
        ...

    async def get_config(self, name: str) -> VMConfig | None:
        """Get the configuration of a VM.

        Returns None if the VM does not exist.
        """
        return None

    async def update_config(self, name: str, config: VMConfig) -> None:
        """Update a VM's configuration (hot-pluggable fields only where supported).

        Raises:
            VMNotFoundError: If the VM does not exist.
            OperationNotSupportedError: If the backend doesn't support updates.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support runtime config updates"
        )

    # ── Metrics ──────────────────────────────────────────────────────────────

    async def get_metrics(self, name: str) -> VMMetrics:
        """Get real-time metrics for a running VM.

        Default implementation returns zeroed metrics.  Backends should
        override to provide actual values.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support runtime metrics"
        )

    async def stream_metrics(self, name: str, interval_s: float = 2.0) -> AsyncIterator[VMMetrics]:
        """Stream metrics at the given interval.

        Yields VMMetrics objects.  Stops when the VM stops running or
        the caller breaks the loop.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support metric streaming"
        )

    # ── Display ──────────────────────────────────────────────────────────────

    async def get_display(self, name: str) -> VMDisplay:
        """Get display connection details for a running VM.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support display access"
        )

    async def set_display_password(self, name: str, password: str) -> None:
        """Set or change the display password for a running VM.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support display passwords"
        )

    async def screenshot(self, name: str) -> bytes:
        """Capture a screenshot from the VM display.

        Returns:
            PNG image bytes.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support screenshots"
        )

    # ── Console / Terminal ───────────────────────────────────────────────────

    async def get_console(self, name: str) -> VMConsole:
        """Get console/terminal access for a VM.

        Returns details for connecting to the VM's text console (serial,
        SSH, or VMCI socket).

        Raises:
            VMNotFoundError: If the VM does not exist.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support console access"
        )

    async def send_console_data(self, name: str, data: bytes) -> None:
        """Send raw data to the VM's console.

        Raises:
            VMNotFoundError: If the VM does not exist.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support console I/O"
        )

    async def receive_console_data(self, name: str, max_bytes: int = 4096) -> bytes:
        """Receive data from the VM's console.

        Raises:
            VMNotFoundError: If the VM does not exist.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support console I/O"
        )

    # ── Guest Agent ──────────────────────────────────────────────────────────

    async def guest_exec(self, name: str, command: str,
                         args: list[str] | None = None,
                         env: dict[str, str] | None = None,
                         timeout: int = 30,
                         capture_output: bool = True) -> dict[str, Any]:
        """Execute a command inside the guest OS via guest agent.

        Returns a dict with keys: exit_code, stdout, stderr, timed_out.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
            OperationNotSupportedError: If guest agent is not available.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support guest execution"
        )

    async def guest_info(self, name: str) -> VMGuestInfo:
        """Get guest OS information via guest agent.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
            OperationNotSupportedError: If guest agent is not available.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support guest info queries"
        )

    async def guest_file_read(self, name: str, path: str,
                              offset: int = 0,
                              max_bytes: int = 65536) -> bytes:
        """Read a file from inside the guest.

        Raises:
            VMNotFoundError: If the VM does not exist.
            OperationNotSupportedError: If guest agent is not available.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support guest file access"
        )

    async def guest_file_write(self, name: str, path: str,
                               data: bytes, offset: int = 0) -> None:
        """Write data to a file inside the guest.

        Raises:
            VMNotFoundError: If the VM does not exist.
            OperationNotSupportedError: If guest agent is not available.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support guest file access"
        )

    # ── Snapshots ────────────────────────────────────────────────────────────

    async def list_snapshots(self, name: str) -> list[VMSnapshot]:
        """List all snapshots for a VM.

        Raises:
            VMNotFoundError: If the VM does not exist.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support snapshots"
        )

    async def create_snapshot(self, name: str, snapshot_name: str,
                              description: str = "",
                              include_memory: bool = False) -> VMSnapshot:
        """Create a snapshot of a VM.

        Args:
            name: VM name.
            snapshot_name: Name for the new snapshot.
            description: Optional human-readable description.
            include_memory: If True, capture running VM state (RAM + devices).

        Returns:
            The created VMSnapshot metadata.

        Raises:
            VMNotFoundError: If the VM does not exist.
            OperationNotSupportedError: If snapshots are not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support snapshots"
        )

    async def restore_snapshot(self, name: str, snapshot_name: str) -> None:
        """Restore a VM to a previous snapshot state.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMAlreadyRunningError: If the VM is running and must be stopped first.
            OperationNotSupportedError: If snapshots are not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support snapshots"
        )

    async def delete_snapshot(self, name: str, snapshot_name: str) -> None:
        """Delete a snapshot.

        Raises:
            VMNotFoundError: If the VM does not exist.
            OperationNotSupportedError: If snapshots are not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support snapshots"
        )

    # ── Disk Operations ─────────────────────────────────────────────────────

    async def resize_disk(self, name: str, new_size_gb: int) -> None:
        """Resize a VM's primary disk image.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMAlreadyRunningError: If the VM is running.
            OperationNotSupportedError: If disk resize is not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support disk resize"
        )

    async def add_disk(self, name: str, size_gb: int,
                       disk_format: str = "qcow2") -> str:
        """Add a new disk to a VM.

        Returns:
            The path to the created disk image.

        Raises:
            VMNotFoundError: If the VM does not exist.
            OperationNotSupportedError: If disk management is not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support disk management"
        )

    async def eject_cdrom(self, name: str) -> None:
        """Eject the virtual CD-ROM media.

        Raises:
            VMNotFoundError: If the VM does not exist.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support CD-ROM ejection"
        )

    async def insert_cdrom(self, name: str, iso_path: str) -> None:
        """Insert an ISO into the virtual CD-ROM drive.

        Raises:
            VMNotFoundError: If the VM does not exist.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support CD-ROM insertion"
        )

    # ── Networking ───────────────────────────────────────────────────────────

    async def list_network_interfaces(self, name: str) -> list[VMNetwork]:
        """List network interfaces attached to a VM.

        Raises:
            VMNotFoundError: If the VM does not exist.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support network interface listing"
        )

    async def add_network_interface(self, name: str,
                                    network: VMNetwork) -> None:
        """Add a network interface to a VM.

        Raises:
            VMNotFoundError: If the VM does not exist.
            OperationNotSupportedError: If NIC management is not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support NIC management"
        )

    async def remove_network_interface(self, name: str, mac: str) -> None:
        """Remove a network interface by MAC address.

        Raises:
            VMNotFoundError: If the VM does not exist.
            OperationNotSupportedError: If NIC management is not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support NIC management"
        )

    async def connect_network(self, name: str, mac: str,
                              connected: bool = True) -> None:
        """Connect or disconnect a network interface.

        Raises:
            VMNotFoundError: If the VM does not exist.
            OperationNotSupportedError: If NIC management is not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support NIC management"
        )

    # ── Migration ────────────────────────────────────────────────────────────

    async def migrate_vm(self, name: str, target_uri: str,
                         live: bool = True,
                         bandwidth_mbps: int = 0) -> None:
        """Migrate a VM to another host.

        Args:
            name: VM name.
            target_uri: Connection URI of the target hypervisor.
            live: If True, perform live migration (zero downtime).
                  If False, cold migrate (stop VM, transfer, start on target).
            bandwidth_mbps: Bandwidth limit in Mbps (0 = unlimited).

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMMigrationError: If migration fails.
            OperationNotSupportedError: If migration is not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support migration"
        )

    # ── Import / Export ─────────────────────────────────────────────────────

    async def export_vm(self, name: str, output_path: str,
                        format: str = "qcow2") -> None:
        """Export a VM's disk image to a file.

        Args:
            name: VM name.
            output_path: Destination file path.
            format: Target disk image format.

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMAlreadyRunningError: If the VM is running.
            OperationNotSupportedError: If export is not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support export"
        )

    async def import_vm(self, input_path: str,
                        new_name: str | None = None) -> str:
        """Import a VM from a disk image file.

        Returns:
            The canonical name assigned to the imported VM.

        Raises:
            OperationNotSupportedError: If import is not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support import"
        )

    # ── Cloning ──────────────────────────────────────────────────────────────

    async def clone_vm(self, name: str, new_name: str,
                       linked: bool = False,
                       snapshots: bool = False) -> str:
        """Clone an existing VM.

        Args:
            name: Source VM name.
            new_name: Target VM name.
            linked: If True, create a linked clone (copy-on-write).
                    If False, create a full independent clone.
            snapshots: If True, clone all snapshots too.

        Returns:
            The canonical name assigned to the clone.

        Raises:
            VMNotFoundError: If the source VM does not exist.
            OperationNotSupportedError: If cloning is not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support cloning"
        )

    # ── Resource Limits ─────────────────────────────────────────────────────

    async def set_resource_limits(self, name: str,
                                 max_ram_mb: int = 0,
                                 max_cpus: int = 0,
                                 cpu_shares: int = 0,
                                 io_bandwidth_mbps: int = 0) -> None:
        """Set resource limits for a VM.

        Args:
            name: VM name.
            max_ram_mb: Maximum RAM in MB (0 = unlimited).
            max_cpus: Maximum vCPUs (0 = unlimited).
            cpu_shares: Relative CPU weight (0 = default).
            io_bandwidth_mbps: Maximum I/O bandwidth in MB/s (0 = unlimited).

        Raises:
            VMNotFoundError: If the VM does not exist.
            OperationNotSupportedError: If resource limits are not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support resource limits"
        )

    # ── USB Passthrough ─────────────────────────────────────────────────────

    async def attach_usb(self, name: str, vendor_id: str,
                         product_id: str) -> None:
        """Attach a USB device to a VM (host passthrough).

        Args:
            name: VM name.
            vendor_id: USB vendor ID (hex string, e.g. "0x1234").
            product_id: USB product ID (hex string).

        Raises:
            VMNotFoundError: If the VM does not exist.
            VMNotRunningError: If the VM is not running.
            OperationNotSupportedError: If USB passthrough is not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support USB passthrough"
        )

    async def detach_usb(self, name: str, vendor_id: str,
                         product_id: str) -> None:
        """Detach a USB device from a VM.

        Raises:
            VMNotFoundError: If the VM does not exist.
            OperationNotSupportedError: If USB passthrough is not supported.
        """
        raise OperationNotSupportedError(
            f"{self.display_name} does not support USB passthrough"
        )

    # ── Event Hooks ─────────────────────────────────────────────────────────

    async def on_vm_started(self, name: str) -> None:
        """Called after a VM has started successfully. Override for custom hooks."""
        pass

    async def on_vm_stopped(self, name: str) -> None:
        """Called after a VM has stopped. Override for custom hooks."""
        pass

    async def on_vm_error(self, name: str, error: str) -> None:
        """Called when a VM enters an error state. Override for custom hooks."""
        pass

    # ── Context Manager ─────────────────────────────────────────────────────

    async def __aenter__(self) -> "HypervisorBackend":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.shutdown()
