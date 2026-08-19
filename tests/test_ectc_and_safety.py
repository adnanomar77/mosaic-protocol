from dataclasses import replace

import pytest

from ccd_nexus import KeyPair
from mosaic import (
    ConflictDetected,
    ECTCStatus,
    Member,
    MosaicProtocol,
    TransitionOutcome,
    unweighted_honest_intersection,
    unweighted_quorum_size,
    weighted_honest_intersection,
    weighted_quorum_threshold,
)
from mosaic.model import Capsule


def make_protocol(size=4):
    members = {f"w{i}": Member(f"w{i}", KeyPair.generate(), weight=1) for i in range(size)}
    return MosaicProtocol(members), KeyPair.generate()


def test_ectc_closed_requires_successor_seal_and_closure_proof():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    capsule = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="next")
    closure = protocol.close(capsule)

    assert protocol.transition_outcome(capsule) is None
    successor = protocol.apply(capsule, closure)
    outcome = protocol.transition_outcome(capsule)

    assert successor.seal_id == outcome.successor_seal_id
    assert outcome.status is ECTCStatus.CLOSED
    assert outcome.is_evidence_complete()


def test_ectc_conflict_retains_conflict_evidence():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    first = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="a")
    second = Capsule.create(
        client=client,
        predecessor=predecessor,
        successor_root="b",
        rule_id="identity-transition",
        rule_witness="valid",
    )
    protocol.witness_receipt("w0", first, "ACCEPT")
    with pytest.raises(ConflictDetected):
        protocol.witness_receipt("w0", second, "ACCEPT")
    outcome = protocol.transition_outcome(second)
    assert outcome.status is ECTCStatus.CONFLICT
    assert outcome.evidence_ids
    assert outcome.is_evidence_complete()


def test_ectc_abandoned_retains_abandon_proof():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    capsule = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="timeout")
    abandon = protocol.abandon(capsule)
    outcome = protocol.transition_outcome(capsule)
    assert abandon.proof_id in outcome.evidence_ids
    assert outcome.status is ECTCStatus.ABANDONED
    assert outcome.is_evidence_complete()


def test_unweighted_model_a_honest_intersection():
    assert unweighted_quorum_size(4) == 3
    assert unweighted_honest_intersection(4, {0, 1, 2}, {1, 2, 3}, {0})
    assert not unweighted_honest_intersection(4, {0, 1}, {2, 3}, {0})


def test_weighted_model_b_honest_intersection():
    weights = {"a": 4, "b": 3, "c": 2, "d": 1}
    assert weighted_quorum_threshold(weights) == 7
    assert weighted_honest_intersection(weights, {"a", "b"}, {"a", "c", "d"}, {"d"})
    assert not weighted_honest_intersection(weights, {"a", "b"}, {"c", "d"}, {"d"})
