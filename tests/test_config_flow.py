"""Configuration preserves existing config entry IDs."""

from unittest.mock import patch

import pytest
import voluptuous as vol

from custom_components.wing_limiter.config_flow import (
    HOST,
    INTERVAL,
    WingLimiterConfigFlow,
    WingOptionsFlow,
)
from custom_components.wing_limiter.const import DOMAIN


def flow(hass, context=None):
    instance = WingLimiterConfigFlow()
    instance.hass = hass
    instance.handler = DOMAIN
    instance.context = context or {"source": "user"}
    return instance


async def test_user_success_and_error(hass):
    instance = flow(hass)
    with patch.object(instance, "_async_connect", return_value=True):
        result = await instance.async_step_user(
            {"host": " WING.LOCAL ", "scan_interval": 5}
        )
    assert result["data"]["host"] == "wing.local"
    instance = flow(hass)
    with patch.object(instance, "_async_connect", return_value=False):
        result = await instance.async_step_user({"host": "offline", "scan_interval": 5})
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_preserves_identity(hass, entry):
    instance = flow(hass, {"source": "reconfigure", "entry_id": entry.entry_id})
    original_id = entry.entry_id
    with (
        patch.object(instance, "_async_connect", return_value=True),
        patch.object(hass.config_entries, "async_schedule_reload") as reload,
        patch.object(hass.config_entries._store, "async_delay_save"),
    ):
        result = await instance.async_step_reconfigure({"host": "192.0.2.10"})
    assert result["reason"] == "reconfigure_successful"
    assert entry.entry_id == original_id
    assert entry.data["host"] == "192.0.2.10"
    assert entry.unique_id == "192.0.2.10"
    reload.assert_called_once_with(entry.entry_id)


async def test_options_defaults_and_schema(hass, entry):
    instance = WingOptionsFlow()
    instance.hass = hass
    instance.handler = entry.entry_id
    result = await instance.async_step_init()
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {"scan_interval": 5, "metering": False}
    for invalid in (0, 61):
        with pytest.raises(vol.Invalid):
            INTERVAL(invalid)
    with pytest.raises(vol.Invalid):
        HOST(" ")
