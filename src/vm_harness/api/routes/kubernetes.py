"""
Kubernetes cluster management route handlers.

Endpoints for cluster lifecycle, node management, pod operations,
deployments, services, configmaps, and RBAC within managed K8s clusters.
Supports multi-cluster federation via context switching.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

log = logging.getLogger("vmharness.api.kubernetes")


def _kube_service(request: web.Request) -> Any:
    svc = request.app.get("kubernetes_service")
    if svc is None:
        raise web.HTTPInternalServerError(
            text=json.dumps({"error": "kubernetes_service_not_configured"})
        )
    return svc


def _ok(data: dict[str, Any] | list[Any]) -> web.Response:
    return web.json_response(data)


def _err(status: int, error: str, detail: str = "") -> web.Response:
    body: dict[str, Any] = {"error": error}
    if detail:
        body["detail"] = detail
    return web.json_response(body, status=status)


# ── cluster operations ───────────────────────────────────────────────────────

async def list_clusters(request: web.Request) -> web.Response:
    """GET /api/v1/kubernetes/clusters — list managed clusters."""
    svc = _kube_service(request)
    try:
        clusters = await svc.list_clusters()
        return _ok(clusters)
    except Exception as e:
        log.exception("list_clusters failed")
        return _err(500, "list_failed", str(e))


async def get_cluster(request: web.Request) -> web.Response:
    """GET /api/v1/kubernetes/clusters/{name} — inspect a cluster."""
    svc = _kube_service(request)
    name = request.match_info["name"]
    try:
        cluster = await svc.get_cluster(name)
        if cluster is None:
            return _err(404, "not_found", f"Cluster {name} not found")
        return _ok(cluster)
    except Exception as e:
        return _err(500, "inspect_failed", str(e))


async def create_cluster(request: web.Request) -> web.Response:
    """POST /api/v1/kubernetes/clusters — provision a new cluster."""
    svc = _kube_service(request)
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    name = body.get("name", "").strip()
    if not name:
        return _err(400, "missing_name")
    try:
        result = await svc.create_cluster(
            name=name,
            version=body.get("version", "1.30"),
            nodes=body.get("nodes", 1),
            cni=body.get("cni", "calico"),
            pod_network_cidr=body.get("pod_network_cidr", "10.244.0.0/16"),
        )
        return web.json_response(result, status=201)
    except Exception as e:
        log.exception("create_cluster failed")
        return _err(500, "create_failed", str(e))


async def delete_cluster(request: web.Request) -> web.Response:
    """DELETE /api/v1/kubernetes/clusters/{name} — tear down a cluster."""
    svc = _kube_service(request)
    name = request.match_info["name"]
    try:
        await svc.delete_cluster(name)
        return _ok({"name": name, "action": "delete", "status": "ok"})
    except Exception as e:
        return _err(500, "delete_failed", str(e))


# ── namespace operations ─────────────────────────────────────────────────────

async def list_namespaces(request: web.Request) -> web.Response:
    """GET /api/v1/kubernetes/namespaces — list namespaces."""
    svc = _kube_service(request)
    cluster = request.query.get("cluster", "")
    try:
        namespaces = await svc.list_namespaces(cluster)
        return _ok(namespaces)
    except Exception as e:
        return _err(500, "list_failed", str(e))


async def create_namespace(request: web.Request) -> web.Response:
    """POST /api/v1/kubernetes/namespaces — create a namespace."""
    svc = _kube_service(request)
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    name = body.get("name", "").strip()
    if not name:
        return _err(400, "missing_name")
    try:
        result = await svc.create_namespace(
            name, cluster=body.get("cluster", "")
        )
        return web.json_response(result, status=201)
    except Exception as e:
        return _err(500, "create_failed", str(e))


# ── pod operations ───────────────────────────────────────────────────────────

async def list_pods(request: web.Request) -> web.Response:
    """GET /api/v1/kubernetes/pods — list pods (optionally by namespace)."""
    svc = _kube_service(request)
    namespace = request.query.get("namespace", "")
    cluster = request.query.get("cluster", "")
    try:
        pods = await svc.list_pods(namespace=namespace, cluster=cluster)
        return _ok(pods)
    except Exception as e:
        return _err(500, "list_failed", str(e))


async def get_pod(request: web.Request) -> web.Response:
    """GET /api/v1/kubernetes/pods/{name} — inspect a pod."""
    svc = _kube_service(request)
    name = request.match_info["name"]
    namespace = request.query.get("namespace", "default")
    cluster = request.query.get("cluster", "")
    try:
        pod = await svc.get_pod(name, namespace=namespace, cluster=cluster)
        if pod is None:
            return _err(404, "not_found")
        return _ok(pod)
    except Exception as e:
        return _err(500, "inspect_failed", str(e))


async def delete_pod(request: web.Request) -> web.Response:
    """DELETE /api/v1/kubernetes/pods/{name} — delete a pod."""
    svc = _kube_service(request)
    name = request.match_info["name"]
    namespace = request.query.get("namespace", "default")
    cluster = request.query.get("cluster", "")
    try:
        await svc.delete_pod(name, namespace=namespace, cluster=cluster)
        return _ok({"name": name, "action": "delete", "status": "ok"})
    except Exception as e:
        return _err(500, "delete_failed", str(e))


async def get_pod_logs(request: web.Request) -> web.Response:
    """GET /api/v1/kubernetes/pods/{name}/logs — fetch pod logs."""
    svc = _kube_service(request)
    name = request.match_info["name"]
    namespace = request.query.get("namespace", "default")
    cluster = request.query.get("cluster", "")
    tail = int(request.query.get("tail", "100"))
    container = request.query.get("container", "")
    try:
        logs = await svc.get_pod_logs(
            name, namespace=namespace, cluster=cluster,
            tail=tail, container=container or None
        )
        return _ok({"name": name, "logs": logs})
    except Exception as e:
        return _err(500, "logs_failed", str(e))


# ── deployment operations ────────────────────────────────────────────────────

async def list_deployments(request: web.Request) -> web.Response:
    """GET /api/v1/kubernetes/deployments — list deployments."""
    svc = _kube_service(request)
    namespace = request.query.get("namespace", "")
    cluster = request.query.get("cluster", "")
    try:
        deployments = await svc.list_deployments(namespace=namespace, cluster=cluster)
        return _ok(deployments)
    except Exception as e:
        return _err(500, "list_failed", str(e))


async def create_deployment(request: web.Request) -> web.Response:
    """POST /api/v1/kubernetes/deployments — create a deployment."""
    svc = _kube_service(request)
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    name = body.get("name", "").strip()
    image = body.get("image", "").strip()
    if not name or not image:
        return _err(400, "missing_name_or_image")
    try:
        result = await svc.create_deployment(
            name=name,
            image=image,
            replicas=body.get("replicas", 1),
            namespace=body.get("namespace", "default"),
            cluster=body.get("cluster", ""),
            port=body.get("port", 80),
            env=body.get("env", {}),
        )
        return web.json_response(result, status=201)
    except Exception as e:
        return _err(500, "create_failed", str(e))


async def scale_deployment(request: web.Request) -> web.Response:
    """POST /api/v1/kubernetes/deployments/{name}/scale — scale a deployment."""
    svc = _kube_service(request)
    name = request.match_info["name"]
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    replicas = body.get("replicas")
    if replicas is None:
        return _err(400, "missing_replicas")
    namespace = body.get("namespace", "default")
    cluster = body.get("cluster", "")
    try:
        result = await svc.scale_deployment(
            name, replicas=replicas, namespace=namespace, cluster=cluster
        )
        return _ok(result)
    except Exception as e:
        return _err(500, "scale_failed", str(e))


# ── service operations ───────────────────────────────────────────────────────

async def list_services(request: web.Request) -> web.Response:
    """GET /api/v1/kubernetes/services — list services."""
    svc = _kube_service(request)
    namespace = request.query.get("namespace", "")
    cluster = request.query.get("cluster", "")
    try:
        services = await svc.list_services(namespace=namespace, cluster=cluster)
        return _ok(services)
    except Exception as e:
        return _err(500, "list_failed", str(e))


async def create_service(request: web.Request) -> web.Response:
    """POST /api/v1/kubernetes/services — create a service."""
    svc = _kube_service(request)
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    name = body.get("name", "").strip()
    if not name:
        return _err(400, "missing_name")
    try:
        result = await svc.create_service(
            name=name,
            port=body.get("port", 80),
            target_port=body.get("target_port", 80),
            selector=body.get("selector", {}),
            service_type=body.get("type", "ClusterIP"),
            namespace=body.get("namespace", "default"),
            cluster=body.get("cluster", ""),
        )
        return web.json_response(result, status=201)
    except Exception as e:
        return _err(500, "create_failed", str(e))


# ── node operations ──────────────────────────────────────────────────────────

async def list_nodes(request: web.Request) -> web.Response:
    """GET /api/v1/kubernetes/nodes — list cluster nodes."""
    svc = _kube_service(request)
    cluster = request.query.get("cluster", "")
    try:
        nodes = await svc.list_nodes(cluster=cluster)
        return _ok(nodes)
    except Exception as e:
        return _err(500, "list_failed", str(e))


async def cordon_node(request: web.Request) -> web.Response:
    """POST /api/v1/kubernetes/nodes/{name}/cordon — cordon a node."""
    svc = _kube_service(request)
    name = request.match_info["name"]
    cluster = request.query.get("cluster", "")
    try:
        await svc.cordon_node(name, cluster=cluster)
        return _ok({"name": name, "action": "cordon", "status": "ok"})
    except Exception as e:
        return _err(500, "cordon_failed", str(e))


async def uncordon_node(request: web.Request) -> web.Response:
    """POST /api/v1/kubernetes/nodes/{name}/uncordon — uncordon a node."""
    svc = _kube_service(request)
    name = request.match_info["name"]
    cluster = request.query.get("cluster", "")
    try:
        await svc.uncordon_node(name, cluster=cluster)
        return _ok({"name": name, "action": "uncordon", "status": "ok"})
    except Exception as e:
        return _err(500, "uncordon_failed", str(e))


# ── route registration ──────────────────────────────────────────────────────

def setup_routes(app: web.Application) -> None:
    """Register Kubernetes routes on the aiohttp app."""
    # clusters
    app.router.add_get("/api/v1/kubernetes/clusters", list_clusters)
    app.router.add_post("/api/v1/kubernetes/clusters", create_cluster)
    app.router.add_get("/api/v1/kubernetes/clusters/{name}", get_cluster)
    app.router.add_delete("/api/v1/kubernetes/clusters/{name}", delete_cluster)

    # namespaces
    app.router.add_get("/api/v1/kubernetes/namespaces", list_namespaces)
    app.router.add_post("/api/v1/kubernetes/namespaces", create_namespace)

    # pods
    app.router.add_get("/api/v1/kubernetes/pods", list_pods)
    app.router.add_get("/api/v1/kubernetes/pods/{name}", get_pod)
    app.router.add_delete("/api/v1/kubernetes/pods/{name}", delete_pod)
    app.router.add_get("/api/v1/kubernetes/pods/{name}/logs", get_pod_logs)

    # deployments
    app.router.add_get("/api/v1/kubernetes/deployments", list_deployments)
    app.router.add_post("/api/v1/kubernetes/deployments", create_deployment)
    app.router.add_post(
        "/api/v1/kubernetes/deployments/{name}/scale", scale_deployment
    )

    # services
    app.router.add_get("/api/v1/kubernetes/services", list_services)
    app.router.add_post("/api/v1/kubernetes/services", create_service)

    # nodes
    app.router.add_get("/api/v1/kubernetes/nodes", list_nodes)
    app.router.add_post("/api/v1/kubernetes/nodes/{name}/cordon", cordon_node)
    app.router.add_post("/api/v1/kubernetes/nodes/{name}/uncordon", uncordon_node)
