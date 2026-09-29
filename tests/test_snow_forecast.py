from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_PACKAGE_PATH = Path(__file__).parents[1] / "custom_components" / "aqshaqar"
_package = ModuleType("custom_components.aqshaqar")
_package.__path__ = [str(_PACKAGE_PATH)]
sys.modules.setdefault("custom_components.aqshaqar", _package)

_parser = importlib.import_module(
    "custom_components.aqshaqar.snow_forecast"
)
parse_level_html = _parser.parse_level_html
parse_page_times = _parser.parse_page_times


def _cell(value: str | None = None, *, attrs: str = "") -> str:
    text = "" if value is None else value
    return f'<td class="forecast-table__cell" {attrs}>{text}</td>'


def make_html(
    periods: int = 16,
    *,
    short_optional_row: bool = False,
    next_snow: tuple[float, str] | None = (3.0, "2026-10-08T08:00:00+05:00"),
) -> str:
    dates = []
    for date_value in ["2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02"]:
        colspan = periods // 4
        dates.append(
            _cell(
                attrs=(
                    f'class="forecast-table__cell" '
                    f'data-date="{date_value}" colspan="{colspan}"'
                ),
            )
        )

    time_cells = "".join(_cell(f"{index}") for index in range(periods))

    def row(name: str, values: list[str | None]) -> str:
        if short_optional_row:
            values = values[:-1]
        return (
            f'<tr data-row="{name}">'
            + "".join(_cell(value) for value in values)
            + "</tr>"
        )

    snow_values = ["—"] * periods
    snow_values[4] = '<span class="snow-amount" data-value="1">1 cm</span>'
    snow_values[5] = '<span class="snow-amount" data-value="2">2 cm</span>'

    phrases = ["Rain showers"] * periods
    wind = [
        '<span class="wind-icon" data-speed="5"><span class="wind-icon__tooltip">N</span></span>'
    ] * periods
    rain = ['<span class="rain-amount" data-value="1">1 mm</span>'] * periods
    temp_max = ['<span class="temp-value" data-value="7">7</span>'] * periods
    temp_min = ['<span class="temp-value" data-value="3">3</span>'] * periods
    chill = ['<span class="temp-value" data-value="2">2</span>'] * periods
    freezing = ['<span class="level-value" data-value="3700">3700</span>'] * periods
    humidity = ["50"] * periods

    event_block = ""
    if next_snow:
        amount, start = next_snow
        event_block = (
            '<script type="application/ld+json">'
            + json.dumps(
                {
                    "@type": "Question",
                    "acceptedAnswer": {
                        "about": {
                            "@type": "Event",
                            "name": "Next snow in Shymbulak:",
                            "startDate": start,
                            "description": f"{amount} cm snowfall",
                            "additionalProperty": [
                                {"name": "snowfall", "value": f"{amount} cm"}
                            ],
                        }
                    },
                }
            )
            + "</script>"
        )

    rows = [
        '<tr data-row="days">' + "".join(dates) + "</tr>",
        f'<tr data-row="time">{time_cells}</tr>',
        row("phrases", phrases),
        row("weather", ['<img class="weather-icon" alt="rain" />' for _ in range(periods)]),
        row("wind", wind),
        row("snow", snow_values),
        row("rain", rain),
        row("temperature-max", temp_max),
        row("temperature-min", temp_min),
        row("temperature-chill", chill),
        row("freezing-level", freezing),
        row("humidity", humidity),
    ]

    return f"""<!doctype html>
<html>
<head><title>Shymbulak Snow Forecast</title></head>
<body>
  <h1>Weather Forecast for Shymbulak</h1>
  <table class="forecast-table">{''.join(rows)}</table>
  <script>
    const serverTime = 1790636400;
    const forecastUpdateTime = 1790643600;
  </script>
  {event_block}
</body>
</html>"""


def test_parser_accepts_dynamic_period_count() -> None:
    data = parse_level_html(
        "mid",
        {"name": "Mid", "elevation_m": 2692, "url": "https://example.test/mid"},
        make_html(16),
    )

    assert len(data["forecast"]) == 16
    assert data["forecast"][4]["snow_amount_cm"] == 1
    assert data["forecast"][5]["snow_amount_cm"] == 2
    assert data["daily_snow"][1]["snow_cm"] == 3.0
    assert data["next_snow"]["amount_cm"] == 3.0
    assert data["next_snow"]["start"] == "2026-10-08T08:00:00+05:00"


def test_parser_reads_visible_next_snow_when_jsonld_is_missing() -> None:
    html = make_html(next_snow=None).replace(
        "<h1>Weather Forecast for Shymbulak</h1>",
        "<h1>Weather Forecast for Shymbulak</h1>"
        "<div>Next snow in Shymbulak: 20.0 cm on Mon 5th</div>",
    )

    data = parse_level_html(
        "top",
        {"name": "Top", "elevation_m": 3163, "url": "https://example.test/top"},
        html,
    )

    assert data["next_snow"]["amount_cm"] == 20
    assert data["next_snow"]["source"] == "snow_forecast_visible"
    assert data["next_snow"]["source_date"] == "2026-10-05"
    assert data["validation"]["next_snow_amount_cm"] == 20


def test_parser_normalizes_optional_short_row() -> None:
    data = parse_level_html(
        "top",
        {"name": "Top", "elevation_m": 3163, "url": "https://example.test/top"},
        make_html(16, short_optional_row=True),
    )

    assert len(data["forecast"]) == 16
    assert any("normalized to 16" in warning for warning in data["validation"]["warnings"])
    assert data["forecast"][-1]["humidity_pct"] is None


def test_parser_rejects_non_forecast_page() -> None:
    with pytest.raises(ValueError, match="forecast table is missing"):
        parse_level_html(
            "base",
            {"name": "Base", "elevation_m": 2220, "url": "https://example.test/base"},
            "<html><body>Verify you are human</body></html>",
        )


def test_page_times_use_source_server_time() -> None:
    html = (
        '<script>window.x = {"serverTime":1000,'
        '"forecastUpdateTime":3700};</script>'
    )
    result = parse_page_times(html)

    assert result["update_in_seconds"] == 2700
    assert result["schedule_source"] == "server_time_delta"
