"""Bounded OSC requests to a single WING console."""

from __future__ import annotations

import logging
import math
import socket
from time import monotonic

from pythonosc.osc_message import OscMessage, ParseError
from pythonosc.osc_message_builder import OscMessageBuilder

from .const import DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)
type OscValue = str | int | float


class WingClient:
    """Use a fresh connected socket for each batch, filtering other senders."""

    def __init__(
        self, host: str, port: int = DEFAULT_PORT, timeout: float = 1.5
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    def query(self, addresses: dict[str, type]) -> dict[str, OscValue]:
        """Receive matching, typed replies until the whole batch deadline."""
        result: dict[str, OscValue] = {}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((self.host, self.port))
            deadline = monotonic() + self.timeout
            for address in addresses:
                sock.send(OscMessageBuilder(address=address).build().dgram)
            while len(result) < len(addresses):
                remaining = deadline - monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    raw = sock.recv(65535)
                except TimeoutError:
                    break
                try:
                    msg = OscMessage(raw)
                except ParseError:
                    _LOGGER.debug("Ignoring malformed OSC reply from %s", self.host)
                    continue
                expected = addresses.get(msg.address)
                if expected is None:
                    continue
                params = msg.params
                if expected is str:
                    if len(params) != 1 or not isinstance(params[0], str):
                        continue
                    value = params[0]
                else:
                    if len(params) != 3:
                        continue
                    value = params[2]
                    if type(value) not in (int, float):
                        continue
                    if not math.isfinite(value):
                        continue
                    if expected is int and type(value) is not int:
                        continue
                result[msg.address] = value
        missing = addresses.keys() - result.keys()
        if missing:
            _LOGGER.debug("Missing OSC replies from %s: %s", self.host, sorted(missing))
        return result

    def set_values(self, values: dict[str, OscValue]) -> None:
        """Send engineering values with explicit OSC types, never normalized floats."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((self.host, self.port))
            for address, value in values.items():
                builder = OscMessageBuilder(address=address)
                builder.add_arg(
                    value,
                    "s"
                    if isinstance(value, str)
                    else ("i" if isinstance(value, int) else "f"),
                )
                sock.send(builder.build().dgram)

    def test_connection(self) -> None:
        """Require a valid compressor state, not just an arbitrary UDP packet."""
        address = "/main/1/dyn/on"
        if self.query({address: int}).get(address) not in (0, 1):
            raise OSError("No valid WING compressor response")
