"""
API schema package.

Exports all Pydantic models for request/response validation.
"""

from vm_harness.api.schemas.container import (
    ContainerState,
    PortMapping,
    VolumeMount,
    CreateContainerRequest,
    ContainerInfo,
    ContainerStats,
    ExecRequest,
    ExecResponse,
    ContainerLogs,
)
from vm_harness.api.schemas.kube import (
    K8sClusterState,
    PodPhase,
    ServiceType,
    CreateClusterRequest,
    K8sClusterInfo,
    NamespaceInfo,
    PodInfo,
    CreateDeploymentRequest,
    DeploymentInfo,
    ScaleRequest,
    CreateServiceRequest,
    ServiceInfo,
    NodeInfo,
)
from vm_harness.api.schemas.vm import (
    VMState,
    VMAction,
    VMDisplayType,
    VMAccelerationType,
    VMConfig,
    VMInfo,
    VMMetrics,
    CreateVMRequest,
    VMActionRequest,
    VMActionResponse,
    QMPCommandRequest,
    QMPCommandResponse,
    SSHCommandRequest,
    SSHCommandResponse,
    SnapshotInfo,
    CreateSnapshotRequest,
)

__all__ = [
    "ContainerState", "PortMapping", "VolumeMount",
    "CreateContainerRequest", "ContainerInfo", "ContainerStats",
    "ExecRequest", "ExecResponse", "ContainerLogs",
    "K8sClusterState", "PodPhase", "ServiceType",
    "CreateClusterRequest", "K8sClusterInfo", "NamespaceInfo",
    "PodInfo", "CreateDeploymentRequest", "DeploymentInfo",
    "ScaleRequest", "CreateServiceRequest", "ServiceInfo", "NodeInfo",
    "VMState", "VMAction", "VMDisplayType", "VMAccelerationType",
    "VMConfig", "VMInfo", "VMMetrics", "CreateVMRequest",
    "VMActionRequest", "VMActionResponse",
    "QMPCommandRequest", "QMPCommandResponse",
    "SSHCommandRequest", "SSHCommandResponse",
    "SnapshotInfo", "CreateSnapshotRequest",
]
