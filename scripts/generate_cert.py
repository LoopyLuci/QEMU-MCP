#!/usr/bin/env python3
"""Generate a self-signed TLS certificate for the VM-Harness headless server.

Creates cert.pem and key.pem in the project root, valid for 365 days.
Uses the cryptography library (already in .venv).
"""
from __future__ import annotations

import datetime
from ipaddress import ip_address
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CERT_FILE = PROJECT_ROOT / "cert.pem"
KEY_FILE = PROJECT_ROOT / "key.pem"

VALID_DAYS = 365
KEY_SIZE = 2048
COMMON_NAME = "localhost"


def generate_self_signed_cert(
    cert_path: Path = CERT_FILE,
    key_path: Path = KEY_FILE,
    valid_days: int = VALID_DAYS,
    common_name: str = COMMON_NAME,
) -> tuple[Path, Path]:
    """Generate a self-signed RSA cert + key pair."""
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=KEY_SIZE,
    )

    now = datetime.datetime.now(datetime.timezone.utc)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=valid_days))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(common_name),
                x509.IPAddress(ip_address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    key_path.chmod(0o600)

    return cert_path, key_path


def main() -> None:
    cert_path, key_path = generate_self_signed_cert()
    print(f"  Certificate: {cert_path}")
    print(f"  Private key: {key_path}")
    print(f"  Valid for:   {VALID_DAYS} days")
    print(f"  CN:          {COMMON_NAME}")
    print(f"  Key size:    {KEY_SIZE}-bit RSA")
    print()


if __name__ == "__main__":
    main()
