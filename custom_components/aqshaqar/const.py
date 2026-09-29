"""Constants for Aqshaqar."""

from __future__ import annotations

DOMAIN = "aqshaqar"
NAME = "Aqshaqar"
VERSION = "0.4.13"

RESORT = "Shymbulak"
WEBSITE_URL = "http://tenirhotels.com/"
DEVICE_ID = "shymbulak"
TIMEZONE = "Asia/Almaty"
BASE_URL = "https://www.snow-forecast.com/resorts/Chimbulak/6day"

FALLBACK_RETRY_MINUTES = 10
PARTIAL_RETRY_MINUTES = 10
MIN_UPDATE_DELAY_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 30
SNAPSHOT_STORE_VERSION = 3


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

LEVELS: dict[str, dict[str, object]] = {
    "base": {
        "name": "Base",
        "elevation_m": 2220,
        "url": f"{BASE_URL}/bot",
    },
    "mid": {
        "name": "Mid",
        "elevation_m": 2692,
        "url": f"{BASE_URL}/mid",
    },
    "top": {
        "name": "Top",
        "elevation_m": 3163,
        "url": f"{BASE_URL}/top",
    },
}
