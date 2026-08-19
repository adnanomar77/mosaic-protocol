import pytest

from ccd_nexus import KeyPair
from mosaic import (
    AdmissionCoordinator,
    AdmissionRequest,
    DurableStore,
    OnboardingError,
    SettlementLedger,
    StakeBond,
    admission_from_wire,
    admission_to_wire,
    bond_from_wire,
    bond_to_wire,
    MembershipManager,
)


def make_onboarding(tmp_path):
    applicant = KeyPair.generate()
    ledger = SettlementLedger()
    ledger.fund(applicant.identity, 20, source_id="onboarding-fund")
    membership = MembershipManager(b"testnet-genesis", minimum_stake=10, settlement=ledger)
    bond = StakeBond.create(applicant, "bond-onboard-0", 10, "MOSAIC", 0, 3)
    request = AdmissionRequest.create(applicant, "validator-new", 10, "deposit-new", 0, bond_id=bond.bond_id)
    store = DurableStore(tmp_path / "onboarding.sqlite")
    coordinator = AdmissionCoordinator(membership, ledger).bind_store(store)
    return applicant, ledger, membership, bond, request, store, coordinator


def test_onboarding_wire_round_trip_and_settlement(tmp_path):
    _, ledger, membership, bond, request, store, coordinator = make_onboarding(tmp_path)
    assert admission_from_wire(admission_to_wire(request)) == request
    assert bond_from_wire(bond_to_wire(bond)) == bond
    certificate = coordinator.admit(request, bond)
    assert certificate.epoch == 0
    assert membership.stake_of("validator-new") == 10
    assert ledger.bonds[bond.bond_id].amount == 10
    assert coordinator.onboarding_root
    assert store.get("onboarding", certificate.certificate_id)["membership_root"] == membership.snapshot.root
    assert ledger.audit()
    store.close()

    with DurableStore(tmp_path / "onboarding.sqlite") as reopened:
        restored_ledger = SettlementLedger.from_store(reopened)
        restored_membership = MembershipManager(b"testnet-genesis", minimum_stake=10, settlement=restored_ledger)
        restored = AdmissionCoordinator(restored_membership, restored_ledger).bind_store(reopened)
        assert restored.restore_from_store() == 1
        assert restored_membership.stake_of("validator-new") == 10
        assert restored.onboarding_root == coordinator.onboarding_root


def test_onboarding_rejects_insufficient_balance(tmp_path):
    applicant = KeyPair.generate()
    ledger = SettlementLedger()
    membership = MembershipManager(b"testnet-genesis", minimum_stake=10, settlement=ledger)
    bond = StakeBond.create(applicant, "bond-poor", 10, "MOSAIC", 0, 3)
    request = AdmissionRequest.create(applicant, "validator-poor", 10, "deposit-poor", 0, bond_id=bond.bond_id)
    store = DurableStore(tmp_path / "poor.sqlite")
    coordinator = AdmissionCoordinator(membership, ledger).bind_store(store)
    with pytest.raises(OnboardingError, match="insufficient"):
        coordinator.admit(request, bond)
    assert membership.snapshot.validators == ()
    store.close()
