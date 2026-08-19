"""Local multi-process TCP network for the CCD/NEXUS prototype."""

from __future__ import annotations

import asyncio
import base64
import json
import random
import struct
import time
from dataclasses import dataclass, field
from typing import Any

from .crypto import canonical_bytes
from .domain import DomainExecutor
from .models import (
    Certificate,
    InputRef,
    ObjectState,
    Operation,
    Validator,
    Vote,
    WriteIntent,
)
from .quorum import QuorumCommittee, QuorumError

MAX_FRAME = 4 * 1024 * 1024


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def operation_to_wire(operation: Operation) -> dict[str, Any]:
    return {
        "op_id": operation.op_id,
        "epoch": operation.epoch,
        "signer": operation.signer,
        "signer_public_key": _b64(operation.signer_public_key),
        "domain_ids": list(operation.domain_ids),
        "inputs": [vars(item) for item in operation.inputs],
        "writes": [vars(item) for item in operation.writes],
        "parent_certificates": list(operation.parent_certificates),
        "nonce": operation.nonce,
        "signature": _b64(operation.signature),
    }


def operation_from_wire(data: dict[str, Any]) -> Operation:
    return Operation(
        op_id=data["op_id"],
        epoch=int(data["epoch"]),
        signer=data["signer"],
        signer_public_key=_unb64(data["signer_public_key"]),
        domain_ids=tuple(data["domain_ids"]),
        inputs=tuple(InputRef(**item) for item in data["inputs"]),
        writes=tuple(WriteIntent(**item) for item in data["writes"]),
        parent_certificates=tuple(data["parent_certificates"]),
        nonce=int(data["nonce"]),
        signature=_unb64(data["signature"]),
    )


def vote_to_wire(vote: Vote) -> dict[str, Any]:
    return {
        "validator_id": vote.validator_id,
        "epoch": vote.epoch,
        "domain_id": vote.domain_id,
        "object_versions": [list(item) for item in vote.object_versions],
        "op_id": vote.op_id,
        "dependency_digest": vote.dependency_digest,
        "phase": vote.phase,
        "signature": _b64(vote.signature),
    }


def vote_from_wire(data: dict[str, Any]) -> Vote:
    return Vote(
        validator_id=data["validator_id"],
        epoch=int(data["epoch"]),
        domain_id=data["domain_id"],
        object_versions=tuple((item[0], int(item[1])) for item in data["object_versions"]),
        op_id=data["op_id"],
        dependency_digest=data["dependency_digest"],
        phase=data["phase"],
        signature=_unb64(data["signature"]),
    )


def certificate_to_wire(certificate: Certificate) -> dict[str, Any]:
    return {
        "certificate_id": certificate.certificate_id,
        "epoch": certificate.epoch,
        "domain_ids": list(certificate.domain_ids),
        "op_id": certificate.op_id,
        "phase": certificate.phase,
        "signers": list(certificate.signers),
        "signatures": [[item, _b64(signature)] for item, signature in certificate.signatures],
        "statement_digest": certificate.statement_digest,
    }


def certificate_from_wire(data: dict[str, Any]) -> Certificate:
    return Certificate(
        certificate_id=data["certificate_id"],
        epoch=int(data["epoch"]),
        domain_ids=tuple(data["domain_ids"]),
        op_id=data["op_id"],
        phase=data["phase"],
        signers=tuple(data["signers"]),
        signatures=tuple((item[0], _unb64(item[1])) for item in data["signatures"]),
        statement_digest=data["statement_digest"],
    )


async def read_frame(reader: asyncio.StreamReader) -> dict[str, Any]:
    header = await reader.readexactly(4)
    (length,) = struct.unpack("!I", header)
    if length <= 0 or length > MAX_FRAME:
        raise ValueError("invalid frame length")
    payload = await reader.readexactly(length)
    return json.loads(payload.decode("utf-8"))


async def write_frame(writer: asyncio.StreamWriter, message: dict[str, Any]) -> int:
    payload = json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_FRAME:
        raise ValueError("message exceeds maximum frame size")
    frame = struct.pack("!I", len(payload)) + payload
    writer.write(frame)
    await writer.drain()
    return len(frame)


