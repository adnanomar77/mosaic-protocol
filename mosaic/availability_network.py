"""Network-facing availability provider coordinator."""

from __future__ import annotations

from dataclasses import dataclass

from .availability import AvailabilityError, AvailabilityStore, ErasureShard, SamplingProof


class AvailabilityNetworkError(ValueError):
    pass


def shard_to_wire(shard: ErasureShard) -> dict:
    return {
        "object_id": shard.object_id,
        "content_digest": shard.content_digest,
        "shard_index": shard.shard_index,
        "total_shards": shard.total_shards,
        "data_shards": shard.data_shards,
        "payload": shard.payload.hex(),
        "shard_digest": shard.shard_digest,
    }


def shard_from_wire(data: dict) -> ErasureShard:
    return ErasureShard(
        object_id=data["object_id"],
        content_digest=data["content_digest"],
        shard_index=int(data["shard_index"]),
        total_shards=int(data["total_shards"]),
        data_shards=int(data["data_shards"]),
        payload=bytes.fromhex(data["payload"]),
        shard_digest=data["shard_digest"],
    )


def sampling_to_wire(proof: SamplingProof) -> dict:
    return {
        "object_id": proof.object_id,
        "content_digest": proof.content_digest,
        "sampled_indices": list(proof.sampled_indices),
        "shard_digests": list(proof.shard_digests),
        "proof_id": proof.proof_id,
    }


@dataclass
class AvailabilityCoordinator:
    provider_store: AvailabilityStore
    durable_store: object | None = None

    def put(self, shard: ErasureShard) -> None:
        try:
            self.provider_store.put(shard)
        except AvailabilityError as exc:
            raise AvailabilityNetworkError(str(exc)) from exc
        if self.durable_store is not None:
            self.durable_store.put(
                "availability_shard",
                f"{shard.object_id}:{shard.shard_index}",
                shard_to_wire(shard),
                event=True,
            )

    def fetch(self, object_id: str, shard_index: int) -> ErasureShard:
        for shard in self.provider_store.shards(object_id):
            if shard.shard_index == shard_index:
                return shard
        raise AvailabilityNetworkError("requested shard is not stored by provider")

    def sample(self, object_id: str, indices: tuple[int, ...]) -> SamplingProof:
        try:
            return self.provider_store.sample(object_id, indices)
        except AvailabilityError as exc:
            raise AvailabilityNetworkError(str(exc)) from exc

    def repair(self, source_shards: tuple[ErasureShard, ...], missing_indices: tuple[int, ...]) -> tuple[ErasureShard, ...]:
        if not source_shards:
            raise AvailabilityNetworkError("repair requires source shards")
        object_id = source_shards[0].object_id
        try:
            repaired = self.provider_store.codec.repair(source_shards, missing_indices)
            for shard in repaired:
                self.put(shard)
            return repaired
        except AvailabilityError as exc:
            raise AvailabilityNetworkError(str(exc)) from exc

    def restore_from_store(self) -> int:
        if self.durable_store is None:
            return 0
        restored = 0
        for _, payload in self.durable_store.items("availability_shard"):
            self.provider_store.put(shard_from_wire(payload))
            restored += 1
        return restored
