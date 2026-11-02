"""Read-only dynamics model detection."""

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAIN_COUNT
from .entity import WingEntity
from .metering import METER_KEYS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        WingModelSensor(hass.data[DOMAIN][entry.entry_id], entry, n, "model")
        for n in range(1, MAIN_COUNT + 1)
    )
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.meters is not None:
        async_add_entities(
            WingMeterSensor(coordinator, entry, n, key)
            for n in range(1, MAIN_COUNT + 1)
            for key in METER_KEYS
        )


class WingModelSensor(WingEntity, SensorEntity):
    @property
    def native_value(self) -> str | None:
        value = (self.coordinator.data or {}).get(self.key)
        return str(value) if value is not None else None


class WingMeterSensor(WingEntity, SensorEntity):
    _attr_native_unit_of_measurement = "dB"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"all"})

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        assert self.coordinator.meters is not None
        self.async_on_remove(
            self.coordinator.meters.async_add_listener(self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        meters = self.coordinator.meters
        if not self.coordinator.last_update_success or meters is None:
            return False
        if self.parameter_key == "gain_reduction" and (
            (self.coordinator.data or {}).get(f"main_{self.main_index}_model") != "COMP"
        ):
            return False
        return meters.last_update_success and self.key in (meters.data or {})

    @property
    def native_value(self) -> float | None:
        meters = self.coordinator.meters
        value = (meters.data or {}).get(self.key) if meters else None
        return round(value, 2) if value is not None else None
