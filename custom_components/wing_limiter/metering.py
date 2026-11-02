"""Opt-in native WING metering; independent from OSC control polling."""

from __future__ import annotations

import asyncio
import logging
import secrets
import socket
import struct
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)
NATIVE_PORT = 2222
METER_KEYS = ("input_l", "input_r", "output_l", "output_r", "gain_reduction")


def native_frame(payload: bytes) -> bytes:
    """Select native channel 3 and escape payload DF bytes."""
    return b"\xdf\xd3" + payload.replace(b"\xdf", b"\xdf\xde")


def meter_request(port: int, report_id: bytes) -> bytes:
    """Original main collection: four zero-based indexes, eight int16s each."""
    return native_frame(
        b"\xd3"
        + struct.pack(">H", port)
        + b"\xd4"
        + report_id
        + b"\xdc\xa3\x00\x01\x02\x03\xde"
    )


def decode_meters(raw: bytes, report_id: bytes) -> dict[str, float]:
    if len(raw) != 68 or raw[:4] != report_id:
        raise ValueError("Unexpected meter report ID or length")
    values = struct.unpack(">32h", raw[4:])
    result = {}
    for n in range(1, 5):
        meters = values[(n - 1) * 8 : n * 8]
        for key, value in zip(METER_KEYS[:4], meters[:4], strict=True):
            result[f"main_{n}_{key}"] = value / 256
        # COMP dynamics gain is normalized: 256 corresponds to 20 dB reduction.
        result[f"main_{n}_gain_reduction"] = meters[7] * 20 / 256
    return result


class WingMeterStream(asyncio.DatagramProtocol):
    """Keep one TCP subscription and one UDP receiver until entry unload."""

    def __init__(self, host: str, port: int = NATIVE_PORT) -> None:
        self.host = host
        self.port = port
        self.report_id = secrets.token_bytes(4)
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.transport: asyncio.DatagramTransport | None = None
        self.peer_ip: str | None = None
        self.latest: dict[str, float] | None = None
        self.received_at = 0.0
        self.renewed_at = 0.0
        self.received = asyncio.Event()
        self.error: Exception | None = None

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if addr[0] != self.peer_ip:
            return
        try:
            self.latest = decode_meters(data, self.report_id)
        except ValueError as err:
            _LOGGER.debug("Ignoring invalid WING meter packet: %s", err)
            return
        self.received_at = asyncio.get_running_loop().time()
        self.received.set()

    def error_received(self, exc: Exception) -> None:
        self.error = exc
        self.received.set()

    async def async_sample(self) -> dict[str, float]:
        loop = asyncio.get_running_loop()
        if (
            self.writer is None
            or self.writer.is_closing()
            or (self.reader is not None and self.reader.at_eof())
        ):
            await self.async_close()
            async with asyncio.timeout(2):
                self.reader, self.writer = await asyncio.open_connection(
                    self.host, self.port, family=socket.AF_INET
                )
            self.peer_ip = self.writer.get_extra_info("peername")[0]
            local_ip = self.writer.get_extra_info("sockname")[0]
            self.transport, _ = await loop.create_datagram_endpoint(
                lambda: self,
                local_addr=(local_ip, 0),
                family=socket.AF_INET,
            )
            local_port = self.transport.get_extra_info("sockname")[1]
            self.writer.write(meter_request(local_port, self.report_id))
            await self.writer.drain()
            self.renewed_at = loop.time()
        if loop.time() - self.renewed_at >= 4:
            self.writer.write(native_frame(b"\xd4" + self.report_id))
            await self.writer.drain()
            self.renewed_at = loop.time()
        if self.error is not None:
            raise OSError(f"Meter receiver failed: {self.error}") from self.error
        if self.latest is None or loop.time() - self.received_at > 2:
            self.received.clear()
            async with asyncio.timeout(2):
                await self.received.wait()
        if self.error is not None:
            raise OSError(f"Meter receiver failed: {self.error}") from self.error
        if self.latest is None or loop.time() - self.received_at > 2:
            raise TimeoutError("No current WING meter data")
        return dict(self.latest)

    async def async_close(self) -> None:
        if self.transport:
            self.transport.close()
            self.transport = None
        if self.writer:
            self.writer.close()
            try:
                async with asyncio.timeout(1):
                    await self.writer.wait_closed()
            except (OSError, TimeoutError) as err:
                _LOGGER.debug("Error closing WING meter connection: %s", err)
            self.writer = None
        self.reader = None
        self.latest = None
        self.error = None
        self.received.clear()


class WingMeterCoordinator(DataUpdateCoordinator[dict[str, float]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
        self.stream = WingMeterStream(host)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="WING meters",
            update_interval=timedelta(seconds=1),
        )

    async def _async_update_data(self) -> dict[str, float]:
        try:
            return await self.stream.async_sample()
        except (OSError, TimeoutError) as err:
            await self.stream.async_close()
            raise UpdateFailed(f"WING metering unavailable: {err}") from err
        except asyncio.CancelledError:
            await self.stream.async_close()
            raise

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        await self.stream.async_close()
