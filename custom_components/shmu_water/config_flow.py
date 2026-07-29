from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    selector,
    SelectSelector,
    SelectSelectorConfig,
    SelectOptionDict,
)
import voluptuous as vol
import logging

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, DEFAULT_STATION_ID
from .api import SHMUWaterAPI

_LOGGER = logging.getLogger(__name__)


class SHMUWaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SHMU Water Levels."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._stations: list[dict] = []
        self._fetch_error: str | None = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Check for duplicate station
            await self.async_set_unique_id(
                f"{DOMAIN}_{user_input['station_id']}"
            )
            self._abort_if_unique_id_configured()

            # Fetch data once to validate the station works
            try:
                api = SHMUWaterAPI(
                    user_input["station_id"],
                    verify_ssl=user_input.get("verify_ssl", True),
                )
                station_data = await api.fetch_station_data()
            except Exception as err:
                _LOGGER.error("Failed to fetch station data: %s", err)
                errors["station_id"] = "cannot_connect"
                # Still need stations list for re-display
                await self._load_stations()
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._build_schema(),
                    errors=errors,
                )

            # Build title from station data
            station_name = station_data.get("station_name", user_input["station_id"])
            river = station_data.get("river", "")

            return self.async_create_entry(
                title=f"SHMU Water: {station_name} ({river})"
                if river
                else f"SHMU Water: {station_name}",
                data={
                    "station_id": user_input["station_id"],
                    "station_name": station_name,
                    "river": river,
                    "scan_interval": user_input.get(
                        "scan_interval", DEFAULT_SCAN_INTERVAL
                    ),
                    "verify_ssl": user_input.get("verify_ssl", True),
                },
            )

        # First load: fetch station list
        await self._load_stations()
        if self._fetch_error:
            errors["base"] = self._fetch_error

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(),
            errors=errors,
        )

    async def _load_stations(self):
        """Fetch station list from SHMU."""
        if self._stations:
            return
        try:
            api = SHMUWaterAPI(DEFAULT_STATION_ID, verify_ssl=True)
            self._stations = await api.fetch_stations()
            self._fetch_error = None
        except Exception as err:
            _LOGGER.warning("Failed to fetch station list: %s", err)
            self._fetch_error = "cannot_connect"
            self._stations = []

    def _build_schema(self) -> vol.Schema:
        """Build the config flow schema."""
        if self._stations:
            station_options = [
                SelectOptionDict(
                    value=s["id"],
                    label=f"{s['name']} — {s['river']} ({'📊' if s['has_forecast'] else ''})",
                )
                for s in self._stations
            ]
            schema = vol.Schema(
                {
                    vol.Required("station_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=station_options,
                            mode="dropdown",
                            sort=False,
                            custom_value=True,
                        )
                    ),
                    vol.Optional(
                        "scan_interval", default=DEFAULT_SCAN_INTERVAL
                    ): int,
                    vol.Optional("verify_ssl", default=True): bool,
                }
            )
        else:
            # Fallback: text input if station list not available
            schema = vol.Schema(
                {
                    vol.Required(
                        "station_id", default=DEFAULT_STATION_ID
                    ): str,
                    vol.Optional(
                        "scan_interval", default=DEFAULT_SCAN_INTERVAL
                    ): int,
                    vol.Optional("verify_ssl", default=True): bool,
                }
            )

        return schema

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SHMUWaterOptionsFlow(config_entry)


class SHMUWaterOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for SHMU Water Levels."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=self.config_entry.data.get(
                            "scan_interval", DEFAULT_SCAN_INTERVAL
                        ),
                    ): int,
                    vol.Optional(
                        "verify_ssl",
                        default=self.config_entry.data.get("verify_ssl", True),
                    ): bool,
                }
            ),
        )
