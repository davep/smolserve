"""Self-signed TLS certificate generator for local Gemini server testing.

This module provides helper utilities to automatically generate temporary or
persistent self-signed X.509 certificates and private RSA keys when user-supplied
certificates are not specified.
"""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def generate_self_signed_cert(
    cert_path: Path,
    key_path: Path,
    hostname: str = "localhost",
    days_valid: int = 365,
) -> None:
    """Generate a self-signed RSA TLS certificate and private key.

    Args:
        cert_path: Path where the output PEM certificate file should be written.
        key_path: Path where the output PEM private key file should be written.
        hostname: Subject Common Name and Subject Alternative Name for the cert.
        days_valid: Number of days before the generated certificate expires.
    """
    # Ensure parent directories exist
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Subject and Issuer are the same for self-signed certificates
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "smolserve dev"),
        ]
    )

    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=days_valid))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName(hostname), x509.DNSName("127.0.0.1")]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Write private key PEM
    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    os.chmod(key_path, 0o600)

    # Write certificate PEM
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


def ensure_certificate(
    cert_file: Path | None,
    key_file: Path | None,
    default_dir: Path,
    hostname: str = "localhost",
) -> tuple[Path, Path]:
    """Ensure valid certificate and key files exist, generating defaults if necessary.

    Args:
        cert_file: Optional explicit path to certificate file.
        key_file: Optional explicit path to private key file.
        default_dir: Directory where default self-signed certificates are generated.
        hostname: Hostname for self-signed certificate subject.

    Returns:
        A tuple of (cert_path, key_path) guaranteed to exist on disk.
    """
    if cert_file and key_file and cert_file.exists() and key_file.exists():
        return cert_file, key_file

    # Default cert/key paths
    default_cert = default_dir / "smolserve_cert.pem"
    default_key = default_dir / "smolserve_key.pem"

    if not default_cert.exists() or not default_key.exists():
        generate_self_signed_cert(default_cert, default_key, hostname=hostname)

    return default_cert, default_key
