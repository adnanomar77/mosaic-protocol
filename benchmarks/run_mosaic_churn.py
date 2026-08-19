"""Multi-process churn, crash-restart and partial-frame DoS benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing as mp
import queue
import signal
import struct
import time
from pathlib import Path

from benchmarks.run_mosaic_network import make_configs, node_main, request, wait_started
from ccd_nexus import KeyPair
from ccd_nexus.crypto import digest
from mosaic import StateSeal
from mosaic.network import capsule_to_wire, read_frame, seal_from_wire, write_frame
from mosaic.model import Capsule


async def partial_frame_flood(host: str, port: int, count: int, frame_timeout: float) -> int:
    writers = []
    for _ in range(count):
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.write(struct.pack("!I", 1024 * 1024))
            await writer.drain()
            writers.append(writer)
        except OSError:
            pass
    await asyncio.sleep(frame_timeout * 2)
    closed = 0
    for writer in writers:
        try:
            writer.close()
            await writer.wait_closed()
            closed += 1
        except OSError:
            pass
    return closed


def run_churn(
    node_count: int,
    operations: int,
    base_port: int,
    data_dir: str,
    byzantine_ids: tuple[str, ...] = (),
) -> dict:
    context = mp.get_context("fork")
    status_queue = context.Queue()
    client = KeyPair.generate()
    configs, predecessor = make_configs(node_count, base_port, client, operations)
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    for config in configs:
        config["store_path"] = str(data_path / f"{config['node_id']}.sqlite")
        Path(config["store_path"]).unlink(missing_ok=True)
        config["byzantine_ids"] = list(byzantine_ids)
        config["equivocate"] = config["node_id"] in byzantine_ids
        config.update(
            {
                "frame_timeout": 0.15,
                "connect_timeout": 1.0,
                "max_connections_per_peer": 32,
                "peer_rate_capacity": 200.0,
                "peer_rate_refill": 200.0,
                "max_pending_capsules": 2000,
            }
        )
    processes = [context.Process(target=node_main, args=(config, status_queue)) for config in configs]
    for process in processes:
        process.start()
    wait_started(status_queue, node_count)

    durations = []
    results = []
    killed_node = 1 if node_count > 2 else 0
    killed_at = max(1, operations // 3)
    restarted = False
    for index in range(operations):
        if index == killed_at:
            processes[killed_node].kill()
            processes[killed_node].join(timeout=2)
            restarted = True
            processes[killed_node] = context.Process(target=node_main, args=(configs[killed_node], status_queue))
            processes[killed_node].start()
            wait_started(status_queue, 1)
        capsule = Capsule.create(
            client=client,
            predecessor=predecessor,
            successor_root=f"churn-state-{index + 1}",
            rule_id="identity-transition",
            rule_witness="valid",
            attempt=index,
        )
        started = time.perf_counter_ns()
        target = configs[index % node_count]
        if restarted and killed_at <= index < killed_at + 3 and target["node_id"] == configs[killed_node]["node_id"]:
            target = configs[(killed_node + 1) % node_count]
        result = {"ok": False, "error": "no response"}
        for retry in range(12):
            try:
                result = asyncio.run(
                    request(
                        target["host"],
                        target["port"],
                        {"type": "SUBMIT", "capsule": capsule_to_wire(capsule)},
                    )
                )
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}
            if result.get("ok"):
                break
            time.sleep(0.20 * min(retry + 1, 4))
        if not result.get("ok") and any(
            marker in str(result.get("error", ""))
            for marker in ("bytes read", "Connection refused", "IncompleteRead", "timed out")
        ):
            for alternate in configs:
                if alternate is target:
                    continue
                try:
                    candidate = asyncio.run(
                        request(
                            alternate["host"],
                            alternate["port"],
                            {"type": "SUBMIT", "capsule": capsule_to_wire(capsule)},
                        )
                    )
                except Exception:
                    continue
                if candidate.get("ok"):
                    result = candidate
                    break
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
        results.append(result)
        if result.get("ok"):
            predecessor = seal_from_wire(result["next_seal"])

    dos_closed = asyncio.run(partial_frame_flood("127.0.0.1", configs[0]["port"], 24, 0.15))
    time.sleep(0.5)
    metrics = []
    for config in configs:
        try:
            metrics.append(asyncio.run(request(config["host"], config["port"], {"type": "METRICS", "message_id": f"metrics-{config['node_id']}"})))
        except Exception as exc:
            metrics.append({"ok": False, "node_id": config["node_id"], "error": str(exc)})
    for config in configs:
        try:
            asyncio.run(request(config["host"], config["port"], {"type": "SHUTDOWN", "message_id": f"shutdown-{config['node_id']}"}))
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
        "killed_node": configs[killed_node]["node_id"],
        "killed_at_operation": killed_at,
        "restarted_from_wal": restarted,
        "byzantine_ids": list(byzantine_ids),
        "dos_partial_frames_closed": dos_closed,
        "p50_ms": ordered[len(ordered) // 2] if ordered else None,
        "p95_ms": p95,
        "results": results,
        "metrics": metrics,
        "scope": "independent localhost TCP processes with crash/restart, partial-frame DoS and SQLite WAL",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=7)
    parser.add_argument("--operations", type=int, default=40)
    parser.add_argument("--base-port", type=int, default=21100)
    parser.add_argument("--data-dir", type=str, default="/tmp/mosaic-churn")
    parser.add_argument("--byzantine-ids", type=str, default="")
    args = parser.parse_args()
    result = run_churn(
        args.nodes,
        args.operations,
        args.base_port,
        args.data_dir,
        tuple(item for item in args.byzantine_ids.split(",") if item),
    )
    output = Path(__file__).resolve().parents[1] / "docs" / "mosaic_churn_result.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
