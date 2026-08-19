"""Epoch transitions and committee reconfiguration for CCD/NEXUS."""

from __future__ import annotations

from dataclasses import dataclass

from .crypto import KeyPair, canonical_bytes, digest
from .models import EpochTransitionCertificate, Validator
from .quorum import QuorumCommittee, QuorumError


class ReconfigurationError(ValueError):
    """Raised when an epoch transition is invalid."""


@dataclass
class EpochManager:
    epoch: int
    committee: QuorumCommittee

    def _statement(self, new_validators: dict[str, Validator]) -> dict:
        return {
            "protocol": "CCD/NEXUS/v1",
            "phase": "EPOCH_TRANSITION",
            "from_epoch": self.epoch,
            "to_epoch": self.epoch + 1,
            "validator_ids": sorted(new_validators),
        }

    def propose_transition(
        self,
        new_validators: dict[str, Validator],
    ) -> EpochTransitionCertificate:
        if not new_validators:
            raise ReconfigurationError("new committee cannot be empty")
        statement = self._statement(new_validators)
        statement_digest = digest(statement)
        signatures = tuple(
            sorted(
                (
                    validator.validator_id,
                    validator.keypair.sign(canonical_bytes(statement)),
                )
                for validator in self.committee.validators.values()
            )
        )
        signers = tuple(item[0] for item in signatures)
        certificate_id = digest(
            {
                "statement": statement_digest,
                "signers": list(signers),
                "signatures": [(item, signature.hex()) for item, signature in signatures],
            }
        )
        certificate = EpochTransitionCertificate(
            certificate_id=certificate_id,
            from_epoch=self.epoch,
            to_epoch=self.epoch + 1,
            validator_ids=tuple(sorted(new_validators)),
            signers=signers,
            signatures=signatures,
            statement_digest=statement_digest,
        )
        if not self.verify_transition(certificate, new_validators):
            raise ReconfigurationError("issued transition certificate failed verification")
        return certificate

    def verify_transition(
        self,
        certificate: EpochTransitionCertificate,
        new_validators: dict[str, Validator],
    ) -> bool:
        statement = self._statement(new_validators)
        expected_digest = digest(statement)
        signatures = tuple(sorted(certificate.signatures))
        expected_id = digest(
            {
                "statement": expected_digest,
                "signers": sorted(certificate.signers),
                "signatures": [(item, signature.hex()) for item, signature in signatures],
            }
        )
        signature_map = dict(signatures)
        valid_signatures = (
            set(signature_map) == set(certificate.signers)
            and set(signature_map).issubset(self.committee.validators)
            and all(
                KeyPair.verify(
                    self.committee.validators[validator_id].keypair.public_key,
                    canonical_bytes(statement),
                    signature_map[validator_id],
                )
                for validator_id in signature_map
            )
        )
        return (
            certificate.certificate_id == expected_id
            and certificate.from_epoch == self.epoch
            and certificate.to_epoch == self.epoch + 1
            and certificate.validator_ids == tuple(sorted(new_validators))
            and certificate.statement_digest == expected_digest
            and self.committee.weight_of(set(certificate.signers)) >= self.committee.threshold
            and valid_signatures
        )

    def apply_transition(
        self,
        certificate: EpochTransitionCertificate,
        new_validators: dict[str, Validator],
    ) -> "EpochManager":
        if not self.verify_transition(certificate, new_validators):
            raise ReconfigurationError("invalid epoch transition certificate")
        return EpochManager(
            epoch=self.epoch + 1,
            committee=QuorumCommittee(new_validators),
        )
