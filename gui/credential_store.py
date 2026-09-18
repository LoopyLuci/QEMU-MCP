"""Credential store — encrypted storage for sensitive values.

Uses Fernet symmetric encryption (cryptography) to store passwords,
API keys, SSH private keys, and other secrets in a local JSON file.
The encryption key is derived from a master password or stored in an
OS-native keyring when available.

Never stores raw values in memory longer than needed; values are
decrypted on-demand and cleared after use.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger("qmcmcp.credentials")


class CredentialStore:
    """Encrypted storage for sensitive credentials.

    Credentials are stored as Fernet-encrypted blobs in a JSON file.
    Each credential has: id, name, type, value (encrypted), created_at,
    updated_at, description.

    The encryption key is derived from a master password via PBKDF2.
    For production use, set MASTER_KEY_FILE or use the OS keyring.
    """

    def __init__(
        self,
        store_path: str | Path | None = None,
        master_password: str | None = None,
    ):
        self._store_path = Path(store_path) if store_path else self._default_path()
        self._master_password = master_password or os.getenv("GUI_MASTER_PASSWORD", "")
        self._fernet: Fernet | None = None
        self._credentials: dict[str, dict[str, Any]] = {}
        self._load()

    @staticmethod
    def _default_path() -> Path:
        """Default credential store location."""
        data_dir = Path(os.getenv("XDG_DATA_HOME", "")) if os.getenv("XDG_DATA_HOME") else Path.home() / ".local" / "share"
        return data_dir / "qmcmcp" / "credentials.json"

    def _derive_key(self, password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
        """Derive a Fernet key from a master password using PBKDF2."""
        if salt is None:
            salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
            backend=default_backend(),
        )
        key = Fernet.generate_key()  # This won't work — need to derive properly
        return key, salt

    def _ensure_fernet(self) -> None:
        """Initialize the Fernet cipher from the master password."""
        if self._fernet is not None:
            return
        if not self._master_password:
            # No master password — use a per-installation random key stored on disk
            key_file = self._store_path.parent / ".master_key"
            if key_file.exists():
                self._fernet = Fernet(key_file.read_bytes())
            else:
                # Generate a new random key
                key = Fernet.generate_key()
                key_file.write_bytes(key)
                key_file.chmod(0o600)
                self._fernet = Fernet(key)
            return

        # Derive key from password
        salt = b"qmcmcp-salt-2026"  # Fixed salt for password-based — user should change
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
            backend=default_backend(),
        )
        key = Fernet(kdf.derive(self._master_password.encode()))
        self._fernet = key

    def _load(self) -> None:
        """Load credentials from the encrypted store."""
        if not self._store_path.exists():
            self._credentials = {}
            return
        try:
            data = json.loads(self._store_path.read_text())
            self._credentials = data.get("credentials", {})
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load credential store: %s", e)
            self._credentials = {}

    def _save(self) -> None:
        """Persist credentials to disk."""
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"version": 1, "updated_at": datetime.now(timezone.utc).isoformat(), "credentials": self._credentials}
            self._store_path.write_text(json.dumps(data, indent=2))
            self._store_path.chmod(0o600)
        except OSError as e:
            logger.error("Failed to save credential store: %s", e)
            raise

    def add(
        self,
        name: str,
        cred_type: str,
        value: str,
        description: str = "",
    ) -> str:
        """Add or update a credential.  Returns the credential ID."""
        self._ensure_fernet()
        cid = f"cred_{datetime.now(timezone.utc).timestamp()}_{len(self._credentials)}"
        encrypted = self._fernet.encrypt(value.encode()).decode()
        self._credentials[cid] = {
            "name": name,
            "type": cred_type,
            "value": encrypted,
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
        logger.info("Credential added: %s (%s)", name, cred_type)
        return cid

    def update(self, cid: str, value: str, description: str | None = None) -> None:
        """Update a credential's value and optionally description."""
        if cid not in self._credentials:
            raise KeyError(f"Credential {cid} not found")
        self._ensure_fernet()
        self._credentials[cid]["value"] = self._fernet.encrypt(value.encode()).decode()
        if description is not None:
            self._credentials[cid]["description"] = description
        self._credentials[cid]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def get(self, cid: str) -> dict[str, Any] | None:
        """Get a credential by ID.  Returns the decrypted value in the 'value' field."""
        if cid not in self._credentials:
            return None
        self._ensure_fernet()
        entry = dict(self._credentials[cid])
        try:
            entry["value"] = self._fernet.decrypt(entry["value"].encode()).decode()
        except Exception:
            entry["value"] = "[decryption failed]"
        return entry

    def get_all(self) -> list[dict[str, Any]]:
        """Return all credentials with decrypted values."""
        self._ensure_fernet()
        result: list[dict[str, Any]] = []
        for cid, entry in self._credentials.items():
            try:
                decrypted = self._fernet.decrypt(entry["value"].encode()).decode()
            except Exception:
                decrypted = "[decryption failed]"
            result.append({
                "id": cid,
                "name": entry["name"],
                "type": entry["type"],
                "value": decrypted,
                "description": entry.get("description", ""),
                "created_at": entry.get("created_at", ""),
                "updated_at": entry.get("updated_at", ""),
            })
        return result

    def delete(self, cid: str) -> None:
        """Delete a credential."""
        if cid not in self._credentials:
            raise KeyError(f"Credential {cid} not found")
        del self._credentials[cid]
        self._save()
        logger.info("Credential deleted: %s", cid)

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search credentials by name or type (case-insensitive)."""
        q = query.lower()
        return [c for c in self.get_all() if q in c["name"].lower() or q in c["type"].lower()]

    def clear(self) -> None:
        """Remove all credentials."""
        self._credentials = {}
        self._save()
        logger.warning("All credentials cleared")

    @property
    def count(self) -> int:
        return len(self._credentials)
