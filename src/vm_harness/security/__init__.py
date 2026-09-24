"""
Security package for vm-harness.

Provides credential management, RBAC enforcement, audit logging,
and device pairing functionality.
"""

from vm_harness.security.credentials import CredentialManager, CredentialType, CredentialMetadata
from vm_harness.security.rbac import RBACEnforcer, Permission, AccessDecision
from vm_harness.security.audit import AuditLogger, AuditEventType, AuditEntry
from vm_harness.security.pairing import PairingManager, PairingPayload, compute_machine_id, get_tailscale_info

__all__ = [
    "CredentialManager",
    "CredentialType",
    "CredentialMetadata",
    "RBACEnforcer",
    "Permission",
    "AccessDecision",
    "AuditLogger",
    "AuditEventType",
    "AuditEntry",
    "PairingManager",
    "PairingPayload",
    "compute_machine_id",
    "get_tailscale_info",
]
