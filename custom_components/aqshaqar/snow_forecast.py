"""Robust Snow-Forecast HTML parser used by Aqshaqar."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .const import TIMEZONE

TZ = ZoneInfo(TIMEZONE)

BLOCK_MARKERS = (
    "verify you are human",
    "captcha",
    "access denied",
    "attention required",
)


def parse_number(value: Any) -> int | float | None:
    """Extract a number from text or a data attribute."""
    if value is None:
        return None

    value = str(value).strip()
    if value in ("", "-", "—", "–"):
        return None

    value = value.replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        return None

    number = float(match.group())
    return int(number) if number.is_integer() else number


def cell_text(cell: Any) -> str | None:
    """Return normalized visible text from a table cell."""
    if cell is None:
        return None
    value = " ".join(cell.stripped_strings)
    return value or None


def unix_to_local(timestamp: int | None) -> str | None:
    """Convert a Unix timestamp to the source timezone."""
    if timestamp is None:
        return None
    return datetime.fromtimestamp(int(timestamp), TZ).isoformat()


def get_row(soup: BeautifulSoup, row_name: str):
    """Return a forecast row by Snow-Forecast's data-row attribute."""
    return soup.select_one(f'tr[data-row="{row_name}"]')


def get_cells(soup: BeautifulSoup, row_name: str) -> list:
    """Return forecast cells for a row."""
    row = get_row(soup, row_name)
    if not row:
        return []
    return row.select("td.forecast-table__cell")


def values_from_data_value(
    soup: BeautifulSoup,
    row_name: str,
    selector: str | None = None,
) -> list[int | float | None]:
    """Parse numeric data-value cells."""
    result: list[int | float | None] = []

    for cell in get_cells(soup, row_name):
        node = cell.select_one(selector) if selector else cell
        if node is None:
            result.append(None)
            continue

        value = node.get("data-value")
        if value is None:
            value = cell_text(node)
        result.append(parse_number(value))

    return result


def values_from_text(
    soup: BeautifulSoup,
    row_name: str,
) -> list[int | float | None]:
    """Parse numeric text cells."""
    return [parse_number(cell_text(cell)) for cell in get_cells(soup, row_name)]


def parse_dates(soup: BeautifulSoup) -> list[str]:
    """Expand Snow-Forecast day cells according to their colspan."""
    row = get_row(soup, "days")
    if not row:
        return []

    result: list[str] = []
    for cell in row.select("td.forecast-table__cell"):
        date_value = cell.get("data-date")
        if not date_value:
            continue

        try:
            colspan = int(cell.get("colspan", "1"))
        except (TypeError, ValueError):
            colspan = 1

        result.extend([str(date_value)] * max(1, colspan))

    return result


def parse_periods(soup: BeautifulSoup) -> list[str | None]:
    """Parse the actual forecast time-column labels."""
    return [cell_text(cell) for cell in get_cells(soup, "time")]


def parse_phrases(soup: BeautifulSoup) -> list[str | None]:
    """Parse condition phrases."""
    result: list[str | None] = []
    row = get_row(soup, "phrases")
    if not row:
        return result

    for cell in row.select("td.forecast-table__cell"):
        node = cell.select_one("[class*='forecast-table__phrase']")
        result.append(cell_text(node or cell))

    return result


def parse_weather(soup: BeautifulSoup) -> list[str | None]:
    """Parse weather icon alt text."""
    result: list[str | None] = []
    row = get_row(soup, "weather")
    if not row:
        return result

    for cell in row.select("td.forecast-table__cell"):
        icon = cell.select_one("img.weather-icon")
        result.append(icon.get("alt") if icon else None)

    return result


