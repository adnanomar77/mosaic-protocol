"""Run a real two-group partition and healing test for MOSAIC."""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing as mp
import queue
import time
from pathlib import Path

from ccd_nexus import KeyPair
from mosaic.model import Capsule
from mosaic.network import capsule_to_wire, read_frame, seal_from_wire, write_frame
from mosaic.storage import DurableStore

from benchmarks.run_mosaic_network import make_configs, node_main


async def request(config: dict, message: dict, timeout: float = 3.0) -> dict:
    reader, writer = await asyncio.open_connection(config["host"], config["port"])
    await write_frame(writer, message)
    response = await asyncio.wait_for(read_frame(reader), timeout=timeout)
    writer.close()
    await writer.wait_closed()
    return response


def request_sync(config: dict, message: dict, timeout: float = 3.0) -> dict:
    return asyncio.run(request(config, message, timeout))


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
        raise RuntimeError(f"only {started}/{expected} nodes started")


def stop_all(processes, configs):
    for config in configs:
        try:
            request_sync(config, {"type": "SHUTDOWN"}, timeout=1)
        except Exception:
            pass
    for process in processes:
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)


def start_all(context, configs, status_queue):
    processes = []
    for config in configs:
        process = context.Process(target=node_main, args=(config, status_queue))
        process.start()
        processes.append(process)
    wait_started(status_queue, len(configs))
    return processes


def run(node_count: int, base_port: int, data_dir: str) -> dict:
    if node_count % 2:
        raise ValueError("node_count must be even for a symmetric partition")
    context = mp.get_context("fork")
    status_queue = context.Queue()
    client = KeyPair.generate()
    configs, predecessor = make_configs(node_count, base_port, client, 1)
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    endpoints = {config["node_id"]: (config["host"], config["port"]) for config in configs}
    midpoint = node_count // 2
    groups = [set(config["node_id"] for config in configs[:midpoint]), set(config["node_id"] for config in configs[midpoint:])]
    for config in configs:
        config["store_path"] = str(data_path / f"{config['node_id']}.sqlite")
        Path(config["store_path"]).unlink(missing_ok=True)
        config["delay_ms"] = 0.0
        config["drop_rate"] = 0.0
        config["submit_timeout"] = 0.35
        config["byzantine_id"] = None
        config["equivocate"] = False
        group = next(group for group in groups if config["node_id"] in group)
        config["peers"] = {peer: endpoints[peer] for peer in sorted(group) if peer != config["node_id"]}

    processes = start_all(context, configs, status_queue)
    capsule = Capsule.create(
        client=client,
        predecessor=predecessor,
        successor_root="partition-state",
        rule_id="identity-transition",
        rule_witness="valid",
        attempt=0,
    )
    partition_response = request_sync(
        configs[0],
        {"type": "SUBMIT", "capsule": capsule_to_wire(capsule)},
        timeout=2,
    )
    liveness_stopped = not partition_response.get("ok", False) and "timeout" in partition_response.get("error", "")
    stop_all(processes, configs)

    for config in configs:
        config["peers"] = {peer: endpoints[peer] for peer in sorted(endpoints) if peer != config["node_id"]}
    time.sleep(0.1)
    processes = start_all(context, configs, status_queue)
    healed_response = request_sync(
        configs[0],
        {"type": "SUBMIT", "capsule": capsule_to_wire(capsule)},
        timeout=5,
    )
    healed = healed_response.get("ok", False)
    restarted_counts = {}
    integrity = {}
    for config in configs:
        with DurableStore(config["store_path"]) as store:
            restarted_counts[config["node_id"]] = {
                "capsules": len(list(store.items("capsule"))),
                "closures": len(list(store.items("closure"))),
            }
            integrity[config["node_id"]] = store.integrity_check()
    stop_all(processes, configs)

    result = {
        "nodes": node_count,
        "partition_groups": [sorted(group) for group in groups],
        "partition_liveness_stopped": liveness_stopped,
        "partition_response": partition_response,
        "healed": healed,
        "healed_response": healed_response,
        "restarted_counts": restarted_counts,
        "store_integrity": integrity,
        "success": liveness_stopped and healed and all(integrity.values()),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=4)
    parser.add_argument("--base-port", type=int, default=20600)
    parser.add_argument("--data-dir", default="/tmp/mosaic-partition")
    args = parser.parse_args()
    result = run(args.nodes, args.base_port, args.data_dir)
    output = Path(__file__).resolve().parents[1] / "docs" / "mosaic_partition.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
