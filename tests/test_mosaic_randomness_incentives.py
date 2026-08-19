import pytest

from ccd_nexus import KeyPair
from mosaic import (
    AdmissionRequest,
    MembershipManager,
    RandomnessCommitment,
    RandomnessIncentiveError,
    RandomnessIncentiveManager,
    RandomnessReveal,
    SettlementLedger,
    StakeBond,
)


def make_round():
    ledger = SettlementLedger()
    manager = MembershipManager(b"seed", minimum_stake=1, settlement=ledger)
    keys = []
    bonds = {}
    for index in range(4):
        key = KeyPair.generate()
        keys.append(key)
        validator_id = f"v{index}"
        bond_id = f"bond-{index}"
        ledger.fund(key.identity, 10, source_id=f"fund-{index}")
        request = AdmissionRequest.create(key, validator_id, 10, f"deposit-{index}", 0, bond_id=bond_id)
        bond = StakeBond.create(key, bond_id, 10, "MOSAIC", 0, 3)
        manager.admit(request, bond=bond)
        bonds[validator_id] = bond_id
    ledger.fund(ledger.treasury, 20, source_id="reward-fund")
    return manager, ledger, keys, bonds


def test_reveals_are_rewarded_and_missing_reveal_is_slashed():
    manager, ledger, keys, bonds = make_round()
    commitments = []
    reveals = []
    for index, key in enumerate(keys):
        secret = f"round-secret-{index}".encode()
        commitment = RandomnessCommitment.create(key, 0, 1, secret, validator_id=f"v{index}")
        commitments.append(commitment)
        if index < 3:
            reveals.append(RandomnessReveal.create(key, 0, 1, secret, commitment.commitment, validator_id=f"v{index}"))
    settlement = RandomnessIncentiveManager().settle_round(
        manager,
        ledger,
        commitments,
        reveals,
        bonds,
        round=1,
        reveal_reward=2,
        non_reveal_penalty=1,
    )
    assert settlement.beacon.mode == "reveal"
    assert settlement.revealed_ids == ("v0", "v1", "v2")
    assert settlement.non_revealed_ids == ("v3",)
    assert len(settlement.reward_event_ids) == 3
    assert ledger.bonds["bond-3"].amount == 9
    assert manager.stake_of("v3") == 9
    assert ledger.audit()


def test_fallback_beacon_preserves_liveness_when_reveals_are_below_quorum():
    manager, ledger, keys, bonds = make_round()
    commitments = []
    reveals = []
    for index, key in enumerate(keys):
        secret = f"fallback-secret-{index}".encode()
        commitment = RandomnessCommitment.create(key, 0, 2, secret, validator_id=f"v{index}")
        commitments.append(commitment)
        if index == 0:
            reveals.append(RandomnessReveal.create(key, 0, 2, secret, commitment.commitment, validator_id="v0"))
    settlement = RandomnessIncentiveManager().settle_round(
        manager,
        ledger,
        commitments,
        reveals,
        bonds,
        round=2,
        reveal_reward=0,
        non_reveal_penalty=1,
    )
    assert settlement.beacon.mode == "commitment-fallback"
    assert settlement.beacon.verify()
    assert len(settlement.non_revealed_ids) == 3
    assert all(manager.stake_of(f"v{i}") == 9 for i in range(1, 4))


def test_fallback_requires_commitment_quorum():
    manager, ledger, keys, bonds = make_round()
    commitments = []
    for index, key in enumerate(keys[:2]):
        secret = f"insufficient-{index}".encode()
        commitments.append(RandomnessCommitment.create(key, 0, 3, secret, validator_id=f"v{index}"))
    with pytest.raises(RandomnessIncentiveError, match="insufficient commitment"):
        RandomnessIncentiveManager().settle_round(
            manager,
            ledger,
            commitments,
            [],
            bonds,
            round=3,
            reveal_reward=0,
            non_reveal_penalty=1,
        )
