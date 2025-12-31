"""
Meteorologic Metric component for Home Assistant.
Maintainer:       Daniel Mason, yoooov
Version:          v1.0.4
Documentation:    https://github.com/yoooov/ha_meteorologic_metrics
"""

from __future__ import annotations

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import UnitOfTemperature, UnitOfPressure, PERCENTAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

import logging
import math as m
import time
from psypy import psySI as SI

from .helpers import *
from .const import *

logger = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
CACHE_TTL = 30.0  # seconds cache for metrics computations to avoid repeated calls


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform (YAML)."""
    # config is the platform config dict
    add_devices(build_entities(hass, config))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up sensor from a config entry (UI)."""
    data = entry.data or {}
    options = entry.options or {}
    # merge options over data so expose_all can be provided as option
    merged = dict(data)
    merged.update(options)
    # build entities and include entry_id to create stable unique_ids
    async_add_entities(build_entities(hass, merged, entry.entry_id), True)


def build_entities(hass, cfg, entry_id: str | None = None):
    """Create a list of entity instances for the integration."""
    name = cfg.get(CONF_NAME) or DEFAULT_SENSOR_NAME
    base_id = (entry_id and f"{DOMAIN}_{entry_id}") or (
        f"{DOMAIN}_{(cfg.get(CONF_TEMP) or '').replace('.', '_')}_{(cfg.get(CONF_HUMIDITY) or '').replace('.', '_')}"
    )

    data = MetricsData(hass, cfg)

    # default: only main wet bulb sensor
    entities = [WetBulbSISensor(hass, data, name, base_id)]

    # expose extra sensors only when requested (cfg key 'expose_all' True)
    if cfg.get("expose_all", False):
        entities.extend(
            [
                SIDryBulbSensor(hass, data, name, base_id),
                SIWetBulbSensor(hass, data, name, base_id),
                SISpecificEnthalpySensor(hass, data, name, base_id),
                SIRelativeHumiditySensor(hass, data, name, base_id),
                SISpecificVolumeSensor(hass, data, name, base_id),
                SIHumidityRatioSensor(hass, data, name, base_id),
                WetBulbStullSensor(hass, data, name, base_id),
                DewPointEstimateSensor(hass, data, name, base_id),
            ]
        )
    return entities


