/* Aqshaqar Lovelace card - weather and snowfall. */

class AqshaqarCard extends HTMLElement {
  setConfig(config) {
    this.config = { title: "Shymbulak Weather", ...config };
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 10;
  }

  static getStubConfig() {
    return { title: "Shymbulak Weather" };
  }

  _weather(level, elevation) {
    return this._hass?.states?.[
      `weather.aqshaqar_${level}_${elevation}_m`
    ] || null;
  }

  _snow(level) {
    const states = this._hass?.states || {};
    return (
      states[`sensor.aqshaqar_${level}_forecast`] ||
      states[`sensor.aqshaqar_${level}_snow_forecast`] ||
      null
    );
  }

  _conditionIcon(condition) {
    const icons = {
      sunny: "mdi:weather-sunny",
      clear: "mdi:weather-night",
      partlycloudy: "mdi:weather-partly-cloudy",
      cloudy: "mdi:weather-cloudy",
      fog: "mdi:weather-fog",
      rainy: "mdi:weather-rainy",
      snowy: "mdi:weather-snowy",
      "snowy-rainy": "mdi:weather-snowy-rainy",
      "lightning-rainy": "mdi:weather-lightning-rainy",
      windy: "mdi:weather-windy",
    };
    return icons[condition] || "mdi:weather-cloudy";
  }

  _conditionLabel(condition) {
    const labels = {
      sunny: "Sunny",
      clear: "Clear",
      partlycloudy: "Partly cloudy",
      cloudy: "Cloudy",
      fog: "Fog",
      rainy: "Rainy",
      snowy: "Snowy",
      "snowy-rainy": "Snow and rain",
      "lightning-rainy": "Thunderstorm",
      windy: "Windy",
    };
    return labels[condition] || "Cloudy";
  }

  _formatTemp(value) {
    if (typeof value !== "number") return "—";
    return `${Math.round(value)}°`;
  }

  _formatSnow(value) {
    if (typeof value !== "number") return "—";
    return `❄ ${Number(value).toLocaleString([], {
      maximumFractionDigits: 1,
    })} cm`;
  }

  _formatDate(value) {
    if (!value) return "—";
    const d = new Date(`${value}T12:00:00`);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString([], {
      weekday: "short",
      day: "numeric",
      month: "short",
    });
  }

  _nextSnow(level) {
    const state = this._snow(level);
    if (!state) return "—";

    const next = state.attributes?.next_snow;
    if (next?.amount_cm != null && next?.start) {
      const d = new Date(next.start);
      if (!Number.isNaN(d.getTime())) {
        return `❄ ${Number(next.amount_cm).toLocaleString([], {
          maximumFractionDigits: 1,
        })} cm · ${d.toLocaleDateString([], {
          day: "numeric",
          month: "short",
        })}, ${d.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })}`;
      }
    }

    return "—";
  }

  _dailyForecast(level, elevation) {
    const weather = this._weather(level, elevation);
    return weather?.attributes?.daily_forecast || [];
  }

  _station(level, title, elevation) {
    const weather = this._weather(level, elevation);
    const days = this._dailyForecast(level, elevation);

    const currentCondition = weather?.state || "cloudy";
    const currentTemp = weather?.attributes?.temperature;
    const humidity = weather?.attributes?.humidity;
    const windSpeed = weather?.attributes?.wind_speed;
    const windBearing = weather?.attributes?.wind_bearing;
    const nextSnow = this._nextSnow(level);

    return `
      <section class="station">
        <div class="station-head">
          <div>
            <div class="station-name">${elevation} ${title}</div>
            <div class="current">
              <ha-icon icon="${this._conditionIcon(currentCondition)}"></ha-icon>
              <span class="current-temp">${this._formatTemp(currentTemp)}</span>
              <span class="condition">${this._conditionLabel(currentCondition)}</span>
            </div>
            <div class="details">
              ${humidity != null ? `Humidity ${Math.round(humidity)}%` : ""}
              ${windSpeed != null ? ` · Wind ${Math.round(windSpeed)} km/h${windBearing ? ` (${windBearing})` : ""}` : ""}
            </div>
          </div>
          <div class="next">
            <div class="next-label">Next snow</div>
            <div class="next-value">${nextSnow}</div>
          </div>
        </div>

        <div class="label">Daily forecast · Daily snow</div>
        <div class="days">
          ${days.map(day => `
            <div class="day">
              <div class="date">${this._formatDate(day.date)}</div>
              <ha-icon class="day-icon" icon="${this._conditionIcon(day.condition)}"></ha-icon>
              <div class="temps">
                <span class="high">${this._formatTemp(day.native_temperature)}</span>
                <span class="low">${this._formatTemp(day.native_templow)}</span>
              </div>
              <div class="condition">${this._conditionLabel(day.condition)}</div>
              <div class="snow">${this._formatSnow(day.snow_cm)}</div>
            </div>
          `).join("")}
        </div>
      </section>
    `;
  }

