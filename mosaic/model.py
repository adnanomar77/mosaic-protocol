"""Reference state/certificate model for MOSAIC v0.1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ccd_nexus.crypto import KeyPair, canonical_bytes, digest


class MosaicError(ValueError):
    """Base error for invalid MOSAIC state or certificates."""


class CapsuleInvalid(MosaicError):
    """Raised when a capsule fails local validation."""


class ClosureInvalid(MosaicError):
    """Raised when a closure proof is invalid or insufficient."""


@dataclass(frozen=True)
class Member:
    member_id: str
    keypair: KeyPair | None
    weight: int = 1
    public_key_override: bytes | None = None

    @property
    def public_key(self) -> bytes:
        if self.keypair is not None:
            return self.keypair.public_key
        if self.public_key_override is not None:
            return self.public_key_override
        raise MosaicError("member has no public key")


@dataclass(frozen=True)
class StateSeal:
    resource_id: str
    epoch: int
    version: int
    state_root: str
    capability_hash: str
    owner: str

    @property
    def seal_id(self) -> str:
        return digest(
            {
                "resource_id": self.resource_id,
                "epoch": self.epoch,
                "version": self.version,
                "state_root": self.state_root,
                "capability_hash": self.capability_hash,
                "owner": self.owner,
            }
        )


@dataclass(frozen=True)
class Capsule:
    capsule_id: str
    predecessor_id: str
    successor_root: str
    rule_id: str
    rule_witness: str
    bundle_id: str | None
    attempt: int
    epoch: int
    client_id: str
    client_public_key: bytes
    client_signature: bytes

    @classmethod
    def create(
        cls,
        *,
        client: KeyPair,
        predecessor: StateSeal,
        successor_root: str,
        rule_id: str,
        rule_witness: str,
        attempt: int = 0,
        bundle_id: str | None = None,
    ) -> "Capsule":
        unsigned = {
            "protocol": "MOSAIC/CAPSULE/v0.1",
            "predecessor_id": predecessor.seal_id,
            "successor_root": successor_root,
            "rule_id": rule_id,
            "rule_witness": rule_witness,
            "bundle_id": bundle_id,
            "attempt": attempt,
            "epoch": predecessor.epoch,
            "client_id": client.identity,
            "client_public_key": client.public_key.hex(),
        }
        capsule_id = digest(unsigned)
        signature = client.sign(canonical_bytes(unsigned))
        return cls(
            capsule_id=capsule_id,
            predecessor_id=predecessor.seal_id,
            successor_root=successor_root,
            rule_id=rule_id,
            rule_witness=rule_witness,
            bundle_id=bundle_id,
            attempt=attempt,
            epoch=predecessor.epoch,
            client_id=client.identity,
            client_public_key=client.public_key,
            client_signature=signature,
        )

    def unsigned_statement(self) -> dict:
        return {
            "protocol": "MOSAIC/CAPSULE/v0.1",
            "predecessor_id": self.predecessor_id,
            "successor_root": self.successor_root,
            "rule_id": self.rule_id,
            "rule_witness": self.rule_witness,
            "bundle_id": self.bundle_id,
            "attempt": self.attempt,
            "epoch": self.epoch,
            "client_id": self.client_id,
            "client_public_key": self.client_public_key.hex(),
        }

    def verify_client_signature(self) -> bool:
        return KeyPair.verify(
            self.client_public_key,
            canonical_bytes(self.unsigned_statement()),
            self.client_signature,
        )


@dataclass(frozen=True)
class WitnessReceipt:
    capsule_id: str
    predecessor_id: str
    witness_id: str
    epoch: int
    attempt: int
    status: str
    signature: bytes

    def statement(self) -> dict:
        return {
            "protocol": "MOSAIC/RECEIPT/v0.1",
            "capsule_id": self.capsule_id,
            "predecessor_id": self.predecessor_id,
            "witness_id": self.witness_id,
            "epoch": self.epoch,
            "attempt": self.attempt,
            "status": self.status,
        }

    @property
    def receipt_id(self) -> str:
        return digest({**self.statement(), "signature": self.signature.hex()})


@dataclass(frozen=True)
class ClosureProof:
    capsule_id: str
    predecessor_id: str
    epoch: int
    attempt: int
    signer_ids: tuple[str, ...]
    receipts: tuple[WitnessReceipt, ...]
    proof_id: str

    @classmethod
    def create(cls, receipts: Iterable[WitnessReceipt]) -> "ClosureProof":
        ordered = tuple(sorted(receipts, key=lambda item: item.witness_id))
        if not ordered:
            raise ClosureInvalid("closure requires receipts")
        first = ordered[0]
        if any(
            item.status != "ACCEPT"
            or item.capsule_id != first.capsule_id
            or item.predecessor_id != first.predecessor_id
            or item.epoch != first.epoch
            or item.attempt != first.attempt
            for item in ordered
        ):
            raise ClosureInvalid("receipts do not describe one capsule")
        proof_id = digest(
            {
                "protocol": "MOSAIC/CLOSURE/v0.1",
                "capsule_id": first.capsule_id,
                "predecessor_id": first.predecessor_id,
                "epoch": first.epoch,
                "attempt": first.attempt,
                "receipts": [item.receipt_id for item in ordered],
            }
        )
        return cls(
            capsule_id=first.capsule_id,
            predecessor_id=first.predecessor_id,
            epoch=first.epoch,
            attempt=first.attempt,
            signer_ids=tuple(item.witness_id for item in ordered),
            receipts=ordered,
            proof_id=proof_id,
        )


@dataclass(frozen=True)
class ConflictEvidence:
    predecessor_id: str
    capsule_a: str
    capsule_b: str
    signatures: tuple[bytes, bytes]
    evidence_id: str

    @classmethod
    def create(cls, first: Capsule, second: Capsule) -> "ConflictEvidence":
        if first.predecessor_id != second.predecessor_id:
            raise MosaicError("conflict requires one predecessor")
        if first.capsule_id == second.capsule_id:
            raise MosaicError("conflict requires distinct capsules")
        ordered = sorted((first, second), key=lambda item: item.capsule_id)
        return cls(
            predecessor_id=first.predecessor_id,
            capsule_a=ordered[0].capsule_id,
            capsule_b=ordered[1].capsule_id,
            signatures=(ordered[0].client_signature, ordered[1].client_signature),
            evidence_id=digest(
                {
                    "protocol": "MOSAIC/CONFLICT/v0.1",
                    "predecessor_id": first.predecessor_id,
                    "capsule_a": ordered[0].capsule_id,
                    "capsule_b": ordered[1].capsule_id,
                    "signatures": [item.client_signature.hex() for item in ordered],
                }
            ),
        )


@dataclass(frozen=True)
class AbandonProof:
    predecessor_id: str
    capsule_id: str
    epoch: int
    attempt: int
    signer_ids: tuple[str, ...]
    receipts: tuple[WitnessReceipt, ...]
    proof_id: str

    @classmethod
    def create(cls, receipts: Iterable[WitnessReceipt]) -> "AbandonProof":
        ordered = tuple(sorted(receipts, key=lambda item: item.witness_id))
        if not ordered or any(item.status != "ABANDON" for item in ordered):
            raise ClosureInvalid("abandon proof requires abandon receipts")
        first = ordered[0]
        if any(
            item.capsule_id != first.capsule_id
            or item.predecessor_id != first.predecessor_id
            or item.epoch != first.epoch
            or item.attempt != first.attempt
            for item in ordered
        ):
            raise ClosureInvalid("abandon receipts do not match")
        proof_id = digest(
            {
                "protocol": "MOSAIC/ABANDON/v0.1",
                "capsule_id": first.capsule_id,
                "predecessor_id": first.predecessor_id,
                "epoch": first.epoch,
                "attempt": first.attempt,
                "receipts": [item.receipt_id for item in ordered],
            }
        )
        return cls(
            predecessor_id=first.predecessor_id,
            capsule_id=first.capsule_id,
            epoch=first.epoch,
            attempt=first.attempt,
            signer_ids=tuple(item.witness_id for item in ordered),
            receipts=ordered,
            proof_id=proof_id,
        )


@dataclass(frozen=True)
class BundleClosure:
    bundle_id: str
    closure_ids: tuple[str, ...]
    proof_id: str

    @classmethod
    def create(cls, bundle_id: str, closures: Iterable[ClosureProof]) -> "BundleClosure":
        ordered = tuple(sorted(closures, key=lambda item: item.predecessor_id))
        if not ordered:
            raise ClosureInvalid("bundle closure requires domain closures")
        proof_id = digest(
            {
                "protocol": "MOSAIC/BUNDLE-CLOSURE/v0.1",
                "bundle_id": bundle_id,
                "closures": [item.proof_id for item in ordered],
            }
        )
        return cls(
            bundle_id=bundle_id,
            closure_ids=tuple(item.proof_id for item in ordered),
            proof_id=proof_id,
        )
