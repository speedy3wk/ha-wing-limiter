"""Model-aware numeric controls for the four main dynamics processors."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAIN_COUNT
from .coordinator import WingLimiterCoordinator
from .entity import WingEntity
from .parameters import NUMBERS, Parameter


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        WingNumber(coordinator, entry, n, param)
        for n in range(1, MAIN_COUNT + 1)
        for param in NUMBERS
    )


class WingNumber(WingEntity, NumberEntity):
    """Expose verified engineering ranges; the console quantizes log controls."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: WingLimiterCoordinator,
        entry: ConfigEntry,
        main_index: int,
        parameter: Parameter,
    ) -> None:
        super().__init__(coordinator, entry, main_index, parameter.key, parameter)
        self._attr_native_min_value = parameter.minimum
        self._attr_native_max_value = parameter.maximum
        self._attr_native_step = parameter.step
        self._attr_native_unit_of_measurement = parameter.unit

    @property
    def native_value(self) -> float | None:
        value = (self.coordinator.data or {}).get(self.key)
        return float(value) if isinstance(value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_parameter(
            self.main_index,
            self.parameter_key,
            value,
        )