  render() {
    if (!this._hass) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });

    const stations = [
      ["base", "Base", 2220],
      ["mid", "Mid", 2692],
      ["top", "Top", 3163],
    ];

    const updateState =
      this._hass.states?.["sensor.aqshaqar_forecast_update"] ||
      this._hass.states?.["sensor.forecast_update"];
    const update = updateState?.state;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; }
        ha-card { overflow:hidden; }
        .wrap { padding:16px; }
        .title { font-size:22px; font-weight:700; }
        .subtitle { color:var(--secondary-text-color); font-size:12px; margin-top:3px; }
        .top { display:flex; justify-content:space-between; gap:16px; margin-bottom:14px; }
        .update { color:var(--secondary-text-color); font-size:11px; text-align:right; }
        .stations { display:grid; grid-template-columns:1fr; gap:12px; }
        .station {
          border:1px solid var(--divider-color);
          border-radius:18px;
          padding:14px;
          background:var(--card-background-color);
        }
        .station-head {
          display:flex;
          align-items:flex-start;
          justify-content:space-between;
          gap:16px;
        }
        .station-name { font-size:18px; font-weight:700; }
        .current {
          margin-top:7px;
          display:flex;
          align-items:center;
          gap:7px;
        }
        .current ha-icon { width:22px; height:22px; }
        .current-temp { font-size:25px; font-weight:700; }
        .condition { font-size:11px; color:var(--secondary-text-color); }
        .details { margin-top:4px; font-size:11px; color:var(--secondary-text-color); }
        .next { min-width:190px; text-align:right; }
        .next-label {
          font-size:11px;
          color:var(--secondary-text-color);
          margin-bottom:4px;
        }
        .next-value { font-size:16px; font-weight:700; color:var(--primary-color); }
        .label {
          margin-top:14px;
          margin-bottom:8px;
          font-size:12px;
          color:var(--secondary-text-color);
        }
        .days {
          display:grid;
          grid-template-columns:repeat(6, minmax(90px, 1fr));
          gap:7px;
          overflow-x:auto;
        }
        .day {
          min-width:90px;
          padding:9px 7px;
          border-radius:12px;
          background:var(--primary-background-color);
          text-align:center;
        }
        .date {
          font-size:11px;
          color:var(--secondary-text-color);
          white-space:nowrap;
        }
        .day-icon {
          display:block;
          width:22px;
          height:22px;
          margin:7px auto 3px;
        }
        .temps {
          display:flex;
          justify-content:center;
          gap:5px;
          font-size:14px;
          font-weight:700;
        }
        .low {
          color:var(--secondary-text-color);
          font-weight:500;
        }
        .snow {
          margin-top:7px;
          min-height:18px;
          font-size:12px;
          font-weight:700;
          color:var(--primary-color);
          line-height:1.3;
        }
        @media (min-width: 1000px) {
          .stations { grid-template-columns:repeat(3, minmax(0, 1fr)); }
          .days { grid-template-columns:repeat(6, minmax(68px, 1fr)); overflow-x:hidden; }
          .next { min-width:0; max-width:45%; }
        }
        @media (max-width: 599px) {
          .station-head { flex-direction:column; }
          .next { min-width:0; text-align:left; }
        }
      </style>
      <ha-card>
        <div class="wrap">
          <div class="top">
            <div>
              <div class="title">${this.config?.title || "Shymbulak Weather"}</div>
              <div class="subtitle">Aqshaqar · Snow-Forecast</div>
            </div>
            <div class="update">Next update<br>${update || "—"}</div>
          </div>
          <div class="stations">
            ${stations.map(([level, title, elevation]) => this._station(level, title, elevation)).join("")}
          </div>
        </div>
      </ha-card>
    `;
  }
}

customElements.define("aqshaqar-card", AqshaqarCard);

window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "aqshaqar-card")) {
  window.customCards.push({
    type: "aqshaqar-card",
    name: "Aqshaqar",
    description: "Weather and daily snowfall forecast by Shymbulak elevation.",
    preview: true,
  });
}
