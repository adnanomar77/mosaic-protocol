from __future__ import annotations

import pytest

from ccd_nexus import (
    DomainExecutionError,
    DomainExecutor,
    EpochManager,
    InputRef,
    JoinCoordinator,
    JoinError,
    KeyPair,
    ObjectState,
    Operation,
    QuorumCommittee,
    QuorumError,
    Validator,
    WriteIntent,
)


def make_committee(size: int = 4):
    validators = {}
    for index in range(size):
        keypair = KeyPair.generate()
        validator_id = f"validator-{index}"
        validators[validator_id] = Validator(validator_id, keypair)
    return validators, QuorumCommittee(validators)


def make_single_operation(client: KeyPair, *, epoch: int = 0, object_id: str = "obj-1", version: int = 0, payload: str = "next"):
    return Operation.create(
        keypair=client,
        epoch=epoch,
        domain_ids=("D1",),
        inputs=(InputRef("D1", object_id, version),),
        writes=(WriteIntent("D1", object_id, version, client.identity, payload),),
        nonce=version + len(payload),
    )


def make_domain(domain_id: str, client: KeyPair, *, epoch: int = 0):
    validators, committee = make_committee()
    domain = DomainExecutor(domain_id, epoch, committee)
    domain.add_object(ObjectState(f"{domain_id}-obj", 0, client.identity, "initial", domain_id))
    return validators, committee, domain


def test_single_domain_finality_and_signature_verification():
    client = KeyPair.generate()
    validators, committee, domain = make_domain("D1", client)
    operation = make_single_operation(client, object_id="D1-obj")

    certificate = domain.finalize(operation)

    assert certificate.phase == "COMMIT"
    assert committee.verify_certificate(
        certificate=certificate,
        epoch=0,
        domain_id="D1",
        object_versions=(("D1-obj", 0),),
        operation=operation,
    )
    assert domain.objects["D1-obj"].version == 1
    assert domain.objects["D1-obj"].payload == "next"
    assert operation.op_id in domain.committed_operations
    assert set(certificate.signers) == set(validators)


def test_stale_conflicting_operation_cannot_commit():
    client = KeyPair.generate()
    _, _, domain = make_domain("D1", client)
    first = make_single_operation(client, object_id="D1-obj", payload="first")
    second = make_single_operation(client, object_id="D1-obj", payload="second")

    domain.finalize(first)

    with pytest.raises(DomainExecutionError, match="stale version"):
        domain.finalize(second)
    assert domain.objects["D1-obj"].payload == "first"


def test_equivocation_is_rejected_and_recorded():
    client = KeyPair.generate()
    validators, committee, _ = make_domain("D1", client)
    first = make_single_operation(client, object_id="D1-obj", payload="first")
    second = make_single_operation(client, object_id="D1-obj", payload="second")
    validator = validators["validator-0"]
    versions = (("D1-obj", 0),)

    committee.record_vote(
        validator.sign_vote(
            epoch=0,
            domain_id="D1",
            object_versions=versions,
            op_id=first.op_id,
            dependency_digest=first.dependency_digest,
            phase="PREPARE",
        )
    )
    with pytest.raises(QuorumError, match="equivocated"):
        committee.record_vote(
            validator.sign_vote(
                epoch=0,
                domain_id="D1",
                object_versions=versions,
                op_id=second.op_id,
                dependency_digest=second.dependency_digest,
                phase="PREPARE",
            )
        )
    assert len(committee.evidence) == 1


def test_certificate_requires_quorum():
    client = KeyPair.generate()
    validators, committee, _ = make_domain("D1", client)
    operation = make_single_operation(client, object_id="D1-obj")
    versions = (("D1-obj", 0),)
    for validator_id in list(validators)[:2]:
        validator = validators[validator_id]
        committee.record_vote(
            validator.sign_vote(
                epoch=0,
                domain_id="D1",
                object_versions=versions,
                op_id=operation.op_id,
                dependency_digest=operation.dependency_digest,
                phase="PREPARE",
            )
        )

    with pytest.raises(QuorumError, match="insufficient quorum"):
        committee.issue_certificate(
            epoch=0,
            domain_id="D1",
            object_versions=versions,
            operation=operation,
            phase="PREPARE",
        )


