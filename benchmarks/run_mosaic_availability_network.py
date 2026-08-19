"""Local multi-process availability provider rehearsal."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import multiprocessing as mp
import time
from pathlib import Path

from ccd_nexus import KeyPair
from mosaic import ErasureCodec, shard_from_wire, shard_to_wire
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
    if nodes < 5:
        raise ValueError("availability rehearsal needs five providers for k=3,m=2")
    context = mp.get_context("fork")
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    validator_keys = {f"w{index}": KeyPair.generate() for index in range(nodes)}
    endpoints = {node_id: {"host": "127.0.0.1", "port": base_port + index} for index, node_id in enumerate(validator_keys)}
    configs = []
    for node_id in validator_keys:
        configs.append(
            {
                "node_id": node_id,
                "bind_host": "127.0.0.1",
                "bind_port": endpoints[node_id]["port"],
                "data_path": str(root / f"{node_id}.sqlite"),
                "genesis_seed": "mosaic-availability-local",
                "membership": {"minimum_stake": 1, "withdrawal_delay": 3},
                "availability": {"data_shards": 3, "parity_shards": 2},
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
    codec = ErasureCodec(3, 2)
    payload = b"availability-over-provider-tcp" * 31
    shards = codec.encode("network-object-0", payload)
    put_responses = []
    for index, shard in enumerate(shards):
        provider = endpoints[f"w{index}"]
        put_responses.append(asyncio.run(request(provider["host"], provider["port"], {"type": "AVAILABILITY_PUT", "shard": shard_to_wire(shard)})))
    source_responses = []
    for index in (0, 1, 2):
        provider = endpoints[f"w{index}"]
        source_responses.append(asyncio.run(request(provider["host"], provider["port"], {"type": "AVAILABILITY_FETCH", "object_id": "network-object-0", "shard_index": index})))
    source_shards = tuple(shard_from_wire(item["shard"]) for item in source_responses if item.get("ok"))
    repair_response = asyncio.run(
        request(
            endpoints["w4"]["host"],
            endpoints["w4"]["port"],
            {
                "type": "AVAILABILITY_REPAIR",
                "source_shards": [shard_to_wire(item) for item in source_shards],
                "missing_indices": [3, 4],
            },
        )
    )
    repaired = tuple(shard_from_wire(item) for item in repair_response.get("repaired", []))
    sample_response = asyncio.run(
        request(
            endpoints["w4"]["host"],
            endpoints["w4"]["port"],
            {"type": "AVAILABILITY_SAMPLE", "object_id": "network-object-0", "indices": [3, 4]},
        )
    )
    recovered = codec.recover(source_shards + repaired) if len(repaired) == 2 else b""
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
    restart = context.Process(target=daemon_main, args=(paths[4],))
    restart.start()
    time.sleep(1.0)
    restart_fetch = asyncio.run(request(endpoints["w4"]["host"], endpoints["w4"]["port"], {"type": "AVAILABILITY_FETCH", "object_id": "network-object-0", "shard_index": 3}))
    try:
        asyncio.run(request(endpoints["w4"]["host"], endpoints["w4"]["port"], {"type": "SHUTDOWN"}))
    except Exception:
        pass
    restart.join(timeout=5)
    if restart.is_alive():
        restart.terminate()
        restart.join(timeout=2)
    return {
        "scope": "LOCAL_EMULATION; independent daemon processes on one host, not public testnet",
        "nodes": nodes,
        "put_responses": put_responses,
        "source_fetches": source_responses,
        "repair_response": repair_response,
        "sample_response": sample_response,
        "recovered_payload_matches": recovered == payload,
        "restart_fetch_ok": restart_fetch.get("ok", False),
        "metrics": metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=5)
    parser.add_argument("--base-port", type=int, default=21920)
    parser.add_argument("--data-dir", type=str, default="/tmp/mosaic-availability-network")
    args = parser.parse_args()
    result = run(args.nodes, args.base_port, args.data_dir)
    output = Path(__file__).resolve().parents[1] / "testnet" / "artifacts" / "mosaic_availability_network_local.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
