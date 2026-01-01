from __future__ import annotations
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector
import voluptuous as vol
from typing import Any
from .const import DOMAIN, CONF_TEMP, CONF_HUMIDITY, CONF_DEW_POINT, CONF_PRESSURE, CONF_NAME, DEFAULT_SENSOR_NAME, CONF_INDOOR_SENSOR

EXPOSE_ALL = "expose_all"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TEMP): selector({"entity": {"domain": "sensor"}}),
        vol.Required(CONF_HUMIDITY): selector({"entity": {"domain": "sensor"}}),
        vol.Required(CONF_PRESSURE): selector({"entity": {"domain": "sensor"}}),
        vol.Optional(CONF_DEW_POINT, default=""): selector({"entity": {"domain": "sensor"}}),
        vol.Optional(CONF_NAME, default=DEFAULT_SENSOR_NAME): str,
        vol.Optional(EXPOSE_ALL, default=False): bool,
        # HVAC/psychrometrics useful for indoor/energy calculations, optional for plain meteorologic displays
        vol.Optional(CONF_INDOOR_SENSOR, default=False): bool,
    }
)

class MeteorologicMetricsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # normalize empty dew to None
            if user_input.get(CONF_DEW_POINT) == "":
                user_input.pop(CONF_DEW_POINT, None)
            title = user_input.get(CONF_NAME) or DEFAULT_SENSOR_NAME
            # ensure expose_all is present (bool)
            user_input.setdefault(EXPOSE_ALL, False)
            return self.async_create_entry(title=title, data=user_input)
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    async def async_step_import(self, import_config):
        # allow YAML -> UI migration (called when user selects "Import YAML")
        # map keys exactly as in YAML
        # ensure boolean key exists in import if not present
        import_config.setdefault(EXPOSE_ALL, bool(import_config.get(EXPOSE_ALL, False)))
        return await self.async_step_user(import_config)