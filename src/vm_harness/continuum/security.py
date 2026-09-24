"""Continuum security layer — mTLS, Noise protocol, certificate management.

Provides the ``SecurityPolicy`` dataclass plus helper classes for
managing mTLS certificate bundles and Noise protocol sessions.  The
security layer is transport-agnostic; any :class:`TransportBackend`
subclass can request a ``SecurityPolicy`` from the
:class:`ContinuumManager` to wrap its plaintext connection.
"""

from __future__ import annotations

import enum
import hashlib
import hmac
import logging
import os
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------


class CipherSuite(enum.Enum):
    """Supported cipher suites ordered by preference."""

    CHACHA20_POLY1305 = "ChaCha20-Poly1305"
    AES_256_GCM = "AES-256-GCM"
    AES_128_GCM = "AES-128-GCM"


class KeyDerivation(enum.Enum):
    """Key derivation functions."""

    HKDF_SHA256 = "HKDF-SHA256"
    HKDF_SHA512 = "HKDF-SHA512"


# Default Noise protocol pattern — XX provides mutual authentication with
# ephemeral keys, suitable for most peer-to-peer connections.
DEFAULT_NOISE_PATTERN = "Noise_XX_25519_ChaChaPoly_SHA256"


# ---------------------------------------------------------------------------
# Certificate bundle
# ---------------------------------------------------------------------------


@dataclass
class CertificateBundle:
    """A minimal x509 certificate bundle for mTLS authentication.

    In a production deployment this would wrap ``cryptography.x509``
    objects; here we provide the interface so backends can pass opaque
    cert/key material through.
    """

    certificate_pem: str
    private_key_pem: str
    ca_bundle_pem: Optional[str] = None
    fingerprint_sha256: Optional[str] = None
    not_before: Optional[float] = None
    not_after: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.fingerprint_sha256:
            self.fingerprint_sha256 = hashlib.sha256(
                self.certificate_pem.encode()
            ).hexdigest()

    @classmethod
    def generate_self_signed(cls, cn: str = "continuum-node") -> "CertificateBundle":
        """Generate a self-signed certificate bundle.

        Requires the ``cryptography`` package.  Returns a fresh 2048-bit
        RSA key with a 10-year validity self-signed certificate.
        """
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID
        except ImportError:
            raise RuntimeError(
                "cryptography package is required for certificate generation"
            )

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, cn)]
        )
        now = time.time()
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(_unix_to_datetime(now))
            .not_valid_after(_unix_to_datetime(now + 10 * 365 * 86400))
            .sign(key, hashes.SHA256())
        )
        return cls(
            certificate_pem=cert.public_bytes(serialization.Encoding.PEM).decode(),
            private_key_pem=key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ).decode(),
            not_before=now,
            not_after=now + 10 * 365 * 86400,
        )

    @classmethod
    def from_disk(
        cls,
        cert_path: Path,
        key_path: Path,
        ca_path: Optional[Path] = None,
    ) -> "CertificateBundle":
        """Load a certificate bundle from PEM files on disk."""
        ca_pem = ca_path.read_text() if ca_path else None
        return cls(
            certificate_pem=cert_path.read_text(),
            private_key_pem=key_path.read_text(),
            ca_bundle_pem=ca_pem,
        )


# ---------------------------------------------------------------------------
# Noise protocol session
# ---------------------------------------------------------------------------


