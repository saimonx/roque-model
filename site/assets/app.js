// Fills the page from data/tonight.json (tonight.py) and data/evaluation.json (site_data.py).
// The page answers one question first (can we observe tonight, and when?) and keeps
// every piece of evidence folded below it.
(function () {
  const LOCAL_TZ = "Atlantic/Canary";
  const state = { lang: pickLang(), tonight: null, evaluation: null, hour: null };

  function pickLang() {
    const fromUrl = new URLSearchParams(location.search).get("lang");
    if (fromUrl === "es" || fromUrl === "en") return fromUrl;
    try { const saved = localStorage.getItem("lang"); if (saved) return saved; } catch (e) { /* private mode */ }
    return (navigator.language || "es").toLowerCase().startsWith("es") ? "es" : "en";
  }

  const T = () => window.I18N[state.lang];
  const fill = (text, values) => text.replace(/\{(\w+)\}/g, (_, k) => (values[k] != null ? values[k] : ""));
  const $ = (id) => document.getElementById(id);
  const locale = () => (state.lang === "es" ? "es-ES" : "en-GB");
  const num = (v, digits = 1) => (v == null ? T().na : v.toLocaleString(locale(), { minimumFractionDigits: digits, maximumFractionDigits: digits }));
  const pct = (p) => (p == null ? T().na : Math.round(p * 100) + " %");
  const ten = (p) => (p == null ? T().na : Math.round(p * 10));
  const timeLocal = (iso, withDate) => new Date(iso).toLocaleString(locale(), {
    timeZone: LOCAL_TZ, hour: "2-digit", minute: "2-digit", ...(withDate ? { day: "numeric", month: "short" } : {}) });
  const monthName = (dateStr) => T().months[+dateStr.slice(5, 7) - 1];
  const COLORS = { low: "--good", medium: "--warning", high: "--critical",
    excellent: "--good", good: "--good", average: "--warning", poor: "--critical" };

  function applyTexts() {
    document.documentElement.lang = state.lang;
    document.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = T()[n.dataset.i18n] || ""; });
    document.querySelectorAll("[data-i18n-html]").forEach((n) => { n.innerHTML = T()[n.dataset.i18nHtml] || ""; });
    document.querySelectorAll("[data-i18n-title]").forEach((n) => { n.title = T()[n.dataset.i18nTitle]; });
    document.querySelectorAll(".lang button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === state.lang)));
  }

  // How often "closed" is right, final and provisional (from the 2024-2026 evaluation).
  function hourRight(e) {
    const h = e && e.plain && e.plain.find((r) => r.key === "hour");
    return h ? { final: h.ours.final.right, provisional: h.ours.provisional.right, raw: h.refs.find((r) => r.name === "raw").right } : {};
  }

  // ---------------------------------------------------------------- the two lines, hour by hour
  // Line 1: our model (probability, coloured green / orange / red).
  // Line 2: the weather forecast read literally (close / open, red / green).
  // Clicking an hour opens a panel that shows how both lines come out for that hour.
  function renderLines(d) {
    const t = T(), c = state.evaluation && state.evaluation.comparison;
    if (c) {
      const model = d.mode === "final" ? c.final : c.provisional;
      $("acc-model").textContent = "(" + fill(t.line_acc, { p: pct(1 - model.wrong) }) + ")";
      $("acc-raw").textContent = "(" + fill(t.line_acc, { p: pct(1 - c.raw.wrong) }) + ")";
      $("acc-note").textContent = fill(t.acc_note, { open: Math.round((1 - c.always_open_wrong) * 100) });
    }
    const sel = state.hour;
    $("strip").parentElement.style.setProperty("--n", d.hours.length);
    const cell = (h, i, inner) => `<button type="button" class="cell${sel === i ? " selected" : ""}" data-i="${i}" aria-pressed="${sel === i}"
      title="${h.local}">${inner}</button>`;
    $("strip").innerHTML = d.hours.map((h, i) => cell(h, i, `
        <span class="cell-hour">${h.local.slice(0, 2)}h${h.moon_up ? ' <span class="cell-moon" title="' + t.moon_up_word + '">☾</span>' : ""}</span>
        <span class="cell-bar" style="background:var(${COLORS[h.level]})"></span>
        <span class="cell-p">${pct(h.p_closed)}</span>`)).join("");
    $("strip-raw").innerHTML = d.hours.map((h, i) => cell(h, i, `
        <span class="cell-bar" style="background:var(${h.raw_closed ? "--critical" : "--good"})"></span>
        <span class="cell-p">${h.raw_closed ? t.raw_close_word : t.raw_open_word}</span>`)).join("");
    document.querySelectorAll("#strip .cell, #strip-raw .cell").forEach((b) => b.addEventListener("click", () => {
      const i = +b.dataset.i;
      state.hour = state.hour === i ? null : i;
      renderLines(d);
    }));
    renderHourDetail(d);
  }

  function renderHourDetail(d) {
    const box = $("hour-detail"), i = state.hour;
    if (i == null || !d.hours[i]) { box.hidden = true; box.innerHTML = ""; return; }
    const t = T(), h = d.hours[i], n = d.night, ex = d.explain;
    const end = new Date(new Date(h.t).getTime() + 3600e3).toISOString();
    const kmh = (ms) => (ms == null ? t.na : num(ms * 3.6, 0));
    const signed = (x) => (Math.abs(x) < 0.005 ? "≈0" : (x >= 0 ? "+" : "−") + num(Math.abs(x * 100), 0)) + " %";
    const maxAbs = Math.max(0.05, ...Object.values(h.why).map(Math.abs));

    // How our model gets its percentage: starting point + one amount per group of inputs.
    // This hour's forecast is split by variable; the other groups follow.
    const detail = {
      humidity: fill(t.gd_humidity, { rh: num(h.raw.rh, 0), spread: num(h.raw.dew_spread, 1) }),
      wind: fill(t.gd_wind, { wind: kmh(h.raw.wind_ms) }),
      temperature: fill(t.gd_temperature, { temp: num(h.raw.temp, 1) }),
      cloud: fill(t.gd_cloud, { cloud: num(h.raw.cloud, 0) }),
      rain: fill(t.gd_rain, { precip: num(h.raw.precip, 1) }),
      pressure: fill(t.gd_pressure, { p: num(h.raw.pressure, 0) }),
      night_forecast: fill(t.gd_night, { rh: num(h.night.rh_mean, 0), rhmax: num(h.night.rh_max, 0), cloud: num(h.night.cloud_mean, 0) }),
      station: fill(t.gd_station, { rh: num(h.night.station_rh, 0), rhmax: num(h.night.station_rh_max, 0), wind: kmh(h.night.station_wind) }),
      last_night: fill(t.gd_last, { p: pct(h.night.last_night_closed) }),
      calendar: fill(t.gd_calendar, { month: monthName(n.date), k: i + 1, total: d.hours.length }),
    };
    const HOUR = ["humidity", "wind", "temperature", "cloud", "rain", "pressure"];
    const line = (g) => {
      if (!(g in h.why)) {
        return `<li class="why-row missing"><span class="why-text"><b>${t.groups[g]}</b><br><span class="muted">${fill(t.station_missing, { time: timeLocal(n.final_from_utc) })}</span></span><span class="why-val">—</span></li>`;
      }
      const v = h.why[g], w = (Math.abs(v) / maxAbs * 50).toFixed(1);
      return `<li class="why-row${HOUR.includes(g) ? " sub" : ""}"><span class="why-text"><b>${t.groups[g]}</b> <span class="muted">${detail[g]}</span></span>
        <span class="why-bar"><span class="${v >= 0 ? "up" : "down"}" style="width:${w}%"></span></span>
        <span class="why-val">${signed(v)}</span></li>`;
    };
    const hourSum = HOUR.reduce((a, g) => a + (h.why[g] || 0), 0);
    const rows = `<li class="why-head"><b>${t.hour_group}</b><span class="why-val">${signed(hourSum)}</span></li>` +
      HOUR.map(line).join("") + ["night_forecast", "station", "last_night", "calendar"].map(line).join("");
    // A worked example with this hour's biggest amount, so the method reads as plain words.
    const top = Object.entries(h.why).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))[0];
    const how = fill(t.model_how, { name: t.groups[top[0]].toLowerCase(), dir: top[1] >= 0 ? t.would_drop : t.would_rise,
      x: num(Math.abs(top[1] * 100), 0), v: signed(top[1]) });
    const color = t.colors[h.level];
    const model = `<div class="why-col">
      <h4>${fill(t.model_title, { p: pct(h.p_closed), color })}</h4>
      <p class="small">${fill(t.model_base, { p: pct(ex.base) })}</p>
      <ul class="why">${rows}</ul>
      <p class="small"><b>${fill(t.model_total, { p: pct(h.p_closed), color, rule: t.rules_color[h.level] })}</b></p>
      <p class="muted small">${how}</p></div>`;

    // How the weather forecast alone decides: the label's three rules on the forecast values.
    const L = ex.limits, r = h.raw;
    const humid = r.rh != null && r.rh >= L.rh, windy = r.wind_ms != null && r.wind_ms >= L.wind_ms;
    const ice = humid && r.temp != null && r.temp <= L.ice_temp;
    const yes = (b) => `<td class="${b ? "rule-yes" : ""}">${b ? t.yes : t.no}</td>`;
    const rawRows = [
      `<tr><th scope="row">${t.raw_rows.humidity}</th><td>${num(r.rh, 0)} %</td><td>${t.raw_cond.humidity}</td>${yes(humid)}</tr>`,
      `<tr><th scope="row">${t.raw_rows.wind}${r.wind_level === "10m" ? " *" : ""}</th><td>${kmh(r.wind_ms)} km/h</td><td>${t.raw_cond.wind}</td>${yes(windy)}</tr>`,
      `<tr><th scope="row">${t.raw_rows.ice}</th><td>${num(r.temp, 1)} °C</td><td>${t.raw_cond.ice}</td>${yes(ice)}</tr>`,
    ];
    const raw = `<div class="why-col">
      <h4>${fill(t.raw_detail_title, { verdict: h.raw_closed ? t.raw_close_word : t.raw_open_word, color: t.colors[h.raw_closed ? "high" : "low"] })}</h4>
      <div class="table-wrap"><table class="small rules-raw"><thead><tr>${t.raw_cols.map((x) => `<th>${x}</th>`).join("")}</tr></thead><tbody>${rawRows.join("")}</tbody></table></div>
      <p class="small"><b>${h.raw_closed ? t.raw_verdict_close : t.raw_verdict_open}</b></p>
      <p class="muted small">${t.raw_note}${r.wind_level === "10m" ? " " + t.raw_wind10 : ""}</p></div>`;

    box.hidden = false;
    box.innerHTML = `<div class="detail-head"><h3>${fill(t.detail_title, { start: h.local, end: timeLocal(end) })}</h3>
      <button type="button" class="detail-close" aria-label="${t.detail_close}">×</button></div>
      <div class="why-cols">${model}${raw}</div>`;
    box.querySelector(".detail-close").addEventListener("click", () => { state.hour = null; renderLines(d); });
  }

  // ---------------------------------------------------------------- tonight
  function renderTonight(d) {
    const t = T(), f = d.forecast, n = d.night;
    const date = new Date(n.date + "T12:00:00Z").toLocaleDateString(locale(), { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
    $("night-title").textContent = fill(t.night_of, { date });
    $("night-window").textContent = fill(t.window, { start: timeLocal(n.start_utc), end: timeLocal(n.end_utc), hours: num(n.length_h), updated: timeLocal(d.issued_utc) });

    const right = hourRight(state.evaluation);
    $("mode").textContent = fill(d.mode === "final" ? t.mode_final : t.mode_provisional, { time: timeLocal(n.final_from_utc) });
    $("mode").className = d.mode;
    $("mode-text").innerHTML = fill(d.mode === "final" ? t.mode_final_text : t.mode_provisional_text,
      { time: timeLocal(n.final_from_utc), prov: pct(right.provisional), fin: pct(right.final) });

    const open = Math.round(f.open_h), total = Math.round(n.length_h);
    $("headline").innerHTML = `<span class="dot-big" style="background:var(${COLORS[f.risk]})"></span>${fill(t.headline, { open, total })}`;

    renderLines(d);

    $("updated").textContent = fill(t.updated, { time: timeLocal(d.issued_utc, true) });
    renderHow(d);
    renderLive(d);
  }

  function renderHow(d) {
    const t = T(), e = state.evaluation;
    const right = hourRight(e);
    const night = e && e.plain && e.plain.find((r) => r.key === "night");
    const items = [
      fill(t.how1, { n: d.forecast.raw_closed_hours, total: d.hours.length, r: ten(right.raw) }),
      t.how2,
      fill(t.how3, { r: ten(right.final), err: night ? num(night.ours.final, 1) : t.na,
        clim: night ? num(night.refs.find((x) => x.name === "climatology").value, 1) : t.na }),
    ];
    $("how").innerHTML = items.map((i) => `<li>${i}</li>`).join("");
  }

  // ---------------------------------------------------------------- the summit, live
  function renderLive(d) {
    const t = T(), n = d.night;
    const fmt = (dt, long) => timeLocal(dt.toISOString(), long);
    const s = d.station_now;
    $("station-text").textContent = fill(t.station_text, { time: timeLocal(s.time_utc), rh: num(s.rh, 0), wind: num(s.wind), temp: num(s.temp) });
    const st = d.station_24h.map((p) => ({ ...p, t: new Date(p.t) }));
    Charts.lineChart($("chart-station"), {
      series: [{ label: t.rh, color: "--series-1", values: st.map((p) => ({ t: p.t, v: p.rh })) }],
      yMin: 0, yMax: 100, unit: " %", threshold: { v: 90, label: t.limit90 }, timeFormat: fmt, maxGapMs: 30 * 60e3,
      valueFormat: (v) => Math.round(v), ariaLabel: t.station_title,
    });
    const hourly = d.hourly.map((h) => ({ ...h, t: new Date(h.t) }));
    Charts.lineChart($("chart-raw"), {
      series: [{ label: t.rh, color: "--series-1", values: hourly.map((h) => ({ t: h.t, v: h.rh })) },
               { label: t.cloud, color: "--series-3", values: hourly.map((h) => ({ t: h.t, v: h.cloud })) }],
      yMin: 0, yMax: 100, unit: " %", threshold: { v: 90, label: t.limit90 },
      bands: [{ from: new Date(n.start_utc), to: new Date(n.end_utc) }], timeFormat: fmt,
      valueFormat: (v) => Math.round(v), ariaLabel: t.raw_title,
    });
    renderGtc(d.gtc_panel);
  }

  function renderGtc(panel) {
    const t = T(), box = $("gtc-panel");
    if (!panel) { box.innerHTML = `<h3>${t.gtc_title}</h3><p class="empty">${t.gtc_none}</p>`; return; }
    const rows = panel.rows.filter((r) => r.value != null).map((r) => {
      const value = typeof r.value === "number" ? num(r.value, 1) + (r.unit ? " " + r.unit.replace("^2", "²").replace("º", "°") : "") : r.value;
      return `<tr><td>${r.name}</td><td>${value}</td><td>${r.age || ""}</td></tr>`;
    }).join("");
    box.innerHTML = `<h3>${t.gtc_title}</h3><p class="muted small">${fill(t.gtc_text, { time: panel.station_time_utc })}</p>
      <div class="table-wrap"><table><tbody>${rows}</tbody></table></div>`;
  }

  // ---------------------------------------------------------------- evidence
  function table(node, headers, rows) {
    node.innerHTML = `<thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody>`;
  }

  function renderRules() {
    const t = T();
    table($("table-rules"), t.rules_cols, t.rules_rows.map((r) => `<tr>${r.map((c, i) => i ? `<td>${c}</td>` : `<th scope="row">${c}</th>`).join("")}</tr>`));
  }

  // One source for every year: the Liverpool Telescope night reports, as plain counts.
  function renderChecks(v) {
    const t = T(), lt = v.liverpool, of100 = (x) => (x == null ? "—" : Math.round(x * 100));
    const [agree, lost, open, more] = t.check_lt;
    $("checks").innerHTML = [
      fill(agree, { a: of100(lt.agree), n: lt.nights, from: lt.first.slice(0, 4), to: lt.last.slice(0, 4) }),
      fill(lost, { k: lt.label_lost_nights, p: of100(lt.label_lost_lt_lost) }),
      fill(open, { k: lt.label_open_nights, p: of100(lt.label_open_lt_kept) }),
      fill(more, { lt: lt.lt_lost_nights, lab: lt.label_lost_nights }),
    ].map((i) => `<li>${i}</li>`).join("");
    table($("table-years"), t.years_cols, lt.by_year.slice().reverse().map((r) =>
      `<tr><td>${r.year}</td><td>${r.nights}</td><td>${of100(r.agree)}</td><td>${r.label_lost_nights}</td><td>${r.lt_lost_nights}</td><td>${r.both_lost_nights}</td></tr>`));
  }

  // What really happened, the weather forecast alone and our model, hour by hour (2024-2026).
  function renderCompare(c) {
    const t = T(), of100 = (x) => Math.round(x * 100);
    $("compare-headline").innerHTML = fill(t.compare_headline, { raw: of100(c.raw.wrong), fin: of100(c.final.wrong), prov: of100(c.provisional.wrong) });
    const row = (key, x, strong) => `<tr${strong ? ' class="ours"' : ""}><th scope="row">${t.compare_rows[key]}</th><td>${num(x.closed_h, 0)} h</td>` +
      `<td>${fill(t.compare_wrong, { n: of100(x.wrong) })}</td><td>${num(x.false_alarm_h, 0)} h</td><td>${num(x.missed_h, 0)} h</td></tr>`;
    table($("table-compare"), t.compare_cols, [
      `<tr class="truth"><th scope="row">${t.compare_rows.real}</th><td>${num(c.real_closed_h, 0)} h</td><td>—</td><td>—</td><td>—</td></tr>`,
      row("raw", c.raw), row("final", c.final, true), row("provisional", c.provisional),
    ]);
    $("compare-note").textContent = fill(t.compare_note, { hours: num(c.hours, 0), open: of100(c.always_open_wrong) });
  }

  function renderEvaluation(e) {
    const t = T();
    renderCompare(e.comparison);
    // Plain words: our forecast (final and, in brackets, provisional) against the simplest references.
    const yesno = (o) => fill(t.plain_yesno, { r: ten(o.right), c: ten(o.caught) });
    const err = (v, r) => fill(t.plain_error, { v: num(v, r.digits) + r.unit });
    const rows = e.plain.map((r) => {
      const ours = r.kind === "yesno"
        ? `<b>${yesno(r.ours.final)}</b><br><span class="muted">${t.provisional_word}: ${yesno(r.ours.provisional)}</span>`
        : `<b>${err(r.ours.final, r)}</b><br><span class="muted">${t.provisional_word}: ${err(r.ours.provisional, r)}</span>`;
      const refs = r.refs.map((x) => `${t.refs[x.name]}: ${r.kind === "yesno" ? yesno(x) : err(x.value, r)}`).join("<br>");
      return `<tr><td>${t.what[r.key]}</td><td>${ours}</td><td>${refs}</td></tr>`;
    });
    table($("table-plain"), [t.col_what, t.col_ours, t.col_refs], rows);

    Charts.nightsChart($("chart-recent"), e.recent, t);
    Charts.reliability($("chart-reliability"), e.reliability, t);

    if (!e.track_record.length) {
      table($("table-track"), [t.col_night], [`<tr><td class="empty">${t.track_empty}</td></tr>`]);
    } else {
      table($("table-track"), [t.col_night, t.col_mode, t.col_fc_h, t.col_real_h, t.col_fc_seeing, t.col_real_seeing],
        e.track_record.map((r) => `<tr><td>${r.night}</td><td>${r.mode === "final" ? t.final_word : t.provisional_word}</td><td>${num(r.closed_h)} h</td><td>${r.dome_closed_h != null ? num(r.dome_closed_h) + " h" : t.na}</td><td>${num(r.seeing_arcsec, 2)}″</td><td>${r.seeing_median != null ? num(r.seeing_median, 2) + "″" : t.na}</td></tr>`));
    }

    const tech = [
      ...e.technical.hour.map((r) => `<tr><td>${t.what.hour}</td><td>${r.method}</td><td>Brier ${num(r.brier, 3)} · skill ${num(r.brier_skill, 2)} · AUC ${num(r.auc, 2)}</td></tr>`),
      ...e.technical.night.map((r) => `<tr><td>${t.what.night}</td><td>${r.method}</td><td>MAE ${num(r.mae, 2)} h · RMSE ${num(r.rmse, 2)} h · skill ${num(r.mae_skill, 2)}</td></tr>`),
      ...e.technical.seeing.map((r) => `<tr><td>${t.what.seeing}</td><td>${r.method}</td><td>MAE ${num(r.mae, 3)}″ · RMSE ${num(r.rmse, 3)}″ · skill ${num(r.rmse_skill_vs_climatology, 2)}</td></tr>`),
    ];
    table($("table-tech"), [t.col_what, t.col_method, t.col_scores], tech);
    renderChecks(e.validation);
  }

  // ---------------------------------------------------------------- wiring
  function render() {
    applyTexts();
    renderRules();
    if (state.evaluation) renderEvaluation(state.evaluation);
    if (state.tonight) renderTonight(state.tonight);
  }

  document.querySelectorAll(".lang button").forEach((b) => b.addEventListener("click", () => {
    state.lang = b.dataset.lang;
    try { localStorage.setItem("lang", state.lang); } catch (e) { /* ignore */ }
    render();
  }));
  $("theme").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("theme", document.documentElement.dataset.theme); } catch (e) { /* ignore */ }
    render();
  });
  try { const th = localStorage.getItem("theme"); if (th) document.documentElement.dataset.theme = th; } catch (e) { /* ignore */ }
  // Charts inside a closed <details> have no width: draw them again when it opens.
  document.querySelectorAll("details").forEach((el) => el.addEventListener("toggle", () => { if (el.open) render(); }));
  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 150); });

  applyTexts();
  const nocache = "?v=" + Date.now();  // the forecast changes every hour: always fetch the latest
  Promise.all([fetch("data/tonight.json" + nocache).then((r) => r.json()), fetch("data/evaluation.json" + nocache).then((r) => r.json())])
    .then(([tonight, evaluation]) => { state.tonight = tonight; state.evaluation = evaluation; render(); })
    .catch((err) => { $("night-title").textContent = "Error: " + err.message; });
})();
