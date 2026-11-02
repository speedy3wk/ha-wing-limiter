"""UI configuration, reconfiguration and options without recreating entities."""

from __future__ import annotations

import logging
from typing import Any

import probatio as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback

from .const import CONF_METERING, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .osc import WingClient

_LOGGER = logging.getLogger(__name__)
INTERVAL = vol.All(vol.Coerce(int), vol.Range(min=1, max=60))
HOST = vol.All(str, vol.Strip, vol.Lower, vol.Length(min=1))


class WingLimiterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WingOptionsFlow:
        return WingOptionsFlow()

    async def _async_connect(self, host: str) -> bool:
        try:
            await self.hass.async_add_executor_job(WingClient(host).test_connection)
        except OSError as err:
            _LOGGER.debug("WING connection failed: %s", err)
            return False
        return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = HOST(user_input[CONF_HOST])
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            if await self._async_connect(host):
                return self.async_create_entry(
                    title=f"Wing @ {host}",
                    data={
                        CONF_HOST: host,
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    },
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): HOST,
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): INTERVAL,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = HOST(user_input[CONF_HOST])
            if any(
                other.entry_id != entry.entry_id and other.unique_id == host
                for other in self._async_current_entries()
            ):
                return self.async_abort(reason="already_configured")
            if await self._async_connect(host):
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=host,
                    data_updates={CONF_HOST: host},
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): HOST,
                }
            ),
            errors=errors,
        )


class WingOptionsFlow(config_entries.OptionsFlowWithReload):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        entry = self.config_entry
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=entry.options.get(
                            CONF_SCAN_INTERVAL,
                            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                        ),
                    ): INTERVAL,
                    vol.Required(
                        CONF_METERING, default=entry.options.get(CONF_METERING, False)
                    ): bool,
                }
            ),
        )
