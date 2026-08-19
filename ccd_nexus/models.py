"""Protocol data models for the CCD/NEXUS prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .crypto import KeyPair, canonical_bytes, digest


@dataclass(frozen=True)
class ObjectState:
    object_id: str
    version: int
    owner: str
    payload: str
    domain_id: str


@dataclass(frozen=True)
class InputRef:
    domain_id: str
    object_id: str
    expected_version: int


@dataclass(frozen=True)
class WriteIntent:
    domain_id: str
    object_id: str
    expected_version: int
    new_owner: str
    new_payload: str


@dataclass(frozen=True)
class Operation:
    op_id: str
    epoch: int
    signer: str
    signer_public_key: bytes
    domain_ids: tuple[str, ...]
    inputs: tuple[InputRef, ...]
    writes: tuple[WriteIntent, ...]
    parent_certificates: tuple[str, ...]
    nonce: int
    signature: bytes

    @classmethod
    def create(
        cls,
        *,
        keypair: KeyPair,
        epoch: int,
        inputs: Iterable[InputRef],
        writes: Iterable[WriteIntent],
        domain_ids: Iterable[str],
        parent_certificates: Iterable[str] = (),
        nonce: int = 0,
    ) -> "Operation":
        input_tuple = tuple(inputs)
        write_tuple = tuple(writes)
        domain_tuple = tuple(sorted(set(domain_ids)))
        parent_tuple = tuple(sorted(set(parent_certificates)))
        unsigned = {
            "epoch": epoch,
            "signer": keypair.identity,
            "public_key": keypair.public_key.hex(),
            "domain_ids": domain_tuple,
            "inputs": [vars(item) for item in input_tuple],
            "writes": [vars(item) for item in write_tuple],
            "parents": parent_tuple,
            "nonce": nonce,
        }
        op_id = digest(unsigned)
        signature = keypair.sign(canonical_bytes({"op_id": op_id, **unsigned}))
        return cls(
            op_id=op_id,
            epoch=epoch,
            signer=keypair.identity,
            signer_public_key=keypair.public_key,
            domain_ids=domain_tuple,
            inputs=input_tuple,
            writes=write_tuple,
            parent_certificates=parent_tuple,
            nonce=nonce,
            signature=signature,
        )

    def signing_payload(self) -> bytes:
        return canonical_bytes(
            {
                "op_id": self.op_id,
                "epoch": self.epoch,
                "signer": self.signer,
                "public_key": self.signer_public_key.hex(),
                "domain_ids": self.domain_ids,
                "inputs": [vars(item) for item in self.inputs],
                "writes": [vars(item) for item in self.writes],
                "parents": self.parent_certificates,
                "nonce": self.nonce,
            }
        )

    def verify_signature(self) -> bool:
        return KeyPair.verify(self.signer_public_key, self.signing_payload(), self.signature)

    @property
    def dependency_digest(self) -> str:
        return digest(
            {
                "parents": self.parent_certificates,
                "inputs": [vars(item) for item in self.inputs],
            }
        )


@dataclass(frozen=True)
class Vote:
    validator_id: str
    epoch: int
    domain_id: str
    object_versions: tuple[tuple[str, int], ...]
    op_id: str
    dependency_digest: str
    phase: str
    signature: bytes

    @property
    def statement(self) -> dict:
        return {
            "protocol": "CCD/NEXUS/v1",
            "phase": self.phase,
            "epoch": self.epoch,
            "domain_id": self.domain_id,
            "object_versions": self.object_versions,
            "op_id": self.op_id,
            "dependency_digest": self.dependency_digest,
        }


@dataclass(frozen=True)
class Certificate:
    certificate_id: str
    epoch: int
    domain_ids: tuple[str, ...]
    op_id: str
    phase: str
    signers: tuple[str, ...]
    signatures: tuple[tuple[str, bytes], ...]
    statement_digest: str


@dataclass(frozen=True)
class JoinCertificate:
    certificate_id: str
    epoch: int
    op_id: str
    domain_certificates: tuple[Certificate, ...]
    signers: tuple[str, ...]
    signatures: tuple[tuple[str, bytes], ...]
    statement_digest: str


@dataclass(frozen=True)
class EpochTransitionCertificate:
    certificate_id: str
    from_epoch: int
    to_epoch: int
    validator_ids: tuple[str, ...]
    signers: tuple[str, ...]
    signatures: tuple[tuple[str, bytes], ...]
    statement_digest: str


@dataclass(frozen=True)
class StateSnapshot:
    snapshot_id: str
    epoch: int
    domain_id: str
    state_root: str
    signers: tuple[str, ...]
    signatures: tuple[tuple[str, bytes], ...]
    statement_digest: str


@dataclass(frozen=True)
class DataAvailabilityCertificate:
    certificate_id: str
    epoch: int
    op_id: str
    payload_digest: str
    signers: tuple[str, ...]
    signatures: tuple[tuple[str, bytes], ...]
    statement_digest: str


@dataclass(frozen=True)
class AbortCertificate:
    certificate_id: str
    epoch: int
    op_id: str
    domain_ids: tuple[str, ...]
    reason_digest: str
    signers: tuple[str, ...]
    signatures: tuple[tuple[str, bytes], ...]
    statement_digest: str


@dataclass(frozen=True)
class Event:
    event_id: str
    epoch: int
    creator: str
    parents: tuple[str, ...]
    operation_ids: tuple[str, ...]


@dataclass
class Epoch:
    number: int
    validators: dict[str, "Validator"] = field(default_factory=dict)

    @property
    def total_weight(self) -> int:
        return sum(validator.weight for validator in self.validators.values())


@dataclass
class Validator:
    validator_id: str
    keypair: KeyPair
    weight: int = 1
    byzantine: bool = False

    def sign_vote(
        self,
        *,
        epoch: int,
        domain_id: str,
        object_versions: tuple[tuple[str, int], ...],
        op_id: str,
        dependency_digest: str,
        phase: str,
    ) -> Vote:
        statement = {
            "protocol": "CCD/NEXUS/v1",
            "phase": phase,
            "epoch": epoch,
            "domain_id": domain_id,
            "object_versions": object_versions,
            "op_id": op_id,
            "dependency_digest": dependency_digest,
        }
        signature = self.keypair.sign(canonical_bytes(statement))
        return Vote(
            validator_id=self.validator_id,
            epoch=epoch,
            domain_id=domain_id,
            object_versions=object_versions,
            op_id=op_id,
            dependency_digest=dependency_digest,
            phase=phase,
            signature=signature,
        )
