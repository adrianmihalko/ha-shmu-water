import aiohttp
import async_timeout
import logging
import re
import json
import time
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://www.shmu.sk"
STATION_PAGE_URL = f"{BASE_URL}/sk/?page=1&id=hydro_vod_all"


class SHMUWaterAPI:
    """Class to handle SHMU water level data retrieval."""

    def __init__(self, station_id: str, verify_ssl: bool = True):
        """Initialize the API client."""
        self._station_id = station_id
        self._verify_ssl = verify_ssl

    async def fetch_stations(self) -> list[dict]:
        """Fetch list of all water level stations.

        Returns list of dicts with keys: id, name, river, has_forecast.
        """
        url = f"{BASE_URL}/popups/hydro/vodne_toky/hydro_stations_geojson.php?ac={int(time.time())}"

        try:
            connector = aiohttp.TCPConnector(ssl=self._verify_ssl)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with async_timeout.timeout(15):
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise Exception(
                                f"Error fetching stations: HTTP {response.status}"
                            )
                        data = await response.json()

            stations = []
            for feature in data.get("features", []):
                props = feature.get("properties", {})
                name = props.get("name", "")
                # Name format: "StationName - RiverName"
                parts = name.split(" - ", 1)
                station_name = parts[0].strip() if parts else name
                river = parts[1].strip() if len(parts) > 1 else ""

                stations.append({
                    "id": feature.get("id", ""),
                    "name": station_name,
                    "river": river,
                    "full_name": name,
                    "has_forecast": props.get("has_forecast", 0) == 1,
                })

            # Sort by name for display
            stations.sort(key=lambda s: (s["name"].lower(), s["river"].lower()))
            return stations

        except aiohttp.ClientError as err:
            raise Exception(f"Communication error fetching stations: {err}")
        except Exception as err:
            raise Exception(f"Unexpected error fetching stations: {err}")

    async def fetch_station_data(self) -> dict:
        """Fetch current water level data and forecast for the station.

        Returns dict with:
            station_name, river, measurement_time, water_level_cm, trend,
            trend_raw, flood_degree, max_y, has_forecast,
            forecast_level_cm, forecast_time, base_serie_last, plot_bands
        """
        url = f"{BASE_URL}/popups/hydro/vodne_toky/tooltip.php?id={self._station_id}"

        try:
            connector = aiohttp.TCPConnector(ssl=self._verify_ssl)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with async_timeout.timeout(15):
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise Exception(
                                f"Error fetching station data: HTTP {response.status}"
                            )
                        html = await response.text()

            return self._parse_tooltip_response(html)

        except aiohttp.ClientError as err:
            raise Exception(f"Communication error fetching station data: {err}")
        except Exception as err:
            raise Exception(f"Unexpected error fetching station data: {err}")

    def _parse_tooltip_response(self, html: str) -> dict:
        """Parse the tooltip.php HTML/JS response."""
        result = {
            "station_name": "",
            "river": "",
            "measurement_time": None,
            "water_level_cm": None,
            "trend": "unknown",
            "trend_raw": "",
            "flood_degree": 0,
            "max_y": None,
            "has_forecast": False,
            "forecast_level_cm": None,
            "forecast_time": None,
            "base_serie_last": None,
            "plot_bands": [],
        }

        # --- Parse HTML portion for current values ---
        # Station name
        name_match = re.search(r"Stanica:\s*<strong>([^<]+)</strong>", html)
        if name_match:
            result["station_name"] = name_match.group(1).strip()

        # River
        river_match = re.search(r"Tok:\s*<strong>([^<]+)</strong>", html)
        if river_match:
            result["river"] = river_match.group(1).strip()

        # Measurement time
        time_match = re.search(
            r"(?:Čas merania|Čas merania):\s*<strong>([^<]+)</strong>", html
        )
        if time_match:
            time_str = time_match.group(1).strip()
            try:
                result["measurement_time"] = datetime.strptime(
                    time_str, "%d.%m.%Y %H:%M"
                )
            except ValueError:
                result["measurement_time"] = time_str

        # Water level
        level_match = re.search(
            r"(?:Vodný stav|Vodný stav):\s*<strong>(-?\d+)\s*cm</strong>", html
        )
        if level_match:
            result["water_level_cm"] = int(level_match.group(1))

        # Trend from image alt text
        trend_match = re.search(
            r'<img[^>]*alt="([^"]*hladina[^"]*|Hladina[^"]*)"[^>]*>', html
        )
        if trend_match:
            alt = trend_match.group(1).strip()
            result["trend_raw"] = alt
            if "ustálená" in alt or "ustálená" in alt:
                result["trend"] = "stable"
            elif "stúpa" in alt or "stúpa" in alt:
                result["trend"] = "rising"
            elif "klesá" in alt or "klesá" in alt:
                result["trend"] = "falling"

        # --- Parse JS portion for time series and thresholds ---
        # max_y
        max_y_match = re.search(r"var\s+max_y\s*=\s*(\d+)", html)
        if max_y_match:
            result["max_y"] = int(max_y_match.group(1))

        # base_serie data (uses bracket counting for nested arrays)
        base_points = self._extract_js_series(html, "base_serie")
        if base_points:
            result["base_serie_last"] = base_points[-1]
            # Use the last base_serie point if HTML didn't have water level
            if result["water_level_cm"] is None:
                result["water_level_cm"] = base_points[-1][1]

        # forecast_serie data
        forecast_points = self._extract_js_series(html, "forecast_serie")
        if forecast_points:
            result["has_forecast"] = True
            result["forecast_level_cm"] = forecast_points[-1][1]
            result["forecast_time"] = datetime.fromtimestamp(
                forecast_points[-1][0] / 1000.0
            )

        # plotBands for flood degree - brackets may be nested, use counter
        plot_bands = self._extract_plot_bands(html)
        if plot_bands:
            result["plot_bands"] = plot_bands

        # Calculate flood degree
        if result["water_level_cm"] is not None and result["plot_bands"]:
            result["flood_degree"] = self._calculate_flood_degree(
                result["water_level_cm"], result["plot_bands"]
            )

        return result

    def _extract_js_series(self, html: str, var_name: str) -> list:
        """Extract a Highcharts data series by variable name using bracket counting.

        Handles nested arrays like: data:[[ts,val],[ts,val],...]
        """
        # Find start of data array: var name = { ..., data: [
        pattern = rf"var\s+{var_name}\s*=\s*\{{[^}}]*data:\s*\["
        m = re.search(pattern, html, re.DOTALL)
        if not m:
            return []

        # Position of the outer opening '['
        bracket_start = m.end() - 1

        # Bracket counting to find matching ']'
        depth = 0
        i = bracket_start
        while i < len(html):
            ch = html[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    break
            i += 1

        if depth != 0:
            return []

        data_str = html[bracket_start : i + 1]
        points = []
        pairs = re.findall(r"\[(\d+),(-?\d+)\]", data_str)
        for ts, val in pairs:
            points.append([int(ts), int(val)])
        return points

    def _extract_plot_bands(self, html: str) -> list:
        """Extract plotBands using bracket counting to handle nested objects."""
        # Find plotBands:[
        m = re.search(r"plotBands:\s*\[", html)
        if not m:
            return []

        bracket_start = m.end() - 1

        # Bracket counting
        depth = 0
        i = bracket_start
        while i < len(html):
            ch = html[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    break
            i += 1

        if depth != 0:
            return []

        bands_str = html[bracket_start : i + 1]

        # Extract {from, to} pairs — SHMU data has "to" before "from"
        bands = []
        band_matches = re.findall(
            r"\{[^}]*?to:\s*(\d+)[^}]*?from:\s*(\d+)[^}]*?\}", bands_str
        )
        for to_val, from_val in band_matches:
            bands.append({"from": int(from_val), "to": int(to_val)})

        # Sort by 'from' ascending (lower thresholds first)
        bands.sort(key=lambda b: b["from"])
        return bands

    async def fetch_water_temperature(self) -> dict:
        """Fetch water temperature from the station detail page.

        Returns dict with:
            water_temperature_c: float or None
            temperature_time: str or None (measurement timestamp)
        """
        url = f"{STATION_PAGE_URL}&station_id={self._station_id}"

        try:
            connector = aiohttp.TCPConnector(ssl=self._verify_ssl)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with async_timeout.timeout(15):
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise Exception(
                                f"Error fetching station page: HTTP {response.status}"
                            )
                        html = await response.text()

            # Extract cells with headers — first match is most recent
            temp_match = re.search(
                r'<td[^>]*headers="h_teplota_vody"[^>]*>([^<]+)</td>', html
            )
            time_match = re.search(
                r'<td[^>]*headers="h_datum_cas"[^>]*>([^<]+)</td>', html
            )

            result = {
                "water_temperature_c": None,
                "temperature_time": None,
            }

            if temp_match:
                try:
                    result["water_temperature_c"] = float(temp_match.group(1).strip())
                except (ValueError, TypeError):
                    pass

            if time_match:
                result["temperature_time"] = time_match.group(1).strip()

            return result

        except aiohttp.ClientError as err:
            _LOGGER.debug("Communication error fetching water temperature: %s", err)
            return {"water_temperature_c": None, "temperature_time": None}
        except Exception as err:
            _LOGGER.debug("Unexpected error fetching water temperature: %s", err)
            return {"water_temperature_c": None, "temperature_time": None}

    def _calculate_flood_degree(self, water_level: int, bands: list) -> int:
        """Calculate flood activity degree based on water level and plot bands.

        Degrees: 0 = normal, 1 = yellow, 2 = orange, 3 = red
        """
        degree = 0
        for i, band in enumerate(bands):
            if water_level >= band["from"] and water_level < band["to"]:
                degree = i + 1
                break
        return degree
