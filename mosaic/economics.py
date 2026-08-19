"""Deterministic economic settlement for MOSAIC validator stake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ccd_nexus.crypto import digest

from .membership import StakeBond


class SettlementError(ValueError):
    pass


@dataclass(frozen=True)
class BondPosition:
    bond_id: str
    owner: str
    asset: str
    amount: int
    unlock_epoch: int
    active: bool = True
    unbonding: bool = False


@dataclass(frozen=True)
class SettlementEvent:
    event_id: str
    kind: str
    epoch: int
    account: str
    amount: int
    asset: str
    related_id: str
    metadata: tuple[tuple[str, str], ...] = ()


class SettlementLedger:
    """A replay-safe, deterministic accounting ledger for stake settlement.

    The ledger is intentionally independent from an external token chain. It
    can be backed by one later, but it already enforces conservation, delayed
    withdrawal, reward funding, reporter rewards, and idempotent event IDs.
    """

    def __init__(
        self,
        asset: str = "MOSAIC",
        treasury: str = "mosaic:treasury",
        reporter_reward_bps: int = 1000,
    ):
        if not asset or not treasury:
            raise SettlementError("asset and treasury are required")
        if not 0 <= reporter_reward_bps <= 10_000:
            raise SettlementError("reporter reward must be between 0 and 10000 bps")
        self.asset = asset
        self.treasury = treasury
        self.reporter_reward_bps = reporter_reward_bps
        self.balances: dict[str, int] = {}
        self.bonds: dict[str, BondPosition] = {}
        self.events: dict[str, SettlementEvent] = {}
        self.slash_evidence_ids: set[str] = set()
        self.settled_reward_epochs: set[int] = set()

    def balance_of(self, account: str) -> int:
        return self.balances.get(account, 0)

    @property
    def state_root(self) -> str:
        return digest(
            {
                "protocol": "MOSAIC/SETTLEMENT-STATE/v1",
                "asset": self.asset,
                "balances": {key: self.balances[key] for key in sorted(self.balances)},
                "bonds": {
                    key: {
                        "owner": item.owner,
                        "asset": item.asset,
                        "amount": item.amount,
                        "unlock_epoch": item.unlock_epoch,
                        "active": item.active,
                        "unbonding": item.unbonding,
                    }
                    for key, item in sorted(self.bonds.items())
                },
                "events": sorted(self.events),
                "slash_evidence_ids": sorted(self.slash_evidence_ids),
                "settled_reward_epochs": sorted(self.settled_reward_epochs),
            }
        )

    def to_dict(self) -> dict:
        return {
            "protocol": "MOSAIC/SETTLEMENT-STATE/v1",
            "asset": self.asset,
            "treasury": self.treasury,
            "reporter_reward_bps": self.reporter_reward_bps,
            "balances": dict(self.balances),
            "bonds": {
                key: {
                    "bond_id": item.bond_id,
                    "owner": item.owner,
                    "asset": item.asset,
                    "amount": item.amount,
                    "unlock_epoch": item.unlock_epoch,
                    "active": item.active,
                    "unbonding": item.unbonding,
                }
                for key, item in self.bonds.items()
            },
            "events": {
                key: {
                    "event_id": item.event_id,
                    "kind": item.kind,
                    "epoch": item.epoch,
                    "account": item.account,
                    "amount": item.amount,
                    "asset": item.asset,
                    "related_id": item.related_id,
                    "metadata": list(item.metadata),
                }
                for key, item in self.events.items()
            },
            "slash_evidence_ids": sorted(self.slash_evidence_ids),
            "settled_reward_epochs": sorted(self.settled_reward_epochs),
            "state_root": self.state_root,
        }

    def persist(self, store: object) -> None:
        store.put("settlement_state", "ledger", self.to_dict(), event=False)

    @classmethod
    def from_store(cls, store: object) -> "SettlementLedger":
        payload = store.get("settlement_state", "ledger")
        if payload is None:
            raise SettlementError("settlement ledger state is missing")
        ledger = cls(
            asset=payload["asset"],
            treasury=payload["treasury"],
            reporter_reward_bps=int(payload["reporter_reward_bps"]),
        )
        ledger.balances = {key: int(value) for key, value in payload["balances"].items()}
        ledger.bonds = {
            key: BondPosition(
                bond_id=value["bond_id"],
                owner=value["owner"],
                asset=value["asset"],
                amount=int(value["amount"]),
                unlock_epoch=int(value["unlock_epoch"]),
                active=bool(value["active"]),
                unbonding=bool(value["unbonding"]),
            )
            for key, value in payload["bonds"].items()
        }
        ledger.events = {
            key: SettlementEvent(
                event_id=value["event_id"],
                kind=value["kind"],
                epoch=int(value["epoch"]),
                account=value["account"],
                amount=int(value["amount"]),
                asset=value["asset"],
                related_id=value["related_id"],
                metadata=tuple(tuple(item) for item in value.get("metadata", [])),
            )
            for key, value in payload["events"].items()
        }
        ledger.slash_evidence_ids = set(payload["slash_evidence_ids"])
        ledger.settled_reward_epochs = set(int(item) for item in payload["settled_reward_epochs"])
        if not ledger.audit() or ledger.state_root != payload["state_root"]:
            raise SettlementError("settlement ledger state root mismatch")
        return ledger

    def audit(self) -> bool:
        return (
            all(amount >= 0 for amount in self.balances.values())
            and all(
                position.amount >= 0
                and position.asset == self.asset
                and not (position.active and position.unbonding)
                for position in self.bonds.values()
            )
            and all(event.amount >= 0 and event.asset == self.asset for event in self.events.values())
        )

    def fund(self, account: str, amount: int, *, epoch: int = 0, source_id: str | None = None) -> SettlementEvent:
        if amount <= 0 or not account:
            raise SettlementError("funding amount and account are invalid")
        related = source_id or digest({"account": account, "amount": amount, "epoch": epoch})
        event = self._event("FUND", epoch, account, amount, related, (("source", "external"),))
        self._credit(account, amount)
        return event

    def bond(self, bond: StakeBond, *, current_epoch: int = 0) -> SettlementEvent:
        if not bond.verify():
            raise SettlementError("invalid stake bond")
        if bond.asset != self.asset:
            raise SettlementError("stake asset does not match ledger")
        if bond.activation_epoch > current_epoch:
            raise SettlementError("bond activation epoch has not arrived")
        if bond.bond_id in self.bonds:
            raise SettlementError("bond already settled")
        self._debit(bond.owner, bond.amount)
        self.bonds[bond.bond_id] = BondPosition(
            bond_id=bond.bond_id,
            owner=bond.owner,
            asset=bond.asset,
            amount=bond.amount,
            unlock_epoch=bond.unlock_epoch,
        )
        return self._event("BOND", current_epoch, bond.owner, bond.amount, bond.bond_id)

    def request_unbond(self, bond_id: str, *, current_epoch: int, delay: int) -> SettlementEvent:
        position = self._position(bond_id)
        if delay < 0 or not position.active or position.unbonding:
            raise SettlementError("bond cannot enter unbonding")
        updated = BondPosition(
            bond_id=position.bond_id,
            owner=position.owner,
            asset=position.asset,
            amount=position.amount,
            unlock_epoch=max(position.unlock_epoch, current_epoch + delay),
            active=False,
            unbonding=True,
        )
        self.bonds[bond_id] = updated
        return self._event("UNBOND_REQUEST", current_epoch, position.owner, 0, bond_id)

    def withdraw(self, bond_id: str, *, current_epoch: int) -> SettlementEvent:
        position = self._position(bond_id)
        if position.active:
            raise SettlementError("bond is still active; request unbonding first")
        if not position.unbonding or current_epoch < position.unlock_epoch:
            raise SettlementError("withdrawal delay has not elapsed")
        amount = position.amount
        del self.bonds[bond_id]
        self._credit(position.owner, amount)
        return self._event("WITHDRAW", current_epoch, position.owner, amount, bond_id)

    def slash(
        self,
        bond_id: str,
        amount: int,
        *,
        epoch: int,
        evidence_id: str,
        reporter: str | None = None,
    ) -> tuple[SettlementEvent, ...]:
        if amount <= 0 or not evidence_id:
            raise SettlementError("slash amount and evidence are required")
        if evidence_id in self.slash_evidence_ids:
            raise SettlementError("slash evidence already settled")
        position = self._position(bond_id)
        penalty = min(amount, position.amount)
        reporter_amount = penalty * self.reporter_reward_bps // 10_000 if reporter else 0
        treasury_amount = penalty - reporter_amount
        self.slash_evidence_ids.add(evidence_id)
        self.bonds[bond_id] = BondPosition(
            bond_id=position.bond_id,
            owner=position.owner,
            asset=position.asset,
            amount=position.amount - penalty,
            unlock_epoch=position.unlock_epoch,
            active=position.active and position.amount > penalty,
            unbonding=position.unbonding,
        )
        events = [self._event("SLASH", epoch, position.owner, penalty, evidence_id)]
        self._credit(self.treasury, treasury_amount)
        if reporter_amount:
            self._credit(reporter or "", reporter_amount)
            events.append(self._event("REPORTER_REWARD", epoch, reporter or "", reporter_amount, evidence_id))
        return tuple(events)

    def charge_fee(self, payer: str, amount: int, *, epoch: int, tx_id: str) -> SettlementEvent:
        if amount <= 0 or not tx_id:
            raise SettlementError("fee amount and tx id are required")
        self._debit(payer, amount)
        self._credit(self.treasury, amount)
        return self._event("FEE", epoch, payer, amount, tx_id)

    def distribute_rewards(
        self,
        epoch: int,
        total_reward: int,
        weights: Mapping[str, int],
    ) -> tuple[SettlementEvent, ...]:
        if epoch in self.settled_reward_epochs:
            raise SettlementError("epoch rewards already settled")
        if total_reward <= 0 or not weights or any(value <= 0 for value in weights.values()):
            raise SettlementError("invalid reward distribution")
        total_weight = sum(weights.values())
        self._debit(self.treasury, total_reward)
        events: list[SettlementEvent] = []
        distributed = 0
        ordered = tuple(sorted(weights.items()))
        for index, (bond_id, weight) in enumerate(ordered):
            position = self._position(bond_id)
            amount = total_reward - distributed if index == len(ordered) - 1 else total_reward * weight // total_weight
            distributed += amount
            self._credit(position.owner, amount)
            events.append(self._event("REWARD", epoch, position.owner, amount, bond_id))
        self.settled_reward_epochs.add(epoch)
        return tuple(events)

    def _position(self, bond_id: str) -> BondPosition:
        try:
            return self.bonds[bond_id]
        except KeyError as exc:
            raise SettlementError("unknown bond") from exc

    def _credit(self, account: str, amount: int) -> None:
        if not account or amount < 0:
            raise SettlementError("invalid credit")
        self.balances[account] = self.balance_of(account) + amount

    def _debit(self, account: str, amount: int) -> None:
        if amount < 0 or self.balance_of(account) < amount:
            raise SettlementError("insufficient settlement balance")
        self.balances[account] = self.balance_of(account) - amount

    def _event(
        self,
        kind: str,
        epoch: int,
        account: str,
        amount: int,
        related_id: str,
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> SettlementEvent:
        event_id = digest(
            {
                "protocol": "MOSAIC/SETTLEMENT-EVENT/v1",
                "kind": kind,
                "epoch": epoch,
                "account": account,
                "amount": amount,
                "asset": self.asset,
                "related_id": related_id,
                "metadata": metadata,
            }
        )
        if event_id in self.events:
            raise SettlementError("duplicate settlement event")
        event = SettlementEvent(event_id, kind, epoch, account, amount, self.asset, related_id, metadata)
        self.events[event_id] = event
        return event
