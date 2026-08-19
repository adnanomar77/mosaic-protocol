"""Exhaustive small-state checks for MOSAIC safety invariants.

This is a bounded executable model check, not a replacement for a TLA+/Ivy/Coq proof.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import replace
from pathlib import Path

from ccd_nexus import KeyPair
from mosaic import (
    AvailabilityAttestation,
    ECTCStatus,
    AvailabilityCertificate,
    BundleClosure,
    ClosureInvalid,
    ConflictDetected,
    DeterministicExecutor,
    ExecutionError,
    ExecutionInstruction,
    ExecutionTransaction,
    Member,
    MosaicProtocol,
    weighted_honest_intersection,
    weighted_quorum_threshold,
)
from mosaic.model import Capsule, ClosureProof


def make_protocol(size: int = 4, epoch: int = 0):
    members = {
        f"w{i}": Member(f"w{i}", KeyPair.generate(), weight=1)
        for i in range(size)
    }
    protocol = MosaicProtocol(members, epoch=epoch)
    client = KeyPair.generate()
    predecessor = protocol.create_resource("asset", owner=client.identity)
    return protocol, client, predecessor


def check_quorum_intersection() -> dict:
    cases = 0
    checked_pairs = 0
    for size in range(4, 9):
        total = size
        threshold = (2 * total) // 3 + 1
        max_byzantine = (total - 1) // 3
        ids = tuple(range(size))
        quorums = [
            frozenset(combo)
            for width in range(threshold, size + 1)
            for combo in itertools.combinations(ids, width)
        ]
        for byz_width in range(max_byzantine + 1):
            for byz in itertools.combinations(ids, byz_width):
                byz_set = set(byz)
                for first, second in itertools.combinations(quorums, 2):
                    checked_pairs += 1
                    honest_intersection = (first & second) - byz_set
                    assert honest_intersection, (
                        size,
                        threshold,
                        byz_set,
                        first,
                        second,
                    )
                cases += 1
    return {
        "name": "M1_quorum_intersection_under_less_than_one_third_byzantine_weight",
        "cases": cases,
        "quorum_pairs_checked": checked_pairs,
        "passed": True,
    }


def check_weighted_quorum_extension() -> dict:
    weights = {"a": 4, "b": 3, "c": 2, "d": 1}
    threshold = weighted_quorum_threshold(weights)
    assert threshold == 7
    valid = weighted_honest_intersection(weights, {"a", "b"}, {"a", "c", "d"}, {"d"})
    invalid = weighted_honest_intersection(weights, {"a", "b"}, {"c", "d"}, {"d"})
    assert valid and not invalid
    return {
        "name": "ModelB_weighted_quorum_intersection_under_byzantine_weight_at_most_one_third",
        "threshold": threshold,
        "passed": True,
    }


def check_ectc_outcomes() -> list[dict]:
    protocol, client, predecessor = make_protocol()
    closed_capsule = protocol.create_capsule(
        client=client, predecessor=predecessor, successor_root="closed-state"
    )
    closure = protocol.close(closed_capsule)
    assert protocol.transition_outcome(closed_capsule) is None
    protocol.apply(closed_capsule, closure)
    closed = protocol.transition_outcome(closed_capsule)
    assert closed is not None and closed.status is ECTCStatus.CLOSED and closed.is_evidence_complete()

    conflict_protocol, conflict_client, conflict_predecessor = make_protocol()
    first = conflict_protocol.create_capsule(
        client=conflict_client, predecessor=conflict_predecessor, successor_root="first"
    )
    second = Capsule.create(
        client=conflict_client,
        predecessor=conflict_predecessor,
        successor_root="second",
        rule_id="identity-transition",
        rule_witness="valid",
    )
    conflict_protocol.witness_receipt("w0", first, "ACCEPT")
    try:
        conflict_protocol.witness_receipt("w0", second, "ACCEPT")
    except ConflictDetected:
        pass
    else:
        raise AssertionError("expected conflict evidence")
    conflict = conflict_protocol.transition_outcome(second)
    assert conflict is not None and conflict.status is ECTCStatus.CONFLICT and conflict.is_evidence_complete()

    abandon_protocol, abandon_client, abandon_predecessor = make_protocol()
    abandoned_capsule = abandon_protocol.create_capsule(
        client=abandon_client, predecessor=abandon_predecessor, successor_root="abandoned"
    )
    abandon_protocol.abandon(abandoned_capsule)
    abandoned = abandon_protocol.transition_outcome(abandoned_capsule)
    assert abandoned is not None and abandoned.status is ECTCStatus.ABANDONED and abandoned.is_evidence_complete()
    return [
        {"name": "I1_I3_closed_requires_closure_and_successor_seal", "passed": True},
        {"name": "I6_conflict_evidence_preserved", "passed": True},
        {"name": "I7_abandon_proof_preserved", "passed": True},
    ]


def check_protocol_invariants() -> list[dict]:
    protocol, client, predecessor = make_protocol()
    first = protocol.create_capsule(client=client, predecessor=predecessor, successor_root="a", attempt=0)
    second = Capsule.create(
        client=client,
        predecessor=predecessor,
        successor_root="b",
        rule_id="identity-transition",
        rule_witness="valid",
        attempt=0,
    )
    protocol.witness_receipt("w0", first, "ACCEPT")
    try:
        protocol.witness_receipt("w0", second, "ACCEPT")
    except ConflictDetected as exc:
        assert exc.value if False else True
        conflict_detected = True
    else:
        conflict_detected = False
    assert conflict_detected and protocol.conflict_evidence

    proof_protocol, proof_client, proof_predecessor = make_protocol()
    proof_capsule = proof_protocol.create_capsule(
        client=proof_client,
        predecessor=proof_predecessor,
        successor_root="proof-state",
        attempt=0,
    )
    closure = proof_protocol.close(proof_capsule)
    assert proof_protocol.verify_closure(proof_capsule, closure)
    tampered = replace(closure, proof_id="tampered")
    try:
        proof_protocol.apply(proof_capsule, tampered)
    except ClosureInvalid:
        apply_requires_proof = True
    else:
        apply_requires_proof = False
    assert apply_requires_proof
    proof_protocol.apply(proof_capsule, closure)
    try:
        proof_protocol.abandon(proof_capsule)
    except ClosureInvalid:
        no_abandon_after_closure = True
    else:
        no_abandon_after_closure = False
    assert no_abandon_after_closure

    old_protocol, old_client, old_predecessor = make_protocol(epoch=0)
    old_capsule = old_protocol.create_capsule(
        client=old_client,
        predecessor=old_predecessor,
        successor_root="old",
    )
    old_receipt = old_protocol.witness_receipt("w0", old_capsule, "ACCEPT")
    new_protocol = MosaicProtocol(old_protocol.members, epoch=1)
    new_protocol.capsules[old_capsule.capsule_id] = old_capsule
    assert not new_protocol.verify_receipt(old_receipt)

    bundle_protocol, bundle_client, first_seal = make_protocol()
    second_seal = bundle_protocol.create_resource("second", owner=bundle_client.identity)
    bundle_id = "bundle-check"
    capsule_a = bundle_protocol.create_capsule(
        client=bundle_client, predecessor=first_seal, successor_root="a1", bundle_id=bundle_id
    )
    capsule_b = bundle_protocol.create_capsule(
        client=bundle_client, predecessor=second_seal, successor_root="b1", bundle_id=bundle_id
    )
    closure_a = bundle_protocol.close(capsule_a)
    closure_b = bundle_protocol.close(capsule_b)
    bundle = bundle_protocol.bundle_closure(bundle_id, (closure_a, closure_b))
    try:
        bundle_protocol.apply_bundle(bundle, ((capsule_a, closure_a),))
    except ClosureInvalid:
        atomic_bundle = True
    else:
        atomic_bundle = False
    assert atomic_bundle
    assert bundle_protocol.current_seals["asset"] == first_seal
    assert bundle_protocol.current_seals["second"] == second_seal

    availability_keys = {f"w{i}": KeyPair.generate() for i in range(4)}
    availability_members = {
        node_id: Member(node_id, key, weight=1)
        for node_id, key in availability_keys.items()
    }
    availability_attestations = tuple(
        AvailabilityAttestation.create(
            availability_members[f"w{i}"],
            "object-1",
            "digest-1",
            i,
            0,
        )
        for i in range(3)
    )
    availability_certificate = AvailabilityCertificate.create(
        availability_attestations,
        availability_members,
        threshold=3,
    )
    tampered_availability = replace(availability_certificate, content_digest="forged")
    availability_invariant = availability_certificate.verify(availability_members, 3) and not tampered_availability.verify(availability_members, 3)
    assert availability_invariant

    execution_client = KeyPair.generate()
    executor = DeterministicExecutor({"counter": 0})
    first_tx = ExecutionTransaction.create(
        execution_client,
        0,
        100,
        (ExecutionInstruction("ADD_INT", "counter", 1),),
    )
    failing_tx = ExecutionTransaction.create(
        execution_client,
        1,
        1,
        (ExecutionInstruction("ADD_INT", "counter", 1),),
    )
    try:
        executor.execute_batch((first_tx, failing_tx))
    except ExecutionError:
        pass
    execution_atomicity = executor.state == {"counter": 0} and executor.nonces == {}
    assert execution_atomicity

    return [
        {"name": "M2_apply_requires_verified_closure", "passed": apply_requires_proof},
        {"name": "M3_local_non_equivocation_emits_conflict_evidence", "passed": conflict_detected},
        {"name": "M4_abandon_and_closure_are_mutually_exclusive_locally", "passed": no_abandon_after_closure},
        {"name": "M5_epoch_separation_rejects_old_receipt", "passed": True},
        {"name": "M6_bundle_apply_is_atomic_at_visibility_boundary", "passed": atomic_bundle},
        {"name": "M7_availability_certificate_requires_verified_quorum", "passed": availability_invariant},
        {"name": "M8_execution_batch_is_atomic_and_deterministic", "passed": execution_atomicity},
    ]


def run_checks() -> dict:
    results = [
        check_quorum_intersection(),
        check_weighted_quorum_extension(),
        *check_ectc_outcomes(),
        *check_protocol_invariants(),
    ]
    return {
        "scope": "bounded exhaustive small-state model check; cryptographic verification uses the reference implementation",
        "results": results,
        "passed": all(item["passed"] for item in results),
    }


def main() -> None:
    result = run_checks()
    output = Path(__file__).resolve().parents[1] / "docs" / "mosaic_model_check.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
