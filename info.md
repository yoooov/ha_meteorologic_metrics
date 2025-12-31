# Meteorologic Metrics — quick info

Purpose

- Compute psychrometric states of moist air based on ASHRAE 2009 Fundamentals, and expose a wet-bulb sensor suitable for History/Charts in Home Assistant.

What is exposed by default

- Wet Bulb (SI) sensor entity (HA sensor state) — this is recorded by Recorder and visible in History.

Optional extras (controlled by `expose_all`)

- DBT, WBT (SI), specific enthalpy, RH, specific volume, humidity ratio, Stull wet bulb estimate, dew point estimate

Configuration options

- YAML: add `expose_all: true` to create all sensors. Default is `false`.
- UI: the config flow and options flow provide the "Expose all extra sensors" toggle.

Where to put icons

- HACS repo logo: `logo.svg` at repo root
- Integration icon for HA: `custom_components/ha_meteorologic_metrics/icon.svg`

Debugging

- Enable debug logs via configuration.yaml (see README). After enabling, reproduce the issue and inspect `home-assistant.log` or the UI Logs.

Notes

- Entities are created with stable unique IDs (entry_id based or derived) so UI management (disable, rename) works correctly.
- The integration supports both YAML and UI config; when using UI the integration uses a config entry and options — when options change the entry is reloaded automatically.
- Default behaviour keeps the integration minimal (wet-bulb only). Enable extra metrics only if you need them to reduce entity clutter.

The state properties include:

* dry bulb temperature (DBT), 
* specific enthalpy (H), 
* relative humidity (RH), 
* specific volume (V), 
* humidity ratio (W), 
* and wet bulb temperature (WBT)
* wet bulb temperature (estimate from dewpoint depression - using [the 1/3 rule](https://www.theweatherprediction.com/habyhints/170/))

[Full Documentation](https://github.com/yoooov/ha_meteorologic_metrics)

# Example YAML snippet

```yaml
sensor:
  - platform: ha_meteorologic_metrics
    name: "Meteorologic Metrics"
    temp: sensor.outside_temp
    hum: sensor.outside_humidity
    pressure: sensor.outside_pressure
    expose_all: false
```