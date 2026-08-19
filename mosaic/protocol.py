"""Executable MOSAIC v0.1 protocol model."""

from __future__ import annotations

from dataclasses import dataclass, field

from ccd_nexus.crypto import KeyPair, canonical_bytes, digest

from .model import (
    AbandonProof,
    BundleClosure,
    Capsule,
    CapsuleInvalid,
    ClosureInvalid,
    ClosureProof,
    ConflictEvidence,
    Member,
    MosaicError,
    StateSeal,
    WitnessReceipt,
)


class ConflictDetected(MosaicError):
    def __init__(self, evidence: ConflictEvidence):
        super().__init__("conflicting capsules share one predecessor")
        self.evidence = evidence


@dataclass
class MosaicProtocol:
    members: dict[str, Member]
    epoch: int = 0
    current_seals: dict[str, StateSeal] = field(default_factory=dict)
    known_seals: dict[str, StateSeal] = field(default_factory=dict)
    locks: dict[str, tuple[str, int, str]] = field(default_factory=dict)
    capsules: dict[str, Capsule] = field(default_factory=dict)
    closures: dict[str, ClosureProof] = field(default_factory=dict)
    abandons: dict[str, AbandonProof] = field(default_factory=dict)
    conflict_evidence: dict[str, ConflictEvidence] = field(default_factory=dict)

    @property
    def total_weight(self) -> int:
        return sum(member.weight for member in self.members.values())

    @property
    def threshold(self) -> int:
        return (2 * self.total_weight) // 3 + 1

    def _member(self, member_id: str) -> Member:
        try:
            return self.members[member_id]
        except KeyError as exc:
            raise MosaicError(f"unknown witness: {member_id}") from exc

    def create_resource(
        self,
        resource_id: str,
        *,
        owner: str,
        state_root: str = "genesis",
        capability_secret: str = "capability",
    ) -> StateSeal:
        if resource_id in self.current_seals:
            raise MosaicError("resource already exists")
        seal = StateSeal(
            resource_id=resource_id,
            epoch=self.epoch,
            version=0,
            state_root=state_root,
            capability_hash=digest(capability_secret),
            owner=owner,
        )
        self.current_seals[resource_id] = seal
        self.known_seals[seal.seal_id] = seal
        return seal

    def create_capsule(
        self,
        *,
        client: KeyPair,
        predecessor: StateSeal,
        successor_root: str,
        rule_id: str = "identity-transition",
        rule_witness: str = "valid",
        attempt: int = 0,
        bundle_id: str | None = None,
    ) -> Capsule:
        current = self.current_seals.get(predecessor.resource_id)
        if current != predecessor:
            raise CapsuleInvalid("predecessor is not the current seal")
        if predecessor.epoch != self.epoch:
            raise CapsuleInvalid("predecessor belongs to another epoch")
        capsule = Capsule.create(
            client=client,
            predecessor=predecessor,
            successor_root=successor_root,
            rule_id=rule_id,
            rule_witness=rule_witness,
            attempt=attempt,
            bundle_id=bundle_id,
        )
        self.capsules[capsule.capsule_id] = capsule
        return capsule

    def validate_capsule(self, capsule: Capsule) -> None:
        current = self.known_seals.get(capsule.predecessor_id)
        if current is None:
            raise CapsuleInvalid("unknown predecessor seal")
        if capsule.epoch != self.epoch or current.epoch != self.epoch:
            raise CapsuleInvalid("capsule epoch mismatch")
        if not capsule.verify_client_signature():
            raise CapsuleInvalid("invalid client signature")
        if capsule.attempt < 0:
            raise CapsuleInvalid("attempt cannot be negative")
        if not capsule.successor_root:
            raise CapsuleInvalid("successor root is empty")

    def _receipt_statement(self, receipt: WitnessReceipt) -> dict:
        return receipt.statement()

    def _sign_receipt(
        self,
        member: Member,
        capsule: Capsule,
        status: str,
    ) -> WitnessReceipt:
        unsigned = {
            "protocol": "MOSAIC/RECEIPT/v0.1",
            "capsule_id": capsule.capsule_id,
            "predecessor_id": capsule.predecessor_id,
            "witness_id": member.member_id,
            "epoch": capsule.epoch,
            "attempt": capsule.attempt,
            "status": status,
        }
        if member.keypair is None:
            raise MosaicError("validator private key is not loaded on this node")
        return WitnessReceipt(
            capsule_id=capsule.capsule_id,
            predecessor_id=capsule.predecessor_id,
            witness_id=member.member_id,
            epoch=capsule.epoch,
            attempt=capsule.attempt,
            status=status,
            signature=member.keypair.sign(canonical_bytes(unsigned)),
        )

    def verify_receipt(self, receipt: WitnessReceipt) -> bool:
        member = self.members.get(receipt.witness_id)
        if member is None:
            return False
        capsule = self.capsules.get(receipt.capsule_id)
        if capsule is None:
            return False
        return (
            receipt.predecessor_id == capsule.predecessor_id
            and receipt.epoch == capsule.epoch == self.epoch
            and receipt.attempt == capsule.attempt
            and KeyPair.verify(
                member.public_key,
                canonical_bytes(receipt.statement()),
                receipt.signature,
            )
        )

    def witness_receipt(self, member_id: str, capsule: Capsule, status: str = "ACCEPT") -> WitnessReceipt:
        if status not in {"ACCEPT", "ABANDON"}:
            raise MosaicError("unknown receipt status")
        self.validate_capsule(capsule)
        member = self._member(member_id)
        key = capsule.predecessor_id
        existing = self.locks.get(key)
        if status == "ACCEPT":
            predecessor = self.known_seals[capsule.predecessor_id]
            current = self.current_seals[predecessor.resource_id]
            if current.seal_id != capsule.predecessor_id:
                if existing is not None and existing[0] != capsule.capsule_id:
                    first = self.capsules.get(existing[0])
                    if first is not None:
                        evidence = ConflictEvidence.create(first, capsule)
                        self.conflict_evidence[evidence.evidence_id] = evidence
                        raise ConflictDetected(evidence)
                raise CapsuleInvalid("predecessor is not current")
            if existing is None:
                self.locks[key] = (capsule.capsule_id, capsule.attempt, "ACCEPT")
                self.capsules[capsule.capsule_id] = capsule
            elif existing[0] == capsule.capsule_id and existing[1] == capsule.attempt:
                pass
            elif existing[2] == "ABANDON" and capsule.attempt > existing[1]:
                self.locks[key] = (capsule.capsule_id, capsule.attempt, "ACCEPT")
                self.capsules[capsule.capsule_id] = capsule
            else:
                first = self.capsules[existing[0]]
                evidence = ConflictEvidence.create(first, capsule)
                self.conflict_evidence[evidence.evidence_id] = evidence
                raise ConflictDetected(evidence)
        else:
            if existing is not None and (
                existing[0] != capsule.capsule_id
                or existing[1] != capsule.attempt
            ):
                first = self.capsules.get(existing[0])
                if first is not None:
                    evidence = ConflictEvidence.create(first, capsule)
                    self.conflict_evidence[evidence.evidence_id] = evidence
                    raise ConflictDetected(evidence)
                raise MosaicError("cannot abandon an unknown local lock")
            if capsule.capsule_id in self.closures:
                raise MosaicError("cannot abandon a closed capsule")
            self.capsules[capsule.capsule_id] = capsule
            self.locks[key] = (capsule.capsule_id, capsule.attempt, "ABANDON")
        return self._sign_receipt(member, capsule, status)

    def collect_accept_receipts(self, capsule: Capsule) -> tuple[WitnessReceipt, ...]:
        receipts = []
        for member_id in sorted(self.members):
            try:
                receipt = self.witness_receipt(member_id, capsule, "ACCEPT")
            except ConflictDetected:
                continue
            if self.verify_receipt(receipt):
                receipts.append(receipt)
        return tuple(receipts)

    def verify_closure(self, capsule: Capsule, closure: ClosureProof) -> bool:
        if (
            closure.capsule_id != capsule.capsule_id
            or closure.predecessor_id != capsule.predecessor_id
            or closure.epoch != capsule.epoch
            or closure.attempt != capsule.attempt
        ):
            return False
        unique = {receipt.witness_id: receipt for receipt in closure.receipts}
        if tuple(sorted(unique)) != tuple(sorted(closure.signer_ids)):
            return False
        valid = all(
            self.verify_receipt(receipt)
            and receipt.status == "ACCEPT"
            and receipt.capsule_id == capsule.capsule_id
            for receipt in unique.values()
        )
        weight = sum(self.members[item].weight for item in unique if item in self.members)
        expected_proof_id = digest(
            {
                "protocol": "MOSAIC/CLOSURE/v0.1",
                "capsule_id": capsule.capsule_id,
                "predecessor_id": capsule.predecessor_id,
                "epoch": capsule.epoch,
                "attempt": capsule.attempt,
                "receipts": [item.receipt_id for item in sorted(unique.values(), key=lambda item: item.witness_id)],
            }
        )
        return valid and weight >= self.threshold and expected_proof_id == closure.proof_id

    def register_closure(self, capsule: Capsule, closure: ClosureProof) -> None:
        if not self.verify_closure(capsule, closure):
            raise ClosureInvalid("invalid closure proof")
        if any(
            evidence.predecessor_id == capsule.predecessor_id
            for evidence in self.conflict_evidence.values()
        ):
            raise ClosureInvalid("predecessor has conflict evidence")
        existing = self.closures.get(capsule.capsule_id)
        if existing is not None:
            return
        self.closures[capsule.capsule_id] = closure

    def close(self, capsule: Capsule, receipts: tuple[WitnessReceipt, ...] | None = None) -> ClosureProof:
        self.validate_capsule(capsule)
        receipts = receipts or self.collect_accept_receipts(capsule)
        unique = {receipt.witness_id: receipt for receipt in receipts}
        valid = tuple(
            receipt
            for receipt in unique.values()
            if self.verify_receipt(receipt)
            and receipt.status == "ACCEPT"
            and receipt.capsule_id == capsule.capsule_id
        )
        weight = sum(self.members[receipt.witness_id].weight for receipt in valid)
        if weight < self.threshold:
            raise ClosureInvalid(f"insufficient closure weight: {weight} < {self.threshold}")
        if any(
            evidence.predecessor_id == capsule.predecessor_id
            for evidence in self.conflict_evidence.values()
        ):
            raise ClosureInvalid("predecessor has conflict evidence")
        closure = ClosureProof.create(valid)
        self.register_closure(capsule, closure)
        return closure

    def collect_abandon_receipts(self, capsule: Capsule) -> tuple[WitnessReceipt, ...]:
        receipts = []
        for member_id in sorted(self.members):
            try:
                receipt = self.witness_receipt(member_id, capsule, "ABANDON")
            except MosaicError:
                continue
            if self.verify_receipt(receipt):
                receipts.append(receipt)
        return tuple(receipts)

    def abandon(self, capsule: Capsule, receipts: tuple[WitnessReceipt, ...] | None = None) -> AbandonProof:
        if capsule.capsule_id in self.closures:
            raise ClosureInvalid("cannot abandon a closed capsule")
        receipts = receipts or self.collect_abandon_receipts(capsule)
        unique = {receipt.witness_id: receipt for receipt in receipts}
        valid = tuple(
            receipt
            for receipt in unique.values()
            if self.verify_receipt(receipt)
            and receipt.status == "ABANDON"
            and receipt.capsule_id == capsule.capsule_id
        )
        weight = sum(self.members[receipt.witness_id].weight for receipt in valid)
        if weight < self.threshold:
            raise ClosureInvalid(f"insufficient abandon weight: {weight} < {self.threshold}")
        proof = AbandonProof.create(valid)
        self.abandons[capsule.capsule_id] = proof
        return proof

    def apply(self, capsule: Capsule, closure: ClosureProof) -> StateSeal:
        if closure.capsule_id != capsule.capsule_id:
            raise ClosureInvalid("closure belongs to another capsule")
        if not self.verify_closure(capsule, closure):
            raise ClosureInvalid("closure was not verified")
        if capsule.capsule_id not in self.closures:
            self.register_closure(capsule, closure)
        predecessor = self.known_seals.get(capsule.predecessor_id)
        if predecessor is None:
            raise ClosureInvalid("predecessor not found")
        current = self.current_seals.get(predecessor.resource_id)
        if current is None:
            raise ClosureInvalid("resource state not found")
        if current.seal_id != capsule.predecessor_id:
            if (
                current.version == predecessor.version + 1
                and current.state_root == capsule.successor_root
                and current.capability_hash == digest(capsule.capsule_id)
            ):
                return current
            raise ClosureInvalid("predecessor is not current")
        next_seal = StateSeal(
            resource_id=current.resource_id,
            epoch=current.epoch,
            version=current.version + 1,
            state_root=capsule.successor_root,
            capability_hash=digest(capsule.capsule_id),
            owner=capsule.client_id,
        )
        self.current_seals[current.resource_id] = next_seal
        self.known_seals[next_seal.seal_id] = next_seal
        return next_seal

    def apply_execution(
        self,
        capsule: Capsule,
        closure: ClosureProof,
        transaction: object,
        executor: object,
    ) -> tuple[StateSeal, object, object]:
        executor_state = dict(executor.state)
        executor_nonces = dict(executor.nonces)
        executor_receipts = dict(executor.receipts)
        try:
            receipt, binding = executor.execute_for_capsule(transaction, capsule, closure, self)
            seal = self.apply(capsule, closure)
            if seal.state_root != receipt.post_state_root:
                raise ClosureInvalid("applied seal does not match execution receipt")
            return seal, receipt, binding
        except Exception:
            executor.state = executor_state
            executor.nonces = executor_nonces
            executor.receipts = executor_receipts
            raise

    def bundle_closure(self, bundle_id: str, closures: tuple[ClosureProof, ...]) -> BundleClosure:
        if not closures:
            raise ClosureInvalid("empty bundle")
        if any(closure.capsule_id not in self.closures for closure in closures):
            raise ClosureInvalid("bundle contains unknown closure")
        return BundleClosure.create(bundle_id, closures)

    def apply_bundle(
        self,
        bundle: BundleClosure,
        entries: tuple[tuple[Capsule, ClosureProof], ...],
    ) -> tuple[StateSeal, ...]:
        if not entries or bundle.bundle_id == "":
            raise ClosureInvalid("invalid bundle application")
        closures = tuple(closure for _, closure in entries)
        if tuple(sorted(item.proof_id for item in closures)) != tuple(sorted(bundle.closure_ids)):
            raise ClosureInvalid("bundle closure does not cover entries")
        for capsule, closure in entries:
            if self.closures.get(capsule.capsule_id) != closure:
                raise ClosureInvalid("bundle contains unregistered closure")
            if closure.capsule_id != capsule.capsule_id:
                raise ClosureInvalid("bundle closure mismatch")
            if not self.verify_closure(capsule, closure):
                raise ClosureInvalid("bundle contains invalid closure")
            if not any(seal.seal_id == capsule.predecessor_id for seal in self.current_seals.values()):
                raise ClosureInvalid("bundle predecessor not current")
        next_seals = []
        for capsule, _ in entries:
            current = next(seal for seal in self.current_seals.values() if seal.seal_id == capsule.predecessor_id)
            next_seals.append(
                StateSeal(
                    resource_id=current.resource_id,
                    epoch=current.epoch,
                    version=current.version + 1,
                    state_root=capsule.successor_root,
                    capability_hash=digest(capsule.capsule_id),
                    owner=capsule.client_id,
                )
            )
        for seal in next_seals:
            self.current_seals[seal.resource_id] = seal
            self.known_seals[seal.seal_id] = seal
        return tuple(next_seals)