@dataclass
class DistributedNode:
    node_id: str
    host: str
    port: int
    peers: dict[str, tuple[str, int]]
    leader_id: str
    validator: Validator
    validators: dict[str, Validator]
    domain: DomainExecutor
    drop_rate: float = 0.0
    delay_ms: float = 0.0
    submit_timeout: float = 8.0
    max_retries: int = 2
    status_queue: Any = None
    server: asyncio.AbstractServer | None = None
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    metrics: dict[str, int] = field(
        default_factory=lambda: {
            "sent_messages": 0,
            "sent_bytes": 0,
            "received_messages": 0,
            "received_bytes": 0,
            "dropped_messages": 0,
            "errors": 0,
            "equivocations": 0,
            "retries": 0,
        }
    )

    async def run(self) -> None:
        self.server = await asyncio.start_server(self._handle_connection, self.host, self.port)
        self._status({"event": "started", "node_id": self.node_id, "port": self.port})
        async with self.server:
            await self.stop_event.wait()
        self._status({"event": "stopped", "node_id": self.node_id, "metrics": self.metrics})

    def _status(self, message: dict[str, Any]) -> None:
        if self.status_queue is not None:
            self.status_queue.put(message)

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            message = await read_frame(reader)
            raw = json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.metrics["received_messages"] += 1
            self.metrics["received_bytes"] += len(raw) + 4
            response = await self._dispatch(message)
            if response is not None:
                await write_frame(writer, response)
        except (asyncio.IncompleteReadError, ConnectionError, ValueError, KeyError) as exc:
            self.metrics["errors"] += 1
            if self.status_queue is not None:
                self._status({"event": "error", "node_id": self.node_id, "error": str(exc)})
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _send(self, peer_id: str, message: dict[str, Any]) -> None:
        if peer_id == self.node_id:
            await self._dispatch(message)
            return
        endpoint = self.peers.get(peer_id)
        if endpoint is None:
            self.metrics["errors"] += 1
            return
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                self.metrics["retries"] += 1
            if self.drop_rate > 0 and random.random() < self.drop_rate:
                self.metrics["dropped_messages"] += 1
                continue
            if self.delay_ms > 0:
                await asyncio.sleep(self.delay_ms / 1000)
            try:
                reader, writer = await asyncio.open_connection(*endpoint)
                sent = await write_frame(writer, message)
                self.metrics["sent_messages"] += 1
                self.metrics["sent_bytes"] += sent
                writer.close()
                await writer.wait_closed()
                return
            except (ConnectionError, OSError, asyncio.TimeoutError):
                self.metrics["errors"] += 1
        return

    async def _broadcast(self, message: dict[str, Any], include_self: bool = True) -> None:
        tasks = [self._send(peer_id, message) for peer_id in self.peers]
        if include_self:
            tasks.append(self._send(self.node_id, message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _dispatch(self, message: dict[str, Any]) -> dict[str, Any] | None:
        message_type = message.get("type")
        if message_type == "SUBMIT":
            return await self._submit(operation_from_wire(message["operation"]))
        if message_type == "PREPARE_REQUEST":
            await self._on_prepare_request(
                operation_from_wire(message["operation"]),
                message["dac"],
                message["leader_id"],
            )
            return None
        if message_type == "PREPARE_VOTE":
            await self._on_prepare_vote(vote_from_wire(message["vote"]))
            return None
        if message_type == "COMMIT_REQUEST":
            await self._on_commit_request(
                operation_from_wire(message["operation"]),
                certificate_from_wire(message["prepare_certificate"]),
                message["leader_id"],
            )
            return None
        if message_type == "COMMIT_VOTE":
            await self._on_commit_vote(vote_from_wire(message["vote"]))
            return None
        if message_type == "COMMIT_CERTIFICATE":
            await self._on_commit_certificate(
                operation_from_wire(message["operation"]),
                certificate_from_wire(message["certificate"]),
                message["leader_id"],
            )
            return None
        if message_type == "ACK":
            await self._on_ack(message["op_id"], message["node_id"])
            return None
        if message_type == "SHUTDOWN":
            self.stop_event.set()
            return {"ok": True, "node_id": self.node_id}
        if message_type == "METRICS":
            return {"ok": True, "node_id": self.node_id, "metrics": self.metrics}
        self.metrics["errors"] += 1
        return {"ok": False, "error": f"unknown message type: {message_type}"}

    async def _submit(self, operation: Operation) -> dict[str, Any]:
        if self.node_id != self.leader_id:
            return {"ok": False, "error": "SUBMIT must be sent to the configured leader"}
        if operation.op_id in self.pending:
            return {"ok": False, "error": "operation is already pending"}
        self.domain.validate_operation(operation)
        dac = self.domain.committee.issue_dac(operation)
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending[operation.op_id] = {
            "operation": operation,
            "dac": dac,
            "future": future,
            "started_ns": time.perf_counter_ns(),
            "prepare_certificate": None,
            "commit_certificate": None,
            "ack_ids": set(),
        }
        request = {
            "type": "PREPARE_REQUEST",
            "leader_id": self.node_id,
            "operation": operation_to_wire(operation),
            "dac": {
                "certificate_id": dac.certificate_id,
                "epoch": dac.epoch,
                "op_id": dac.op_id,
                "payload_digest": dac.payload_digest,
                "signers": list(dac.signers),
                "signatures": [[item, _b64(signature)] for item, signature in dac.signatures],
                "statement_digest": dac.statement_digest,
            },
        }
        await self._broadcast(request)
        try:
            return await asyncio.wait_for(future, timeout=self.submit_timeout)
        except asyncio.TimeoutError:
            self.pending.pop(operation.op_id, None)
            return {"ok": False, "error": "commit timeout", "op_id": operation.op_id}

    def _parse_dac(self, data: dict[str, Any]):
        from .models import DataAvailabilityCertificate

        return DataAvailabilityCertificate(
            certificate_id=data["certificate_id"],
            epoch=int(data["epoch"]),
            op_id=data["op_id"],
            payload_digest=data["payload_digest"],
            signers=tuple(data["signers"]),
            signatures=tuple((item[0], _unb64(item[1])) for item in data["signatures"]),
            statement_digest=data["statement_digest"],
        )

    async def _on_prepare_request(
        self,
        operation: Operation,
        dac_data: dict[str, Any],
        leader_id: str,
    ) -> None:
        dac = self._parse_dac(dac_data)
        if not self.domain.committee.verify_dac(operation, dac):
            return
        self.domain.validate_operation(operation)
        object_versions = self.domain._object_versions(operation)
        vote = self.validator.sign_vote(
            epoch=operation.epoch,
            domain_id=self.domain.domain_id,
            object_versions=object_versions,
            op_id=operation.op_id,
            dependency_digest=operation.dependency_digest,
            phase="PREPARE",
        )
        self.domain.committee.record_vote(vote)
        await self._send(leader_id, {"type": "PREPARE_VOTE", "vote": vote_to_wire(vote)})
        if self.validator.byzantine:
            forged_vote = self.validator.sign_vote(
                epoch=operation.epoch,
                domain_id=self.domain.domain_id,
                object_versions=object_versions,
                op_id=operation.op_id,
                dependency_digest=operation.dependency_digest + "-equivocation",
                phase="PREPARE",
            )
            await self._send(leader_id, {"type": "PREPARE_VOTE", "vote": vote_to_wire(forged_vote)})

    async def _on_prepare_vote(self, vote: Vote) -> None:
        if self.node_id != self.leader_id:
            return
        pending = self.pending.get(vote.op_id)
        if pending is None:
            return
        try:
            self.domain.committee.record_vote(vote)
        except QuorumError:
            self.metrics["equivocations"] += 1
            return
        if pending["prepare_certificate"] is not None:
            return
        operation = pending["operation"]
        try:
            certificate = self.domain.committee.issue_certificate(
                epoch=operation.epoch,
                domain_id=self.domain.domain_id,
                object_versions=self.domain._object_versions(operation),
                operation=operation,
                phase="PREPARE",
            )
        except QuorumError:
            return
        pending["prepare_certificate"] = certificate
        request = {
            "type": "COMMIT_REQUEST",
            "leader_id": self.node_id,
            "operation": operation_to_wire(operation),
            "prepare_certificate": certificate_to_wire(certificate),
        }
        await self._broadcast(request)

    async def _on_commit_request(
        self,
        operation: Operation,
        prepare_certificate: Certificate,
        leader_id: str,
    ) -> None:
        if not self.domain.committee.verify_certificate(
            certificate=prepare_certificate,
            epoch=operation.epoch,
            domain_id=self.domain.domain_id,
            object_versions=self.domain._object_versions(operation),
            operation=operation,
        ):
            return
        self.domain.validate_operation(operation)
        object_versions = self.domain._object_versions(operation)
        vote = self.validator.sign_vote(
            epoch=operation.epoch,
            domain_id=self.domain.domain_id,
            object_versions=object_versions,
            op_id=operation.op_id,
            dependency_digest=operation.dependency_digest,
            phase="COMMIT",
        )
        self.domain.committee.record_vote(vote)
        await self._send(leader_id, {"type": "COMMIT_VOTE", "vote": vote_to_wire(vote)})
        if self.validator.byzantine:
            forged_vote = self.validator.sign_vote(
                epoch=operation.epoch,
                domain_id=self.domain.domain_id,
                object_versions=object_versions,
                op_id=operation.op_id,
                dependency_digest=operation.dependency_digest + "-equivocation",
                phase="COMMIT",
            )
            await self._send(leader_id, {"type": "COMMIT_VOTE", "vote": vote_to_wire(forged_vote)})

    async def _on_commit_vote(self, vote: Vote) -> None:
        if self.node_id != self.leader_id:
            return
        pending = self.pending.get(vote.op_id)
        if pending is None:
            return
        try:
            self.domain.committee.record_vote(vote)
        except QuorumError:
            self.metrics["equivocations"] += 1
            return
        if pending["commit_certificate"] is not None:
            return
        operation = pending["operation"]
        try:
            certificate = self.domain.committee.issue_certificate(
                epoch=operation.epoch,
                domain_id=self.domain.domain_id,
                object_versions=self.domain._object_versions(operation),
                operation=operation,
                phase="COMMIT",
            )
        except QuorumError:
            return
        pending["commit_certificate"] = certificate
        self.domain.apply_committed(operation, certificate)
        pending["ack_ids"].add(self.node_id)
        request = {
            "type": "COMMIT_CERTIFICATE",
            "leader_id": self.node_id,
            "operation": operation_to_wire(operation),
            "certificate": certificate_to_wire(certificate),
        }
        await self._broadcast(request, include_self=False)
        await self._maybe_finish(operation.op_id)

    async def _on_commit_certificate(
        self,
        operation: Operation,
        certificate: Certificate,
        leader_id: str,
    ) -> None:
        if self.node_id == self.leader_id:
            return
        if not self.domain.committee.verify_certificate(
            certificate=certificate,
            epoch=operation.epoch,
            domain_id=self.domain.domain_id,
            object_versions=self.domain._object_versions(operation),
            operation=operation,
        ):
            return
        self.domain.apply_committed(operation, certificate)
        await self._send(
            leader_id,
            {"type": "ACK", "op_id": operation.op_id, "node_id": self.node_id},
        )

    async def _on_ack(self, op_id: str, node_id: str) -> None:
        pending = self.pending.get(op_id)
        if pending is None:
            return
        pending["ack_ids"].add(node_id)
        await self._maybe_finish(op_id)

    async def _maybe_finish(self, op_id: str) -> None:
        pending = self.pending.get(op_id)
        if pending is None or pending["future"].done():
            return
        ack_ids = pending["ack_ids"]
        try:
            ack_weight = self.domain.committee.weight_of(ack_ids)
        except KeyError:
            return
        if ack_weight < self.domain.committee.threshold:
            return
        elapsed_ms = (time.perf_counter_ns() - pending["started_ns"]) / 1_000_000
        result = {
            "ok": True,
            "op_id": op_id,
            "certificate_id": pending["commit_certificate"].certificate_id,
            "ack_ids": sorted(ack_ids),
            "ack_weight": ack_weight,
            "finality_ms": round(elapsed_ms, 4),
            "leader_metrics": dict(self.metrics),
        }
        pending["future"].set_result(result)
        self.pending.pop(op_id, None)
