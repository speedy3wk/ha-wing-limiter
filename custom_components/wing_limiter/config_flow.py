"""Config flow for the Wing Limiter integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import CONF_SCAN_INTERVAL, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN
from .osc import WingClient

_LOGGER = logging.getLogger(__name__)


def _test_wing_connection(host: str, port: int) -> None:
    """Require a matching, typed OSC reply from the console."""
    WingClient(host, port).test_connection()


class WingLimiterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wing Limiter."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            scan_interval = user_input[CONF_SCAN_INTERVAL]

            try:
                await self.hass.async_add_executor_job(
                    _test_wing_connection, host, DEFAULT_PORT
                )
            except OSError as err:
                _LOGGER.debug("WING connection failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Wing @ {host}",
                    data={CONF_HOST: host, CONF_SCAN_INTERVAL: scan_interval},
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(int, vol.Range(min=1, max=60)),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
