"""Run the same local workloads across committee sizes."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.run_benchmark import run_multi_domain, run_single_domain


def main() -> None:
    operations = 20
    rows = []
    for validators in (4, 7, 10):
        rows.extend(
            [
                {"validators": validators, **run_single_domain(operations, validators, False)},
                {"validators": validators, **run_single_domain(operations, validators, True)},
                {"validators": validators, **run_multi_domain(operations, validators)},
            ]
        )
    output_dir = Path(__file__).resolve().parents[1] / "docs"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "benchmark_sweep.json").write_text(
        json.dumps({"operations_per_workload": operations, "rows": rows}, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# CCD/NEXUS committee-size sweep",
        "",
        f"Operations per workload: {operations}. Local single-process measurements only.",
        "",
        "| Validators | Workload | Ops/s | p95 finality (ms) | Messages/op | Bytes/op |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['validators']} | {row['workload']} | {row['throughput_ops_s']} | "
            f"{row['finality_p95_ms']} | {row['message_count'] / row['operations']:.2f} | "
            f"{row['bytes_per_operation']} |"
        )
    (output_dir / "benchmark_sweep.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
