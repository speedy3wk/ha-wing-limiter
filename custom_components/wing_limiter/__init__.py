"""Wing Limiter integration — entry point."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CONF_METERING, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import WingLimiterCoordinator
from .metering import WingMeterCoordinator
from .profiles import WingProfiles, async_setup_services, profile_store

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "number", "select", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host: str = entry.data[CONF_HOST]
    scan_interval: int = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    coordinator = WingLimiterCoordinator(hass, entry, host, scan_interval)
    # Raises ConfigEntryNotReady when WING is unreachable on startup
    await coordinator.async_config_entry_first_refresh()
    coordinator.profiles = WingProfiles(coordinator, entry.entry_id)
    await coordinator.profiles.async_load()
    if entry.options.get(CONF_METERING, False):
        coordinator.meters = WingMeterCoordinator(hass, entry, host)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
        if coordinator.meters:
            await coordinator.meters.async_shutdown()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete only the profile store belonging to the removed entry."""
    await profile_store(hass, entry.entry_id).async_remove()
