import pytest

from ccd_nexus import KeyPair
from mosaic import SettlementError, SettlementLedger, StakeBond


def funded_bond(ledger, key, bond_id="bond-1", amount=100):
    ledger.fund(key.identity, amount, source_id=f"fund-{bond_id}")
    bond = StakeBond.create(key, bond_id, amount, "MOSAIC", 0, 3)
    ledger.bond(bond, current_epoch=0)
    return bond


def test_stake_settlement_locks_then_withdraws_after_delay():
    key = KeyPair.generate()
    ledger = SettlementLedger()
    bond = funded_bond(ledger, key)
    assert ledger.balance_of(key.identity) == 0
    with pytest.raises(SettlementError, match="unbonding"):
        ledger.withdraw(bond.bond_id, current_epoch=3)
    ledger.request_unbond(bond.bond_id, current_epoch=1, delay=2)
    with pytest.raises(SettlementError, match="delay"):
        ledger.withdraw(bond.bond_id, current_epoch=2)
    receipt = ledger.withdraw(bond.bond_id, current_epoch=3)
    assert receipt.kind == "WITHDRAW"
    assert ledger.balance_of(key.identity) == 100
    assert ledger.audit()


def test_slashing_is_replay_safe_and_distributes_reporter_reward():
    key = KeyPair.generate()
    reporter = KeyPair.generate()
    ledger = SettlementLedger(reporter_reward_bps=1000)
    bond = funded_bond(ledger, key, amount=100)
    events = ledger.slash(
        bond.bond_id,
        40,
        epoch=1,
        evidence_id="evidence-1",
        reporter=reporter.identity,
    )
    assert events[0].kind == "SLASH"
    assert ledger.bonds[bond.bond_id].amount == 60
    assert ledger.balance_of(reporter.identity) == 4
    with pytest.raises(SettlementError, match="already settled"):
        ledger.slash(bond.bond_id, 1, epoch=1, evidence_id="evidence-1")
    assert ledger.audit()


def test_fees_and_epoch_rewards_are_conservation_checked():
    key1 = KeyPair.generate()
    key2 = KeyPair.generate()
    ledger = SettlementLedger()
    bond1 = funded_bond(ledger, key1, "bond-1", 40)
    bond2 = funded_bond(ledger, key2, "bond-2", 60)
    ledger.fund(ledger.treasury, 10, source_id="reward-fund")
    ledger.fund(key1.identity, 5, source_id="fee-fund")
    ledger.charge_fee(key1.identity, 5, epoch=1, tx_id="tx-1")
    rewards = ledger.distribute_rewards(1, 10, {bond1.bond_id: 1, bond2.bond_id: 3})
    assert sum(item.amount for item in rewards) == 10
    assert ledger.balance_of(key1.identity) == 2
    assert ledger.balance_of(key2.identity) == 8
    with pytest.raises(SettlementError, match="already settled"):
        ledger.distribute_rewards(1, 1, {bond1.bond_id: 1})
    assert ledger.audit()


def test_bond_requires_funded_balance_and_matching_asset():
    key = KeyPair.generate()
    ledger = SettlementLedger(asset="MOSAIC")
    bond = StakeBond.create(key, "bond-unfunded", 10, "MOSAIC", 0, 2)
    with pytest.raises(SettlementError, match="insufficient"):
        ledger.bond(bond)
    ledger.fund(key.identity, 10, source_id="fund-matching")
    wrong_asset = StakeBond.create(key, "bond-wrong", 10, "OTHER", 0, 2)
    with pytest.raises(SettlementError, match="does not match"):
        ledger.bond(wrong_asset)
