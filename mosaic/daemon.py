"""Production-style MOSAIC node daemon entry point."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import signal
import ssl
from pathlib import Path

from ccd_nexus import KeyPair

from .model import Member, StateSeal
from .availability import ErasureCodec, AvailabilityStore
from .availability_network import AvailabilityCoordinator
from .beacon import BeaconRoundCoordinator
from .economics import SettlementLedger
from .membership import MembershipManager
from .network import MosaicNode, seal_from_wire
from .onboarding import AdmissionCoordinator, admission_from_wire, bond_from_wire
from .protocol import MosaicProtocol
from .storage import DurableStore


def make_tls_context(config: dict) -> tuple[ssl.SSLContext | None, ssl.SSLContext | None]:
    tls = config.get("tls")
    if not tls:
        return None, None
    server = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    server.load_cert_chain(tls["certfile"], tls["keyfile"])
    server.load_verify_locations(cafile=tls["cafile"])
    server.verify_mode = ssl.CERT_REQUIRED
    client = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=tls["cafile"])
    client.load_cert_chain(tls["certfile"], tls["keyfile"])
    client.check_hostname = False
    return server, client


def load_node(config_path: str) -> MosaicNode:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    node_id = config["node_id"]
    members = {}
    for member_id, item in config["members"].items():
        private = None
        if member_id == node_id:
            if not item.get("private_key_b64"):
                raise ValueError("local validator private_key_b64 is missing")
            private = KeyPair.from_private_bytes(
                base64.b64decode(item["private_key_b64"], validate=True)
            )
        public_key = base64.b64decode(item["public_key_b64"], validate=True)
        members[member_id] = Member(
            member_id=member_id,
            keypair=private,
            weight=int(item["weight"]),
            public_key_override=public_key,
        )
    protocol = MosaicProtocol(members, epoch=int(config.get("epoch", 0)))
    store_path = config.get("data_path", f"./data/{node_id}.sqlite")
    store = DurableStore(store_path)
    try:
        settlement = SettlementLedger.from_store(store)
    except Exception:
        settlement = SettlementLedger(
            asset=config.get("settlement", {}).get("asset", "MOSAIC"),
            treasury=config.get("settlement", {}).get("treasury", "mosaic:treasury"),
        )
        for account, amount in config.get("genesis_balances", {}).items():
            settlement.fund(account, int(amount), source_id=f"genesis:{account}")
        settlement.persist(store)
    membership_config = config.get("membership", {})
    membership = MembershipManager(
        config.get("genesis_seed", "mosaic-testnet-genesis").encode("utf-8"),
        minimum_stake=int(membership_config.get("minimum_stake", 1)),
        withdrawal_delay=int(membership_config.get("withdrawal_delay", 3)),
        settlement=settlement,
    )
    for item in config.get("genesis_admissions", []):
        request = admission_from_wire(item["request"])
        bond = bond_from_wire(item["bond"])
        if request.validator_id in membership.snapshot.by_id():
            continue
        if bond.bond_id in settlement.bonds:
            membership.restore_admission(request, bond)
        else:
            membership.admit(request, bond=bond)
    settlement.persist(store)
    onboarding = AdmissionCoordinator(membership, settlement).bind_store(store)
    beacon = BeaconRoundCoordinator(membership, settlement, store)
    availability_config = config.get("availability", {})
    availability = AvailabilityCoordinator(
        AvailabilityStore(
            ErasureCodec(
                int(availability_config.get("data_shards", 5)),
                int(availability_config.get("parity_shards", 3)),
            )
        ),
        store,
    )
    for item in config.get("initial_seals", []):
        seal = seal_from_wire(item)
        protocol.current_seals[seal.resource_id] = seal
        protocol.known_seals[seal.seal_id] = seal
    peers = {peer_id: (endpoint["host"], int(endpoint["port"])) for peer_id, endpoint in config["peers"].items()}
    server_tls, client_tls = make_tls_context(config)
    return MosaicNode(
        node_id=node_id,
        host=config.get("bind_host", "0.0.0.0"),
        port=int(config["bind_port"]),
        peers=peers,
        protocol=protocol,
        membership=membership,
        onboarding=onboarding,
        beacon=beacon,
        availability=availability,
        store=store,
        ssl_context=server_tls,
        client_ssl_context=client_tls,
        delay_ms=0.0,
        drop_rate=0.0,
        byzantine_id=None,
        equivocate=False,
        submit_timeout=float(config.get("submit_timeout", 8.0)),
        frame_timeout=float(config.get("frame_timeout", 5.0)),
        connect_timeout=float(config.get("connect_timeout", 3.0)),
        max_connections_per_peer=int(config.get("max_connections_per_peer", 64)),
        max_pending_capsules=int(config.get("max_pending_capsules", 10000)),
        peer_rate_capacity=float(config.get("peer_rate_capacity", 1000.0)),
        peer_rate_refill=float(config.get("peer_rate_refill", 1000.0)),
        retry_backoff_ms=float(config.get("retry_backoff_ms", 5.0)),
    )


async def serve(config_path: str) -> None:
    node = load_node(config_path)
    await node.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a MOSAIC validator node")
    parser.add_argument("--config", required=True, help="path to node JSON config")
    args = parser.parse_args()
    asyncio.run(serve(args.config))


if __name__ == "__main__":
    main()
