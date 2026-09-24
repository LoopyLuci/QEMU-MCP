"""Kubernetes data models.

Pydantic-based models representing Kubernetes resources used by the
KubernetesBackend for type-safe resource manipulation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Enums ──────────────────────────────────────────────────────────────────────

class PodPhase(str, Enum):
    """Possible phases for a Kubernetes pod."""
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ServiceType(str, Enum):
    """Service types for Kubernetes services."""
    CLUSTER_IP = "ClusterIP"
    NODE_PORT = "NodePort"
    LOAD_BALANCER = "LoadBalancer"
    EXTERNAL_NAME = "ExternalName"


class RestartPolicy(str, Enum):
    """Container restart policies."""
    ALWAYS = "Always"
    ON_FAILURE = "OnFailure"
    NEVER = "Never"


class PullPolicy(str, Enum):
    """Image pull policies."""
    ALWAYS = "Always"
    IF_NOT_PRESENT = "IfNotPresent"
    NEVER = "Never"


# ── Base Model ─────────────────────────────────────────────────────────────────

class KubeModel:
    """Base Kubernetes model with dict serialization."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Kubernetes API dict."""
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KubeModel":
        """Create instance from Kubernetes API dict."""
        raise NotImplementedError


# ── Namespace ──────────────────────────────────────────────────────────────────

class Namespace(KubeModel):
    """Represents a Kubernetes namespace."""

    def __init__(
        self,
        name: str,
        status: str = "Active",
        labels: Optional[Dict[str, str]] = None,
        annotations: Optional[Dict[str, str]] = None,
        created: Optional[datetime] = None,
    ):
        self.name = name
        self.status = status
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.created = created

    def to_dict(self) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": self.name,
                "labels": self.labels,
                "annotations": self.annotations,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Namespace":
        metadata = data.get("metadata", {})
        status = data.get("status", {})
        created_str = metadata.get("timestamp") or metadata.get("creationTimestamp")
        created = None
        if created_str:
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        return cls(
            name=metadata.get("name", ""),
            status=status.get("phase", "Active"),
            labels=metadata.get("labels") or {},
            annotations=metadata.get("annotations") or {},
            created=created,
        )

    def __repr__(self) -> str:
        return f"Namespace(name={self.name!r}, status={self.status!r})"


# ── Cluster Context ────────────────────────────────────────────────────────────

class KubeCluster(KubeModel):
    """Represents a Kubernetes cluster context."""

    def __init__(
        self,
        name: str,
        server: str,
        namespace: str = "default",
        is_active: bool = False,
        user: Optional[str] = None,
    ):
        self.name = name
        self.server = server
        self.namespace = namespace
        self.is_active = is_active
        self.user = user

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "cluster": {"server": self.server},
            "context": {"namespace": self.namespace},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], active: bool = False) -> "KubeCluster":
        context = data.get("context", {})
        return cls(
            name=data.get("name", ""),
            server=context.get("cluster", ""),
            namespace=context.get("namespace", "default"),
            is_active=active,
            user=context.get("user"),
        )

    def __repr__(self) -> str:
        return f"KubeCluster(name={self.name!r}, active={self.is_active})"


# ── Pod ────────────────────────────────────────────────────────────────────────

class ContainerPort:
    """Container port definition."""

    def __init__(
        self,
        container_port: int,
        name: Optional[str] = None,
        protocol: str = "TCP",
    ):
        self.container_port = container_port
        self.name = name
        self.protocol = protocol

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"containerPort": self.container_port}
        if self.name:
            d["name"] = self.name
        d["protocol"] = self.protocol
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContainerPort":
        return cls(
            container_port=data.get("containerPort", 0),
            name=data.get("name"),
            protocol=data.get("protocol", "TCP"),
        )


class EnvVar:
    """Environment variable."""

    def __init__(self, name: str, value: Optional[str] = None):
        self.name = name
        self.value = value

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "value": self.value}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvVar":
        return cls(name=data.get("name", ""), value=data.get("value"))


class ContainerSpec:
    """Specification for a container within a pod."""

    def __init__(
        self,
        name: str,
        image: str,
        command: Optional[List[str]] = None,
        args: Optional[List[str]] = None,
        env: Optional[List[EnvVar]] = None,
        ports: Optional[List[ContainerPort]] = None,
        pull_policy: PullPolicy = PullPolicy.IF_NOT_PRESENT,
    ):
        self.name = name
        self.image = image
        self.command = command or []
        self.args = args or []
        self.env = env or []
        self.ports = ports or []
        self.pull_policy = pull_policy

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "image": self.image,
            "imagePullPolicy": self.pull_policy.value,
        }
        if self.command:
            d["command"] = self.command
        if self.args:
            d["args"] = self.args
        if self.env:
            d["env"] = [e.to_dict() for e in self.env]
        if self.ports:
            d["ports"] = [p.to_dict() for p in self.ports]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContainerSpec":
        env = [EnvVar.from_dict(e) for e in data.get("env", [])]
        ports = [ContainerPort.from_dict(p) for p in data.get("ports", [])]
        return cls(
            name=data.get("name", ""),
            image=data.get("image", ""),
            command=data.get("command"),
            args=data.get("args"),
            env=env or None,
            ports=ports or None,
            pull_policy=PullPolicy(data.get("imagePullPolicy", "IfNotPresent")),
        )


