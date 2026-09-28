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

    @staticmethod
    def _next_snow_label(level: dict[str, Any] | None) -> str:
        """Format the explicit Snow-Forecast next-snow event."""
        if not level:
            return "—"

        event = level.get("next_snow") or {}
        amount = event.get("amount_cm")
        start = event.get("start")

        if amount is None or not start:
            return "—"

        try:
            dt = datetime.fromisoformat(str(start))
            return f"{amount:g} cm · {dt.day} {dt.strftime('%b')} {dt:%H:%M}"
        except ValueError:
            return f"{amount:g} cm"

    @staticmethod
    def _daily_snow(level: dict[str, Any] | None) -> dict[str, float | None]:
        """Return explicit daily snowfall totals from Snow-Forecast periods."""
        if not level:
            return {}

        grouped: dict[str, list[float]] = {}
        for period in level.get("forecast") or []:
            date_value = period.get("date")
            amount = period.get("snow_amount_cm")
            if not date_value or not isinstance(amount, (int, float)):
                continue
            grouped.setdefault(str(date_value), []).append(float(amount))

        return {
            date_value: round(sum(values), 1)
            for date_value, values in grouped.items()
        }

    @classmethod
    def _forecast_changes(
        cls,
        previous_levels: dict[str, Any],
        current_levels: dict[str, Any],
    ) -> list[str]:
        """Describe what changed between the previous and current forecast."""
        changes: list[str] = []

        for level_key, current in current_levels.items():
            previous = previous_levels.get(level_key)
            if previous is None:
                continue

            level_name = str(current.get("name") or level_key.title())

            old_next = cls._next_snow_label(previous)
            new_next = cls._next_snow_label(current)
            if old_next != new_next:
                changes.append(
                    f"{level_name} next snow: {old_next} → {new_next}"
                )

            old_daily = cls._daily_snow(previous)
            new_daily = cls._daily_snow(current)
            for date_value in sorted(set(old_daily) | set(new_daily)):
                old_amount = old_daily.get(date_value)
                new_amount = new_daily.get(date_value)
                if old_amount == new_amount:
                    continue

                old_label = (
                    f"{old_amount:g} cm" if old_amount is not None else "—"
                )
                new_label = (
                    f"{new_amount:g} cm" if new_amount is not None else "—"
                )

                try:
                    dt = datetime.fromisoformat(date_value)
                    date_label = f"{dt.day} {dt.strftime('%b')}"
                except ValueError:
                    date_label = date_value

                changes.append(
                    f"{level_name} {date_label}: {old_label} → {new_label}"
                )

                if len(changes) >= 8:
                    return changes

        return changes

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

        fetched_at_dt = datetime.now().astimezone()
        fetched_at = fetched_at_dt.isoformat()
        next_update_at = (
            fetched_at_dt + timedelta(seconds=next_update_seconds)
        ).isoformat()

        # Show only meaningful forecast changes in device Activity.
        # The previous successful forecast is available in self.data.
        changes = self._forecast_changes(previous_levels, successful_levels)
        if changes:
            self.hass.bus.async_fire(
                "logbook_entry",
                {
                    "name": NAME,
                    "message": "Forecast changed · " + " | ".join(changes),
                    "domain": "sensor",
                    "entity_id": "sensor.aqshaqar_forecast_update",
                },
            )

        return {
            "app": NAME,
            "resort": RESORT,
            "timezone": "Asia/Almaty",
            "fetched_at": fetched_at,
            "next_update_in_seconds": next_update_seconds,
            "next_update_at": next_update_at,
            "levels": levels,
            "errors": errors,
        }
