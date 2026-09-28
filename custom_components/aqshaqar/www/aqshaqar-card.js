/* Aqshaqar Lovelace card - daily forecast by date + next snow. */

class AqshaqarCard extends HTMLElement {
  setConfig(config) {
    this.config = { title: "Shymbulak", ...config };
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
    return { title: "Shymbulak" };
  }

  _state(level, key) {
    return this._hass?.states?.[`sensor.aqshaqar_${level}_${key}`] ?? null;
  }

  _value(level, key, fallback = "—") {
    const state = this._state(level, key);
    if (!state || state.state === "unknown" || state.state === "unavailable") {
      return fallback;
    }
    return state.state;
  }

  _escape(value) {
    return String(value ?? "—")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _formatDate(value) {
    if (!value) return "—";
    const d = new Date(`${value}T12:00:00`);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
  }

  _formatUpdate(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString([], { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  _conditionIcon(period) {
    const text = `${period?.phrase || ""} ${period?.weather || ""}`.toLowerCase();
    if (text.includes("thunder") || text.includes("storm")) return "⛈️";
    if (text.includes("snow")) return "❄️";
    if (text.includes("rain") || text.includes("shwr") || text.includes("shower")) return "🌧️";
    if (text.includes("fog") || text.includes("mist")) return "🌫️";
    if (text.includes("partly")) return "⛅";
    if (text.includes("sun") || text.includes("clear")) return "☀️";
    if (text.includes("cloud") || text.includes("overcast")) return "☁️";
    return "☁️";
  }

  _dailyForecast(level) {
    const conditions = this._state(level, "conditions");
    const periods = conditions?.attributes?.forecast || [];
    const grouped = new Map();

    for (const p of periods) {
      if (!p?.date) continue;
      if (!grouped.has(p.date)) grouped.set(p.date, []);
      grouped.get(p.date).push(p);
    }

    return [...grouped.entries()].map(([date, items]) => {
      const highs = items.map(x => x.temp_max_c).filter(v => typeof v === "number");
      const lows = items.map(x => x.temp_min_c).filter(v => typeof v === "number");
      const rain = items.map(x => x.rain_mm).filter(v => typeof v === "number");
      const snow = items.map(x => x.snow_amount_cm).filter(v => typeof v === "number");

      const representative = items.find(x => /am|pm/i.test(x.period || "")) || items[0];

      return {
        date,
        icon: this._conditionIcon(representative),
        high: highs.length ? Math.max(...highs) : null,
        low: lows.length ? Math.min(...lows) : null,
        rain: rain.length ? rain.reduce((a, b) => a + b, 0) : null,
        snow: snow.length ? snow.reduce((a, b) => a + b, 0) : null,
      };
    });
  }

  _dailyRow(level) {
    const days = this._dailyForecast(level);

    return `
      <div class="forecast-title">Forecast</div>
      <div class="days">
        ${days.map(day => `
          <div class="day">
            <div class="day-date">${this._escape(this._formatDate(day.date))}</div>
            <div class="day-icon">${day.icon}</div>
            <div class="day-temp">
              <b>${this._escape(day.high ?? "—")}°</b>
              <span>${this._escape(day.low ?? "—")}°</span>
            </div>
            <div class="day-precip">
              ${day.snow != null ? `❄ ${this._escape(day.snow)} cm` : ""}
              ${day.rain != null ? `🌧 ${this._escape(day.rain)} mm` : ""}
            </div>
          </div>
        `).join("")}
      </div>
    `;
  }

  _station(level, title, elevation) {
    const conditions = this._value(level, "conditions");
    const high = this._value(level, "temperature_high");
    const low = this._value(level, "temperature_low");
    const wind = this._value(level, "wind_speed");
    const humidity = this._value(level, "humidity");
    const nextSnowState = this._state(level, "next_snow");
    const nextSnow = nextSnowState?.state || "—";
    const updateAt = this._state(level, "forecast_update")?.state;

    return `
      <section class="station">
        <div class="station-head">
          <div>
            <div class="station-name">${this._escape(title)}</div>
            <div class="elevation">${this._escape(elevation)} m</div>
          </div>
          <div class="condition">${this._escape(conditions)}</div>
        </div>

        <div class="current">
          <div class="current-temp">${this._escape(high)}°</div>
          <div class="current-low">↓ ${this._escape(low)}°</div>
          <div class="current-meta">💨 ${this._escape(wind)} km/h · 💧 ${this._escape(humidity)}%</div>
        </div>

        <div class="next-snow">
          <div>
            <div class="label">Next snow</div>
            <div class="next-value">${this._escape(nextSnow)}</div>
          </div>
          <div class="update">Forecast update<br>${this._escape(this._formatUpdate(updateAt))}</div>
        </div>

        ${this._dailyRow(level)}
      </section>
    `;
  }

  render() {
    if (!this._hass) return;

    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }

    const stations = [
      ["base", "Base", 2220],
      ["mid", "Mid", 2692],
      ["top", "Top", 3163],
    ];

    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; }
        ha-card { overflow:hidden; }
        .wrap { padding:16px; }
        .title-row {
          display:flex; align-items:flex-start; justify-content:space-between;
          gap:16px; margin-bottom:14px;
        }
        .title { font-size:22px; font-weight:700; letter-spacing:.2px; }
        .subtitle { color:var(--secondary-text-color); font-size:12px; margin-top:3px; }
        .stations { display:grid; grid-template-columns:1fr; gap:14px; }
        .station {
          border:1px solid var(--divider-color);
          border-radius:20px;
          padding:14px;
          background:var(--card-background-color);
        }
        .station-head {
          display:flex; justify-content:space-between; gap:12px;
        }
        .station-name { font-size:18px; font-weight:700; }
        .elevation { font-size:12px; color:var(--secondary-text-color); margin-top:2px; }
        .condition {
          max-width:45%; text-align:right;
          font-size:13px; color:var(--secondary-text-color);
        }
        .current {
          display:flex; align-items:baseline; gap:10px; margin:10px 0 8px;
        }
        .current-temp { font-size:40px; line-height:1; font-weight:700; }
        .current-low { font-size:16px; color:var(--secondary-text-color); }
        .current-meta { margin-left:auto; font-size:13px; color:var(--secondary-text-color); }
        .next-snow {
          display:flex; justify-content:space-between; align-items:center; gap:12px;
          padding:10px 12px; border-radius:14px;
          background:color-mix(in srgb, #6fb9ff 12%, var(--card-background-color));
          margin-bottom:12px;
        }
        .label {
          color:var(--secondary-text-color); font-size:11px;
          text-transform:uppercase; letter-spacing:.6px;
        }
        .next-value { font-size:18px; font-weight:700; margin-top:2px; }
        .update {
          text-align:right; color:var(--secondary-text-color); font-size:10px; line-height:1.35;
        }
        .forecast-title { font-size:13px; font-weight:600; margin:6px 0 8px; }
        .days {
          display:grid;
          grid-template-columns:repeat(6, minmax(90px, 1fr));
          gap:7px;
          overflow-x:auto;
        }
        .day {
          min-width:90px; padding:9px 7px; border-radius:13px;
          background:color-mix(in srgb, var(--primary-background-color) 75%, transparent);
          text-align:center;
        }
        .day-date { font-size:11px; color:var(--secondary-text-color); white-space:nowrap; }
        .day-icon { font-size:24px; line-height:1.2; margin:5px 0; }
        .day-temp { display:flex; justify-content:center; gap:7px; }
        .day-temp b { font-size:14px; }
        .day-temp span { font-size:12px; color:var(--secondary-text-color); }
        .day-precip {
          min-height:28px; margin-top:6px;
          font-size:9px; color:var(--secondary-text-color); line-height:1.35;
        }
        @media (min-width: 1000px) {
          .stations { grid-template-columns:repeat(3, minmax(0,1fr)); }
          .current { display:block; }
          .current-meta { margin-top:7px; }
          .days { grid-template-columns:repeat(6, minmax(78px,1fr)); overflow-x:hidden; }
        }
      </style>
      <ha-card>
        <div class="wrap">
          <div class="title-row">
            <div>
              <div class="title">${this._escape(this.config?.title || "Shymbulak")}</div>
              <div class="subtitle">Aqshaqar · Snow-Forecast</div>
            </div>
            <div class="subtitle">Base · Mid · Top</div>
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
if (!window.customCards.some((card) => card.type === "aqshaqar-card")) {
  window.customCards.push({
    type: "aqshaqar-card",
    name: "Aqshaqar",
    description: "Shymbulak daily weather forecast for Base, Mid and Top with next snow.",
    preview: true,
  });
}
