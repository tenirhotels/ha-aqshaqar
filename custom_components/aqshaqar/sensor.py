"""AQSHAQAR sensors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
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
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.MEASUREMENT,
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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up AQSHAQAR sensors."""
    coordinator: AqshaqarCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[AqshaqarSensor] = []

    for level_key, level in coordinator.data["levels"].items():
        for definition in SENSOR_DEFINITIONS:
            entities.append(
                AqshaqarSensor(coordinator, level_key, level, definition)
            )

    async_add_entities(entities)


class AqshaqarSensor(CoordinatorEntity[AqshaqarCoordinator], SensorEntity):
    """One AQSHAQAR sensor bound to one elevation."""

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
        self._elevation = int(level["elevation_m"])
        self._attr_unique_id = f"aqshaqar_{level_key}_{definition['key']}"
        self._attr_name = definition["name"]
        self._attr_icon = definition.get("icon")
        self._attr_native_unit_of_measurement = definition.get("unit")
        self._attr_device_class = definition.get("device_class")
        self._attr_state_class = definition.get("state_class")
        self._attr_entity_category = definition.get("entity_category")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, level_key)},
            name=f"AQSHAQAR — Shymbulak {level['name']}",
            manufacturer=NAME,
            model=f"Shymbulak {self._elevation} m",
            configuration_url=str(level["source"]),
        )

    @property
    def _level_data(self) -> dict[str, Any]:
        return self.coordinator.data["levels"].get(self._level_key, {})

    @property
    def _current(self) -> dict[str, Any] | None:
        forecast = self._level_data.get("forecast") or []
        return forecast[0] if forecast else None

    @property
    def native_value(self):
        key = self._definition["key"]
        current = self._current

        if key == "conditions":
            return current.get("phrase") if current else None
        if key == "wind_speed_kmh":
            return ((current or {}).get("wind") or {}).get("speed_kmh")
        if key == "next_snow":
            return (self._level_data.get("next_snow") or {}).get("amount_cm")
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
        return super().available and self._level_key in self.coordinator.data.get("levels", {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        level = self._level_data
        current = self._current
        key = self._definition["key"]
        if not level:
            return None

        if key == "conditions":
            return {
                "elevation_m": level.get("elevation_m"),
                "date": (current or {}).get("date"),
                "period": (current or {}).get("period"),
                "weather": (current or {}).get("weather"),
                "snow_expected": (current or {}).get("snow_expected"),
                "issued_at": level.get("issued_at"),
                "forecast_update_at": level.get("forecast_update_at"),
                "next_snow": level.get("next_snow"),
                "forecast": level.get("forecast"),
            }

        if key == "wind_speed_kmh":
            return {
                "direction": ((current or {}).get("wind") or {}).get("direction"),
                "date": (current or {}).get("date"),
                "period": (current or {}).get("period"),
            }

        if key == "next_snow":
            next_snow = level.get("next_snow") or {}
            return {
                "start": next_snow.get("start"),
                "description": next_snow.get("description"),
            }

        return {
            "elevation_m": level.get("elevation_m"),
            "date": (current or {}).get("date"),
            "period": (current or {}).get("period"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh the state from coordinator data."""
        self.async_write_ha_state()
