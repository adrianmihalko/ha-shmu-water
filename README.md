# ha-shmu-water

## SHMU Water Levels Integration for Home Assistant

This integration fetches water level (hydrological) data from the [Slovenský hydrometeorologický ústav (SHMU)](https://www.shmu.sk/) and provides sensors for monitoring river and water body levels across Slovakia. It covers **409 monitoring stations** (vodomerné stanice), with flood forecast data available for ~97 major stations.

All data is provided by SHMU's public water monitoring portal.

## Installation

1. **Add this repository to HACS**:
   - Go to HACS > Integrations > Custom Repositories.
   - Add `https://github.com/adrianmihalko/ha-shmu-water` as a custom repository.
   - Install the "SHMU Water Levels" integration.

2. **Configure the integration**:
   - Go to Configuration > Integrations > Add Integration > SHMU Water Levels.
   - Select your station from the dropdown (searchable, 409 stations available).
   - Tap `Submit` to add the station (you can add multiple stations).

## Configuration Options

| Option        | Description                                                                 |
|---------------|-----------------------------------------------------------------------------|
| Station       | Select a water level monitoring station from the list (name — river).       |
| Scan Interval | How often (in seconds) the data should be updated (default: 300 seconds).    |
| Verify SSL    | Verify SHMU SSL certificates (recommended).                                  |

- You can browse all stations at [SHMU Water Levels](https://www.shmu.sk/sk/?page=1&id=hydro_vod_all).

## Sensors

The integration creates a device with the following sensors:

- **Water Level** (cm) — current water level measurement with rich attributes
- **Water Trend** — rising, falling, or stable
- **Water Forecast** (cm) — predicted water level (available for ~30 stations with forecast data)

### Water Level Attributes

| Attribute            | Description                                                    |
|----------------------|----------------------------------------------------------------|
| `measurement_time`   | Timestamp of the last measurement                              |
| `trend`              | stable / rising / falling                                      |
| `flood_degree`       | 0 = normal, 1 = 1st degree, 2 = 2nd degree, 3 = 3rd degree   |
| `flood_status`       | Human-readable flood status                                    |
| `flood_thresholds`   | Threshold values for each flood degree                         |
| `station_id`         | SHMU station ID                                                |
| `station_name`       | Station name                                                   |
| `river`              | River/water body name                                          |
| `forecast_available` | Whether forecast data is available for this station            |
| `forecast_time`      | Timestamp of the forecast value (if available)                 |

## Flood Activity Degrees

The flood degree is calculated based on SHMU's official thresholds for each station:

- **Degree 0** — Normal (below 1st degree threshold)
- **Degree 1** — Alert (yellow) — water level approaching flood stage
- **Degree 2** — Warning (orange) — flood activity declared
- **Degree 3** — Emergency (red) — severe flooding

These thresholds vary per station and are sourced directly from SHMU's data.

## Troubleshooting

- Ensure your station ID is correct (visible in attributes after setup).
- Check the logs for errors if sensors are unavailable.
- Some stations may have delayed or missing data.
- Not all stations have forecast data — the forecast sensor will show as unavailable for those.
- Water level values can be negative for stations where the zero reference is above the riverbed (common on large rivers like the Danube).

## Related Integrations

- [ha-shmu](https://github.com/3DRIK/ha-shmu) — Meteorological data (temperature, humidity, pressure, wind, etc.) from SHMU
