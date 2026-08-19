from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "paper" / "figures"
DATA = ROOT / "paper" / "data"
FIGURES.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

with (ROOT / "testnet/artifacts/mosaic_testnet_long_final_v3.json").open(encoding="utf-8") as handle:
    v3 = json.load(handle)
with (ROOT / "testnet/artifacts/mosaic_testnet_long_final.json").open(encoding="utf-8") as handle:
    v5 = json.load(handle)

rows = [
    ("v3 (before restart-path correction)", v3["p50_ms"], v3["p95_ms"], v3["safety_signal"]["errors"]),
    ("v5 (after correction)", v5["p50_ms"], v5["p95_ms"], v5["safety_signal"]["errors"]),
]
with (DATA / "long_run_latency.csv").open("w", encoding="utf-8") as handle:
    handle.write("run,p50_ms,p95_ms,unexpected_errors\n")
    for name, p50, p95, errors in rows:
        handle.write(f'"{name}",{p50},{p95},{errors}\n')

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "figure.dpi": 160,
    "savefig.dpi": 600,
})

labels = ["v3\nbefore fix", "v5\nafter fix"]
x = np.arange(len(labels))
width = 0.32
p50 = np.array([r[1] for r in rows], dtype=float)
p95 = np.array([r[2] for r in rows], dtype=float)

fig, ax = plt.subplots(figsize=(5.8, 3.6), constrained_layout=True)
b1 = ax.bar(x - width / 2, p50, width, label="p50", color="#6a1b75")
b2 = ax.bar(x + width / 2, p95, width, label="p95", color="#9e9e9e")
ax.set_yscale("log")
ax.set_ylabel("Latency (ms; logarithmic scale)")
ax.set_xticks(x, labels)
ax.set_title("Long-run latency before and after restart-path correction")
ax.grid(axis="y", which="both", color="#dddddd", linewidth=0.5)
ax.legend(frameon=False, ncols=2, loc="upper left")
for bars in (b1, b2):
    for bar in bars:
        value = bar.get_height()
        ax.annotate(
            f"{value:.1f}",
            xy=(bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )
fig.savefig(FIGURES / "long_run_latency_comparison.png", bbox_inches="tight")
fig.savefig(FIGURES / "long_run_latency_comparison.pdf", bbox_inches="tight")
plt.close(fig)

with (DATA / "evaluation_summary.csv").open("w", encoding="utf-8") as handle:
    handle.write("evidence,value,unit,scope\n")
    handle.write("pytest tests,102,tests,local repository\n")
    handle.write("wire fuzz,4000,cases,parser harness\n")
    handle.write("bounded model records,12,records,finite ECTC/quorum/availability/execution checks\n")
    handle.write("long-run nodes,7,nodes,local emulation\n")
    handle.write("long-run operations,120,operations,local emulation\n")
    handle.write("long-run successes,120,operations,local emulation\n")
    handle.write("event-log events,8,events,hash-chain verified\n")

print("wrote", FIGURES / "long_run_latency_comparison.png")
print("wrote", FIGURES / "long_run_latency_comparison.pdf")
print("wrote", DATA / "long_run_latency.csv")
print("wrote", DATA / "evaluation_summary.csv")


with (ROOT / "docs/mosaic_ectc_workloads.json").open(encoding="utf-8") as handle:
    workload_rows = json.load(handle)["results"]
with (DATA / "ectc_workloads.csv").open("w", encoding="utf-8") as handle:
    columns = list(workload_rows[0].keys())
    handle.write(",".join(columns) + "\n")
    for row in workload_rows:
        handle.write(",".join(str(row[column]) for column in columns) + "\n")

selected = [
    row for row in workload_rows
    if (row["mode"] == "disjoint" and row["batch_size"] == 1)
    or (row["mode"] == "contended" and row["batch_size"] == 1)
    or (row["mode"] == "batched" and row["batch_size"] in {10, 100})
]
labels = [
    "disjoint",
    "competing claims",
    "batch 10",
    "batch 100",
]
x = np.arange(len(selected))
width = 0.34
fig, ax = plt.subplots(figsize=(6.4, 3.8), constrained_layout=True)
p50 = np.array([row["latency_ms_p50"] for row in selected], dtype=float)
p95 = np.array([row["latency_ms_p95"] for row in selected], dtype=float)
b1 = ax.bar(x - width / 2, p50, width, label="p50", color="#6a1b75")
b2 = ax.bar(x + width / 2, p95, width, label="p95", color="#9e9e9e")
ax.set_ylabel("Per-operation latency (ms)")
ax.set_xticks(x, labels)
ax.set_title("ECTC workloads: disjoint, competing, and batching")
ax.grid(axis="y", color="#dddddd", linewidth=0.5)
ax.legend(frameon=False, ncols=2)
for bars in (b1, b2):
    for bar in bars:
        value = bar.get_height()
        ax.annotate(f"{value:.2f}", xy=(bar.get_x() + bar.get_width() / 2, value), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=7)
fig.savefig(FIGURES / "ectc_workload_latency.png", bbox_inches="tight")
fig.savefig(FIGURES / "ectc_workload_latency.pdf", bbox_inches="tight")
plt.close(fig)

scaling = [row for row in workload_rows if row["mode"] == "scaling"]
fig, ax = plt.subplots(figsize=(5.8, 3.6), constrained_layout=True)
ax.plot([row["validators"] for row in scaling], [row["throughput_ops_s"] for row in scaling], marker="o", color="#6a1b75")
ax.set_xlabel("Validator processes")
ax.set_ylabel("Serialized operations/s")
ax.set_title("Local scaling sweep (disjoint workload)")
ax.grid(color="#dddddd", linewidth=0.5)
fig.savefig(FIGURES / "ectc_scaling.png", bbox_inches="tight")
fig.savefig(FIGURES / "ectc_scaling.pdf", bbox_inches="tight")
plt.close(fig)

print("wrote", FIGURES / "ectc_workload_latency.png")
print("wrote", FIGURES / "ectc_scaling.png")
print("wrote", DATA / "ectc_workloads.csv")
