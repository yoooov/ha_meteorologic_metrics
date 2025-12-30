"""The Meteorologic Metrics integration."""

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: dict):
    # keep YAML support: if YAML config present, import to config entries (optional)
    # return True to finish setup when integration is loaded from YAML
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update by reloading the config entry so platforms pick up changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # store entry & forward setup to sensor platform
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # reload integration when options are changed in the UI
    entry.add_update_listener(_async_update_listener)

    await hass.config_entries.async_forward_entry_setup(entry, "sensor")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok