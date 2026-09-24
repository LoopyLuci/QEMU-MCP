"""
Multi-cluster federation and service mesh route handlers.

Manages cluster registration, cross-cluster service discovery,
federation policies, and Tailscale-based secure mesh networking
between geographically distributed clusters.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

log = logging.getLogger("vmharness.api.federation")


def _fed_service(request: web.Request) -> Any:
    svc = request.app.get("federation_service")
    if svc is None:
        raise web.HTTPInternalServerError(
            text=json.dumps({"error": "federation_service_not_configured"})
        )
    return svc


def _ok(data: dict[str, Any] | list[Any]) -> web.Response:
    return web.json_response(data)


def _err(status: int, error: str, detail: str = "") -> web.Response:
    body: dict[str, Any] = {"error": error}
    if detail:
        body["detail"] = detail
    return web.json_response(body, status=status)


# ── federation management ────────────────────────────────────────────────────

async def get_federation_status(request: web.Request) -> web.Response:
    """GET /api/v1/federation/status — overall federation health."""
    svc = _fed_service(request)
    try:
        status = await svc.get_status()
        return _ok(status)
    except Exception as e:
        log.exception("get_federation_status failed")
        return _err(500, "status_failed", str(e))


async def list_federation_members(request: web.Request) -> web.Response:
    """GET /api/v1/federation/members — list federation member clusters."""
    svc = _fed_service(request)
    try:
        members = await svc.list_members()
        return _ok(members)
    except Exception as e:
        return _err(500, "list_failed", str(e))


async def join_federation(request: web.Request) -> web.Response:
    """POST /api/v1/federation/members — join a cluster to the federation."""
    svc = _fed_service(request)
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    cluster_name = body.get("cluster_name", "").join("")
    if not cluster_name:
        return _err(400, "missing_cluster_name")
    try:
        result = await svc.join(
            cluster_name=cluster_name,
            endpoint=body.get("endpoint", ""),
            token=body.get("token", ""),
            region=body.get("region", ""),
            zone=body.get("zone", ""),
        )
        return web.json_response(result, status=201)
    except Exception as e:
        log.exception("join_federation failed")
        return _err(500, "join_failed", str(e))


async def leave_federation(request: web.Request) -> web.Response:
    """DELETE /api/v1/federation/members/{name} — remove a member."""
    svc = _fed_service(request)
    name = request.match_info["name"]
    try:
        await svc.leave(name)
        return _ok({"name": name, "action": "leave", "status": "ok"})
    except Exception as e:
        return _err(500, "leave_failed", str(e))


# ── service mesh ─────────────────────────────────────────────────────────────

async def list_mesh_services(request: web.Request) -> web.Response:
    """GET /api/v1/federation/mesh/services — discover services across clusters."""
    svc = _fed_service(request)
    try:
        services = await svc.discover_services()
        return _ok(services)
    except Exception as e:
        return _err(500, "discovery_failed", str(e))


async def expose_service(request: web.Request) -> web.Response:
    """POST /api/v1/federation/mesh/expose — expose a service to the mesh."""
    svc = _fed_service(request)
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    service_name = body.get("service", "").strip()
    if not service_name:
        return _err(400, "missing_service")
    try:
        result = await svc.expose_service(
            service_name=service_name,
            port=body.get("port", 80),
            clusters=body.get("clusters", []),
            tailscale=body.get("tailscale", True),
        )
        return web.json_response(result, status=201)
    except Exception as e:
        return _err(500, "expose_failed", str(e))


async def unexpose_service(request: web.Request) -> web.Response:
    """DELETE /api/v1/federation/mesh/expose/{name} — unexpose a service."""
    svc = _fed_service(request)
    name = request.match_info["name"]
    try:
        await svc.unexpose_service(name)
        return _ok({"service": name, "action": "unexpose", "status": "ok"})
    except Exception as e:
        return _err(500, "unexpose_failed", str(e))


# ── DNS / discovery ─────────────────────────────────────────────────────────

async def get_dns_records(request: web.Request) -> web.Response:
    """GET /api/v1/federation/dns — list federation DNS records."""
    svc = _fed_service(request)
    try:
        records = await svc.get_dns_records()
        return _ok(records)
    except Exception as e:
        return _err(500, "dns_failed", str(e))


async def add_dns_record(request: web.Request) -> web.Response:
    """POST /api/v1/federation/dns — add a DNS record."""
    svc = _fed_service(request)
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    name = body.get("name", "").strip()
    ip = body.get("ip", "").strip()
    if not name or not ip:
        return _err(400, "missing_name_or_ip")
    try:
        await svc.add_dns_record(name=name, ip=ip, record_type=body.get("type", "A"))
        return web.json_response({"name": name, "ip": ip, "action": "add"}, status=201)
    except Exception as e:
        return _err(500, "add_failed", str(e))


# ── Tailscale integration ───────────────────────────────────────────────────

async def get_tailscale_status(request: web.Request) -> web.Response:
    """GET /api/v1/federation/tailscale — Tailscale status."""
    svc = _fed_service(request)
    try:
        ts = await svc.get_tailscale_status()
        return _ok(ts)
    except Exception as e:
        return _err(500, "tailscale_failed", str(e))


async def enable_tailscale_exit_node(request: web.Request) -> web.Response:
    """POST /api/v1/federation/tailscale/exit-node — configure exit node."""
    svc = _fed_service(request)
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    node = body.get("node", "").strip()
    if not node:
        return _err(400, "missing_node")
    try:
        result = await svc.enable_exit_node(node)
        return _ok(result)
    except Exception as e:
        return _err(500, "exit_node_failed", str(e))


# ── route registration ──────────────────────────────────────────────────────

def setup_routes(app: web.Application) -> None:
    """Register federation routes on the aiohttp app."""
    app.router.add_get("/api/v1/federation/status", get_federation_status)
    app.router.add_get("/api/v1/federation/members", list_federation_members)
    app.router.add_post("/api/v1/federation/members", join_federation)
    app.router.add_delete("/api/v1/federation/members/{name}", leave_federation)

    app.router.add_get("/api/v1/federation/mesh/services", list_mesh_services)
    app.router.add_post("/api/v1/federation/mesh/expose", expose_service)
    app.router.add_delete("/api/v1/federation/mesh/expose/{name}", unexpose_service)

    app.router.add_get("/api/v1/federation/dns", get_dns_records)
    app.router.add_post("/api/v1/federation/dns", add_dns_record)

    app.router.add_get("/api/v1/federation/tailscale", get_tailscale_status)
    app.router.add_post(
        "/api/v1/federation/tailscale/exit-node", enable_tailscale_exit_node
    )
