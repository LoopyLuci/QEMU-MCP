
"""
Device pairing for vm-harness mobile clients.

Implements the pairing protocol for securely onboarding mobile
devices (Android/iOS) to the vm-harness server. Uses Ed25519
signatures for token verification and Tailscale for secure transport.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import platform
import struct
import subprocess
n# Suppress CLI console windows on Windows
CREATE_NO_WINDOW = 0x08000000
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

log = logging.getLogger("vmharness.security.pairing")

# Constants
PAIRING_TOKEN_VERSION = "v1"
PAIRING_PURPOSE = "mobile-pairing"
PAIRING_TOKEN_TTL_SECONDS = 86400  # 24 hours
TAILSCALE_IPV4_PREFIX = (100, 0, 0, 0)
API_KEY_HEADER = "X-API-Key"


@dataclass(frozen=True)
class PairingPayload:
    """Content of a mobile pairing token — signed by the server's Ed25519 key."""
    version: str = PAIRING_TOKEN_VERSION
    purpose: str = PAIRING_PURPOSE
    host: str = ""
    ip: str = ""
    tailnet: str = ""
    machine_id: str = ""
    display_name: str = ""
    created: int = 0
    expires: int = 0
    secret: str = ""


class PairingManager:
    """
    Manages the device pairing lifecycle.

    Handles token generation, verification, and API key registration
    for mobile clients connecting over Tailscale.
    """

    def __init__(
        self,
        key_dir: Path | str,
        credential_manager: Any = None,
    ) -> None:
        self._key_dir = Path(key_dir)
        self._key_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._credential_manager = credential_manager
        self._signing_key = self._load_or_generate_signing_key()
        self._public_key = self._signing_key.public_key()

    def _load_or_generate_signing_key(self) -> ed25519.Ed25519PrivateKey:
        """Load or generate the Ed25519 signing key."""
        key_file = self._key_dir / ".vmh_signing_key"
        if key_file.exists():
            try:
                raw = key_file.read_bytes()
                private_key = ed25519.Ed25519PrivateKey.from_private_bytes(raw)
                private_key.public_key()  # verify
                return private_key
            except (ValueError, OSError):
                pass

        private_key = ed25519.Ed25519PrivateKey.generate()
        try:
            key_file.write_bytes(private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            ))
            key_file.chmod(0o600)
        except OSError:
            pass
        return private_key

    def get_public_key_bytes(self) -> bytes:
        """Return the Ed25519 public key as raw bytes."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def get_public_key_pem(self) -> str:
        """Return the Ed25519 public key as PEM."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def generate_pairing_token(
        self,
        host: str = "",
        ip: str = "",
        tailnet: str = "",
        machine_id: str = "",
        display_name: str = "",
        ttl_seconds: int = PAIRING_TOKEN_TTL_SECONDS,
    ) -> tuple[str, PairingPayload]:
        """
        Generate a signed pairing token.

        Returns (token_string, payload).
        """
        now = int(time.time())
        secret = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")

        payload = PairingPayload(
            host=host,
            ip=ip,
            tailnet=tailnet,
            machine_id=machine_id,
            display_name=display_name or host,
            created=now,
            expires=now + ttl_seconds if ttl_seconds > 0 else 0,
            secret=secret,
        )

        payload_json = json.dumps({
            "v": payload.version,
            "p": payload.purpose,
            "h": payload.host,
            "i": payload.ip,
            "t": payload.tailnet,
            "m": payload.machine_id,
            "n": payload.display_name,
            "c": payload.created,
            "e": payload.expires,
            "s": payload.secret,
        }, separators=(",", ":"))

        payload_bytes = payload_json.encode("utf-8")
        signature = self._signing_key.sign(payload_bytes)
        sig_b64 = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
        pay_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
        token = f"{sig_b64}.{pay_b64}"

        return token, payload

    def verify_pairing_token(self, token: str) -> PairingPayload | None:
        """Verify a pairing token's signature and validity."""
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return None
            sig = base64.urlsafe_b64decode(parts[0] + "==")
            pay = base64.urlsafe_b64decode(parts[1] + "==")
        except (ValueError, IndexError):
            return None

        try:
            self._public_key.verify(sig, pay)
        except InvalidSignature:
            return None

        try:
            raw = json.loads(pay.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        now = int(time.time())
        payload = PairingPayload(
            version=raw.get("v", ""),
            purpose=raw.get("p", ""),
            host=raw.get("h", ""),
            ip=raw.get("i", ""),
            tailnet=raw.get("t", ""),
            machine_id=raw.get("m", ""),
            display_name=raw.get("n", ""),
            created=raw.get("c", 0),
            expires=raw.get("e", 0),
            secret=raw.get("s", ""),
        )

        # Validate
        if payload.version != PAIRING_TOKEN_VERSION:
            return None
        if payload.purpose != PAIRING_PURPOSE:
            return None
        if not payload.host or "." not in payload.host:
            return None
        if not payload.secret:
            return None
        # Tailscale IP range check
        try:
            ip_parts = [int(x) for x in payload.ip.split(".")]
            if len(ip_parts) != 4 or ip_parts[0] != TAILSCALE_IPV4_PREFIX[0]:
                return None
        except (ValueError, AttributeError):
            return None
        # Expiry
        if payload.expires > 0 and payload.expires < now:
            return None
        # Not created in the future
        if payload.created > now + 60:
            return None

        return payload

    def complete_pairing(
        self,
        token: str,
        source_ip: str = "",
    ) -> dict[str, Any] | None:
        """
        Complete the pairing process.

        Verifies the token, creates an API key, and returns the
        pairing result with credentials.
        """
        payload = self.verify_pairing_token(token)
        if payload is None:
            return None

        # Create API key from the pairing secret
        if self._credential_manager is None:
            return {
                "paired": True,
                "secret": payload.secret,
                "host": payload.host,
                "ip": payload.ip,
                "tailnet": payload.tailnet,
                "machine_id": payload.machine_id,
                "display_name": payload.display_name,
                "created": payload.created,
                "expires": payload.expires,
            }

        key_id, _ = self._credential_manager.create_api_key(
            name=f"pairing-{payload.display_name}",
            roles=["operator"],
            machine_id=payload.machine_id,
            display_name=payload.display_name,
            description=f"Paired device: {payload.display_name}",
        )

        return {
            "paired": True,
            "key_id": key_id,
            "secret": payload.secret,
            "host": payload.host,
            "ip": payload.ip,
            "tailnet": payload.tailnet,
            "machine_id": payload.machine_id,
            "display_name": payload.display_name,
            "created": payload.created,
            "expires": payload.expires,
        }


def compute_machine_id(store_dir: Path | str) -> str:
    """Compute a stable, privacy-hashed machine fingerprint."""
    store_dir = Path(store_dir)
    cache_file = store_dir / ".vmh_machine_id"
    if cache_file.exists():
        return cache_file.read_text().strip()

    parts = [
        platform.node(),
        str(uuid.getnode()),
        platform.machine(),
        platform.system(),
    ]
    raw = "|".join(parts).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:32]
    result = f"sha256:{digest}"
    try:
        cache_file.write_text(result)
    except OSError:
        pass
    return result


def get_tailscale_info() -> dict[str, Any] | None:
    """Detect Tailscale state: IP, MagicDNS suffix, tailnet name."""
    info: dict[str, Any] = {"running": False}

    # Try psutil first
    try:
        import psutil
        for nic, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == 2:  # AF_INET
                    parts = addr.address.split(".")
                    if len(parts) == 4 and int(parts[0]) == TAILSCALE_IPV4_PREFIX[0]:
                        info["ip"] = addr.address
                        info["running"] = True
                        break
    except ImportError:
        pass

    # Try tailscale CLI
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                ips = data.get("TailscaleIPs") or []
                if ips and not info.get("ip"):
                    info["ip"] = ips[0]
                    info["running"] = True
                info["magic_dns"] = data.get("MagicDNSSuffix") or ""
                info["tailnet"] = data.get("Tailnet") or ""
                info["hostname"] = data.get("Hostname") or platform.node()
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass

    if not info.get("running"):
        return None
    return info
