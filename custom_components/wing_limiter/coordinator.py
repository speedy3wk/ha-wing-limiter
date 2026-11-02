"""Poll and control the four WING main dynamics processors."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MAIN_COUNT
from .osc import OscValue, WingClient
from .parameters import PARAMETERS

_LOGGER = logging.getLogger(__name__)
if TYPE_CHECKING:
    from .profiles import WingProfiles
type WingData = dict[str, OscValue | None]


class WingLimiterCoordinator(DataUpdateCoordinator[WingData]):
    """Re-detect models each poll and before every model-dependent write."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, host: str, scan_interval: int
    ) -> None:
        self.client = WingClient(host)
        self.profiles: WingProfiles | None = None
        self.command_lock = asyncio.Lock()
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    def _query_models(self) -> dict[str, OscValue]:
        return self.client.query(
            {f"/main/{n}/dyn/mdl": str for n in range(1, MAIN_COUNT + 1)}
        )

    def _fetch_all_data(self) -> WingData:
        models = self._query_models()
        requests: dict[str, type] = {}
        keys = {}
        data: WingData = {}
        for n in range(1, MAIN_COUNT + 1):
            data[f"main_{n}_model"] = model = models.get(f"/main/{n}/dyn/mdl")
            address = f"/main/{n}/name"
            requests[address] = str
            keys[address] = f"main_{n}_name"
            for param in PARAMETERS.values():
                key = f"main_{n}_{param.key}"
                data[key] = None
                if param.comp_only and model != "COMP":
                    continue
                address = f"/main/{n}/{param.path}"
                requests[address] = param.kind
                keys[address] = key
        replies = self.client.query(requests)
        data.update({key: replies.get(address) for address, key in keys.items()})
        return data

    async def _async_update_data(self) -> WingData:
        try:
            async with self.command_lock:
                data = await self.hass.async_add_executor_job(self._fetch_all_data)
        except OSError as err:
            raise UpdateFailed(f"Error communicating with WING: {err}") from err
        if all(
            data[f"main_{n}_comp_on"] not in (0, 1) for n in range(1, MAIN_COUNT + 1)
        ):
            raise UpdateFailed("No valid compressor response from WING")
        return data

    def _write_parameters(self, n: int, values: dict[str, OscValue]) -> None:
        if not 1 <= n <= MAIN_COUNT:
            raise ValueError("Main index must be 1..4")
        model = self.client.query({f"/main/{n}/dyn/mdl": str}).get(f"/main/{n}/dyn/mdl")
        writes = {}
        for key, value in values.items():
            param = PARAMETERS[key]
            if param.comp_only and model != "COMP":
                raise ValueError(f"{key} requires the COMP model; detected {model}")
            writes[f"/main/{n}/{param.path}"] = param.encode(value)
        self.client.set_values(writes)

    async def async_set_parameter(self, n: int, key: str, value: OscValue) -> None:
        try:
            async with self.command_lock:
                await self.hass.async_add_executor_job(
                    self._write_parameters, n, {key: value}
                )
        except (OSError, ValueError) as err:
            raise HomeAssistantError(f"Unable to set WING parameter: {err}") from err
        # A UDP send is not an acknowledgement; publish only read-back values.
        await self.async_request_refresh()
