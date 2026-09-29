"""Diagnostics for Aqshaqar."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import AqshaqarCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return safe diagnostics for the Aqshaqar config entry."""
    coordinator: AqshaqarCoordinator = hass.data["aqshaqar"][entry.entry_id]
    return coordinator.diagnostics()