def test_join_is_atomic_across_two_domains():
    client = KeyPair.generate()
    validators, committee = make_committee()
    domain_a = DomainExecutor("D1", 0, committee)
    domain_b = DomainExecutor("D2", 0, committee)
    domain_a.add_object(ObjectState("a", 0, client.identity, "A0", "D1"))
    domain_b.add_object(ObjectState("b", 0, client.identity, "B0", "D2"))
    operation = Operation.create(
        keypair=client,
        epoch=0,
        domain_ids=("D1", "D2"),
        inputs=(InputRef("D1", "a", 0), InputRef("D2", "b", 0)),
        writes=(
            WriteIntent("D1", "a", 0, client.identity, "A1"),
            WriteIntent("D2", "b", 0, client.identity, "B1"),
        ),
        nonce=77,
    )

    coordinator = JoinCoordinator({"D1": domain_a, "D2": domain_b})
    join_certificate = coordinator.finalize(operation)

    assert coordinator.verify_join_certificate(operation, join_certificate)
    assert domain_a.objects["a"].version == 1
    assert domain_b.objects["b"].version == 1
    assert domain_a.objects["a"].payload == "A1"
    assert domain_b.objects["b"].payload == "B1"
    assert set(join_certificate.signers) == set(validators)


def test_join_failure_does_not_apply_partial_state():
    client = KeyPair.generate()
    _, committee = make_committee()
    domain_a = DomainExecutor("D1", 0, committee)
    domain_b = DomainExecutor("D2", 0, committee)
    domain_a.add_object(ObjectState("a", 0, client.identity, "A0", "D1"))
    operation = Operation.create(
        keypair=client,
        epoch=0,
        domain_ids=("D1", "D2"),
        inputs=(InputRef("D1", "a", 0), InputRef("D2", "missing", 0)),
        writes=(
            WriteIntent("D1", "a", 0, client.identity, "A1"),
            WriteIntent("D2", "missing", 0, client.identity, "B1"),
        ),
        nonce=78,
    )

    coordinator = JoinCoordinator({"D1": domain_a, "D2": domain_b})
    with pytest.raises(DomainExecutionError, match="unknown object"):
        coordinator.finalize(operation)
    assert domain_a.objects["a"].version == 0
    assert not domain_a.committed_operations


def test_epoch_isolation():
    client = KeyPair.generate()
    _, committee = make_committee()
    domain = DomainExecutor("D1", 1, committee)
    domain.add_object(ObjectState("D1-obj", 0, client.identity, "initial", "D1"))
    operation = make_single_operation(client, epoch=0, object_id="D1-obj")

    with pytest.raises(DomainExecutionError, match="another epoch"):
        domain.finalize(operation)


def test_tampered_certificate_is_rejected():
    client = KeyPair.generate()
    _, committee, domain = make_domain("D1", client)
    operation = make_single_operation(client, object_id="D1-obj")
    certificate = domain.finalize(operation)
    first_signer, first_signature = certificate.signatures[0]
    tampered = type(certificate)(
        certificate_id=certificate.certificate_id,
        epoch=certificate.epoch,
        domain_ids=certificate.domain_ids,
        op_id=certificate.op_id,
        phase=certificate.phase,
        signers=certificate.signers,
        signatures=tuple(
            (first_signer, bytes([first_signature[0] ^ 1]) + first_signature[1:])
            if signer == first_signer
            else (signer, signature)
            for signer, signature in certificate.signatures
        ),
        statement_digest=certificate.statement_digest,
    )
    assert not committee.verify_certificate(
        certificate=tampered,
        epoch=0,
        domain_id="D1",
        object_versions=(("D1-obj", 0),),
        operation=operation,
    )


def test_unknown_validator_certificate_is_rejected_without_crash():
    client = KeyPair.generate()
    _, committee, domain = make_domain("D1", client)
    operation = make_single_operation(client, object_id="D1-obj")
    certificate = domain.finalize(operation)
    unknown_signatures = certificate.signatures + (("unknown", b"bad"),)
    malformed = type(certificate)(
        certificate_id=certificate.certificate_id,
        epoch=certificate.epoch,
        domain_ids=certificate.domain_ids,
        op_id=certificate.op_id,
        phase=certificate.phase,
        signers=certificate.signers + ("unknown",),
        signatures=unknown_signatures,
        statement_digest=certificate.statement_digest,
    )
    assert not committee.verify_certificate(
        certificate=malformed,
        epoch=0,
        domain_id="D1",
        object_versions=(("D1-obj", 0),),
        operation=operation,
    )


