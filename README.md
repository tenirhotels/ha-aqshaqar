# Aqshaqar Tenir Shymbulak

Home Assistant custom integration for Shymbulak Snow-Forecast data.

Aqshaqr  provides the live Snow-Forecast pages for three stations of Shymbulak Resort:

- Base — 2220 m
- Mid — 2692 m
- Top — 3163 m

## Installation with HACS

1. Open **HACS → Integrations**.
2. Open the menu in the top-right corner and choose **Custom repositories**.
3. Add:

   `https://github.com/tenirhotels/ha-aqshaqar`

4. Select **Integration** as the repository type.
5. Install **Aqshaqar**.
6. Restart Home Assistant.
7. Open **Settings → Devices & services → Add integration**.
8. Select **AQSHAQAR**.

The integration creates three Shymbulak level devices with forecast sensors.

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

The Conditions sensor also exposes the complete 17-period forecast as an attribute named `forecast`.

## Data source

Snow-Forecast:
- https://www.snow-forecast.com/

## Data updates

Aqshaqar does not use a fixed polling interval. Each Snow-Forecast page exposes its own `forecastUpdateTime`. After a successful fetch, the integration schedules the next poll for the earliest update time reported by Base, Mid, or Top.

If Snow-Forecast does not provide an update time, AQSHAQAR retries after 10 minutes. If an update time has already passed, a minimum 60-second delay prevents a tight request loop.

When only some levels fail, the last known good data is kept for the failed levels and the next poll is scheduled from the successfully fetched levels. If all levels fail, Home Assistant retries after 10 minutes.

## Development

This repository is a HACS custom integration repository. 
