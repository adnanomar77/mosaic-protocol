import pytest

from ccd_nexus import KeyPair
from mosaic import AdmissionRequest, MembershipError, MembershipManager, SettlementLedger, SlashEvidence, StakeBond


def make_integrated_manager():
    key = KeyPair.generate()
    ledger = SettlementLedger()
    ledger.fund(key.identity, 100, source_id="fund-validator")
    manager = MembershipManager(b"genesis", minimum_stake=1, withdrawal_delay=2, settlement=ledger)
    request = AdmissionRequest.create(key, "v0", 100, "deposit-0", 0, bond_id="bond-0")
    bond = StakeBond.create(key, "bond-0", 100, "MOSAIC", 0, 2)
    manager.admit(request, bond=bond)
    return manager, ledger, key


def test_membership_settlement_admission_exit_and_withdraw_are_atomic():
    manager, ledger, key = make_integrated_manager()
    assert ledger.balance_of(key.identity) == 0
    certificate = manager.exit("v0")
    assert certificate.unlock_epoch == 2
    with pytest.raises(MembershipError, match="delay"):
        manager.withdraw("v0", current_epoch=1)
    manager.advance_epoch()
    manager.advance_epoch()
    receipt = manager.withdraw("v0", current_epoch=2)
    assert receipt.amount == 100
    assert ledger.balance_of(key.identity) == 100
    assert ledger.audit()


def test_membership_slash_updates_settlement_bond():
    manager, ledger, _ = make_integrated_manager()
    evidence = SlashEvidence.create("v0", 0, {"claim": "a"}, {"claim": "b"})
    updated = manager.slash(evidence)
    assert updated.stake == 0
    assert ledger.bonds["bond-0"].amount == 0
    assert ledger.bonds["bond-0"].active is False
    assert ledger.audit()
