"""Aqshaqar Home Assistant integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import AqshaqarCoordinator

PLATFORMS = ("sensor", "weather")
CARD_URL = "/aqshaqar/aqshaqar-card.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Aqshaqar frontend resources."""
    card_path = Path(__file__).parent / "www" / "aqshaqar-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), True)]
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aqshaqar from a config entry."""
    coordinator = AqshaqarCoordinator(hass)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Remove legacy station devices created by older Aqshaqar releases.
    # Weather entities are now attached to the single Aqshaqar device.
    device_registry = dr.async_get(hass)
    for legacy_level in ("base", "mid", "top"):
        legacy_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, legacy_level), entry.entry_id
        )
        if legacy_device is not None:
            device_registry.async_remove_device(legacy_device.id)

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
