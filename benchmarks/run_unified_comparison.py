"""Controlled same-environment architectural comparison.

These are executable abstractions, not the official implementations of the
referenced systems. The report labels them accordingly.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

from ccd_nexus import DomainExecutor, InputRef, KeyPair, ObjectState, Operation, QuorumCommittee, Validator, WriteIntent
from ccd_nexus.crypto import canonical_bytes
from benchmarks.run_benchmark import run_multi_domain, run_single_domain


def make_committee(size: int):
    validators = {}
    for index in range(size):
        keypair = KeyPair.generate()
        validator_id = f"validator-{index}"
        validators[validator_id] = Validator(validator_id, keypair)
    return validators, QuorumCommittee(validators)


def p95(values: list[float]) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * 0.95) - 1)]


def make_operation(client: KeyPair, workload: str, index: int, domain_id: str) -> Operation:
    if workload == "independent":
        refs = (InputRef(domain_id, f"obj-{index}", 0),)
        writes = (WriteIntent(domain_id, f"obj-{index}", 0, client.identity, f"p-{index}"),)
    elif workload == "conflict":
        refs = (InputRef(domain_id, "obj-0", index),)
        writes = (WriteIntent(domain_id, "obj-0", index, client.identity, f"p-{index}"),)
    else:
        refs = (InputRef(domain_id, "a", index), InputRef(domain_id, "b", index))
        writes = (
            WriteIntent(domain_id, "a", index, client.identity, f"a-{index}"),
            WriteIntent(domain_id, "b", index, client.identity, f"b-{index}"),
        )
    return Operation.create(
        keypair=client,
        epoch=0,
        domain_ids=(domain_id,),
        inputs=refs,
        writes=writes,
        nonce=50_000 + index,
    )


def run_global_baseline(name: str, workload: str, validators_count: int, operations_count: int, dag_barrier: bool = False) -> dict:
    client = KeyPair.generate()
    validators, committee = make_committee(validators_count)
    domain = DomainExecutor("GLOBAL", 0, committee)
    if workload == "independent":
        objects = [f"obj-{index}" for index in range(operations_count)]
    elif workload == "conflict":
        objects = ["obj-0"]
    else:
        objects = ["a", "b"]
    for object_id in objects:
        domain.add_object(ObjectState(object_id, 0, client.identity, "initial", "GLOBAL"))

    durations = []
    modeled_dag_messages = 0
    modeled_dag_bytes = 0
    started_all = time.perf_counter_ns()
    for index in range(operations_count):
        operation = make_operation(client, workload, index, "GLOBAL")
        if dag_barrier:
            event = {"event": operation.op_id, "parents": [], "operation": operation.op_id}
            event_bytes = len(canonical_bytes(event))
            modeled_dag_messages += validators_count
            modeled_dag_bytes += validators_count * event_bytes
        started = time.perf_counter_ns()
        domain.finalize(operation)
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
    elapsed_ms = (time.perf_counter_ns() - started_all) / 1_000_000
    total_messages = committee.message_count + modeled_dag_messages
    total_bytes = committee.message_bytes + modeled_dag_bytes
    return {
        "baseline": name,
        "workload": workload,
        "validators": validators_count,
        "operations": operations_count,
        "throughput_ops_s": round(operations_count / (elapsed_ms / 1000), 4),
        "p95_finality_ms": round(p95(durations), 4),
        "messages_per_operation": round(total_messages / operations_count, 2),
        "bytes_per_operation": round(total_bytes / operations_count, 2),
        "note": "controlled abstraction; not an official protocol implementation",
    }


def run_comparison(validators_count: int = 4, operations_count: int = 20) -> list[dict]:
    rows = []
    for workload in ("independent", "conflict", "multi_domain"):
        ccd = (
            run_single_domain(operations_count, validators_count, workload == "conflict")
            if workload != "multi_domain"
            else run_multi_domain(operations_count, validators_count)
        )
        rows.append(
            {
                "baseline": "CCD/NEXUS",
                "workload": workload,
                "validators": validators_count,
                "operations": operations_count,
                "throughput_ops_s": ccd["throughput_ops_s"],
                "p95_finality_ms": ccd["finality_p95_ms"],
                "messages_per_operation": round(ccd["message_count"] / operations_count, 2),
                "bytes_per_operation": ccd["bytes_per_operation"],
                "note": "local implementation with local-domain path and Join",
            }
        )
        rows.append(run_global_baseline("HotStuff-style global", workload, validators_count, operations_count))
        rows.append(
            run_global_baseline(
                "Narwhal/Tusk-style DAG barrier",
                workload,
                validators_count,
                operations_count,
                dag_barrier=True,
            )
        )
        if workload != "multi_domain":
            rows.append(
                {
                    "baseline": "Sui Lutris-style hybrid",
                    "workload": workload,
                    "validators": validators_count,
                    "operations": operations_count,
                    "throughput_ops_s": ccd["throughput_ops_s"],
                    "p95_finality_ms": ccd["finality_p95_ms"],
                    "messages_per_operation": round(ccd["message_count"] / operations_count, 2),
                    "bytes_per_operation": ccd["bytes_per_operation"],
                    "note": "controlled object-local fast path abstraction",
                }
            )
        else:
            rows.append(
                run_global_baseline(
                    "Sui Lutris-style hybrid",
                    workload,
                    validators_count,
                    operations_count,
                )
            )
    return rows


def main() -> None:
    rows = run_comparison()
    output_dir = Path(__file__).resolve().parents[1] / "docs"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "unified_comparison.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        "# Controlled same-environment comparison",
        "",
        "> These rows compare executable abstractions under the same Python process and committee model. They are not official HotStuff, Narwhal/Tusk, or Sui Lutris implementations and must not be cited as their benchmark results.",
        "",
        "| Baseline | Workload | Ops/s | p95 ms | Messages/op | Bytes/op |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['baseline']} | {row['workload']} | {row['throughput_ops_s']} | "
            f"{row['p95_finality_ms']} | {row['messages_per_operation']} | {row['bytes_per_operation']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The comparison isolates architectural cost under a common implementation substrate. It does not establish production superiority because the reference protocols have different network, cryptographic aggregation, batching, and execution implementations. The valid next step is to replace each abstraction with a real distributed implementation or an official test harness.",
            "",
        ]
    )
    (output_dir / "unified_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
