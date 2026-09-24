"""
API package for vm-harness.

Provides HTTP/WebSocket route handlers, middleware (auth, RBAC, rate limiting),
and Pydantic schemas for request/response validation.
"""

from vm_harness.api.middleware import (
    auth_middleware,
    rbac_middleware,
    rate_limit_middleware,
    resolve_permissions,
    has_permission,
    RateLimitConfig,
)
from vm_harness.api.schemas import (
    VMState, VMAction, VMDisplayType, VMAccelerationType,
    VMConfig, VMInfo, VMMetrics, CreateVMRequest,
    VMActionRequest, VMActionResponse,
    QMPCommandRequest, QMPCommandResponse,
    SSHCommandRequest, SSHCommandResponse,
    SnapshotInfo, CreateSnapshotRequest,
    ContainerState, PortMapping, VolumeMount,
    CreateContainerRequest, ContainerInfo, ContainerStats,
    ExecRequest, ExecResponse, ContainerLogs,
    K8sClusterState, PodPhase, ServiceType,
    CreateClusterRequest, K8sClusterInfo, NamespaceInfo,
    PodInfo, CreateDeploymentRequest, DeploymentInfo,
    ScaleRequest, CreateServiceRequest, ServiceInfo, NodeInfo,
)

__all__ = [
    "auth_middleware", "rbac_middleware", "rate_limit_middleware",
    "resolve_permissions", "has_permission", "RateLimitConfig",
    "VMState", "VMAction", "VMDisplayType", "VMAccelerationType",
    "VMConfig", "VMInfo", "VMMetrics", "CreateVMRequest",
    "VMActionRequest", "VMActionResponse",
    "QMPCommandRequest", "QMPCommandResponse",
    "SSHCommandRequest", "SSHCommandResponse",
    "SnapshotInfo", "CreateSnapshotRequest",
    "ContainerState", "PortMapping", "VolumeMount",
    "CreateContainerRequest", "ContainerInfo", "ContainerStats",
    "ExecRequest", "ExecResponse", "ContainerLogs",
    "K8sClusterState", "PodPhase", "ServiceType",
    "CreateClusterRequest", "K8sClusterInfo", "NamespaceInfo",
    "PodInfo", "CreateDeploymentRequest", "DeploymentInfo",
    "ScaleRequest", "CreateServiceRequest", "ServiceInfo", "NodeInfo",
]
