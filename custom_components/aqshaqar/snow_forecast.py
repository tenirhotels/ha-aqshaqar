"""Snow-Forecast HTML parser used by the AQSHAQAR integration."""

from __future__ import annotations

import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .const import EXPECTED_PERIODS, TIMEZONE

TZ = ZoneInfo(TIMEZONE)


def parse_number(value):
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


def cell_text(cell):
    """Return normalized visible text from a BeautifulSoup node."""
    if cell is None:
        return None
    value = " ".join(cell.stripped_strings)
    return value or None


def unix_to_local(timestamp):
    """Convert Unix timestamp to an ISO-8601 timestamp in Almaty time."""
    if timestamp is None:
        return None
    return datetime.fromtimestamp(int(timestamp), TZ).isoformat()


def get_row(soup: BeautifulSoup, row_name: str):
    return soup.select_one(f'tr[data-row="{row_name}"]')


def get_cells(soup: BeautifulSoup, row_name: str):
    row = get_row(soup, row_name)
    if not row:
        return []
    return row.select("td.forecast-table__cell")


def values_from_data_value(soup: BeautifulSoup, row_name: str, selector: str | None = None):
    """Extract numerical values, preferring data-value when available."""
    result = []
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


def values_from_text(soup: BeautifulSoup, row_name: str):
    return [parse_number(cell_text(cell)) for cell in get_cells(soup, row_name)]


def parse_dates(soup: BeautifulSoup):
    """Expand day cells by their colspan into one date per forecast period."""
    row = get_row(soup, "days")
    if not row:
        return []

    result = []
    for cell in row.select("td.forecast-table__cell"):
        date_value = cell.get("data-date")
        if not date_value:
            continue
        try:
            colspan = int(cell.get("colspan", "1"))
        except ValueError:
            colspan = 1
        result.extend([date_value] * colspan)
    return result


def parse_periods(soup: BeautifulSoup):
    return [cell_text(cell) for cell in get_cells(soup, "time")]


def parse_phrases(soup: BeautifulSoup):
    row = get_row(soup, "phrases")
    if not row:
        return []

    result = []
    for cell in row.select("td.forecast-table__cell"):
        node = cell.select_one("[class*='forecast-table__phrase']")
        result.append(cell_text(node or cell))
    return result


def parse_weather(soup: BeautifulSoup):
    row = get_row(soup, "weather")
    if not row:
        return []

    result = []
    for cell in row.select("td.forecast-table__cell"):
        icon = cell.select_one("img.weather-icon")
        result.append(icon.get("alt") if icon else None)
    return result


def parse_wind(soup: BeautifulSoup):
    row = get_row(soup, "wind")
    if not row:
        return []

    result = []
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


def parse_next_snow(soup: BeautifulSoup):
    """Parse structured Next Snow data from JSON-LD, with HTML fallback."""
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        objects = data if isinstance(data, list) else [data]
        for obj in objects:
            if not isinstance(obj, dict):
                continue

            accepted = obj.get("acceptedAnswer")
            if not isinstance(accepted, dict):
                continue

            event = accepted.get("about")
            if not isinstance(event, dict) or event.get("@type") != "Event":
                continue

            if event.get("name") != "Next snow in Shymbulak:":
                continue

            amount = None
            additional = event.get("additionalProperty")
            if isinstance(additional, dict) and additional.get("name") == "snowfall":
                amount = parse_number(additional.get("value"))

            return {
                "amount_cm": amount,
                "start": event.get("startDate"),
                "description": event.get("description"),
            }

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


def parse_page_times(html: str):
    server_match = re.search(r'"serverTime"\s*:\s*(\d+)', html)
    update_match = re.search(r'"forecastUpdateTime"\s*:\s*(\d+)', html)

    server_ts = int(server_match.group(1)) if server_match else None
    update_ts = int(update_match.group(1)) if update_match else None

    server_at = unix_to_local(server_ts)
    update_at = unix_to_local(update_ts)

    update_in_seconds = None
    if update_ts:
        update_in_seconds = max(
            0,
            int((datetime.fromtimestamp(update_ts, TZ) - datetime.now(TZ)).total_seconds()),
        )

    return {
        "server_time": server_at,
        "forecast_update_at": update_at,
        "update_in_seconds": update_in_seconds,
    }


def parse_level_html(level_key: str, config: dict[str, object], html: str) -> dict:
    """Parse one Snow-Forecast level from already downloaded HTML."""
    started = datetime.now(TZ)
    soup = BeautifulSoup(html, "html.parser")

    dates = parse_dates(soup)
    periods = parse_periods(soup)
    phrases = parse_phrases(soup)
    weather = parse_weather(soup)
    wind = parse_wind(soup)

    snow = values_from_data_value(soup, "snow", ".snow-amount")
    rain = values_from_data_value(soup, "rain", ".rain-amount")
    temp_max = values_from_data_value(soup, "temperature-max", ".temp-value")
    temp_min = values_from_data_value(soup, "temperature-min", ".temp-value")
    chill = values_from_data_value(soup, "temperature-chill", ".temp-value")
    freezing = values_from_data_value(soup, "freezing-level", ".level-value")
    humidity = values_from_text(soup, "humidity")
    timing = parse_page_times(html)

    lengths = {
        "dates": len(dates),
        "periods": len(periods),
        "phrases": len(phrases),
        "weather": len(weather),
        "wind": len(wind),
        "snow": len(snow),
        "rain": len(rain),
        "temp_max": len(temp_max),
        "temp_min": len(temp_min),
        "chill": len(chill),
        "freezing": len(freezing),
        "humidity": len(humidity),
    }

    invalid = [
        f"{name}={length}, expected {EXPECTED_PERIODS}"
        for name, length in lengths.items()
        if length != EXPECTED_PERIODS
    ]
    if invalid:
        raise ValueError("Invalid Snow-Forecast page: " + "; ".join(invalid))

    forecast = []
    for i in range(EXPECTED_PERIODS):
        phrase = phrases[i]
        weather_value = weather[i]
        combined = " ".join(x for x in (phrase, weather_value) if x).lower()
        snow_expected = "snow" in combined

        forecast.append(
            {
                "index": i,
                "date": dates[i],
                "period": periods[i],
                "phrase": phrase,
                "weather": weather_value,
                "snow_expected": snow_expected,
                "snow_amount_cm": snow[i],
                "rain_mm": rain[i],
                "temp_max_c": temp_max[i],
                "temp_min_c": temp_min[i],
                "chill_c": chill[i],
                "freezing_level_m": freezing[i],
                "humidity_pct": humidity[i],
                "wind": wind[i],
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
        "next_snow": parse_next_snow(soup),
        "forecast": forecast,
        "validation": {
            "expected_periods": EXPECTED_PERIODS,
            "actual_periods": len(forecast),
            "row_lengths": lengths,
            "warnings": [],
        },
        "duration_seconds": round((finished - started).total_seconds(), 3),
    }
