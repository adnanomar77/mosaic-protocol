"""Permissionless membership, stake lifecycle, slashing and committee selection."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from ccd_nexus.crypto import KeyPair, canonical_bytes, digest


class MembershipError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatorRecord:
    validator_id: str
    public_key: bytes
    stake: int
    deposit_id: str
    active: bool = True
    locked_until_epoch: int = 0
    jailed: bool = False


@dataclass(frozen=True)
class StakeBond:
    bond_id: str
    owner: str
    owner_public_key: bytes
    amount: int
    asset: str
    activation_epoch: int
    unlock_epoch: int
    owner_signature: bytes

    @classmethod
    def create(
        cls,
        owner: KeyPair,
        bond_id: str,
        amount: int,
        asset: str,
        activation_epoch: int,
        unlock_epoch: int,
    ) -> "StakeBond":
        unsigned = {
            "protocol": "MOSAIC/STAKE-BOND/v1",
            "bond_id": bond_id,
            "owner": owner.identity,
            "owner_public_key": owner.public_key.hex(),
            "amount": amount,
            "asset": asset,
            "activation_epoch": activation_epoch,
            "unlock_epoch": unlock_epoch,
        }
        return cls(
            bond_id=bond_id,
            owner=owner.identity,
            owner_public_key=owner.public_key,
            amount=amount,
            asset=asset,
            activation_epoch=activation_epoch,
            unlock_epoch=unlock_epoch,
            owner_signature=owner.sign(canonical_bytes(unsigned)),
        )

    def statement(self) -> dict:
        return {
            "protocol": "MOSAIC/STAKE-BOND/v1",
            "bond_id": self.bond_id,
            "owner": self.owner,
            "owner_public_key": self.owner_public_key.hex(),
            "amount": self.amount,
            "asset": self.asset,
            "activation_epoch": self.activation_epoch,
            "unlock_epoch": self.unlock_epoch,
        }

    def verify(self) -> bool:
        return (
            self.amount > 0
            and self.activation_epoch >= 0
            and self.unlock_epoch >= self.activation_epoch
            and KeyPair.verify(
                self.owner_public_key,
                canonical_bytes(self.statement()),
                self.owner_signature,
            )
        )


@dataclass(frozen=True)
class RandomnessCommitment:
    validator_id: str
    epoch: int
    round: int
    commitment: str
    signature: bytes

    @classmethod
    def create(
        cls,
        validator: KeyPair,
        epoch: int,
        round: int,
        secret: bytes,
        validator_id: str | None = None,
    ) -> "RandomnessCommitment":
        member_id = validator.identity if validator_id is None else validator_id
        commitment = sha256(b"MOSAIC/RANDOMNESS-COMMIT/v1" + secret).hexdigest()
        statement = {
            "protocol": "MOSAIC/RANDOMNESS-COMMIT/v1",
            "validator_id": member_id,
            "epoch": epoch,
            "round": round,
            "commitment": commitment,
        }
        return cls(
            validator_id=member_id,
            epoch=epoch,
            round=round,
            commitment=commitment,
            signature=validator.sign(canonical_bytes(statement)),
        )

    def statement(self) -> dict:
        return {
            "protocol": "MOSAIC/RANDOMNESS-COMMIT/v1",
            "validator_id": self.validator_id,
            "epoch": self.epoch,
            "round": self.round,
            "commitment": self.commitment,
        }


@dataclass(frozen=True)
class RandomnessReveal:
    validator_id: str
    epoch: int
    round: int
    secret: bytes
    commitment: str
    signature: bytes

    @classmethod
    def create(
        cls,
        validator: KeyPair,
        epoch: int,
        round: int,
        secret: bytes,
        commitment: str,
        validator_id: str | None = None,
    ) -> "RandomnessReveal":
        member_id = validator.identity if validator_id is None else validator_id
        statement = {
            "protocol": "MOSAIC/RANDOMNESS-REVEAL/v1",
            "validator_id": member_id,
            "epoch": epoch,
            "round": round,
            "secret": secret.hex(),
            "commitment": commitment,
        }
        return cls(
            validator_id=member_id,
            epoch=epoch,
            round=round,
            secret=secret,
            commitment=commitment,
            signature=validator.sign(canonical_bytes(statement)),
        )

    def statement(self) -> dict:
        return {
            "protocol": "MOSAIC/RANDOMNESS-REVEAL/v1",
            "validator_id": self.validator_id,
            "epoch": self.epoch,
            "round": self.round,
            "secret": self.secret.hex(),
            "commitment": self.commitment,
        }


@dataclass(frozen=True)
class RandomnessBeacon:
    epoch: int
    round: int
    reveal_ids: tuple[str, ...]
    beacon_value: bytes
    proof_id: str
    mode: str = "reveal"
    commitment_ids: tuple[str, ...] = ()

    def verify(self) -> bool:
        if self.mode == "reveal":
            if not self.reveal_ids:
                return False
            payload = {
                "protocol": "MOSAIC/RANDOMNESS-BEACON/v1",
                "epoch": self.epoch,
                "round": self.round,
                "reveal_ids": self.reveal_ids,
                "beacon_value": self.beacon_value.hex(),
            }
        elif self.mode == "commitment-fallback":
            if not self.commitment_ids:
                return False
            payload = {
                "protocol": "MOSAIC/RANDOMNESS-FALLBACK/v1",
                "epoch": self.epoch,
                "round": self.round,
                "commitment_ids": self.commitment_ids,
                "beacon_value": self.beacon_value.hex(),
            }
        else:
            return False
        return self.proof_id == digest(payload)


@dataclass(frozen=True)
class AdmissionRequest:
    validator_id: str
    public_key: bytes
    stake: int
    deposit_id: str
    requested_epoch: int
    applicant_signature: bytes
    bond_id: str | None = None

    @classmethod
    def create(
        cls,
        applicant: KeyPair,
        validator_id: str,
        stake: int,
        deposit_id: str,
        requested_epoch: int,
        bond_id: str | None = None,
    ) -> "AdmissionRequest":
        statement = {
            "protocol": "MOSAIC/ADMISSION/v1",
            "validator_id": validator_id,
            "public_key": applicant.public_key.hex(),
            "stake": stake,
            "deposit_id": deposit_id,
            "requested_epoch": requested_epoch,
            "bond_id": bond_id,
        }
        return cls(
            validator_id=validator_id,
            public_key=applicant.public_key,
            stake=stake,
            deposit_id=deposit_id,
            requested_epoch=requested_epoch,
            applicant_signature=applicant.sign(canonical_bytes(statement)),
            bond_id=bond_id,
        )

    def statement(self) -> dict:
        return {
            "protocol": "MOSAIC/ADMISSION/v1",
            "validator_id": self.validator_id,
            "public_key": self.public_key.hex(),
            "stake": self.stake,
            "deposit_id": self.deposit_id,
            "requested_epoch": self.requested_epoch,
            "bond_id": self.bond_id,
        }

    def verify(self) -> bool:
        return KeyPair.verify(
            self.public_key,
            canonical_bytes(self.statement()),
            self.applicant_signature,
        )


@dataclass(frozen=True)
class AdmissionCertificate:
    request_digest: str
    epoch: int
    approver_ids: tuple[str, ...]
    signatures: tuple[bytes, ...]
    certificate_id: str


@dataclass(frozen=True)
class ExitCertificate:
    validator_id: str
    epoch: int
    approver_ids: tuple[str, ...]
    certificate_id: str
    unlock_epoch: int = 0


@dataclass(frozen=True)
class WithdrawalReceipt:
    validator_id: str
    deposit_id: str
    amount: int
    unlock_epoch: int
    receipt_id: str


@dataclass(frozen=True)
class SlashEvidence:
    offender_id: str
    epoch: int
    first_digest: str
    second_digest: str
    witness_ids: tuple[str, ...]
    evidence_id: str

    @classmethod
    def create(
        cls,
        offender_id: str,
        epoch: int,
        first_object: object,
        second_object: object,
        witness_ids: Iterable[str] = (),
    ) -> "SlashEvidence":
        first_digest = digest(first_object)
        second_digest = digest(second_object)
        if first_digest == second_digest:
            raise MembershipError("slash evidence objects must conflict")
        witnesses = tuple(sorted(set(witness_ids)))
        evidence_id = digest(
            {
                "protocol": "MOSAIC/SLASH-EVIDENCE/v1",
                "offender_id": offender_id,
                "epoch": epoch,
                "first_digest": first_digest,
                "second_digest": second_digest,
                "witness_ids": witnesses,
            }
        )
        return cls(offender_id, epoch, first_digest, second_digest, witnesses, evidence_id)

    def verify(self) -> bool:
        return (
            bool(self.offender_id)
            and self.epoch >= 0
            and self.first_digest != self.second_digest
            and self.evidence_id
            == digest(
                {
                    "protocol": "MOSAIC/SLASH-EVIDENCE/v1",
                    "offender_id": self.offender_id,
                    "epoch": self.epoch,
                    "first_digest": self.first_digest,
                    "second_digest": self.second_digest,
                    "witness_ids": self.witness_ids,
                }
            )
        )


@dataclass(frozen=True)
class MembershipSnapshot:
    epoch: int
    seed: bytes
    validators: tuple[ValidatorRecord, ...]
    root: str

    @property
    def total_stake(self) -> int:
        return sum(item.stake for item in self.validators if item.active and not item.jailed)

    @property
    def threshold(self) -> int:
        return (2 * self.total_stake) // 3 + 1

    def by_id(self) -> dict[str, ValidatorRecord]:
        return {
            item.validator_id: item
            for item in self.validators
            if item.active and not item.jailed
        }

    def verify(self) -> bool:
        active = tuple(
            sorted(
                (item for item in self.validators if item.active and not item.jailed),
                key=lambda x: x.validator_id,
            )
        )
        expected = digest(
            {
                "protocol": "MOSAIC/MEMBERSHIP-ROOT/v1",
                "epoch": self.epoch,
                "seed": self.seed.hex(),
                "validators": [
                    {
                        "validator_id": item.validator_id,
                        "public_key": item.public_key.hex(),
                        "stake": item.stake,
                        "deposit_id": item.deposit_id,
                        "locked_until_epoch": item.locked_until_epoch,
                        "jailed": item.jailed,
                    }
                    for item in active
                ],
            }
        )
        return expected == self.root and all(item.stake > 0 for item in active)


@dataclass(frozen=True)
class CommitteeSelectionProof:
    epoch: int
    committee_size: int
    selected_ids: tuple[str, ...]
    selected_tickets: tuple[tuple[str, int], ...]
    seed: bytes
    proof_id: str
    beacon_id: str | None = None


class MembershipManager:
    """Reference membership state machine with stake bonds and deterministic penalties."""

    def __init__(
        self,
        genesis_seed: bytes,
        minimum_stake: int = 1,
        max_tickets_per_validator: int = 10_000,
        withdrawal_delay: int = 2,
        settlement: object | None = None,
    ):
        self.genesis_seed = genesis_seed
        self.minimum_stake = minimum_stake
        self.max_tickets_per_validator = max_tickets_per_validator
        self.withdrawal_delay = withdrawal_delay
        self.settlement = settlement
        self._validator_bonds: dict[str, str] = {}
        self._records: dict[str, ValidatorRecord] = {}
        self._deposits: set[str] = set()
        self._bonds: dict[str, StakeBond] = {}
        self._slash_history: dict[str, SlashEvidence] = {}
        self._non_reveal_history: set[str] = set()
        self._epoch = 0
        self._seed = genesis_seed
        self._snapshot = self._build_snapshot()

    @property
    def snapshot(self) -> MembershipSnapshot:
        return self._snapshot

    @property
    def slash_history(self) -> dict[str, SlashEvidence]:
        return dict(self._slash_history)

    @property
    def validator_bonds(self) -> dict[str, str]:
        return dict(self._validator_bonds)

    def stake_of(self, validator_id: str) -> int:
        record = self._records.get(validator_id)
        if record is None:
            raise MembershipError("unknown validator")
        return record.stake

    def restore_admission(self, request: AdmissionRequest, bond: StakeBond) -> None:
        if not request.verify() or not bond.verify():
            raise MembershipError("cannot restore invalid admission")
        if request.stake < self.minimum_stake or request.bond_id != bond.bond_id:
            raise MembershipError("restored admission does not satisfy stake policy")
        if request.validator_id in self._records or request.deposit_id in self._deposits:
            raise MembershipError("restored admission is duplicated")
        if bond.owner_public_key != request.public_key or bond.amount != request.stake:
            raise MembershipError("restored bond does not match admission")
        self._bonds[bond.bond_id] = bond
        self._validator_bonds[request.validator_id] = bond.bond_id
        self._records[request.validator_id] = ValidatorRecord(
            validator_id=request.validator_id,
            public_key=request.public_key,
            stake=request.stake,
            deposit_id=request.deposit_id,
            active=True,
        )
        self._deposits.add(request.deposit_id)
        self._snapshot = self._build_snapshot()

    def admit(
        self,
        request: AdmissionRequest,
        approver_ids: Iterable[str] = (),
        bond: StakeBond | None = None,
    ) -> AdmissionCertificate:
        if not request.verify():
            raise MembershipError("invalid applicant signature")
        if request.stake < self.minimum_stake:
            raise MembershipError("stake below minimum")
        if request.requested_epoch < self._epoch:
            raise MembershipError("admission request is stale")
        if self.settlement is not None and bond is None:
            raise MembershipError("settlement-backed admission requires a stake bond")
        if request.validator_id in self._records:
            raise MembershipError("validator id already exists")
        if request.deposit_id in self._deposits:
            raise MembershipError("deposit cannot be reused")
        if bond is not None:
            if not bond.verify():
                raise MembershipError("invalid stake bond")
            if bond.bond_id != (request.bond_id or request.deposit_id):
                raise MembershipError("admission bond does not match request")
            if bond.owner_public_key != request.public_key or bond.amount != request.stake:
                raise MembershipError("stake bond owner or amount mismatch")
            if bond.activation_epoch > self._epoch:
                raise MembershipError("stake bond is not active yet")
            if self.settlement is not None:
                self.settlement.bond(bond, current_epoch=self._epoch)
            self._bonds[bond.bond_id] = bond
            self._validator_bonds[request.validator_id] = bond.bond_id
        record = ValidatorRecord(
            validator_id=request.validator_id,
            public_key=request.public_key,
            stake=request.stake,
            deposit_id=request.deposit_id,
            active=True,
        )
        self._records[request.validator_id] = record
        self._deposits.add(request.deposit_id)
        self._snapshot = self._build_snapshot()
        approvers = tuple(sorted(set(approver_ids)))
        request_digest = digest({**request.statement(), "signature": request.applicant_signature.hex()})
        return AdmissionCertificate(
            request_digest=request_digest,
            epoch=self._epoch,
            approver_ids=approvers,
            signatures=tuple(),
            certificate_id=digest(
                {
                    "protocol": "MOSAIC/ADMISSION-CERT/v1",
                    "request": request_digest,
                    "epoch": self._epoch,
                    "approvers": approvers,
                }
            ),
        )

    def exit(self, validator_id: str, epoch: int | None = None) -> ExitCertificate:
        if validator_id not in self._records:
            raise MembershipError("unknown validator")
        if epoch is not None and epoch < self._epoch:
            raise MembershipError("stale exit epoch")
        record = self._records[validator_id]
        bond_id = self._validator_bonds.get(validator_id)
        if self.settlement is not None:
            if bond_id is None:
                raise MembershipError("validator has no settlement bond")
            self.settlement.request_unbond(
                bond_id,
                current_epoch=self._epoch,
                delay=self.withdrawal_delay,
            )
        unlock_epoch = self._epoch + self.withdrawal_delay
        self._records[validator_id] = ValidatorRecord(
            validator_id=record.validator_id,
            public_key=record.public_key,
            stake=record.stake,
            deposit_id=record.deposit_id,
            active=False,
            locked_until_epoch=unlock_epoch,
            jailed=record.jailed,
        )
        self._snapshot = self._build_snapshot()
        return ExitCertificate(
            validator_id=validator_id,
            epoch=self._epoch,
            approver_ids=tuple(),
            certificate_id=digest(
                {
                    "protocol": "MOSAIC/EXIT/v1",
                    "validator": validator_id,
                    "epoch": self._epoch,
                    "unlock_epoch": unlock_epoch,
                }
            ),
            unlock_epoch=unlock_epoch,
        )

    def withdraw(self, validator_id: str, current_epoch: int | None = None) -> WithdrawalReceipt:
        if validator_id not in self._records:
            raise MembershipError("unknown validator")
        record = self._records[validator_id]
        epoch = self._epoch if current_epoch is None else current_epoch
        bond_id = self._validator_bonds.get(validator_id)
        if self.settlement is not None:
            if bond_id is None:
                raise MembershipError("validator has no settlement bond")
            try:
                self.settlement.withdraw(bond_id, current_epoch=epoch)
            except ValueError as exc:
                raise MembershipError(str(exc)) from exc
        if record.active:
            raise MembershipError("validator is still active")
        if epoch < record.locked_until_epoch:
            raise MembershipError("withdrawal delay has not elapsed")
        receipt = WithdrawalReceipt(
            validator_id=validator_id,
            deposit_id=record.deposit_id,
            amount=record.stake,
            unlock_epoch=record.locked_until_epoch,
            receipt_id=digest(
                {
                    "protocol": "MOSAIC/WITHDRAWAL/v1",
                    "validator": validator_id,
                    "deposit": record.deposit_id,
                    "amount": record.stake,
                    "unlock_epoch": record.locked_until_epoch,
                }
            ),
        )
        del self._records[validator_id]
        self._validator_bonds.pop(validator_id, None)
        self._snapshot = self._build_snapshot()
        return receipt

    def slash(self, evidence: SlashEvidence, penalty: int | None = None) -> ValidatorRecord:
        if not evidence.verify():
            raise MembershipError("invalid slash evidence")
        if evidence.evidence_id in self._slash_history:
            raise MembershipError("slash evidence already applied")
        record = self._records.get(evidence.offender_id)
        if record is None:
            raise MembershipError("unknown slashing offender")
        bond_id = self._validator_bonds.get(evidence.offender_id)
        if self.settlement is not None:
            if bond_id is None:
                raise MembershipError("validator has no settlement bond")
            self.settlement.slash(
                bond_id,
                record.stake if penalty is None else penalty,
                epoch=evidence.epoch,
                evidence_id=evidence.evidence_id,
            )
        if evidence.epoch > self._epoch:
            raise MembershipError("slash evidence is from a future epoch")
        amount = record.stake if penalty is None else penalty
        if amount <= 0:
            raise MembershipError("slash penalty must be positive")
        new_stake = max(0, record.stake - amount)
        updated = ValidatorRecord(
            validator_id=record.validator_id,
            public_key=record.public_key,
            stake=new_stake,
            deposit_id=record.deposit_id,
            active=new_stake > 0 and not record.jailed,
            locked_until_epoch=record.locked_until_epoch,
            jailed=new_stake == 0 or record.jailed,
        )
        self._records[evidence.offender_id] = updated
        self._slash_history[evidence.evidence_id] = evidence
        self._snapshot = self._build_snapshot()
        return updated

    def penalize_non_reveal(
        self,
        validator_id: str,
        *,
        epoch: int,
        round: int,
        penalty: int,
    ) -> ValidatorRecord:
        if epoch != self._epoch:
            raise MembershipError("non-reveal epoch is not current")
        if penalty <= 0:
            raise MembershipError("non-reveal penalty must be positive")
        record = self._records.get(validator_id)
        if record is None:
            raise MembershipError("unknown non-revealing validator")
        evidence_id = digest(
            {
                "protocol": "MOSAIC/NON-REVEAL/v1",
                "validator_id": validator_id,
                "epoch": epoch,
                "round": round,
            }
        )
        if evidence_id in self._non_reveal_history:
            raise MembershipError("non-reveal penalty already applied")
        new_stake = max(0, record.stake - penalty)
        updated = ValidatorRecord(
            validator_id=record.validator_id,
            public_key=record.public_key,
            stake=new_stake,
            deposit_id=record.deposit_id,
            active=new_stake > 0 and record.active,
            locked_until_epoch=record.locked_until_epoch,
            jailed=new_stake == 0 or record.jailed,
        )
        self._records[validator_id] = updated
        self._non_reveal_history.add(evidence_id)
        self._snapshot = self._build_snapshot()
        return updated

    def advance_epoch(self) -> MembershipSnapshot:
        previous_root = self._snapshot.root
        self._epoch += 1
        self._seed = sha256(
            b"MOSAIC/EPOCH-SEED/v1"
            + self._seed
            + bytes.fromhex(previous_root)
            + self._epoch.to_bytes(8, "big")
        ).digest()
        self._snapshot = self._build_snapshot()
        return self._snapshot

    def _build_snapshot(self) -> MembershipSnapshot:
        validators = tuple(sorted(self._records.values(), key=lambda item: item.validator_id))
        root = digest(
            {
                "protocol": "MOSAIC/MEMBERSHIP-ROOT/v1",
                "epoch": self._epoch,
                "seed": self._seed.hex(),
                "validators": [
                    {
                        "validator_id": item.validator_id,
                        "public_key": item.public_key.hex(),
                        "stake": item.stake,
                        "deposit_id": item.deposit_id,
                        "locked_until_epoch": item.locked_until_epoch,
                        "jailed": item.jailed,
                    }
                    for item in validators
                    if item.active and not item.jailed
                ],
            }
        )
        return MembershipSnapshot(self._epoch, self._seed, validators, root)

    def make_beacon(
        self,
        commitments: Iterable[RandomnessCommitment],
        reveals: Iterable[RandomnessReveal],
        round: int = 0,
    ) -> RandomnessBeacon:
        commitment_map = {item.validator_id: item for item in commitments}
        reveal_map = {item.validator_id: item for item in reveals}
        if not reveal_map:
            raise MembershipError("randomness beacon has no reveals")
        active = self._snapshot.by_id()
        reveal_weight = 0
        for validator_id, reveal in reveal_map.items():
            commitment = commitment_map.get(validator_id)
            record = active.get(validator_id)
            if commitment is None or record is None:
                raise MembershipError("randomness reveal is not backed by active commitment")
            if commitment.epoch != self._epoch or reveal.epoch != self._epoch:
                raise MembershipError("randomness epoch mismatch")
            if commitment.round != round or reveal.round != round:
                raise MembershipError("randomness round mismatch")
            if not KeyPair.verify(record.public_key, canonical_bytes(commitment.statement()), commitment.signature):
                raise MembershipError("invalid randomness commitment signature")
            if not KeyPair.verify(record.public_key, canonical_bytes(reveal.statement()), reveal.signature):
                raise MembershipError("invalid randomness reveal signature")
            expected_commitment = sha256(b"MOSAIC/RANDOMNESS-COMMIT/v1" + reveal.secret).hexdigest()
            if expected_commitment != commitment.commitment or reveal.commitment != commitment.commitment:
                raise MembershipError("randomness reveal does not open commitment")
            reveal_weight += record.stake
        if reveal_weight < self.snapshot.threshold:
            raise MembershipError("insufficient randomness reveal weight")
        reveal_ids = tuple(sorted(reveal_map))
        ordered_reveals = tuple(reveal_map[item].secret for item in reveal_ids)
        beacon_value = sha256(
            b"MOSAIC/RANDOMNESS-BEACON/v1"
            + self._seed
            + round.to_bytes(8, "big")
            + b"".join(ordered_reveals)
        ).digest()
        proof_id = digest(
            {
                "protocol": "MOSAIC/RANDOMNESS-BEACON/v1",
                "epoch": self._epoch,
                "round": round,
                "reveal_ids": reveal_ids,
                "beacon_value": beacon_value.hex(),
            }
        )
        return RandomnessBeacon(self._epoch, round, reveal_ids, beacon_value, proof_id, "reveal", ())

    def make_fallback_beacon(
        self,
        commitments: Iterable[RandomnessCommitment],
        round: int = 0,
    ) -> RandomnessBeacon:
        commitment_map = {item.validator_id: item for item in commitments}
        if not commitment_map:
            raise MembershipError("randomness fallback has no commitments")
        active = self._snapshot.by_id()
        committed_weight = 0
        for validator_id, commitment in commitment_map.items():
            record = active.get(validator_id)
            if record is None:
                raise MembershipError("fallback commitment is not from active validator")
            if commitment.epoch != self._epoch or commitment.round != round:
                raise MembershipError("fallback commitment epoch or round mismatch")
            if not KeyPair.verify(record.public_key, canonical_bytes(commitment.statement()), commitment.signature):
                raise MembershipError("invalid fallback commitment signature")
            committed_weight += record.stake
        if committed_weight < self.snapshot.threshold:
            raise MembershipError("insufficient commitment weight for randomness fallback")
        commitment_ids = tuple(sorted(commitment_map))
        ordered_commitments = tuple(commitment_map[item].commitment for item in commitment_ids)
        beacon_value = sha256(
            b"MOSAIC/RANDOMNESS-FALLBACK/v1"
            + self._seed
            + round.to_bytes(8, "big")
            + b"".join(bytes.fromhex(item) for item in ordered_commitments)
        ).digest()
        proof_id = digest(
            {
                "protocol": "MOSAIC/RANDOMNESS-FALLBACK/v1",
                "epoch": self._epoch,
                "round": round,
                "commitment_ids": commitment_ids,
                "beacon_value": beacon_value.hex(),
            }
        )
        return RandomnessBeacon(
            self._epoch,
            round,
            (),
            beacon_value,
            proof_id,
            "commitment-fallback",
            commitment_ids,
        )

    def _tickets(self, snapshot: MembershipSnapshot, seed: bytes | None = None) -> list[tuple[int, str, int]]:
        selection_seed = snapshot.seed if seed is None else seed
        tickets: list[tuple[int, str, int]] = []
        for validator in snapshot.validators:
            if not validator.active or validator.jailed:
                continue
            ticket_count = min(validator.stake, self.max_tickets_per_validator)
            for slot in range(ticket_count):
                score = int.from_bytes(
                    sha256(
                        b"MOSAIC/TICKET/v1"
                        + selection_seed
                        + validator.validator_id.encode("utf-8")
                        + slot.to_bytes(8, "big")
                    ).digest(),
                    "big",
                )
                tickets.append((score, validator.validator_id, slot))
        return tickets

    def select_committee(
        self,
        committee_size: int,
        beacon: RandomnessBeacon | None = None,
    ) -> CommitteeSelectionProof:
        if committee_size <= 0:
            raise MembershipError("committee size must be positive")
        if beacon is not None and (not beacon.verify() or beacon.epoch != self._epoch):
            raise MembershipError("invalid randomness beacon")
        selection_seed = self._seed if beacon is None else beacon.beacon_value
        tickets = sorted(self._tickets(self._snapshot, selection_seed))
        selected = tickets[: min(committee_size, len(tickets))]
        selected_ids = tuple(dict.fromkeys(item[1] for item in selected))
        selected_tickets = tuple((item[1], item[2]) for item in selected)
        proof_id = digest(
            {
                "protocol": "MOSAIC/COMMITTEE/v1",
                "epoch": self._epoch,
                "size": committee_size,
                "selected": selected_tickets,
                "seed": selection_seed.hex(),
                "beacon_id": None if beacon is None else beacon.proof_id,
            }
        )
        return CommitteeSelectionProof(
            epoch=self._epoch,
            committee_size=committee_size,
            selected_ids=selected_ids,
            selected_tickets=selected_tickets,
            seed=selection_seed,
            proof_id=proof_id,
            beacon_id=None if beacon is None else beacon.proof_id,
        )

    def verify_selection(
        self,
        proof: CommitteeSelectionProof,
        beacon: RandomnessBeacon | None = None,
    ) -> bool:
        if proof.epoch != self._snapshot.epoch:
            return False
        if proof.beacon_id is None:
            if proof.seed != self._snapshot.seed:
                return False
        else:
            if beacon is None or not beacon.verify() or beacon.proof_id != proof.beacon_id:
                return False
            if proof.seed != beacon.beacon_value or beacon.epoch != proof.epoch:
                return False
        tickets = sorted(self._tickets(self._snapshot, proof.seed))
        expected = tuple((item[1], item[2]) for item in tickets[: min(proof.committee_size, len(tickets))])
        if expected != proof.selected_tickets:
            return False
        expected_ids = tuple(dict.fromkeys(item[0] for item in expected))
        return expected_ids == proof.selected_ids and digest(
            {
                "protocol": "MOSAIC/COMMITTEE/v1",
                "epoch": proof.epoch,
                "size": proof.committee_size,
                "selected": proof.selected_tickets,
                "seed": proof.seed.hex(),
                "beacon_id": proof.beacon_id,
            }
        ) == proof.proof_id
