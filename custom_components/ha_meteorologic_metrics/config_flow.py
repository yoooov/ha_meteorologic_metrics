from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, CONF_TEMP, CONF_HUMIDITY, CONF_DEW_POINT, CONF_PRESSURE, CONF_NAME

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TEMP): str,
        vol.Required(CONF_HUMIDITY): str,
        vol.Required(CONF_PRESSURE): str,
        vol.Optional(CONF_DEW_POINT, default=""): str,
        vol.Optional(CONF_NAME, default="Meteorologic Metrics"): str,
    }
)

class MeteorologicMetricsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # remove empty dewpoint
            if user_input.get(CONF_DEW_POINT) == "":
                user_input.pop(CONF_DEW_POINT, None)
            title = user_input.get(CONF_NAME) or "Meteorologic Metrics"
            return self.async_create_entry(title=title, data=user_input)
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_import(self, import_config):
        # allow YAML -> UI migration (called when user selects "Import YAML")
        # map keys exactly as in YAML
        return await self.async_step_user(import_config)