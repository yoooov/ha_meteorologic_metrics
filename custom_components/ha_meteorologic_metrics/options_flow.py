"""Config flow options for Meteorologic Metrics integration (edition after creation)."""

from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import selector

from .const import (
    CONF_TEMP,
    CONF_HUMIDITY,
    CONF_PRESSURE,
    CONF_DEW_POINT,
    CONF_NAME,
    DOMAIN,
    CONF_INDOOR_SENSOR,
)
EXPOSE_ALL = "expose_all"


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options for the integration."""
        if user_input is not None:
            # store options as provided
            return self.async_create_entry(title="", data=user_input)

        # Defaults come first from entry.options then fallback to entry.data
        current = {}
        current.update(self.config_entry.data or {})
        current.update(self.config_entry.options or {})

        schema = vol.Schema(
            {
                vol.Required(CONF_TEMP, default=current.get(CONF_TEMP, "")): selector({"entity": {"domain": "sensor"}}),
                vol.Required(CONF_HUMIDITY, default=current.get(CONF_HUMIDITY, "")): selector({"entity": {"domain": "sensor"}}),
                vol.Required(CONF_PRESSURE, default=current.get(CONF_PRESSURE, "")): selector({"entity": {"domain": "sensor"}}),
                vol.Optional(CONF_DEW_POINT, default=current.get(CONF_DEW_POINT, "")): selector({"entity": {"domain": "sensor"}}),
                vol.Optional(CONF_NAME, default=current.get(CONF_NAME, "Meteorologic Metrics")): str,
                vol.Optional(EXPOSE_ALL, default=current.get(EXPOSE_ALL, False)): bool,
                # indoor sensor toggle, optional for plain meteorologic displays
                vol.Optional(CONF_INDOOR_SENSOR, default=current.get(CONF_INDOOR_SENSOR, False)): bool,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)