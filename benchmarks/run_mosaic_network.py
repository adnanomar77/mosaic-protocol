"""Run MOSAIC leaderless reference nodes as independent localhost TCP processes."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import multiprocessing as mp
import queue
import time
from pathlib import Path

from ccd_nexus import KeyPair
from ccd_nexus.crypto import digest
from mosaic import Member, MosaicProtocol, StateSeal
from mosaic.network import (
    MosaicNode,
    capsule_to_wire,
    read_frame,
    seal_from_wire,
    seal_to_wire,
    write_frame,
)
from mosaic.model import Capsule
from mosaic.storage import DurableStore


def enc(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def node_main(config: dict, status_queue) -> None:
    members = {
        member_id: Member(
            member_id,
            KeyPair.from_private_bytes(base64.b64decode(item["private"])) if item.get("private") else None,
            weight=int(item["weight"]),
            public_key_override=base64.b64decode(item["public"]),
        )
        for member_id, item in config["members"].items()
    }
    protocol = MosaicProtocol(members, epoch=int(config["epoch"]))
    for item in config["initial_seals"]:
        seal = seal_from_wire(item)
        protocol.current_seals[seal.resource_id] = seal
        protocol.known_seals[seal.seal_id] = seal
    node = MosaicNode(
        node_id=config["node_id"],
        host=config["host"],
        port=int(config["port"]),
        peers={item: tuple(endpoint) for item, endpoint in config["peers"].items()},
        protocol=protocol,
        store=DurableStore(config["store_path"]),
        delay_ms=float(config.get("delay_ms", 0.0)),
        drop_rate=float(config.get("drop_rate", 0.0)),
        byzantine_id=config.get("byzantine_id"),
        byzantine_ids=tuple(config.get("byzantine_ids", ())),
        equivocate=bool(config.get("equivocate", False)),
        submit_timeout=float(config.get("submit_timeout", 8.0)),
        frame_timeout=float(config.get("frame_timeout", 5.0)),
        connect_timeout=float(config.get("connect_timeout", 3.0)),
        max_connections_per_peer=int(config.get("max_connections_per_peer", 64)),
        max_pending_capsules=int(config.get("max_pending_capsules", 10000)),
        peer_rate_capacity=float(config.get("peer_rate_capacity", 1000.0)),
        peer_rate_refill=float(config.get("peer_rate_refill", 1000.0)),
        retry_backoff_ms=float(config.get("retry_backoff_ms", 5.0)),
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


def wait_started(status_queue, expected: int) -> None:
    started = 0
    deadline = time.time() + 10
    while started < expected and time.time() < deadline:
        try:
            item = status_queue.get(timeout=0.25)
        except queue.Empty:
            continue
        if item.get("event") == "started":
            started += 1
    if started != expected:
        raise RuntimeError(f"only {started}/{expected} MOSAIC nodes started")


def make_configs(node_count: int, base_port: int, client: KeyPair, operations: int) -> tuple[list[dict], StateSeal]:
    member_keys = {f"w{index}": KeyPair.generate() for index in range(node_count)}
    endpoints = {member_id: ("127.0.0.1", base_port + index) for index, member_id in enumerate(member_keys)}
    genesis = StateSeal(
        resource_id="asset",
        epoch=0,
        version=0,
        state_root="genesis",
        capability_hash=digest("capability"),
        owner=client.identity,
    )
    configs = []
    for node_id in member_keys:
        configs.append(
            {
                "node_id": node_id,
                "host": "127.0.0.1",
                "port": endpoints[node_id][1],
                "peers": {peer: endpoint for peer, endpoint in endpoints.items() if peer != node_id},
                "epoch": 0,
                "members": {
                    member_id: {
                        "private": enc(key.private_bytes) if member_id == node_id else None,
                        "public": enc(key.public_key),
                        "weight": 1,
                    }
                    for member_id, key in member_keys.items()
                },
                "initial_seals": [seal_to_wire(genesis)],
                "operations": operations,
            }
        )
    return configs, genesis


def run_cluster(
    node_count: int,
    operations: int,
    base_port: int,
    delay_ms: float = 0.0,
    drop_rate: float = 0.0,
    byzantine_id: str | None = None,
    data_dir: str = "/tmp/mosaic-network",
    byzantine_ids: tuple[str, ...] = (),
) -> dict:
    context = mp.get_context("fork")
    status_queue = context.Queue()
    client = KeyPair.generate()
    configs, predecessor = make_configs(node_count, base_port, client, operations)
    for config in configs:
        config["store_path"] = str(Path(data_dir) / f"{config['node_id']}.sqlite")
        Path(config["store_path"]).unlink(missing_ok=True)
        config["delay_ms"] = delay_ms
        config["drop_rate"] = drop_rate
        config["byzantine_id"] = byzantine_id
        config["byzantine_ids"] = list(byzantine_ids)
        config["equivocate"] = byzantine_id == config["node_id"] or config["node_id"] in byzantine_ids
    processes = [context.Process(target=node_main, args=(config, status_queue)) for config in configs]
    for process in processes:
        process.start()
    wait_started(status_queue, node_count)

    durations = []
    results = []
    for index in range(operations):
        capsule = Capsule.create(
            client=client,
            predecessor=predecessor,
            successor_root=f"state-{index + 1}",
            rule_id="identity-transition",
            rule_witness="valid",
            attempt=index,
        )
        started = time.perf_counter_ns()
        target = configs[index % node_count]
        result = asyncio.run(
            request(
                target["host"],
                target["port"],
                {"type": "SUBMIT", "capsule": capsule_to_wire(capsule)},
            )
        )
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
        results.append(result)
        if not result.get("ok"):
            break
        predecessor = seal_from_wire(result["next_seal"])

    time.sleep(0.25)
    status_events = []
    while True:
        try:
            status_events.append(status_queue.get_nowait())
        except queue.Empty:
            break
    node_metrics = []
    for config in configs:
        node_metrics.append(asyncio.run(request(config["host"], config["port"], {"type": "METRICS"})))
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
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)] if ordered else None
    return {
        "nodes": node_count,
        "operations_requested": operations,
        "operations_successful": sum(1 for item in results if item.get("ok")),
        "delay_ms": delay_ms,
        "drop_rate": drop_rate,
        "byzantine_id": byzantine_id,
        "byzantine_ids": list(byzantine_ids),
        "p50_ms": ordered[len(ordered) // 2] if ordered else None,
        "p95_ms": p95,
        "durations_ms": durations,
        "node_metrics": node_metrics,
        "status_events": status_events,
        "scope": "independent localhost TCP processes; leaderless receipt gossip; Ed25519 receipts and closure",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=4)
    parser.add_argument("--operations", type=int, default=10)
    parser.add_argument("--base-port", type=int, default=19100)
    parser.add_argument("--delay-ms", type=float, default=0.0)
    parser.add_argument("--drop-rate", type=float, default=0.0)
    parser.add_argument("--byzantine-id", type=str, default=None)
    parser.add_argument("--byzantine-ids", type=str, default="")
    parser.add_argument("--data-dir", type=str, default="/tmp/mosaic-network")
    args = parser.parse_args()
    result = run_cluster(
        args.nodes,
        args.operations,
        args.base_port,
        args.delay_ms,
        args.drop_rate,
        args.byzantine_id,
        args.data_dir,
        tuple(item for item in args.byzantine_ids.split(",") if item),
    )
    output = Path(__file__).resolve().parents[1] / "docs" / "mosaic_network_result.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