class MetricsData:
    """Shared data holder and calculator for the metrics."""

    def __init__(self, hass: HomeAssistant, config: dict):
        self.hass = hass
        self.config = config or {}
        self.outdoorTemp = self.config.get(CONF_TEMP)
        self.outdoorHum = self.config.get(CONF_HUMIDITY)
        self.pressureSensor = self.config.get(CONF_PRESSURE)
        self.dewSensor = self.config.get(CONF_DEW_POINT)

        self.last_update = 0.0
        self._cache = {}
        self.lock = False

    def refresh(self):
        """Refresh cached metrics if TTL expired. Synchronous helper used by entities."""
        now = time.time()
        if now - self.last_update < CACHE_TTL and self._cache:
            return self._cache

        # protect simple re-entrancy
        if self.lock:
            return self._cache
        self.lock = True
        try:
            result = {}
            # read and normalize inputs (reuse same helper logic)
            result["temp_out_k"] = self._outdoor_temp()
            result["hum_out"] = self._outdoor_hum()
            result["pressure"] = self._pressure()

            logger.debug("MetricsData inputs: temp_k=%s hum=%s pressure=%s",
                         result["temp_out_k"], result["hum_out"], result["pressure"])

            # dew handling
            if self.dewSensor:
                dew_k = self._dew_temp()
                result["dew_temp_k"] = dew_k
                if dew_k is not None and result["temp_out_k"] is not None:
                    result["web_bulb_dew_k"] = result["temp_out_k"] - (result["temp_out_k"] - dew_k) / 3
                else:
                    result["web_bulb_dew_k"] = None
                result["dew_temp_estimate_c"] = None
            else:
                result["dew_temp_k"] = None
                result["dew_temp_estimate_c"] = self._calculate_dewpoint(result["temp_out_k"], result["hum_out"])
                result["web_bulb_dew_k"] = None

            # call psySI if we have required inputs
            if result["temp_out_k"] is None or result["hum_out"] is None or result["pressure"] is None:
                logger.debug("MetricsData: insufficient data for psySI computation")
                result["S"] = None
            else:
                try:
                    logger.debug("MetricsData: calling psySI.state DBT=%s RH=%s P=%s",
                                 result["temp_out_k"], result["hum_out"]/100.0, result["pressure"])
                    S = SI.state("DBT", result["temp_out_k"], "RH", result["hum_out"]/100.0, result["pressure"])
                    result["S"] = S
                    logger.debug("MetricsData: psySI returned %s", repr(S))
                except Exception:
                    logger.exception("MetricsData: psySI.state failure")
                    result["S"] = None

            # other derived metrics
            result["wet_bulb_stull_c"] = self._calculate_wb_stull(result["temp_out_k"], result["hum_out"])
            result["heat_index_c"] = self._calculate_heat_index(result["temp_out_k"], result["hum_out"])
            result["comfort_level"] = self._determine_comfort(
                toC(result["dew_temp_k"]) if result["dew_temp_k"] is not None else result["dew_temp_estimate_c"]
            )

            # store cache
            self._cache = result
            self.last_update = now
            return result
        finally:
            self.lock = False

    # --- input normalization helpers (adapted from previous functions) ---
    def _outdoor_temp(self):
        state = self.hass.states.get(self.outdoorTemp)
        if state is None:
            return None
        try:
            val = float(state.state)
        except (ValueError, TypeError):
            logger.warning("Outdoor temp state not numeric: %s", state.state)
            return None
        unit = state.attributes.get("unit_of_measurement")
        if unit == UnitOfTemperature.CELSIUS:
            return toK(val)
        if unit == UnitOfTemperature.FAHRENHEIT:
            return toK(FtoC(val))
        if unit == "K" or unit == "kelvin" or (hasattr(UnitOfTemperature, "KELVIN") and unit == UnitOfTemperature.KELVIN):
            return val
        logger.debug("MetricsData: unknown temp unit '%s' for %s; assuming Celsius", unit, self.outdoorTemp)
        return toK(val)

    def _pressure(self):
        state = self.hass.states.get(self.pressureSensor)
        if state is None:
            return None
        try:
            val = float(state.state)
        except (ValueError, TypeError):
            logger.warning("Pressure state not numeric: %s", state.state)
            return None
        unit = state.attributes.get("unit_of_measurement")
        if unit in (UnitOfPressure.HPA, "hPa", "mbar", "mb"):
            return val * 100.0
        if unit in (UnitOfPressure.PA, "Pa"):
            return val
        if unit in ("mmHg",):
            return val * 133.322
        logger.debug("MetricsData: unknown pressure unit '%s' for %s; assuming hPa", unit, self.pressureSensor)
        return val * 100.0

    def _outdoor_hum(self):
        state = self.hass.states.get(self.outdoorHum)
        if state is None:
            return None
        try:
            val = float(state.state)
        except (ValueError, TypeError):
            logger.warning("Humidity state not numeric: %s", state.state)
            return None
        unit = state.attributes.get("unit_of_measurement")
        if unit == PERCENTAGE or unit == "%":
            return val
        if 0.0 <= val <= 1.0:
            return val * 100.0
        logger.debug("MetricsData: unknown humidity unit '%s' for %s; assuming percent", unit, self.outdoorHum)
        return val

    def _dew_temp(self):
        if not self.dewSensor:
            return None
        state = self.hass.states.get(self.dewSensor)
        if state is None:
            return None
        try:
            val = float(state.state)
        except (ValueError, TypeError):
            logger.warning("Dew point state not numeric: %s", state.state)
            return None
        unit = state.attributes.get("unit_of_measurement")
        if unit == UnitOfTemperature.CELSIUS:
            return toK(val)
        if unit == UnitOfTemperature.FAHRENHEIT:
            return toK(FtoC(val))
        if unit == "K" or (hasattr(UnitOfTemperature, "KELVIN") and unit == UnitOfTemperature.KELVIN):
            return val
        logger.debug("MetricsData: unknown dew unit '%s' for %s; assuming Celsius", unit, self.dewSensor)
        return toK(val)

    # --- derived helpers ---
    def _calculate_dewpoint(self, temp_out_k, hum_out):
        if temp_out_k is not None and hum_out is not None:
            try:
                alpha = m.log(hum_out / 100) + (AA * toC(temp_out_k)) / (BB + toC(temp_out_k))
                dp = (BB * alpha) / (AA - alpha)
                return dp
            except Exception:
                logger.exception("MetricsData: invalid inputs for dewpoint calc (temp_k=%s, hum=%s)", temp_out_k, hum_out)
        return None

    def _calculate_heat_index(self, temp_k, hum):
        if temp_k is not None and hum is not None:
            T = KtoF(temp_k)
            R = hum
            if T > 80 and R > 40:
                hi = c1 + c2 * T + c3 * R + c4 * T * R + c5 * m.pow(T, 2) + c6 * m.pow(R, 2) + c7 * m.pow(T, 2) * R + c8 * m.pow(R, 2) * T + c9 * m.pow(T, 2) * m.pow(R, 2)
                return FtoC(hi)
        return None

    def _calculate_wb_stull(self, temp_k, hum):
        if temp_k is None or hum is None:
            return None
        T = toC(temp_k)
        H = hum
        if not isinstance(H, (int, float)) or not isinstance(T, (int, float)):
            return None
        if H > 5 and H < 99 and T > -20 and T < 50:
            return T * m.atan(0.151977 * m.pow(H + 8.313659, 0.5)) + m.atan(T + H) - m.atan(H - 1.676331) + 0.00391838 * m.pow(H, 3/2) * m.atan(0.023101 * H) - 4.686035
        return None

    def _determine_comfort(self, dp):
        if dp is None:
            return None
        if dp > 21:
            return 4
        if dp > 18:
            return 3
        if dp > 16:
            return 2
        if dp > 10:
            return 1
        return 0


