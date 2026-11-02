"""Compressor bypass and automatic timing controls."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAIN_COUNT
from .entity import WingEntity
from .parameters import SWITCHES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        WingSwitch(hass.data[DOMAIN][entry.entry_id], entry, n, param.key, param)
        for n in range(1, MAIN_COUNT + 1)
        for param in SWITCHES
    )


class WingSwitch(WingEntity, SwitchEntity):
    """Only enable supported model-dependent switches."""

    @property
    def is_on(self) -> bool | None:
        value = (self.coordinator.data or {}).get(self.key)
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_parameter(
            self.main_index, self.key.removeprefix(f"main_{self.main_index}_"), 1
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_parameter(
            self.main_index, self.key.removeprefix(f"main_{self.main_index}_"), 0
        )
