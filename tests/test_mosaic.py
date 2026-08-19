from dataclasses import replace

import pytest

from ccd_nexus import KeyPair
from mosaic import (
    BundleClosure,
    Capsule,
    ClosureInvalid,
    ConflictDetected,
    Member,
    MosaicProtocol,
)


def make_protocol(size=4):
    members = {
        f"w{index}": Member(f"w{index}", KeyPair.generate(), weight=1)
        for index in range(size)
    }
    return MosaicProtocol(members), KeyPair.generate()


def test_single_capsule_closes_and_applies_without_global_order():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    capsule = protocol.create_capsule(
        client=client,
        predecessor=predecessor,
        successor_root="state-1",
    )
    closure = protocol.close(capsule)
    assert protocol.verify_closure(capsule, closure)
    with pytest.raises(ClosureInvalid):
        protocol.apply(capsule, replace(closure, proof_id="tampered"))
    successor = protocol.apply(capsule, closure)
    assert successor.version == 1
    assert successor.state_root == "state-1"


def test_conflicting_successor_cannot_close_after_first_closure():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    first = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="state-1")
    first_closure = protocol.close(first)
    protocol.apply(first, first_closure)

    conflicting = Capsule.create(
        client=client,
        predecessor=predecessor,
        successor_root="state-evil",
        rule_id="identity-transition",
        rule_witness="valid",
        attempt=0,
    )
    with pytest.raises(ConflictDetected) as error:
        protocol.witness_receipt("w0", conflicting)
    assert error.value.evidence.predecessor_id == predecessor.seal_id
    assert protocol.conflict_evidence


def test_abandon_allows_a_new_attempt_without_rollback():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    abandoned = protocol.create_capsule(
        client=client,
        predecessor=predecessor,
        successor_root="state-timeout",
        attempt=0,
    )
    abandon = protocol.abandon(abandoned)
    assert abandon.attempt == 0

    retry = protocol.create_capsule(
        client=client,
        predecessor=predecessor,
        successor_root="state-retry",
        attempt=1,
    )
    closure = protocol.close(retry)
    successor = protocol.apply(retry, closure)
    assert successor.version == 1
    assert successor.state_root == "state-retry"


def test_bundle_is_all_or_nothing_at_apply_boundary():
    protocol, client = make_protocol()
    first = protocol.create_resource("a", owner=client.identity)
    second = protocol.create_resource("b", owner=client.identity)
    bundle_id = "bundle-1"
    capsule_a = protocol.create_capsule(
        client=client,
        predecessor=first,
        successor_root="a1",
        bundle_id=bundle_id,
    )
    capsule_b = protocol.create_capsule(
        client=client,
        predecessor=second,
        successor_root="b1",
        bundle_id=bundle_id,
    )
    closure_a = protocol.close(capsule_a)
    closure_b = protocol.close(capsule_b)
    bundle = protocol.bundle_closure(bundle_id, (closure_a, closure_b))

    with pytest.raises(ClosureInvalid):
        protocol.apply_bundle(bundle, ((capsule_a, closure_a),))
    assert protocol.current_seals["a"] == first
    assert protocol.current_seals["b"] == second

    successors = protocol.apply_bundle(
        bundle,
        ((capsule_a, closure_a), (capsule_b, closure_b)),
    )
    assert {seal.resource_id for seal in successors} == {"a", "b"}
    assert protocol.current_seals["a"].version == 1
    assert protocol.current_seals["b"].version == 1


def test_invalid_client_signature_is_rejected():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    capsule = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="state-1")
    tampered = replace(capsule, successor_root="state-forged")
    with pytest.raises(ValueError, match="signature"):
        protocol.validate_capsule(tampered)


def test_weighted_threshold_uses_stake_not_identity_count():
    protocol, client = make_protocol(size=3)
    protocol.members["w0"] = Member("w0", protocol.members["w0"].keypair, weight=100)
    protocol.members["w1"] = Member("w1", protocol.members["w1"].keypair, weight=1)
    protocol.members["w2"] = Member("w2", protocol.members["w2"].keypair, weight=1)
    predecessor = protocol.create_resource("asset", owner=client.identity)
    capsule = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="state-1")
    closure = protocol.close(capsule)
    assert protocol.verify_closure(capsule, closure)
    assert protocol.threshold == 69
