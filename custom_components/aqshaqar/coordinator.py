"""Data update coordinator for AQSHAQAR."""

from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    FALLBACK_RETRY_MINUTES,
    HEADERS,
    LEVELS,
    MIN_UPDATE_DELAY_SECONDS,
    NAME,
    PARTIAL_RETRY_MINUTES,
    REQUEST_TIMEOUT_SECONDS,
    RESORT,
    SNAPSHOT_STORE_VERSION,
)
from .snow_forecast import parse_level_html

_LOGGER = logging.getLogger(__package__)

FALLBACK_RETRY_SECONDS = FALLBACK_RETRY_MINUTES * 60
PARTIAL_RETRY_SECONDS = PARTIAL_RETRY_MINUTES * 60
BACKOFF_SECONDS = (120, 300, 600, 1200, 1800, 3600)


class AqshaqarCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate one poll for all Shymbulak elevations."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
    ) -> None:
        """Initialize the coordinator."""
        self._session = async_get_clientsession(hass)
        self._level_configs = LEVELS
        self._entry_id = entry_id
        self._device_id: str | None = None
        self._failure_count = 0
        self._last_change: list[str] = []
        self._snapshot_store = Store(
            hass,
            SNAPSHOT_STORE_VERSION,
            f"aqshaqar_{entry_id}_snow_snapshot",
        )
        self._previous_snapshot: dict[str, Any] | None = None

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{NAME} {RESORT}",
            update_interval=timedelta(seconds=FALLBACK_RETRY_SECONDS),
            always_update=True,
        )

    async def async_initialize(self) -> None:
        """Load the last successful snowfall snapshot from HA storage."""
        stored = await self._snapshot_store.async_load()
        if isinstance(stored, dict):
            self._previous_snapshot = stored

    def set_device_id(self, device_id: str) -> None:
        """Store the real Home Assistant device registry id for events."""
        self._device_id = device_id

    @property
    def consecutive_failures(self) -> int:
        """Return the current complete-fetch failure count."""
        return self._failure_count

    @property
    def last_changes(self) -> list[str]:
        """Return changes from the most recent successful refresh."""
        return list(self._last_change)

    async def _fetch_level(
        self,
        level_key: str,
        config: dict[str, object],
    ) -> dict[str, Any]:
        """Download and parse one elevation."""
        timeout = ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)

        try:
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

        except (ClientError, TimeoutError, UpdateFailed) as err:
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
        """Use the earliest source-reported update interval."""
        candidates = [
            int(level["update_in_seconds"])
            for level in levels.values()
            if isinstance(level.get("update_in_seconds"), (int, float))
        ]
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
    def _next_snow_key(level: dict[str, Any] | None) -> tuple[Any, Any]:
        """Return only the stable Next snow fields used for comparisons."""
        if not level:
            return (None, None)

        event = level.get("next_snow") or {}
        return (
            event.get("amount_cm"),
            event.get("start"),
        )

    @staticmethod
    def _daily_snow(level: dict[str, Any] | None) -> dict[str, float | None]:
        """Return explicit daily snowfall totals, including unknown days."""
        if not level:
            return {}

        daily = level.get("daily_snow")
        if isinstance(daily, list):
            return {
                str(item["date"]): item.get("snow_cm")
                for item in daily
                if isinstance(item, dict) and item.get("date")
            }

        result: dict[str, list[float]] = {}
        dates: list[str] = []

        for period in level.get("forecast") or []:
            date_value = period.get("date")
            if not date_value:
                continue

            date_value = str(date_value)
            if date_value not in dates:
                dates.append(date_value)

            amount = period.get("snow_amount_cm")
            if isinstance(amount, (int, float)):
                result.setdefault(date_value, []).append(float(amount))

        return {
            date_value: (
                round(sum(result[date_value]), 1)
                if date_value in result
                else None
            )
            for date_value in dates
        }

    @classmethod
    def _snow_snapshot(
        cls,
        levels: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist Next snow and daily snowfall data for change detection."""
        return {
            "levels": {
                key: {
                    "next_snow": {
                        "amount_cm": cls._next_snow_key(level)[0],
                        "start": cls._next_snow_key(level)[1],
                    },
                    "daily_snow": cls._daily_snow(level),
                }
                for key, level in levels.items()
            }
        }

    @classmethod
    def _next_snow_changes(
        cls,
        previous_levels: dict[str, Any],
        current_levels: dict[str, Any],
    ) -> list[str]:
        """Report only changes to the explicit Next snow event."""
        changes: list[str] = []

        for level_key, current in current_levels.items():
            previous = previous_levels.get(level_key)
            if previous is None:
                continue

            if cls._next_snow_key(previous) == cls._next_snow_key(current):
                continue

            level_name = str(current.get("name") or level_key.title())
            elevation = int(current["elevation_m"])

            changes.append(
                f"{level_name} · {elevation} m — "
                f"~~{cls._next_snow_label(previous)}~~ → "
                f"{cls._next_snow_label(current)}"
            )

        return changes

    @classmethod
    def _forecast_changes(
        cls,
        previous_levels: dict[str, Any],
        current_levels: dict[str, Any],
    ) -> list[str]:
        """Describe all meaningful snowfall forecast changes."""
        changes: list[str] = []

        for level_key, current in current_levels.items():
            previous = previous_levels.get(level_key)
            if previous is None:
                continue

            level_name = str(current.get("name") or level_key.title())
            elevation = int(current["elevation_m"])

            if cls._next_snow_key(previous) != cls._next_snow_key(current):
                changes.append(
                    f"{level_name} · {elevation} m — "
                    f"Next snow: {cls._next_snow_label(previous)} → "
                    f"{cls._next_snow_label(current)}"
                )

            old_daily = cls._daily_snow(previous)
            new_daily = cls._daily_snow(current)

            for date_value in sorted(set(old_daily) & set(new_daily)):
                old_amount = old_daily[date_value]
                new_amount = new_daily[date_value]
                if old_amount == new_amount:
                    continue
                if old_amount is None and new_amount is None:
                    continue

                old_label = f"{old_amount:g} cm" if old_amount is not None else "—"
                new_label = f"{new_amount:g} cm" if new_amount is not None else "—"

                try:
                    dt = datetime.fromisoformat(date_value)
                    date_label = f"{dt.day} {dt.strftime('%b')}"
                except ValueError:
                    date_label = date_value

                changes.append(
                    f"{level_name} · {elevation} m — "
                    f"Forecast · {date_label}: {old_label} → {new_label}"
                )

                if len(changes) >= 12:
                    return changes

            for date_value in sorted(set(new_daily) - set(old_daily)):
                amount = new_daily[date_value]
                if not isinstance(amount, (int, float)) or amount <= 0:
                    continue

                try:
                    dt = datetime.fromisoformat(date_value)
                    date_label = f"{dt.day} {dt.strftime('%b')}"
                except ValueError:
                    date_label = date_value

                changes.append(
                    f"{level_name} · {elevation} m — "
                    f"Forecast · {date_label}: — → {amount:g} cm"
                )
                if len(changes) >= 12:
                    return changes

        return changes

    @classmethod
    def _event_data(
        cls,
        previous_snapshot: dict[str, Any] | None,
        current_levels: dict[str, Any],
        changes: list[str],
    ) -> dict[str, Any]:
        """Build a stable event payload for automations and notifications."""
        current_snapshot = cls._snow_snapshot(current_levels)
        return {
            "resort": RESORT,
            "changes": changes,
            "previous": previous_snapshot or {},
            "current": current_snapshot,
        }

    async def _persist_snapshot(
        self,
        snapshot: dict[str, Any],
    ) -> None:
        """Persist the stable snowfall snapshot."""
        self._previous_snapshot = deepcopy(snapshot)
        try:
            await self._snapshot_store.async_save(snapshot)
        except (HomeAssistantError, OSError, TypeError, ValueError) as err:
            _LOGGER.warning("Unable to persist Aqshaqar snow snapshot: %s", err)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all levels and schedule the next source-reported poll."""
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
            self._level_configs.items(),
            results,
            strict=True,
        ):
            if isinstance(result, Exception):
                errors[level_key] = str(result)
                if level_key in previous_levels:
                    stale = deepcopy(previous_levels[level_key])
                    stale["status"] = "stale"
                    stale["last_error"] = str(result)
                    levels[level_key] = stale
                continue

            result["status"] = "ok"
            result["last_error"] = None
            levels[level_key] = result
            successful_levels[level_key] = result

        if not successful_levels:
            self._failure_count += 1
            delay = BACKOFF_SECONDS[
                min(self._failure_count - 1, len(BACKOFF_SECONDS) - 1)
            ]
            self.update_interval = timedelta(seconds=delay)
            details = "; ".join(
                f"{key}: {value}" for key, value in errors.items()
            ) or "all forecast levels failed"
            raise UpdateFailed(details, retry_after=delay)

        self._failure_count = 0

        source_delay = self._next_update_seconds(successful_levels)
        if errors:
            next_update_seconds = min(source_delay, PARTIAL_RETRY_SECONDS)
        else:
            next_update_seconds = source_delay

        self.update_interval = timedelta(seconds=next_update_seconds)

        fetched_at_dt = datetime.now().astimezone()
        fetched_at = fetched_at_dt.isoformat()
        next_update_at = (
            fetched_at_dt + timedelta(seconds=next_update_seconds)
        ).isoformat()

        previous_snapshot = deepcopy(self._previous_snapshot or {})
        current_snapshot = self._snow_snapshot(levels)
        changes = self._forecast_changes(
            previous_snapshot.get("levels", {}),
            levels,
        )
        next_snow_changes = self._next_snow_changes(
            previous_snapshot.get("levels", {}),
            levels,
        )
        self._last_change = changes

        await self._persist_snapshot(current_snapshot)

        if changes:
            event_data = self._event_data(
                previous_snapshot,
                levels,
                changes,
            )
            event_data["previous"] = previous_snapshot
            event_data["current"] = current_snapshot

            if self._device_id:
                event_data["device_id"] = self._device_id

            self.hass.bus.async_fire(
                "aqshaqar_forecast_changed",
                event_data,
            )
            self.hass.bus.async_fire(
                "logbook_entry",
                {
                    "name": NAME,
                    "message": "Forecast changed · " + " | ".join(changes),
                    "domain": "sensor",
                    "entity_id": "sensor.aqshaqar_forecast_update",
                },
            )

        if next_snow_changes:
            next_event_data = {
                "resort": RESORT,
                "changes": next_snow_changes,
                "previous": previous_snapshot,
                "current": current_snapshot,
            }
            if self._device_id:
                next_event_data["device_id"] = self._device_id

            self.hass.bus.async_fire(
                "aqshaqar_next_snow_changed",
                next_event_data,
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
            "consecutive_failures": self._failure_count,
            "last_changes": changes,
            "next_snow_changes": next_snow_changes,
            "device_id": self._device_id,
        }

    def diagnostics(self) -> dict[str, Any]:
        """Return safe diagnostics for HA support."""
        levels = (self.data or {}).get("levels", {})
        return {
            "app": NAME,
            "resort": RESORT,
            "entry_id": self._entry_id,
            "device_id": self._device_id,
            "next_update_at": (self.data or {}).get("next_update_at"),
            "next_update_in_seconds": (self.data or {}).get(
                "next_update_in_seconds"
            ),
            "fetched_at": (self.data or {}).get("fetched_at"),
            "consecutive_failures": self._failure_count,
            "last_changes": self._last_change,
            "next_snow_changes": (self.data or {}).get("next_snow_changes", []),
            "snapshot_loaded": self._previous_snapshot is not None,
            "levels": {
                key: {
                    "elevation_m": level.get("elevation_m"),
                    "source": level.get("source"),
                    "status": level.get("status"),
                    "last_error": level.get("last_error"),
                    "fetched_at": level.get("fetched_at"),
                    "issued_at": level.get("issued_at"),
                    "forecast_update_at": level.get("forecast_update_at"),
                    "schedule_source": level.get("schedule_source"),
                    "next_snow": level.get("next_snow"),
                    "validation": level.get("validation"),
                    "duration_seconds": level.get("duration_seconds"),
                }
                for key, level in levels.items()
            },
        }