def test_snapshot_is_signed_and_detects_state_mutation():
    client = KeyPair.generate()
    _, _, domain = make_domain("D1", client)
    snapshot = domain.create_snapshot()
    assert domain.verify_snapshot(snapshot)
    domain.objects["D1-obj"] = ObjectState("D1-obj", 0, client.identity, "tampered", "D1")
    assert not domain.verify_snapshot(snapshot)


def test_epoch_transition_requires_old_quorum_and_changes_committee():
    client = KeyPair.generate()
    old_validators, old_committee, _ = make_domain("D1", client)
    manager = EpochManager(0, old_committee)
    new_validators = {}
    for index in range(4):
        keypair = KeyPair.generate()
        validator_id = f"new-validator-{index}"
        new_validators[validator_id] = Validator(validator_id, keypair)

    transition = manager.propose_transition(new_validators)
    assert manager.verify_transition(transition, new_validators)
    next_manager = manager.apply_transition(transition, new_validators)
    assert next_manager.epoch == 1
    assert set(next_manager.committee.validators) == set(new_validators)
    assert set(transition.signers) == set(old_validators)


def test_tampered_dac_blocks_prepare():
    client = KeyPair.generate()
    _, committee, domain = make_domain("D1", client)
    operation = make_single_operation(client, object_id="D1-obj")
    dac = committee.issue_dac(operation)
    tampered = type(dac)(
        certificate_id=dac.certificate_id,
        epoch=dac.epoch,
        op_id=dac.op_id + "tampered",
        payload_digest=dac.payload_digest,
        signers=dac.signers,
        signatures=dac.signatures,
        statement_digest=dac.statement_digest,
    )
    with pytest.raises(QuorumError, match="not available"):
        domain.prepare(operation, tampered)


def test_abort_certificate_is_threshold_backed_and_non_mutating():
    client = KeyPair.generate()
    _, committee = make_committee()
    domain_a = DomainExecutor("D1", 0, committee)
    domain_b = DomainExecutor("D2", 0, committee)
    domain_a.add_object(ObjectState("a", 0, client.identity, "A0", "D1"))
    domain_b.add_object(ObjectState("b", 0, client.identity, "B0", "D2"))
    operation = Operation.create(
        keypair=client,
        epoch=0,
        domain_ids=("D1", "D2"),
        inputs=(InputRef("D1", "a", 0), InputRef("D2", "b", 0)),
        writes=(
            WriteIntent("D1", "a", 0, client.identity, "A1"),
            WriteIntent("D2", "b", 0, client.identity, "B1"),
        ),
        nonce=79,
    )
    coordinator = JoinCoordinator({"D1": domain_a, "D2": domain_b})
    certificate = coordinator.abort(operation, "timeout")
    assert coordinator.verify_abort(operation, certificate, "timeout")
    assert not coordinator.verify_abort(operation, certificate, "different reason")
    assert domain_a.objects["a"].version == 0
    assert domain_b.objects["b"].version == 0


def test_tampered_join_certificate_is_rejected():
    client = KeyPair.generate()
    _, committee = make_committee()
    domain_a = DomainExecutor("D1", 0, committee)
    domain_b = DomainExecutor("D2", 0, committee)
    domain_a.add_object(ObjectState("a", 0, client.identity, "A0", "D1"))
    domain_b.add_object(ObjectState("b", 0, client.identity, "B0", "D2"))
    operation = Operation.create(
        keypair=client,
        epoch=0,
        domain_ids=("D1", "D2"),
        inputs=(InputRef("D1", "a", 0), InputRef("D2", "b", 0)),
        writes=(
            WriteIntent("D1", "a", 0, client.identity, "A1"),
            WriteIntent("D2", "b", 0, client.identity, "B1"),
        ),
        nonce=80,
    )
    coordinator = JoinCoordinator({"D1": domain_a, "D2": domain_b})
    certificates = coordinator.prepare_all(operation)
    join_certificate = coordinator.issue_join_certificate(operation, certificates)
    signer, signature = join_certificate.signatures[0]
    tampered = type(join_certificate)(
        certificate_id=join_certificate.certificate_id,
        epoch=join_certificate.epoch,
        op_id=join_certificate.op_id,
        domain_certificates=join_certificate.domain_certificates,
        signers=join_certificate.signers,
        signatures=tuple(
            (signer, bytes([signature[0] ^ 1]) + signature[1:])
            if item == signer
            else (item, item_signature)
            for item, item_signature in join_certificate.signatures
        ),
        statement_digest=join_certificate.statement_digest,
    )
    assert not coordinator.verify_join_certificate(operation, tampered)
