"""Local performance benchmark for the MOSAIC reference model."""

from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

from ccd_nexus import KeyPair
from ccd_nexus.crypto import canonical_bytes
from mosaic import Member, MosaicProtocol


def make_protocol(member_count: int = 4) -> tuple[MosaicProtocol, KeyPair]:
    members = {
        f"w{index}": Member(f"w{index}", KeyPair.generate(), weight=1)
        for index in range(member_count)
    }
    return MosaicProtocol(members), KeyPair.generate()


def p95(values: list[float]) -> float:
    return sorted(values)[max(0, math.ceil(0.95 * len(values)) - 1)]


def summarize(name: str, durations: list[float], bytes_seen: int, operations: int, elapsed: float) -> dict:
    return {
        "workload": name,
        "operations": operations,
        "throughput_ops_s": round(operations / elapsed, 4),
        "p50_ms": round(statistics.median(durations), 4),
        "p95_ms": round(p95(durations), 4),
        "bytes_per_operation": round(bytes_seen / operations, 2),
        "scope": "single-process reference model; Ed25519 and witness receipts included; network excluded",
    }


def run_independent(count: int, members: int) -> dict:
    protocol, client = make_protocol(members)
    durations, bytes_seen = [], 0
    started_all = time.perf_counter()
    for index in range(count):
        start = time.perf_counter_ns()
        predecessor = protocol.create_resource(f"i-{index}", owner=client.identity)
        capsule = protocol.create_capsule(client=client, predecessor=predecessor, successor_root=f"s-{index}")
        closure = protocol.close(capsule)
        protocol.apply(capsule, closure)
        durations.append((time.perf_counter_ns() - start) / 1_000_000)
        bytes_seen += len(canonical_bytes(capsule.unsigned_statement()))
        bytes_seen += sum(len(canonical_bytes(receipt.statement())) + len(receipt.signature) for receipt in closure.receipts)
    return summarize("independent_capsules", durations, bytes_seen, count, time.perf_counter() - started_all)


def run_conflict_free_sequential(count: int, members: int) -> dict:
    protocol, client = make_protocol(members)
    predecessor = protocol.create_resource("shared", owner=client.identity)
    durations, bytes_seen = [], 0
    started_all = time.perf_counter()
    for index in range(count):
        start = time.perf_counter_ns()
        capsule = protocol.create_capsule(
            client=client,
            predecessor=predecessor,
            successor_root=f"shared-{index}",
            attempt=index,
        )
        closure = protocol.close(capsule)
        predecessor = protocol.apply(capsule, closure)
        durations.append((time.perf_counter_ns() - start) / 1_000_000)
        bytes_seen += len(canonical_bytes(capsule.unsigned_statement()))
        bytes_seen += sum(len(canonical_bytes(receipt.statement())) + len(receipt.signature) for receipt in closure.receipts)
    return summarize("sequential_same_resource", durations, bytes_seen, count, time.perf_counter() - started_all)


def run_bundles(count: int, members: int) -> dict:
    protocol, client = make_protocol(members)
    a = protocol.create_resource("bundle-a", owner=client.identity)
    b = protocol.create_resource("bundle-b", owner=client.identity)
    durations, bytes_seen = [], 0
    started_all = time.perf_counter()
    for index in range(count):
        start = time.perf_counter_ns()
        bundle_id = f"bundle-{index}"
        capsule_a = protocol.create_capsule(
            client=client,
            predecessor=a,
            successor_root=f"a-{index}",
            attempt=index,
            bundle_id=bundle_id,
        )
        capsule_b = protocol.create_capsule(
            client=client,
            predecessor=b,
            successor_root=f"b-{index}",
            attempt=index,
            bundle_id=bundle_id,
        )
        closure_a = protocol.close(capsule_a)
        closure_b = protocol.close(capsule_b)
        bundle = protocol.bundle_closure(bundle_id, (closure_a, closure_b))
        next_seals = protocol.apply_bundle(bundle, ((capsule_a, closure_a), (capsule_b, closure_b)))
        a, b = next_seals
        durations.append((time.perf_counter_ns() - start) / 1_000_000)
        bytes_seen += len(canonical_bytes(capsule_a.unsigned_statement()))
        bytes_seen += len(canonical_bytes(capsule_b.unsigned_statement()))
        bytes_seen += sum(
            len(canonical_bytes(receipt.statement())) + len(receipt.signature)
            for closure in (closure_a, closure_b)
            for receipt in closure.receipts
        )
    return summarize("two_resource_bundle", durations, bytes_seen, count, time.perf_counter() - started_all)


def main() -> None:
    count = 50
    rows = [
        run_independent(count, 4),
        run_conflict_free_sequential(count, 4),
        run_bundles(count, 4),
    ]
    output_dir = Path(__file__).resolve().parents[1] / "docs"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "mosaic_benchmark.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        "# MOSAIC reference-model benchmark",
        "",
        "> Single-process measurements with real Ed25519 signatures and witness receipts. They do not represent distributed network latency.",
        "",
        "| Workload | Ops/s | p50 ms | p95 ms | Bytes/op |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['workload']} | {row['throughput_ops_s']} | {row['p50_ms']} | {row['p95_ms']} | {row['bytes_per_operation']} |"
        )
    lines.append("")
    (output_dir / "mosaic_benchmark.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
