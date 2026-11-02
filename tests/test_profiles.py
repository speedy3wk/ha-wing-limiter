"""Snapshots are fresh, persisted and verified rather than optimistically accepted."""

from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.wing_limiter.const import DOMAIN
from custom_components.wing_limiter.osc import OscValue
from custom_components.wing_limiter.parameters import PARAMETERS
from custom_components.wing_limiter.profiles import WingProfiles, async_setup_services


def complete_data():
    result: dict[str, OscValue] = {"main_1_model": "COMP"}
    for key, param in PARAMETERS.items():
        value = param.options[0] if param.options else param.minimum
        if param.kind is float:
            value = float(value)
        elif param.kind is int:
            value = int(value)
        result[f"main_1_{key}"] = value
    return result


async def test_profile_persistence_restore_and_delete(coordinator, entry):
    profiles = WingProfiles(coordinator, entry.entry_id)
    await profiles.async_load()
    observed = complete_data()
    with patch.object(coordinator, "_fetch_all_data", return_value=observed):
        await profiles.async_save(1, "Live")
    reloaded = WingProfiles(coordinator, entry.entry_id)
    await reloaded.async_load()
    assert reloaded.profiles["Live"]["model"] == "COMP"
    with (
        patch.object(coordinator, "_write_parameters") as write,
        patch.object(coordinator, "_fetch_all_data", return_value=observed),
    ):
        await reloaded.async_restore(1, "Live")
    assert list(write.call_args.args[1])[-1] == "comp_on"
    await reloaded.async_delete(1, "Live")
    await profiles.async_load()
    assert profiles.profiles == {}


async def test_incomplete_or_wrong_model_never_saved(coordinator, entry):
    profiles = WingProfiles(coordinator, entry.entry_id)
    for data in ({}, {"main_1_model": "76LA"}, {"main_1_model": "COMP"}):
        with patch.object(coordinator, "_fetch_all_data", return_value=data):
            with pytest.raises(HomeAssistantError):
                await profiles.async_save(1, "Broken")
    assert not profiles.profiles


async def test_restore_failure_not_success_shaped(coordinator, entry):
    profiles = WingProfiles(coordinator, entry.entry_id)
    data = complete_data()
    with patch.object(coordinator, "_fetch_all_data", return_value=data):
        await profiles.async_save(1, "Live")
        with pytest.raises(ServiceValidationError, match="already exists"):
            await profiles.async_save(1, "Live")
    with (
        patch.object(coordinator, "_write_parameters"),
        patch.object(
            coordinator,
            "_fetch_all_data",
            return_value={
                **data,
                "main_1_comp_thr": -10,
            },
        ),
    ):
        with pytest.raises(HomeAssistantError, match="not confirmed"):
            await profiles.async_restore(1, "Live")
    with pytest.raises(ServiceValidationError):
        await profiles.async_restore(2, "Live")


async def test_service_lifecycle_and_entry_validation(coordinator, hass, entry):
    coordinator.profiles = WingProfiles(coordinator, entry.entry_id)
    hass.data[DOMAIN] = {entry.entry_id: coordinator}
    async_setup_services(hass)
    async_setup_services(hass)
    response = await hass.services.async_call(
        DOMAIN,
        "list_profiles",
        {"entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == {"profiles": []}
    with pytest.raises(ServiceValidationError, match="not loaded"):
        await hass.services.async_call(
            DOMAIN,
            "list_profiles",
            {"entry_id": "missing"},
            blocking=True,
            return_response=True,
        )


async def test_invalid_stored_profile_is_not_silently_accepted(coordinator, entry):
    profiles = WingProfiles(coordinator, entry.entry_id)
    with patch.object(
        profiles.store,
        "async_load",
        return_value={"Broken": {"main_index": 1, "model": "COMP", "values": {}}},
    ):
        with pytest.raises(HomeAssistantError, match="Invalid stored WING profiles"):
            await profiles.async_load()
