# AQSHAQAR by Tenir Shymbulak

Home Assistant custom integration for live Snow-Forecast data from Shymbulak Ski Resort.

Aqshaqar provides weather and snowfall data for three Shymbulak elevations:

- **2220 Base**
- **2692 Mid**
- **3163 Top**

## Installation with HACS

1. Open **HACS → Integrations**.
2. Open the **⋮** menu in the top-right corner.
3. Select **Custom repositories**.
4. Add:
   `https://github.com/tenirhotels/ha-aqshaqar`
5. Select **Integration**.
6. Install **Aqshaqar**.
7. Restart Home Assistant.
8. Go to **Settings → Devices & services → Add integration**.
9. Select **Aqshaqar**.

Aqshaqar creates one Home Assistant device named **Aqshaqar**.

## Data source

Aqshaqar uses **Snow-Forecast** as its only forecast source:

- Base: https://www.snow-forecast.com/resorts/Chimbulak/6day/bot
- Mid: https://www.snow-forecast.com/resorts/Chimbulak/6day/mid
- Top: https://www.snow-forecast.com/resorts/Chimbulak/6day/top

The integration parses the source forecast table, the source `Next snow in Shymbulak` event, and the source `forecastUpdateTime`.

Aqshaqar does not invent snowfall values. If Snow-Forecast displays `—`, Aqshaqar keeps the value unknown and shows `—` in the snowfall card.

## Update strategy

Aqshaqar does **not** use a fixed polling interval during normal operation.

The parser reads both `serverTime` and `forecastUpdateTime` from Snow-Forecast. The normal next poll is calculated from the difference between those two source timestamps, so the Home Assistant host clock does not determine the forecast cadence.

If a valid source update time is unavailable, Aqshaqar uses a 10-minute fallback.

When only some elevations fail, the last known good data is retained for those elevations and the integration retries within the partial-failure window.

When all elevations fail, Aqshaqar uses exponential backoff:

`2m → 5m → 10m → 20m → 30m → 60m`

A successful fetch resets the backoff.

If Snow-Forecast returns an obvious challenge/error page, Aqshaqar rejects it instead of replacing good forecast data with invalid HTML.

## Snow forecast

The main Aqshaqar value is snowfall.

For each elevation Aqshaqar provides:

- **Next snow** — amount, date and time from Snow-Forecast.
- **Daily snowfall** — explicit snowfall amounts grouped by calendar date.
- **Next snow sensor** — compact summary of the explicit Next snow event; daily forecast remains on the weather entity.
- **Weather entity** — normal Home Assistant weather presentation with daily forecast.

The number of source forecast periods is dynamic. Aqshaqar does not assume a fixed number such as 16 or 17. Optional source rows are normalized to the actual time-column count.

## Home Assistant entities

Weather:

- `weather.aqshaqar_2220_base`
- `weather.aqshaqar_2692_mid`
- `weather.aqshaqar_3163_top`

Snow:

- `sensor.aqshaqar_next_snow_at_the_base`
- `sensor.aqshaqar_next_snow_at_the_mid`
- `sensor.aqshaqar_next_snow_at_the_top`

Diagnostics:

- `sensor.aqshaqar_forecast_update`

All entities belong to the single **Aqshaqar** device.

## Forecast change events

Aqshaqar compares the current snowfall forecast with the previously accepted forecast.

The integration fires:

`aqshaqar_forecast_changed`

when the accepted snowfall forecast changes, including Next snow and daily snowfall changes.

It also fires:

`aqshaqar_next_snow_changed`

when the explicit Next snow event changes. This event is intended for operational notifications such as Telegram.

Examples:

`Mid 8 Oct: 3 cm → 5 cm`

or:

`Top next snow: 1 cm · 5 Oct 20:00 → 2 cm · 5 Oct 18:00`

Routine forecast refreshes with identical snowfall data do not create an Activity entry or forecast-change event.

The event contains:

- `device_id`
- `changes`
- `previous`
- `current`

This event can be used by Home Assistant automations, including Telegram notifications.

## Persistent change tracking

Aqshaqar stores the last accepted snowfall snapshot in Home Assistant storage.

This prevents a Home Assistant restart from resetting change detection and avoids duplicate notifications after a restart.

Only snowfall-related data is persisted.

## Diagnostics

Aqshaqar provides Home Assistant integration diagnostics.

Diagnostics include:

- last successful fetch
- source issue/update timestamps
- next poll
- per-elevation status
- parser warnings
- parser row lengths
- last errors
- next snow
- consecutive complete-fetch failures
- last detected snowfall changes

No credentials or authentication tokens are stored by the integration.

## Aqshaqar card

Aqshaqar includes a lightweight Lovelace card with no external frontend dependencies.

Resource:

```yaml
url: /aqshaqar/aqshaqar-card.js
type: module
```

Card:

```yaml
type: custom:aqshaqar-card
title: Shymbulak Snow
stations:
  - top
  - mid
  - base
```

The `stations` key controls both the display order and visibility.

Supported station keys:

- `top` — 3163 Top
- `mid` — 2692 Mid
- `base` — 2220 Base

When `stations` is omitted, the default order is `top → mid → base`.

To hide a station, simply omit it. For example:

```yaml
type: custom:aqshaqar-card
stations:
  - top
  - mid
```

An explicitly empty `stations: []` hides all station sections.

## Device naming

The intended presentation is:

- **Aqshaqar**
  - **2220 Base**
- **2692 Mid**
- **3163 Top**

This avoids duplicate names such as `Aqshaqar Base Base`.

## Visit

The **Visit** link opens:

http://tenirhotels.com/

## Development

Run parser tests locally:

```bash
python -m pip install beautifulsoup4 pytest
python -m pytest
```

Static linting:

```bash
ruff check custom_components tests
```

## License

MIT License
