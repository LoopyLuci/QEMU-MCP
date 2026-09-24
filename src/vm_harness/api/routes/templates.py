"""
Template management route handlers.

Templates are reusable VM/container definitions that can be instantiated
with variable substitution. Supports versioning, import/export, and
parameterized provisioning.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

log = logging.getLogger("vmharness.api.templates")


def _template_service(request: web.Request) -> Any:
    svc = request.app.get("template_service")
    if svc is None:
        raise web.HTTPInternalServerError(
            text=json.dumps({"error": "template_service_not_configured"})
        )
    return svc


def _ok(data: dict[str, Any] | list[Any]) -> web.Response:
    return web.json_response(data)


def _err(status: int, error: str, detail: str = "") -> web.Response:
    body: dict[str, Any] = {"error": error}
    if detail:
        body["detail"] = detail
    return web.json_response(body, status=status)


# ── template CRUD ───────────────────────────────────────────────────────────

async def list_templates(request: web.Request) -> web.Response:
    """GET /api/v1/templates — list all templates."""
    svc = _template_service(request)
    try:
        category = request.query.get("category", "")
        templates = await svc.list(category=category or None)
        return _ok(templates)
    except Exception as e:
        log.exception("list_templates failed")
        return _err(500, "list_failed", str(e))


async def get_template(request: web.Request) -> web.Response:
    """GET /api/v1/templates/{name} — get a template."""
    svc = _template_service(request)
    name = request.match_info["name"]
    version = request.query.get("version", "")
    try:
        template = await svc.get(name, version=version or None)
        if template is None:
            return _err(404, "not_found", f"Template {name} not found")
        return _ok(template)
    except Exception as e:
        return _err(500, "get_failed", str(e))


async def create_template(request: web.Request) -> web.Response:
    """POST /api/v1/templates — create a new template."""
    svc = _template_service(request)
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
            category=body.get("category", "general"),
            template_type=body.get("type", "vm"),  # vm, container, compose
            definition=body.get("definition", {}),
            parameters=body.get("parameters", []),
            version=body.get("version", "1.0.0"),
        )
        return web.json_response(result, status=201)
    except Exception as e:
        log.exception("create_template failed")
        return _err(500, "create_failed", str(e))


async def update_template(request: web.Request) -> web.Response:
    """PUT /api/v1/templates/{name} — update a template."""
    svc = _template_service(request)
    name = request.match_info["name"]
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    try:
        result = await svc.update(
            name,
            description=body.get("description"),
            definition=body.get("definition"),
            parameters=body.get("parameters"),
            version=body.get("version"),
        )
        return _ok(result)
    except Exception as e:
        return _err(500, "update_failed", str(e))


async def delete_template(request: web.Request) -> web.Response:
    """DELETE /api/v1/templates/{name} — delete a template."""
    svc = _template_service(request)
    name = request.match_info["name"]
    version = request.query.get("version", "")
    try:
        await svc.delete(name, version=version or None)
        return _ok({"name": name, "action": "delete", "status": "ok"})
    except Exception as e:
        return _err(500, "delete_failed", str(e))


# ── template versioning ─────────────────────────────────────────────────────

async def list_template_versions(request: web.Request) -> web.Response:
    """GET /api/v1/templates/{name}/versions — list template versions."""
    svc = _template_service(request)
    name = request.match_info["name"]
    try:
        versions = await svc.list_versions(name)
        return _ok(versions)
    except Exception as e:
        return _err(500, "list_failed", str(e))


async def get_template_version(request: web.Request) -> web.Response:
    """GET /api/v1/templates/{name}/versions/{version} — get specific version."""
    svc = _template_service(request)
    name = request.match_info["name"]
    version = request.match_info["version"]
    try:
        template = await svc.get(name, version=version)
        if template is None:
            return _err(404, "not_found")
        return _ok(template)
    except Exception as e:
        return _err(500, "get_failed", str(e))


# ── template instantiation ──────────────────────────────────────────────────

async def instantiate_template(request: web.Request) -> web.Response:
    """POST /api/v1/templates/{name}/instantiate — create resources from template."""
    svc = _template_service(request)
    name = request.match_info["name"]
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    version = body.get("version", "")
    try:
        result = await svc.instantiate(
            name=name,
            instance_name=body.get("instance_name", ""),
            parameters=body.get("parameters", {}),
            version=version or None,
        )
        return web.json_response(result, status=201)
    except Exception as e:
        log.exception("instantiate_template failed")
        return _err(500, "instantiate_failed", str(e))


# ── template validation ─────────────────────────────────────────────────────

async def validate_template(request: web.Request) -> web.Response:
    """POST /api/v1/templates/validate — validate a template definition."""
    svc = _template_service(request)
    try:
        body = await request.json()
    except Exception:
        return _err(400, "invalid_json")
    definition = body.get("definition", {})
    template_type = body.get("type", "vm")
    try:
        result = await svc.validate(definition, template_type=template_type)
        return _ok(result)
    except Exception as e:
        return _err(500, "validate_failed", str(e))


# ── route registration ──────────────────────────────────────────────────────

def setup_routes(app: web.Application) -> None:
    """Register template routes on the aiohttp app."""
    app.router.add_get("/api/v1/templates", list_templates)
    app.router.add_post("/api/v1/templates", create_template)
    app.router.add_get("/api/v1/templates/{name}", get_template)
    app.router.add_put("/api/v1/templates/{name}", update_template)
    app.router.add_delete("/api/v1/templates/{name}", delete_template)

    app.router.add_get(
        "/api/v1/templates/{name}/versions", list_template_versions
    )
    app.router.add_get(
        "/api/v1/templates/{name}/versions/{version}", get_template_version
    )
    app.router.add_post(
        "/api/v1/templates/{name}/instantiate", instantiate_template
    )
    app.router.add_post("/api/v1/templates/validate", validate_template)
