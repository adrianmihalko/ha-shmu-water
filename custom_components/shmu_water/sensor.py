from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from datetime import datetime

from .const import DOMAIN

# Trend icons for each state
TREND_ICONS = {
    "stable": "mdi:trending-neutral",
    "rising": "mdi:trending-up",
    "falling": "mdi:trending-down",
    "unknown": "mdi:help-circle",
}

# Flood degree display names
FLOOD_NAMES = {
    0: "Normal",
    1: "1st Degree",
    2: "2nd Degree",
    3: "3rd Degree",
}


class SHMUWaterLevelSensor(CoordinatorEntity, SensorEntity):
    """Main sensor showing current water level in cm."""

    def __init__(self, coordinator, entry_id: str):
        """Initialize the water level sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_water_level_{entry_id}"
        self._attr_name = "SHMU Water Level"
        self._attr_native_unit_of_measurement = "cm"
        self._attr_icon = "mdi:waves"
        self._attr_state_class = SensorStateClass.MEASUREMENT

        # Device info
        station_id = coordinator.config_entry.data.get("station_id", "")
        station_name = coordinator.config_entry.data.get("station_name", "")
        river = coordinator.config_entry.data.get("river", "")
        device_name = f"SHMU Water: {station_name}" if station_name else f"SHMU Water Station {station_id}"
        if river:
            device_name += f" ({river})"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=device_name,
            manufacturer="Slovenský hydrometeorologický ústav",
            model="Water Level Station",
            sw_version="1.0",
            configuration_url=f"https://www.shmu.sk/sk/?page=1&id=hydro_vod_all&station_id={station_id}",
        )

    @property
    def native_value(self):
        """Return the water level in cm."""
        return self.coordinator.data.get("water_level_cm")

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        data = self.coordinator.data
        if not data:
            return {}

        attrs = {
            "measurement_time": data.get("measurement_time"),
            "trend": data.get("trend"),
            "flood_degree": data.get("flood_degree"),
            "flood_status": FLOOD_NAMES.get(data.get("flood_degree", 0), "Unknown"),
            "station_id": self.coordinator.config_entry.data.get("station_id"),
            "station_name": data.get("station_name"),
            "river": data.get("river"),
            "max_y": data.get("max_y"),
            "forecast_available": data.get("has_forecast", False),
        }

        if data.get("base_serie_last"):
            attrs["last_measurement_ts"] = datetime.fromtimestamp(
                data["base_serie_last"][0] / 1000.0
            ).isoformat()

        if data.get("plot_bands"):
            attrs["flood_thresholds"] = data["plot_bands"]

        if data.get("forecast_time"):
            attrs["forecast_time"] = data["forecast_time"].isoformat()

        return attrs


class SHMUWaterTrendSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the water level trend: stable, rising, or falling."""

    def __init__(self, coordinator, entry_id: str):
        """Initialize the trend sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_water_trend_{entry_id}"
        self._attr_name = "SHMU Water Trend"
        self._attr_state_class = None

        station_id = coordinator.config_entry.data.get("station_id", "")
        station_name = coordinator.config_entry.data.get("station_name", "")
        river = coordinator.config_entry.data.get("river", "")
        device_name = f"SHMU Water: {station_name}" if station_name else f"SHMU Water Station {station_id}"
        if river:
            device_name += f" ({river})"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=device_name,
            manufacturer="Slovenský hydrometeorologický ústav",
            model="Water Level Station",
            sw_version="1.0",
        )

    @property
    def native_value(self):
        """Return the trend."""
        return self.coordinator.data.get("trend", "unknown")

    @property
    def icon(self):
        """Return dynamic icon based on trend."""
        trend = self.coordinator.data.get("trend", "unknown")
        return TREND_ICONS.get(trend, TREND_ICONS["unknown"])


class SHMUWaterForecastSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the forecasted water level in cm."""

    def __init__(self, coordinator, entry_id: str):
        """Initialize the forecast sensor."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_water_forecast_{entry_id}"
        self._attr_name = "SHMU Water Forecast"
        self._attr_native_unit_of_measurement = "cm"
        self._attr_icon = "mdi:waves-arrow-up"
        self._attr_state_class = SensorStateClass.MEASUREMENT

        station_id = coordinator.config_entry.data.get("station_id", "")
        station_name = coordinator.config_entry.data.get("station_name", "")
        river = coordinator.config_entry.data.get("river", "")
        device_name = f"SHMU Water: {station_name}" if station_name else f"SHMU Water Station {station_id}"
        if river:
            device_name += f" ({river})"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=device_name,
            manufacturer="Slovenský hydrometeorologický ústav",
            model="Water Level Station",
            sw_version="1.0",
        )

    @property
    def native_value(self):
        """Return the forecast water level in cm."""
        return self.coordinator.data.get("forecast_level_cm")

    @property
    def extra_state_attributes(self):
        """Return forecast attributes."""
        data = self.coordinator.data
        if not data:
            return {}

        attrs = {}
        if data.get("forecast_time"):
            attrs["forecast_time"] = data["forecast_time"].isoformat()
        return attrs

    @property
    def available(self) -> bool:
        """Return True if forecast data is available."""
        if not super().available:
            return False
        return self.coordinator.data.get("has_forecast", False)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the SHMU water sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    entry_id = config_entry.entry_id

    sensors = [
        SHMUWaterLevelSensor(coordinator, entry_id),
        SHMUWaterTrendSensor(coordinator, entry_id),
    ]

    # Always add forecast sensor — it shows as unavailable if no forecast
    sensors.append(SHMUWaterForecastSensor(coordinator, entry_id))

    async_add_entities(sensors)
