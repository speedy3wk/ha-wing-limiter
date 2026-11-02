"""Native byte framing, stream lifecycle, sender filtering and model-aware GR."""

import asyncio
import struct
from unittest.mock import patch

import pytest

from custom_components.wing_limiter.metering import (
    WingMeterCoordinator,
    WingMeterStream,
    decode_meters,
    meter_request,
    native_frame,
)
from custom_components.wing_limiter.sensor import WingMeterSensor


def test_native_framing_and_meter_scale():
    assert native_frame(b"\xdf\xd3") == b"\xdf\xd3\xdf\xde\xd3"
    assert meter_request(12345, b"TEST") == (
        b"\xdf\xd3\xd3\x30\x39\xd4TEST\xdc\xa3\x00\x01\x02\x03\xde"
    )
    data = decode_meters(
        b"TEST" + struct.pack(">32h", *([-2560, -5120, 0, -256, 0, 0, 0, 128] * 4)),
        b"TEST",
    )
    assert data["main_1_input_l"] == -10
    assert data["main_4_output_r"] == -1
    assert data["main_2_gain_reduction"] == 10
    for bad in (b"", b"OTHER" + bytes(64), b"FAIL" + bytes(64)):
        with pytest.raises(ValueError):
            decode_meters(bad, b"TEST")


async def test_bad_sources_reports_and_error_handling():
    stream = WingMeterStream("127.0.0.1")
    stream.peer_ip = "127.0.0.1"
    packet = stream.report_id + bytes(64)
    stream.datagram_received(packet, ("192.0.2.1", 2222))
    assert stream.latest is None
    stream.datagram_received(b"bad", ("127.0.0.1", 2222))
    assert stream.latest is None
    stream.datagram_received(packet, ("127.0.0.1", 2222))
    assert stream.latest["main_1_input_l"] == 0
    await stream.async_close()
    assert stream.latest is None


async def test_real_tcp_subscription_and_udp_report():
    seen = []
    finished = asyncio.Event()

    async def console(reader, writer):
        try:
            raw = bytearray(await reader.readexactly(2))
            while len(raw) < 17:
                byte = await reader.readexactly(1)
                if byte == b"\xdf":
                    assert await reader.readexactly(1) == b"\xde"
                raw.extend(byte)
            seen.append(raw)
            assert raw[:3] == b"\xdf\xd3\xd3"
            port = struct.unpack(">H", raw[3:5])[0]
            report_id = raw[6:10]
            loop = asyncio.get_running_loop()
            transport, _ = await loop.create_datagram_endpoint(
                asyncio.DatagramProtocol, remote_addr=("127.0.0.1", port)
            )
            transport.sendto(report_id + struct.pack(">32h", *([-256] * 32)))
            transport.close()
            await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()
            finished.set()

    server = await asyncio.start_server(console, "127.0.0.1", 0)
    stream = WingMeterStream("127.0.0.1", server.sockets[0].getsockname()[1])
    stream.report_id = b"TEST"
    try:
        values = await stream.async_sample()
        assert values["main_1_input_l"] == -1
        assert seen
    finally:
        await stream.async_close()
        await asyncio.wait_for(finished.wait(), 2)
        server.close()
        await server.wait_closed()
    assert stream.transport is None and stream.writer is None


async def test_meter_failure_is_independent_and_shutdown(coordinator, entry, hass):
    meter = WingMeterCoordinator(hass, entry, "127.0.0.1")
    coordinator.meters = meter
    coordinator.async_set_updated_data({"main_1_model": "76LA", "main_1_name": "Live"})
    meter.async_set_updated_data({"main_1_input_l": -10, "main_1_gain_reduction": 2})
    level = WingMeterSensor(coordinator, entry, 1, "input_l")
    gr = WingMeterSensor(coordinator, entry, 1, "gain_reduction")
    assert level.available
    assert not gr.available
    with patch.object(meter.stream, "async_sample", side_effect=TimeoutError):
        await meter.async_refresh()
    assert not level.available
    assert coordinator.last_update_success
    await meter.async_shutdown()
