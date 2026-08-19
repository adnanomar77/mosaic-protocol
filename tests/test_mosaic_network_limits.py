import asyncio
import struct

from ccd_nexus import KeyPair
from mosaic import Member, MosaicProtocol
from mosaic.network import read_frame, write_frame
from mosaic.network import MosaicNode


def make_node(**kwargs):
    key = KeyPair.generate()
    protocol = MosaicProtocol({"w0": Member("w0", key, weight=1)})
    return MosaicNode(
        node_id="w0",
        host="127.0.0.1",
        port=0,
        peers={},
        protocol=protocol,
        **kwargs,
    )


def test_partial_frame_is_closed_by_timeout():
    node = make_node(frame_timeout=0.02)

    async def exercise():
        server = await asyncio.start_server(node._handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(struct.pack("!I", 128))
            await writer.drain()
            await asyncio.sleep(0.08)
            assert await reader.read() == b""
            writer.close()
            await writer.wait_closed()
        assert node.metrics["frame_timeouts"] + node.metrics["malformed_frames"] >= 1

    asyncio.run(exercise())


def test_peer_rate_limit_does_not_kill_server():
    node = make_node(peer_rate_capacity=1.0, peer_rate_refill=0.01)

    async def exercise():
        server = await asyncio.start_server(node._handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            await write_frame(writer, {"type": "METRICS", "message_id": "first"})
            response = await asyncio.wait_for(read_frame(reader), timeout=1)
            assert response["ok"] is True
            writer.close()
            await writer.wait_closed()

            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            await write_frame(writer, {"type": "METRICS", "message_id": "second"})
            await asyncio.sleep(0.05)
            assert await reader.read() == b""
            writer.close()
            await writer.wait_closed()
        assert node.metrics["rate_limited"] >= 1

    asyncio.run(exercise())
