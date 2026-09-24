"""
Container lifecycle management route handlers.

Provides REST endpoints for Docker container operations: create, start,
stop, restart, remove, exec, logs, and status queries. All endpoints
require authentication via the API key middleware.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from aiohttp import web

log = logging.getLogger("vmharness.api.containers")


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_container_service(request: web.Request) -> Any:
    """Extract the container service from the request app context."""
    service = request.app.get("container_service")
    if service is None:
        raise web.HTTPInternalServerError(
            text=json.dumps({"error": "container_service_not_configured"})
        )
    return service


def _ok(data: dict[str, Any] | list[Any]) -> web.Response:
    return web.json_response(data)


def _err(status: int, error: str, detail: str = "") -> web.Response:
    body: dict[str, Any] = {"error": error}
    if detail:
        body["detail"] = detail
    return web.json_response(body, status=status)


# ── route handlers ───────────────────────────────────────────────────────────

async def list_containers(request: web.Request) -> web.Response:
    """GET /api/v1/containers — list all containers (running + stopped)."""
    service = _get_container_service(request)
    try:
        all_flag = request.query.get("all", "true").lower() == "true"
        containers = await service.list(all=all_flag)
        return _ok(containers)
    except Exception as e:
        log.exception("list_containers failed")
        return _err(500, "list_failed", str(e))


async def get_container(request: web.Request) -> web.Response:
    """GET /api/v1/containers/{id} — inspect a single container."""
    service = _get_container_service(request)
    container_id = request.match_info["id"]
    try:
        info = await service.inspect(container_id)
        if info is None:
            return _err(404, "not_found", f"Container {container_id} not found")
        return _ok(info)
    except Exception as e:
        log.exception("inspect_container failed")
        return _err(500, "inspect_failed", str(e))


async def create_container(request: web.Request) -> web.Response:
    """POST /api/v1/containers — create a new container."""
    service = _get_container_service(request)
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")

    name = body.get("name", "").strip()
    image = body.get("image", "").strip()
    if not image:
        return _err(400, "missing_image", "Container image is required")

    try:
        result = await service.create(
            image=image,
            name=name or None,
            command=body.get("command"),
            environment=body.get("env", {}),
            ports=body.get("ports", {}),
            volumes=body.get("volumes", []),
            network=body.get("network"),
            cpu_limit=body.get("cpu_limit"),
            memory_limit=body.get("memory_limit"),
            labels=body.get("labels", {}),
            restart_policy=body.get("restart_policy", "unless-stopped"),
        )
        return web.json_response(result, status=201)
    except Exception as e:
        log.exception("create_container failed")
        return _err(500, "create_failed", str(e))


async def start_container(request: web.Request) -> web.Response:
    """POST /api/v1/containers/{id}/start — start a container."""
    service = _get_container_service(request)
    container_id = request.match_info["id"]
    try:
        await service.start(container_id)
        return _ok({"id": container_id, "action": "start", "status": "ok"})
    except Exception as e:
        log.exception("start_container failed")
        return _err(500, "start_failed", str(e))


async def stop_container(request: web.Request) -> web.Response:
    """POST /api/v1/containers/{id}/stop — stop a container."""
    service = _get_container_service(request)
    container_id = request.match_info["id"]
    timeout = int(request.query.get("timeout", "30"))
    try:
        await service.stop(container_id, timeout=timeout)
        return _ok({"id": container_id, "action": "stop", "status": "ok"})
    except Exception as e:
        log.exception("stop_container failed")
        return _err(500, "stop_failed", str(e))


async def restart_container(request: web.Request) -> web.Response:
    """POST /api/v1/containers/{id}/restart — restart a container."""
    service = _get_container_service(request)
    container_id = request.match_info["id"]
    timeout = int(request.query.get("timeout", "30"))
    try:
        await service.restart(container_id, timeout=timeout)
        return _ok({"id": container_id, "action": "restart", "status": "ok"})
    except Exception as e:
        log.exception("restart_container failed")
        return _err(500, "restart_failed", str(e))


async def remove_container(request: web.Request) -> web.Response:
    """DELETE /api/v1/containers/{id} — remove a container."""
    service = _get_container_service(request)
    container_id = request.match_info["id"]
    force = request.query.get("force", "false").lower() == "true"
    volumes = request.query.get("volumes", "false").lower() == "true"
    try:
        await service.remove(container_id, force=force, volumes=volumes)
        return _ok({"id": container_id, "action": "remove", "status": "ok"})
    except Exception as e:
        log.exception("remove_container failed")
        return _err(500, "remove_failed", str(e))


async def exec_in_container(request: web.Request) -> web.Response:
    """POST /api/v1/containers/{id}/exec — execute a command inside a container."""
    service = _get_container_service(request)
    container_id = request.match_info["id"]
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")

    command = body.get("command")
    if not command:
        return _err(400, "missing_command")

    try:
        result = await service.exec_command(
            container_id,
            command=command,
            tty=body.get("tty", False),
            environment=body.get("env", {}),
            working_dir=body.get("working_dir"),
        )
        return _ok(result)
    except Exception as e:
        log.exception("exec_in_container failed")
        return _err(500, "exec_failed", str(e))


async def get_container_logs(request: web.Request) -> web.Response:
    """GET /api/v1/containers/{id}/logs — fetch container logs."""
    service = _get_container_service(request)
    container_id = request.match_info["id"]
    tail = int(request.query.get("tail", "100"))
    since = request.query.get("since", "")
    timestamps = request.query.get("timestamps", "false").lower() == "true"
    try:
        logs = await service.logs(
            container_id, tail=tail, since=since or None, timestamps=timestamps
        )
        return _ok({"id": container_id, "logs": logs})
    except Exception as e:
        log.exception("get_container_logs failed")
        return _err(500, "logs_failed", str(e))


async def get_container_stats(request: web.Request) -> web.Response:
    """GET /api/v1/containers/{id}/stats — real-time container stats."""
    service = _get_container_service(request)
    container_id = request.match_info["id"]
    try:
        stats = await service.stats(container_id)
        return _ok(stats)
    except Exception as e:
        log.exception("get_container_stats failed")
        return _err(500, "stats_failed", str(e))


# ── route registration ──────────────────────────────────────────────────────

def setup_routes(app: web.Application) -> None:
    """Register container routes on the aiohttp app."""
    app.router.add_get("/api/v1/containers", list_containers)
    app.router.add_post("/api/v1/containers", create_container)
    app.router.add_get("/api/v1/containers/{id}", get_container)
    app.router.add_post("/api/v1/containers/{id}/start", start_container)
    app.router.add_post("/api/v1/containers/{id}/stop", stop_container)
    app.router.add_post("/api/v1/containers/{id}/restart", restart_container)
    app.router.add_delete("/api/v1/containers/{id}", remove_container)
    app.router.add_post("/api/v1/containers/{id}/exec", exec_in_container)
    app.router.add_get("/api/v1/containers/{id}/logs", get_container_logs)
    app.router.add_get("/api/v1/containers/{id}/stats", get_container_stats)
