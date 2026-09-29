"""Aqshaqar weather entities."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, RESORT, TIMEZONE, WEBSITE_URL
from .coordinator import AqshaqarCoordinator

LOCAL_TZ = ZoneInfo(TIMEZONE)


def _condition_from_period(period: dict[str, Any]) -> str:
    """Map Snow-Forecast wording to a Home Assistant weather condition."""
    phrase = " ".join(
        value for value in (period.get("phrase"), period.get("weather")) if value
    ).lower()

    snow = "snow" in phrase or period.get("snow_expected") is True
    rain = (
        "rain" in phrase
        or "shwr" in phrase
        or "shower" in phrase
        or (isinstance(period.get("rain_mm"), (int, float)) and period["rain_mm"] > 0)
    )
    thunder = "thunder" in phrase or "storm" in phrase

    if thunder and (rain or snow):
        return "lightning-rainy"
    if snow and rain:
        return "snowy-rainy"
    if snow:
        return "snowy"
    if rain:
        return "rainy"
    if "fog" in phrase or "mist" in phrase:
        return "fog"
    if "partly" in phrase:
        return "partlycloudy"
    if "sunny" in phrase or "clear" in phrase:
        return "sunny"
    if "wind" in phrase:
        return "windy"
    if "cloud" in phrase or "overcast" in phrase:
        return "cloudy"
    return "cloudy"


def _day_condition(periods: list[dict[str, Any]]) -> str:
    """Pick the most relevant condition for a calendar day."""
    priority = {
        "lightning-rainy": 7,
        "snowy-rainy": 6,
        "snowy": 5,
        "rainy": 4,
        "partlycloudy": 3,
        "cloudy": 2,
        "windy": 1,
        "sunny": 0,
        "fog": 2,
    }

    best_condition = "cloudy"
    best_score = -1

    for index, period in enumerate(periods):
        condition = _condition_from_period(period)
        score = priority.get(condition, 1)
        period_name = str(period.get("period") or "").lower()
        if "am" in period_name or "pm" in period_name:
            score += 1

        # Prefer earlier daylight periods only when scores tie.
        score_key = score * 100 - index
        if score_key > best_score:
            best_score = score_key
            best_condition = condition

    return best_condition


def _day_datetime(date_value: str) -> str:
    """Return an RFC3339 UTC timestamp representing the local calendar day."""
    local_dt = datetime.combine(
        datetime.fromisoformat(date_value).date(),
        time(hour=12),
        tzinfo=LOCAL_TZ,
    )
    return local_dt.astimezone(UTC).isoformat()


class AqshaqarWeather(CoordinatorEntity[AqshaqarCoordinator], WeatherEntity):
    """Weather entity for one Shymbulak elevation."""

    _attr_has_entity_name = False
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = "km/h"
    _attr_native_precipitation_unit = "mm"
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    def __init__(
        self,
        coordinator: AqshaqarCoordinator,
        level_key: str,
        level: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._level_key = level_key
        self._level_name = str(level["name"])
        self._elevation = int(level["elevation_m"])

        self._attr_unique_id = f"{DOMAIN}_{level_key}_weather"
        self._attr_name = f"{self._level_name} ({self._elevation} m)"
        self._attr_suggested_object_id = (
            f"{DOMAIN}_{level_key}_{self._elevation}_m"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "shymbulak")},
            name=NAME,
            manufacturer="Tenir Shymbulak",
            model=f"{RESORT} Snow Forecast",
            configuration_url=WEBSITE_URL,
        )

    @property
    def _level_data(self) -> dict[str, Any]:
        return self.coordinator.data["levels"].get(self._level_key, {})

    @property
    def _current(self) -> dict[str, Any] | None:
        forecast = self._level_data.get("forecast") or []
        return forecast[0] if forecast else None

    @property
    def native_temperature(self) -> float | None:
        current = self._current
        value = (current or {}).get("temp_max_c")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def condition(self) -> str | None:
        current = self._current
        return _condition_from_period(current) if current else None

    @property
    def humidity(self) -> float | None:
        value = (self._current or {}).get("humidity_pct")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def native_apparent_temperature(self) -> float | None:
        value = (self._current or {}).get("chill_c")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def native_wind_speed(self) -> float | None:
        value = ((self._current or {}).get("wind") or {}).get("speed_kmh")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def wind_bearing(self) -> float | str | None:
        return ((self._current or {}).get("wind") or {}).get("direction")

    @property
    def native_precipitation(self) -> float | None:
        value = (self._current or {}).get("rain_mm")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        level = self._level_data
        return {
            "elevation_m": level.get("elevation_m"),
            "issued_at": level.get("issued_at"),
            "forecast_update_at": level.get("forecast_update_at"),
            "next_snow": level.get("next_snow"),
            "status": level.get("status"),
            "last_error": level.get("last_error"),
            "fetched_at": level.get("fetched_at"),
            "daily_snow": level.get("daily_snow"),
            "source": level.get("source"),
        }

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return one Home Assistant daily forecast item per calendar date."""
        periods = self._level_data.get("forecast") or []
        if not periods:
            return None

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for period in periods:
            date_value = period.get("date")
            if date_value:
                grouped[str(date_value)].append(period)

        forecasts: list[Forecast] = []

        for date_value, day_periods in grouped.items():
            high_values = [
                float(p["temp_max_c"])
                for p in day_periods
                if isinstance(p.get("temp_max_c"), (int, float))
            ]
            low_values = [
                float(p["temp_min_c"])
                for p in day_periods
                if isinstance(p.get("temp_min_c"), (int, float))
            ]
            humidity_values = [
                float(p["humidity_pct"])
                for p in day_periods
                if isinstance(p.get("humidity_pct"), (int, float))
            ]
            rain_values = [
                float(p["rain_mm"])
                for p in day_periods
                if isinstance(p.get("rain_mm"), (int, float))
            ]
            wind_values = [
                float((p.get("wind") or {}).get("speed_kmh"))
                for p in day_periods
                if isinstance((p.get("wind") or {}).get("speed_kmh"), (int, float))
            ]

            strongest_wind = max(
                day_periods,
                key=lambda p: (
                    (p.get("wind") or {}).get("speed_kmh")
                    if isinstance((p.get("wind") or {}).get("speed_kmh"), (int, float))
                    else -1
                ),
            )

            forecasts.append(
                {
                    "datetime": _day_datetime(date_value),
                    "condition": _day_condition(day_periods),
                    "native_temperature": max(high_values) if high_values else None,
                    "native_templow": min(low_values) if low_values else None,
                    "humidity": (
                        sum(humidity_values) / len(humidity_values)
                        if humidity_values
                        else None
                    ),
                    "native_precipitation": (
                        sum(rain_values) if rain_values else None
                    ),
                    "native_wind_speed": max(wind_values) if wind_values else None,
                    "wind_bearing": (
                        (strongest_wind.get("wind") or {}).get("direction")
                    ),
                }
            )

        return forecasts


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Aqshaqar weather entities."""
    coordinator: AqshaqarCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        AqshaqarWeather(coordinator, level_key, level)
        for level_key, level in coordinator.data["levels"].items()
    ]
    async_add_entities(entities)
