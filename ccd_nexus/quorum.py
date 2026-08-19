"""Quorum and vote validation for CCD/NEXUS."""

from __future__ import annotations

from dataclasses import dataclass, field

from .crypto import KeyPair, canonical_bytes, digest
from .models import (
    Certificate,
    DataAvailabilityCertificate,
    Operation,
    Validator,
    Vote,
)


class QuorumError(ValueError):
    """Raised when a quorum or certificate rule is violated."""


@dataclass(frozen=True)
class EquivocationEvidence:
    validator_id: str
    first_op_id: str
    second_op_id: str
    epoch: int
    domain_id: str
    object_versions: tuple[tuple[str, int], ...]


@dataclass
class QuorumCommittee:
    validators: dict[str, Validator]
    _votes: dict[tuple[int, str, tuple[tuple[str, int], ...], str], dict[str, Vote]] = field(
        default_factory=dict
    )
    _statements: dict[
        tuple[int, str, tuple[tuple[str, int], ...], str], dict[str, tuple[str, str]]
    ] = field(default_factory=dict)
    evidence: list[EquivocationEvidence] = field(default_factory=list)
    message_count: int = 0
    message_bytes: int = 0

    @property
    def total_weight(self) -> int:
        return sum(item.weight for item in self.validators.values())

    @property
    def threshold(self) -> int:
        # Strictly greater than 2/3 of the total voting weight.
        return (2 * self.total_weight) // 3 + 1

    def weight_of(self, validator_ids: set[str]) -> int:
        return sum(self.validators[item].weight for item in validator_ids)

    def reset_metrics(self) -> None:
        self.message_count = 0
        self.message_bytes = 0

    def record_vote(self, vote: Vote) -> None:
        validator = self.validators.get(vote.validator_id)
        if validator is None:
            raise QuorumError("vote is from an unknown validator")
        if vote.epoch < 0:
            raise QuorumError("epoch must be non-negative")
        if not KeyPair.verify(
            validator.keypair.public_key,
            canonical_bytes(vote.statement),
            vote.signature,
        ):
            raise QuorumError("invalid validator signature")

        conflict_key = (
            vote.epoch,
            vote.domain_id,
            vote.object_versions,
            vote.phase,
        )
        statement = (vote.op_id, vote.dependency_digest)
        known = self._statements.setdefault(conflict_key, {})
        previous = known.get(vote.validator_id)
        if previous is not None and previous != statement:
            self.evidence.append(
                EquivocationEvidence(
                    validator_id=vote.validator_id,
                    first_op_id=previous[0],
                    second_op_id=vote.op_id,
                    epoch=vote.epoch,
                    domain_id=vote.domain_id,
                    object_versions=vote.object_versions,
                )
            )
            raise QuorumError("validator equivocated on the same object version")
        if previous is None:
            self.message_count += 1
            self.message_bytes += len(canonical_bytes(vote.statement)) + len(vote.signature)
        known[vote.validator_id] = statement
        self._votes.setdefault(conflict_key, {})[vote.validator_id] = vote

    def issue_certificate(
        self,
        *,
        epoch: int,
        domain_id: str,
        object_versions: tuple[tuple[str, int], ...],
        operation: Operation,
        phase: str,
    ) -> Certificate:
        key = (epoch, domain_id, object_versions, phase)
        votes = self._votes.get(key, {})
        matching = [
            vote
            for vote in votes.values()
            if vote.op_id == operation.op_id
            and vote.dependency_digest == operation.dependency_digest
        ]
        signers = {vote.validator_id for vote in matching}
        if self.weight_of(signers) < self.threshold:
            raise QuorumError(
                f"insufficient quorum: weight={self.weight_of(signers)}, "
                f"required={self.threshold}"
            )
        statement_digest = digest(
            {
                "protocol": "CCD/NEXUS/v1",
                "epoch": epoch,
                "domain_id": domain_id,
                "object_versions": object_versions,
                "op_id": operation.op_id,
                "dependency_digest": operation.dependency_digest,
                "phase": phase,
            }
        )
        signature_items = tuple(
            sorted((vote.validator_id, vote.signature) for vote in matching)
        )
        certificate_id = digest(
            {
                "statement": statement_digest,
                "signers": sorted(signers),
                "signatures": [(item, signature.hex()) for item, signature in signature_items],
            }
        )
        return Certificate(
            certificate_id=certificate_id,
            epoch=epoch,
            domain_ids=(domain_id,),
            op_id=operation.op_id,
            phase=phase,
            signers=tuple(sorted(signers)),
            signatures=signature_items,
            statement_digest=statement_digest,
        )

    def verify_certificate(
        self,
        *,
        certificate: Certificate,
        epoch: int,
        domain_id: str,
        object_versions: tuple[tuple[str, int], ...],
        operation: Operation,
    ) -> bool:
        expected_statement = digest(
            {
                "protocol": "CCD/NEXUS/v1",
                "epoch": epoch,
                "domain_id": domain_id,
                "object_versions": object_versions,
                "op_id": operation.op_id,
                "dependency_digest": operation.dependency_digest,
                "phase": certificate.phase,
            }
        )
        expected_signatures = tuple(sorted(certificate.signatures))
        expected_id = digest(
            {
                "statement": expected_statement,
                "signers": sorted(set(certificate.signers)),
                "signatures": [(item, signature.hex()) for item, signature in expected_signatures],
            }
        )
        signature_map = dict(expected_signatures)
        statement = {
            "protocol": "CCD/NEXUS/v1",
            "phase": certificate.phase,
            "epoch": epoch,
            "domain_id": domain_id,
            "object_versions": object_versions,
            "op_id": operation.op_id,
            "dependency_digest": operation.dependency_digest,
        }
        signatures_valid = (
            set(signature_map) == set(certificate.signers)
            and set(signature_map).issubset(self.validators)
            and all(
                KeyPair.verify(
                    self.validators[validator_id].keypair.public_key,
                    canonical_bytes(statement),
                    signature_map[validator_id],
                )
                for validator_id in signature_map
            )
        )
        return (
            certificate.certificate_id == expected_id
            and certificate.statement_digest == expected_statement
            and certificate.epoch == epoch
            and certificate.domain_ids == (domain_id,)
            and certificate.op_id == operation.op_id
            and certificate.phase in {"PREPARE", "COMMIT"}
            and len(set(certificate.signers)) == len(certificate.signers)
            and self.weight_of(set(certificate.signers)) >= self.threshold
            and set(certificate.signers).issubset(self.validators)
            and signatures_valid
        )

    def _availability_statement(self, operation: Operation) -> dict:
        return {
            "protocol": "CCD/NEXUS/v1",
            "phase": "DAC",
            "epoch": operation.epoch,
            "op_id": operation.op_id,
            "payload_digest": operation.op_id,
        }

    def issue_dac(self, operation: Operation) -> DataAvailabilityCertificate:
        statement = self._availability_statement(operation)
        statement_digest = digest(statement)
        signatures = tuple(
            sorted(
                (
                    validator.validator_id,
                    validator.keypair.sign(canonical_bytes(statement)),
                )
                for validator in self.validators.values()
            )
        )
        signers = tuple(item[0] for item in signatures)
        self.message_count += len(signatures)
        self.message_bytes += sum(
            len(canonical_bytes(statement)) + len(signature)
            for _, signature in signatures
        )
        certificate_id = digest(
            {
                "statement": statement_digest,
                "signers": list(signers),
                "signatures": [(item, signature.hex()) for item, signature in signatures],
            }
        )
        certificate = DataAvailabilityCertificate(
            certificate_id=certificate_id,
            epoch=operation.epoch,
            op_id=operation.op_id,
            payload_digest=operation.op_id,
            signers=signers,
            signatures=signatures,
            statement_digest=statement_digest,
        )
        if not self.verify_dac(operation, certificate):
            raise QuorumError("issued DAC failed verification")
        return certificate

    def verify_dac(
        self,
        operation: Operation,
        certificate: DataAvailabilityCertificate,
    ) -> bool:
        statement = self._availability_statement(operation)
        expected_digest = digest(statement)
        signatures = tuple(sorted(certificate.signatures))
        signature_map = dict(signatures)
        expected_id = digest(
            {
                "statement": expected_digest,
                "signers": sorted(certificate.signers),
                "signatures": [(item, signature.hex()) for item, signature in signatures],
            }
        )
        valid_signatures = (
            set(signature_map) == set(certificate.signers)
            and set(signature_map).issubset(self.validators)
            and all(
                KeyPair.verify(
                    self.validators[validator_id].keypair.public_key,
                    canonical_bytes(statement),
                    signature_map[validator_id],
                )
                for validator_id in signature_map
            )
        )
        return (
            certificate.certificate_id == expected_id
            and certificate.statement_digest == expected_digest
            and certificate.epoch == operation.epoch
            and certificate.op_id == operation.op_id
            and certificate.payload_digest == operation.op_id
            and self.weight_of(set(certificate.signers)) >= self.threshold
            and valid_signatures
        )
