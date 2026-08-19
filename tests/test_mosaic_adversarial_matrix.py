from dataclasses import replace

import pytest

from ccd_nexus import KeyPair
from mosaic import Capsule, ClosureInvalid, ClosureProof, Member, MosaicProtocol


def make_protocol(size=4):
    members = {f"w{i}": Member(f"w{i}", KeyPair.generate(), weight=1) for i in range(size)}
    return MosaicProtocol(members), KeyPair.generate()


def test_duplicate_capsule_is_idempotent_at_identifier_boundary():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    first = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="same")
    duplicate = Capsule.create(
        client=client,
        predecessor=predecessor,
        successor_root="same",
        rule_id="identity-transition",
        rule_witness="valid",
    )
    assert duplicate.capsule_id == first.capsule_id
    assert len(protocol.capsules) == 1


def test_invalid_predecessor_is_rejected():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    forged = replace(predecessor, state_root="not-current")
    with pytest.raises(ValueError, match="predecessor"):
        protocol.create_capsule(client=client, predecessor=forged, successor_root="next")


def test_empty_successor_root_is_rejected():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    capsule = Capsule.create(
        client=client,
        predecessor=predecessor,
        successor_root="",
        rule_id="identity-transition",
        rule_witness="valid",
    )
    with pytest.raises(ValueError, match="successor root"):
        protocol.validate_capsule(capsule)


def test_insufficient_quorum_cannot_close():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    capsule = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="next")
    receipt = protocol.witness_receipt("w0", capsule)
    with pytest.raises(ClosureInvalid, match="insufficient"):
        protocol.close(capsule, (receipt,))


def test_conflicting_receipts_cannot_form_one_closure():
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
    receipt = protocol.witness_receipt("w0", first)
    conflicting = replace(receipt, capsule_id=second.capsule_id)
    with pytest.raises(ClosureInvalid, match="receipts"):
        ClosureProof.create((receipt, conflicting))


def test_delayed_receipt_from_old_attempt_cannot_close_new_attempt():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    old_capsule = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="old", attempt=0)
    old_receipt = protocol.witness_receipt("w0", old_capsule)
    new_capsule = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="new", attempt=1)
    with pytest.raises(ClosureInvalid, match="insufficient"):
        protocol.close(new_capsule, (old_receipt,))


def test_independent_resources_close_without_shared_predecessor():
    protocol, client = make_protocol()
    first = protocol.create_resource("a", owner=client.identity)
    second = protocol.create_resource("b", owner=client.identity)
    capsule_a = protocol.create_capsule(client=client, predecessor=first, successor_root="a1")
    capsule_b = protocol.create_capsule(client=client, predecessor=second, successor_root="b1")
    closure_a = protocol.close(capsule_a)
    closure_b = protocol.close(capsule_b)
    successor_a = protocol.apply(capsule_a, closure_a)
    successor_b = protocol.apply(capsule_b, closure_b)
    assert successor_a.resource_id == "a"
    assert successor_b.resource_id == "b"


def test_replayed_receipt_from_old_epoch_is_rejected():
    protocol, client = make_protocol()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    capsule = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="next")
    receipt = protocol.witness_receipt("w0", capsule)
    restored = MosaicProtocol(protocol.members, epoch=1)
    restored.capsules[capsule.capsule_id] = capsule
    assert not restored.verify_receipt(receipt)
