# HA Meteorologic Metrics (Home Assistant integration)

This component calculates psychrometric states of moist air using ASHRAE 2009 Fundamentals formulations (via the psypy package). Atmospheric pressure and humidity must be provided to compute the remaining properties.

Core features
- UI config flow (Config Entry) + YAML support
- Option to expose extra SI sensors (default: only Wet Bulb sensor is created)
- Entities created with unique_id so they appear in the entity registry and are manageable in the UI
- Optional HACS support (include hacs.json and logo file in releases)

Entities and attributes

- Primary entity (default): Wet bulb temperature (SI) — recorded by Recorder and available in History
- Optional extra sensors (enabled by `expose_all: true` or UI toggle):
  - SI dry bulb temp C (DBT)
  - SI wet bulb temp C (WBT)
  - SI specific enthalpy
  - SI relative humidity
  - SI specific volume
  - SI humidity ratio
  - wet bulb temp (stull) C (Stull estimate)
  - dew point estimate C (if no dew sensor configured)

Attribute names (on the original combined sensor and for reference)
- SI dry bulb temp C
- SI wet bulb temp C
- SI specific enthalpy
- SI relative humidity
- SI specific volume
- SI humidity ratio
- wet bulb temp (dew estimate) C
- wet bulb temp (stull) C
- heat index
- comfort level
- dew point (if configured dew sensor exists)

## Note on Dew Point Calculation

If the `dew` sensor is not supplied, the component calculates an estimate for dew point (°C) using the Magnus-Tetens formula. This produces accurate results (with an uncertainty of 0.35°C) for temperatures ranging from -45°C to 60°C.

Source: https://www.omnicalculator.com/physics/dew-point

## Note on Heat Index (Feels like temp)

Attribute name: `heat index`

> The formula below approximates the heat index in degrees Fahrenheit, to within ±1.3 °F (0.7 °C). It is the result of a multivariate fit (temperature equal to or greater than 80 °F (27 °C) and relative humidity equal to or greater than 40%) to a model of the human body. This equation reproduces the above NOAA National Weather Service table (except the values at 90 °F (32 °C) & 45%/70% relative humidity vary unrounded by less than ±1, respectively).
Source: https://en.wikipedia.org/wiki/Heat_index

The heat index represents the apparent temperature (feels like). It will only be calculated for temperatures above 27C and humidty over 40%.

## Wet Bulb Temperature Estimations

### ASHRAE 2009 Fundamentals Calculation

Attibute name: `SI wet bulb temp C`

Psychrometric states of moist air are calculated using ASHRAE 2009 Fundamentals formulations implemented in the [`psypy` package](https://pypi.org/project/psypy/)

### Dewpoint Depression estimate

Attribute name: `wet bulb temp (dew estimate) C`

This estimate using [the 1/3 rule](https://www.theweatherprediction.com/habyhints/170/)
The 1/3 rule works quite well for temperatures between -1.1C and 15.5C. For warmer temperatures than 15.5C, the cooling is between about 1/3 and 1/2 the dewpoint depression.

### Stull Estimate
Attribute name: `wet bulb temp stull estimate C`
> Although many equations have been created over the years our calculator uses the Stull formula, which is accurate for relative humidities between 5% and 99% and temperatures between -20°C and 50°C. It loses its accuracy in situations where both moisture and heat are low in value, but even then the error range is only between -1°C to +0.65°C.
Source: https://www.omnicalculator.com/physics/wet-bulb

## Installation / files

- Place integration under custom_components/ha_meteorologic_metrics/
- Provide logo.svg at repo root for HACS and icon.svg inside the integration folder for the HA UI
- manifest.json must include "config_flow": true and correct "domain"
- Add hacs.json in repo root for HACS detection (if publishing)

## Configuration

YAML configuration example
- By default only the wet-bulb SI sensor is created.
- To enable all additional SI sensors set `expose_all: true`.

```yaml
sensor:
  - platform: ha_meteorologic_metrics
    name: "Meteorologic Metrics"      # optional, use if you want to use mulitple instances
    temp: sensor.outside_temp         # entity_id for temperature sensor (celsius prefered)
    hum: sensor.outside_humidity      # entity_id for humidity sensor (percent)
    pressure: sensor.outside_pressure # entity_id for pressure (hPa == mbar == Pa * 100)
    dew: sensor.outside_dewpoint      # optional dew point sensor (°C), 
                                      # required if you want WBT estimated with dewpoint depression
    expose_all: false                 # optional, default false (only wet bulb sensor)
```

## Notes about UI setup

- Use Integrations → Add Integration → Meteorologic Metrics and pick sensors using the entity selector (autocomplete).
- The config flow offers an "Expose all extra sensors" toggle which mirrors expose_all YAML option.
- Options can be edited after creation (Options flow) and the entry will be reloaded when options change.

## History & Recorder

- The primary wet-bulb SI sensor is a proper HA sensor state (not only an attribute) so it will be recorded by Recorder and available in History/Charts.
- Optional additional sensors are created as HA sensors when expose_all is enabled.

## Debug logging

- To enable debug logging for troubleshooting, add to configuration.yaml:

```yaml
logger:
  default: info
  logs:
    custom_components.ha_meteorologic_metrics: debug
    custom_components.ha_meteorologic_metrics.sensor: debug
    psypy: debug
```

## Migration & YAML -> UI

- The config flow supports import from YAML (async_step_import). You can convert YAML setup to a UI config entry from Integrations if desired.

## HACS packaging

Include hacs.json at repo root and logo.svg in the release archive. The integration icon should be placed under custom_components/ha_meteorologic_metrics/icon.svg (no manifest reference required).

## Support & docs

Full code and usage examples: https://github.com/yoooov/ha_meteorologic_metrics

## TODO

### Attribute naming rule

* dry bulb temperature
* specific enthalpy
* relative humidity
* specific volume
* humidity ratio
* heat index
* dew point (if `dew` sensor not supplied)
* wet bulb temperature
* wet bulb temperature (estimation using dewpoint depression)
* wet bulb temperature (estimation using stull formula)