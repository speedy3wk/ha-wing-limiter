"""Persistent, user-created COMP snapshots, with read-back verification."""

from __future__ import annotations

import asyncio
import math
from typing import TypedDict

import probatio as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .coordinator import WingLimiterCoordinator
from .osc import OscValue
from .parameters import PARAMETERS

PROFILE_STORAGE_SCHEMA = vol.Schema(
    {
        vol.All(str, vol.Length(min=1, max=64)): {
            vol.Required("main_index"): vol.All(int, vol.Range(min=1, max=4)),
            vol.Required("model"): "COMP",
            vol.Required("values"): {
                vol.Required(key): parameter.encode
                for key, parameter in PARAMETERS.items()
            },
        }
    }
)


class Profile(TypedDict):
    main_index: int
    model: str
    values: dict[str, OscValue]


def profile_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Profile]]:
    return Store(hass, 1, f"{DOMAIN}.{entry_id}.profiles")


class WingProfiles:
    def __init__(self, coordinator: WingLimiterCoordinator, entry_id: str) -> None:
        self.coordinator = coordinator
        self.store = profile_store(coordinator.hass, entry_id)
        self.profiles: dict[str, Profile] = {}
        self.lock = asyncio.Lock()

    async def async_load(self) -> None:
        stored = await self.store.async_load()
        try:
            self.profiles = PROFILE_STORAGE_SCHEMA(stored if stored is not None else {})
        except vol.Invalid as err:
            raise HomeAssistantError(f"Invalid stored WING profiles: {err}") from err

    async def async_save(self, n: int, name: str, overwrite: bool = False) -> None:
        async with self.lock:
            if name in self.profiles and not overwrite:
                raise ServiceValidationError("Profile already exists; enable overwrite")
            coordinator = self.coordinator
            try:
                async with coordinator.command_lock:
                    data = await coordinator.hass.async_add_executor_job(
                        coordinator._fetch_all_data
                    )
            except OSError as err:
                raise HomeAssistantError(f"Unable to read WING profile: {err}") from err
            if data.get(f"main_{n}_model") != "COMP":
                raise ServiceValidationError("Profiles require the COMP model")
            values = {}
            for key, param in PARAMETERS.items():
                value = data.get(f"main_{n}_{key}")
                if value is None or not param.valid(value):
                    raise HomeAssistantError(
                        f"Profile incomplete: missing or invalid {key}"
                    )
                values[key] = value
            profile: Profile = {"main_index": n, "model": "COMP", "values": values}
            updated = {**self.profiles, name: profile}
            await self.store.async_save(updated)
            self.profiles = updated

    async def async_restore(self, n: int, name: str) -> None:
        async with self.lock:
            profile = self.profiles.get(name)
            if profile is None or profile["main_index"] != n:
                raise ServiceValidationError("Profile not found for this main bus")
            if profile["model"] != "COMP" or set(profile["values"]) != set(PARAMETERS):
                raise ServiceValidationError("Invalid or incompatible profile")
            values = dict(profile["values"])
            # Apply enable/bypass last; never switch the Dynamics model.
            on = values.pop("comp_on")
            values["comp_on"] = on
            coordinator = self.coordinator
            try:
                async with coordinator.command_lock:
                    await coordinator.hass.async_add_executor_job(
                        coordinator._write_parameters, n, values
                    )
                    observed = await coordinator.hass.async_add_executor_job(
                        coordinator._fetch_all_data
                    )
            except (OSError, ValueError) as err:
                raise HomeAssistantError(
                    f"Unable to restore WING profile: {err}"
                ) from err
            coordinator.async_set_updated_data(observed)
            if observed.get(f"main_{n}_model") != "COMP":
                raise HomeAssistantError(
                    "Dynamics model changed during profile restore"
                )
            for key, expected in values.items():
                actual = observed.get(f"main_{n}_{key}")
                matches = actual == expected
                if isinstance(expected, (int, float)) and isinstance(
                    actual, (int, float)
                ):
                    matches = math.isclose(
                        actual, expected, rel_tol=1e-5, abs_tol=0.001
                    )
                if not matches:
                    raise HomeAssistantError(
                        f"Profile not confirmed: {key} expected {expected}, received {actual}. "
                        "Some settings may already have changed."
                    )

    async def async_delete(self, n: int, name: str) -> None:
        async with self.lock:
            profile = self.profiles.get(name)
            if profile is None or profile["main_index"] != n:
                raise ServiceValidationError("Profile not found for this main bus")
            updated = {
                key: value for key, value in self.profiles.items() if key != name
            }
            await self.store.async_save(updated)
            self.profiles = updated


def async_setup_services(hass: HomeAssistant) -> None:
    """Resolve the target on every call so reloads never keep stale coordinators."""
    if hass.services.has_service(DOMAIN, "save_profile"):
        return
    common: dict[object, object] = {
        vol.Required("entry_id"): str,
        vol.Required("main_index"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
        vol.Required("name"): vol.All(str, vol.Strip, vol.Length(min=1, max=64)),
    }

    async def handle(call: ServiceCall) -> dict | None:
        coordinator = hass.data.get(DOMAIN, {}).get(call.data["entry_id"])
        if coordinator is None or coordinator.profiles is None:
            raise ServiceValidationError("WING entry is not loaded")
        profiles = coordinator.profiles
        if call.service == "list_profiles":
            return {
                "profiles": [
                    {
                        "name": name,
                        "main_index": profile["main_index"],
                        "model": profile["model"],
                    }
                    for name, profile in sorted(profiles.profiles.items())
                ]
            }
        n, name = call.data["main_index"], call.data["name"]
        if call.service == "save_profile":
            await profiles.async_save(n, name, call.data["overwrite"])
        elif call.service == "restore_profile":
            await profiles.async_restore(n, name)
        else:
            await profiles.async_delete(n, name)
        return None

    for service in ("save_profile", "restore_profile", "delete_profile"):
        schema = dict(common)
        if service == "save_profile":
            schema[vol.Optional("overwrite", default=False)] = bool
        hass.services.async_register(DOMAIN, service, handle, schema=vol.Schema(schema))
    hass.services.async_register(
        DOMAIN,
        "list_profiles",
        handle,
        schema=vol.Schema({vol.Required("entry_id"): str}),
        supports_response=SupportsResponse.ONLY,
    )
