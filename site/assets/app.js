// Fills the page from data/tonight.json (tonight.py) and data/evaluation.json (site_data.py).
// The page answers one question first (can we observe tonight, and when?) and keeps
// every piece of evidence folded below it.
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

  // ---------------------------------------------------------------- tonight
  function renderTonight(d) {
    const t = T(), f = d.forecast, n = d.night, month = monthName(n.date);
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

    // The night, hour by hour: one cell per hour, coloured by the chance that the dome is closed.
    $("strip").innerHTML = d.hours.map((h) => `
      <div class="cell" title="${fill(t.cell_title, { time: h.local, p: pct(h.p_closed) })}${h.moon_up ? " · " + t.moon_up_word : ""}">
        <span class="cell-hour">${h.local.slice(0, 2)}h</span>
        <span class="cell-bar" style="background:var(${COLORS[h.level]})"></span>
        <span class="cell-p">${pct(h.p_closed)}</span>
        <span class="cell-moon">${h.moon_up ? "☾" : ""}</span>
      </div>`).join("");

    // Seeing: value, a 0.4-2" scale and how it ranks among Roque nights.
    $("seeing").textContent = num(f.seeing_arcsec, 2) + "″";
    const x = Math.min(1, Math.max(0, (f.seeing_arcsec - 0.4) / 1.6));
    $("seeing-mark").style.left = (x * 100).toFixed(1) + "%";
    $("seeing-class").textContent = t["seeing_" + f.seeing_class];
    const q = state.evaluation && state.evaluation.seeing_quantiles;
    $("seeing-ref").textContent = q ? fill(t.seeing_better, { p: 100 - q.filter((v) => v < f.seeing_arcsec).length }) : "";

    if (d.moon) renderMoon(d.moon);
    $("usual").textContent = num(f.usual.closed_h) + " h";
    $("usual-text").textContent = fill(t.usual_text, { month, h: num(f.closed_h) });
    $("updated").textContent = fill(t.updated, { time: timeLocal(d.issued_utc, true) });
    renderHow(d);
    renderLive(d);
  }

  function moonPhase(m) {
    const k = m.illumination;
    if (k < 0.03) return "new";
    if (k > 0.97) return "full";
    if (k >= 0.43 && k <= 0.57) return m.waxing ? "first_quarter" : "last_quarter";
    return (m.waxing ? "waxing_" : "waning_") + (k < 0.5 ? "crescent" : "gibbous");
  }

  function renderMoon(m) {
    const t = T();
    Charts.moonIcon($("moon-icon"), m.illumination, m.waxing);
    let when;
    if (m.rises_utc.length) when = fill(t.moon_rises, { time: timeLocal(m.rises_utc[0]) });
    else if (m.sets_utc.length) when = fill(t.moon_sets, { time: timeLocal(m.sets_utc[0]) });
    else when = m.up_at_start ? t.moon_all_night : t.moon_none;
    $("moon-pct").textContent = pct(m.illumination);
    $("moon-text").textContent = fill(t.moon_text, { phase: t.moon_phases[moonPhase(m)], when, dark: num(m.dark_h) });
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

  // "Mon YYYY" for a "YYYY-MM" or "YYYY-MM-DD" string.
  function monthYear(s) {
    return new Date(s.slice(0, 7) + "-15T12:00:00Z").toLocaleDateString(locale(), { month: "short", year: "numeric", timeZone: "UTC" });
  }

  function renderChecks(v) {
    const t = T(), items = [];
    const g = v.gtc || [], lt = v.liverpool, tn = v.tng;
    if (g.length) {
      const h = g.reduce((a, x) => a + x.exposing_hours, 0);
      // Share of all GTC exposing minutes labelled closed, pooled over the years.
      const p = g.reduce((a, x) => a + x.exposing_when_label_closed * x.exposing_hours, 0) / h;
      const last = g[g.length - 1].last_month;
      items.push(fill(t.check_gtc, { from: monthYear(g[0].first_month), to: monthYear(last), h: Math.round(h),
        p: num(p * 100, 1), n: g.reduce((a, x) => a + x.nights_fully_closed, 0) }));
      const next = new Date(last + "-15T12:00:00Z"); next.setUTCMonth(next.getUTCMonth() + 1);
      items.push(fill(t.check_gtc_gap, { after: monthYear(next.toISOString()) }));
    }
    if (lt) items.push(fill(t.check_lt, { from: lt.first.slice(0, 4), to: lt.last.slice(0, 4), r: num(lt.correlation, 2),
      n: lt.label_closed_nights, p: Math.round(lt.label_closed_also_lost * 100), lab: num(lt.mean_closed_h_label, 1), lt: num(lt.mean_lost_h, 1) }));
    if (tn) items.push(fill(t.check_tng, { from: monthYear(tn.first), to: monthYear(tn.last), r: num(tn.correlation, 2),
      n: tn.label_closed_nights, p: Math.round(tn.label_closed_also_lost * 100) }));
    items.push(t.check_wht);
    $("checks").innerHTML = items.map((i) => `<li>${i}</li>`).join("");

    const suspect = [2019, 2020, 2021, 2022, 2024, 2025];
    const cell = (x) => (x == null ? `<td class="muted">—</td>` : `<td>${num(x, 2)}</td>`);
    table($("table-years"), [t.col_year, t.col_gtc, t.col_lt, t.col_tng, t.col_wht],
      v.by_year.slice().reverse().map((r) => `<tr><td>${r.year}</td>${r.gtc == null ? `<td class="muted">—</td>` : `<td>${num(r.gtc * 100, 1)} %</td>`}${cell(r.liverpool)}${cell(r.tng)}${r.wht == null ? `<td class="muted">—</td>` : `<td>${num(r.wht, 2)}${suspect.includes(r.year) ? " ⚠" : ""}</td>`}</tr>`));
  }

  function renderEvaluation(e) {
    const t = T();
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
