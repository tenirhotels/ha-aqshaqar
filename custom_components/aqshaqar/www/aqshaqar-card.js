/* Aqshaqar Lovelace card - responsive weather and snowfall. */

class AqshaqarCard extends HTMLElement {
  setConfig(config) {
    this.config = { title: "Shymbulak Weather", ...config };
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() { return 12; }

  static getStubConfig() { return { title: "Shymbulak Weather" }; }

  // Aqshaqar weather entities use: weather.aqshaqar_2220_base,
  // weather.aqshaqar_2692_mid and weather.aqshaqar_3163_top.
  _weather(level, elevation) {
    return this._hass?.states?.[`weather.aqshaqar_${elevation}_${level}`] || null;
  }

  _conditionIcon(condition) {
    const icons = {
      sunny: "mdi:weather-sunny", clear: "mdi:weather-night",
      partlycloudy: "mdi:weather-partly-cloudy", cloudy: "mdi:weather-cloudy",
      fog: "mdi:weather-fog", rainy: "mdi:weather-rainy", snowy: "mdi:weather-snowy",
      "snowy-rainy": "mdi:weather-snowy-rainy", "lightning-rainy": "mdi:weather-lightning-rainy",
      windy: "mdi:weather-windy",
    };
    return icons[condition] || "mdi:weather-cloudy";
  }

  _conditionLabel(condition) {
    const labels = {
      sunny: "Sunny", clear: "Clear", partlycloudy: "Partly cloudy", cloudy: "Cloudy",
      fog: "Fog", rainy: "Rainy", snowy: "Snowy", "snowy-rainy": "Snow + rain",
      "lightning-rainy": "Thunderstorm", windy: "Windy",
    };
    return labels[condition] || condition || "Unknown";
  }

  _formatTemp(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    return `${Math.round(number)}°`;
  }

  _formatSnow(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    return `❄ ${number.toLocaleString([], { maximumFractionDigits: 1 })} cm`;
  }

  _formatDate(value) {
    if (!value) return "—";
    const d = new Date(`${value}T12:00:00`);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
  }

  _formatNextSnow(weather) {
    const next = weather?.attributes?.next_snow;
    if (!next || next.amount_cm == null) return null;

    const amount = Number(next.amount_cm);
    if (!Number.isFinite(amount)) return null;

    if (next.start) {
      const d = new Date(next.start);
      if (!Number.isNaN(d.getTime())) {
        return {
          amount: `❄ ${amount.toLocaleString([], { maximumFractionDigits: 1 })} cm`,
          date: d.toLocaleDateString([], { day: "numeric", month: "short" }),
          time: d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }),
        };
      }
    }