# --- Base sensor class used by all metric sensors ---
class MetricsBaseSensor(Entity):
    def __init__(self, hass, data: MetricsData, name: str, base_id: str, suffix: str):
        self.hass = hass
        self._data = data
        # if suffix is empty, keep the base name (no trailing space) and use base_id as unique_id
        if suffix:
            self._name = f"{name} {suffix}"
            self._unique_id = f"{base_id}_{suffix.replace(' ', '_').lower()}"
        else:
            self._name = name
            self._unique_id = f"{base_id}"
        self._state = None

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def available(self):
        # available if shared data has enough inputs
        cache = self._data.refresh()
        return cache.get("temp_out_k") is not None and cache.get("hum_out") is not None and cache.get("pressure") is not None

    def update(self):
        # update shared cache and then read own value
        cache = self._data.refresh()
        self._update_from_cache(cache)


# --- Individual sensor entities ---

class WetBulbSISensor(MetricsBaseSensor):
    """Main wet-bulb sensor (keeps prior behaviour/state)"""
    def __init__(self, hass, data, name, base_id):
        super().__init__(hass, data, name, base_id, "Wet bulb (SI)")
        self._attr_unit = UnitOfTemperature.CELSIUS

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return UnitOfTemperature.CELSIUS

    def _update_from_cache(self, cache):
        S = cache.get("S")
        if S and S[5] is not None:
            self._state = round(toC(S[5]), 2)
        else:
            self._state = None

    @property
    def extra_state_attributes(self):
        """Expose related SI values and derived metrics as attributes (legacy-style)."""
        cache = self._data.refresh()
        attrs = {}

        S = cache.get("S")
        if S:
            if S[0] is not None:
                attrs["SI dry bulb temp C"] = round(toC(S[0]), 2)
            if S[5] is not None:
                attrs["SI wet bulb temp C"] = round(toC(S[5]), 2)
            if S[1] is not None:
                attrs["SI specific enthalpy"] = round(S[1], 2)
            if S[2] is not None:
                attrs["SI relative humidity"] = round(S[2], 2)
            if S[3] is not None:
                attrs["SI specific volume"] = round(S[3], 4)
            if S[4] is not None:
                attrs["SI humidity ratio"] = round(S[4], 6)

        if cache.get("dew_temp_k") is not None:
            attrs["dew point"] = round(toC(cache["dew_temp_k"]), 2)
        if cache.get("dew_temp_estimate_c") is not None:
            attrs["dew point estimate"] = round(cache["dew_temp_estimate_c"], 2)
        if cache.get("heat_index_c") is not None:
            attrs["heat index"] = round(cache["heat_index_c"], 2)
        if cache.get("wet_bulb_stull_c") is not None:
            attrs["wet bulb temp (stull) C"] = round(cache["wet_bulb_stull_c"], 2)
        if cache.get("comfort_level") is not None:
            attrs["comfort level"] = cache["comfort_level"]

        return attrs


