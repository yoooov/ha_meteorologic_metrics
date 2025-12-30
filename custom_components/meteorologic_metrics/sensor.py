"""
Meteorologic Metric component for Home Assistant.
Maintainer:       Daniel Mason, yoooov
Version:          v1.0.2
Documentation:    https://github.com/yoooov/ha_meteorologic_metrics
Issues Tracker:   Report issues on Github. Ensure you have the latest version. Include:
                    * YAML configuration (for the misbehaving entity)
                    * log entries at time of error and at time of initialisation
"""

from homeassistant.helpers.entity import Entity
import logging
import math as m
from psypy import psySI as SI
from .helpers import *
from homeassistant.const import UnitOfTemperature, UnitOfPressure, PERCENTAGE
logger = logging.getLogger(__name__)

from .const import *


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    add_devices([ClimateMetricsSensor(hass, config)])

class ClimateMetricsSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self.hass = hass
        self.outdoorTemp = config.get(CONF_TEMP)
        self.outdoorHum = config.get(CONF_HUMIDITY)
        self.pressureSensor= config.get(CONF_PRESSURE)

        self.dewSensor = config.get(CONF_DEW_POINT)
        self.dew_temp_k = None
        self.dew_temp_estimate_c = None
        self.temp_out_k = None
        self.hum_out = None
        self.pressure = None
        self.comfort_level = None
        self.heat_index = None
        self.web_bulb_dew = None
        self.wet_bulb_stull = None
        self.relative_humidity = None
        self.S = None
        if config.get(CONF_NAME):
            self._name = config.get(CONF_NAME)
        else:
            self._name = "Meteologic Metrics"
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def extra_state_attributes(self):
        attr = {}

        if self.S:
            S = self.S
            # S elements may be None; guard each access
            if S[2] is not None:
                self.relative_humidity = S[2]

            if S[0] is not None:
                attr["SI dry bulb temp C"] = round(toC(S[0]), 2)
            if S[5] is not None:
                attr["SI wet bulb temp C"] = round(toC(S[5]), 2)
            if S[1] is not None:
                attr["SI specific enthalpy"] = round(S[1], 2)
            if S[2] is not None:
                attr["SI relative humidity"] = round(S[2], 2)
            if S[3] is not None:
                attr["SI specific volume"] = round(S[3], 2)
            if S[4] is not None:
                attr["SI humidity ratio"] = round(S[4], 2)

        if self.temp_out_k is not None:
            attr['temperature'] = round(toC(self.temp_out_k), 2)
        if self.hum_out is not None:
            attr['humidity'] = self.hum_out
        if self.dew_temp_k is not None:
            attr['dew point'] = round(toC(self.dew_temp_k), 2)
        if self.dew_temp_estimate_c is not None:
            attr['dew point estimate'] = round(self.dew_temp_estimate_c, 2)
        if self.pressure is not None:
            attr['pressure (pascals)'] = self.pressure
        if self.heat_index is not None:
            attr['heat index'] = self.heat_index

        if self.web_bulb_dew is not None:
            attr["wet bulb temp (dew estimate) C"] = round(toC(self.web_bulb_dew), 2)

        if self.wet_bulb_stull is not None:
            attr["wet bulb temp stull estimate C"] = round(self.wet_bulb_stull, 2)

        if self.comfort_level is not None:
            attr["comfort level "] = self.comfort_level
            attr["comfort level info"] = COMFORT[self.comfort_level]

        return attr

    def _outdoor_temp(self):
        """Return outdoor temperature normalized to Kelvin by inspecting unit_of_measurement."""
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
            # convert F -> C -> K
            return toK(FtoC(val))
        # assume Kelvin if explicit or unknown; if unit indicates Kelvin string
        if unit == "K" or unit == "kelvin" or unit == UnitOfTemperature.KELVIN if hasattr(UnitOfTemperature, "KELVIN") else False:
            return val
        # fallback: assume Celsius (common)
        logger.debug("Unknown temperature unit '%s' for %s; assuming Celsius", unit, self.outdoorTemp)
        return toK(val)

    def _pressure(self):
        """Return pressure normalized to Pascals. Reads unit_of_measurement to decide conversion."""
        state = self.hass.states.get(self.pressureSensor)
        if state is None:
            return None
        try:
            val = float(state.state)
        except (ValueError, TypeError):
            logger.warning("Pressure state not numeric: %s", state.state)
            return None

        unit = state.attributes.get("unit_of_measurement")
        # hPa / mbar -> Pa
        if unit in (UnitOfPressure.HPA, "hPa", "mbar", "mb"):
            return val * 100.0
        # Pascals already
        if unit in (UnitOfPressure.PA, "Pa"):
            return val
        # mmHg -> convert to Pa (1 mmHg = 133.322 Pa)
        if unit in ("mmHg",):
            return val * 133.322
        # fallback: assume hPa (common weather sensors) and convert
        logger.debug("Unknown pressure unit '%s' for %s; assuming hPa", unit, self.pressureSensor)
        return val * 100.0

    def _outdoor_hum(self):
        """Return humidity as percent (0-100)."""
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
        # some sensors provide 0-1 fractional humidity
        if 0.0 <= val <= 1.0:
            return val * 100.0
        # fallback: assume already percent
        logger.debug("Unknown humidity unit '%s' for %s; assuming percent", unit, self.outdoorHum)
        return val

    def _dew_temp(self):
        """Return dew point normalized to Kelvin if sensor exists (detect unit)."""
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
        if unit == "K" or unit == UnitOfTemperature.KELVIN if hasattr(UnitOfTemperature, "KELVIN") else False:
            return val
        # fallback assume Celsius
        logger.debug("Unknown dewpoint unit '%s' for %s; assuming Celsius", unit, self.dewSensor)
        return toK(val)

    def update(self):
        if not self._data_available():
            return False
        try:
            # normalize inputs using unit-aware getters
            self.temp_out_k = self._outdoor_temp()
            self.hum_out = self._outdoor_hum()
            self.pressure = self._pressure()  # already in Pascals

            logger.debug("Temp outdoor (K):      " + str(self.temp_out_k))
            logger.debug("Hum outdoor (%):       " + str(self.hum_out))
            logger.debug("Pressure (pascal): " + str(self.pressure))

            if self.dewSensor:
                dew_k = self._dew_temp()
                if dew_k is None:
                    # dew sensor configured but unreadable
                    logger.warning("Configured dew sensor '%s' unreadable", self.dewSensor)
                    self.dew_temp_k = None
                    self.dew_temp_estimate_c = None
                    self.comfort_level = None
                else:
                    self.dew_temp_k = dew_k
                    logger.debug("dew (raw sensor -> K):     " + str(self.dew_temp_k))
                    logger.debug("Dew (C): " + str(toC(self.dew_temp_k)))
                    # compute web_bulb_dew in Kelvin (both temps in K)
                    self.web_bulb_dew = self.temp_out_k - (self.temp_out_k - self.dew_temp_k) / 3
                    logger.debug("Wet bulb dewpoint depression (K): " + str(self.web_bulb_dew))
                    self.comfort_level = self.determine_comfort(toC(self.dew_temp_k))
            else:
                # no dew sensor configured -> estimate dewpoint from temp & humidity
                self.dew_temp_estimate_c = self.calculate_dewpoint(self.temp_out_k, self.hum_out)
                self.comfort_level = self.determine_comfort(self.dew_temp_estimate_c)

            # ensure required inputs for SI.state are present
            if self.temp_out_k is None or self.hum_out is None or self.pressure is None:
                logger.warning("Insufficient data for psychrometric calculation")
                self.S = None
            else:
                S = SI.state("DBT", self.temp_out_k, "RH", self.hum_out/100.0, self.pressure)
                self.S = S

            # existing logging and guards for S
            if self.S:
                logger.debug("SI Results ================================ START")
                logger.debug("The dry bulb temperature is " + str(self.S[0]))
                logger.debug("The specific enthalpy is " + str(self.S[1]))
                logger.debug("The relative humidity is " + str(self.S[2]))
                logger.debug("The specific volume is " + str(self.S[3]))
                logger.debug("The humidity ratio is " + str(self.S[4]))
                if self.S[5] is not None:
                    logger.debug("The wet bulb temperature is " + str(toC(self.S[5])))
                logger.debug("SI Results ================================ END")

                if self.S[5] is not None:
                    self._state = round(toC(self.S[5]), 2)
                else:
                    self._state = None
            else:
                self._state = None

            self.wet_bulb_stull = self.calculate_wb_stull()
            logger.debug("The wet bulb temperature (Stull formulat)) "+ str(self.wet_bulb_stull))

            self.heat_index = self.calculate_heat_index(self.temp_out_k, self.hum_out)
            logger.debug("Heat index "+ str(self.heat_index))

        except ValueError as e:
            logger.warning("Some input sensor values are still unavailable")

        except AttributeError:
            logger.error("Some entity does not exist or is spelled incorrectly. Did its component initialise correctly?")
        except Exception as e:
            logger.error(e)

    @property
    def available(self):
        return self._data_available()

    def _data_available(self):
        d = [
            self.outdoorHum, self.outdoorTemp, self.pressureSensor, self.dewSensor
        ]

        for s in d:
            if s:
                state = self.hass.states.get(s)
                if state is None:
                    return False
                if state.state == 'unknown':
                    return False
        return True

    def calculate_heat_index(self, temp_k, hum) -> float:
        """
        https://en.wikipedia.org/wiki/Heat_index
        The formula below approximates the heat index in degrees Fahrenheit, to within ±1.3 °F (0.7 °C). It is the result of a multivariate fit (temperature equal to or greater than 80 °F (27 °C) and relative humidity equal to or greater than 40%) to a model of the human body.[1][13] This equation reproduces the above NOAA National Weather Service table (except the values at 90 °F (32 °C) & 45%/70% relative humidity vary unrounded by less than ±1, respectively).
        Params: temperature in Kelvin, and humidity as a percentage
        """
        if temp_k and hum:
            T = KtoF(temp_k)
            R = hum
            if T > 80 and R > 40:
                hi = c1 + c2*T + c3*R + c4*T*R + c5*m.pow(T, 2) + c6*m.pow(R, 2) + c7*m.pow(T, 2)*R + c8*m.pow(R, 2)*T + c9*m.pow(T, 2)*m.pow(R, 2)
                return FtoC(hi)

        return None

    def calculate_dewpoint(self, temp_out_k, hum_out) -> float:
        if temp_out_k and hum_out:
            alpha = m.log(hum_out / 100) + (AA*toC(temp_out_k))/(BB+toC(temp_out_k))
            dp = (BB*alpha) / (AA - alpha)
            logger.debug("Dew Point Estimate (C): " + str(dp))
            return dp
        return None

    @property
    def icon(self):
        """Return the entity icon."""
        if self.comfort_level == 0:
            return "mdi:emoticon-excited-outline"
        if self.comfort_level == 1:
            return "mdi:emoticon-outline"
        if self.comfort_level == 2:
            return "mdi:emoticon-happy-outline"
        if self.comfort_level == 3:
            return "mdi:emoticon-neutral-outline"
        if self.comfort_level == 4:
            return "mdi:emoticon-sad-outline"
        return "mdi:circle-outline"

    def determine_comfort(self, dp):
        # use elif so a single correct bucket is chosen
        if dp is None:
            return None
        if dp > 21:
            comfort_level = 4
        elif dp > 18:
            comfort_level = 3
        elif dp > 16:
            comfort_level = 2
        elif dp > 10:
            comfort_level = 1
        else:
            comfort_level = 0

        return comfort_level

    def calculate_wb_stull(self) -> float:
        """
            Although many equations have been created over the years our calculator uses the Stull formula,
            which is accurate for relative humidities between 5% and 99% and temperatures between -20°C and 50°C.
            It loses its accuracy in situations where both moisture and heat are low in value, but even then the error range is only between -1°C to +0.65°C.
            Source: https://www.omnicalculator.com/physics/wet-bulb
        """
        if self.temp_out_k is None or self.hum_out is None:
            return None

        T = toC(self.temp_out_k)
        H = self.hum_out
        if H > 5 and H < 99 and T > -20 and T < 50:
            return T * m.atan(0.151977 * m.pow(H + 8.313659, 0.5)) + m.atan(T + H) - m.atan(H - 1.676331) + 0.00391838 * m.pow(H, 3/2) * m.atan(0.023101 * H) - 4.686035
        return None
