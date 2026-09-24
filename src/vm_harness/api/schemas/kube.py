"""
Pydantic models for Kubernetes API requests and responses.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class K8sClusterState(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    DEGRADED = "degraded"
    DELETING = "deleting"
    DELETED = "deleted"
    ERROR = "error"


class PodPhase(str, Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ServiceType(str, Enum):
    CLUSTER_IP = "ClusterIP"
    NODE_PORT = "NodePort"
    LOAD_BALANCER = "LoadBalancer"
    EXTERNAL_NAME = "ExternalName"


class CreateClusterRequest(BaseModel):
    """Request to create a Kubernetes cluster."""
    name: str = Field(..., min_length=1, max_length=63)
    version: str = Field(default="1.30", pattern=r"^\d+\.\d+$")
    nodes: int = Field(default=1, ge=1, le=100)
    cni: str = Field(default="calico", pattern="^(calico|flannel|cilium|weave)$")
    pod_network_cidr: str = Field(default="10.244.0.0/16")


class K8sClusterInfo(BaseModel):
    """Kubernetes cluster information."""
    name: str
    state: K8sClusterState
    version: str
    endpoint: str = ""
    node_count: int = 0
    pod_count: int = 0
    namespace_count: int = 0
    cni: str = "calico"
    created: datetime | None = None
    region: str = ""
    zone: str = ""


class NamespaceInfo(BaseModel):
    """Kubernetes namespace information."""
    name: str
    status: str = "Active"
    labels: dict[str, str] = Field(default_factory=dict)
    created: datetime | None = None


class PodInfo(BaseModel):
    """Kubernetes pod information."""
    name: str
    namespace: str = "default"
    phase: PodPhase = PodPhase.UNKNOWN
    pod_ip: str = ""
    host_ip: str = ""
    containers: list[str] = Field(default_factory=list)
    restart_count: int = 0
    created: datetime | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class CreateDeploymentRequest(BaseModel):
    """Request to create a deployment."""
    name: str = Field(..., min_length=1, max_length=253)
    image: str = Field(...)
    replicas: int = Field(default=1, ge=0, le=1000)
    namespace: str = Field(default="default")
    port: int = Field(default=80, ge=1, le=65535)
    env: dict[str, str] = Field(default_factory=dict)


class DeploymentInfo(BaseModel):
    """Deployment information."""
    name: str
    namespace: str = "default"
    replicas: int = 0
    ready_replicas: int = 0
    available_replicas: int = 0
    image: str = ""
    created: datetime | None = None


class ScaleRequest(BaseModel):
    """Request to scale a deployment."""
    replicas: int = Field(..., ge=0, le=1000)


class CreateServiceRequest(BaseModel):
    """Request to create a service."""
    name: str = Field(..., min_length=1, max_length=253)
    port: int = Field(default=80, ge=1, le=65535)
    target_port: int = Field(default=80, ge=1, le=65535)
    selector: dict[str, str] = Field(default_factory=dict)
    type: ServiceType = ServiceType.CLUSTER_IP
    namespace: str = Field(default="default")


class ServiceInfo(BaseModel):
    """Service information."""
    name: str
    namespace: str = "default"
    type: ServiceType = ServiceType.CLUSTER_IP
    cluster_ip: str = ""
    external_ip: str = ""
    ports: list[dict[str, Any]] = Field(default_factory=list)
    selector: dict[str, str] = Field(default_factory=dict)


class NodeInfo(BaseModel):
    """Kubernetes node information."""
    name: str
    status: str = "Ready"
    roles: list[str] = Field(default_factory=list)
    cpu_cores: int = 0
    memory_mb: int = 0
    pods_running: int = 0
    pods_capacity: int = 0
    kubelet_version: str = ""
    os_image: str = ""
    container_runtime: str = ""
    unschedulable: bool = False
    created: datetime | None = None