class SIDryBulbSensor(MetricsBaseSensor):
    def __init__(self, hass, data, name, base_id):
        super().__init__(hass, data, name, base_id, "SI dry bulb temp C")

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return UnitOfTemperature.CELSIUS

    def _update_from_cache(self, cache):
        S = cache.get("S")
        if S and S[0] is not None:
            self._state = round(toC(S[0]), 2)
        else:
            self._state = None


class SIWetBulbSensor(MetricsBaseSensor):
    def __init__(self, hass, data, name, base_id):
        super().__init__(hass, data, name, base_id, "SI wet bulb temp C")

    @property
    def unit_of_measurement(self):
        return UnitOfTemperature.CELSIUS

    def _update_from_cache(self, cache):
        S = cache.get("S")
        if S and S[5] is not None:
            self._state = round(toC(S[5]), 2)
        else:
            self._state = None


class SISpecificEnthalpySensor(MetricsBaseSensor):
    def __init__(self, hass, data, name, base_id):
        super().__init__(hass, data, name, base_id, "SI specific enthalpy")
    def _update_from_cache(self, cache):
        S = cache.get("S")
        self._state = round(S[1], 2) if S and S[1] is not None else None


class SIRelativeHumiditySensor(MetricsBaseSensor):
    def __init__(self, hass, data, name, base_id):
        super().__init__(hass, data, name, base_id, "SI relative humidity")
    def _update_from_cache(self, cache):
        S = cache.get("S")
        self._state = round(S[2], 2) if S and S[2] is not None else None
    @property
    def unit_of_measurement(self):
        return PERCENTAGE


class SISpecificVolumeSensor(MetricsBaseSensor):
    def __init__(self, hass, data, name, base_id):
        super().__init__(hass, data, name, base_id, "SI specific volume")
    def _update_from_cache(self, cache):
        S = cache.get("S")
        self._state = round(S[3], 4) if S and S[3] is not None else None


class SIHumidityRatioSensor(MetricsBaseSensor):
    def __init__(self, hass, data, name, base_id):
        super().__init__(hass, data, name, base_id, "SI humidity ratio")
    def _update_from_cache(self, cache):
        S = cache.get("S")
        self._state = round(S[4], 6) if S and S[4] is not None else None


class WetBulbStullSensor(MetricsBaseSensor):
    def __init__(self, hass, data, name, base_id):
        super().__init__(hass, data, name, base_id, "wet bulb temp (stull) C")
    @property
    def unit_of_measurement(self):
        return UnitOfTemperature.CELSIUS
    def _update_from_cache(self, cache):
        v = cache.get("wet_bulb_stull_c")
        self._state = round(v, 2) if isinstance(v, (int, float)) else None


class DewPointEstimateSensor(MetricsBaseSensor):
    def __init__(self, hass, data, name, base_id):
        super().__init__(hass, data, name, base_id, "dew point estimate C")
    @property
    def unit_of_measurement(self):
        return UnitOfTemperature.CELSIUS
    def _update_from_cache(self, cache):
        v = cache.get("dew_temp_estimate_c")
        self._state = round(v, 2) if isinstance(v, (int, float)) else None
