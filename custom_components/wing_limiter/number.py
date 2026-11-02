"""Number entities for Behringer WING compressor threshold per main bus."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MAIN_COUNT
from .coordinator import WingLimiterCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WingLimiterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        WingCompressorThreshold(coordinator, entry, n) for n in range(1, MAIN_COUNT + 1)
    )


class WingCompressorThreshold(CoordinatorEntity[WingLimiterCoordinator], NumberEntity):
    """Number entity representing the compressor threshold (dB) for one WING main bus.

    Range:  -60 .. 0 dB in 0.5 dB steps (121 steps as per WING spec).
    """

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = -60.0
    _attr_native_max_value = 0.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "dB"

    def __init__(
        self,
        coordinator: WingLimiterCoordinator,
        entry: ConfigEntry,
        main_index: int,
    ) -> None:
        super().__init__(coordinator)
        self._main_index = main_index
        self._key = f"main_{main_index}_comp_thr"
        self._attr_unique_id = f"{entry.entry_id}_main_{main_index}_comp_thr"
        self._attr_name = "Threshold"
        wing_name = (
            (coordinator.data or {}).get(f"main_{main_index}_name")
            or f"Main {main_index}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_main_{main_index}")},
            name=wing_name,
            manufacturer="Behringer",
            model="WING",
        )

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        val = self.coordinator.data.get(self._key)
        # Round to one decimal to avoid floating-point noise (e.g. -19.999... → -20.0)
        return round(float(val), 1) if val is not None else None

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.get(self._key) is not None
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_comp_thr(self._main_index, value)
