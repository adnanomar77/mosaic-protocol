"""Run reproducible local measurements for the CCD/NEXUS prototype."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path

from ccd_nexus import (
    DomainExecutor,
    InputRef,
    JoinCoordinator,
    KeyPair,
    ObjectState,
    Operation,
    QuorumCommittee,
    Validator,
    WriteIntent,
)

from benchmarks.baselines import PROFILES


def make_committee(size: int):
    validators = {}
    for index in range(size):
        keypair = KeyPair.generate()
        validator_id = f"validator-{index}"
        validators[validator_id] = Validator(validator_id, keypair)
    return validators, QuorumCommittee(validators)


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(p * len(ordered)) - 1)
    return ordered[index]


def summarize(name: str, durations_ns: list[int], elapsed_ns: int, message_count: int, message_bytes: int, count: int) -> dict:
    durations_ms = [value / 1_000_000 for value in durations_ns]
    elapsed_s = elapsed_ns / 1_000_000_000
    return {
        "workload": name,
        "operations": count,
        "elapsed_ms": round(elapsed_s * 1000, 4),
        "throughput_ops_s": round(count / elapsed_s, 4) if elapsed_s else None,
        "finality_p50_ms": round(statistics.median(durations_ms), 4),
        "finality_p95_ms": round(percentile(durations_ms, 0.95), 4),
        "message_count": message_count,
        "bytes_per_operation": round(message_bytes / count, 2) if count else 0,
        "prototype_scope": "single-process; signatures and quorum logic included; network transport excluded",
    }


def run_single_domain(count: int, validators_count: int, conflict: bool) -> dict:
    client = KeyPair.generate()
    validators, committee = make_committee(validators_count)
    domain = DomainExecutor("D1", 0, committee)
    object_count = 1 if conflict else count
    for index in range(object_count):
        domain.add_object(ObjectState(f"obj-{index}", 0, client.identity, "initial", "D1"))

    durations = []
    start_all = time.perf_counter_ns()
    for index in range(count):
        object_id = "obj-0" if conflict else f"obj-{index}"
        version = index if conflict else 0
        operation = Operation.create(
            keypair=client,
            epoch=0,
            domain_ids=("D1",),
            inputs=(InputRef("D1", object_id, version),),
            writes=(WriteIntent("D1", object_id, version, client.identity, f"payload-{index}"),),
            nonce=index,
        )
        start = time.perf_counter_ns()
        domain.finalize(operation)
        durations.append(time.perf_counter_ns() - start)
    elapsed = time.perf_counter_ns() - start_all
    return summarize(
        "single_domain_conflict" if conflict else "single_domain_independent",
        durations,
        elapsed,
        committee.message_count,
        committee.message_bytes,
        count,
    )


def run_multi_domain(count: int, validators_count: int) -> dict:
    client = KeyPair.generate()
    _, committee = make_committee(validators_count)
    domain_a = DomainExecutor("D1", 0, committee)
    domain_b = DomainExecutor("D2", 0, committee)
    domain_a.add_object(ObjectState("a", 0, client.identity, "A0", "D1"))
    domain_b.add_object(ObjectState("b", 0, client.identity, "B0", "D2"))
    coordinator = JoinCoordinator({"D1": domain_a, "D2": domain_b})

    durations = []
    start_all = time.perf_counter_ns()
    for index in range(count):
        operation = Operation.create(
            keypair=client,
            epoch=0,
            domain_ids=("D1", "D2"),
            inputs=(InputRef("D1", "a", index), InputRef("D2", "b", index)),
            writes=(
                WriteIntent("D1", "a", index, client.identity, f"A{index + 1}"),
                WriteIntent("D2", "b", index, client.identity, f"B{index + 1}"),
            ),
            nonce=10_000 + index,
        )
        start = time.perf_counter_ns()
        coordinator.finalize(operation)
        durations.append(time.perf_counter_ns() - start)
    elapsed = time.perf_counter_ns() - start_all
    return summarize(
        "multi_domain_join",
        durations,
        elapsed,
        committee.message_count,
        committee.message_bytes,
        count,
    )


def build_report(results: list[dict], validators_count: int, count: int) -> str:
    lines = [
        "# CCD/NEXUS local benchmark",
        "",
        f"Configuration: validators={validators_count}, operations per workload={count}.",
        "",
        "> هذه أرقام محلية لنموذج Python أحادي العملية. لا تمثل latency شبكة أو throughput موزعًا، ولا يجوز مقارنتها مباشرة بأرقام الأوراق المنشورة.",
        "",
        "| Workload | Ops/s | p50 finality (ms) | p95 finality (ms) | Messages | Bytes/op |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in results:
        lines.append(
            f"| {item['workload']} | {item['throughput_ops_s']} | {item['finality_p50_ms']} | "
            f"{item['finality_p95_ms']} | {item['message_count']} | {item['bytes_per_operation']} |"
        )
    lines.extend(
        [
            "",
            "## Baseline context",
            "",
            "The following are architecture references, not measurements from this run:",
            "",
            "| Baseline | Ordering | Fast path | Source |",
            "|---|---|---|---|",
        ]
    )
    for profile in PROFILES:
        lines.append(
            f"| {profile.name} | {profile.ordering} | {profile.fast_path} | [{profile.source}]({profile.source}) |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The independent workload measures the intended local-domain path. The conflict workload measures repeated writes to one object and is the expected bottleneck case. The multi-domain workload measures atomic Join, not a network-parallel implementation. A valid future comparison must run the same workloads and message sizes against distributed implementations of HotStuff, Narwhal/Tusk, and an object-centric hybrid.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validators", type=int, default=4)
    parser.add_argument("--operations", type=int, default=25)
    args = parser.parse_args()
    results = [
        run_single_domain(args.operations, args.validators, conflict=False),
        run_single_domain(args.operations, args.validators, conflict=True),
        run_multi_domain(args.operations, args.validators),
    ]
    output_dir = Path(__file__).resolve().parents[1] / "docs"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "benchmark_results.json").write_text(
        json.dumps(
            {
                "configuration": vars(args),
                "results": results,
                "warning": "Local single-process prototype measurements; literature profiles are not mixed with these values.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "benchmark_results.md").write_text(
        build_report(results, args.validators, args.operations),
        encoding="utf-8",
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