class Pod(KubeModel):
    """Represents a Kubernetes pod."""

    def __init__(
        self,
        name: str,
        namespace: str = "default",
        status: PodPhase = PodPhase.PENDING,
        node: Optional[str] = None,
        ip: Optional[str] = None,
        containers: Optional[List[str]] = None,
        restart_count: int = 0,
        labels: Optional[Dict[str, str]] = None,
        created: Optional[datetime] = None,
    ):
        self.name = name
        self.namespace = namespace
        self.status = status if isinstance(status, PodPhase) else PodPhase(status)
        self.node = node
        self.ip = ip
        self.containers = containers or []
        self.restart_count = restart_count
        self.labels = labels or {}
        self.created = created

    def to_dict(self) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pod":
        metadata = data.get("metadata", {})
        status = data.get("status", {})
        spec = data.get("spec", {})

        containers = [c.get("name", "") for c in spec.get("containers", [])]
        container_statuses = status.get("containerStatuses") or []
        restart_count = sum(cs.get("restartCount", 0) for cs in container_statuses)

        created_str = metadata.get("creationTimestamp")
        created = None
        if created_str:
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return cls(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            status=PodPhase(status.get("phase", "Unknown")),
            node=spec.get("nodeName"),
            ip=status.get("podIP"),
            containers=containers,
            restart_count=restart_count,
            labels=metadata.get("labels") or {},
            created=created,
        )

    def __repr__(self) -> str:
        return (
            f"Pod(name={self.name!r}, namespace={self.namespace!r}, "
            f"status={self.status.value!r})"
        )


# ── Deployment ─────────────────────────────────────────────────────────────────

class Deployment(KubeModel):
    """Represents a Kubernetes deployment."""

    def __init__(
        self,
        name: str,
        namespace: str = "default",
        replicas: int = 1,
        available_replicas: int = 0,
        ready_replicas: int = 0,
        updated_replicas: int = 0,
        containers: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
        selector: Optional[Dict[str, str]] = None,
        created: Optional[datetime] = None,
    ):
        self.name = name
        self.namespace = namespace
        self.replicas = replicas
        self.available_replicas = available_replicas
        self.ready_replicas = ready_replicas
        self.updated_replicas = updated_replicas
        self.containers = containers or []
        self.labels = labels or {}
        self.selector = selector or {}
        self.created = created

    def to_dict(self) -> Dict[str, Any]:
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
            },
            "spec": {
                "replicas": self.replicas,
                "selector": {"matchLabels": self.selector},
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Deployment":
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        status = data.get("status", {})
        template_spec = spec.get("template", {}).get("spec", {})

        containers = [c.get("name", "") for c in template_spec.get("containers", [])]

        created_str = metadata.get("creationTimestamp")
        created = None
        if created_str:
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return cls(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            replicas=spec.get("replicas", 0),
            available_replicas=status.get("availableReplicas", 0),
            ready_replicas=status.get("readyReplicas", 0),
            updated_replicas=status.get("updatedReplicas", 0),
            containers=containers,
            labels=metadata.get("labels") or {},
            selector=spec.get("selector", {}).get("matchLabels") or {},
            created=created,
        )

    @property
    def is_ready(self) -> bool:
        return (
            self.available_replicas == self.replicas
            and self.ready_replicas == self.replicas
            and self.replicas > 0
        )

    def __repr__(self) -> str:
        return (
            f"Deployment(name={self.name!r}, replicas={self.replicas}, "
            f"available={self.available_replicas})"
        )


# ── Service ─────────────────────────────────────────────────────────────────────

class ServicePort:
    """Service port definition."""

    def __init__(
        self,
        port: int,
        target_port: Optional[int] = None,
        node_port: Optional[int] = None,
        name: Optional[str] = None,
        protocol: str = "TCP",
    ):
        self.port = port
        self.target_port = target_port
        self.node_port = node_port
        self.name = name
        self.protocol = protocol

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"port": self.port, "protocol": self.protocol}
        if self.target_port is not None:
            d["targetPort"] = self.target_port
        if self.node_port is not None:
            d["nodePort"] = self.node_port
        if self.name:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServicePort":
        return cls(
            port=data.get("port", 0),
            target_port=data.get("targetPort"),
            node_port=data.get("nodePort"),
            name=data.get("name"),
            protocol=data.get("protocol", "TCP"),
        )


