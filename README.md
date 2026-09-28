# Aqshaqar by Tenir Shymbulak

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

After installation, Aqshaqar creates three Shymbulak forecast devices: **Base**, **Mid**, and **Top**.

## Sensors

Each elevation provides the following sensors:

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

The **Conditions** sensor also exposes the complete 17-period forecast in the `forecast` attribute.

## Data Source

Aqshaqar uses live data from Snow-Forecast:
https://www.snow-forecast.com/

## Data Updates

Aqshaqar does not use a fixed polling interval.
Each Snow-Forecast forecast page provides its own `forecastUpdateTime`. After a successful update, Aqshaqar calculates the next refresh from the update time reported by Snow-Forecast.
The integration uses the earliest next update reported by **Base**, **Mid**, or **Top**.
This means Aqshaqar only requests new forecast data when Snow-Forecast indicates that new forecast data should be available.

### Error Handling
If Snow-Forecast does not provide a valid update time, Aqshaqar retries after 10 minutes.
If the calculated update time has already passed, a minimum delay of 60 seconds is used to prevent repeated requests.
If only some elevation pages fail, Aqshaqar keeps the last known good data for the failed levels and continues using successful levels to schedule the next update.
If all elevation pages fail, Aqshaqar retries after 10 minutes.

## Home Assistant
Aqshaqar is designed as a native Home Assistant custom integration.

It provides entities that can be used in:

- Dashboards
- Automations
- Templates
- History
- Scripts
- Notifications

No additional Docker container, MQTT broker, or external Aqshaqar service is required.

## Development

This repository contains the Home Assistant custom integration for Aqshaqar.
Main components:

- `custom_components/aqshaqar/` — Home Assistant integration
- `snow_forecast.py` — Snow-Forecast data
- `coordinator.py` — data update coordinator
- `sensor.py` — Home Assistant sensors

## License

MIT License
