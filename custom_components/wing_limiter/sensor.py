"""Read-only dynamics model detection."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAIN_COUNT
from .entity import WingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        WingModelSensor(hass.data[DOMAIN][entry.entry_id], entry, n, "model")
        for n in range(1, MAIN_COUNT + 1)
    )


class WingModelSensor(WingEntity, SensorEntity):
    @property
    def native_value(self) -> str | None:
        value = (self.coordinator.data or {}).get(self.key)
        return str(value) if value is not None else None
