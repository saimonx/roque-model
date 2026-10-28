// Fills the page from data/tonight.json (written by tonight.py) and data/evaluation.json (site_data.py).
(function () {
  const LOCAL_TZ = "Atlantic/Canary";
  const state = { lang: pickLang(), tonight: null, evaluation: null };

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
  const timeLocal = (iso, withDate) => new Date(iso).toLocaleString(locale(), {
    timeZone: LOCAL_TZ, hour: "2-digit", minute: "2-digit", ...(withDate ? { day: "numeric", month: "short" } : {}) });
  const monthName = (dateStr) => T().months[+dateStr.slice(5, 7) - 1];

  const STATUS = { low: ["--good", "✓"], medium: ["--warning", "!"], high: ["--critical", "✕"],
    excellent: ["--good", "✓"], good: ["--good", "✓"], average: ["--warning", "!"], poor: ["--critical", "✕"] };
  function status(node, key, label) {
    const [color, icon] = STATUS[key];
    node.innerHTML = `<span class="icon" style="background:var(${color})">${icon}</span><span>${label}</span>`;
  }

  // ---------------------------------------------------------------- static texts
  function applyTexts() {
    document.documentElement.lang = state.lang;
    document.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = T()[n.dataset.i18n] || ""; });
    document.querySelectorAll("[data-i18n-html]").forEach((n) => { n.innerHTML = T()[n.dataset.i18nHtml] || ""; });
    document.querySelectorAll("[data-i18n-title]").forEach((n) => { n.title = T()[n.dataset.i18nTitle]; });
    document.querySelectorAll(".lang button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === state.lang)));
  }

  // ---------------------------------------------------------------- tonight
  function renderTonight(d) {
    const t = T(), f = d.forecast, r = d.references, n = d.night, month = monthName(n.date);
    const date = new Date(n.date + "T12:00:00Z").toLocaleDateString(locale(), { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
    $("night-title").textContent = fill(t.night_of, { date });
    $("night-window").textContent = fill(t.window, { start: timeLocal(n.start_utc), end: timeLocal(n.end_utc), hours: num(n.length_h) });
    const mode = $("mode");
    mode.textContent = d.mode === "final" ? t.mode_final : t.mode_provisional;
    mode.className = "badge " + d.mode;
    $("mode-note").textContent = fill(d.mode === "final" ? t.note_final : t.note_provisional, { time: timeLocal(n.final_from_utc) });

    $("p-closed").textContent = pct(f.p_closed);
    status($("risk"), f.risk, t["risk_" + f.risk]);
    $("meter-fill").style.width = Math.round(f.p_closed * 100) + "%";
    $("meter-clim").style.left = Math.round(r.closure_climatology * 100) + "%";
    $("closure-ref").textContent = fill(t.closure_ref, { month, clim: pct(r.closure_climatology), pers: pct(r.closure_persistence),
      prec: r.closure_precasting != null ? fill(t.closure_prec, { p: pct(r.closure_precasting) }) : "" });
    $("closed-hours").textContent = fill(t.closed_hours, { h: num(f.closed_h) });

    $("seeing").textContent = num(f.seeing_arcsec, 2) + "″";
    status($("seeing-class"), f.seeing_class, t["seeing_" + f.seeing_class]);
    $("seeing-ref").textContent = fill(t.seeing_ref, { month, clim: num(r.seeing_climatology, 2) });

    $("lost").textContent = num(f.lost_h) + " h";
    $("lost-of").textContent = fill(t.lost_of, { h: num(n.length_h) });
    $("lost-ref").textContent = fill(t.lost_ref, { month, clim: num(r.lost_h_climatology) });
    if (d.moon) renderMoon(d.moon, n);

    // Inputs, with readable names and units (fractions shown as %).
    const dl = $("inputs");
    dl.innerHTML = "";
    for (const [key, value] of Object.entries(d.inputs)) {
      if (key.startsWith("doy_")) continue;  // the season is shown by the date itself
      const [label, unit] = t.features[key] || [key, ""];
      let shown = value == null ? t.na : key === "prev_dome_closed_frac" ? Math.round(value * 100) + " %" : num(value, key === "prev_seeing_median" ? 2 : 1) + (unit && unit !== "%" ? " " + unit : unit === "%" ? " %" : "");
      if (unit === "″" && value != null) shown = num(value, 2) + "″";
      const row = document.createElement("div");
      row.innerHTML = `<dt></dt><dd></dd>`;
      row.querySelector("dt").textContent = label;
      row.querySelector("dd").textContent = shown;
      dl.appendChild(row);
    }

    // Hour-by-hour forecast.
    const hourly = d.hourly.map((h) => ({ ...h, t: new Date(h.t) }));
    const bands = [{ from: new Date(n.start_utc), to: new Date(n.end_utc) }];
    const fmt = (dt, long) => timeLocal(dt.toISOString(), long);
    Charts.lineChart($("chart-hourly-rh"), {
      series: [{ label: t.rh, color: "--series-1", values: hourly.map((h) => ({ t: h.t, v: h.rh })) },
               { label: t.cloud, color: "--series-3", values: hourly.map((h) => ({ t: h.t, v: h.cloud })) }],
      yMin: 0, yMax: 100, unit: " %", threshold: { v: 90, label: t.limit90 }, bands, timeFormat: fmt,
      valueFormat: (v) => Math.round(v), ariaLabel: t.hourly_title,
    });
    Charts.lineChart($("chart-hourly-wind"), {
      series: [{ label: t.wind, color: "--series-2", values: hourly.map((h) => ({ t: h.t, v: h.wind })) }],
      yMin: 0, unit: " m/s", bands, timeFormat: fmt, valueFormat: (v) => num(v), ariaLabel: t.wind,
    });

    // Station, last 24 h.
    const s = d.station_now;
    $("station-text").textContent = fill(t.station_text, { time: timeLocal(s.time_utc), rh: num(s.rh, 0), wind: num(s.wind), temp: num(s.temp) });
    const st = d.station_24h.map((p) => ({ ...p, t: new Date(p.t) }));
    Charts.lineChart($("chart-station"), {
      series: [{ label: t.rh, color: "--series-1", values: st.map((p) => ({ t: p.t, v: p.rh })) }],
      yMin: 0, yMax: 100, unit: " %", threshold: { v: 90, label: t.limit90 }, timeFormat: fmt, maxGapMs: 30 * 60e3,
      valueFormat: (v) => Math.round(v), ariaLabel: t.station_title,
    });
    renderGtc(d.gtc_panel);
    $("updated").textContent = fill(t.updated, { time: timeLocal(d.issued_utc, true),
      eval: state.evaluation ? new Date(state.evaluation.generated_utc).toLocaleDateString(locale()) : t.na });
  }

  function moonPhase(m) {
    const k = m.illumination;
    if (k < 0.03) return "new";
    if (k > 0.97) return "full";
    if (k >= 0.43 && k <= 0.57) return m.waxing ? "first_quarter" : "last_quarter";
    return (m.waxing ? "waxing_" : "waning_") + (k < 0.5 ? "crescent" : "gibbous");
  }

  function renderMoon(m, n) {
    const t = T();
    Charts.moonIcon($("moon-icon"), m.illumination, m.waxing);
    let when;
    if (m.rises_utc.length) when = fill(t.moon_rises, { time: timeLocal(m.rises_utc[0]) });
    else if (m.sets_utc.length) when = fill(t.moon_sets, { time: timeLocal(m.sets_utc[0]) });
    else when = m.up_at_start ? t.moon_all_night : t.moon_none;
    $("moon-text").innerHTML = fill(t.moon_text, { pct: pct(m.illumination), phase: t.moon_phases[moonPhase(m)], when,
      dark: `<b>${num(m.dark_h)} h</b>`, total: num(n.length_h) });
  }

  function renderGtc(panel) {
    const t = T(), box = $("gtc-panel");
    if (!panel) { box.innerHTML = `<h3>${t.gtc_title}</h3><p class="empty">${t.gtc_none}</p>`; return; }
    const rows = panel.rows.filter((r) => r.value != null).map((r) => {
      const st = r.status === "ok" ? ["--good", "✓", t.status_ok] : r.status === "warning" ? ["--warning", "!", t.status_warning] : null;
      const value = typeof r.value === "number" ? num(r.value, 1) + (r.unit ? " " + r.unit.replace("^2", "²").replace("º", "°") : "") : r.value;
      return `<tr><td>${r.name}</td><td>${value}</td><td>${r.age || ""}</td><td>${st ? `<span class="status small"><span class="icon" style="background:var(${st[0]})">${st[1]}</span>${st[2]}</span>` : ""}</td></tr>`;
    }).join("");
    box.innerHTML = `<div class="gtc"><h3>${t.gtc_title}</h3><p class="muted small">${fill(t.gtc_text, { time: panel.station_time_utc })}</p>
      <div class="table-wrap"><table><tbody>${rows}</tbody></table></div></div>`;
  }

  // ---------------------------------------------------------------- evaluation
  function table(node, headers, rows) {
    node.innerHTML = `<thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody>`;
  }

  function renderEvaluation(e) {
    const t = T(), name = (m) => t.methods[m] || m;
    const closure = e.closure.filter((r) => r.inputs === "forecast archive");
    Charts.skillBars($("chart-skill"), closure.map((r) => ({ label: name(r.method), value: r.brier_skill_vs_climatology, model: r.kind === "model" })), t);
    table($("table-closure"), [t.col_method, t.col_nights, t.col_brier, t.col_skill, t.col_auc, t.col_hit, t.col_far],
      closure.map((r) => `<tr class="${r.kind}"><td>${name(r.method)}</td><td>${r.nights}</td><td>${num(r.brier, 3)}</td><td>${num(r.brier_skill_vs_climatology, 2)}</td><td>${num(r.auc, 2)}</td><td>${r.hit_rate ? pct(r.hit_rate) : t.na}</td><td>${pct(r.false_alarm_ratio)}</td></tr>`));

    Charts.reliability($("chart-reliability"), e.reliability, t);
    const cal = e.calibration_check && e.calibration_check.full;
    $("reliability-text").textContent = cal ? fill(t.reliability_text, { raw: num(cal.brier_raw, 4), iso: num(cal.brier_isotonic, 4) }) : "";

    // Which inputs matter most (permutation importance on the test years), as a share of the total.
    const share = { format: (v) => Math.round(v * 100) + " %" };
    const impRows = (rows) => rows.map((r) => ({ label: (t.features[r.feature] || [r.feature])[0], value: r.share, model: true }));
    Charts.skillBars($("chart-imp-closure"), impRows(e.importance.closure), t, { ...share, aria: t.importance_closure });
    Charts.skillBars($("chart-imp-seeing"), impRows(e.importance.seeing), t, { ...share, aria: t.importance_seeing });

    Charts.nightsChart($("chart-recent"), e.recent, t);
    const fmtDay = (dt, long) => dt.toLocaleDateString(locale(), { day: "numeric", month: "short", ...(long ? { year: "numeric" } : {}), timeZone: "UTC" });
    const recent = e.recent.map((n) => ({ ...n, t: new Date(n.night + "T00:00:00Z") }));
    Charts.lineChart($("chart-seeing"), {
      series: [{ label: t.predicted, color: "--series-1", values: recent.map((n) => ({ t: n.t, v: n.pred_seeing })) },
               { label: t.measured, color: "--series-2", points: true, values: recent.map((n) => ({ t: n.t, v: n.seeing })) }],
      yMin: 0, unit: "″", timeFormat: fmtDay, valueFormat: (v) => num(v, 2), maxGapMs: 86400e3 * 1.5, ariaLabel: t.eval_seeing,
    });
    const seeing = e.seeing.filter((r) => r.inputs === "forecast archive");
    table($("table-seeing"), [t.col_method, t.col_nights, t.col_rmse, t.col_mae, t.col_skill],
      seeing.map((r) => `<tr class="${r.kind}"><td>${name(r.method)}</td><td>${r.nights}</td><td>${num(r.rmse, 3)}″</td><td>${num(r.mae, 3)}″</td><td>${num(r.rmse_skill_vs_climatology, 2)}</td></tr>`));
    table($("table-lost"), [t.col_method, t.col_set, t.col_nights, t.col_rmse, t.col_mae],
      e.lost_hours.map((r) => `<tr class="${r.kind}"><td>${name(r.method)}</td><td>${t.sets[r.inputs] || r.inputs}</td><td>${r.nights}</td><td>${num(r.rmse, 2)} h</td><td>${num(r.mae, 2)} h</td></tr>`));

    if (!e.track_record.length) {
      table($("table-track"), [t.col_night], [`<tr><td class="empty">${t.track_empty}</td></tr>`]);
    } else {
      table($("table-track"), [t.col_night, t.col_mode, t.col_p, t.col_fc_h, t.col_real_h, t.col_fc_seeing, t.col_real_seeing],
        e.track_record.map((r) => `<tr><td>${r.night}</td><td>${r.mode === "final" ? t.mode_final : t.mode_provisional}</td><td>${pct(r.p_closed)}</td><td>${num(r.closed_h)} h</td><td>${r.dome_closed_h != null ? num(r.dome_closed_h) + " h" : t.na}</td><td>${num(r.seeing_arcsec, 2)}″</td><td>${r.seeing_median != null ? num(r.seeing_median, 2) + "″" : t.na}</td></tr>`));
    }
  }

  // ---------------------------------------------------------------- wiring
  function renderFlow() {
    $("flow").innerHTML = T().flow.map(([title, text]) => `<li><b>${title}</b>${text}</li>`).join("");
  }

  function render() {
    applyTexts();
    renderFlow();
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
  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 150); });

  applyTexts();
  const nocache = "?v=" + Date.now();  // the forecast changes every hour: always fetch the latest
  Promise.all([fetch("data/tonight.json" + nocache).then((r) => r.json()), fetch("data/evaluation.json" + nocache).then((r) => r.json())])
    .then(([tonight, evaluation]) => { state.tonight = tonight; state.evaluation = evaluation; render(); })
    .catch((err) => { $("night-title").textContent = "Error: " + err.message; });
})();
