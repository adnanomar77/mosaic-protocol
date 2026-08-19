import pytest

from mosaic import AvailabilityError, ErasureCodec, SamplingProof


def test_erasure_codec_recovers_payload_after_two_shard_losses():
    codec = ErasureCodec(data_shards=3, parity_shards=2)
    payload = b"MOSAIC availability payload " * 17
    shards = codec.encode("object-erasure-1", payload)
    assert len(shards) == 5
    assert all(item.verify() for item in shards)
    recovered = codec.recover((shards[0], shards[2], shards[4]))
    assert recovered == payload


def test_erasure_codec_repairs_missing_shards_deterministically():
    codec = ErasureCodec(4, 2)
    payload = b"repair-me" * 50
    shards = codec.encode("object-erasure-2", payload)
    repaired = codec.repair((shards[0], shards[1], shards[3], shards[5]), (2, 4))
    assert tuple(item.shard_index for item in repaired) == (2, 4)
    assert codec.recover((shards[0], shards[1], *repaired)) == payload


def test_sampling_proof_binds_indices_and_digests():
    codec = ErasureCodec(3, 2)
    shards = codec.encode("object-sample", b"sample-data")
    proof = SamplingProof.create(shards, (0, 3))
    assert proof.verify()
    forged = type(proof)(
        object_id=proof.object_id,
        content_digest=proof.content_digest,
        sampled_indices=(0, 4),
        shard_digests=proof.shard_digests,
        proof_id=proof.proof_id,
    )
    assert not forged.verify()


def test_erasure_codec_rejects_insufficient_or_tampered_shards():
    codec = ErasureCodec(3, 2)
    shards = codec.encode("object-invalid", b"payload")
    with pytest.raises(AvailabilityError, match="not enough"):
        codec.recover(shards[:2])
    tampered = type(shards[0])(
        object_id=shards[0].object_id,
        content_digest=shards[0].content_digest,
        shard_index=shards[0].shard_index,
        total_shards=shards[0].total_shards,
        data_shards=shards[0].data_shards,
        payload=b"forged",
        shard_digest=shards[0].shard_digest,
    )
    with pytest.raises(AvailabilityError, match="invalid"):
        codec.recover((tampered, shards[1], shards[2]))
