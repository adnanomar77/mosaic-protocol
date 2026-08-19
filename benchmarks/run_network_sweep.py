"""Run a small distributed TCP fault matrix for CCD/NEXUS."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.run_distributed_network import run_cluster


def main() -> None:
    rows = []
    port = 18900
    for node_count in (4, 7):
        scenarios = (
            ("healthy", 0.0, 0.0, None),
            ("delay_drop_retry", 1.0, 0.10, None),
            ("one_byzantine", 0.0, 0.0, "validator-1"),
        )
        for name, delay_ms, drop_rate, byzantine_id in scenarios:
            result = run_cluster(
                node_count=node_count,
                operations=5,
                base_port=port,
                delay_ms=delay_ms,
                drop_rate=drop_rate,
                byzantine_id=byzantine_id,
            )
            rows.append({"scenario": name, **result})
            port += 20
    output_dir = Path(__file__).resolve().parents[1] / "docs"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "network_sweep.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        "# Distributed TCP network sweep",
        "",
        "> Localhost multi-process results. They validate transport integration and fault handling, not Internet-scale performance.",
        "",
        "| Nodes | Scenario | Success | p50 ms | p95 ms | Drop events | Retries | Equivocations | Errors |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        all_metrics = [item["metrics"] for item in row["node_metrics"]]
        drops = sum(item.get("dropped_messages", 0) for item in all_metrics)
        retries = sum(item.get("retries", 0) for item in all_metrics)
        equivocations = sum(item.get("equivocations", 0) for item in all_metrics)
        errors = sum(item.get("errors", 0) for item in all_metrics)
        lines.append(
            f"| {row['node_count']} | {row['scenario']} | {row['successful_operations']}/{row['operations']} | "
            f"{row['p50_finality_ms']:.4f} | {row['p95_finality_ms']:.4f} | {drops} | {retries} | {equivocations} | {errors} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Healthy and one-Byzantine scenarios should preserve successful operations when the Byzantine weight is below one third. The delay/drop scenario tests retries and may increase p95. A localhost result does not establish production safety or WAN performance.",
            "",
        ]
    )
    (output_dir / "network_sweep.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
