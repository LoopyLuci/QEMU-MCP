"""
Real-time streaming route handlers via WebSocket and Server-Sent Events.

Provides channels for VM console (QMP), SSH terminal, container exec,
log tailing, metrics streaming, and event notifications. Uses aiohttp
WebSocket support with automatic reconnection and heartbeat.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import aiohttp
from aiohttp import web

log = logging.getLogger("vmharness.api.streaming")


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_stream_service(request: web.Request) -> Any:
    svc = request.app.get("stream_service")
    if svc is None:
        raise web.HTTPInternalServerError(
            text=json.dumps({"error": "stream_service_not_configured"})
        )
    return svc


# ── VM console (QMP over WebSocket) ─────────────────────────────────────────

async def stream_vm_console(request: web.Request) -> web.WebSocketResponse:
    """GET /api/v1/vms/{name}/console — WebSocket QMP console."""
    vm_name = request.match_info["name"]
    service = _get_stream_service(request)

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    # Authenticate first message
    authenticated = False
    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "auth":
                key = data.get("key", "")
                registry = request.app.get("api_key_registry")
                if registry and registry.authenticate(key):
                    authenticated = True
                    await ws.send_json({"type": "auth_ok"})
                else:
                    await ws.send_json({"type": "error", "data": "unauthorized"})
                    await ws.close()
                    return ws
            if authenticated and data.get("type") == "command":
                command = data.get("command", "")
                try:
                    result = service.vm_console_command(vm_name, command)
                    await ws.send_json({"type": "response", "data": result})
                except Exception as e:
                    await ws.send_json({"type": "error", "data": str(e)})
        elif msg.type == aiohttp.WSMsgType.ERROR:
            break

    return ws


# ── SSH terminal (WebSocket) ────────────────────────────────────────────────

async def stream_ssh_terminal(request: web.Request) -> web.WebSocketResponse:
    """GET /api/v1/vms/{name}/terminal — WebSocket SSH terminal."""
    vm_name = request.match_info["name"]
    service = _get_stream_service(request)

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    authenticated = False
    session_id: str | None = None

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
            except json.JSONDecodeError:
                continue
            if not authenticated:
                if data.get("type") == "auth":
                    key = data.get("key", "")
                    registry = request.app.get("api_key_registry")
                    if registry and registry.authenticate(key):
                        authenticated = True
                        session_id = service.create_terminal_session(vm_name)
                        await ws.send_json({"type": "auth_ok", "session": session_id})
                    else:
                        await ws.send_json({"type": "error", "data": "unauthorized"})
                        await ws.close()
                        return ws
                continue
            if authenticated:
                msg_type = data.get("type", "")
                if msg_type == "stdin":
                    text = data.get("data", "")
                    service.send_terminal_input(session_id, text)
                elif msg_type == "resize":
                    cols = data.get("cols", 80)
                    rows = data.get("rows", 24)
                    service.resize_terminal(session_id, cols, rows)
                elif msg_type == "command":
                    cmd = data.get("command", "")
                    result = service.run_terminal_command(session_id, cmd)
                    await ws.send_json({"type": "command_result", "data": result})
        elif msg.type == aiohttp.WSMsgType.ERROR:
            break

    if session_id:
        service.close_terminal_session(session_id)
    return ws


# ── Container exec (WebSocket) ──────────────────────────────────────────────

async def stream_container_exec(request: web.Request) -> web.WebSocketResponse:
    """GET /api/v1/containers/{id}/exec-ws — WebSocket container exec."""
    container_id = request.match_info["id"]
    service = _get_stream_service(request)

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    try:
        await service.stream_container_exec(container_id, ws)
    except Exception as e:
        log.exception("container exec stream failed for %s", container_id)

    return ws


# ── Log tailing (Server-Sent Events) ────────────────────────────────────────

async def stream_logs(request: web.Request) -> web.Response:
    """GET /api/v1/logs/stream — Server-Sent Events log stream."""
    service = _get_stream_service(request)
    source = request.query.get("source", "app")
    tail = int(request.query.get("tail", "0"))
    follow = request.query.get("follow", "true").lower() == "true"
    filter_pattern = request.query.get("filter", "")

    response = web.StreamResponse()
    response.content_type = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    await response.prepare(request)

    async for line in service.tail_logs(
        source=source, tail=follow, filter=filter_pattern
    ):
        event_data = json.dumps(line)
        await response.write(f"data: {event_data}\n\n".encode())

    return response


# ── Metrics streaming (SSE) ─────────────────────────────────────────────────

async def stream_metrics(request: web.Request) -> web.Response:
    """GET /api/v1/metrics/stream — Server-Sent Events metrics."""
    service = _get_stream_service(request)
    interval = float(request.query.get("interval", "5.0"))
    metrics_type = request.query.get("type", "all")  # all, cpu, mem, disk, net

    response = web.StreamResponse()
    response.content_type = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    await response.prepare(request)

    try:
        async for snapshot in service.stream_metrics(
            interval=interval, metrics_type=metrics_type
        ):
            event_data = json.dumps(snapshot)
            await response.write(f"data: {event_data}\n\n".encode())
    except asyncio.CancelledError:
        pass

    return response


# ── Events stream (SSE) ────────────────────────────────────────────────────

async def stream_events(request: web.Request) -> web.Response:
    """GET /api/v1/events/stream — Server-Sent Events for system events."""
    service = _get_stream_service(request)
    event_types = request.query.get("types", "").split(",")
    event_types = [e.strip() for e in event_types if e.strip()]

    response = web.StreamResponse()
    response.content_type = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    await response.prepare(request)

    try:
        async for event in service.stream_events(filter_types=event_types or None):
            event_data = json.dumps(event)
            await response.write(
                f"event: {event.get('type', 'message')}\n"
                f"data: {event_data}\n\n".encode()
            )
    except asyncio.CancelledError:
        pass

    return response


# ── Kubernetes pod log tailing (SSE) ────────────────────────────────────────

async def stream_pod_logs(request: web.Request) -> web.Response:
    """GET /api/v1/kubernetes/pods/{name}/logs/stream — SSE pod logs."""
    service = _get_stream_service(request)
    pod_name = request.match_info["name"]
    namespace = request.query.get("namespace", "default")
    cluster = request.query.get("cluster", "")
    container = request.query.get("container", "")

    response = web.StreamResponse()
    response.content_type = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    await response.prepare(request)

    try:
        async for line in service.stream_k8s_logs(
            pod_name, namespace=namespace, cluster=cluster, container=container
        ):
            event_data = json.dumps(line)
            await response.write(f"data: {event_data}\n\n".encode())
    except asyncio.CancelledError:
        pass

    return response


# ── route registration ──────────────────────────────────────────────────────

def setup_routes(app: web.Application) -> None:
    """Register streaming routes on the aiohttp app."""
    app.router.add_get("/api/v1/vms/{name}/console", stream_vm_console)
    app.router.add_get("/api/v1/vms/{name}/terminal", stream_ssh_terminal)
    app.router.add_get("/api/v1/containers/{id}/exec-ws", stream_container_exec)
    app.router.add_get("/api/v1/logs/stream", stream_logs)
    app.router.add_get("/api/v1/metrics/stream", stream_metrics)
    app.router.add_get("/api/v1/events/stream", stream_events)
    app.router.add_get(
        "/api/v1/kubernetes/pods/{name}/logs/stream", stream_pod_logs
    )
