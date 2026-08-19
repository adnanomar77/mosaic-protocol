import pytest

from mosaic import AvailabilityError, AvailabilityStore, ErasureCodec


def test_availability_store_recovers_and_repairs_missing_shards():
    codec = ErasureCodec(3, 2)
    source = AvailabilityStore(codec)
    shards = source.publish("object-store", b"distributed-data" * 30)
    target = AvailabilityStore(codec)
    for shard in (shards[0], shards[2], shards[4]):
        target.put(shard)
    assert target.recover("object-store") == b"distributed-data" * 30
    proof = target.sample("object-store", (0, 2))
    assert proof.verify()
    repaired = target.repair("object-store")
    assert tuple(item.shard_index for item in repaired) == (1, 3)
    assert target.missing_indices("object-store") == ()
    assert target.recover("object-store") == b"distributed-data" * 30


def test_availability_store_rejects_wrong_codec_and_invalid_shard():
    source = AvailabilityStore(ErasureCodec(3, 2))
    shard = source.publish("object-store-2", b"payload")[0]
    target = AvailabilityStore(ErasureCodec(2, 2))
    with pytest.raises(AvailabilityError, match="codec"):
        target.put(shard)
