"""
Authentication middleware for vm-harness API.

Validates API keys on every protected endpoint. The X-API-Key header
is required unless the route is explicitly whitelisted (e.g., pairing,
public key endpoint, health check).
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from typing import Any

from aiohttp import web

from vm_harness.security.credentials import CredentialManager
from vm_harness.security.rbac import RBACEnforcer

log = logging.getLogger("vmharness.api.auth")

# Paths that skip authentication
_PUBLIC_PATHS: tuple[str, ...] = (
    "/health",
    "/api/v1/auth/pair",
    "/api/v1/auth/public-key",
)


@web.middleware
async def auth_middleware(request: web.Request, handler: Any) -> web.StreamResponse:
    """
    Authentication middleware.

    Validates the X-API-Key header for protected routes. Attaches
    `request["auth_context"]` with the caller's identity, roles, and
    metadata for downstream handlers to use.
    """
    path = request.path

    # Skip auth for public routes
    if any(path.startswith(p) for p in _PUBLIC_PATHS):
        request["auth_context"] = None
        return await handler(request)

    # Extract API key from header
    api_key = request.headers.get("X-API-Key", "").strip()
    if not api_key:
        # Try Bearer token in Authorization header as fallback
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:].strip()

    if not api_key:
        raise web.HTTPUnauthorized(
            text=json.dumps({"error": "missing_api_key"}),
            content_type="application/json",
        )

    # Validate the API key
    credential_mgr = request.app.get("credential_manager")
    if credential_mgr is None:
        log.warning("credential_manager not configured in app context")
        raise web.HTTPInternalServerError(
            text=json.dumps({"error": "auth_service_unavailable"}),
        )

    key_meta = credential_mgr.validate_api_key(api_key)
    if key_meta is None:
        raise web.HTTPForbidden(
            text=json.dumps({"error": "invalid_api_key"}),
            content_type="application/json",
        )

    # Check if the key has expired
    expires = key_meta.get("expires", 0)
    if expires > 0 and expires < int(time.time()):
        raise web.HTTPForbidden(
            text=json.dumps({"error": "api_key_expired"}),
            content_type="application/json",
        )

    # Resolve roles via RBAC enforcer
    rbac = request.app.get("rbac_enforcer")
    roles = rbac.resolve_roles(key_meta) if rbac else ["viewer"]

    # Build auth context
    auth_context = {
        "key_id": key_meta.get("key_id"),
        "identity": key_meta.get("identity", "unknown"),
        "roles": roles,
        "permissions": rbac.resolve_permissions(roles) if rbac else [],
        "source_ip": _get_client_ip(request),
        "machine_id": key_meta.get("machine_id", ""),
        "display_name": key_meta.get("display_name", ""),
        "authenticated_at": int(time.time()),
    }

    request["auth_context"] = auth_context

    try:
        return await handler(request)
    except web.HTTPException as exc:
        exc.content_type = "application/json"
        if not exc.text or not exc.text.startswith("{"):
            exc.text = json.dumps({"error": exc.reason or "http_error"})
        raise


def _get_client_ip(request: web.Request) -> str:
    """Extract client IP, preferring X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    peername = request.transport.get_extra_info("peername")
    if peername:
        return peername[0]
    return "unknown"
