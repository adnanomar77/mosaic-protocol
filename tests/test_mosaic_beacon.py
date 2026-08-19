import pytest

from ccd_nexus import KeyPair
from mosaic import (
    BeaconRoundCoordinator,
    BeaconRoundError,
    DurableStore,
    MembershipManager,
    RandomnessCommitment,
    RandomnessReveal,
    SettlementLedger,
    StakeBond,
    AdmissionRequest,
)


def make_beacon(tmp_path):
    ledger = SettlementLedger()
    membership = MembershipManager(b"beacon-genesis", minimum_stake=1, settlement=ledger)
    keys = []
    for index in range(4):
        key = KeyPair.generate()
        keys.append(key)
        ledger.fund(key.identity, 10, source_id=f"fund-{index}")
        bond = StakeBond.create(key, f"beacon-bond-{index}", 10, "MOSAIC", 0, 3)
        request = AdmissionRequest.create(key, f"v{index}", 10, f"beacon-deposit-{index}", 0, bond_id=bond.bond_id)
        membership.admit(request, bond=bond)
    ledger.fund(ledger.treasury, 20, source_id="beacon-treasury")
    store = DurableStore(tmp_path / "beacon.sqlite")
    coordinator = BeaconRoundCoordinator(membership, ledger, store)
    return ledger, membership, keys, store, coordinator


def test_beacon_round_settles_reveals_and_persists(tmp_path):
    ledger, membership, keys, store, coordinator = make_beacon(tmp_path)
    commitments = []
    for index, key in enumerate(keys):
        secret = f"beacon-{index}".encode()
        commitment = RandomnessCommitment.create(key, 0, 0, secret, validator_id=f"v{index}")
        coordinator.submit_commitment(commitment)
        commitments.append((commitment, secret))
    for commitment, secret in commitments[:3]:
        coordinator.submit_reveal(
            RandomnessReveal.create(
                keys[int(commitment.validator_id[1:])],
                0,
                0,
                secret,
                commitment.commitment,
                validator_id=commitment.validator_id,
            )
        )
    result = coordinator.finalize(0, reveal_reward=1, non_reveal_penalty=1)
    assert result.beacon.verify()
    assert result.non_revealed_ids == ("v3",)
    assert ledger.bonds["beacon-bond-3"].amount == 9
    assert store.get("beacon_round", result.settlement_id)["proof_id"] == result.beacon.proof_id
    assert ledger.audit()
    store.close()


def test_beacon_fallback_keeps_liveness_when_reveal_weight_is_low(tmp_path):
    ledger, membership, keys, store, coordinator = make_beacon(tmp_path)
    for index, key in enumerate(keys):
        secret = f"fallback-{index}".encode()
        coordinator.submit_commitment(RandomnessCommitment.create(key, 0, 1, secret, validator_id=f"v{index}"))
    result = coordinator.finalize(1, reveal_reward=0, non_reveal_penalty=1)
    assert result.beacon.mode == "commitment-fallback"
    assert result.beacon.verify()
    assert set(result.non_revealed_ids) == {"v0", "v1", "v2", "v3"}
    store.close()


def test_beacon_rejects_equivocation_and_invalid_reveal(tmp_path):
    _, _, keys, store, coordinator = make_beacon(tmp_path)
    first = RandomnessCommitment.create(keys[0], 0, 2, b"one", validator_id="v0")
    second = RandomnessCommitment.create(keys[0], 0, 2, b"two", validator_id="v0")
    coordinator.submit_commitment(first)
    with pytest.raises(BeaconRoundError, match="equivocated"):
        coordinator.submit_commitment(second)
    with pytest.raises(BeaconRoundError, match="does not match"):
        coordinator.submit_reveal(RandomnessReveal.create(keys[0], 0, 2, b"wrong", first.commitment, validator_id="v0"))
    store.close()
