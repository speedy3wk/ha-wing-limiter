"""Model gating, entity identity and command validation."""

from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from custom_components.wing_limiter.const import DOMAIN
from custom_components.wing_limiter.number import WingNumber
from custom_components.wing_limiter.parameters import NUMBERS, PARAMETERS
from custom_components.wing_limiter.select import WingSelect
from custom_components.wing_limiter.switch import WingSwitch


def values(model="COMP"):
    return {
        f"main_{n}_{key}": value
        for n in range(1, 5)
        for key, value in (
            ("model", model),
            ("name", f"Bus {n}"),
            ("comp_on", 1),
            ("comp_thr", -20.0),
        )
    }


def test_model_gating_and_stable_ids(coordinator, entry):
    coordinator.async_set_updated_data(values())
    threshold = WingNumber(coordinator, entry, 1, NUMBERS[0])
    assert threshold.unique_id == f"{entry.entry_id}_main_1_comp_thr"
    assert threshold.available
    assert threshold.native_min_value == -60
    assert threshold.native_step == 0.5
    coordinator.async_set_updated_data(values("76LA"))
    assert not threshold.available
    on = PARAMETERS["comp_on"]
    assert WingSwitch(coordinator, entry, 1, on.key, on).available


def test_poll_does_not_query_unknown_model_controls(coordinator):
    def query(requests):
        return {address: "76LA" for address in requests if address.endswith("/mdl")}

    with patch.object(coordinator.client, "query", side_effect=query) as mocked:
        data = coordinator._fetch_all_data()
    assert data["main_1_comp_thr"] is None
    requests = mocked.call_args.args[0]
    assert "/main/1/dyn/thr" not in requests
    assert "/main/1/dyn/on" in requests


async def test_live_model_checked_before_write(coordinator):
    with (
        patch.object(
            coordinator.client, "query", return_value={"/main/1/dyn/mdl": "LA"}
        ),
        patch.object(coordinator.client, "set_values") as write,
    ):
        with pytest.raises(HomeAssistantError, match="requires the COMP"):
            await coordinator.async_set_parameter(1, "comp_thr", -20)
        write.assert_not_called()


async def test_values_validated_and_ratio_sent_as_float(coordinator):
    with (
        patch.object(
            coordinator.client, "query", return_value={"/main/1/dyn/mdl": "COMP"}
        ),
        patch.object(coordinator.client, "set_values") as write,
    ):
        for key, value in (
            ("comp_thr", 10),
            ("comp_thr", float("nan")),
            ("comp_knee", 2.5),
            ("comp_ratio", "7.0"),
        ):
            with pytest.raises(HomeAssistantError):
                await coordinator.async_set_parameter(1, key, value)
        write.assert_not_called()
        await coordinator.async_set_parameter(1, "comp_ratio", "4.0")
        write.assert_called_once_with({"/main/1/dyn/ratio": 4.0})


async def test_names_updated_without_overwriting_user_name(coordinator, entry, hass):
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_main_1")},
        name="Old",
    )
    registry.async_update_device(device.id, name_by_user="My name")
    coordinator.async_set_updated_data(values())
    entity = WingNumber(coordinator, entry, 1, NUMBERS[0])
    entity.hass = hass
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()
    assert registry.async_get(device.id).name == "Bus 1"
    assert registry.async_get(device.id).name_by_user == "My name"


def test_select_choices(coordinator, entry):
    param = PARAMETERS["comp_ratio"]
    entity = WingSelect(coordinator, entry, 1, param.key, param)
    coordinator.async_set_updated_data({**values(), "main_1_comp_ratio": 4.0})
    assert entity.current_option == "4.0"
    assert "100.0" in entity.options
