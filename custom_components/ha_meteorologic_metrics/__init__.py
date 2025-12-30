"""The Meteorologic Metrics integration."""

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry

from .const import DOMAIN

PLATFORMS = ["sensor"]  # used with the new config_entries helpers


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

    # Use the newer plural helper that accepts a list/tuple of platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Unload platforms using the appropriate helper
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok