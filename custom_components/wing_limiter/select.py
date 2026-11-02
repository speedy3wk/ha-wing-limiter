"""Discrete COMP and sidechain settings."""

import math

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAIN_COUNT
from .entity import WingEntity
from .parameters import SELECTS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        WingSelect(hass.data[DOMAIN][entry.entry_id], entry, n, param.key, param)
        for n in range(1, MAIN_COUNT + 1)
        for param in SELECTS
    )


class WingSelect(WingEntity, SelectEntity):
    @property
    def options(self) -> list[str]:
        assert self.parameter is not None
        return list(self.parameter.options)

    @property
    def current_option(self) -> str | None:
        value = (self.coordinator.data or {}).get(self.key)
        if (
            self.parameter
            and self.parameter.kind is float
            and isinstance(value, (int, float))
        ):
            return next(
                (
                    option
                    for option in self.options
                    if math.isclose(value, float(option), rel_tol=1e-6)
                ),
                None,
            )
        return str(value) if value is not None else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_parameter(
            self.main_index, self.key.removeprefix(f"main_{self.main_index}_"), option
        )
