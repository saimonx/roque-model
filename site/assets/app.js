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
    // External links (references, sources) open in a new tab, so the page stays open.
    document.querySelectorAll('a[href^="http"]').forEach((l) => { l.target = "_blank"; l.rel = "noopener"; });
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
        <span class="cell-hour">${h.local.slice(0, 2)}h</span>
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
      last_night: fill(t.gd_last, { p: pct(h.night.last_night_closed), s: h.night.last_night_seeing == null ? t.na : num(h.night.last_night_seeing, 2) + "″" }),
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
    if (d.model) { renderRoqueModel(d); renderRoqueAccuracy(d); }
    renderLive(d);
  }

  // ---------------------------------------------------------------- how RoqueModel works (3 parts)
  function renderRoqueModel(d) {
    const t = T(), m = d.model, tr = m.trained_on, f = m.final, pr = m.provisional;
    const n0 = (v) => num(v, 0);

    // 1. What it is: four key figures and the technical settings.
    $("rm-stats").innerHTML = [
      [t.rm_stat_model, "1"], [t.rm_stat_inputs, `${f.inputs}`], [t.rm_stat_trees, `${f.trees}`], [t.rm_stat_out, "%"],
    ].map(([label, value]) => `<div class="rm-stat"><span class="rm-stat-v">${value}</span><span class="rm-stat-l">${label}</span></div>`).join("");
    const lr = (x) => num(x, x < 0.1 ? 2 : 1);
    table($("rm-tech"), t.rm_tech_cols, [
      [t.rm_tech.inputs, f.inputs, pr.inputs],
      [t.rm_tech.trees, f.trees, pr.trees],
      [t.rm_tech.leaves, f.leaves, pr.leaves],
      [t.rm_tech.rate, lr(f.learning_rate), lr(pr.learning_rate)],
      [t.rm_tech.min, f.min_hours_per_leaf, pr.min_hours_per_leaf],
      [t.rm_tech.l2, "1", "1"],
    ].map(([what, a, b]) => `<tr><th scope="row">${what[0]}</th><td>${a}</td><td>${b}</td><td class="muted">${what[1]}</td></tr>`));

    // 2. How it was trained: a timeline of the years and the data it learnt from.
    $("rm2-text").innerHTML = fill(t.rm2_text, { hours: n0(tr.hours), closed: n0(tr.closed_hours),
      from: dateLong(tr.first_night), to: dateLong(tr.last_night) });
    const years = [];
    for (let y = tr.first_year; y <= tr.last_year; y++) years.push(y);
    $("rm-timeline").innerHTML = `
      <div class="tl-row"><span class="tl-label">${t.rm_tl_live}</span><div class="tl-bar">${years.map((y) => `<span class="tl-y live">${y}</span>`).join("")}</div></div>
      <p class="tl-legend small"><span class="sw tl-livesw"></span> ${t.rm_tl_livetext}</p>`;
    table($("rm-data"), t.rm_data_cols, t.rm_data.map((r) => `<tr><th scope="row">${r[0]}</th><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td></tr>`));

    // 3. How it forecasts: the steps, then a worked example with tonight's riskiest hour.
    $("rm-flow").innerHTML = t.rm_flow.map((st, i) => `<li><span class="rm-step-n">${i + 1}</span><b>${st[0]}</b><span>${st[1]}</span></li>`).join("");
    const k = d.hours.reduce((best, h, i) => (h.p_closed > d.hours[best].p_closed ? i : best), 0), h = d.hours[k];
    $("rm-example-title").textContent = fill(t.rm_example_title, { time: h.local });
    const HOUR = ["humidity", "wind", "temperature", "cloud", "rain", "pressure"];
    const steps = [[t.rm_start, d.explain.base, true]];
    const hourSum = HOUR.reduce((a, g) => a + (h.why[g] || 0), 0);
    steps.push([t.hour_group, hourSum]);
    ["night_forecast", "station", "last_night", "calendar"].forEach((g) => { if (g in h.why) steps.push([t.groups[g], h.why[g]]); });
    const top = Math.max(0.5, ...steps.reduce((acc2, s2) => { const last = acc2.length ? acc2[acc2.length - 1] : 0; acc2.push(last + s2[1]); return acc2; }, []));
    let run = 0;
    const signed = (x) => (Math.abs(x) < 0.005 ? "≈0" : (x >= 0 ? "+" : "−") + num(Math.abs(x * 100), 0)) + " %";
    const rows = steps.map(([label, v, isBase]) => {
      const from = isBase ? 0 : run, to = isBase ? v : run + v;
      run = to;
      const left = (Math.min(from, to) / top * 100).toFixed(1), width = (Math.abs(to - from) / top * 100).toFixed(1);
      const cls = isBase ? "base" : v >= 0 ? "up" : "down";
      return `<li><span class="wf-label">${label}</span><span class="wf-track"><span class="wf-bar ${cls}" style="left:${left}%;width:${Math.max(0.6, width)}%"></span></span><span class="wf-val">${isBase ? pct(v) : signed(v)}</span></li>`;
    });
    rows.push(`<li class="wf-total"><span class="wf-label">${t.rm_total}</span><span class="wf-track"><span class="wf-bar total" style="left:0;width:${(h.p_closed / top * 100).toFixed(1)}%;background:var(${COLORS[h.level]})"></span></span><span class="wf-val">${pct(h.p_closed)}</span></li>`);
    $("rm-example").innerHTML = rows.join("");
  }

  // 4. How good it is: a copy trained on the early years, checked on the later ones,
  // against the weather forecast alone read with the same closing rules.
  function renderRoqueAccuracy(d) {
    const t = T(), m = d.model, c = state.evaluation && state.evaluation.comparison;
    if (!c) return;
    const [e0, e1] = m.evaluated_on.trained, [x0, x1] = m.evaluated_on.tested;
    const ok = (x) => 1 - x.wrong;
    const vals = { fin: pct(ok(c.final)), prov: pct(ok(c.provisional)), raw: pct(ok(c.raw)), open: pct(1 - c.always_open_wrong) };
    $("rm4-text").innerHTML = fill(t.rm4_text, { e0, e1, x0, x1, hours: num(c.hours, 0), ...vals });
    const years = [];
    for (let y = e0; y <= x1; y++) years.push(y);
    const cls = (y) => (y <= e1 ? "learn" : "test");
    $("rm4-timeline").innerHTML = `
      <div class="tl-row"><span class="tl-label">${t.rm_tl_copy}</span><div class="tl-bar">${years.map((y) => `<span class="tl-y ${cls(y)}">${y}</span>`).join("")}</div></div>
      <p class="tl-legend small"><span class="sw tl-learn"></span> ${t.rm_tl_learn} &nbsp; <span class="sw tl-test"></span> ${t.rm_tl_test}</p>`;
    const bars = [
      [t.rm4_bars.final, ok(c.final), "--series-1"],
      [t.rm4_bars.provisional, ok(c.provisional), "--series-1"],
      [t.rm4_bars.raw, ok(c.raw), "--critical"],
    ];
    $("rm4-bars").innerHTML = bars.map(([label, v, color]) => `<li><span class="bar-label">${label}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${(v * 100).toFixed(1)}%;background:var(${color})"></span></span>
      <span class="bar-val">${pct(v)}</span></li>`).join("");
    $("rm4-note").innerHTML = fill(t.rm4_note, vals);
  }

  function dateLong(iso) {
    return new Date(iso + "T12:00:00Z").toLocaleDateString(locale(), { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  }

  // ---------------------------------------------------------------- the summit, live
  // Small charts in a grid: one variable each, same time axis, so scales never mix.
  function miniCharts(grid, charts) {
    // Each chart sits in its own box, so the legend the chart adds below stays with it.
    grid.innerHTML = charts.map((_, i) => `<div class="mini"><div class="chart short" data-k="${i}"></div></div>`).join("");
    charts.forEach((c, i) => Charts.lineChart(grid.querySelector(`[data-k="${i}"]`), c));
  }

  function renderLive(d) {
    const t = T(), n = d.night;
    const fmt = (dt, long) => timeLocal(dt.toISOString(), long);
    const kmh = (v) => (v == null ? null : v * 3.6);
    const pts = (rows, key, f = (v) => v) => rows.map((p) => ({ t: p.t, v: p[key] == null ? null : f(p[key]) }));
    const top = (rows, key, f, floor) => Math.max(floor, ...rows.map((p) => (p[key] == null ? 0 : f(p[key]))));
    const night = [{ from: new Date(n.start_utc), to: new Date(n.end_utc) }];

    // 1. Tonight's forecast, hour by hour (ECMWF; summit wind from GFS at 750 hPa).
    const fc = d.hourly.map((h) => ({ ...h, t: new Date(h.t) }));
    const base = { timeFormat: fmt, bands: night };
    miniCharts($("fc-grid"), [
      { ...base, series: [{ label: t.c_rh, color: "--series-1", values: pts(fc, "rh") }], yMin: 0, yMax: 100, unit: " %",
        threshold: { v: 90, label: t.c_limit }, valueFormat: (v) => Math.round(v) },
      { ...base, series: [{ label: t.c_wind750, color: "--series-3", values: pts(fc, "wind750", kmh) }], yMin: 0,
        yMax: Math.ceil(top(fc, "wind750", kmh, 80) * 1.1), unit: " km/h", threshold: { v: 80, label: t.c_limit }, valueFormat: (v) => Math.round(v) },
      { ...base, series: [{ label: t.c_temp, color: "--series-2", values: pts(fc, "temp") }, { label: t.c_dew, color: "--series-1", values: pts(fc, "dew") }],
        yMin: Math.min(-2, ...fc.map((p) => Math.floor(Math.min(p.temp, p.dew) - 1))), unit: " °C", threshold: { v: 0, label: t.c_ice }, valueFormat: (v) => Math.round(v) },
      { ...base, series: [{ label: t.c_cloud, color: "--text-3", values: pts(fc, "cloud") }], yMin: 0, yMax: 100, unit: " %", valueFormat: (v) => Math.round(v) },
      { ...base, series: [{ label: t.c_rain, color: "--series-1", values: pts(fc, "precip") }], yMin: 0,
        yMax: Math.max(1, ...fc.map((p) => p.precip || 0)) * 1.2, unit: " mm", valueFormat: (v) => num(v, 1) },
      { ...base, series: [{ label: t.c_pressure, color: "--text-3", values: pts(fc, "pressure") }], unit: " hPa", valueFormat: (v) => Math.round(v) },
    ]);

    // 2. Measured at the summit: the NOT station, last 24 h (the readings RoqueModel takes before the night).
    const s = d.station_now;
    $("station-text").textContent = fill(t.station_text, { time: timeLocal(s.time_utc), rh: num(s.rh, 0), wind: num(kmh(s.wind), 0), p: num(s.pressure, 0) });
    const st = d.station_24h.map((p) => ({ ...p, t: new Date(p.t) }));
    const sb = { timeFormat: fmt, maxGapMs: 30 * 60e3 };
    miniCharts($("station-grid"), [
      { ...sb, series: [{ label: t.c_rh, color: "--series-1", values: pts(st, "rh") }], yMin: 0, yMax: 100, unit: " %", threshold: { v: 90, label: t.c_limit }, valueFormat: (v) => Math.round(v) },
      { ...sb, series: [{ label: t.c_wind_station, color: "--series-3", values: pts(st, "wind", kmh) }], yMin: 0,
        yMax: Math.ceil(top(st, "wind", kmh, 80) * 1.1), unit: " km/h", threshold: { v: 80, label: t.c_limit }, valueFormat: (v) => Math.round(v) },
      { ...sb, series: [{ label: t.c_pressure, color: "--text-3", values: pts(st, "pressure") }], unit: " hPa", valueFormat: (v) => Math.round(v) },
    ]);

    // 3. Forecast against what was measured: humidity, last 24 h.
    const vs = d.forecast_vs_measured.map((p) => ({ ...p, t: new Date(p.t) }));
    Charts.lineChart($("chart-vs"), {
      series: [{ label: t.c_vs_fc, color: "--baseline", values: pts(vs, "forecast") }, { label: t.c_vs_measured, color: "--series-2", values: pts(vs, "measured") }],
      yMin: 0, yMax: 100, unit: " %", threshold: { v: 90, label: t.c_limit }, timeFormat: fmt, valueFormat: (v) => Math.round(v), ariaLabel: t.vs_title,
    });

  }


  // ---------------------------------------------------------------- evidence
  function table(node, headers, rows) {
    node.innerHTML = `<thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody>`;
  }

  // ---------------------------------------------------------------- wiring
  function render() {
    applyTexts();
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
