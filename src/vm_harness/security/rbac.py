"""
Role-Based Access Control (RBAC) enforcement for vm-harness.

Defines roles, permissions, and policy enforcement. Works with the
RBAC middleware to authorize API requests. Supports role inheritance,
resource-level permissions, and audit logging of access decisions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("vmharness.security.rbac")


class Permission(str, Enum):
    """All defined permissions in the system."""
    # VM permissions
    VM_READ = "vm:read"
    VM_CREATE = "vm:create"
    VM_DELETE = "vm:delete"
    VM_START = "vm:start"
    VM_STOP = "vm:stop"
    VM_RESTART = "vm:restart"
    VM_EXEC = "vm:exec"
    VM_CONSOLE = "vm:console"

    # Container permissions
    CONTAINER_READ = "container:read"
    CONTAINER_CREATE = "container:create"
    CONTAINER_DELETE = "container:delete"
    CONTAINER_START = "container:start"
    CONTAINER_STOP = "container:stop"
    CONTAINER_RESTART = "container:restart"
    CONTAINER_EXEC = "container:exec"

    # Kubernetes permissions
    KUBERNETES_READ = "kubernetes:read"
    KUBERNETES_CREATE = "kubernetes:create"
    KUBERNETES_DELETE = "kubernetes:delete"
    KUBERNETES_DEPLOY = "kubernetes:deploy"
    KUBERNETES_SCALE = "kubernetes:scale"

    # Stack permissions
    STACK_READ = "stack:read"
    STACK_CREATE = "stack:create"
    STACK_DELETE = "stack:delete"
    STACK_START = "stack:start"
    STACK_STOP = "stack:stop"
    STACK_UPDATE = "stack:update"

    # Template permissions
    TEMPLATE_READ = "template:read"
    TEMPLATE_CREATE = "template:create"
    TEMPLATE_DELETE = "template:delete"
    TEMPLATE_INSTANTIATE = "template:instantiate"

    # Federation permissions
    FEDERATION_READ = "federation:read"
    FEDERATION_JOIN = "federation:join"
    FEDERATION_LEAVE = "federation:leave"
    FEDERATION_EXPOSE = "federation:expose"

    # Security permissions
    SECURITY_READ = "security:read"
    SECURITY_WRITE = "security:write"
    AUDIT_READ = "audit:read"

    # Config permissions
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"

    # Metrics & logs
    METRICS_READ = "metrics:read"
    LOGS_READ = "logs:read"


# ── Role definitions ────────────────────────────────────────────────────────

ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "viewer": {
        Permission.VM_READ, Permission.CONTAINER_READ,
        Permission.KUBERNETES_READ, Permission.STACK_READ,
        Permission.TEMPLATE_READ, Permission.FEDERATION_READ,
        Permission.METRICS_READ, Permission.LOGS_READ,
        Permission.SECURITY_READ,
    },
    "operator": {
        Permission.VM_READ, Permission.VM_START, Permission.VM_STOP,
        Permission.VM_RESTART, Permission.VM_EXEC, Permission.VM_CONSOLE,
        Permission.CONTAINER_READ, Permission.CONTAINER_START,
        Permission.CONTAINER_STOP, Permission.CONTAINER_RESTART,
        Permission.CONTAINER_EXEC,
        Permission.KUBERNETES_READ, Permission.KUBERNETES_DEPLOY,
        Permission.KUBERNETES_SCALE,
        Permission.STACK_READ, Permission.STACK_START, Permission.STACK_STOP,
        Permission.TEMPLATE_READ, Permission.TEMPLATE_INSTANTIATE,
        Permission.FEDERATION_READ,
        Permission.METRICS_READ, Permission.LOGS_READ,
    },
    "admin": set(Permission),  # all permissions
    "auditor": {
        Permission.AUDIT_READ, Permission.LOGS_READ, Permission.METRICS_READ,
        Permission.SECURITY_READ, Permission.VM_READ, Permission.CONTAINER_READ,
        Permission.KUBERNETES_READ, Permission.STACK_READ, Permission.TEMPLATE_READ,
    },
}

# Role inheritance
ROLE_INHERITANCE: dict[str, set[str]] = {
    "operator": {"viewer"},
    "admin": {"viewer", "operator"},
    "auditor": {"viewer"},
}


@dataclass
class AccessDecision:
    """Result of an access control decision."""
    allowed: bool
    permission: Permission | None = None
    roles: list[str] = field(default_factory=list)
    reason: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            import time
            self.timestamp = time.time()


class RBACEnforcer:
    """
    Enforces RBAC policies for API requests.

    Resolves roles to permissions and checks whether a caller
    has the required permission for a given resource/action.
    """

    def __init__(self) -> None:
        self._role_cache: dict[str, set[Permission]] = {}

    def resolve_roles(self, key_meta: dict[str, Any]) -> list[str]:
        """Resolve the effective roles for a credential."""
        return key_meta.get("roles", ["viewer"])

    def resolve_permissions(self, roles: list[str]) -> list[str]:
        """Resolve the full set of permissions for a list of roles."""
        permissions = self._resolve_permissions_set(roles)
        return [p.value for p in permissions]

    def _resolve_permissions_set(self, roles: list[str]) -> set[Permission]:
        """Resolve permissions as a set, with caching."""
        cache_key = ",".join(sorted(roles))
        if cache_key in self._role_cache:
            return self._role_cache[cache_key]

        permissions: set[Permission] = set()
        visited: set[str] = set()

        def _resolve(role: str) -> None:
            if role in visited:
                return
            visited.add(role)
            permissions.update(ROLE_PERMISSIONS.get(role, set()))
            for parent in ROLE_INHERITANCE.get(role, set()):
                _resolve(parent)

        for role in roles:
            _resolve(role)

        self._role_cache[cache_key] = permissions
        return permissions

    def check_permission(
        self,
        roles: list[str],
        required: Permission | str,
        resource: str = "",
    ) -> AccessDecision:
        """
        Check if the given roles have the required permission.

        Args:
            roles: List of role names assigned to the caller.
            required: The permission to check (Permission enum or string).
            resource: Optional resource identifier for audit logging.

        Returns:
            AccessDecision with the result.
        """
        if isinstance(required, str):
            try:
                required = Permission(required)
            except ValueError:
                return AccessDecision(
                    allowed=False,
                    permission=None,
                    roles=roles,
                    reason=f"Unknown permission: {required}",
                )

        permissions = self._resolve_permissions_set(roles)

        # Check direct permission
        if required in permissions:
            return AccessDecision(
                allowed=True,
                permission=required,
                roles=roles,
                reason="Direct permission match",
            )

        # Check wildcard (admin has all)
        if set(Permission).issubset(permissions):
            return AccessDecision(
                allowed=True,
                permission=required,
                roles=roles,
                reason="Wildcard (admin) permission",
            )

        return AccessDecision(
            allowed=False,
            permission=required,
            roles=roles,
            reason=f"Permission {required.value} not in roles",
        )

    def check_any_permission(
        self,
        roles: list[str],
        required: list[Permission | str],
    ) -> AccessDecision:
        """Check if any of the required permissions are satisfied."""
        for perm in required:
            decision = self.check_permission(roles, perm)
            if decision.allowed:
                return decision
        return AccessDecision(
            allowed=False,
            roles=roles,
            reason=f"None of the required permissions satisfied",
        )

    def check_all_permissions(
        self,
        roles: list[str],
        required: list[Permission | str],
    ) -> AccessDecision:
        """Check if all of the required permissions are satisfied."""
        for perm in required:
            decision = self.check_permission(roles, perm)
            if not decision.allowed:
                return decision
        return AccessDecision(
            allowed=True,
            roles=roles,
            reason="All required permissions satisfied",
        )
