"""Exercise MOSAIC crash/restart recovery with independent TCP processes."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import multiprocessing as mp
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ccd_nexus import KeyPair
from mosaic.model import Capsule
from mosaic.network import capsule_to_wire, seal_from_wire, write_frame, read_frame
from mosaic.storage import DurableStore

from benchmarks.run_mosaic_network import make_configs, node_main


async def request(host: str, port: int, message: dict) -> dict:
    reader, writer = await asyncio.open_connection(host, port)
    await write_frame(writer, message)
    response = await asyncio.wait_for(read_frame(reader), timeout=20)
    writer.close()
    await writer.wait_closed()
    return response


def request_sync(config: dict, message: dict) -> dict:
    return asyncio.run(request(config["host"], config["port"], message))


def wait_started(status_queue, expected: int, timeout: float = 10.0) -> None:
    started = 0
    deadline = time.time() + timeout
    while started < expected and time.time() < deadline:
        try:
            item = status_queue.get(timeout=0.25)
        except queue.Empty:
            continue
        if item.get("event") == "started":
            started += 1
    if started != expected:
        raise RuntimeError(f"only {started}/{expected} MOSAIC nodes started")


def stop_processes(processes):
    for process in processes:
        if process.is_alive():
            try:
                request_sync(
                    {"host": "127.0.0.1", "port": process._mosaic_port},
                    {"type": "SHUTDOWN"},
                )
            except Exception:
                pass
    for process in processes:
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)


def run(node_count: int, base_port: int, data_dir: str) -> dict:
    context = mp.get_context("fork")
    status_queue = context.Queue()
    client = KeyPair.generate()
    configs, predecessor = make_configs(node_count, base_port, client, 4)
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    for config in configs:
        config["store_path"] = str(data_path / f"{config['node_id']}.sqlite")
        Path(config["store_path"]).unlink(missing_ok=True)
        config["delay_ms"] = 0.0
        config["drop_rate"] = 0.0
        config["byzantine_id"] = None
        config["equivocate"] = False

    processes = []
    for config in configs:
        process = context.Process(target=node_main, args=(config, status_queue))
        process._mosaic_port = config["port"]
        process.start()
        processes.append(process)
    wait_started(status_queue, node_count)

    results = []
    predecessor_seal = predecessor
    for index in range(2):
        capsule = Capsule.create(
            client=client,
            predecessor=predecessor_seal,
            successor_root=f"state-{index + 1}",
            rule_id="identity-transition",
            rule_witness="valid",
            attempt=index,
        )
        response = request_sync(
            configs[index % node_count],
            {"type": "SUBMIT", "capsule": capsule_to_wire(capsule)},
        )
        results.append(response)
        if not response.get("ok"):
            raise RuntimeError(f"pre-crash operation failed: {response}")
        predecessor_seal = seal_from_wire(response["next_seal"])

    crash_index = 2
    crash_capsule = Capsule.create(
        client=client,
        predecessor=predecessor_seal,
        successor_root="state-3",
        rule_id="identity-transition",
        rule_witness="valid",
        attempt=crash_index,
    )
    crash_message = {"type": "SUBMIT", "capsule": capsule_to_wire(crash_capsule)}
    target_config = configs[1]
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(request_sync, target_config, crash_message)
        time.sleep(0.003)
        processes[1].terminate()
        processes[1].join(timeout=5)
        try:
            interrupted = future.result(timeout=3)
        except Exception as exc:
            interrupted = {"ok": False, "error": f"request interrupted by crash: {type(exc).__name__}"}

    time.sleep(0.1)
    restarted = context.Process(target=node_main, args=(target_config, status_queue))
    restarted._mosaic_port = target_config["port"]
    restarted.start()
    processes[1] = restarted
    wait_started(status_queue, 1)

    metrics_after_restart = request_sync(target_config, {"type": "METRICS"})
    recovery = request_sync(target_config, crash_message)
    if recovery.get("ok"):
        predecessor_seal = seal_from_wire(recovery["next_seal"])

    final_capsule = Capsule.create(
        client=client,
        predecessor=predecessor_seal,
        successor_root="state-4",
        rule_id="identity-transition",
        rule_witness="valid",
        attempt=3,
    )
    final_response = request_sync(
        configs[2],
        {"type": "SUBMIT", "capsule": capsule_to_wire(final_capsule)},
    )
    results.extend([recovery, final_response])

    store_path = Path(target_config["store_path"])
    with DurableStore(store_path) as store:
        persisted_counts = {
            kind: len(list(store.items(kind)))
            for kind in ("capsule", "receipt", "closure", "seal_current")
        }
        store_ok = store.integrity_check()

    for config in configs:
        try:
            request_sync(config, {"type": "SHUTDOWN"})
        except Exception:
            pass
    for process in processes:
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)

    success = (
        all(item.get("ok") for item in results)
        and metrics_after_restart.get("ok") is True
        and store_ok
        and persisted_counts["closure"] >= 3
    )
    return {
        "nodes": node_count,
        "pre_crash_operations": 2,
        "crash_target": target_config["node_id"],
        "request_interrupted": not interrupted.get("ok", False),
        "interrupted_response": interrupted,
        "recovery_response": recovery,
        "final_response": final_response,
        "metrics_after_restart": metrics_after_restart,
        "persisted_counts_on_reopen": persisted_counts,
        "store_integrity": store_ok,
        "success": success,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=4)
    parser.add_argument("--base-port", type=int, default=20500)
    parser.add_argument("--data-dir", default="/tmp/mosaic-crash-restart")
    args = parser.parse_args()
    result = run(args.nodes, args.base_port, args.data_dir)
    output = Path(__file__).resolve().parents[1] / "docs" / "mosaic_crash_restart.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
