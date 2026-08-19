import pytest

from ccd_nexus import KeyPair
from mosaic import (
    AvailabilityAttestation,
    AvailabilityCertificate,
    AvailabilityError,
    Member,
)


def members():
    keys = {f"w{i}": KeyPair.generate() for i in range(4)}
    return keys, {node_id: Member(node_id, key, weight=1) for node_id, key in keys.items()}


def test_availability_certificate_requires_weighted_quorum():
    keys, registry = members()
    attestations = tuple(
        AvailabilityAttestation.create(registry[f"w{i}"], "capsule-1", "digest-1", i, 0)
        for i in range(3)
    )
    certificate = AvailabilityCertificate.create(attestations, registry, threshold=3)
    assert certificate.verify(registry, threshold=3)
    assert certificate.total_weight == 3


def test_availability_rejects_duplicate_provider_and_wrong_content():
    keys, registry = members()
    first = AvailabilityAttestation.create(registry["w0"], "capsule-1", "digest-1", 0, 0)
    duplicate = AvailabilityAttestation.create(registry["w0"], "capsule-1", "digest-1", 1, 0)
    with pytest.raises(AvailabilityError, match="duplicate"):
        AvailabilityCertificate.create((first, duplicate), registry, threshold=2)

    wrong = AvailabilityAttestation.create(registry["w1"], "capsule-1", "digest-other", 1, 0)
    with pytest.raises(AvailabilityError, match="mismatched"):
        AvailabilityCertificate.create((first, wrong), registry, threshold=2)


def test_availability_signature_tampering_invalidates_certificate():
    keys, registry = members()
    attestations = tuple(
        AvailabilityAttestation.create(registry[f"w{i}"], "capsule-1", "digest-1", i, 0)
        for i in range(3)
    )
    certificate = AvailabilityCertificate.create(attestations, registry, threshold=3)
    tampered = type(certificate)(
        object_id=certificate.object_id,
        content_digest="forged",
        epoch=certificate.epoch,
        attestations=certificate.attestations,
        total_weight=certificate.total_weight,
        certificate_id=certificate.certificate_id,
    )
    assert not tampered.verify(registry, threshold=3)
