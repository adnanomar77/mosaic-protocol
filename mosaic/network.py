"""Leaderless gossip transport for MOSAIC v1 reference network."""

from __future__ import annotations

import asyncio
import base64
import json
import random
import ssl
import struct
import time
from dataclasses import dataclass, field
from typing import Any

from ccd_nexus.crypto import digest

from .model import Capsule, CapsuleInvalid, ClosureInvalid, ClosureProof, StateSeal, WitnessReceipt
from .protocol import ConflictDetected, MosaicProtocol
from .availability_network import (
    AvailabilityCoordinator,
    AvailabilityNetworkError,
    sampling_to_wire,
    shard_from_wire,
    shard_to_wire,
)
from .beacon import (
    BeaconRoundCoordinator,
    BeaconRoundError,
    commitment_from_wire,
    commitment_to_wire,
    reveal_from_wire,
    reveal_to_wire,
)
from .onboarding import (
    AdmissionCoordinator,
    OnboardingError,
    admission_certificate_to_wire,
    admission_from_wire,
    admission_to_wire,
    bond_from_wire,
    bond_to_wire,
)
from .storage import DurableStore
from .security import ReplayGuard, TokenBucket

MAX_FRAME = 4 * 1024 * 1024


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def unb64(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError("invalid base64 wire field") from exc


def seal_to_wire(seal: StateSeal) -> dict:
    return {
        "resource_id": seal.resource_id,
        "epoch": seal.epoch,
        "version": seal.version,
        "state_root": seal.state_root,
        "capability_hash": seal.capability_hash,
        "owner": seal.owner,
    }


def seal_from_wire(data: dict) -> StateSeal:
    return StateSeal(
        resource_id=data["resource_id"],
        epoch=int(data["epoch"]),
        version=int(data["version"]),
        state_root=data["state_root"],
        capability_hash=data["capability_hash"],
        owner=data["owner"],
    )


def capsule_to_wire(capsule: Capsule) -> dict:
    return {
        "capsule_id": capsule.capsule_id,
        "predecessor_id": capsule.predecessor_id,
        "successor_root": capsule.successor_root,
        "rule_id": capsule.rule_id,
        "rule_witness": capsule.rule_witness,
        "bundle_id": capsule.bundle_id,
        "attempt": capsule.attempt,
        "epoch": capsule.epoch,
        "client_id": capsule.client_id,
        "client_public_key": b64(capsule.client_public_key),
        "client_signature": b64(capsule.client_signature),
    }


def capsule_from_wire(data: dict) -> Capsule:
    return Capsule(
        capsule_id=data["capsule_id"],
        predecessor_id=data["predecessor_id"],
        successor_root=data["successor_root"],
        rule_id=data["rule_id"],
        rule_witness=data["rule_witness"],
        bundle_id=data["bundle_id"],
        attempt=int(data["attempt"]),
        epoch=int(data["epoch"]),
        client_id=data["client_id"],
        client_public_key=unb64(data["client_public_key"]),
        client_signature=unb64(data["client_signature"]),
    )


def receipt_to_wire(receipt: WitnessReceipt) -> dict:
    return {
        "capsule_id": receipt.capsule_id,
        "predecessor_id": receipt.predecessor_id,
        "witness_id": receipt.witness_id,
        "epoch": receipt.epoch,
        "attempt": receipt.attempt,
        "status": receipt.status,
        "signature": b64(receipt.signature),
    }


def receipt_from_wire(data: dict) -> WitnessReceipt:
    return WitnessReceipt(
        capsule_id=data["capsule_id"],
        predecessor_id=data["predecessor_id"],
        witness_id=data["witness_id"],
        epoch=int(data["epoch"]),
        attempt=int(data["attempt"]),
        status=data["status"],
        signature=unb64(data["signature"]),
    )


def closure_to_wire(closure: ClosureProof) -> dict:
    return {
        "capsule_id": closure.capsule_id,
        "predecessor_id": closure.predecessor_id,
        "epoch": closure.epoch,
        "attempt": closure.attempt,
        "signer_ids": list(closure.signer_ids),
        "receipts": [receipt_to_wire(receipt) for receipt in closure.receipts],
        "proof_id": closure.proof_id,
    }


def closure_from_wire(data: dict) -> ClosureProof:
    return ClosureProof(
        capsule_id=data["capsule_id"],
        predecessor_id=data["predecessor_id"],
        epoch=int(data["epoch"]),
        attempt=int(data["attempt"]),
        signer_ids=tuple(data["signer_ids"]),
        receipts=tuple(receipt_from_wire(item) for item in data["receipts"]),
        proof_id=data["proof_id"],
    )


async def read_frame(reader: asyncio.StreamReader) -> dict:
    header = await reader.readexactly(4)
    (length,) = struct.unpack("!I", header)
    if length <= 0 or length > MAX_FRAME:
        raise ValueError("invalid frame length")
    return json.loads((await reader.readexactly(length)).decode("utf-8"))


async def write_frame(writer: asyncio.StreamWriter, message: dict) -> int:
    payload = json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_FRAME:
        raise ValueError("frame too large")
    writer.write(struct.pack("!I", len(payload)) + payload)
    await writer.drain()
    return len(payload) + 4


@dataclass
class MosaicNode:
    node_id: str
    host: str
    port: int
    peers: dict[str, tuple[str, int]]
    protocol: MosaicProtocol
    membership: object | None = None
    onboarding: AdmissionCoordinator | None = None
    beacon: BeaconRoundCoordinator | None = None
    availability: AvailabilityCoordinator | None = None
    store: DurableStore | None = None
    ssl_context: ssl.SSLContext | None = None
    client_ssl_context: ssl.SSLContext | None = None
    delay_ms: float = 0.0
    drop_rate: float = 0.0
    retries: int = 2
    byzantine_id: str | None = None
    byzantine_ids: tuple[str, ...] = ()
    equivocate: bool = False
    submit_timeout: float = 8.0
    frame_timeout: float = 5.0
    connect_timeout: float = 3.0
    max_connections_per_peer: int = 64
    max_pending_capsules: int = 10_000
    peer_rate_capacity: float = 1000.0
    peer_rate_refill: float = 1000.0
    retry_backoff_ms: float = 5.0
    status_queue: Any = None
    server: asyncio.AbstractServer | None = None
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    pending: dict[str, dict] = field(default_factory=dict)
    receipt_pool: dict[str, dict[str, WitnessReceipt]] = field(default_factory=dict)
    receipt_history: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    seen_capsules: set[str] = field(default_factory=set)
    pending_capsules: dict[str, Capsule] = field(default_factory=dict)
    emitted_closures: set[str] = field(default_factory=set)
    replay_guard: ReplayGuard = field(default_factory=ReplayGuard)
    rate_limiter: TokenBucket = field(default_factory=lambda: TokenBucket(1000, 1000))
    peer_limiters: dict[str, TokenBucket] = field(default_factory=dict)
    peer_connections: dict[str, int] = field(default_factory=dict)
    onboarding_requests: set[str] = field(default_factory=set)
    metrics: dict[str, int] = field(default_factory=lambda: {
        "sent_messages": 0,
        "sent_bytes": 0,
        "received_messages": 0,
        "received_bytes": 0,
        "dropped_messages": 0,
        "retries": 0,
        "errors": 0,
        "error_types": {},
        "error_details": {},
        "protocol_rejections": 0,
        "conflicts": 0,
        "transport_failures": 0,
        "frame_timeouts": 0,
        "malformed_frames": 0,
        "rate_limited": 0,
        "closures_issued": 0,
        "replay_rejected": 0,
        "admissions": 0,
        "onboarding_restored": 0,
        "beacon_commits": 0,
        "beacon_reveals": 0,
        "beacon_finalizations": 0,
        "availability_puts": 0,
        "availability_fetches": 0,
        "availability_samples": 0,
        "availability_repairs": 0,
    })

    async def run(self) -> None:
        self._restore()
        self.server = await asyncio.start_server(
            self._handle,
            self.host,
            self.port,
            ssl=self.ssl_context,
        )
        self._status({"event": "started", "node_id": self.node_id, "port": self.port})
        async with self.server:
            await self.stop_event.wait()
        if self.store is not None:
            self.store.checkpoint()
            self.store.close()
        self._status({"event": "stopped", "node_id": self.node_id, "metrics": self.metrics})

    def _status(self, message: dict) -> None:
        if self.status_queue is not None:
            self.status_queue.put(message)

    def _restore(self) -> None:
        if self.store is None:
            return
        for _, payload in self.store.items("seal_known"):
            seal = seal_from_wire(payload)
            self.protocol.known_seals[seal.seal_id] = seal
        for _, payload in self.store.items("seal_current"):
            seal = seal_from_wire(payload)
            self.protocol.current_seals[seal.resource_id] = seal
        for _, payload in self.store.items("capsule"):
            capsule = capsule_from_wire(payload)
            self.protocol.capsules[capsule.capsule_id] = capsule
            self.seen_capsules.add(capsule.capsule_id)
        for _, payload in self.store.items("receipt"):
            receipt = receipt_from_wire(payload)
            self.receipt_pool.setdefault(receipt.capsule_id, {})[receipt.witness_id] = receipt
        for _, payload in self.store.items("closure"):
            closure = closure_from_wire(payload)
            capsule = self.protocol.capsules.get(closure.capsule_id)
            if capsule is not None:
                try:
                    self.protocol.register_closure(capsule, closure)
                except Exception:
                    self.metrics["errors"] += 1
        if self.availability is not None:
            try:
                self.availability.restore_from_store()
            except Exception as exc:
                self.metrics["errors"] += 1
                self._status({"event": "availability_restore_error", "node_id": self.node_id, "error": str(exc)})
        if self.onboarding is not None:
            try:
                restored = self.onboarding.restore_from_store()
                self.metrics["onboarding_restored"] = restored
                for _, payload in self.store.items("onboarding"):
                    request = admission_from_wire(payload["request"])
                    self.onboarding_requests.add(
                        digest({**request.statement(), "signature": request.applicant_signature.hex()})
                    )
            except Exception as exc:
                self.metrics["errors"] += 1
                self._status({"event": "onboarding_restore_error", "node_id": self.node_id, "error": str(exc)})

    def _persist(self, kind: str, key: str, payload: dict) -> None:
        if self.store is not None:
            self.store.put(kind, key, payload)

    def _persist_admission(self, request: object, bond: object, certificate: object) -> None:
        self._persist(
            "admission",
            certificate.certificate_id,
            {
                "request": admission_to_wire(request),
                "bond": bond_to_wire(bond),
                "certificate": admission_certificate_to_wire(certificate),
            },
        )

    def _persist_capsule(self, capsule: Capsule) -> None:
        self._persist("capsule", capsule.capsule_id, capsule_to_wire(capsule))

    def _persist_receipt(self, receipt: WitnessReceipt) -> None:
        self._persist("receipt", receipt.receipt_id, receipt_to_wire(receipt))

    def _persist_closure(self, capsule: Capsule, closure: ClosureProof) -> None:
        self._persist("closure", closure.proof_id, closure_to_wire(closure))
        predecessor = self.protocol.known_seals[capsule.predecessor_id]
        current = self.protocol.current_seals[predecessor.resource_id]
        self._persist("seal_known", predecessor.seal_id, seal_to_wire(predecessor))
        self._persist("seal_known", current.seal_id, seal_to_wire(current))
        self._persist("seal_current", current.resource_id, seal_to_wire(current))
        if self.store is not None:
            self.store.create_snapshot(
                f"{current.resource_id}:{current.seal_id}",
                {
                    "resource_id": current.resource_id,
                    "current_seal": seal_to_wire(current),
                    "closure_id": closure.proof_id,
                    "capsule_id": capsule.capsule_id,
                },
            )

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer_info = writer.get_extra_info("peername")
        peer_id = str(peer_info[0]) if isinstance(peer_info, tuple) and peer_info else "unknown"
        active = self.peer_connections.get(peer_id, 0)
        if active >= self.max_connections_per_peer:
            self.metrics["rate_limited"] += 1
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return
        self.peer_connections[peer_id] = active + 1
        limiter = self.peer_limiters.setdefault(
            peer_id,
            TokenBucket(self.peer_rate_capacity, self.peer_rate_refill),
        )
        try:
            message = await asyncio.wait_for(read_frame(reader), timeout=self.frame_timeout)
            if not self.rate_limiter.allow() or not limiter.allow():
                self.metrics["rate_limited"] += 1
                return
            message_id = message.get("message_id") or json.dumps(message, sort_keys=True, separators=(",", ":"))
            if not self.replay_guard.accept(message_id):
                self.metrics["replay_rejected"] += 1
                return
            self.metrics["received_messages"] += 1
            self.metrics["received_bytes"] += len(json.dumps(message, sort_keys=True)) + 4
            response = await self._dispatch(message)
            if response is not None:
                await write_frame(writer, response)
        except asyncio.TimeoutError:
            self.metrics["frame_timeouts"] += 1
        except asyncio.IncompleteReadError as exc:
            self.metrics["malformed_frames"] += 1
            self._status({"event": "malformed_frame", "node_id": self.node_id, "error": str(exc)})
        except (ConnectionError, OSError) as exc:
            self.metrics["transport_failures"] += 1
            self._status({"event": "transport_failure", "node_id": self.node_id, "error": str(exc)})
        except (ValueError, KeyError, AttributeError, TypeError) as exc:
            self.metrics["errors"] += 1
            name = type(exc).__name__
            self.metrics["error_types"][name] = self.metrics["error_types"].get(name, 0) + 1
            detail = str(exc)[:160]
            self.metrics["error_details"][detail] = self.metrics["error_details"].get(detail, 0) + 1
            self._status({"event": "error", "node_id": self.node_id, "error": str(exc)})
        finally:
            self.peer_connections[peer_id] = max(0, self.peer_connections.get(peer_id, 1) - 1)
            if self.peer_connections[peer_id] == 0:
                self.peer_connections.pop(peer_id, None)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _send(self, peer_id: str, message: dict) -> None:
        if peer_id == self.node_id:
            await self._dispatch(message)
            return
        endpoint = self.peers.get(peer_id)
        if endpoint is None:
            self.metrics["errors"] += 1
            return
        for attempt in range(self.retries + 1):
            if attempt:
                self.metrics["retries"] += 1
                await asyncio.sleep(self.retry_backoff_ms * (2 ** (attempt - 1)) / 1000)
            if self.drop_rate and random.random() < self.drop_rate:
                self.metrics["dropped_messages"] += 1
                continue
            if self.delay_ms:
                await asyncio.sleep(self.delay_ms / 1000)
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        *endpoint,
                        ssl=self.client_ssl_context,
                        server_hostname=endpoint[0] if self.client_ssl_context is not None else None,
                    ),
                    timeout=self.connect_timeout,
                )
                sent = await asyncio.wait_for(write_frame(writer, message), timeout=self.connect_timeout)
                self.metrics["sent_messages"] += 1
                self.metrics["sent_bytes"] += sent
                writer.close()
                await writer.wait_closed()
                return
            except (ConnectionError, OSError, asyncio.TimeoutError):
                self.metrics["transport_failures"] += 1

    async def _broadcast(self, message: dict) -> None:
        tasks = [self._send(peer_id, message) for peer_id in self.peers]
        tasks.append(self._send(self.node_id, message))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _dispatch(self, message: dict) -> dict | None:
        kind = message.get("type")
        if kind == "ADMISSION":
            return await self._admit(message)
        if kind == "BEACON_COMMIT":
            return await self._beacon_commit(message)
        if kind == "BEACON_REVEAL":
            return await self._beacon_reveal(message)
        if kind == "BEACON_FINALIZE":
            return await self._beacon_finalize(message)
        if kind == "AVAILABILITY_PUT":
            return await self._availability_put(message)
        if kind == "AVAILABILITY_FETCH":
            return await self._availability_fetch(message)
        if kind == "AVAILABILITY_SAMPLE":
            return await self._availability_sample(message)
        if kind == "AVAILABILITY_REPAIR":
            return await self._availability_repair(message)
        if kind == "SUBMIT":
            return await self._submit(capsule_from_wire(message["capsule"]))
        if kind == "CAPSULE":
            await self._on_capsule(capsule_from_wire(message["capsule"]))
            return None
        if kind == "RECEIPT":
            await self._on_receipt(receipt_from_wire(message["receipt"]))
            return None
        if kind == "CLOSURE":
            await self._on_closure(
                capsule_from_wire(message["capsule"]),
                closure_from_wire(message["closure"]),
            )
            return None
        if kind == "METRICS":
            return {"ok": True, "node_id": self.node_id, "metrics": self.metrics}
        if kind == "SHUTDOWN":
            self.stop_event.set()
            return {"ok": True, "node_id": self.node_id}
        self.metrics["errors"] += 1
        return {"ok": False, "error": f"unknown message: {kind}"}

    async def _admit(self, message: dict) -> dict:
        if self.onboarding is None:
            return {"ok": False, "error": "onboarding is disabled"}
        try:
            request = admission_from_wire(message["request"])
            bond = bond_from_wire(message["bond"])
            request_key = digest({**request.statement(), "signature": request.applicant_signature.hex()})
            if request_key in self.onboarding_requests:
                return {"ok": True, "duplicate": True, "node_id": self.node_id}
            certificate = self.onboarding.admit(request, bond)
            self.onboarding_requests.add(request_key)
            self.metrics["admissions"] += 1
            self._persist_admission(request, bond, certificate)
            if not message.get("gossip"):
                await self._broadcast(
                    {
                        "type": "ADMISSION",
                        "request": admission_to_wire(request),
                        "bond": bond_to_wire(bond),
                        "gossip": True,
                    }
                )
            return {
                "ok": True,
                "node_id": self.node_id,
                "certificate": admission_certificate_to_wire(certificate),
                "onboarding_root": self.onboarding.onboarding_root,
            }
        except (KeyError, ValueError, OnboardingError) as exc:
            self.metrics["protocol_rejections"] += 1
            return {"ok": False, "node_id": self.node_id, "error": str(exc)}

    async def _beacon_commit(self, message: dict) -> dict:
        if self.beacon is None:
            return {"ok": False, "error": "beacon is disabled"}
        try:
            commitment = commitment_from_wire(message["commitment"])
            self.beacon.submit_commitment(commitment)
            self.metrics["beacon_commits"] += 1
            if not message.get("gossip"):
                await self._broadcast(
                    {
                        "type": "BEACON_COMMIT",
                        "commitment": commitment_to_wire(commitment),
                        "gossip": True,
                    }
                )
            return {"ok": True, "node_id": self.node_id, "commitment": commitment_to_wire(commitment)}
        except (KeyError, ValueError, BeaconRoundError) as exc:
            self.metrics["protocol_rejections"] += 1
            return {"ok": False, "node_id": self.node_id, "error": str(exc)}

    async def _beacon_reveal(self, message: dict) -> dict:
        if self.beacon is None:
            return {"ok": False, "error": "beacon is disabled"}
        try:
            reveal = reveal_from_wire(message["reveal"])
            self.beacon.submit_reveal(reveal)
            self.metrics["beacon_reveals"] += 1
            if not message.get("gossip"):
                await self._broadcast(
                    {
                        "type": "BEACON_REVEAL",
                        "reveal": reveal_to_wire(reveal),
                        "gossip": True,
                    }
                )
            return {"ok": True, "node_id": self.node_id, "reveal": reveal_to_wire(reveal)}
        except (KeyError, ValueError, BeaconRoundError) as exc:
            self.metrics["protocol_rejections"] += 1
            return {"ok": False, "node_id": self.node_id, "error": str(exc)}

    async def _beacon_finalize(self, message: dict) -> dict:
        if self.beacon is None:
            return {"ok": False, "error": "beacon is disabled"}
        try:
            settlement = self.beacon.finalize(
                int(message["round"]),
                reveal_reward=int(message.get("reveal_reward", 1)),
                non_reveal_penalty=int(message.get("non_reveal_penalty", 1)),
            )
            self.metrics["beacon_finalizations"] += 1
            return {
                "ok": True,
                "node_id": self.node_id,
                "round": settlement.round,
                "beacon_mode": settlement.beacon.mode,
                "beacon_proof_id": settlement.beacon.proof_id,
                "membership_root": self.beacon.membership.snapshot.root,
                "settlement_root": self.beacon.settlement.state_root,
            }
        except (KeyError, ValueError, BeaconRoundError) as exc:
            self.metrics["protocol_rejections"] += 1
            return {"ok": False, "node_id": self.node_id, "error": str(exc)}

    async def _availability_put(self, message: dict) -> dict:
        if self.availability is None:
            return {"ok": False, "error": "availability is disabled"}
        try:
            shard = shard_from_wire(message["shard"])
            self.availability.put(shard)
            self.metrics["availability_puts"] += 1
            return {"ok": True, "node_id": self.node_id, "shard_index": shard.shard_index, "object_id": shard.object_id}
        except (KeyError, ValueError, AvailabilityNetworkError) as exc:
            self.metrics["protocol_rejections"] += 1
            return {"ok": False, "node_id": self.node_id, "error": str(exc)}

    async def _availability_fetch(self, message: dict) -> dict:
        if self.availability is None:
            return {"ok": False, "error": "availability is disabled"}
        try:
            shard = self.availability.fetch(message["object_id"], int(message["shard_index"]))
            self.metrics["availability_fetches"] += 1
            return {"ok": True, "node_id": self.node_id, "shard": shard_to_wire(shard)}
        except (KeyError, ValueError, AvailabilityNetworkError) as exc:
            self.metrics["protocol_rejections"] += 1
            return {"ok": False, "node_id": self.node_id, "error": str(exc)}

    async def _availability_sample(self, message: dict) -> dict:
        if self.availability is None:
            return {"ok": False, "error": "availability is disabled"}
        try:
            proof = self.availability.sample(message["object_id"], tuple(int(item) for item in message["indices"]))
            self.metrics["availability_samples"] += 1
            return {"ok": True, "node_id": self.node_id, "proof": sampling_to_wire(proof)}
        except (KeyError, ValueError, AvailabilityNetworkError) as exc:
            self.metrics["protocol_rejections"] += 1
            return {"ok": False, "node_id": self.node_id, "error": str(exc)}

    async def _availability_repair(self, message: dict) -> dict:
        if self.availability is None:
            return {"ok": False, "error": "availability is disabled"}
        try:
            source = tuple(shard_from_wire(item) for item in message["source_shards"])
            repaired = self.availability.repair(source, tuple(int(item) for item in message["missing_indices"]))
            self.metrics["availability_repairs"] += 1
            return {"ok": True, "node_id": self.node_id, "repaired": [shard_to_wire(item) for item in repaired]}
        except (KeyError, ValueError, AvailabilityNetworkError) as exc:
            self.metrics["protocol_rejections"] += 1
            return {"ok": False, "node_id": self.node_id, "error": str(exc)}

    async def _submit(self, capsule: Capsule) -> dict:
        if len(self.pending) >= self.max_pending_capsules:
            return {"ok": False, "error": "pending capsule capacity exhausted"}
        if capsule.capsule_id in self.pending:
            return {"ok": False, "error": "capsule already pending"}
        existing_closure = self.protocol.closures.get(capsule.capsule_id)
        if existing_closure is not None:
            predecessor = self.protocol.known_seals[capsule.predecessor_id]
            current = self.protocol.current_seals[predecessor.resource_id]
            return {
                "ok": True,
                "capsule_id": capsule.capsule_id,
                "closure_id": existing_closure.proof_id,
                "finality_ms": 0.0,
                "next_seal": seal_to_wire(current),
            }
        self.protocol.capsules[capsule.capsule_id] = capsule
        self._persist_capsule(capsule)
        try:
            self.protocol.validate_capsule(capsule)
        except (CapsuleInvalid, ConflictDetected) as exc:
            self.metrics["protocol_rejections"] += 1
            return {"ok": False, "capsule_id": capsule.capsule_id, "error": str(exc)}
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending[capsule.capsule_id] = {
            "capsule": capsule,
            "future": future,
            "started": time.perf_counter_ns(),
        }
        await self._broadcast({"type": "CAPSULE", "capsule": capsule_to_wire(capsule)})
        try:
            return await asyncio.wait_for(future, timeout=self.submit_timeout)
        except asyncio.TimeoutError:
            self.pending.pop(capsule.capsule_id, None)
            return {"ok": False, "capsule_id": capsule.capsule_id, "error": "closure timeout"}

    async def _on_capsule(self, capsule: Capsule) -> None:
        if capsule.capsule_id in self.seen_capsules:
            if capsule.capsule_id in self.protocol.closures:
                return
            try:
                receipt = self.protocol.witness_receipt(self.node_id, capsule, "ACCEPT")
            except (CapsuleInvalid, ConflictDetected):
                return
            await self._broadcast({"type": "RECEIPT", "receipt": receipt_to_wire(receipt)})
            return
        self.seen_capsules.add(capsule.capsule_id)
        self.protocol.capsules[capsule.capsule_id] = capsule
        self._persist_capsule(capsule)
        try:
            receipt = self.protocol.witness_receipt(self.node_id, capsule, "ACCEPT")
        except CapsuleInvalid:
            self.pending_capsules[capsule.capsule_id] = capsule
            return
        except ConflictDetected:
            self.metrics["conflicts"] += 1
            return
        await self._broadcast({"type": "RECEIPT", "receipt": receipt_to_wire(receipt)})
        if self.equivocate and (self.node_id == self.byzantine_id or self.node_id in self.byzantine_ids):
            member = self.protocol._member(self.node_id)
            contradictory = self.protocol._sign_receipt(member, capsule, "ABANDON")
            await self._broadcast({"type": "RECEIPT", "receipt": receipt_to_wire(contradictory)})

    async def _on_receipt(self, receipt: WitnessReceipt) -> None:
        history_key = (receipt.capsule_id, receipt.witness_id)
        receipt_ids = self.receipt_history.setdefault(history_key, set())
        if receipt.receipt_id in receipt_ids:
            return
        if receipt_ids:
            self.metrics["conflicts"] += 1
        receipt_ids.add(receipt.receipt_id)
        self.receipt_pool.setdefault(receipt.capsule_id, {})[receipt.witness_id] = receipt
        self._persist_receipt(receipt)
        capsule = self.protocol.capsules.get(receipt.capsule_id)
        if capsule is None or not self.protocol.verify_receipt(receipt):
            return
        await self._try_close(capsule)

    async def _try_close(self, capsule: Capsule) -> None:
        if capsule.capsule_id in self.protocol.closures:
            await self._finish_pending(capsule.capsule_id)
            return
        pool = self.receipt_pool.get(capsule.capsule_id, {})
        valid = tuple(
            receipt
            for receipt in pool.values()
            if receipt.status == "ACCEPT"
            and self.protocol.verify_receipt(receipt)
        )
        weight = sum(self.protocol.members[item.witness_id].weight for item in valid)
        if weight < self.protocol.threshold:
            return
        try:
            closure = ClosureProof.create(valid)
            self.protocol.register_closure(capsule, closure)
            self.protocol.apply(capsule, closure)
            self._persist_closure(capsule, closure)
        except (ClosureInvalid, ConflictDetected, CapsuleInvalid) as exc:
            self.metrics["protocol_rejections"] += 1
            self._status({"event": "closure_rejected", "node_id": self.node_id, "error": str(exc)})
            return
        except Exception as exc:
            self.metrics["errors"] += 1
            name = type(exc).__name__
            self.metrics["error_types"][name] = self.metrics["error_types"].get(name, 0) + 1
            detail = str(exc)[:160]
            self.metrics["error_details"][detail] = self.metrics["error_details"].get(detail, 0) + 1
            self._status({"event": "closure_error", "node_id": self.node_id, "error": str(exc)})
            return
        if closure.proof_id not in self.emitted_closures:
            self.emitted_closures.add(closure.proof_id)
            self.metrics["closures_issued"] += 1
            await self._broadcast({
                "type": "CLOSURE",
                "capsule": capsule_to_wire(capsule),
                "closure": closure_to_wire(closure),
            })
        await self._finish_pending(capsule.capsule_id)

    async def _on_closure(self, capsule: Capsule, closure: ClosureProof) -> None:
        self.protocol.capsules[capsule.capsule_id] = capsule
        self._persist_capsule(capsule)
        try:
            self.protocol.register_closure(capsule, closure)
            self.protocol.apply(capsule, closure)
            self._persist_closure(capsule, closure)
            await self._retry_pending()
        except (ClosureInvalid, ConflictDetected, CapsuleInvalid) as exc:
            self.metrics["protocol_rejections"] += 1
            self._status({"event": "closure_rejected", "node_id": self.node_id, "error": str(exc)})
            return
        except Exception as exc:
            self.metrics["errors"] += 1
            self._status({"event": "closure_error", "node_id": self.node_id, "error": str(exc)})
            return
        await self._finish_pending(capsule.capsule_id)

    async def _retry_pending(self) -> None:
        for capsule_id, capsule in list(self.pending_capsules.items()):
            predecessor = self.protocol.known_seals.get(capsule.predecessor_id)
            if predecessor is None:
                continue
            current = self.protocol.current_seals.get(predecessor.resource_id)
            if current is not None and current.seal_id == capsule.predecessor_id:
                self.pending_capsules.pop(capsule_id, None)
                self.seen_capsules.discard(capsule_id)
                await self._on_capsule(capsule)

    async def _finish_pending(self, capsule_id: str) -> None:
        pending = self.pending.get(capsule_id)
        if pending is None or pending["future"].done():
            return
        capsule = pending["capsule"]
        predecessor = self.protocol.known_seals[capsule.predecessor_id]
        current = self.protocol.current_seals[predecessor.resource_id]
        pending["future"].set_result({
            "ok": True,
            "capsule_id": capsule_id,
            "closure_id": self.protocol.closures[capsule_id].proof_id,
            "finality_ms": round((time.perf_counter_ns() - pending["started"]) / 1_000_000, 4),
            "next_seal": seal_to_wire(current),
        })
        self.pending.pop(capsule_id, None)
