"""Single-domain execution and finality for CCD/NEXUS."""

from __future__ import annotations

from dataclasses import dataclass, field

from .crypto import KeyPair, canonical_bytes, digest
from .models import (
    Certificate,
    DataAvailabilityCertificate,
    ObjectState,
    Operation,
    StateSnapshot,
)
from .quorum import QuorumCommittee, QuorumError


class DomainExecutionError(ValueError):
    """Raised when a domain operation is invalid or conflicts with state."""


@dataclass
class DomainExecutor:
    domain_id: str
    epoch: int
    committee: QuorumCommittee
    objects: dict[str, ObjectState] = field(default_factory=dict)
    committed_operations: set[str] = field(default_factory=set)
    availability_certificates: dict[str, DataAvailabilityCertificate] = field(default_factory=dict)
    prepared_certificates: dict[str, Certificate] = field(default_factory=dict)
    commit_certificates: dict[str, Certificate] = field(default_factory=dict)

    def add_object(self, state: ObjectState) -> None:
        if state.domain_id != self.domain_id:
            raise DomainExecutionError("object belongs to another domain")
        if state.object_id in self.objects:
            raise DomainExecutionError("object already exists")
        self.objects[state.object_id] = state

    def _local_inputs(self, operation: Operation):
        return tuple(item for item in operation.inputs if item.domain_id == self.domain_id)

    def _local_writes(self, operation: Operation):
        return tuple(item for item in operation.writes if item.domain_id == self.domain_id)

    def _object_versions(self, operation: Operation) -> tuple[tuple[str, int], ...]:
        return tuple(
            sorted((item.object_id, item.expected_version) for item in self._local_inputs(operation))
        )

    def validate_operation(self, operation: Operation) -> None:
        if operation.epoch != self.epoch:
            raise DomainExecutionError("operation belongs to another epoch")
        if self.domain_id not in operation.domain_ids:
            raise DomainExecutionError("operation does not declare this domain")
        if not operation.verify_signature():
            raise DomainExecutionError("invalid client signature")
        if operation.op_id in self.committed_operations:
            raise DomainExecutionError("operation is already committed")
        if not operation.inputs:
            raise DomainExecutionError("operation must have at least one input")

        declared_domains = {item.domain_id for item in operation.inputs}
        if declared_domains != set(operation.domain_ids):
            raise DomainExecutionError("domain declaration does not match inputs")
        if len({(item.domain_id, item.object_id) for item in operation.inputs}) != len(
            operation.inputs
        ):
            raise DomainExecutionError("duplicate input object")
        if len({(item.domain_id, item.object_id) for item in operation.writes}) != len(
            operation.writes
        ):
            raise DomainExecutionError("duplicate write intent")
        input_map = {(item.domain_id, item.object_id): item for item in operation.inputs}
        write_map = {(item.domain_id, item.object_id): item for item in operation.writes}
        if set(input_map) != set(write_map):
            raise DomainExecutionError("prototype requires one write intent per input")

        for key, input_ref in input_map.items():
            intent = write_map[key]
            if intent.expected_version != input_ref.expected_version:
                raise DomainExecutionError("write version disagrees with input version")

        local_inputs = self._local_inputs(operation)
        if not local_inputs:
            raise DomainExecutionError("operation has no input in this domain")
        for item in local_inputs:
            state = self.objects.get(item.object_id)
            if state is None:
                raise DomainExecutionError(f"unknown object: {item.object_id}")
            if state.domain_id != self.domain_id:
                raise DomainExecutionError("input references another domain")
            if state.version != item.expected_version:
                raise DomainExecutionError(
                    f"stale version for {item.object_id}: "
                    f"expected {item.expected_version}, found {state.version}"
                )
            if state.owner != operation.signer:
                raise DomainExecutionError("operation signer does not own input")

    def _record_votes(self, operation: Operation, phase: str) -> None:
        object_versions = self._object_versions(operation)
        for validator in self.committee.validators.values():
            vote = validator.sign_vote(
                epoch=self.epoch,
                domain_id=self.domain_id,
                object_versions=object_versions,
                op_id=operation.op_id,
                dependency_digest=operation.dependency_digest,
                phase=phase,
            )
            self.committee.record_vote(vote)

    def prepare(
        self,
        operation: Operation,
        availability_certificate: DataAvailabilityCertificate | None = None,
    ) -> Certificate:
        self.validate_operation(operation)
        dac = availability_certificate or self.committee.issue_dac(operation)
        if not self.committee.verify_dac(operation, dac):
            raise QuorumError("operation data is not available to the quorum")
        self.availability_certificates[operation.op_id] = dac
        object_versions = self._object_versions(operation)
        self._record_votes(operation, "PREPARE")
        certificate = self.committee.issue_certificate(
            epoch=self.epoch,
            domain_id=self.domain_id,
            object_versions=object_versions,
            operation=operation,
            phase="PREPARE",
        )
        if not self.committee.verify_certificate(
            certificate=certificate,
            epoch=self.epoch,
            domain_id=self.domain_id,
            object_versions=object_versions,
            operation=operation,
        ):
            raise QuorumError("issued prepare certificate failed verification")
        self.prepared_certificates[operation.op_id] = certificate
        return certificate

    def commit_certificate(
        self,
        operation: Operation,
        prepare_certificate: Certificate,
    ) -> Certificate:
        self.validate_operation(operation)
        object_versions = self._object_versions(operation)
        if operation.op_id not in self.prepared_certificates:
            raise DomainExecutionError("operation has not been prepared")
        if prepare_certificate != self.prepared_certificates[operation.op_id]:
            raise DomainExecutionError("unknown prepare certificate")
        self._record_votes(operation, "COMMIT")
        certificate = self.committee.issue_certificate(
            epoch=self.epoch,
            domain_id=self.domain_id,
            object_versions=object_versions,
            operation=operation,
            phase="COMMIT",
        )
        if not self.committee.verify_certificate(
            certificate=certificate,
            epoch=self.epoch,
            domain_id=self.domain_id,
            object_versions=object_versions,
            operation=operation,
        ):
            raise QuorumError("issued commit certificate failed verification")
        return certificate

    def apply_committed(self, operation: Operation, commit_certificate: Certificate) -> None:
        self.validate_operation(operation)
        object_versions = self._object_versions(operation)
        if not self.committee.verify_certificate(
            certificate=commit_certificate,
            epoch=self.epoch,
            domain_id=self.domain_id,
            object_versions=object_versions,
            operation=operation,
        ):
            raise QuorumError("invalid commit certificate")
        if operation.op_id in self.committed_operations:
            raise DomainExecutionError("operation would be applied twice")
        for intent in self._local_writes(operation):
            state = self.objects[intent.object_id]
            self.objects[intent.object_id] = ObjectState(
                object_id=state.object_id,
                version=state.version + 1,
                owner=intent.new_owner,
                payload=intent.new_payload,
                domain_id=state.domain_id,
            )
        self.committed_operations.add(operation.op_id)
        self.commit_certificates[operation.op_id] = commit_certificate

    def commit(self, operation: Operation, prepare_certificate: Certificate) -> Certificate:
        certificate = self.commit_certificate(operation, prepare_certificate)
        self.apply_committed(operation, certificate)
        return certificate

    def finalize(self, operation: Operation) -> Certificate:
        prepare = self.prepare(operation)
        return self.commit(operation, prepare)

    def state_root(self) -> str:
        """Compute a deterministic Merkle-like root for the current object map."""
        return digest(
            {
                "protocol": "CCD/NEXUS/v1",
                "epoch": self.epoch,
                "domain_id": self.domain_id,
                "objects": [vars(self.objects[key]) for key in sorted(self.objects)],
            }
        )

    def create_snapshot(self) -> StateSnapshot:
        state_root = self.state_root()
        statement = {
            "protocol": "CCD/NEXUS/v1",
            "phase": "SNAPSHOT",
            "epoch": self.epoch,
            "domain_id": self.domain_id,
            "state_root": state_root,
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
        snapshot_id = digest(
            {
                "statement": statement_digest,
                "signers": list(signers),
                "signatures": [(item, signature.hex()) for item, signature in signatures],
            }
        )
        return StateSnapshot(
            snapshot_id=snapshot_id,
            epoch=self.epoch,
            domain_id=self.domain_id,
            state_root=state_root,
            signers=signers,
            signatures=signatures,
            statement_digest=statement_digest,
        )

    def verify_snapshot(self, snapshot: StateSnapshot) -> bool:
        statement = {
            "protocol": "CCD/NEXUS/v1",
            "phase": "SNAPSHOT",
            "epoch": snapshot.epoch,
            "domain_id": snapshot.domain_id,
            "state_root": snapshot.state_root,
        }
        expected_digest = digest(statement)
        signatures = tuple(sorted(snapshot.signatures))
        signature_map = dict(signatures)
        expected_id = digest(
            {
                "statement": expected_digest,
                "signers": sorted(snapshot.signers),
                "signatures": [(item, signature.hex()) for item, signature in signatures],
            }
        )
        valid_signatures = (
            set(signature_map) == set(snapshot.signers)
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
            snapshot.snapshot_id == expected_id
            and snapshot.statement_digest == expected_digest
            and snapshot.epoch == self.epoch
            and snapshot.domain_id == self.domain_id
            and snapshot.state_root == self.state_root()
            and self.committee.weight_of(set(snapshot.signers)) >= self.committee.threshold
            and valid_signatures
        )
