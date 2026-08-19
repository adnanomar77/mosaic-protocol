"""Atomic multi-domain Join/Abort coordination for CCD/NEXUS."""

from __future__ import annotations

from dataclasses import dataclass

from .crypto import KeyPair, canonical_bytes, digest
from .domain import DomainExecutionError, DomainExecutor
from .models import AbortCertificate, Certificate, JoinCertificate, Operation


class JoinError(ValueError):
    """Raised when a multi-domain operation cannot be joined atomically."""


@dataclass
class JoinCoordinator:
    domains: dict[str, DomainExecutor]

    @property
    def committee(self):
        committees = {id(domain.committee): domain.committee for domain in self.domains.values()}
        if len(committees) != 1:
            raise JoinError("prototype requires one committee shared by all domains")
        return next(iter(committees.values()))

    def prepare_all(self, operation: Operation) -> tuple[Certificate, ...]:
        expected = set(operation.domain_ids)
        if expected != set(self.domains):
            raise JoinError("coordinator domains do not match operation domains")
        certificates = []
        for domain_id in sorted(expected):
            certificates.append(self.domains[domain_id].prepare(operation))
        return tuple(certificates)

    def _join_statement(self, operation: Operation, certificates: tuple[Certificate, ...]) -> dict:
        return {
            "protocol": "CCD/NEXUS/v1",
            "phase": "JOIN",
            "epoch": operation.epoch,
            "op_id": operation.op_id,
            "domains": sorted(operation.domain_ids),
            "domain_certificates": [
                {
                    "domain": cert.domain_ids[0],
                    "certificate_id": cert.certificate_id,
                    "statement_digest": cert.statement_digest,
                }
                for cert in certificates
            ],
        }

    def issue_join_certificate(
        self,
        operation: Operation,
        domain_certificates: tuple[Certificate, ...],
    ) -> JoinCertificate:
        if len(domain_certificates) != len(operation.domain_ids):
            raise JoinError("missing domain certificate")
        if {cert.domain_ids[0] for cert in domain_certificates} != set(operation.domain_ids):
            raise JoinError("domain certificates do not cover operation domains")
        if any(cert.op_id != operation.op_id or cert.phase != "PREPARE" for cert in domain_certificates):
            raise JoinError("domain certificate is not a prepare certificate for this operation")
        statement = self._join_statement(operation, domain_certificates)
        statement_digest = digest(statement)
        signatures = []
        for validator in self.committee.validators.values():
            signatures.append((validator.validator_id, validator.keypair.sign(canonical_bytes(statement))))
        signature_items = tuple(sorted(signatures))
        self.committee.message_count += len(signature_items)
        self.committee.message_bytes += sum(
            len(canonical_bytes(statement)) + len(signature)
            for _, signature in signature_items
        )
        signers = tuple(item[0] for item in signature_items)
        certificate_id = digest(
            {
                "statement": statement_digest,
                "signers": list(signers),
                "signatures": [(item, sig.hex()) for item, sig in signature_items],
            }
        )
        return JoinCertificate(
            certificate_id=certificate_id,
            epoch=operation.epoch,
            op_id=operation.op_id,
            domain_certificates=tuple(
                sorted(domain_certificates, key=lambda cert: cert.domain_ids[0])
            ),
            signers=signers,
            signatures=signature_items,
            statement_digest=statement_digest,
        )

    def verify_join_certificate(
        self,
        operation: Operation,
        certificate: JoinCertificate,
    ) -> bool:
        expected_domains = set(operation.domain_ids)
        if certificate.epoch != operation.epoch or certificate.op_id != operation.op_id:
            return False
        if {cert.domain_ids[0] for cert in certificate.domain_certificates} != expected_domains:
            return False
        if any(cert.op_id != operation.op_id or cert.phase != "PREPARE" for cert in certificate.domain_certificates):
            return False
        statement = self._join_statement(
            operation,
            tuple(sorted(certificate.domain_certificates, key=lambda cert: cert.domain_ids[0])),
        )
        expected_statement_digest = digest(statement)
        signatures = tuple(sorted(certificate.signatures))
        expected_id = digest(
            {
                "statement": expected_statement_digest,
                "signers": sorted(certificate.signers),
                "signatures": [(item, sig.hex()) for item, sig in signatures],
            }
        )
        signature_map = dict(signatures)
        signatures_valid = (
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
            and certificate.statement_digest == expected_statement_digest
            and len(set(certificate.signers)) == len(certificate.signers)
            and set(certificate.signers).issubset(self.committee.validators)
            and self.committee.weight_of(set(certificate.signers)) >= self.committee.threshold
            and signatures_valid
        )

    def finalize(self, operation: Operation) -> JoinCertificate:
        prepare_certificates = self.prepare_all(operation)
        join_certificate = self.issue_join_certificate(operation, prepare_certificates)
        if not self.verify_join_certificate(operation, join_certificate):
            raise JoinError("issued Join certificate failed verification")

        commit_certificates = []
        for domain_id in sorted(operation.domain_ids):
            domain = self.domains[domain_id]
            commit_certificates.append(
                domain.commit_certificate(operation, domain.prepared_certificates[operation.op_id])
            )

        # The all-or-nothing point: no domain is applied until every domain has
        # produced and locally verified a COMMIT certificate.
        for domain_id, commit_certificate in zip(sorted(operation.domain_ids), commit_certificates):
            domain = self.domains[domain_id]
            domain.apply_committed(operation, commit_certificate)
        return join_certificate

    def abort(self, operation: Operation, reason: str) -> AbortCertificate:
        """Issue a threshold-backed abort certificate; no state is committed."""
        if not reason.strip():
            raise JoinError("abort requires a reason")
        statement = {
            "protocol": "CCD/NEXUS/v1",
            "phase": "ABORT",
            "epoch": operation.epoch,
            "op_id": operation.op_id,
            "domains": sorted(operation.domain_ids),
            "reason_digest": digest(reason),
        }
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
        certificate = AbortCertificate(
            certificate_id=certificate_id,
            epoch=operation.epoch,
            op_id=operation.op_id,
            domain_ids=tuple(sorted(operation.domain_ids)),
            reason_digest=digest(reason),
            signers=signers,
            signatures=signatures,
            statement_digest=statement_digest,
        )
        if not self.verify_abort(operation, certificate, reason):
            raise JoinError("issued Abort certificate failed verification")
        return certificate

    def verify_abort(
        self,
        operation: Operation,
        certificate: AbortCertificate,
        reason: str,
    ) -> bool:
        statement = {
            "protocol": "CCD/NEXUS/v1",
            "phase": "ABORT",
            "epoch": operation.epoch,
            "op_id": operation.op_id,
            "domains": sorted(operation.domain_ids),
            "reason_digest": digest(reason),
        }
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
            and certificate.statement_digest == expected_digest
            and certificate.epoch == operation.epoch
            and certificate.op_id == operation.op_id
            and certificate.domain_ids == tuple(sorted(operation.domain_ids))
            and certificate.reason_digest == digest(reason)
            and self.committee.weight_of(set(certificate.signers)) >= self.committee.threshold
            and valid_signatures
        )
