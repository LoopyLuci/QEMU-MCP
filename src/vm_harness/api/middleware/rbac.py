"""
Role-Based Access Control (RBAC) middleware.

Enforces fine-grained permissions on API routes based on the caller's
roles (resolved by the auth middleware). Uses a declarative permission
model with role inheritance.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

log = logging.getLogger("vmharness.api.rbac")


# ── Permission definitions ──────────────────────────────────────────────────

# Role -> set of permissions mapping
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {
        "vm:read", "container:read", "kubernetes:read",
        "stack:read", "template:read", "metrics:read", "logs:read",
    },
    "operator": {
        "vm:read", "vm:start", "vm:stop", "vm:restart",
        "container:read", "container:start", "container:stop", "container:restart",
        "kubernetes:read", "kubernetes:deploy", "kubernetes:scale",
        "stack:read", "stack:start", "stack:stop",
        "template:read", "template:instantiate",
        "metrics:read", "logs:read",
    },
    "admin": {
        # Full access to all operations
        "vm:*", "container:*", "kubernetes:*", "stack:*",
        "template:*", "federation:*", "security:*",
        "metrics:*", "logs:*", "config:*", "audit:*",
    },
    "auditor": {
        "audit:read", "logs:read", "metrics:read",
        "security:read", "vm:read", "container:read", "kubernetes:read",
    },
}

# Role inheritance: child -> set of parent roles
ROLE_INHERITANCE: dict[str, set[str]] = {
    "operator": {"viewer"},
    "admin": {"viewer", "operator"},
    "auditor": {"viewer"},
}

# Route-level permission overrides (method:path -> required permission)
ROUTE_PERMISSIONS: dict[str, str] = {
    "POST /api/v1/vms/{name}/start": "vm:start",
    "POST /api/v1/vms/{name}/stop": "vm:stop",
    "POST /api/v1/vms/{name}/restart": "vm:restart",
    "POST /api/v1/stacks": "stack:create",
    "DELETE /api/v1/stacks/{name}": "stack:delete",
    "POST /api/v1/federation/members": "federation:join",
    "DELETE /api/v1/federation/members/{name}": "federation:leave",
}


def resolve_permissions(roles: list[str]) -> set[str]:
    """Resolve the full set of permissions for a list of roles."""
    permissions: set[str] = set()
    resolved: set[str] = set()

    def _resolve(role: str) -> None:
        if role in resolved:
            return
        resolved.add(role)
        permissions.update(ROLE_PERMISSIONS.get(role, set()))
        for parent in ROLE_INHERITANCE.get(role, set()):
            _resolve(parent)

    for role in roles:
        _resolve(role)
    return permissions


def has_permission(permission: str, user_permissions: set[str]) -> bool:
    """Check if a permission is satisfied, accounting for wildcards."""
    if permission in user_permissions:
        return True
    # Wildcard: check if any user permission has a matching prefix
    parts = permission.split(":")
    for perm in user_permissions:
        if perm.endswith(":*"):
            prefix = perm[:-2]
            if permission.startswith(prefix + ":"):
                return True
    return False


@web.middleware
async def rbac_middleware(request: web.Request, handler: Any) -> web.StreamResponse:
    """
    RBAC enforcement middleware.

    Runs AFTER auth middleware. Checks that the caller has the required
    permission for the requested route/method. Denies with 403 if insufficient.
    """
    auth_context = request.get("auth_context")
    if auth_context is None:
        # Public route — no RBAC check needed
        return await handler(request)

    user_permissions = set(auth_context.get("permissions", []))
    method = request.method
    path = request.path

    # Try exact route match first
    permission_key = f"{method} {path}"
    required = ROUTE_PERMISSIONS.get(permission_key)

    if required is None:
        # Fall back to a generic permission check based on the path prefix
        path_parts = path.strip("/").split("/")
        if len(path_parts) >= 3:
            resource = path_parts[2]  # /api/v1/{resource}/...
            action = _infer_action(method, path_parts)
            required = f"{resource}:{action}"

    if required and not has_permission(required, user_permissions):
        log.warning(
            "RBAC denied: identity=%s roles=%s required=%s",
            auth_context.get("identity"),
            auth_context.get("roles"),
            required,
        )
        raise web.HTTPForbidden(
            text=json.dumps({
                "error": "insufficient_permissions",
                "required": required,
            }),
            content_type="application/json",
        )

    return await handler(request)


def _infer_action(method: str, path_parts: list[str]) -> str:
    """Map HTTP method + path to a CRUD-style action name."""
    if method == "GET":
        if len(path_parts) > 3 and path_parts[-1] not in (
            "logs", "status", "events", "stats", "metrics"
        ):
            return "read"
        return "read"
    if method == "POST":
        return "create"
    if method == "PUT":
        return "update"
    if method == "PATCH":
        return "patch"
    if method == "DELETE":
        return "delete"
    return "execute"