    return {
      amount: `❄ ${amount.toLocaleString([], { maximumFractionDigits: 1 })} cm`,
      date: next.description || "",
      time: "",
    };
  }

  _dailyForecast(weather) {
    return weather?.attributes?.daily_forecast || [];
  }

  _station(level, title, elevation) {
    const weather = this._weather(level, elevation);
    const days = this._dailyForecast(weather).slice(0, 6);
    const currentCondition = weather?.state || "cloudy";
    const currentTemp = weather?.attributes?.temperature;
    const apparentTemp = weather?.attributes?.apparent_temperature;
    const humidity = weather?.attributes?.humidity;
    const windSpeed = weather?.attributes?.wind_speed;
    const windBearing = weather?.attributes?.wind_bearing;
    const nextSnow = this._formatNextSnow(weather);

    return `
      <section class="station">
        <div class="station-head">
          <div class="station-main">
            <div class="station-name">${elevation} ${title}</div>
            <div class="current">
              <ha-icon class="current-icon" icon="${this._conditionIcon(currentCondition)}"></ha-icon>
              <span class="current-temp">${this._formatTemp(currentTemp)}</span>
              <span class="condition">${this._conditionLabel(currentCondition)}</span>
            </div>
            <div class="details">
              ${apparentTemp != null ? `<span>Feels ${this._formatTemp(apparentTemp)}</span>` : ""}
              ${humidity != null ? `<span>Humidity ${Math.round(Number(humidity))}%</span>` : ""}
              ${windSpeed != null ? `<span>Wind ${Math.round(Number(windSpeed))} km/h${windBearing ? ` (${windBearing})` : ""}</span>` : ""}
            </div>
          </div>
          ${nextSnow ? `
            <div class="next">
              <div class="next-label">Next snow</div>
              <div class="next-main">
                <span class="next-amount">${nextSnow.amount}</span>
                ${nextSnow.date ? `<span class="next-date">${nextSnow.date}${nextSnow.time ? ` · ${nextSnow.time}` : ""}</span>` : ""}
              </div>
            </div>
          ` : ""}
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
              <div class="day-condition">${this._conditionLabel(day.condition)}</div>
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

    const stations = [["base", "Base", 2220], ["mid", "Mid", 2692], ["top", "Top", 3163]];
    const update = this._hass.states?.["sensor.aqshaqar_forecast_update"]?.state;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; }
        ha-card { overflow:hidden; }
        .wrap { padding:16px; }
        .top { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:14px; }
        .title { font-size:22px; font-weight:700; line-height:1.2; }
        .subtitle { color:var(--secondary-text-color); font-size:12px; margin-top:4px; }
        .update { color:var(--secondary-text-color); font-size:11px; line-height:1.4; text-align:right; white-space:nowrap; }
        .stations { display:flex; flex-direction:column; gap:12px; }
        .station { border:1px solid var(--divider-color); border-radius:18px; padding:14px; background:var(--card-background-color); min-width:0; box-sizing:border-box; }
        .station-head { display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:start; gap:18px; }
        .station-main { min-width:0; }
        .station-name { font-size:18px; font-weight:700; line-height:1.2; }
        .current { margin-top:7px; display:flex; align-items:center; gap:8px; min-width:0; }
        .current-icon { width:24px; height:24px; flex:0 0 24px; }
        .current-temp { font-size:28px; font-weight:700; line-height:1; }
        .condition { font-size:12px; color:var(--secondary-text-color); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .details { display:flex; flex-wrap:wrap; gap:5px 12px; margin-top:7px; font-size:11px; color:var(--secondary-text-color); }
        .next { min-width:150px; max-width:230px; padding:8px 10px; border-radius:12px; background:var(--primary-background-color); box-sizing:border-box; }
        .next-label { font-size:10px; color:var(--secondary-text-color); margin-bottom:3px; }
        .next-main { display:flex; flex-direction:column; gap:2px; }
        .next-amount { font-size:15px; font-weight:700; color:var(--primary-color); white-space:nowrap; }
        .next-date { font-size:11px; color:var(--secondary-text-color); white-space:nowrap; }
        .label { margin-top:15px; margin-bottom:8px; font-size:12px; color:var(--secondary-text-color); }
        .days { display:grid; grid-template-columns:repeat(6, minmax(82px, 1fr)); gap:7px; min-width:0; }
        .day { min-width:0; padding:9px 5px; border-radius:12px; background:var(--primary-background-color); text-align:center; overflow:hidden; box-sizing:border-box; }
        .date { font-size:10px; color:var(--secondary-text-color); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .day-icon { display:block; width:22px; height:22px; margin:7px auto 4px; }
        .temps { display:flex; justify-content:center; align-items:baseline; gap:5px; font-size:15px; font-weight:700; }
        .low { color:var(--secondary-text-color); font-weight:500; }
        .day-condition { margin-top:4px; min-height:28px; font-size:10px; line-height:1.25; color:var(--secondary-text-color); display:flex; align-items:flex-start; justify-content:center; }
        .snow { margin-top:6px; min-height:17px; font-size:11px; font-weight:700; color:var(--primary-color); line-height:1.3; white-space:nowrap; }

        @media (max-width: 850px) {
          .station-head { grid-template-columns:minmax(0,1fr) 145px; gap:12px; }
          .next { min-width:0; max-width:none; }
          .days { grid-template-columns:repeat(6, minmax(78px, 1fr)); overflow-x:auto; padding-bottom:3px; scrollbar-width:thin; }
        }

        @media (max-width: 600px) {
          .wrap { padding:12px; }
          .top { gap:8px; }
          .title { font-size:19px; }
          .update { font-size:10px; }
          .station-head { grid-template-columns:1fr; gap:10px; }
          .next { width:100%; max-width:none; }
          .next-main { flex-direction:row; align-items:baseline; gap:8px; flex-wrap:wrap; }
          .days { grid-template-columns:repeat(6, 78px); }
        }

        @media (max-width: 420px) {
          .top { flex-direction:column; }
          .update { text-align:left; }
          .station { padding:12px; }
          .current-temp { font-size:26px; }
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
    description: "Responsive weather and daily snowfall forecast by Shymbulak elevation.",
    preview: true,
  });
}
