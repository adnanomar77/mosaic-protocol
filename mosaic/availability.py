"""Availability attestations for public MOSAIC delivery paths."""

from __future__ import annotations

from dataclasses import dataclass

from ccd_nexus.crypto import KeyPair, canonical_bytes, digest

from .model import Member


class AvailabilityError(ValueError):
    pass


@dataclass(frozen=True)
class AvailabilityAttestation:
    object_id: str
    content_digest: str
    shard_index: int
    epoch: int
    provider_id: str
    signature: bytes

    @classmethod
    def create(
        cls,
        member: Member,
        object_id: str,
        content_digest: str,
        shard_index: int,
        epoch: int,
    ) -> "AvailabilityAttestation":
        if member.keypair is None:
            raise AvailabilityError("provider private key is not loaded")
        if shard_index < 0 or epoch < 0:
            raise AvailabilityError("invalid shard or epoch")
        unsigned = {
            "protocol": "MOSAIC/AVAILABILITY-ATTEST/v1",
            "object_id": object_id,
            "content_digest": content_digest,
            "shard_index": shard_index,
            "epoch": epoch,
            "provider_id": member.member_id,
        }
        return cls(
            object_id=object_id,
            content_digest=content_digest,
            shard_index=shard_index,
            epoch=epoch,
            provider_id=member.member_id,
            signature=member.keypair.sign(canonical_bytes(unsigned)),
        )

    def statement(self) -> dict:
        return {
            "protocol": "MOSAIC/AVAILABILITY-ATTEST/v1",
            "object_id": self.object_id,
            "content_digest": self.content_digest,
            "shard_index": self.shard_index,
            "epoch": self.epoch,
            "provider_id": self.provider_id,
        }

    def verify(self, members: dict[str, Member]) -> bool:
        member = members.get(self.provider_id)
        return bool(
            member is not None
            and self.object_id
            and self.content_digest
            and self.shard_index >= 0
            and self.epoch >= 0
            and KeyPair.verify(
                member.public_key,
                canonical_bytes(self.statement()),
                self.signature,
            )
        )


@dataclass(frozen=True)
class AvailabilityCertificate:
    object_id: str
    content_digest: str
    epoch: int
    attestations: tuple[AvailabilityAttestation, ...]
    total_weight: int
    certificate_id: str

    @classmethod
    def create(
        cls,
        attestations: tuple[AvailabilityAttestation, ...],
        members: dict[str, Member],
        threshold: int,
    ) -> "AvailabilityCertificate":
        if not attestations:
            raise AvailabilityError("availability certificate cannot be empty")
        unique = {item.provider_id: item for item in attestations}
        if len(unique) != len(attestations):
            raise AvailabilityError("duplicate availability provider")
        first = attestations[0]
        if any(
            item.object_id != first.object_id
            or item.content_digest != first.content_digest
            or item.epoch != first.epoch
            or not item.verify(members)
            for item in attestations
        ):
            raise AvailabilityError("invalid or mismatched availability attestation")
        total_weight = sum(members[provider_id].weight for provider_id in unique)
        if total_weight < threshold:
            raise AvailabilityError("insufficient availability weight")
        ordered = tuple(sorted(attestations, key=lambda item: item.provider_id))
        certificate_id = digest(
            {
                "protocol": "MOSAIC/AVAILABILITY-CERT/v1",
                "object_id": first.object_id,
                "content_digest": first.content_digest,
                "epoch": first.epoch,
                "attestations": [
                    {
                        "provider_id": item.provider_id,
                        "shard_index": item.shard_index,
                        "signature": item.signature.hex(),
                    }
                    for item in ordered
                ],
                "total_weight": total_weight,
            }
        )
        return cls(first.object_id, first.content_digest, first.epoch, ordered, total_weight, certificate_id)

    def verify(self, members: dict[str, Member], threshold: int) -> bool:
        try:
            rebuilt = AvailabilityCertificate.create(self.attestations, members, threshold)
        except AvailabilityError:
            return False
        return (
            rebuilt.object_id == self.object_id
            and rebuilt.content_digest == self.content_digest
            and rebuilt.epoch == self.epoch
            and rebuilt.total_weight == self.total_weight
            and rebuilt.certificate_id == self.certificate_id
        )


# GF(256) Reed-Solomon primitives. The implementation is intentionally small,
# deterministic, and self-contained so recovery does not depend on an external
# binary or a non-audited runtime.
_GF_POLY = 0x11D


def _gf_mul(left: int, right: int) -> int:
    result = 0
    while right:
        if right & 1:
            result ^= left
        right >>= 1
        left <<= 1
        if left & 0x100:
            left ^= _GF_POLY
    return result & 0xFF


def _gf_pow(value: int, exponent: int) -> int:
    result = 1
    for _ in range(exponent):
        result = _gf_mul(result, value)
    return result


def _gf_inv(value: int) -> int:
    if value == 0:
        raise AvailabilityError("zero has no finite-field inverse")
    return _gf_pow(value, 254)


