"""
Credential management for vm-harness.

Handles API key generation, validation, rotation, and revocation.
Uses Fernet encryption for stored secrets with PBKDF2 key derivation.
Supports multiple credential types: API keys, SSH keys, TLS certs.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

log = logging.getLogger("vmharness.security.credentials")


class CredentialType(str, Enum):
    API_KEY = "api_key"
    SSH_KEY = "ssh_key"
    TLS_CERT = "tls_cert"
    PAIRING_TOKEN = "pairing_token"


@dataclass
class CredentialMetadata:
    """Metadata for a stored credential."""
    id: str
    name: str
    type: CredentialType
    created: datetime
    expires: datetime | None = None
    last_used: datetime | None = None
    description: str = ""
    roles: list[str] = field(default_factory=lambda: ["viewer"])
    machine_id: str = ""
    display_name: str = ""
    revoked: bool = False


class CredentialManager:
    """
    Manages credentials with Fernet encryption at rest.

    Three-layer security:
      1. Master key derived from a passphrase via PBKDF2
      2. Fernet encryption for stored secrets
      3. In-memory only plaintext (never persisted)
    """

    def __init__(
        self,
        store_dir: Path | str,
        master_passphrase: str | None = None,
    ) -> None:
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Derive master key
        self._fernet = self._init_encryption(master_passphrase or self._get_default_passphrase())

        # In-memory credential cache (id -> secret)
        self._cache: dict[str, str] = {}
        self._metadata: dict[str, CredentialMetadata] = {}

        # Load existing credentials
        self._load_all()

    def _get_default_passphrase(self) -> str:
        """Get passphrase from environment or generate one."""
        passphrase = os.getenv("VMH_MASTER_PASSPHRASE")
        if passphrase:
            return passphrase
        # Generate and cache a passphrase
        pp_file = self._store_dir / ".vmh_passphrase"
        if pp_file.exists():
            return pp_file.read_text().strip()
        pp = secrets.token_hex(32)
        try:
            pp_file.write_text(pp)
            pp_file.chmod(0o600)
        except OSError:
            pass
        return pp

    def _init_encryption(self, passphrase: str) -> Fernet:
        """Initialize Fernet encryption with a passphrase-derived key."""
        salt_file = self._store_dir / ".vmh_salt"
        if salt_file.exists():
            salt = salt_file.read_bytes()
        else:
            salt = os.urandom(16)
            try:
                salt_file.write_bytes(salt)
                salt_file.chmod(0o600)
            except OSError:
                pass

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))
        return Fernet(key)

    def _load_all(self) -> None:
        """Load all credentials from disk."""
        meta_file = self._store_dir / "credentials.json"
        if not meta_file.exists():
            return
        try:
            data = json.loads(meta_file.read_text())
            for item in data:
                meta = CredentialMetadata(
                    id=item["id"],
                    name=item["name"],
                    type=CredentialType(item["type"]),
                    created=datetime.fromisoformat(item["created"]),
                    expires=datetime.fromisoformat(item["expires"]) if item.get("expires") else None,
                    last_used=datetime.fromisoformat(item["last_used"]) if item.get("last_used") else None,
                    description=item.get("description", ""),
                    roles=item.get("roles", ["viewer"]),
                    machine_id=item.get("machine_id", ""),
                    display_name=item.get("display_name", ""),
                    revoked=item.get("revoked", False),
                )
                self._metadata[meta.id] = meta
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            log.error("Failed to load credentials: %s", e)

    def _save_all(self) -> None:
        """Persist credential metadata to disk."""
        meta_file = self._store_dir / "credentials.json"
        data = []
        for meta in self._metadata.values():
            data.append({
                "id": meta.id,
                "name": meta.name,
                "type": meta.type.value,
                "created": meta.created.isoformat(),
                "expires": meta.expires.isoformat() if meta.expires else None,
                "last_used": meta.last_used.isoformat() if meta.last_used else None,
                "description": meta.description,
                "roles": meta.roles,
                "machine_id": meta.machine_id,
                "display_name": meta.display_name,
                "revoked": meta.revoked,
            })
        try:
            meta_file.write_text(json.dumps(data, indent=2))
            meta_file.chmod(0o600)
        except OSError as e:
            log.error("Failed to save credentials: %s", e)

    def _save_secret(self, cred_id: str, secret: str) -> None:
        """Encrypt and save a secret to disk."""
        encrypted = self._fernet.encrypt(secret.encode("utf-8"))
        secret_file = self._store_dir / f"{cred_id}.enc"
        try:
            secret_file.write_bytes(encrypted)
            secret_file.chmod(0o600)
        except OSError as e:
            log.error("Failed to save secret for %s: %s", cred_id, e)

    def _load_secret(self, cred_id: str) -> str | None:
        """Load and decrypt a secret from disk."""
        secret_file = self._store_dir / f"{cred_id}.enc"
        if not secret_file.exists():
            return None
        try:
            encrypted = secret_file.read_bytes()
            return self._fernet.decrypt(encrypted).decode("utf-8")
        except (OSError, InvalidToken) as e:
            log.error("Failed to load secret for %s: %s", cred_id, e)
            return None

    # ── API key operations ────────────────────────────────────────────────

    def create_api_key(
        self,
        name: str,
        roles: list[str] | None = None,
        ttl_hours: int | None = None,
        machine_id: str = "",
        display_name: str = "",
        description: str = "",
    ) -> tuple[str, str]:
        """
        Create a new API key.

        Returns (key_id, secret). The secret is shown once at creation.
        """
        key_id = secrets.token_hex(16)
        secret = secrets.token_urlsafe(48)

        now = datetime.utcnow()
        expires = None
        if ttl_hours and ttl_hours > 0:
            expires = now + timedelta(hours=ttl_hours)

        meta = CredentialMetadata(
            id=key_id,
            name=name,
            type=CredentialType.API_KEY,
            created=now,
            expires=expires,
            description=description,
            roles=roles or ["viewer"],
            machine_id=machine_id,
            display_name=display_name,
        )

        self._metadata[key_id] = meta
        self._cache[key_id] = secret
        self._save_secret(key_id, secret)
        self._save_all()

        log.info("Created API key: %s (%s)", name, key_id)
        return key_id, secret

    def validate_api_key(self, secret: str) -> dict[str, Any] | None:
        """
        Validate an API key secret.

        Returns metadata dict if valid, None otherwise.
        Uses constant-time comparison to prevent timing attacks.
        """
        # Hash the provided secret for lookup
        for key_id, stored_secret in self._cache.items():
            if hmac.compare_digest(secret, stored_secret):
                meta = self._metadata.get(key_id)
                if meta is None or meta.revoked:
                    return None
                if meta.expires and meta.expires < datetime.utcnow():
                    return None
                # Update last_used
                meta.last_used = datetime.utcnow()
                return {
                    "key_id": meta.id,
                    "name": meta.name,
                    "identity": meta.name,
                    "roles": meta.roles,
                    "machine_id": meta.machine_id,
                    "display_name": meta.display_name,
                    "expires": int(meta.expires.timestamp()) if meta.expires else 0,
                }

        # Try loading from disk (not in cache)
        for key_id in list(self._metadata.keys()):
            if key_id in self._cache:
                continue
            stored = self._load_secret(key_id)
            if stored is not None:
                self._cache[key_id] = stored
                if hmac.compare_digest(secret, stored):
                    meta = self._metadata[key_id]
                    if meta.revoked:
                        return None
                    if meta.expires and meta.expires < datetime.utcnow():
                        return None
                    meta.last_used = datetime.utcnow()
                    return {
                        "key_id": meta.id,
                        "name": meta.name,
                        "identity": meta.name,
                        "roles": meta.roles,
                        "machine_id": meta.machine_id,
                        "display_name": meta.display_name,
                        "expires": int(meta.expires.timestamp()) if meta.expires else 0,
                    }

        return None

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key by ID."""
        meta = self._metadata.get(key_id)
        if meta is None:
            return False
        meta.revoked = True
        self._cache.pop(key_id, None)
        # Delete the encrypted secret
        secret_file = self._store_dir / f"{key_id}.enc"
        try:
            secret_file.unlink(missing_ok=True)
        except OSError:
            pass
        self._save_all()
        log.info("Revoked API key: %s", key_id)
        return True

    def rotate_api_key(self, key_id: str) -> str | None:
        """Rotate an API key. Returns the new secret."""
        meta = self._metadata.get(key_id)
        if meta is None:
            return None
        new_secret = secrets.token_urlsafe(48)
        self._cache[key_id] = new_secret
        self._save_secret(key_id, new_secret)
        self._save_all()
        log.info("Rotated API key: %s", key_id)
        return new_secret

    def list_credentials(self) -> list[dict[str, Any]]:
        """List all credentials (secrets masked)."""
        result = []
        for meta in self._metadata.values():
            result.append({
                "id": meta.id,
                "name": meta.name,
                "type": meta.type.value,
                "created": meta.created.isoformat(),
                "expires": meta.expires.isoformat() if meta.expires else None,
                "last_used": meta.last_used.isoformat() if meta.last_used else None,
                "roles": meta.roles,
                "machine_id": meta.machine_id,
                "display_name": meta.display_name,
                "revoked": meta.revoked,
            })
        return result

    # ── SSH key operations ─────────────────────────────────────────────────

    def store_ssh_key(self, name: str, private_key: str, public_key: str = "") -> str:
        """Store an SSH key pair."""
        key_id = secrets.token_hex(16)
        meta = CredentialMetadata(
            id=key_id,
            name=name,
            type=CredentialType.SSH_KEY,
            created=datetime.utcnow(),
        )
        self._metadata[key_id] = meta
        # Store as JSON
        secret_data = json.dumps({"private": private_key, "public": public_key})
        self._save_secret(key_id, secret_data)
        self._save_all()
        return key_id

    def get_ssh_key(self, key_id: str) -> dict[str, str] | None:
        """Retrieve an SSH key pair."""
        meta = self._metadata.get(key_id)
        if meta is None or meta.type != CredentialType.SSH_KEY:
            return None
        data = self._load_secret(key_id)
        if data is None:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None
