"""Aqshaqar snowfall sensors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_ID, DOMAIN, NAME, RESORT, WEBSITE_URL
from .coordinator import AqshaqarCoordinator


def _daily_snow(level: dict[str, Any]) -> list[dict[str, Any]]:
    """Return coordinator-normalized daily snowfall data."""
    value = level.get("daily_snow")
    return value if isinstance(value, list) else []


def _format_snow_summary(level: dict[str, Any]) -> str:
    """Return the explicit next-snow event, then the first daily amount."""
    next_snow = level.get("next_snow") or {}
    amount = next_snow.get("amount_cm")
    start = next_snow.get("start")

    if amount is not None and start:
        try:
            dt = datetime.fromisoformat(str(start))
            return f"❄ {amount:g} cm · {dt.day} {dt.strftime('%b')}, {dt:%H:%M}"
        except ValueError:
            return f"❄ {amount:g} cm"

    for day in _daily_snow(level):
        amount = day.get("snow_cm")
        if isinstance(amount, (int, float)) and amount > 0:
            try:
                dt = datetime.fromisoformat(str(day["date"]))
                label = dt.strftime("%-d %b")
            except ValueError:
                label = str(day["date"])
            return f"❄ {amount:g} cm · {label}"

    return "No snow expected"


class AqshaqarBaseEntity(CoordinatorEntity[AqshaqarCoordinator]):
    """Common entity implementation for Aqshaqar."""

    _attr_has_entity_name = True

    def _level_data(self, level_key: str) -> dict[str, Any]:
        """Return normalized level data."""
        return self.coordinator.data.get("levels", {}).get(level_key, {})

    @property
    def _device_info(self) -> DeviceInfo:
        """Return the shared Aqshaqar device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, DEVICE_ID)},
            name=NAME,
            manufacturer="Tenir Shymbulak",
            model=f"{RESORT} Snow Forecast",
            configuration_url=WEBSITE_URL,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up snowfall sensors and one shared diagnostic sensor."""
    coordinator: AqshaqarCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        AqshaqarSnowSensor(coordinator, level_key, level)
        for level_key, level in coordinator.data["levels"].items()
    ]
    entities.append(AqshaqarUpdateSensor(coordinator))
    async_add_entities(entities)


class AqshaqarSnowSensor(AqshaqarBaseEntity, SensorEntity):
    """One snowfall forecast sensor per Shymbulak elevation."""

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
        self._attr_suggested_object_id = f"{DOMAIN}_{level_key}_forecast"
        self._attr_name = f"Next snow at the {self._level_name}"
        self._attr_icon = "mdi:snowflake-variant"
        self._attr_device_info = self._device_info

    @property
    def native_value(self) -> str:
        """Return the next meaningful snowfall summary."""
        return _format_snow_summary(self._level_data(self._level_key))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose normalized forecast and source health."""
        level = self._level_data(self._level_key)
        return {
            "level": self._level_name,
            "elevation_m": self._elevation,
            "status": level.get("status"),
            "last_error": level.get("last_error"),
            "fetched_at": level.get("fetched_at"),
            "source_update_at": level.get("forecast_update_at"),
            "next_snow": level.get("next_snow"),
            "forecast": _daily_snow(level),
            "source": level.get("source"),
        }


class AqshaqarUpdateSensor(AqshaqarBaseEntity, SensorEntity):
    """One common next-update diagnostic sensor for all elevations."""

    def __init__(self, coordinator: AqshaqarCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_forecast_update"
        self._attr_suggested_object_id = f"{DOMAIN}_forecast_update"
        self._attr_name = "Forecast update"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:update"
        self._attr_device_info = self._device_info

    @property
    def native_value(self) -> datetime | None:
        """Return the shared next poll time."""
        value = self.coordinator.data.get("next_update_at")
        if not value:
            return None

        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh the diagnostic state."""
        self.async_write_ha_state()