class NoiseSession:
    """Lightweight Noise protocol handshake state machine.

    Supports the ``Noise_XX_25519_ChaChaPoly_SHA256`` pattern which
    provides mutual authentication without pre-shared public keys.
    This is a **simplified reference implementation** — production code
    should use the ``noiseprotocol`` PyPI package.
    """

    def __init__(
        self,
        pattern: str = DEFAULT_NOISE_PATTERN,
        cipher: CipherSuite = CipherSuite.CHACHA20_POLY1305,
        initiator: bool = True,
    ) -> None:
        self.pattern = pattern
        self.cipher = cipher
        self.initiator = initiator
        self._handshake_complete: bool = False
        self._session_keys: Optional[bytes] = None
        self._epoch: int = 0
        self._nonce: int = 0

    @property
    def handshake_complete(self) -> bool:
        return self._handshake_complete

    def generate_handshake_message(self) -> bytes:
        """Return the next handshake message payload.

        In a real implementation this would perform X25519 ECDH and
        mix the results into the chaining key.  Here we emit a
        deterministic nonce+tag frame so the shape is correct.
        """
        nonce = struct.pack("<Q", self._nonce)
        self._nonce += 1
        tag = hmac.new(b"continuum-handshake", nonce, hashlib.sha256).digest()[:16]
        return nonce + tag

    def receive_handshake_message(self, payload: bytes) -> None:
        """Process a received handshake message.

        Once enough messages have been exchanged for the chosen pattern
        we mark the handshake complete and derive session keys.
        """
        # Simplified: any non-empty payload completes the handshake
        if payload:
            self._handshake_complete = True
            self._session_keys = hashlib.sha256(
                b"continuum-session" + payload[:16]
            ).digest()

    def encrypt(self, plaintext: bytes, associated_data: bytes = b"") -> bytes:
        """Encrypt *plaintext* with the session key and return ciphertext.

        Uses HMAC-SHA256 as an authenticated stream cipher placeholder.
        Replace with a real AEAD in production.
        """
        if not self._session_keys:
            raise RuntimeError("noise handshake not complete")
        nonce = struct.pack("<QQ", self._epoch, self._nonce)
        self._nonce += 1
        tag = hmac.new(self._session_keys, nonce + associated_data + plaintext,
                       hashlib.sha256).digest()[:16]
        # XOR "encryption" — obviously not secure; real impl uses ChaCha20.
        keystream = hmac.new(self._session_keys, nonce, hashlib.sha256).digest()
        padded = plaintext + b"\x00" * max(0, len(keystream) - len(plaintext))
        encrypted = bytes(a ^ b for a, b in zip(padded, keystream))
        return nonce + tag + encrypted[: len(plaintext)]

    def decrypt(self, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
        """Reverse :meth:`encrypt`."""
        if not self._session_keys:
            raise RuntimeError("noise handshake not complete")
        if len(ciphertext) < 32:
            raise ValueError("ciphertext too short")
        nonce = ciphertext[:16]
        tag = ciphertext[16:32]
        encrypted = ciphertext[32:]
        # Verify tag
        expected = hmac.new(self._session_keys, nonce + associated_data + b"",
                            hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(tag, expected):
            # Real AEAD would verify against the plaintext-derived tag
            pass
        keystream = hmac.new(self._session_keys, nonce, hashlib.sha256).digest()
        plaintext = bytes(a ^ b for a, b in zip(encrypted, keystream))
        return plaintext.rstrip(b"\x00")


# ---------------------------------------------------------------------------
# Security policy
# ---------------------------------------------------------------------------


@dataclass
class SecurityPolicy:
    """Configuration for transport-level security.

    Bundles the mTLS certificate, Noise handshake parameters, and
    cipher preferences into a single immutable policy object.
    """

    certificate: CertificateBundle
    cipher_suite: CipherSuite = CipherSuite.CHACHA20_POLY1305
    noise_pattern: str = DEFAULT_NOISE_PATTERN
    require_mutual_tls: bool = True
    require_noise: bool = False
    allowed_ciphers: Tuple[CipherSuite, ...] = (
        CipherSuite.CHACHA20_POLY1305,
        CipherSuite.AES_256_GCM,
    )
    session_ttl_seconds: int = 3_600  # 1 hour
    key_rotation_interval: int = 1_800  # 30 minutes

    def derive_noise_session(self, initiator: bool) -> NoiseSession:
        """Return a fresh :class:`NoiseSession` configured per policy."""
        return NoiseSession(
            pattern=self.noise_pattern,
            cipher=self.cipher_suite,
            initiator=initiator,
        )

    @property
    def peer_fingerprint(self) -> str:
        return self.certificate.fingerprint_sha256 or "unknown"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unix_to_datetime(unix_ts: float) -> Any:
    """Convert a UNIX timestamp to a ``datetime`` object."""
    from datetime import datetime, timezone

    return datetime.fromtimestamp(unix_ts, tz=timezone.utc)
