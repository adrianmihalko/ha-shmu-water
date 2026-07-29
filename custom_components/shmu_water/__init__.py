from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import logging
from datetime import timedelta

from .const import DOMAIN
from .api import SHMUWaterAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SHMU Water Levels from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = SHMUWaterDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, ["sensor"]
    ):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class SHMUWaterDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching SHMU water level data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the coordinator."""
        self._entry = entry
        self._station_id = entry.data.get("station_id", "")
        self._verify_ssl = entry.data.get("verify_ssl", True)
        self._api = SHMUWaterAPI(self._station_id, self._verify_ssl)

        # Station metadata (set after first fetch)
        self.station_name = entry.data.get("station_name", "")
        self.river = entry.data.get("river", "")

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.data.get("scan_interval", 300)
            ),
        )

    async def _async_update_data(self):
        """Fetch data from SHMU."""
        try:
            data = await self._api.fetch_station_data()

            # Fetch water temperature from station page (best-effort)
            temp_data = await self._api.fetch_water_temperature()
            data["water_temperature_c"] = temp_data.get("water_temperature_c")
            data["temperature_time"] = temp_data.get("temperature_time")

            # Update stored metadata on first successful fetch
            if not self.station_name and data.get("station_name"):
                self.station_name = data["station_name"]
            if not self.river and data.get("river"):
                self.river = data["river"]

            return data
        except Exception as err:
            raise UpdateFailed(
                f"Error communicating with SHMU: {err}"
            )
