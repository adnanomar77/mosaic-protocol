"""Validate a MOSAIC multi-host testnet inventory before deployment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PLACEHOLDERS = {"REPLACE_VALUE", "REPLACE_TREASURY_ACCOUNT"}


def validate(path: Path, allow_placeholders: bool = False) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if data.get("protocol_version") != "MOSAIC/TESTNET/v1":
        errors.append("protocol_version must be MOSAIC/TESTNET/v1")
    nodes = data.get("nodes", [])
    if len(nodes) < 4:
        errors.append("testnet needs at least four validators")
    ids = [item.get("node_id") for item in nodes]
    hosts = [item.get("host") for item in nodes]
    if len(set(ids)) != len(ids):
        errors.append("node_id values must be unique")
    if len(set(hosts)) != len(hosts):
        errors.append("advertised hosts must be unique")
    for node in nodes:
        for field in ("node_id", "host", "advertise_host", "private_key_path", "tls_cert_path", "tls_key_path", "tls_ca_path", "data_dir", "log_dir"):
            if not node.get(field):
                errors.append(f"{node.get('node_id', '<unknown>')} missing {field}")
        if node.get("bind_host") == "127.0.0.1":
            errors.append(f"{node.get('node_id')} bind_host is localhost; use 0.0.0.0 or private interface for multi-host")
        if not isinstance(node.get("port"), int) or not 1024 <= node["port"] <= 65535:
            errors.append(f"{node.get('node_id')} has invalid port")
        if node.get("private_key_b64") or node.get("private_key"):
            errors.append(f"{node.get('node_id')} inventory must not contain private key material")
    security = data.get("security", {})
    if security.get("tls_mode") != "mutual":
        errors.append("tls_mode must be mutual for public testnet")
    if security.get("private_key_policy") != "one-node-one-key":
        errors.append("private_key_policy must be one-node-one-key")
    economics = data.get("economics", {})
    for name in ("minimum_stake", "non_reveal_penalty", "reveal_reward", "treasury_account"):
        if not allow_placeholders and economics.get(name) in PLACEHOLDERS:
            errors.append(f"economics.{name} is still a placeholder")
    if not data.get("availability", {}).get("data_shards") or not data.get("availability", {}).get("parity_shards"):
        errors.append("availability data_shards and parity_shards are required")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()
    errors = validate(args.inventory, args.allow_placeholders)
    if errors:
        print(json.dumps({"passed": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"passed": True, "inventory": str(args.inventory)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
