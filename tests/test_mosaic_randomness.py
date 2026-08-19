import pytest

from ccd_nexus import KeyPair
from mosaic.membership import (
    AdmissionRequest,
    MembershipError,
    MembershipManager,
    RandomnessCommitment,
    RandomnessReveal,
)


def make_manager():
    manager = MembershipManager(b"genesis", minimum_stake=1)
    keys = []
    for index in range(4):
        key = KeyPair.generate()
        keys.append(key)
        manager.admit(AdmissionRequest.create(key, f"v{index}", 1, f"deposit-{index}", 0))
    return manager, keys


def test_commit_reveal_beacon_requires_quorum_and_verifies():
    manager, keys = make_manager()
    commitments = []
    reveals = []
    for index, key in enumerate(keys[:3]):
        secret = f"secret-{index}".encode()
        commitment = RandomnessCommitment.create(key, 0, 7, secret, validator_id=f"v{index}")
        commitments.append(commitment)
        reveals.append(RandomnessReveal.create(key, 0, 7, secret, commitment.commitment, validator_id=f"v{index}"))
    beacon = manager.make_beacon(commitments, reveals, round=7)
    assert beacon.verify()
    proof = manager.select_committee(3, beacon=beacon)
    assert manager.verify_selection(proof, beacon=beacon)
    assert not manager.verify_selection(proof)


def test_randomness_reveal_must_open_signed_commitment():
    manager, keys = make_manager()
    commitment = RandomnessCommitment.create(keys[0], 0, 0, b"committed", validator_id="v0")
    bad_reveal = RandomnessReveal.create(keys[0], 0, 0, b"different", commitment.commitment, validator_id="v0")
    with pytest.raises(MembershipError, match="open commitment"):
        manager.make_beacon([commitment], [bad_reveal], round=0)


def test_randomness_requires_two_thirds_reveal_weight():
    manager, keys = make_manager()
    secret = b"only-one"
    commitment = RandomnessCommitment.create(keys[0], 0, 0, secret, validator_id="v0")
    reveal = RandomnessReveal.create(keys[0], 0, 0, secret, commitment.commitment, validator_id="v0")
    with pytest.raises(MembershipError, match="insufficient"):
        manager.make_beacon([commitment], [reveal], round=0)


def test_old_beacon_cannot_select_new_epoch_committee():
    manager, keys = make_manager()
    commitments = []
    reveals = []
    for index, key in enumerate(keys[:3]):
        secret = f"epoch0-{index}".encode()
        commitment = RandomnessCommitment.create(key, 0, 0, secret, validator_id=f"v{index}")
        commitments.append(commitment)
        reveals.append(RandomnessReveal.create(key, 0, 0, secret, commitment.commitment, validator_id=f"v{index}"))
    beacon = manager.make_beacon(commitments, reveals)
    manager.advance_epoch()
    with pytest.raises(MembershipError, match="invalid randomness beacon"):
        manager.select_committee(2, beacon=beacon)
