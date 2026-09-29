"""Aqshaqar Home Assistant integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    DEVICE_ID,
    DOMAIN,
    LEVELS,
    NAME,
    RESORT,
    WEBSITE_URL,
)
from .coordinator import AqshaqarCoordinator

PLATFORMS = ("sensor", "weather")
CARD_URL = "/aqshaqar/aqshaqar-card.js"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Aqshaqar frontend resources."""
    card_path = Path(__file__).parent / "www" / "aqshaqar-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), True)]
    )
    return True


async def _async_migrate_weather_entity_ids(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Migrate legacy entity IDs and integration-generated names."""
    registry = er.async_get(hass)

    for level_key, level in LEVELS.items():
        elevation = int(level["elevation_m"])
        old_entity_id = f"weather.{DOMAIN}_{level_key}_{level_key}"
        new_entity_id = f"weather.{DOMAIN}_{level_key}_{elevation}_m"

        registry_entry = registry.async_get(old_entity_id)
        if (
            not registry_entry
            or registry_entry.config_entry_id != entry.entry_id
        ):
            continue

        if registry.async_get(new_entity_id):
            continue

        registry.async_update_entity(
            old_entity_id,
            new_entity_id=new_entity_id,
        )

    for level_key, level in LEVELS.items():
        elevation = int(level["elevation_m"])
        level_name = str(level["name"])

        weather_entity_id = f"weather.{DOMAIN}_{level_key}_{elevation}_m"
        weather_entry = registry.async_get(weather_entity_id)
        if (
            weather_entry
            and weather_entry.config_entry_id == entry.entry_id
            and weather_entry.name in {
                level_name,
                f"{level_name} ({elevation} m)",
            }
        ):
            registry.async_update_entity(
                weather_entity_id,
                name=f"{elevation} {level_name}",
            )

        sensor_entity_id = f"sensor.{DOMAIN}_{level_key}_forecast"
        sensor_entry = registry.async_get(sensor_entity_id)
        if (
            sensor_entry
            and sensor_entry.config_entry_id == entry.entry_id
            and sensor_entry.name in {
                f"Aqshaqar Next snow at the {level_name}",
                f"Next snow at the {level_name}",
            }
        ):
            registry.async_update_entity(
                sensor_entity_id,
                name=f"Next snow at the {level_name}",
            )

    for level_key in LEVELS:
        old_entity_id = f"sensor.{DOMAIN}_{level_key}_snow_forecast"
        new_entity_id = f"sensor.{DOMAIN}_{level_key}_forecast"

        registry_entry = registry.async_get(old_entity_id)
        if (
            not registry_entry
            or registry_entry.config_entry_id != entry.entry_id
        ):
            continue

        if registry.async_get(new_entity_id):
            continue

        registry.async_update_entity(
            old_entity_id,
            new_entity_id=new_entity_id,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aqshaqar from a config entry."""
    coordinator = AqshaqarCoordinator(hass, entry.entry_id)
    await coordinator.async_initialize()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEVICE_ID)},
        manufacturer="Tenir Shymbulak",
        name=NAME,
        model=f"{RESORT} Snow Forecast",
        configuration_url=WEBSITE_URL,
    )
    coordinator.set_device_id(device.id)
    await _async_migrate_weather_entity_ids(hass, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when config entry options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Aqshaqar."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
