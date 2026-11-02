"""Exercise actual HA platform setup, registration, translations and unloading."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries, loader
from homeassistant.helpers import entity_registry as er

from custom_components.wing_limiter.const import DOMAIN
from custom_components.wing_limiter.coordinator import WingLimiterCoordinator
from custom_components.wing_limiter.metering import METER_KEYS, WingMeterStream
from custom_components.wing_limiter.parameters import PARAMETERS


@pytest.mark.parametrize("model", ["COMP", "76LA"])
@pytest.mark.parametrize("metering", [False, True])
async def test_real_platform_setup_and_unload(hass, entry, model, metering):
    loader.async_setup(hass)
    await er.async_load(hass)
    data = {}
    for n in range(1, 5):
        data[f"main_{n}_model"] = model
        data[f"main_{n}_name"] = f"Bus {n}"
        for key, parameter in PARAMETERS.items():
            value = parameter.options[0] if parameter.options else parameter.minimum
            data[f"main_{n}_{key}"] = parameter.encode(value)
    entry._async_set_state(hass, config_entries.ConfigEntryState.NOT_LOADED, None)
    meter_data = {f"main_{n}_{key}": 0.0 for n in range(1, 5) for key in METER_KEYS}
    with (
        patch.object(hass.config_entries._store, "async_delay_save"),
        patch.object(WingLimiterCoordinator, "_fetch_all_data", return_value=data),
        patch.object(
            WingMeterStream, "async_sample", return_value=meter_data
        ) as sample,
    ):
        hass.config_entries.async_update_entry(entry, options={"metering": metering})
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        assert len(entities) == (92 if metering else 72)
        threshold = next(
            item
            for item in entities
            if item.unique_id == f"{entry.entry_id}_main_1_comp_thr"
        )
        state = hass.states.get(threshold.entity_id)
        assert state is not None
        assert state.state == ("-60.0" if model == "COMP" else "unavailable")
        assert "Threshold" in state.name
        coordinator = hass.data[DOMAIN][entry.entry_id]
        coordinator.async_set_updated_data({**data, "main_1_model": "76LA"})
        await hass.async_block_till_done()
        assert hass.states.get(threshold.entity_id).state == "unavailable"
        coordinator.async_set_updated_data(
            {**data, "main_1_model": "COMP", "main_1_comp_thr": -20.0}
        )
        await hass.async_block_till_done()
        assert hass.states.get(threshold.entity_id).state == "-20.0"
        if metering:
            await coordinator.meters.async_refresh()
            await hass.async_block_till_done()
            sample.assert_awaited_once()
            level = next(
                item
                for item in entities
                if item.unique_id == f"{entry.entry_id}_main_1_input_l"
            )
            assert hass.states.get(level.entity_id).state == "0.0"
        else:
            sample.assert_not_called()
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entry.entry_id not in hass.data[DOMAIN]
