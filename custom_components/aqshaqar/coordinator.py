"""Data update coordinator for AQSHAQAR."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    FALLBACK_RETRY_MINUTES,
    HEADERS,
    LEVELS,
    MIN_UPDATE_DELAY_SECONDS,
    NAME,
    REQUEST_TIMEOUT_SECONDS,
    RESORT,
)
from .snow_forecast import parse_level_html

_LOGGER = logging.getLogger(__package__)
FALLBACK_RETRY_SECONDS = FALLBACK_RETRY_MINUTES * 60


class AqshaqarCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate one poll for all Shymbulak elevations."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        self._session = async_get_clientsession(hass)
        self._level_configs = LEVELS
        initial_interval = timedelta(seconds=FALLBACK_RETRY_SECONDS)

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{NAME} {RESORT}",
            update_interval=initial_interval,
        )

    async def _fetch_level(
        self, level_key: str, config: dict[str, object]
    ) -> dict[str, Any]:
        """Download and parse one elevation."""
        try:
            timeout = ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
            async with self._session.get(
                str(config["url"]),
                headers=HEADERS,
                timeout=timeout,
                allow_redirects=True,
            ) as response:
                if response.status >= 400:
                    body = (await response.text())[:300]
                    raise UpdateFailed(
                        f"{level_key}: HTTP {response.status}: {body}"
                    )
                html = await response.text()
        except (ClientError, asyncio.TimeoutError, UpdateFailed) as err:
            raise UpdateFailed(f"{level_key}: {err}") from err

        try:
            return await self.hass.async_add_executor_job(
                parse_level_html,
                level_key,
                config,
                html,
            )
        except Exception as err:
            raise UpdateFailed(f"{level_key}: parser error: {err}") from err

    @staticmethod
    def _next_update_seconds(levels: dict[str, Any]) -> int:
        """Return the earliest next forecast update reported by Snow-Forecast."""
        candidates: list[int] = []

        for level in levels.values():
            value = level.get("update_in_seconds")
            if isinstance(value, (int, float)):
                candidates.append(max(0, int(value)))

        if not candidates:
            return FALLBACK_RETRY_SECONDS

        return max(MIN_UPDATE_DELAY_SECONDS, min(candidates))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all levels and schedule the next poll from Snow-Forecast data."""
        tasks = [
            self._fetch_level(level_key, config)
            for level_key, config in self._level_configs.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        previous_levels = (self.data or {}).get("levels", {})
        levels: dict[str, Any] = {}
        errors: dict[str, str] = {}
        successful_levels: dict[str, Any] = {}

        for (level_key, _config), result in zip(
            self._level_configs.items(), results, strict=True
        ):
            if isinstance(result, Exception):
                errors[level_key] = str(result)
                if level_key in previous_levels:
                    levels[level_key] = previous_levels[level_key]
                continue

            levels[level_key] = result
            successful_levels[level_key] = result

        if not successful_levels:
            details = "; ".join(
                f"{key}: {value}" for key, value in errors.items()
            ) or "all forecast levels failed"
            raise UpdateFailed(details, retry_after=FALLBACK_RETRY_SECONDS)

        next_update_seconds = self._next_update_seconds(successful_levels)
        self.update_interval = timedelta(seconds=next_update_seconds)

        fetched_at = datetime.now().astimezone().isoformat()
        return {
            "app": NAME,
            "resort": RESORT,
            "timezone": "Asia/Almaty",
            "fetched_at": fetched_at,
            "next_update_in_seconds": next_update_seconds,
            "levels": levels,
            "errors": errors,
        }
