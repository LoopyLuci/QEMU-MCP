"""
Pydantic models for container API requests and responses.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ContainerState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    EXITED = "exited"
    DEAD = "dead"
    UNKNOWN = "unknown"


class PortMapping(BaseModel):
    """Port mapping for a container."""
    host_ip: str = Field(default="0.0.0.0")
    host_port: int = Field(ge=1, le=65535)
    container_port: int = Field(ge=1, le=65535)
    protocol: str = Field(default="tcp", pattern="^(tcp|udp|sctp)$")


class VolumeMount(BaseModel):
    """Volume mount for a container."""
    source: str = Field(description="Host path or volume name")
    target: str = Field(description="Container mount point")
    mode: str = Field(default="rw", pattern="^(rw|ro)$")


class CreateContainerRequest(BaseModel):
    """Request to create a new container."""
    name: str = Field(default="", description="Container name (auto-generated if empty)")
    image: str = Field(..., description="Docker image (e.g., ubuntu:22.04)")
    command: list[str] | None = Field(default=None, description="Entrypoint command")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    ports: dict[str, PortMapping] = Field(default_factory=dict, description="Port mappings")
    volumes: list[VolumeMount] = Field(default_factory=list, description="Volume mounts")
    network: str | None = Field(default=None, description="Network to connect to")
    cpu_limit: float | None = Field(default=None, ge=0.01, description="CPU limit (cores)")
    memory_limit: int | None = Field(default=None, ge=4, description="Memory limit in MB")
    labels: dict[str, str] = Field(default_factory=dict)
    restart_policy: str = Field(
        default="unless-stopped", pattern="^(no|always|on-failure|unless-stopped)$"
    )


class ContainerInfo(BaseModel):
    """Container information response."""
    id: str
    name: str
    image: str
    state: ContainerState
    status: str = ""
    created: datetime | None = None
    started: datetime | None = None
    ports: list[PortMapping] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    network_mode: str = "bridge"
    ip_address: str = ""
    cpu_usage: float = 0.0
    memory_usage_mb: float = 0.0
    memory_limit_mb: float = 0.0


class ContainerStats(BaseModel):
    """Real-time container statistics."""
    cpu_percent: float
    memory_usage_bytes: int
    memory_limit_bytes: int
    network_rx_bytes: int
    network_tx_bytes: int
    block_read_bytes: int
    block_write_bytes: int
    pids: int
    timestamp: datetime


class ExecRequest(BaseModel):
    """Request to execute a command in a container."""
    command: list[str] = Field(..., description="Command to execute")
    tty: bool = Field(default=False)
    env: dict[str, str] = Field(default_factory=dict)
    working_dir: str | None = Field(default=None)


class ExecResponse(BaseModel):
    """Response from container exec."""
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0


class ContainerLogs(BaseModel):
    """Container logs response."""
    id: str
    logs: list[str] = Field(default_factory=list)
    total_lines: int = 0
