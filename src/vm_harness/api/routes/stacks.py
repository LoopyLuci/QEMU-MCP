"""
Stack management route handlers.

A "stack" is a named, versioned collection of VMs, containers, and
Kubernetes resources deployed together as a unit. Stacks support
compose-like definitions, dependency ordering, and atomic updates.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

log = logging.getLogger("vmharness.api.stacks")


def _stack_service(request: web.Request) -> Any:
    svc = request.app.get("stack_service")
    if svc is None:
        raise web.HTTPInternalServerError(
            text=json.dumps({"error": "stack_service_not_configured"})
        )
    return svc


def _ok(data: dict[str, Any] | list[Any]) -> web.Response:
    return web.json_response(data)


def _err(status: int, error: str, detail: str = "") -> web.Response:
    body: dict[str, Any] = {"error": error}
    if detail:
        body["detail"] = detail
    return web.json_response(body, status=status)


# ── stack CRUD ──────────────────────────────────────────────────────────────

async def list_stacks(request: web.Request) -> web.Response:
    """GET /api/v1/stacks — list all stacks."""
    svc = _stack_service(request)
    try:
        all_flag = request.query.get("all", "true").lower() == "true"
        stacks = await svc.list(all=all_flag)
        return _ok(stacks)
    except Exception as e:
        log.exception("list_stacks failed")
        return _err(500, "list_failed", str(e))


async def get_stack(request: web.Request) -> web.Response:
    """GET /api/v1/stacks/{name} — inspect a stack."""
    svc = _stack_service(request)
    name = request.match_info["name"]
    try:
        stack = await svc.inspect(name)
        if stack is None:
            return _err(404, "not_found", f"Stack {name} not found")
        return _ok(stack)
    except Exception as e:
        return _err(500, "inspect_failed", str(e))


async def create_stack(request: web.Request) -> web.Response:
    """POST /api/v1/stacks — create a new stack."""
    svc = _stack_service(request)
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    name = body.get("name", "").strip()
    if not name:
        return _err(400, "missing_name")
    try:
        result = await svc.create(
            name=name,
            description=body.get("description", ""),
            compose=body.get("compose", {}),
            vm_specs=body.get("vms", []),
            container_specs=body.get("containers", []),
            kube_manifests=body.get("kubernetes", []),
            env_vars=body.get("env", {}),
            labels=body.get("labels", {}),
        )
        return web.json_response(result, status=201)
    except Exception as e:
        log.exception("create_stack failed")
        return _err(500, "create_failed", str(e))


async def update_stack(request: web.Request) -> web.Response:
    """PUT /api/v1/stacks/{name} — update a stack."""
    svc = _stack_service(request)
    name = request.match_info["name"]
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    try:
        result = await svc.update(
            name,
            compose=body.get("compose"),
            vm_specs=body.get("vms"),
            container_specs=body.get("containers"),
            kube_manifests=body.get("kubernetes"),
            env_vars=body.get("env"),
        )
        return _ok(result)
    except Exception as e:
        log.exception("update_stack failed")
        return _err(500, "update_failed", str(e))


async def delete_stack(request: web.Request) -> web.Response:
    """DELETE /api/v1/stacks/{name} — delete a stack and all its resources."""
    svc = _stack_service(request)
    name = request.match_info["name"]
    force = request.query.get("force", "false").lower() == "true"
    try:
        await svc.delete(name, force=force)
        return _ok({"name": name, "action": "delete", "status": "ok"})
    except Exception as e:
        return _err(500, "delete_failed", str(e))


# ── stack lifecycle ─────────────────────────────────────────────────────────

async def start_stack(request: web.Request) -> web.Response:
    """POST /api/v1/stacks/{name}/start — start all resources in a stack."""
    svc = _stack_service(request)
    name = request.match_info["name"]
    try:
        await svc.start(name)
        return _ok({"name": name, "action": "start", "status": "ok"})
    except Exception as e:
        return _err(500, "start_failed", str(e))


async def stop_stack(request: web.Request) -> web.Response:
    """POST /api/v1/stacks/{name}/stop — stop all resources in a stack."""
    svc = _stack_service(request)
    name = request.match_info["name"]
    force = request.query.get("force", "false").lower() == "true"
    try:
        await svc.stop(name, force=force)
        return _ok({"name": name, "action": "stop", "status": "ok"})
    except Exception as e:
        return _err(500, "stop_failed", str(e))


async def restart_stack(request: web.Request) -> web.Response:
    """POST /api/v1/stacks/{name}/restart — restart all resources in a stack."""
    svc = _stack_service(request)
    name = request.match_info["name"]
    try:
        await svc.restart(name)
        return _ok({"name": name, "action": "restart", "status": "ok"})
    except Exception as e:
        return _err(500, "restart_failed", str(e))


async def scale_stack(request: web.Request) -> web.Response:
    """POST /api/v1/stacks/{name}/scale — scale stack resources."""
    svc = _stack_service(request)
    name = request.match_info["name"]
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    resource = body.get("resource", "").strip()
    replicas = body.get("replicas")
    if not resource or replicas is None:
        return _err(400, "missing_resource_or_replicas")
    try:
        result = await svc.scale(name, resource, replicas=replicas)
        return _ok(result)
    except Exception as e:
        return _err(500, "scale_failed", str(e))


# ── stack status & events ──────────────────────────────────────────────────

async def get_stack_status(request: web.Request) -> web.Response:
    """GET /api/v1/stacks/{name}/status — detailed stack status."""
    svc = _stack_service(request)
    name = request.match_info["name"]
    try:
        status = await svc.status(name)
        return _ok(status)
    except Exception as e:
        return _err(500, "status_failed", str(e))


async def get_stack_logs(request: web.Request) -> web.Response:
    """GET /api/v1/stacks/{name}/logs — aggregated stack logs."""
    svc = _stack_service(request)
    name = request.match_info["name"]
    tail = int(request.query.get("tail", "200"))
    try:
        logs = await svc.logs(name, tail=tail)
        return _ok({"name": name, "logs": logs})
    except Exception as e:
        return _err(500, "logs_failed", str(e))


async def get_stack_events(request: web.Request) -> web.Response:
    """GET /api/v1/stacks/{name}/events — stack lifecycle events."""
    svc = _stack_service(request)
    name = request.match_info["name"]
    try:
        events = await svc.events(name)
        return _ok(events)
    except Exception as e:
        return _err(500, "events_failed", str(e))


# ── route registration ──────────────────────────────────────────────────────

def setup_routes(app: web.Application) -> None:
    """Register stack routes on the aiohttp app."""
    app.router.add_get("/api/v1/stacks", list_stacks)
    app.router.add_post("/api/v1/stacks", create_stack)
    app.router.add_get("/api/v1/stacks/{name}", get_stack)
    app.router.add_put("/api/v1/stacks/{name}", update_stack)
    app.router.add_delete("/api/v1/stacks/{name}", delete_stack)
    app.router.add_post("/api/v1/stacks/{name}/start", start_stack)
    app.router.add_post("/api/v1/stacks/{name}/stop", stop_stack)
    app.router.add_post("/api/v1/stacks/{name}/restart", restart_stack)
    app.router.add_post("/api/v1/stacks/{name}/scale", scale_stack)
    app.router.add_get("/api/v1/stacks/{name}/status", get_stack_status)
    app.router.add_get("/api/v1/stacks/{name}/logs", get_stack_logs)
    app.router.add_get("/api/v1/stacks/{name}/events", get_stack_events)