def parse_wind(soup: BeautifulSoup) -> list[dict[str, Any] | None]:
    """Parse wind speed and direction."""
    result: list[dict[str, Any] | None] = []
    row = get_row(soup, "wind")
    if not row:
        return result

    for cell in row.select("td.forecast-table__cell"):
        icon = cell.select_one(".wind-icon")
        if not icon:
            result.append(None)
            continue

        speed = parse_number(icon.get("data-speed"))
        direction_node = icon.select_one(".wind-icon__tooltip")
        direction = cell_text(direction_node) if direction_node else None
        result.append({"speed_kmh": speed, "direction": direction})

    return result


def parse_next_snow(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Parse Snow-Forecast's explicit 'Next snow in Shymbulak' event."""
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        if not raw:
            continue

        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue

        objects = data if isinstance(data, list) else [data]
        for obj in objects:
            if not isinstance(obj, dict):
                continue

            accepted = obj.get("acceptedAnswer")
            if not isinstance(accepted, dict):
                continue

            event = accepted.get("about")
            if not isinstance(event, dict):
                continue
            if event.get("@type") != "Event":
                continue
            if event.get("name") != "Next snow in Shymbulak:":
                continue

            amount = None
            additional = event.get("additionalProperty")

            properties = (
                additional
                if isinstance(additional, list)
                else [additional]
                if isinstance(additional, dict)
                else []
            )

            for prop in properties:
                if (
                    isinstance(prop, dict)
                    and prop.get("name") == "snowfall"
                ):
                    amount = parse_number(prop.get("value"))
                    break

            return {
                "amount_cm": amount,
                "start": event.get("startDate"),
                "description": event.get("description"),
            }

    # Conservative fallback for a layout that exposes the value in HTML.
    node = soup.select_one(".next-snow")
    if node:
        amount_node = node.select_one(".next-snow__snow")
        amount = parse_number(cell_text(amount_node)) if amount_node else None
        if amount is not None:
            return {
                "amount_cm": amount,
                "start": None,
                "description": cell_text(node),
            }

    return None


def parse_page_times(html: str) -> dict[str, Any]:
    """Parse source timestamps and derive the poll delay from source time."""
    server_match = re.search(r'"serverTime"\s*:\s*(\d+)', html)
    update_match = re.search(r'"forecastUpdateTime"\s*:\s*(\d+)', html)

    server_ts = int(server_match.group(1)) if server_match else None
    update_ts = int(update_match.group(1)) if update_match else None

    server_at = unix_to_local(server_ts)
    update_at = unix_to_local(update_ts)

    update_in_seconds: int | None = None
    schedule_source = "fallback"

    if server_ts is not None and update_ts is not None:
        update_in_seconds = max(0, update_ts - server_ts)
        schedule_source = "server_time_delta"
    elif update_ts is not None:
        update_in_seconds = max(
            0,
            int(
                (
                    datetime.fromtimestamp(update_ts, TZ)
                    - datetime.now(TZ)
                ).total_seconds()
            ),
        )
        schedule_source = "local_clock_fallback"

    return {
        "server_time": server_at,
        "forecast_update_at": update_at,
        "update_in_seconds": update_in_seconds,
        "schedule_source": schedule_source,
    }


def _align(values: list[Any], length: int) -> tuple[list[Any], bool]:
    """Align an optional row to the forecast length without failing the page."""
    if len(values) == length:
        return values, False
    if len(values) < length:
        return values + [None] * (length - len(values)), True
    return values[:length], True


def _daily_snow_from_forecast(forecast: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build stable daily snowfall totals from explicit numeric source cells."""
    grouped: dict[str, list[float]] = {}
    dates_in_order: list[str] = []

    for period in forecast:
        date_value = str(period["date"])
        if date_value not in dates_in_order:
            dates_in_order.append(date_value)

        amount = period.get("snow_amount_cm")
        if isinstance(amount, (int, float)):
            grouped.setdefault(date_value, []).append(float(amount))

    return [
        {
            "date": date_value,
            "snow_cm": (
                round(sum(grouped[date_value]), 1)
                if date_value in grouped
                else None
            ),
        }
        for date_value in dates_in_order
    ]


def _validate_source_page(soup: BeautifulSoup) -> None:
    """Reject obvious non-forecast pages before returning data."""
    if not get_row(soup, "days") or not get_row(soup, "time"):
        raise ValueError("Snow-Forecast forecast table is missing")

    text = soup.get_text(" ", strip=True).lower()
    if any(marker in text for marker in BLOCK_MARKERS):
        raise ValueError("Snow-Forecast returned an access challenge page")


def parse_level_html(
    level_key: str,
    config: dict[str, object],
    html: str,
) -> dict[str, Any]:
    """Parse one Snow-Forecast elevation with resilient row handling."""
    started = datetime.now(TZ)
    soup = BeautifulSoup(html, "html.parser")
    _validate_source_page(soup)

    dates = parse_dates(soup)
    periods = parse_periods(soup)
    if not periods:
        raise ValueError("Snow-Forecast time row is empty")

    forecast_length = len(periods)
    if len(dates) != forecast_length:
        raise ValueError(
            "Snow-Forecast day columns do not match time columns: "
            f"dates={len(dates)}, periods={forecast_length}"
        )

    rows: dict[str, list[Any]] = {
        "phrases": parse_phrases(soup),
        "weather": parse_weather(soup),
        "wind": parse_wind(soup),
        "snow": values_from_data_value(soup, "snow", ".snow-amount"),
        "rain": values_from_data_value(soup, "rain", ".rain-amount"),
        "temp_max": values_from_data_value(
            soup, "temperature-max", ".temp-value"
        ),
        "temp_min": values_from_data_value(
            soup, "temperature-min", ".temp-value"
        ),
        "chill": values_from_data_value(
            soup, "temperature-chill", ".temp-value"
        ),
        "freezing": values_from_data_value(
            soup, "freezing-level", ".level-value"
        ),
        "humidity": values_from_text(soup, "humidity"),
    }

    warnings: list[str] = []
    aligned: dict[str, list[Any]] = {}
    for name, values in rows.items():
        values, changed = _align(values, forecast_length)
        aligned[name] = values
        if changed:
            warnings.append(
                f"{name} row had {len(rows[name])} cells; "
                f"normalized to {forecast_length}"
            )

    timing = parse_page_times(html)
    forecast: list[dict[str, Any]] = []

    for index in range(forecast_length):
        phrase = aligned["phrases"][index]
        weather_value = aligned["weather"][index]
        combined = " ".join(
            value
            for value in (phrase, weather_value)
            if value
        ).lower()

        forecast.append(
            {
                "index": index,
                "date": dates[index],
                "period": periods[index],
                "phrase": phrase,
                "weather": weather_value,
                "snow_expected": "snow" in combined,
                "snow_amount_cm": aligned["snow"][index],
                "rain_mm": aligned["rain"][index],
                "temp_max_c": aligned["temp_max"][index],
                "temp_min_c": aligned["temp_min"][index],
                "chill_c": aligned["chill"][index],
                "freezing_level_m": aligned["freezing"][index],
                "humidity_pct": aligned["humidity"][index],
                "wind": aligned["wind"][index],
            }
        )

    finished = datetime.now(TZ)
    return {
        "name": config["name"],
        "elevation_m": config["elevation_m"],
        "source": config["url"],
        "fetched_at": finished.isoformat(),
        "issued_at": timing["server_time"],
        "forecast_update_at": timing["forecast_update_at"],
        "update_in_seconds": timing["update_in_seconds"],
        "schedule_source": timing["schedule_source"],
        "next_snow": parse_next_snow(soup),
        "forecast": forecast,
        "daily_snow": _daily_snow_from_forecast(forecast),
        "status": "ok",
        "last_error": None,
        "validation": {
            "actual_periods": forecast_length,
            "row_lengths": {
                name: len(values)
                for name, values in rows.items()
            },
            "warnings": warnings,
        },
        "duration_seconds": round(
            (finished - started).total_seconds(),
            3,
        ),
    }
