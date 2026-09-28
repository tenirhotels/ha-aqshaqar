"""Aqshaqar sensors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_ID, DOMAIN, NAME, RESORT, WEBSITE_URL
from .coordinator import AqshaqarCoordinator


SENSOR_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "conditions",
        "name": "Conditions",
        "icon": "mdi:weather-partly-cloudy",
    },
    {
        "key": "temp_max_c",
        "name": "Temperature high",
        "icon": "mdi:thermometer-high",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "temp_min_c",
        "name": "Temperature low",
        "icon": "mdi:thermometer-low",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "chill_c",
        "name": "Wind chill",
        "icon": "mdi:snowflake-thermometer",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "humidity_pct",
        "name": "Humidity",
        "icon": "mdi:water-percent",
        "unit": "%",
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "wind_speed_kmh",
        "name": "Wind speed",
        "icon": "mdi:weather-windy",
        "unit": "km/h",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "rain_mm",
        "name": "Rain",
        "icon": "mdi:weather-rainy",
        "unit": "mm",
        "device_class": SensorDeviceClass.PRECIPITATION,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "snow_amount_cm",
        "name": "Snow amount",
        "icon": "mdi:weather-snowy",
        "unit": "cm",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "freezing_level_m",
        "name": "Freezing level",
        "icon": "mdi:altimeter",
        "unit": "m",
        "state_class": SensorStateClass.MEASUREMENT,
        "display_precision": 0,
    },
    {
        "key": "next_snow",
        "name": "Next snow",
        "icon": "mdi:snowflake",
        "unit": "cm",
    },
    {
        "key": "forecast_update_at",
        "name": "Forecast update",
        "icon": "mdi:update",
        "device_class": SensorDeviceClass.TIMESTAMP,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    {
        "key": "snow_forecast",
        "name": "Forecast",
        "icon": "mdi:snowflake-variant",
    },
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Aqshaqar sensors."""
    coordinator: AqshaqarCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[AqshaqarSensor] = []

    for level_key, level in coordinator.data["levels"].items():
        for definition in SENSOR_DEFINITIONS:
            entities.append(
                AqshaqarSensor(coordinator, level_key, level, definition)
            )

    async_add_entities(entities)


class AqshaqarSensor(CoordinatorEntity[AqshaqarCoordinator], SensorEntity):
    """One Aqshaqar sensor for one Shymbulak elevation."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AqshaqarCoordinator,
        level_key: str,
        level: dict[str, Any],
        definition: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._level_key = level_key
        self._definition = definition
        self._level_name = str(level["name"])
        self._elevation = int(level["elevation_m"])

        sensor_key = definition["key"]
        self._attr_unique_id = f"{DOMAIN}_{level_key}_{sensor_key}"
        self._attr_suggested_object_id = f"{level_key}_{sensor_key}"
        self._attr_name = f"{self._level_name} {definition['name']}"
        self._attr_icon = definition.get("icon")
        self._attr_native_unit_of_measurement = definition.get("unit")
        self._attr_device_class = definition.get("device_class")
        self._attr_state_class = definition.get("state_class")
        self._attr_entity_category = definition.get("entity_category")
        self._attr_suggested_display_precision = definition.get("display_precision")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DEVICE_ID)},
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

    @staticmethod
    def _format_next_snow(next_snow: dict[str, Any] | None) -> str:
        """Return amount plus exact next-snow date/time, or a dash."""
        if not next_snow:
            return "—"

        amount = next_snow.get("amount_cm")
        start = next_snow.get("start")
        if amount is None or not start:
            return "—"

        try:
            dt = datetime.fromisoformat(start)
            return f"{amount:g} cm · {dt.day} {dt.strftime('%b')}, {dt:%H:%M}"
        except (TypeError, ValueError):
            return f"{amount:g} cm"

    @staticmethod
    def _snow_forecast_by_day(level: dict[str, Any]) -> list[dict[str, Any]]:
        """Group the raw Snow-Forecast periods into daily snowfall totals."""
        grouped: dict[str, list[dict[str, Any]]] = {}

        for period in level.get("forecast") or []:
            date_value = period.get("date")
            if not date_value:
                continue
            grouped.setdefault(str(date_value), []).append(period)

        result: list[dict[str, Any]] = []
        for date_value, periods in grouped.items():
            numeric_snow = [
                float(period["snow_amount_cm"])
                for period in periods
                if isinstance(period.get("snow_amount_cm"), (int, float))
            ]
            numeric_rain = [
                float(period["rain_mm"])
                for period in periods
                if isinstance(period.get("rain_mm"), (int, float))
            ]
            highs = [
                float(period["temp_max_c"])
                for period in periods
                if isinstance(period.get("temp_max_c"), (int, float))
            ]
            lows = [
                float(period["temp_min_c"])
                for period in periods
                if isinstance(period.get("temp_min_c"), (int, float))
            ]

            result.append(
                {
                    "date": date_value,
                    "weekday": __import__("datetime").date.fromisoformat(date_value).strftime("%a"),
                    "snow_cm": round(sum(numeric_snow), 1) if numeric_snow else None,
                    "snow_expected": any(
                        period.get("snow_expected") is True for period in periods
                    ),
                    "rain_mm": round(sum(numeric_rain), 1) if numeric_rain else None,
                    "temp_high_c": max(highs) if highs else None,
                    "temp_low_c": min(lows) if lows else None,
                }
            )

        return result

    @property
    def native_value(self):
        key = self._definition["key"]
        current = self._current

        if key == "conditions":
            return current.get("phrase") if current else None
        if key == "wind_speed_kmh":
            return ((current or {}).get("wind") or {}).get("speed_kmh")
        if key == "next_snow":
            return self._format_next_snow(self._level_data.get("next_snow"))
        if key == "snow_forecast":
            daily = self._snow_forecast_by_day(self._level_data)
            first = daily[0] if daily else None
            return first.get("snow_cm") if first and first.get("snow_cm") is not None else None
        if key == "forecast_update_at":
            value = self._level_data.get("forecast_update_at")
            if not value:
                return None
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return (current or {}).get(key)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._level_key in self.coordinator.data.get("levels", {})
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        level = self._level_data
        current = self._current
        key = self._definition["key"]
        if not level:
            return None

        base_attributes = {
            "level": self._level_name,
            "elevation_m": self._elevation,
            "date": (current or {}).get("date"),
            "period": (current or {}).get("period"),
        }

        if key == "conditions":
            return {
                **base_attributes,
                "weather": (current or {}).get("weather"),
                "snow_expected": (current or {}).get("snow_expected"),
                "issued_at": level.get("issued_at"),
                "forecast_update_at": level.get("forecast_update_at"),
                "next_snow": level.get("next_snow"),
                "forecast": level.get("forecast"),
            }

        if key == "wind_speed_kmh":
            return {
                **base_attributes,
                "direction": ((current or {}).get("wind") or {}).get("direction"),
            }

        if key == "next_snow":
            next_snow = level.get("next_snow") or {}
            return {
                **base_attributes,
                "amount_cm": next_snow.get("amount_cm"),
                "start": next_snow.get("start"),
                "description": next_snow.get("description"),
            }

        return base_attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh the state from coordinator data."""
        self.async_write_ha_state()
