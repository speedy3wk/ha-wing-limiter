"""DataUpdateCoordinator for the Wing Limiter integration."""
from __future__ import annotations

import logging
import socket
from datetime import timedelta

from pythonosc.osc_message import OscMessage
from pythonosc.osc_message_builder import OscMessageBuilder

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_PORT, DOMAIN, MAIN_COUNT, OSC_COMP_ON, OSC_COMP_THR, OSC_MAIN_NAME

_LOGGER = logging.getLogger(__name__)


class WingLimiterCoordinator(DataUpdateCoordinator[dict]):
    """Poll the WING console for compressor state of all 4 mains."""

    def __init__(self, hass: HomeAssistant, host: str, scan_interval: int) -> None:
        self.host = host
        self._port = DEFAULT_PORT
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    # ------------------------------------------------------------------
    # DataUpdateCoordinator interface
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        try:
            data = await self.hass.async_add_executor_job(self._fetch_all_data)
        except Exception as err:
            raise UpdateFailed(
                f"Error communicating with WING at {self.host}: {err}"
            ) from err

        if all(v is None for k, v in data.items() if not k.endswith("_name")):
            raise UpdateFailed(f"No response from WING at {self.host}")

        return data

    # ------------------------------------------------------------------
    # Blocking helpers (run in executor thread)
    # ------------------------------------------------------------------

    def _fetch_all_data(self) -> dict:
        """Open one UDP socket and sequentially GET all parameters for all mains."""
        data: dict = {}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("", 0))
            sock.settimeout(2.0)
            for n in range(1, MAIN_COUNT + 1):
                data[f"main_{n}_comp_on"] = self._osc_get(sock, OSC_COMP_ON.format(n))
                data[f"main_{n}_comp_thr"] = self._osc_get(sock, OSC_COMP_THR.format(n))
                data[f"main_{n}_name"] = self._osc_get_name(sock, OSC_MAIN_NAME.format(n))
        return data

    def _osc_get(self, sock: socket.socket, address: str):
        """
        Send an OSC GET request (no args) and return params[2] from the response.

        WING responds:
          INT params  → ,sfi  → [str, float, int]
          FLOAT params → ,sff  → [str, float, float]
        params[2] is always the actual engineering value.
        """
        try:
            builder = OscMessageBuilder(address=address)
            sock.sendto(builder.build().dgram, (self.host, self._port))
            raw, _ = sock.recvfrom(4096)
            msg = OscMessage(raw)
            if msg.address != address or len(msg.params) < 3:
                _LOGGER.debug(
                    "Unexpected OSC response for %s: addr=%s params=%s",
                    address,
                    msg.address,
                    msg.params,
                )
                return None
            return msg.params[2]
        except socket.timeout:
            _LOGGER.debug("Timeout waiting for OSC response on %s", address)
            return None
        except Exception as err:
            _LOGGER.debug("Error in OSC GET for %s: %s", address, err)
            return None

    def _osc_get_name(self, sock: socket.socket, address: str) -> str | None:
        """
        Send an OSC GET request and return the single string param.

        WING responds to /main/N/name with ,s -> params = ['name_string']
        """
        try:
            builder = OscMessageBuilder(address=address)
            sock.sendto(builder.build().dgram, (self.host, self._port))
            raw, _ = sock.recvfrom(4096)
            msg = OscMessage(raw)
            if msg.address != address or not msg.params:
                return None
            return str(msg.params[0]).strip() or None
        except socket.timeout:
            _LOGGER.debug("Timeout waiting for name response on %s", address)
            return None
        except Exception as err:
            _LOGGER.debug("Error in OSC GET name for %s: %s", address, err)
            return None

    def _osc_set_int(self, address: str, value: int) -> None:
        """Send an OSC message with a single int32 argument (fire-and-forget)."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            builder = OscMessageBuilder(address=address)
            builder.add_arg(value, "i")
            sock.sendto(builder.build().dgram, (self.host, self._port))

    def _osc_set_float(self, address: str, value: float) -> None:
        """Send an OSC message with a single float32 argument (fire-and-forget)."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            builder = OscMessageBuilder(address=address)
            builder.add_arg(float(value), "f")
            sock.sendto(builder.build().dgram, (self.host, self._port))

    # ------------------------------------------------------------------
    # Public async setters (called from entity platforms)
    # ------------------------------------------------------------------

    async def async_set_comp_on(self, main_index: int, value: int) -> None:
        """Enable or disable the compressor on main bus *main_index* (1-based)."""
        address = OSC_COMP_ON.format(main_index)
        await self.hass.async_add_executor_job(self._osc_set_int, address, value)
        # Optimistic update: reflect new state immediately without waiting for next poll
        if self.data is not None:
            updated = dict(self.data)
            updated[f"main_{main_index}_comp_on"] = value
            self.async_set_updated_data(updated)
        await self.async_request_refresh()

    async def async_set_comp_thr(self, main_index: int, value: float) -> None:
        """Set the compressor threshold (dB) on main bus *main_index* (1-based)."""
        address = OSC_COMP_THR.format(main_index)
        await self.hass.async_add_executor_job(self._osc_set_float, address, float(value))
        # Optimistic update: reflect new value immediately
        if self.data is not None:
            updated = dict(self.data)
            updated[f"main_{main_index}_comp_thr"] = float(value)
            self.async_set_updated_data(updated)
        await self.async_request_refresh()
