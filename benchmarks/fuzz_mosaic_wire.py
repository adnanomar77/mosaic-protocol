"""Deterministic wire parser fuzz harness."""

from __future__ import annotations

import json
import random

from mosaic.network import capsule_from_wire, closure_from_wire, receipt_from_wire, seal_from_wire, unb64


SEED = 271828


def mutate(rng: random.Random, value: object) -> object:
    choice = rng.randrange(8)
    if choice == 0:
        return None
    if choice == 1:
        return []
    if choice == 2:
        return rng.randrange(-1000, 1000)
    if choice == 3:
        return {"unexpected": "field"}
    if choice == 4:
        return "garbled"
    if choice == 5:
        return {str(rng.randrange(5)): value}
    if choice == 6:
        return [value, value]
    return value


def run(iterations: int = 2000) -> dict:
    rng = random.Random(SEED)
    parsers = [capsule_from_wire, closure_from_wire, receipt_from_wire, seal_from_wire]
    accepted = 0
    rejected = 0
    unexpected = []
    for index in range(iterations):
        parser = parsers[index % len(parsers)]
        base = {
            "capsule_id": "c",
            "predecessor_id": "p",
            "successor_root": "s",
            "rule_id": "r",
            "rule_witness": "w",
            "bundle_id": None,
            "attempt": 0,
            "epoch": 0,
            "client_id": "client",
            "client_public_key": "AA==",
            "client_signature": "AA==",
            "witness_id": "w0",
            "status": "ACCEPT",
            "signature": "AA==",
            "resource_id": "asset",
            "version": 0,
            "state_root": "root",
            "capability_hash": "cap",
            "owner": "owner",
            "signer_ids": [],
            "receipts": [],
            "proof_id": "proof",
        }
        candidate = {key: mutate(rng, value) if rng.random() < 0.7 else value for key, value in base.items()}
        try:
            parser(candidate)
            accepted += 1
        except (ValueError, KeyError, TypeError, AttributeError, IndexError):
            rejected += 1
        except Exception as exc:
            unexpected.append({"parser": parser.__name__, "type": type(exc).__name__, "error": str(exc)})
    for _ in range(iterations):
        value = "".join(rng.choice("!@#$%^&*not-base64") for _ in range(rng.randrange(1, 80)))
        try:
            unb64(value)
            accepted += 1
        except (ValueError, UnicodeEncodeError):
            rejected += 1
        except Exception as exc:
            unexpected.append({"parser": "unb64", "type": type(exc).__name__, "error": str(exc)})
    return {
        "seed": SEED,
        "iterations": iterations,
        "accepted": accepted,
        "rejected": rejected,
        "unexpected_count": len(unexpected),
        "unexpected": unexpected[:10],
        "passed": not unexpected,
        "scope": "parser-level deterministic fuzz; not a substitute for network penetration testing",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
