from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "docs" / "benchmark_sweep.json").read_text(encoding="utf-8"))
rows = DATA["rows"]
workloads = [
    "single_domain_independent",
    "single_domain_conflict",
    "multi_domain_join",
]
labels = {
    "single_domain_independent": "Independent",
    "single_domain_conflict": "Conflict",
    "multi_domain_join": "Multi-domain Join",
}
colors = {
    "single_domain_independent": "#0f766e",
    "single_domain_conflict": "#d97706",
    "multi_domain_join": "#7c3aed",
}

plt.style.use("seaborn-v0_8-whitegrid")
fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), dpi=160)
for workload in workloads:
    subset = [row for row in rows if row["workload"] == workload]
    xs = [row["validators"] for row in subset]
    p95 = [row["finality_p95_ms"] for row in subset]
    bytes_per_op = [row["bytes_per_operation"] for row in subset]
    axes[0].plot(xs, p95, marker="o", linewidth=2.5, label=labels[workload], color=colors[workload])
    axes[1].plot(xs, bytes_per_op, marker="o", linewidth=2.5, label=labels[workload], color=colors[workload])

axes[0].set_title("p95 finality in local prototype")
axes[0].set_xlabel("Validators")
axes[0].set_ylabel("Milliseconds")
axes[0].set_xticks([4, 7, 10])
axes[0].legend(frameon=True)
axes[1].set_title("Logical bytes per operation")
axes[1].set_xlabel("Validators")
axes[1].set_ylabel("Bytes/op")
axes[1].set_xticks([4, 7, 10])
axes[1].legend(frameon=True)
fig.suptitle("CCD/NEXUS committee-size sweep", fontsize=15, fontweight="bold")
fig.text(
    0.5,
    0.01,
    "Single-process Python measurements; network transport and WAN latency are excluded.",
    ha="center",
    fontsize=9,
)
fig.tight_layout(rect=[0, 0.04, 1, 0.95])
fig.savefig(ROOT / "docs" / "benchmark_sweep.png", bbox_inches="tight")
