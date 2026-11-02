"""Shared identity, model availability and bus device naming."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WingLimiterCoordinator
from .parameters import Parameter


class WingEntity(CoordinatorEntity[WingLimiterCoordinator]):
    """Keep 0.1 entity and device unique IDs stable."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WingLimiterCoordinator,
        entry: ConfigEntry,
        main_index: int,
        key: str,
        parameter: Parameter | None = None,
    ) -> None:
        super().__init__(coordinator)
        self.main_index = main_index
        self._entry_id = entry.entry_id
        self.parameter_key = key
        self.parameter = parameter
        self.key = f"main_{main_index}_{key}"
        self._identifier = (DOMAIN, f"{entry.entry_id}_main_{main_index}")
        self._attr_unique_id = f"{entry.entry_id}_main_{main_index}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = dr.DeviceInfo(
            identifiers={self._identifier},
            name=self.bus_name,
            manufacturer="Behringer",
            model="WING",
        )

    @property
    def bus_name(self) -> str:
        value = (self.coordinator.data or {}).get(f"main_{self.main_index}_name")
        return str(value) if value else f"Main {self.main_index}"

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        if self.parameter:
            model = self.coordinator.data.get(f"main_{self.main_index}_model")
            return (
                not self.parameter.comp_only or model == "COMP"
            ) and self.parameter.valid(self.coordinator.data.get(self.key))
        return self.coordinator.data.get(self.key) is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        registry = dr.async_get(self.hass)
        device = registry.async_get_device_by_identifier(
            self._identifier, self._entry_id
        )
        if device and device.name != self.bus_name:
            registry.async_update_device(device.id, name=self.bus_name)
        super()._handle_coordinator_update()
