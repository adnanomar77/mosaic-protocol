"""Cryptographic primitives for the CCD/NEXUS prototype.

This module intentionally keeps the protocol-facing API small: canonical
encoding, SHA-256 digests, and Ed25519 signatures.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def canonical_bytes(value: Any) -> bytes:
    """Encode JSON-compatible values deterministically."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    """Return a stable SHA-256 hex digest for a JSON-compatible value."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def identity_from_public_key(public_key: bytes) -> str:
    """Derive a compact validator/client identity from a public key."""
    return hashlib.sha256(public_key).hexdigest()[:32]


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def unb64(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


@dataclass
class KeyPair:
    """Ed25519 keypair used by a simulated client or validator."""

    private_key: Ed25519PrivateKey

    @classmethod
    def generate(cls) -> "KeyPair":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_private_bytes(cls, value: bytes) -> "KeyPair":
        return cls(Ed25519PrivateKey.from_private_bytes(value))

    @property
    def private_bytes(self) -> bytes:
        return self.private_key.private_bytes(
            Encoding.Raw,
            PrivateFormat.Raw,
            NoEncryption(),
        )

    @property
    def public_key(self) -> bytes:
        return self.private_key.public_key().public_bytes(
            Encoding.Raw,
            PublicFormat.Raw,
        )

    @property
    def identity(self) -> str:
        return identity_from_public_key(self.public_key)

    def sign(self, message: bytes) -> bytes:
        return self.private_key.sign(message)

    @staticmethod
    def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
            return True
        except Exception:
            return False
