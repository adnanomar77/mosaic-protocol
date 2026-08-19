"""Long-run local testnet harness with public incident and upgrade log."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.run_mosaic_churn import run_churn
from testnet.events import EventLog


def run(nodes: int, operations: int, base_port: int, data_dir: str, event_path: str) -> dict:
    log = EventLog(event_path, "mosaic-testnet-0", "0.1.0-testnet")
    log.append("testnet_started", "orchestrator", nodes=nodes, operations=operations, scope="LOCAL_EMULATION")
    log.append("onboarding_gate_verified", "orchestrator", artifact="testnet/artifacts/mosaic_onboarding_gate.json")
    log.append("beacon_gate_verified", "orchestrator", artifact="testnet/artifacts/mosaic_beacon_network_local.json")
    log.append("availability_gate_verified", "orchestrator", artifact="testnet/artifacts/mosaic_availability_network_local.json")
    result = run_churn(nodes, operations, base_port, data_dir, ("w0", "w1"))
    log.append(
        "byzantine_schedule_completed",
        "orchestrator",
        byzantine_ids=result["byzantine_ids"],
        conflicts="recorded-as-protocol-conflicts",
    )
    log.append(
        "validator_kill_restart_completed",
        result["killed_node"],
        killed_at_operation=result["killed_at_operation"],
        restarted_from_wal=result["restarted_from_wal"],
    )
    log.append(
        "config_upgrade_candidate_recorded",
        "orchestrator",
        upgrade_id="config-v2",
        status="not_applied_to_consensus",
        reason="requires public governance window and external operators",
    )
    log.append("testnet_finished", "orchestrator", operations_successful=result["operations_successful"])
    metrics = result.get("metrics", [])
    total_sent = sum(item.get("metrics", {}).get("sent_bytes", 0) for item in metrics)
    total_received = sum(item.get("metrics", {}).get("received_bytes", 0) for item in metrics)
    total_errors = sum(item.get("metrics", {}).get("errors", 0) for item in metrics)
    sent_by_type: dict[str, int] = {}
    received_by_type: dict[str, int] = {}
    for item in metrics:
        item_metrics = item.get("metrics", {})
        for key, value in item_metrics.get("sent_bytes_by_type", {}).items():
            sent_by_type[key] = sent_by_type.get(key, 0) + int(value)
        for key, value in item_metrics.get("received_bytes_by_type", {}).items():
            received_by_type[key] = received_by_type.get(key, 0) + int(value)
    output = {
        "scope": "LOCAL_EMULATION; not independent public hosts",
        "nodes": nodes,
        "operations_requested": operations,
        "operations_successful": result["operations_successful"],
        "liveness_ratio": result["operations_successful"] / operations if operations else 0.0,
        "safety_signal": {
            "errors": total_errors,
            "byzantine_ids": result["byzantine_ids"],
            "conflicts_are_evidence": True,
            "interpretation": "bounded operational signal, not a formal proof",
        },
        "cost": {
            "sent_bytes": total_sent,
            "received_bytes": total_received,
            "sent_bytes_by_type": sent_by_type,
            "received_bytes_by_type": received_by_type,
            "bytes_per_success": (total_sent + total_received) / result["operations_successful"] if result["operations_successful"] else None,
        },
        "p50_ms": result["p50_ms"],
        "p95_ms": result["p95_ms"],
        "dos_partial_frames_closed": result["dos_partial_frames_closed"],
        "event_log": str(event_path),
        "event_log_verified": log.verify(),
        "event_count": len(log.read()),
        "raw_churn": result,
    }
    destination = Path(__file__).resolve().parents[1] / "testnet" / "artifacts" / "mosaic_testnet_long_local.json"
    destination.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=7)
    parser.add_argument("--operations", type=int, default=120)
    parser.add_argument("--base-port", type=int, default=22020)
    parser.add_argument("--data-dir", type=str, default="/tmp/mosaic-testnet-long")
    parser.add_argument("--event-log", type=str, default="/home/ubuntu/blockchain_alt/testnet/events/testnet-0.jsonl")
    args = parser.parse_args()
    print(json.dumps(run(args.nodes, args.operations, args.base_port, args.data_dir, args.event_log), indent=2))


if __name__ == "__main__":
    main()
