/* Aqshaqar Lovelace card - snowfall first. */

class AqshaqarCard extends HTMLElement {
  setConfig(config) {
    this.config = { title: "Shymbulak Snow", ...config };
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 9;
  }

  static getStubConfig() {
    return { title: "Shymbulak Snow" };
  }

  _state(level) {
    const states = this._hass?.states || {};
    return (
      states[`sensor.aqshaqar_${level}_snow_forecast`] ||
      states[`sensor.${level}_snow_forecast`] ||
      states[`sensor.${level}_forecast`] ||
      null
    );
  }

  _value(level) {
    return this._state(level)?.state || "—";
  }

  _forecast(level) {
    return this._state(level)?.attributes?.forecast || [];
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
    const state = this._state(level);
    if (!state) return "—";

    const next = state.attributes?.next_snow;
    if (next?.amount_cm != null && next?.start) {
      const d = new Date(next.start);
      if (!Number.isNaN(d.getTime())) {
        return `❄ ${Number(next.amount_cm).toLocaleString([], { maximumFractionDigits: 1 })} cm · ${d.toLocaleDateString([], { day: "numeric", month: "short" })}, ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
      }
    }

    return state.state;
  }

  _daySnow(day) {
    if (typeof day.snow_cm === "number") {
      return `❄ ${Number(day.snow_cm).toLocaleString([], { maximumFractionDigits: 1 })} cm`;
    }
    return "—";
  }

  _station(level, title, elevation) {
    const days = this._forecast(level);

    return `
      <section class="station">
        <div class="station-head">
          <div>
            <div class="station-name">${title}</div>
            <div class="elevation">${elevation} m</div>
          </div>
          <div class="next">${this._nextSnow(level)}</div>
        </div>

        <div class="label">Snowfall forecast</div>
        <div class="days">
          ${days.map(day => `
            <div class="day">
              <div class="date">${this._formatDate(day.date)}</div>
              <div class="snow">${this._daySnow(day)}</div>
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
          align-items:center;
          justify-content:space-between;
          gap:12px;
        }
        .station-name { font-size:18px; font-weight:700; }
        .elevation { font-size:12px; color:var(--secondary-text-color); margin-top:2px; }
        .next { font-size:18px; font-weight:700; text-align:right; color:var(--primary-color); }
        .label {
          margin-top:12px;
          margin-bottom:7px;
          font-size:12px;
          color:var(--secondary-text-color);
        }
        .days {
          display:grid;
          grid-template-columns:repeat(6, minmax(85px, 1fr));
          gap:7px;
          overflow-x:auto;
        }
        .day {
          min-width:85px;
          padding:9px 7px;
          border-radius:12px;
          background:var(--primary-background-color);
          text-align:center;
        }
        .date { font-size:11px; color:var(--secondary-text-color); white-space:nowrap; }
        .snow {
          margin-top:8px;
          min-height:18px;
          font-size:12px;
          font-weight:700;
          color:var(--primary-color);
          line-height:1.3;
        }
        @media (min-width: 1000px) {
          .stations { grid-template-columns:repeat(3, minmax(0, 1fr)); }
          .days { grid-template-columns:repeat(6, minmax(70px, 1fr)); overflow-x:hidden; }
        }
      </style>
      <ha-card>
        <div class="wrap">
          <div class="top">
            <div>
              <div class="title">${this.config?.title || "Shymbulak Snow"}</div>
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
    description: "Snowfall forecast by Shymbulak elevation.",
    preview: true,
  });
}
