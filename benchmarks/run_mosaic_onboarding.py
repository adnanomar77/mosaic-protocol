"""Local multi-process rehearsal for networked onboarding."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import multiprocessing as mp
import time
from pathlib import Path

from ccd_nexus import KeyPair
from mosaic import AdmissionRequest, StakeBond, admission_to_wire, bond_to_wire
from mosaic.daemon import load_node
from mosaic.network import read_frame, write_frame


def enc(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def daemon_main(config_path: str) -> None:
    import asyncio

    node = load_node(config_path)
    asyncio.run(node.run())


async def request(host: str, port: int, message: dict) -> dict:
    reader, writer = await asyncio.open_connection(host, port)
    await write_frame(writer, message)
    response = await asyncio.wait_for(read_frame(reader), timeout=15)
    writer.close()
    await writer.wait_closed()
    return response


def run(nodes: int, base_port: int, data_dir: str) -> dict:
    if nodes < 4:
        raise ValueError("onboarding rehearsal needs at least four nodes")
    context = mp.get_context("fork")
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    applicant = KeyPair.generate()
    validator_keys = {f"w{index}": KeyPair.generate() for index in range(nodes)}
    endpoints = {node_id: {"host": "127.0.0.1", "port": base_port + index} for index, node_id in enumerate(validator_keys)}
    genesis = {
        "resource_id": "asset",
        "epoch": 0,
        "version": 0,
        "state_root": "genesis",
        "capability_hash": "capability",
        "owner": applicant.identity,
    }
    from mosaic.model import StateSeal
    from ccd_nexus.crypto import digest
    genesis["capability_hash"] = digest("capability")
    genesis_seal = StateSeal(**genesis)
    configs: list[dict] = []
    for node_id, key in validator_keys.items():
        configs.append(
            {
                "node_id": node_id,
                "bind_host": "127.0.0.1",
                "bind_port": endpoints[node_id]["port"],
                "data_path": str(root / f"{node_id}.sqlite"),
                "genesis_seed": "mosaic-onboarding-local",
                "genesis_balances": {applicant.identity: 20},
                "membership": {"minimum_stake": 10, "withdrawal_delay": 3},
                "settlement": {"asset": "MOSAIC", "treasury": "mosaic:treasury"},
                "members": {
                    member_id: {
                        "private_key_b64": enc(member_key.private_bytes) if member_id == node_id else None,
                        "public_key_b64": enc(member_key.public_key),
                        "weight": 1,
                    }
                    for member_id, member_key in validator_keys.items()
                },
                "peers": {peer_id: endpoint for peer_id, endpoint in endpoints.items() if peer_id != node_id},
                "initial_seals": [
                    {
                        "resource_id": genesis_seal.resource_id,
                        "epoch": genesis_seal.epoch,
                        "version": genesis_seal.version,
                        "state_root": genesis_seal.state_root,
                        "capability_hash": genesis_seal.capability_hash,
                        "owner": genesis_seal.owner,
                    }
                ],
                "frame_timeout": 1.0,
                "connect_timeout": 1.0,
                "submit_timeout": 5.0,
            }
        )
    config_paths = []
    for config in configs:
        path = root / f"{config['node_id']}.json"
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        config_paths.append(str(path))
    processes = [context.Process(target=daemon_main, args=(path,)) for path in config_paths]
    for process in processes:
        process.start()
    time.sleep(1.5)
    bond = StakeBond.create(applicant, "bond-local-onboarding", 10, "MOSAIC", 0, 3)
    admission = AdmissionRequest.create(
        applicant,
        "validator-applicant",
        10,
        "deposit-local-onboarding",
        0,
        bond_id=bond.bond_id,
    )
    response = asyncio.run(
        request(
            "127.0.0.1",
            base_port,
            {"type": "ADMISSION", "request": admission_to_wire(admission), "bond": bond_to_wire(bond)},
        )
    )
    time.sleep(0.6)
    metrics = []
    for endpoint in endpoints.values():
        try:
            metrics.append(asyncio.run(request(endpoint["host"], endpoint["port"], {"type": "METRICS"})))
        except Exception as exc:
            metrics.append({"ok": False, "error": str(exc)})
    for endpoint in endpoints.values():
        try:
            asyncio.run(request(endpoint["host"], endpoint["port"], {"type": "SHUTDOWN"}))
        except Exception:
            pass
    for process in processes:
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
    restart_process = context.Process(target=daemon_main, args=(config_paths[0],))
    restart_process.start()
    time.sleep(1.0)
    restart_metrics = asyncio.run(request("127.0.0.1", endpoints["w0"]["port"], {"type": "METRICS"}))
    try:
        asyncio.run(request("127.0.0.1", endpoints["w0"]["port"], {"type": "SHUTDOWN"}))
    except Exception:
        pass
    restart_process.join(timeout=5)
    if restart_process.is_alive():
        restart_process.terminate()
        restart_process.join(timeout=2)
    return {
        "scope": "LOCAL_EMULATION; independent daemon processes on one host, not public testnet",
        "nodes": nodes,
        "admission_response": response,
        "metrics": metrics,
        "gossip_admissions": sum(item.get("metrics", {}).get("admissions", 0) for item in metrics),
        "restart_metrics": restart_metrics,
        "restart_onboarding_wal_check": restart_metrics.get("ok") and not restart_metrics.get("metrics", {}).get("errors"),
        "applicant_identity": applicant.identity,
        "private_keys_written_to": "local ephemeral rehearsal only; production deployment must provision keys out-of-band",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=4)
    parser.add_argument("--base-port", type=int, default=21740)
    parser.add_argument("--data-dir", type=str, default="/tmp/mosaic-onboarding")
    args = parser.parse_args()
    result = run(args.nodes, args.base_port, args.data_dir)
    output = Path(__file__).resolve().parents[1] / "testnet" / "artifacts" / "mosaic_onboarding_local.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
