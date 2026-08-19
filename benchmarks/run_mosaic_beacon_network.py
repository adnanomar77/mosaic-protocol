"""Local multi-process beacon round rehearsal after genesis onboarding."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import multiprocessing as mp
import time
from pathlib import Path

from ccd_nexus import KeyPair
from mosaic import (
    AdmissionRequest,
    RandomnessCommitment,
    RandomnessReveal,
    StakeBond,
    admission_to_wire,
    bond_to_wire,
    commitment_to_wire,
    reveal_to_wire,
)
from mosaic.daemon import load_node
from mosaic.network import read_frame, write_frame


def enc(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def daemon_main(config_path: str) -> None:
    import asyncio

    asyncio.run(load_node(config_path).run())


async def request(host: str, port: int, message: dict) -> dict:
    reader, writer = await asyncio.open_connection(host, port)
    await write_frame(writer, message)
    response = await asyncio.wait_for(read_frame(reader), timeout=20)
    writer.close()
    await writer.wait_closed()
    return response


def run(nodes: int, base_port: int, data_dir: str) -> dict:
    if nodes < 4:
        raise ValueError("beacon rehearsal needs at least four validators")
    context = mp.get_context("fork")
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    validator_keys = {f"w{index}": KeyPair.generate() for index in range(nodes)}
    endpoints = {node_id: {"host": "127.0.0.1", "port": base_port + index} for index, node_id in enumerate(validator_keys)}
    genesis_admissions = []
    genesis_balances = {"mosaic:treasury": 20}
    for index, (validator_id, key) in enumerate(validator_keys.items()):
        bond = StakeBond.create(key, f"genesis-bond-{index}", 10, "MOSAIC", 0, 3)
        request_object = AdmissionRequest.create(
            key,
            validator_id,
            10,
            f"genesis-deposit-{index}",
            0,
            bond_id=bond.bond_id,
        )
        genesis_admissions.append({"request": admission_to_wire(request_object), "bond": bond_to_wire(bond)})
        genesis_balances[key.identity] = 10
    configs = []
    for node_id in validator_keys:
        configs.append(
            {
                "node_id": node_id,
                "bind_host": "127.0.0.1",
                "bind_port": endpoints[node_id]["port"],
                "data_path": str(root / f"{node_id}.sqlite"),
                "genesis_seed": "mosaic-beacon-local",
                "genesis_balances": genesis_balances,
                "genesis_admissions": genesis_admissions,
                "membership": {"minimum_stake": 10, "withdrawal_delay": 3},
                "settlement": {"asset": "MOSAIC", "treasury": "mosaic:treasury"},
                "members": {
                    member_id: {
                        "private_key_b64": enc(key.private_bytes) if member_id == node_id else None,
                        "public_key_b64": enc(key.public_key),
                        "weight": 1,
                    }
                    for member_id, key in validator_keys.items()
                },
                "peers": {peer_id: endpoint for peer_id, endpoint in endpoints.items() if peer_id != node_id},
                "initial_seals": [],
                "frame_timeout": 1.0,
                "connect_timeout": 1.0,
            }
        )
    paths = []
    for config in configs:
        path = root / f"{config['node_id']}.json"
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        paths.append(str(path))
    processes = [context.Process(target=daemon_main, args=(path,)) for path in paths]
    for process in processes:
        process.start()
    time.sleep(1.5)
    commitments = []
    secrets = {}
    commit_responses = []
    for index, (validator_id, key) in enumerate(validator_keys.items()):
        secret = f"beacon-network-secret-{index}".encode()
        secrets[validator_id] = secret
        commitment = RandomnessCommitment.create(key, 0, 0, secret, validator_id=validator_id)
        commitments.append(commitment)
        commit_responses.append(
            asyncio.run(
                request(
                    "127.0.0.1",
                    endpoints["w0"]["port"],
                    {"type": "BEACON_COMMIT", "commitment": commitment_to_wire(commitment)},
                )
            )
        )
    reveal_responses = []
    for validator_id in list(validator_keys)[:3]:
        index = int(validator_id[1:])
        reveal = RandomnessReveal.create(
            validator_keys[validator_id],
            0,
            0,
            secrets[validator_id],
            commitments[index].commitment,
            validator_id=validator_id,
        )
        reveal_responses.append(
            asyncio.run(
                request(
                    "127.0.0.1",
                    endpoints["w0"]["port"],
                    {"type": "BEACON_REVEAL", "reveal": reveal_to_wire(reveal)},
                )
            )
        )
    time.sleep(0.8)
    finalize = asyncio.run(
        request(
            "127.0.0.1",
            endpoints["w0"]["port"],
            {"type": "BEACON_FINALIZE", "round": 0, "reveal_reward": 1, "non_reveal_penalty": 1},
        )
    )
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
    result = {
        "scope": "LOCAL_EMULATION; independent daemon processes on one host, not public testnet",
        "nodes": nodes,
        "commit_responses": commit_responses,
        "reveal_responses": reveal_responses,
        "finalize_response": finalize,
        "metrics": metrics,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=4)
    parser.add_argument("--base-port", type=int, default=21860)
    parser.add_argument("--data-dir", type=str, default="/tmp/mosaic-beacon-network")
    args = parser.parse_args()
    result = run(args.nodes, args.base_port, args.data_dir)
    output = Path(__file__).resolve().parents[1] / "testnet" / "artifacts" / "mosaic_beacon_network_local.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
