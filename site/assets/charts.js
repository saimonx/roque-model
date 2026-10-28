// Small hand-written SVG charts (no library): line chart with hover, bars + markers, skill bars.
// Colours come from the CSS tokens, so light and dark themes work without redrawing logic.
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const tip = () => document.getElementById("tooltip");

  function el(tag, attrs, parent) {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }

  function scale(d0, d1, r0, r1) {
    return (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0);
  }

  function niceTicks(lo, hi, count) {
    const step0 = (hi - lo) / count;
    const mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) || step0;
    const ticks = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(+v.toFixed(6));
    return ticks;
  }

  function showTip(html, event) {
    const t = tip();
    t.innerHTML = html;
    t.hidden = false;
    const pad = 14;
    let x = event.clientX + pad;
    let y = event.clientY + pad;
    const r = t.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = event.clientX - r.width - pad;
    if (y + r.height > window.innerHeight - 8) y = event.clientY - r.height - pad;
    t.style.left = x + "px";
    t.style.top = y + "px";
  }
  const hideTip = () => { tip().hidden = true; };

  function legend(container, items) {
    const box = document.createElement("div");
    box.className = "legend";
    for (const it of items) {
      const s = document.createElement("span");
      s.textContent = it.label;
      s.style.setProperty("--c", it.color);
      if (it.kind) s.className = it.kind;
      box.appendChild(s);
    }
    container.after(box);
    return box;
  }

  /**
   * Line chart over time.
   * opts: {series: [{label, color (css var name), values: [{t: Date, v}]}], yMin, yMax, unit,
   *        threshold: {v, label}, bands: [{from: Date, to: Date}], timeFormat: (Date) => string,
   *        valueFormat: (v) => string}
   */
  function lineChart(container, opts) {
    container.innerHTML = "";
    if (container.nextElementSibling && container.nextElementSibling.classList.contains("legend")) {
      container.nextElementSibling.remove();
    }
    const W = container.clientWidth, H = container.clientHeight;
    const m = { top: 10, right: 12, bottom: 24, left: 40 };
    const all = opts.series.flatMap((s) => s.values).filter((p) => p.v != null);
    if (!all.length) return;
    const t0 = Math.min(...all.map((p) => +p.t)), t1 = Math.max(...all.map((p) => +p.t));
    let lo = opts.yMin != null ? opts.yMin : Math.min(...all.map((p) => p.v));
    let hi = opts.yMax != null ? opts.yMax : Math.max(...all.map((p) => p.v));
    if (opts.yMin == null) lo = Math.floor(lo - (hi - lo) * 0.1);
    if (opts.yMax == null) hi = hi + (hi - lo) * 0.1;
    const x = scale(t0, t1, m.left, W - m.right), y = scale(lo, hi, H - m.bottom, m.top);
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.ariaLabel || "" }, container);

    for (const b of opts.bands || []) {
      const a = Math.max(+b.from, t0), z = Math.min(+b.to, t1);
      if (z > a) el("rect", { x: x(a), y: m.top, width: x(z) - x(a), height: H - m.top - m.bottom, fill: css("--shade") }, svg);
    }
    const grid = el("g", { class: "grid axis" }, svg);
    for (const v of niceTicks(lo, hi, 4)) {
      el("line", { x1: m.left, x2: W - m.right, y1: y(v), y2: y(v) }, grid);
      el("text", { x: m.left - 6, y: y(v) + 4, "text-anchor": "end" }, grid).textContent = opts.valueFormat ? opts.valueFormat(v) : v;
    }
    // Time ticks on round hours (short spans) or whole days (long spans).
    const nx = Math.max(2, Math.floor((W - m.left - m.right) / 90));
    const span = t1 - t0, HOUR = 3600e3, DAY = 86400e3;
    const unit = span <= 2 * DAY ? HOUR : DAY;
    const steps = unit === HOUR ? [1, 2, 3, 4, 6, 12] : [1, 2, 3, 5, 7, 10, 14, 30];
    const step = (steps.find((k) => span / (k * unit) <= nx) || steps[steps.length - 1]) * unit;
    for (let t = Math.ceil(t0 / step) * step; t <= t1; t += step) {
      el("line", { x1: x(t), x2: x(t), y1: H - m.bottom, y2: H - m.bottom + 4 }, grid);
      el("text", { x: x(t), y: H - 6, "text-anchor": "middle" }, grid).textContent = opts.timeFormat(new Date(t));
    }
    if (opts.threshold) {
      el("line", { x1: m.left, x2: W - m.right, y1: y(opts.threshold.v), y2: y(opts.threshold.v),
        stroke: css("--critical"), "stroke-width": 1.5, "stroke-dasharray": "5 4" }, svg);
    }
    for (const s of opts.series) {
      // Break the line where values are missing or more than 2 steps apart.
      let d = "", prev = null;
      const gap = opts.maxGapMs || 3 * 3600e3;
      for (const p of s.values) {
        if (p.v == null) { prev = null; continue; }
        d += (prev && +p.t - +prev.t <= gap ? "L" : "M") + x(+p.t).toFixed(1) + "," + y(p.v).toFixed(1);
        prev = p;
      }
      el("path", { d, fill: "none", stroke: css(s.color), "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
      if (s.points) {
        for (const p of s.values) if (p.v != null) {
          el("circle", { cx: x(+p.t), cy: y(p.v), r: 4, fill: css(s.color), stroke: css("--surface"), "stroke-width": 2 }, svg);
        }
      }
    }

    // Hover: vertical line + dots + tooltip with every series at the nearest time.
    const times = [...new Set(all.map((p) => +p.t))].sort((a, b) => a - b);
    const cursor = el("line", { y1: m.top, y2: H - m.bottom, stroke: css("--text-3"), "stroke-width": 1, visibility: "hidden" }, svg);
    const dots = opts.series.map((s) => el("circle", { r: 5, fill: css(s.color), stroke: css("--surface"), "stroke-width": 2, visibility: "hidden" }, svg));
    const hit = el("rect", { x: m.left, y: 0, width: W - m.left - m.right, height: H, fill: "transparent" }, svg);
    hit.addEventListener("mousemove", (ev) => {
      const r = svg.getBoundingClientRect();
      const tx = t0 + ((ev.clientX - r.left) * (W / r.width) - m.left) / (W - m.left - m.right) * (t1 - t0);
      const t = times.reduce((best, c) => (Math.abs(c - tx) < Math.abs(best - tx) ? c : best), times[0]);
      cursor.setAttribute("x1", x(t)); cursor.setAttribute("x2", x(t)); cursor.setAttribute("visibility", "visible");
      let html = `<div><b>${opts.timeFormat(new Date(t), true)}</b></div>`;
      opts.series.forEach((s, i) => {
        const p = s.values.find((q) => +q.t === t);
        if (p && p.v != null) {
          dots[i].setAttribute("cx", x(t)); dots[i].setAttribute("cy", y(p.v)); dots[i].setAttribute("visibility", "visible");
          html += `<div class="row"><span class="key" style="--c:${css(s.color)}">${s.label}</span><b>${opts.valueFormat ? opts.valueFormat(p.v) : p.v}${opts.unit || ""}</b></div>`;
        } else dots[i].setAttribute("visibility", "hidden");
      });
      showTip(html, ev);
    });
    hit.addEventListener("mouseleave", () => {
      cursor.setAttribute("visibility", "hidden");
      dots.forEach((d) => d.setAttribute("visibility", "hidden"));
      hideTip();
    });

    const items = opts.series.map((s) => ({ label: s.label, color: css(s.color), kind: s.points ? "dot" : "" }));
    if (opts.threshold) items.push({ label: opts.threshold.label, color: css("--critical"), kind: "dash" });
    legend(container, items);  // also for one series: it names the chart
  }

  /** One bar per night (probability) and a marker on the nights that really closed. */
  function nightsChart(container, nights, t) {
    container.innerHTML = "";
    if (container.nextElementSibling && container.nextElementSibling.classList.contains("legend")) container.nextElementSibling.remove();
    const W = container.clientWidth, H = container.clientHeight;
    const m = { top: 18, right: 8, bottom: 24, left: 40 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": t.eval_recent }, container);
    const y = scale(0, 1, H - m.bottom, m.top);
    const step = (W - m.left - m.right) / nights.length;
    const bw = Math.max(2, step - 2);  // 2px gap between bars
    const grid = el("g", { class: "grid axis" }, svg);
    for (const v of [0, 0.25, 0.5, 0.75, 1]) {
      el("line", { x1: m.left, x2: W - m.right, y1: y(v), y2: y(v) }, grid);
      el("text", { x: m.left - 6, y: y(v) + 4, "text-anchor": "end" }, grid).textContent = Math.round(v * 100) + " %";
    }
    nights.forEach((n, i) => {
      const x0 = m.left + i * step + 1;
      const h = y(0) - y(n.p_closed);
      el("rect", { x: x0, y: y(n.p_closed), width: bw, height: Math.max(h, 0.5), rx: Math.min(2, bw / 2), fill: css("--series-1") }, svg);
      if (n.closed === 1) el("circle", { cx: x0 + bw / 2, cy: m.top - 8, r: Math.min(4, bw / 2 + 1), fill: css("--series-2") }, svg);
      if (i % Math.ceil(nights.length / 6) === 0) {
        el("text", { x: x0, y: H - 6 }, grid).textContent = n.night.slice(5);
      }
      const hit = el("rect", { x: m.left + i * step, y: 0, width: step, height: H, fill: "transparent" }, svg);
      hit.addEventListener("mousemove", (ev) => showTip(
        `<div><b>${n.night}</b></div>
         <div class="row"><span class="key" style="--c:${css("--series-1")}">${t.probability}</span><b>${Math.round(n.p_closed * 100)} %</b></div>
         <div class="row"><span class="key" style="--c:${css("--series-2")}">${t.col_real_h}</span><b>${n.closed_h != null ? n.closed_h.toFixed(1) + " h" : t.na}</b></div>`, ev));
      hit.addEventListener("mouseleave", hideTip);
    });
    legend(container, [{ label: t.probability, color: css("--series-1") }, { label: t.closed_real, color: css("--series-2"), kind: "dot" }]);
  }

  /** Horizontal bars, one per method: models in blue, references in grey. */
  function skillBars(container, rows, t) {
    container.innerHTML = "";
    const rowH = 30, m = { top: 6, right: 48, bottom: 26, left: Math.min(300, container.clientWidth * 0.45) };
    const W = container.clientWidth, H = m.top + m.bottom + rows.length * rowH;
    container.style.height = H + "px";
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": t.skill_axis }, container);
    const vals = rows.map((r) => r.value);
    const lo = Math.min(0, ...vals), hi = Math.max(...vals) * 1.05;
    const x = scale(lo, hi, m.left, W - m.right);
    const grid = el("g", { class: "grid axis" }, svg);
    for (const v of niceTicks(lo, hi, 4)) {
      el("line", { x1: x(v), x2: x(v), y1: m.top, y2: H - m.bottom }, grid);
      el("text", { x: x(v), y: H - 8, "text-anchor": "middle" }, grid).textContent = v.toFixed(1);
    }
    rows.forEach((r, i) => {
      const yy = m.top + i * rowH + 5, h = rowH - 10;
      const a = x(Math.min(0, r.value)), b = x(Math.max(0, r.value));
      el("rect", { x: a, y: yy, width: Math.max(b - a, 1), height: h, rx: 3, fill: css(r.model ? "--series-1" : "--baseline") }, svg);
      const lab = el("text", { x: m.left - 8, y: yy + h / 2 + 4, "text-anchor": "end", class: "label" }, svg);
      lab.textContent = r.label;
      if (r.model) lab.setAttribute("font-weight", "600");
      el("text", { x: b + 6, y: yy + h / 2 + 4, class: "label" }, svg).textContent = r.value.toFixed(2);
    });
  }

  window.Charts = { lineChart, nightsChart, skillBars };
})();