class KubeService(KubeModel):
    """Represents a Kubernetes service."""

    def __init__(
        self,
        name: str,
        namespace: str = "default",
        service_type: ServiceType = ServiceType.CLUSTER_IP,
        cluster_ip: str = "",
        external_ip: Optional[str] = None,
        ports: Optional[List[ServicePort]] = None,
        selector: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None,
        created: Optional[datetime] = None,
    ):
        self.name = name
        self.namespace = namespace
        self.service_type = (
            service_type
            if isinstance(service_type, ServiceType)
            else ServiceType(service_type)
        )
        self.cluster_ip = cluster_ip
        self.external_ip = external_ip
        self.ports = ports or []
        self.selector = selector or {}
        self.labels = labels or {}
        self.created = created

    def to_dict(self) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
            },
            "spec": {
                "type": self.service_type.value,
                "clusterIP": self.cluster_ip,
                "ports": [p.to_dict() for p in self.ports],
                "selector": self.selector,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KubeService":
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        ports = [ServicePort.from_dict(p) for p in spec.get("ports", [])]

        created_str = metadata.get("creationTimestamp")
        created = None
        if created_str:
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return cls(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            service_type=ServiceType(spec.get("type", "ClusterIP")),
            cluster_ip=spec.get("clusterIP", ""),
            external_ip=spec.get("externalIP"),
            ports=ports,
            selector=spec.get("selector") or {},
            labels=metadata.get("labels") or {},
            created=created,
        )

    def __repr__(self) -> str:
        return (
            f"KubeService(name={self.name!r}, type={self.service_type.value!r}, "
            f"cluster_ip={self.cluster_ip!r})"
        )


# ── Ingress ────────────────────────────────────────────────────────────────────

class IngressPath:
    """Ingress path rule."""

    def __init__(
        self,
        path: str,
        service_name: str,
        service_port: int = 80,
        path_type: str = "Prefix",
    ):
        self.path = path
        self.service_name = service_name
        self.service_port = service_port
        self.path_type = path_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "pathType": self.path_type,
            "backend": {
                "service": {
                    "name": self.service_name,
                    "port": {"number": self.service_port},
                }
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IngressPath":
        backend = data.get("backend", {})
        svc = backend.get("service", {})
        port = svc.get("port", {})
        return cls(
            path=data.get("path", "/"),
            service_name=svc.get("name", ""),
            service_port=port.get("number", 80),
            path_type=data.get("pathType", "Prefix"),
        )


class Ingress(KubeModel):
    """Represents a Kubernetes ingress."""

    def __init__(
        self,
        name: str,
        namespace: str = "default",
        hosts: Optional[List[str]] = None,
        paths: Optional[List[IngressPath]] = None,
        tls: Optional[List[Dict[str, Any]]] = None,
        labels: Optional[Dict[str, str]] = None,
        created: Optional[datetime] = None,
    ):
        self.name = name
        self.namespace = namespace
        self.hosts = hosts or []
        self.paths = paths or []
        self.tls = tls or []
        self.labels = labels or {}
        self.created = created

    def to_dict(self) -> Dict[str, Any]:
        rules = []
        for host in self.hosts:
            http_paths = [p.to_dict() for p in self.paths]
            rules.append({"host": host, "http": {"paths": http_paths}})

        d: Dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
            },
            "spec": {"rules": rules},
        }
        if self.tls:
            d["spec"]["tls"] = self.tls
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Ingress":
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})

        hosts = []
        paths = []
        for rule in spec.get("rules", []):
            host = rule.get("host", "")
            hosts.append(host)
            http = rule.get("http", {})
            for p in http.get("paths", []):
                paths.append(IngressPath.from_dict(p))

        created_str = metadata.get("creationTimestamp")
        created = None
        if created_str:
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return cls(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            hosts=hosts,
            paths=paths,
            tls=spec.get("tls"),
            labels=metadata.get("labels") or {},
            created=created,
        )

    def __repr__(self) -> str:
        return (
            f"Ingress(name={self.name!r}, hosts={self.hosts!r}, "
            f"paths={len(self.paths)})"
        )


# ── ConfigMap & Secret ─────────────────────────────────────────────────────────

class ConfigMap(KubeModel):
    """Represents a Kubernetes ConfigMap."""

    def __init__(
        self,
        name: str,
        namespace: str = "default",
        data: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.namespace = namespace
        self.data = data or {}
        self.labels = labels or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
            },
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigMap":
        metadata = data.get("metadata", {})
        return cls(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            data=data.get("data") or {},
            labels=metadata.get("labels") or {},
        )


class Secret(KubeModel):
    """Represents a Kubernetes Secret."""

    def __init__(
        self,
        name: str,
        namespace: str = "default",
        data: Optional[Dict[str, str]] = None,
        secret_type: str = "Opaque",
        labels: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.namespace = namespace
        self.data = data or {}
        self.secret_type = secret_type
        self.labels = labels or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "labels": self.labels,
            },
            "type": self.secret_type,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Secret":
        metadata = data.get("metadata", {})
        return cls(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            data=data.get("data") or {},
            secret_type=data.get("type", "Opaque"),
            labels=metadata.get("labels") or {},
        )
