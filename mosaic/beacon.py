"""Durable beacon round coordinator for MOSAIC testnet."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from ccd_nexus.crypto import KeyPair, canonical_bytes, digest

from .economics import SettlementLedger
from .membership import (
    MembershipError,
    MembershipManager,
    RandomnessCommitment,
    RandomnessReveal,
)
from .randomness import RandomnessIncentiveError, RandomnessIncentiveManager, RandomnessRoundSettlement


class BeaconRoundError(ValueError):
    pass


def commitment_to_wire(item: RandomnessCommitment) -> dict:
    return {
        "validator_id": item.validator_id,
        "epoch": item.epoch,
        "round": item.round,
        "commitment": item.commitment,
        "signature": item.signature.hex(),
    }


def commitment_from_wire(data: dict) -> RandomnessCommitment:
    return RandomnessCommitment(
        validator_id=data["validator_id"],
        epoch=int(data["epoch"]),
        round=int(data["round"]),
        commitment=data["commitment"],
        signature=bytes.fromhex(data["signature"]),
    )


def reveal_to_wire(item: RandomnessReveal) -> dict:
    return {
        "validator_id": item.validator_id,
        "epoch": item.epoch,
        "round": item.round,
        "secret": item.secret.hex(),
        "commitment": item.commitment,
        "signature": item.signature.hex(),
    }


def reveal_from_wire(data: dict) -> RandomnessReveal:
    return RandomnessReveal(
        validator_id=data["validator_id"],
        epoch=int(data["epoch"]),
        round=int(data["round"]),
        secret=bytes.fromhex(data["secret"]),
        commitment=data["commitment"],
        signature=bytes.fromhex(data["signature"]),
    )


@dataclass
class BeaconRoundCoordinator:
    membership: MembershipManager
    settlement: SettlementLedger
    store: object | None = None

    def __post_init__(self) -> None:
        self.incentives = RandomnessIncentiveManager()
        self.commitments: dict[tuple[int, int, str], RandomnessCommitment] = {}
        self.reveals: dict[tuple[int, int, str], RandomnessReveal] = {}
        self.settlements: dict[tuple[int, int], RandomnessRoundSettlement] = {}

    def _key(self, epoch: int, round: int, validator_id: str) -> tuple[int, int, str]:
        return epoch, round, validator_id

    def submit_commitment(self, commitment: RandomnessCommitment) -> None:
        record = self.membership.snapshot.by_id().get(commitment.validator_id)
        if record is None:
            raise BeaconRoundError("commitment validator is not active")
        if commitment.epoch != self.membership.snapshot.epoch:
            raise BeaconRoundError("commitment epoch is not current")
        if commitment.round < 0 or not commitment.commitment:
            raise BeaconRoundError("invalid commitment round")
        if not KeyPair.verify(record.public_key, canonical_bytes(commitment.statement()), commitment.signature):
            raise BeaconRoundError("invalid commitment signature")
        key = self._key(commitment.epoch, commitment.round, commitment.validator_id)
        existing = self.commitments.get(key)
        if existing is not None and existing != commitment:
            raise BeaconRoundError("validator equivocated in commitment round")
        self.commitments[key] = commitment
        if self.store is not None:
            self.store.put("beacon_commitment", digest(commitment.statement()), commitment_to_wire(commitment))

    def submit_reveal(self, reveal: RandomnessReveal) -> None:
        record = self.membership.snapshot.by_id().get(reveal.validator_id)
        if record is None:
            raise BeaconRoundError("reveal validator is not active")
        key = self._key(reveal.epoch, reveal.round, reveal.validator_id)
        commitment = self.commitments.get(key)
        if commitment is None or commitment.commitment != reveal.commitment:
            raise BeaconRoundError("reveal has no matching commitment")
        if not KeyPair.verify(record.public_key, canonical_bytes(reveal.statement()), reveal.signature):
            raise BeaconRoundError("invalid reveal signature")
        if commitment.commitment != sha256(
            b"MOSAIC/RANDOMNESS-COMMIT/v1" + reveal.secret
        ).hexdigest():
            raise BeaconRoundError("reveal secret does not match commitment")
        existing = self.reveals.get(key)
        if existing is not None and existing != reveal:
            raise BeaconRoundError("validator equivocated in reveal round")
        self.reveals[key] = reveal
        if self.store is not None:
            self.store.put("beacon_reveal", digest(reveal.statement()), reveal_to_wire(reveal))

    def finalize(self, round: int, *, reveal_reward: int = 1, non_reveal_penalty: int = 1) -> RandomnessRoundSettlement:
        epoch = self.membership.snapshot.epoch
        key = (epoch, round)
        if key in self.settlements:
            return self.settlements[key]
        commitments = [item for (item_epoch, item_round, _), item in self.commitments.items() if item_epoch == epoch and item_round == round]
        reveals = [item for (item_epoch, item_round, _), item in self.reveals.items() if item_epoch == epoch and item_round == round]
        if not commitments:
            raise BeaconRoundError("cannot finalize empty beacon round")
        try:
            settlement = self.incentives.settle_round(
                self.membership,
                self.settlement,
                commitments,
                reveals,
                self.membership.validator_bonds,
                round=round,
                reveal_reward=reveal_reward,
                non_reveal_penalty=non_reveal_penalty,
            )
        except RandomnessIncentiveError as exc:
            raise BeaconRoundError(str(exc)) from exc
        self.settlements[key] = settlement
        if self.store is not None:
            self.settlement.persist(self.store)
            self.store.put(
                "beacon_round",
                settlement.settlement_id,
                {
                    "epoch": settlement.epoch,
                    "round": settlement.round,
                    "mode": settlement.beacon.mode,
                    "proof_id": settlement.beacon.proof_id,
                    "beacon_value": settlement.beacon.beacon_value.hex(),
                    "committed_ids": list(settlement.committed_ids),
                    "revealed_ids": list(settlement.revealed_ids),
                    "non_revealed_ids": list(settlement.non_revealed_ids),
                    "reward_event_ids": list(settlement.reward_event_ids),
                    "penalty_event_ids": list(settlement.penalty_event_ids),
                    "membership_root": self.membership.snapshot.root,
                    "settlement_root": self.settlement.state_root,
                },
                event=True,
            )
        return settlement
