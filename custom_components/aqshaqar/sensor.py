"""Aqshaqar snowfall sensors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_ID, DOMAIN, NAME, RESORT, WEBSITE_URL
from .coordinator import AqshaqarCoordinator


def _snow_forecast_by_day(level: dict[str, Any]) -> list[dict[str, Any]]:
    """Group explicit Snow-Forecast snowfall amounts by calendar day."""
    grouped: dict[str, list[dict[str, Any]]] = {}

    for period in level.get("forecast") or []:
        date_value = period.get("date")
        if not date_value:
            continue
        grouped.setdefault(str(date_value), []).append(period)

    result: list[dict[str, Any]] = []
    for date_value, periods in grouped.items():
        snow_values = [
            float(period["snow_amount_cm"])
            for period in periods
            if isinstance(period.get("snow_amount_cm"), (int, float))
        ]
        result.append(
            {
                "date": date_value,
                "snow_cm": round(sum(snow_values), 1) if snow_values else None,
                "snow_expected": any(
                    period.get("snow_expected") is True for period in periods
                ),
            }
        )

    return result


def _format_snow_summary(level: dict[str, Any]) -> str:
    """Return the next known snowfall amount and date."""
    for day in _snow_forecast_by_day(level):
        amount = day.get("snow_cm")
        if isinstance(amount, (int, float)) and amount > 0:
            try:
                dt = datetime.fromisoformat(str(day["date"]))
                label = dt.strftime("%-d %b")
            except ValueError:
                label = str(day["date"])
            return f"❄ {amount:g} cm · {label}"

        if day.get("snow_expected") is True:
            try:
                dt = datetime.fromisoformat(str(day["date"]))
                label = dt.strftime("%-d %b")
            except ValueError:
                label = str(day["date"])
            return f"❄ Snow expected · {label}"

    return "No snowfall in forecast"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up only snowfall and one common diagnostic update sensor."""
    coordinator: AqshaqarCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Remove legacy Aqshaqar sensors so the device stays focused on snowfall.
    registry = async_get_entity_registry(hass)
    legacy_prefixes = (
        "_conditions",
        "_temp_max_c",
        "_temp_min_c",
        "_chill_c",
        "_humidity_pct",
        "_wind_speed_kmh",
        "_rain_mm",
        "_snow_amount_cm",
        "_freezing_level_m",
        "_next_snow",
        "_forecast_update_at",
    )
    for entity in list(registry.entities.values()):
        if (
            entity.config_entry_id == entry.entry_id
            and entity.platform == DOMAIN
            and any(entity.unique_id == f"{DOMAIN}_{level}{suffix}"
                    for level in ("base", "mid", "top")
                    for suffix in legacy_prefixes)
        ):
            registry.async_remove(entity.entity_id)

    entities: list[SensorEntity] = [
        AqshaqarSnowSensor(coordinator, level_key, level)
        for level_key, level in coordinator.data["levels"].items()
    ]
    entities.append(AqshaqarUpdateSensor(coordinator))

    async_add_entities(entities)


class AqshaqarSnowSensor(
    CoordinatorEntity[AqshaqarCoordinator], SensorEntity
):
    """One snowfall forecast sensor per Shymbulak elevation."""

    _attr_has_entity_name = True

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

        self._attr_unique_id = f"{DOMAIN}_{level_key}_snow_forecast"
        self._attr_suggested_object_id = f"{level_key}_snow_forecast"
        self._attr_name = f"{self._level_name} Snow forecast"
        self._attr_icon = "mdi:snowflake-variant"
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
    def native_value(self) -> str:
        return _format_snow_summary(self._level_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        level = self._level_data
        return {
            "level": self._level_name,
            "elevation_m": self._elevation,
            "next_snow": level.get("next_snow"),
            "forecast_update_at": self.coordinator.data.get("next_update_at"),
            "forecast": _snow_forecast_by_day(level),
            "source": level.get("source"),
        }


class AqshaqarUpdateSensor(
    CoordinatorEntity[AqshaqarCoordinator], SensorEntity
):
    """One common next-update diagnostic sensor for all elevations."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AqshaqarCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_forecast_update"
        self._attr_name = "Forecast update"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = "diagnostic"
        self._attr_icon = "mdi:update"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DEVICE_ID)},
            name=NAME,
            manufacturer="Tenir Shymbulak",
            model=f"{RESORT} Snow Forecast",
            configuration_url=WEBSITE_URL,
        )

    @property
    def native_value(self) -> datetime | None:
        value = self.coordinator.data.get("next_update_at")
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None


    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh the state from coordinator data."""
        self.async_write_ha_state()
