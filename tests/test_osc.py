"""Wire-level OSC regression tests with real UDP sockets."""

import socket
import threading
from time import monotonic

import pytest
from pythonosc.osc_message import OscMessage
from pythonosc.osc_message_builder import OscMessageBuilder

from custom_components.wing_limiter.osc import WingClient


def packet(address, *values):
    builder = OscMessageBuilder(address=address)
    for value in values:
        builder.add_arg(value)
    return builder.build().dgram


@pytest.fixture
def udp_server():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.settimeout(2)
        yield sock


def test_out_of_order_invalid_and_unrelated_packets(udp_server):
    def reply():
        _, peer = udp_server.recvfrom(4096)
        udp_server.recvfrom(4096)
        for raw in (
            b"invalid",
            packet("/unrelated", "value"),
            packet("/main/1/dyn/on", "bad", 1.0, "bad"),
            packet("/main/1/dyn/thr", "-20", 0.5, -20.0),
            packet("/main/1/dyn/on", "1", 1.0, 1),
        ):
            udp_server.sendto(raw, peer)

    thread = threading.Thread(target=reply)
    thread.start()
    client = WingClient("127.0.0.1", udp_server.getsockname()[1], 0.2)
    assert client.query({"/main/1/dyn/on": int, "/main/1/dyn/thr": float}) == {
        "/main/1/dyn/on": 1,
        "/main/1/dyn/thr": -20.0,
    }
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_single_batch_timeout(udp_server):
    client = WingClient("127.0.0.1", udp_server.getsockname()[1], 0.1)
    start = monotonic()
    assert client.query({f"/main/{n}/dyn/on": int for n in range(1, 5)}) == {}
    assert monotonic() - start < 0.5


def test_connection_rejects_garbage(udp_server):
    def reply():
        _, peer = udp_server.recvfrom(4096)
        udp_server.sendto(b"not OSC", peer)

    thread = threading.Thread(target=reply)
    thread.start()
    with pytest.raises(OSError, match="No valid WING"):
        WingClient("127.0.0.1", udp_server.getsockname()[1], 0.1).test_connection()
    thread.join(timeout=2)


def test_explicit_engineering_write_types(udp_server):
    client = WingClient("127.0.0.1", udp_server.getsockname()[1])
    client.set_values({"/on": 1, "/thr": -20.5, "/det": "RMS"})
    messages = [OscMessage(udp_server.recvfrom(4096)[0]) for _ in range(3)]
    assert [msg.params for msg in messages] == [[1], [-20.5], ["RMS"]]
    assert [msg.dgram for msg in messages] == [
        packet("/on", 1),
        packet("/thr", -20.5),
        packet("/det", "RMS"),
    ]
