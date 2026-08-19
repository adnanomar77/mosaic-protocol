"""Incentive settlement and fallback policy for randomness rounds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .economics import SettlementError, SettlementLedger
from .membership import (
    MembershipError,
    MembershipManager,
    RandomnessBeacon,
    RandomnessCommitment,
    RandomnessReveal,
)


class RandomnessIncentiveError(ValueError):
    pass


@dataclass(frozen=True)
class RandomnessRoundSettlement:
    epoch: int
    round: int
    beacon: RandomnessBeacon
    committed_ids: tuple[str, ...]
    revealed_ids: tuple[str, ...]
    non_revealed_ids: tuple[str, ...]
    reward_event_ids: tuple[str, ...]
    penalty_event_ids: tuple[str, ...]
    settlement_id: str


class RandomnessIncentiveManager:
    """Settles reveal rewards and non-reveal penalties for one round."""

    def settle_round(
        self,
        membership: MembershipManager,
        ledger: SettlementLedger,
        commitments: Iterable[RandomnessCommitment],
        reveals: Iterable[RandomnessReveal],
        validator_bonds: Mapping[str, str],
        *,
        round: int = 0,
        reveal_reward: int = 1,
        non_reveal_penalty: int = 1,
    ) -> RandomnessRoundSettlement:
        if reveal_reward < 0 or non_reveal_penalty < 0:
            raise RandomnessIncentiveError("incentive amounts cannot be negative")
        commitment_map = {item.validator_id: item for item in commitments}
        reveal_map = {item.validator_id: item for item in reveals}
        if not commitment_map:
            raise RandomnessIncentiveError("randomness round has no commitments")
        if not set(reveal_map).issubset(commitment_map):
            raise RandomnessIncentiveError("reveal is not backed by a commitment")
        active_ids = set(membership.snapshot.by_id())
        if not set(commitment_map).issubset(active_ids):
            raise RandomnessIncentiveError("commitment is not from active validator")
        if not set(commitment_map).issubset(validator_bonds):
            raise RandomnessIncentiveError("missing settlement bond mapping")
        if reveal_reward and ledger.balance_of(ledger.treasury) < reveal_reward * len(reveal_map):
            raise RandomnessIncentiveError("treasury cannot fund reveal rewards")

        try:
            reveal_weight = sum(membership.snapshot.by_id()[item].stake for item in reveal_map)
            if reveal_weight >= membership.snapshot.threshold:
                beacon = membership.make_beacon(commitment_map.values(), reveal_map.values(), round=round)
                non_revealed_ids = tuple(sorted(set(commitment_map) - set(reveal_map)))
            else:
                beacon = membership.make_fallback_beacon(commitment_map.values(), round=round)
                non_revealed_ids = tuple(sorted(set(commitment_map) - set(reveal_map)))
        except MembershipError as exc:
            raise RandomnessIncentiveError(str(exc)) from exc

        penalty_event_ids: list[str] = []
        for validator_id in non_revealed_ids:
            if non_reveal_penalty <= 0:
                continue
            bond_id = validator_bonds[validator_id]
            evidence_id = f"MOSAIC/NON-REVEAL/{membership.snapshot.epoch}/{round}/{validator_id}"
            try:
                events = ledger.slash(
                    bond_id,
                    non_reveal_penalty,
                    epoch=membership.snapshot.epoch,
                    evidence_id=evidence_id,
                )
            except SettlementError as exc:
                raise RandomnessIncentiveError(str(exc)) from exc
            try:
                membership.penalize_non_reveal(
                    validator_id,
                    epoch=membership.snapshot.epoch,
                    round=round,
                    penalty=non_reveal_penalty,
                )
            except MembershipError as exc:
                raise RandomnessIncentiveError(str(exc)) from exc
            penalty_event_ids.extend(item.event_id for item in events)

        reward_event_ids: list[str] = []
        if reveal_reward and reveal_map:
            try:
                reward_events = ledger.distribute_rewards(
                    membership.snapshot.epoch * 1_000_000 + round,
                    reveal_reward * len(reveal_map),
                    {validator_bonds[item]: 1 for item in reveal_map},
                )
            except SettlementError as exc:
                raise RandomnessIncentiveError(str(exc)) from exc
            reward_event_ids.extend(item.event_id for item in reward_events)

        settlement_id = f"MOSAIC/RANDOMNESS-SETTLEMENT/{membership.snapshot.epoch}/{round}"
        return RandomnessRoundSettlement(
            epoch=membership.snapshot.epoch,
            round=round,
            beacon=beacon,
            committed_ids=tuple(sorted(commitment_map)),
            revealed_ids=tuple(sorted(reveal_map)),
            non_revealed_ids=non_revealed_ids,
            reward_event_ids=tuple(reward_event_ids),
            penalty_event_ids=tuple(penalty_event_ids),
            settlement_id=settlement_id,
        )
