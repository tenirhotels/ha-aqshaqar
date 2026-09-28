# AQSHAQAR by Tenir Shymbulak

Home Assistant custom integration for live Snow-Forecast data from Shymbulak Ski Resort.

Aqshaqar provides current weather and snow forecast data for three elevations of Shymbulak:

- **Base** — 2220 m
- **Mid** — 2692 m
- **Top** — 3163 m

## Installation with HACS

1. Open **HACS → Integrations**.
2. Open the **⋮** menu in the top-right corner.
3. Select **Custom repositories**.
4. Add:

   `https://github.com/tenirhotels/ha-aqshaqar`

5. Select **Integration** as the repository type.
6. Install **Aqshaqar**.
7. Restart Home Assistant.
8. Go to **Settings → Devices & services → Add integration**.
9. Select **Aqshaqar**.

Aqshaqar creates one Home Assistant device named **Aqshaqar**. The device contains sensors for all three Shymbulak elevations.

## Sensors

Each elevation provides:

- Conditions
- Temperature high
- Temperature low
- Wind chill
- Humidity
- Wind speed
- Rain
- Snow amount
- Freezing level
- Next snow
- Forecast update

Entity IDs are level-specific, for example:

- `sensor.aqshaqar_base_conditions`
- `sensor.aqshaqar_mid_conditions`
- `sensor.aqshaqar_top_conditions`

The **Conditions** sensors also expose the complete 17-period forecast in the `forecast` attribute.

## Data source

Aqshaqar uses live data from Snow-Forecast:

https://www.snow-forecast.com/

The three source pages are:

- Base: https://www.snow-forecast.com/resorts/Chimbulak/6day/bot
- Mid: https://www.snow-forecast.com/resorts/Chimbulak/6day/mid
- Top: https://www.snow-forecast.com/resorts/Chimbulak/6day/top

## Data updates

Aqshaqar does not use a fixed polling interval.

Each Snow-Forecast page provides its own `forecastUpdateTime`. After every successful fetch, Aqshaqar schedules the next poll using the earliest update time reported by Base, Mid, or Top.

This means Aqshaqar requests fresh data when Snow-Forecast indicates that a new forecast is expected, rather than polling on an arbitrary fixed schedule.

If Snow-Forecast does not provide a valid update time, Aqshaqar retries after 10 minutes.

If the calculated update time has already passed, a minimum delay of 60 seconds prevents a tight request loop.

If only some elevations fail, their last known good data is retained. The next refresh is scheduled from the successfully fetched elevations.

If all elevations fail, Home Assistant retries after 10 minutes.

## Aqshaqar card

Aqshaqar includes a lightweight Lovelace card with no external frontend dependencies.

Add the resource:

```yaml
url: /aqshaqar/aqshaqar-card.js
type: module
```

Then add:

```yaml
type: custom:aqshaqar-card
title: Shymbulak
```

The card shows Base, Mid and Top in one responsive view with conditions, temperature, wind, humidity, precipitation, freezing level, next snow and forecast update time.

## Weather entities

Aqshaqar also provides native Home Assistant weather entities for each Shymbulak elevation:

- `weather.aqshaqar_base`
- `weather.aqshaqar_mid`
- `weather.aqshaqar_top`

Each weather entity supports the standard **daily forecast**. The 17 Snow-Forecast periods are grouped by calendar date to produce daily high/low temperatures, conditions, precipitation and wind.

This means the standard Home Assistant Weather Forecast card can be used directly with Aqshaqar.

The bundled Aqshaqar card also shows the three elevations together, the daily forecast by date, and the next snowfall event for each station.

## Visit

The **Visit** link in Home Assistant opens: http://tenirhotels.com/

## Snow forecast

The Aqshaqar **Forecast** sensor is centered on the value that matters most for a ski resort: expected snowfall by calendar day.

For each elevation, the sensor exposes a daily `forecast` attribute containing:

- date
- weekday
- expected snowfall in cm
- whether snow is expected
- rain
- daily high and low temperature

Snow amounts are taken only from the explicit Snow-Forecast snowfall cells. When Snow-Forecast does not provide an amount (`—`), Aqshaqar keeps it as unavailable rather than inventing `0 cm`.

## License

MIT License
