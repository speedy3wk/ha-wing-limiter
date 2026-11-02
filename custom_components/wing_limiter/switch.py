"""Switch entities for Behringer WING compressor on/off per main bus."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
        WingCompressorSwitch(coordinator, entry, n) for n in range(1, MAIN_COUNT + 1)
    )


class WingCompressorSwitch(CoordinatorEntity[WingLimiterCoordinator], SwitchEntity):
    """Switch entity representing the compressor on/off for one WING main bus."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WingLimiterCoordinator,
        entry: ConfigEntry,
        main_index: int,
    ) -> None:
        super().__init__(coordinator)
        self._main_index = main_index
        self._key = f"main_{main_index}_comp_on"
        self._attr_unique_id = f"{entry.entry_id}_main_{main_index}_comp_on"
        self._attr_name = "Compressor"
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
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        val = self.coordinator.data.get(self._key)
        return bool(val) if val is not None else None

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

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_comp_on(self._main_index, 1)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_comp_on(self._main_index, 0)
