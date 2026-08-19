"""Run a real localhost multi-process CCD/NEXUS cluster."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import multiprocessing as mp
import queue
import time
from pathlib import Path

from ccd_nexus import (
    AdmissionCertificate,
    DomainExecutor,
    InputRef,
    KeyPair,
    MembershipRegistry,
    ObjectState,
    Operation,
    QuorumCommittee,
    Validator,
    WriteIntent,
)
from ccd_nexus.network import DistributedNode, certificate_from_wire, operation_to_wire, read_frame, write_frame


def encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def admission_to_wire(certificate: AdmissionCertificate) -> dict:
    return {
        "certificate_id": certificate.certificate_id,
        "epoch": certificate.epoch,
        "validator_id": certificate.validator_id,
        "public_key": encode(certificate.public_key),
        "deposit_id": certificate.deposit_id,
        "stake": certificate.stake,
        "signatory": certificate.signatory,
        "authority_signature": encode(certificate.authority_signature),
        "statement_digest": certificate.statement_digest,
    }


def admission_from_wire(data: dict) -> AdmissionCertificate:
    return AdmissionCertificate(
        certificate_id=data["certificate_id"],
        epoch=int(data["epoch"]),
        validator_id=data["validator_id"],
        public_key=base64.b64decode(data["public_key"]),
        deposit_id=data["deposit_id"],
        stake=int(data["stake"]),
        signatory=data["signatory"],
        authority_signature=base64.b64decode(data["authority_signature"]),
        statement_digest=data["statement_digest"],
    )


def node_process_main(config: dict, status_queue) -> None:
    authority = KeyPair.from_private_bytes(base64.b64decode(config["authority_private"]))
    registry = MembershipRegistry(authority, min_stake=int(config["min_stake"]), epoch=config["epoch"])
    for admission_data in config["admissions"]:
        registry.register_external_certificate(admission_from_wire(admission_data))
    validators = {}
    for validator_id, item in config["validators"].items():
        keypair = KeyPair.from_private_bytes(base64.b64decode(item["private"]))
        admission = registry.records.get(validator_id)
        if admission is None or admission.public_key != keypair.public_key:
            raise RuntimeError(f"validator {validator_id} is not admitted by membership registry")
        validators[validator_id] = Validator(
            validator_id,
            keypair,
            weight=admission.stake,
            byzantine=(validator_id == config.get("byzantine_id")),
        )
    committee = QuorumCommittee(validators)
    domain = DomainExecutor(config["domain_id"], config["epoch"], committee)
    for object_id, payload in config["objects"].items():
        domain.add_object(
            ObjectState(
                object_id=object_id,
                version=0,
                owner=config["client_id"],
                payload=payload,
                domain_id=config["domain_id"],
            )
        )
    node = DistributedNode(
        node_id=config["node_id"],
        host=config["host"],
        port=config["port"],
        peers={item: tuple(endpoint) for item, endpoint in config["peers"].items()},
        leader_id=config["leader_id"],
        validator=validators[config["node_id"]],
        validators=validators,
        domain=domain,
        delay_ms=float(config.get("delay_ms", 0.0)),
        drop_rate=float(config.get("drop_rate", 0.0)),
        status_queue=status_queue,
    )
    asyncio.run(node.run())


async def request(host: str, port: int, message: dict) -> dict:
    reader, writer = await asyncio.open_connection(host, port)
    await write_frame(writer, message)
    response = await asyncio.wait_for(read_frame(reader), timeout=20)
    writer.close()
    await writer.wait_closed()
    return response


def wait_for_started(status_queue, expected: int, timeout: float = 10.0) -> list[dict]:
    started = []
    deadline = time.time() + timeout
    while len(started) < expected and time.time() < deadline:
        try:
            item = status_queue.get(timeout=0.25)
        except queue.Empty:
            continue
        if item.get("event") == "started":
            started.append(item)
    if len(started) != expected:
        raise RuntimeError(f"only {len(started)}/{expected} nodes started: {started}")
    return started


def make_configs(node_count: int, base_port: int, client_id: str, object_count: int) -> tuple[list[dict], KeyPair]:
    client_key = KeyPair.generate()
    authority_key = KeyPair.generate()
    registry = MembershipRegistry(authority_key, min_stake=10, epoch=0)
    validator_keys = {f"validator-{index}": KeyPair.generate() for index in range(node_count)}
    admissions = {
        validator_id: registry.admit(
            validator_id=validator_id,
            public_key=keypair.public_key,
            deposit_id=f"deposit-{validator_id}",
            stake=10,
        )
        for validator_id, keypair in validator_keys.items()
    }
    endpoints = {
        node_id: ("127.0.0.1", base_port + index)
        for index, node_id in enumerate(validator_keys)
    }
    configs = []
    for node_id, keypair in validator_keys.items():
        peers = {peer_id: endpoint for peer_id, endpoint in endpoints.items() if peer_id != node_id}
        configs.append(
            {
                "node_id": node_id,
                "host": "127.0.0.1",
                "port": endpoints[node_id][1],
                "peers": peers,
                "leader_id": "validator-0",
                "validators": {
                    item: {"private": encode(peer_key.private_bytes)}
                    for item, peer_key in validator_keys.items()
                },
                "authority_private": encode(authority_key.private_bytes),
                "min_stake": registry.min_stake,
                "admissions": [admission_to_wire(admissions[item]) for item in sorted(admissions)],
                "domain_id": "D1",
                "epoch": 0,
                "client_id": client_id,
                "objects": {f"obj-{index}": "initial" for index in range(object_count)},
            }
        )
    return configs, client_key


def run_cluster(
    node_count: int,
    operations: int,
    base_port: int,
    delay_ms: float = 0.0,
    drop_rate: float = 0.0,
    byzantine_id: str | None = None,
) -> dict:
    context = mp.get_context("fork")
    status_queue = context.Queue()
    configs, client_key = make_configs(node_count, base_port, "client-placeholder", operations)
    client_id = client_key.identity
    for config in configs:
        config["client_id"] = client_id
        config["delay_ms"] = delay_ms
        config["drop_rate"] = drop_rate
        config["byzantine_id"] = byzantine_id

    processes = [context.Process(target=node_process_main, args=(config, status_queue)) for config in configs]
    for process in processes:
        process.start()
    wait_for_started(status_queue, node_count)

    durations = []
    results = []
    leader_port = base_port
    for index in range(operations):
        operation = Operation.create(
            keypair=client_key,
            epoch=0,
            domain_ids=("D1",),
            inputs=(InputRef("D1", f"obj-{index}", 0),),
            writes=(WriteIntent("D1", f"obj-{index}", 0, client_id, f"payload-{index}"),),
            nonce=index,
        )
        started = time.perf_counter_ns()
        result = asyncio.run(
            request(
                "127.0.0.1",
                leader_port,
                {"type": "SUBMIT", "operation": operation_to_wire(operation)},
            )
        )
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
        results.append(result)

    metrics = []
    for config in configs:
        metrics.append(
            asyncio.run(request(config["host"], config["port"], {"type": "METRICS"}))
        )
    for config in configs:
        try:
            asyncio.run(request(config["host"], config["port"], {"type": "SHUTDOWN"}))
        except Exception:
            pass
    for process in processes:
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)

    ordered = sorted(durations)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    successful = sum(1 for result in results if result.get("ok"))
    return {
        "node_count": node_count,
        "operations": operations,
        "delay_ms_per_message": delay_ms,
        "drop_rate": drop_rate,
        "byzantine_id": byzantine_id,
        "successful_operations": successful,
        "p50_finality_ms": ordered[len(ordered) // 2],
        "p95_finality_ms": p95,
        "durations_ms": durations,
        "node_metrics": metrics,
        "scope": "real localhost TCP processes; injected Byzantine node and transport faults are local test conditions only",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=4)
    parser.add_argument("--operations", type=int, default=10)
    parser.add_argument("--base-port", type=int, default=18700)
    parser.add_argument("--delay-ms", type=float, default=0.0)
    parser.add_argument("--byzantine-id", type=str, default=None)
    parser.add_argument("--drop-rate", type=float, default=0.0)
    args = parser.parse_args()
    result = run_cluster(
        args.nodes,
        args.operations,
        args.base_port,
        args.delay_ms,
        drop_rate=args.drop_rate,
        byzantine_id=args.byzantine_id,
    )
    output = Path(__file__).resolve().parents[1] / "docs" / "distributed_network_result.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