def _matrix_inverse(matrix: list[list[int]]) -> list[list[int]]:
    size = len(matrix)
    if size == 0 or any(len(row) != size for row in matrix):
        raise AvailabilityError("matrix must be square")
    augmented = [row[:] + [1 if row == index else 0 for row in range(size)] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = next((row for row in range(column, size) if augmented[row][column]), None)
        if pivot is None:
            raise AvailabilityError("erasure matrix is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        inverse = _gf_inv(augmented[column][column])
        augmented[column] = [_gf_mul(item, inverse) for item in augmented[column]]
        for row in range(size):
            if row == column or augmented[row][column] == 0:
                continue
            factor = augmented[row][column]
            augmented[row] = [left ^ _gf_mul(factor, right) for left, right in zip(augmented[row], augmented[column])]
    return [row[size:] for row in augmented]


def _matrix_vector(matrix: list[list[int]], vector: list[bytes]) -> list[bytes]:
    if not matrix or len(matrix[0]) != len(vector):
        raise AvailabilityError("matrix/vector dimensions do not match")
    width = len(vector[0])
    output: list[bytes] = []
    for row in matrix:
        result = bytearray(width)
        for coefficient, shard in zip(row, vector):
            if len(shard) != width:
                raise AvailabilityError("shards have inconsistent sizes")
            if coefficient:
                for index, value in enumerate(shard):
                    result[index] ^= _gf_mul(coefficient, value)
        output.append(bytes(result))
    return output


@dataclass(frozen=True)
class ErasureShard:
    object_id: str
    content_digest: str
    shard_index: int
    total_shards: int
    data_shards: int
    payload: bytes
    shard_digest: str

    @classmethod
    def create(
        cls,
        object_id: str,
        content_digest: str,
        shard_index: int,
        total_shards: int,
        data_shards: int,
        payload: bytes,
    ) -> "ErasureShard":
        return cls(
            object_id,
            content_digest,
            shard_index,
            total_shards,
            data_shards,
            payload,
            digest({"protocol": "MOSAIC/ERASURE-SHARD/v1", "payload": payload.hex()}),
        )

    def verify(self) -> bool:
        return (
            bool(self.object_id and self.content_digest)
            and 0 <= self.shard_index < self.total_shards
            and 0 < self.data_shards <= self.total_shards
            and self.shard_digest
            == digest({"protocol": "MOSAIC/ERASURE-SHARD/v1", "payload": self.payload.hex()})
        )


@dataclass(frozen=True)
class SamplingProof:
    object_id: str
    content_digest: str
    sampled_indices: tuple[int, ...]
    shard_digests: tuple[str, ...]
    proof_id: str

    @classmethod
    def create(cls, shards: Iterable[ErasureShard], sample_indices: Iterable[int]) -> "SamplingProof":
        shard_map = {item.shard_index: item for item in shards}
        indices = tuple(sorted(set(sample_indices)))
        if not indices or any(index not in shard_map for index in indices):
            raise AvailabilityError("sampling index is missing")
        selected = tuple(shard_map[index] for index in indices)
        if any(not item.verify() for item in selected):
            raise AvailabilityError("sampling contains invalid shard")
        first = selected[0]
        if any(item.object_id != first.object_id or item.content_digest != first.content_digest for item in selected):
            raise AvailabilityError("sampling shards do not match object")
        digests = tuple(item.shard_digest for item in selected)
        proof_id = digest(
            {
                "protocol": "MOSAIC/SAMPLING-PROOF/v1",
                "object_id": first.object_id,
                "content_digest": first.content_digest,
                "sampled_indices": indices,
                "shard_digests": digests,
            }
        )
        return cls(first.object_id, first.content_digest, indices, digests, proof_id)

    def verify(self) -> bool:
        return bool(self.sampled_indices) and self.proof_id == digest(
            {
                "protocol": "MOSAIC/SAMPLING-PROOF/v1",
                "object_id": self.object_id,
                "content_digest": self.content_digest,
                "sampled_indices": self.sampled_indices,
                "shard_digests": self.shard_digests,
            }
        ) and len(self.sampled_indices) == len(self.shard_digests)


class ErasureCodec:
    """Systematic Reed-Solomon codec requiring any k of n shards for recovery."""

    def __init__(self, data_shards: int, parity_shards: int):
        if data_shards <= 0 or parity_shards <= 0:
            raise AvailabilityError("data and parity shard counts must be positive")
        if data_shards + parity_shards > 255:
            raise AvailabilityError("GF(256) supports at most 255 shards")
        self.data_shards = data_shards
        self.parity_shards = parity_shards
        self.total_shards = data_shards + parity_shards

    @property
    def matrix(self) -> list[list[int]]:
        rows: list[list[int]] = []
        for row in range(self.total_shards):
            if row < self.data_shards:
                rows.append([1 if row == column else 0 for column in range(self.data_shards)])
            else:
                rows.append([_gf_pow(row + 1, column) for column in range(self.data_shards)])
        return rows

    def encode(self, object_id: str, payload: bytes) -> tuple[ErasureShard, ...]:
        if not object_id:
            raise AvailabilityError("object id cannot be empty")
        content_digest = digest({"protocol": "MOSAIC/OBJECT-DATA/v1", "payload": payload.hex()})
        framed = len(payload).to_bytes(8, "big") + payload
        shard_size = (len(framed) + self.data_shards - 1) // self.data_shards
        padded = framed.ljust(shard_size * self.data_shards, b"\0")
        data = [padded[offset : offset + shard_size] for offset in range(0, len(padded), shard_size)]
        all_payloads = _matrix_vector(self.matrix, data)
        return tuple(
            ErasureShard.create(
                object_id,
                content_digest,
                index,
                self.total_shards,
                self.data_shards,
                item,
            )
            for index, item in enumerate(all_payloads)
        )

    def recover(self, shards: Iterable[ErasureShard]) -> bytes:
        shard_map = {item.shard_index: item for item in shards}
        if len(shard_map) < self.data_shards:
            raise AvailabilityError("not enough shards for recovery")
        selected = tuple(shard_map[index] for index in sorted(shard_map)[: self.data_shards])
        if any(not item.verify() for item in selected):
            raise AvailabilityError("invalid shard in recovery set")
        first = selected[0]
        if any(
            item.object_id != first.object_id
            or item.content_digest != first.content_digest
            or item.total_shards != self.total_shards
            or item.data_shards != self.data_shards
            for item in selected
        ):
            raise AvailabilityError("incompatible shards")
        submatrix = [self.matrix[item.shard_index] for item in selected]
        data_matrix = _matrix_inverse(submatrix)
        data_payloads = _matrix_vector(data_matrix, [item.payload for item in selected])
        framed = b"".join(data_payloads)
        payload_size = int.from_bytes(framed[:8], "big")
        payload = framed[8 : 8 + payload_size]
        expected = digest({"protocol": "MOSAIC/OBJECT-DATA/v1", "payload": payload.hex()})
        if expected != first.content_digest:
            raise AvailabilityError("recovered payload digest mismatch")
        return payload

    def repair(self, shards: Iterable[ErasureShard], missing_indices: Iterable[int]) -> tuple[ErasureShard, ...]:
        available = tuple(shards)
        payload = self.recover(available)
        rebuilt = {item.shard_index: item for item in self.encode(available[0].object_id, payload)}
        missing = tuple(sorted(set(missing_indices)))
        if any(index < 0 or index >= self.total_shards for index in missing):
            raise AvailabilityError("repair index is outside shard set")
        return tuple(rebuilt[index] for index in missing)


class AvailabilityStore:
    """Node-local shard store with deterministic recovery and repair planning."""

    def __init__(self, codec: ErasureCodec):
        self.codec = codec
        self._objects: dict[str, dict[int, ErasureShard]] = {}

    def publish(self, object_id: str, payload: bytes) -> tuple[ErasureShard, ...]:
        shards = self.codec.encode(object_id, payload)
        self._objects[object_id] = {item.shard_index: item for item in shards}
        return shards

    def put(self, shard: ErasureShard) -> None:
        if shard.total_shards != self.codec.total_shards or shard.data_shards != self.codec.data_shards:
            raise AvailabilityError("shard codec parameters do not match store")
        if not shard.verify():
            raise AvailabilityError("invalid shard")
        existing = self._objects.setdefault(shard.object_id, {})
        if existing:
            first = next(iter(existing.values()))
            if first.content_digest != shard.content_digest:
                raise AvailabilityError("object shard content digest mismatch")
        existing[shard.shard_index] = shard

    def shards(self, object_id: str) -> tuple[ErasureShard, ...]:
        return tuple(self._objects.get(object_id, {}).values())

    def sample(self, object_id: str, sample_indices: Iterable[int]) -> SamplingProof:
        return SamplingProof.create(self.shards(object_id), sample_indices)

    def recover(self, object_id: str) -> bytes:
        return self.codec.recover(self.shards(object_id))

    def missing_indices(self, object_id: str) -> tuple[int, ...]:
        present = set(self._objects.get(object_id, {}))
        return tuple(index for index in range(self.codec.total_shards) if index not in present)

    def repair(self, object_id: str, source_shards: Iterable[ErasureShard] | None = None) -> tuple[ErasureShard, ...]:
        source = tuple(source_shards) if source_shards is not None else self.shards(object_id)
        missing = self.missing_indices(object_id)
        if not missing:
            return ()
        repaired = self.codec.repair(source, missing)
        for shard in repaired:
            self.put(shard)
        return repaired

    def available_weight(self, object_id: str, provider_weights: dict[int, int]) -> int:
        return sum(provider_weights.get(index, 0) for index in self._objects.get(object_id, {}))
