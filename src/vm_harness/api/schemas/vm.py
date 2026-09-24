"""
Pydantic models for VM API requests and responses.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VMState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    SAVED = "saved"
    ERROR = "error"
    UNKNOWN = "unknown"


class VMAction(str, Enum):
    START = "start"
    STOP = "stop"
    RESET = "reset"
    POWERDOWN = "powerdown"
    PAUSE = "pause"
    RESUME = "resume"
    EJECT = "eject"


class VMDisplayType(str, Enum):
    SDL = "sdl"
    GTK = "gtk"
    NONE = "none"
    SPICE = "spice"


class VMAccelerationType(str, Enum):
    WHPX = "whpx"
    HAXM = "haxm"
    KVM = "kvm"
    TCG = "tcg"


class VMConfig(BaseModel):
    """VM configuration."""
    name: str = Field(..., min_length=1, max_length=64)
    ram_mb: int = Field(default=8192, ge=512, le=131072)
    cpus: int = Field(default=4, ge=1, le=128)
    disk_path: str = ""
    iso_path: str | None = None
    display: VMDisplayType = VMDisplayType.SDL
    gl_enabled: bool = True
    acceleration: VMAccelerationType = VMAccelerationType.WHPX
    network_bridge: str = ""
    mac_address: str = ""


class VMInfo(BaseModel):
    """VM information response."""
    name: str
    state: VMState
    config: VMConfig | None = None
    pid: int | None = None
    qmp_port: int = 4444
    ssh_port: int = 22
    uptime_seconds: int = 0
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    memory_allocated_mb: int = 0
    created: datetime | None = None
    last_started: datetime | None = None


class VMMetrics(BaseModel):
    """VM performance metrics."""
    name: str
    cpu_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_read_bytes: int
    disk_write_bytes: int
    network_rx_bytes: int
    network_tx_bytes: int
    timestamp: datetime


class CreateVMRequest(BaseModel):
    """Request to create a new VM."""
    name: str = Field(..., min_length=1, max_length=64)
    ram_mb: int = Field(default=8192, ge=512, le=131072)
    cpus: int = Field(default=4, ge=1, le=128)
    disk_size_gb: int = Field(default=40, ge=1, le=2048)
    iso_path: str | None = None
    display: VMDisplayType = VMDisplayType.SDL
    acceleration: VMAccelerationType = VMAccelerationType.WHPX
    network_bridge: str = ""
    start_after_create: bool = False


class VMActionRequest(BaseModel):
    """Request to perform a VM action."""
    action: VMAction
    force: bool = False


class VMActionResponse(BaseModel):
    """Response from a VM action."""
    name: str
    action: VMAction
    status: str = "ok"
    detail: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QMPCommandRequest(BaseModel):
    """Request to execute a QMP command."""
    command: str = Field(..., min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)


class QMPCommandResponse(BaseModel):
    """Response from a QMP command."""
    return_data: Any = {}
    error: str | None = None
    duration_ms: int = 0


class SSHCommandRequest(BaseModel):
    """Request to run an SSH command on the guest."""
    command: str = Field(..., min_length=1)
    timeout: int = Field(default=30, ge=1, le=300)


class SSHCommandResponse(BaseModel):
    """Response from an SSH command."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_ms: int = 0


class SnapshotInfo(BaseModel):
    """VM snapshot information."""
    name: str
    description: str = ""
    created: datetime | None = None
    size_bytes: int = 0
    is_current: bool = False


class CreateSnapshotRequest(BaseModel):
    """Request to create a snapshot."""
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    include_memory: bool = False
