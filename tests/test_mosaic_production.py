import asyncio
import json
import random
import struct

from ccd_nexus import KeyPair

from mosaic import Member, MosaicProtocol, StateSeal
from mosaic.model import ClosureProof
from mosaic.network import MosaicNode, read_frame, write_frame
from mosaic.storage import DurableStore


def _protocol_with_members(count: int = 4):
    keys = {f"w{i}": KeyPair.generate() for i in range(count)}
    members = {
        node_id: Member(node_id, key, weight=1)
        for node_id, key in keys.items()
    }
    protocol = MosaicProtocol(members)
    genesis = protocol.create_resource("asset", owner="client", state_root="genesis")
    return keys, protocol, genesis


def test_protocol_state_survives_real_close_and_restart(tmp_path):
    path = tmp_path / "restart.sqlite"
    keys, protocol, predecessor = _protocol_with_members()
    client = KeyPair.generate()
    capsule = protocol.create_capsule(
        client=client,
        predecessor=predecessor,
        successor_root="state-1",
        attempt=0,
    )
    receipts = tuple(
        protocol.witness_receipt(node_id, capsule, "ACCEPT")
        for node_id in sorted(protocol.members)
    )
    closure = ClosureProof.create(receipts[:3])
    protocol.register_closure(capsule, closure)
    next_seal = protocol.apply(capsule, closure)

    with DurableStore(path) as store:
        node = MosaicNode(
            node_id="w0",
            host="127.0.0.1",
            port=0,
            peers={},
            protocol=protocol,
            store=store,
        )
        node._persist_capsule(capsule)
        node._persist_closure(capsule, closure)
        store.checkpoint()

    restarted = MosaicProtocol(
        {
            node_id: Member(node_id, key, weight=1)
            for node_id, key in keys.items()
        }
    )
    with DurableStore(path) as store:
        node = MosaicNode(
            node_id="w0",
            host="127.0.0.1",
            port=0,
            peers={},
            protocol=restarted,
            store=store,
        )
        node._restore()
        assert restarted.current_seals["asset"] == next_seal
        assert capsule.capsule_id in restarted.closures
        assert restarted.closures[capsule.capsule_id].proof_id == closure.proof_id
        assert store.integrity_check()


def test_fuzzed_frames_do_not_kill_node_server():
    keys, protocol, _ = _protocol_with_members(4)
    node = MosaicNode(
        node_id="w0",
        host="127.0.0.1",
        port=0,
        peers={},
        protocol=protocol,
    )

    rng = random.Random(20260819)
    corpus = [b"", b"null", b"[]", b"1", b'"text"', b"{", b"not-json"]
    for _ in range(128):
        choice = rng.randrange(4)
        if choice == 0:
            value = {"type": rng.choice([None, "", "UNKNOWN", 17]), "payload": rng.randbytes(rng.randrange(0, 64)).hex()}
        elif choice == 1:
            value = [rng.randint(-1000, 1000) for _ in range(rng.randrange(0, 8))]
        elif choice == 2:
            value = {rng.randbytes(4).hex(): rng.randbytes(rng.randrange(0, 32)).hex()}
        else:
            value = rng.choice([True, False, None, rng.randrange(1000)])
        corpus.append(json.dumps(value).encode())

    async def exercise():
        server = await asyncio.start_server(node._handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            for payload in corpus:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.write(struct.pack("!I", len(payload)) + payload)
                await writer.drain()
                try:
                    await asyncio.wait_for(reader.read(), timeout=0.25)
                except (asyncio.TimeoutError, ConnectionError):
                    pass
                writer.close()
                await writer.wait_closed()

            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            await write_frame(writer, {"type": "METRICS"})
            response = await asyncio.wait_for(read_frame(reader), timeout=1)
            writer.close()
            await writer.wait_closed()
            assert response["ok"] is True
            assert response["node_id"] == "w0"
            assert node.metrics["errors"] >= 1

    asyncio.run(exercise())
