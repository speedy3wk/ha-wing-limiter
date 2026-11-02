"""Poll and control the four WING main dynamics processors."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MAIN_COUNT, OSC_COMP_ON, OSC_COMP_THR, OSC_MAIN_NAME
from .osc import OscValue, WingClient

_LOGGER = logging.getLogger(__name__)
type WingData = dict[str, OscValue | None]


class WingLimiterCoordinator(DataUpdateCoordinator[WingData]):
    """Serialize polling and commands, with a bounded timeout for the whole poll."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, host: str, scan_interval: int
    ) -> None:
        self.client = WingClient(host)
        self.command_lock = asyncio.Lock()
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> WingData:
        try:
            async with self.command_lock:
                data = await self.hass.async_add_executor_job(self._fetch_all_data)
        except OSError as err:
            raise UpdateFailed(f"Error communicating with WING: {err}") from err
        if all(data[f"main_{n}_comp_on"] is None for n in range(1, MAIN_COUNT + 1)):
            raise UpdateFailed("No valid compressor response from WING")
        return data

    def _fetch_all_data(self) -> WingData:
        requests = {}
        keys = {}
        for n in range(1, MAIN_COUNT + 1):
            for key, address, kind in (
                ("comp_on", OSC_COMP_ON.format(n), int),
                ("comp_thr", OSC_COMP_THR.format(n), float),
                ("name", OSC_MAIN_NAME.format(n), str),
            ):
                requests[address] = kind
                keys[address] = f"main_{n}_{key}"
        replies = self.client.query(requests)
        return {key: replies.get(address) for address, key in keys.items()}

    async def _async_set(self, n: int, key: str, address: str, value: OscValue) -> None:
        try:
            async with self.command_lock:
                await self.hass.async_add_executor_job(
                    self.client.set_values, {address: value}
                )
        except OSError as err:
            raise HomeAssistantError(f"Unable to send WING command: {err}") from err
        # A UDP send is not an acknowledgement; publish only read-back values.
        await self.async_request_refresh()

    async def async_set_comp_on(self, main_index: int, value: int) -> None:
        await self._async_set(
            main_index, "comp_on", OSC_COMP_ON.format(main_index), value
        )

    async def async_set_comp_thr(self, main_index: int, value: float) -> None:
        await self._async_set(
            main_index, "comp_thr", OSC_COMP_THR.format(main_index), float(value)
        )
