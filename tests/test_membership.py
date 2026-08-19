from __future__ import annotations

import pytest

from ccd_nexus import KeyPair, MembershipError, MembershipRegistry


def test_membership_requires_unique_deposit_and_minimum_stake():
    authority = KeyPair.generate()
    registry = MembershipRegistry(authority, min_stake=10)
    first_key = KeyPair.generate()
    certificate = registry.admit(
        validator_id="v1",
        public_key=first_key.public_key,
        deposit_id="deposit-1",
        stake=20,
    )
    assert registry.verify_certificate(certificate)
    with pytest.raises(MembershipError, match="deposit id"):
        registry.admit(
            validator_id="v2",
            public_key=KeyPair.generate().public_key,
            deposit_id="deposit-1",
            stake=20,
        )
    with pytest.raises(MembershipError, match="below minimum"):
        registry.admit(
            validator_id="v3",
            public_key=KeyPair.generate().public_key,
            deposit_id="deposit-3",
            stake=9,
        )


def test_sybil_split_does_not_create_weight():
    authority = KeyPair.generate()
    registry = MembershipRegistry(authority, min_stake=10)
    parts = registry.split_budget(100, 10)
    assert len(parts) == 10
    assert sum(parts) == 100
    assert registry.sybil_capacity(100) == 10


def test_tampered_admission_certificate_is_rejected():
    authority = KeyPair.generate()
    registry = MembershipRegistry(authority, min_stake=10)
    certificate = registry.admit(
        validator_id="v1",
        public_key=KeyPair.generate().public_key,
        deposit_id="deposit-1",
        stake=20,
    )
    tampered = type(certificate)(
        certificate_id=certificate.certificate_id,
        epoch=certificate.epoch,
        validator_id=certificate.validator_id,
        public_key=certificate.public_key,
        deposit_id=certificate.deposit_id,
        stake=certificate.stake + 1000,
        signatory=certificate.signatory,
        authority_signature=certificate.authority_signature,
        statement_digest=certificate.statement_digest,
    )
    assert not registry.verify_certificate(tampered)
