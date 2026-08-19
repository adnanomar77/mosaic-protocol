import pytest

from ccd_nexus import KeyPair
from mosaic.membership import AdmissionRequest, MembershipError, MembershipManager


def test_stake_is_not_inflated_by_multiple_keys_with_fixed_budget():
    manager = MembershipManager(b"genesis", minimum_stake=10)
    keys = [KeyPair.generate() for _ in range(10)]
    for index, key in enumerate(keys):
        manager.admit(
            AdmissionRequest.create(
                applicant=key,
                validator_id=f"v{index}",
                stake=10,
                deposit_id=f"deposit-{index}",
                requested_epoch=0,
            )
        )
    assert manager.snapshot.total_stake == 100
    assert len(manager.snapshot.by_id()) == 10


def test_deposit_reuse_and_duplicate_id_are_rejected():
    manager = MembershipManager(b"genesis", minimum_stake=10)
    key = KeyPair.generate()
    request = AdmissionRequest.create(key, "v0", 10, "deposit-0", 0)
    manager.admit(request)
    with pytest.raises(MembershipError, match="deposit"):
        manager.admit(AdmissionRequest.create(KeyPair.generate(), "v1", 10, "deposit-0", 0))
    with pytest.raises(MembershipError, match="id"):
        manager.admit(AdmissionRequest.create(KeyPair.generate(), "v0", 10, "deposit-1", 0))


def test_committee_selection_is_deterministic_and_verifiable():
    manager = MembershipManager(b"genesis", minimum_stake=1)
    for index, stake in enumerate((5, 2, 1, 1)):
        key = KeyPair.generate()
        manager.admit(AdmissionRequest.create(key, f"v{index}", stake, f"deposit-{index}", 0))
    proof = manager.select_committee(3)
    assert manager.verify_selection(proof)
    assert proof.selected_ids == manager.select_committee(3).selected_ids


def test_epoch_change_invalidates_old_selection_proof():
    manager = MembershipManager(b"genesis", minimum_stake=1)
    key = KeyPair.generate()
    manager.admit(AdmissionRequest.create(key, "v0", 5, "deposit-0", 0))
    old = manager.select_committee(1)
    manager.advance_epoch()
    assert not manager.verify_selection(old)


def test_invalid_signature_is_rejected():
    manager = MembershipManager(b"genesis", minimum_stake=1)
    key = KeyPair.generate()
    request = AdmissionRequest.create(key, "v0", 5, "deposit-0", 0)
    tampered = request.__class__(
        validator_id=request.validator_id,
        public_key=request.public_key,
        stake=99,
        deposit_id=request.deposit_id,
        requested_epoch=request.requested_epoch,
        applicant_signature=request.applicant_signature,
    )
    with pytest.raises(MembershipError, match="signature"):
        manager.admit(tampered)
