"""Operational security primitives for MOSAIC v1."""

from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


class SecurityError(ValueError):
    pass


class CapabilityVault:
    """Encrypts capability material at rest; plaintext is returned only on explicit use."""

    def __init__(self, master_key: bytes):
        if len(master_key) not in {16, 24, 32}:
            raise SecurityError("master key must be 128, 192 or 256 bits")
        self._aead = AESGCM(master_key)
        self._items: dict[str, tuple[bytes, bytes]] = {}

    def put(self, capability_id: str, secret: bytes, *, associated_data: bytes = b"") -> None:
        nonce = secrets.token_bytes(12)
        ciphertext = self._aead.encrypt(nonce, secret, associated_data)
        self._items[capability_id] = (nonce, ciphertext)

    def get(self, capability_id: str, *, associated_data: bytes = b"") -> bytes:
        try:
            nonce, ciphertext = self._items[capability_id]
        except KeyError as exc:
            raise SecurityError("unknown capability") from exc
        try:
            return self._aead.decrypt(nonce, ciphertext, associated_data)
        except Exception as exc:
            raise SecurityError("capability authentication failed") from exc

    def consume(self, capability_id: str, *, associated_data: bytes = b"") -> bytes:
        secret = self.get(capability_id, associated_data=associated_data)
        del self._items[capability_id]
        return secret


@dataclass
class ReplayGuard:
    max_entries: int = 100_000
    ttl_seconds: float = 300.0

    def __post_init__(self) -> None:
        self._seen: OrderedDict[str, float] = OrderedDict()

    def accept(self, message_id: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        expired = [key for key, timestamp in self._seen.items() if now - timestamp > self.ttl_seconds]
        for key in expired:
            self._seen.pop(key, None)
        if message_id in self._seen:
            return False
        self._seen[message_id] = now
        self._seen.move_to_end(message_id)
        while len(self._seen) > self.max_entries:
            self._seen.popitem(last=False)
        return True


@dataclass
class TokenBucket:
    capacity: float
    refill_per_second: float

    def __post_init__(self) -> None:
        if self.capacity <= 0 or self.refill_per_second <= 0:
            raise SecurityError("bucket parameters must be positive")
        self.tokens = self.capacity
        self.updated_at = time.monotonic()

    def allow(self, amount: float = 1.0, now: float | None = None) -> bool:
        if amount <= 0:
            raise SecurityError("amount must be positive")
        now = time.monotonic() if now is None else now
        elapsed = max(0.0, now - self.updated_at)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.updated_at = now
        if self.tokens < amount:
            return False
        self.tokens -= amount
        return True


def derive_node_key(master_key: bytes, node_id: str, epoch: int) -> bytes:
    if len(master_key) < 16:
        raise SecurityError("master key too short")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=f"MOSAIC/NODE/{node_id}/{epoch}".encode("utf-8"),
    ).derive(master_key)
