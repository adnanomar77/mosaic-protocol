import pytest

from ccd_nexus import KeyPair
from mosaic.membership import (
    AdmissionRequest,
    MembershipError,
    MembershipManager,
    SlashEvidence,
    StakeBond,
)


def test_stake_bond_is_bound_to_owner_and_admission_request():
    manager = MembershipManager(b"genesis", minimum_stake=10)
    key = KeyPair.generate()
    bond = StakeBond.create(key, "bond-0", 25, "MOSAIC", 0, 4)
    request = AdmissionRequest.create(key, "v0", 25, "deposit-0", 0, bond_id="bond-0")
    certificate = manager.admit(request, bond=bond)
    assert certificate.epoch == 0
    assert manager.stake_of("v0") == 25
    assert manager.snapshot.verify()


def test_invalid_bond_owner_or_amount_is_rejected():
    manager = MembershipManager(b"genesis", minimum_stake=1)
    key = KeyPair.generate()
    other = KeyPair.generate()
    bond = StakeBond.create(other, "bond-0", 10, "MOSAIC", 0, 2)
    request = AdmissionRequest.create(key, "v0", 10, "deposit-0", 0, bond_id="bond-0")
    with pytest.raises(MembershipError, match="owner"):
        manager.admit(request, bond=bond)


def test_exit_requires_withdrawal_delay():
    manager = MembershipManager(b"genesis", minimum_stake=1, withdrawal_delay=2)
    key = KeyPair.generate()
    manager.admit(AdmissionRequest.create(key, "v0", 10, "deposit-0", 0))
    exit_certificate = manager.exit("v0")
    assert not manager.snapshot.by_id()
    with pytest.raises(MembershipError, match="delay"):
        manager.withdraw("v0", current_epoch=exit_certificate.unlock_epoch - 1)
    receipt = manager.withdraw("v0", current_epoch=exit_certificate.unlock_epoch)
    assert receipt.amount == 10
    with pytest.raises(MembershipError, match="unknown"):
        manager.withdraw("v0", current_epoch=exit_certificate.unlock_epoch)


def test_valid_slash_reduces_stake_and_cannot_replay():
    manager = MembershipManager(b"genesis", minimum_stake=10)
    key = KeyPair.generate()
    manager.admit(AdmissionRequest.create(key, "v0", 20, "deposit-0", 0))
    evidence = SlashEvidence.create("v0", 0, {"capsule": "a"}, {"capsule": "b"}, ["w1"])
    updated = manager.slash(evidence, penalty=7)
    assert updated.stake == 13
    assert manager.snapshot.total_stake == 13
    with pytest.raises(MembershipError, match="already"):
        manager.slash(evidence, penalty=7)


def test_full_slash_jails_validator_and_removes_it_from_committee():
    manager = MembershipManager(b"genesis", minimum_stake=1)
    key = KeyPair.generate()
    manager.admit(AdmissionRequest.create(key, "v0", 5, "deposit-0", 0))
    evidence = SlashEvidence.create("v0", 0, "accept", "abandon")
    updated = manager.slash(evidence, penalty=5)
    assert updated.jailed is True
    assert updated.active is False
    assert manager.snapshot.total_stake == 0
    assert manager.select_committee(1).selected_ids == ()
