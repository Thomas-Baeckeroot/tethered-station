/* Graphiques en courbes SVG, sans dépendance.
 *
 * lineChart(el, {
 *   x: [...] | per-series x,           // abscisses communes (ou s.x par série)
 *   series: [{name, y, x?, color?, dash?}],
 *   xLabel, yLabel, xLog, yLog, yMin, yMax, xMin, xMax,
 *   refs: [{y, label}],                // lignes de référence horizontales
 *   vrefs: [{x, label}],               // lignes de référence verticales
 *   xFmt, yFmt, height, tooltipFmt
 * })
 * Couleurs : variables CSS --series-1..4, --ink, --ink-2, --muted, --grid, --surface.
 * Survol : réticule + info-bulle (valeur de chaque série à l'abscisse la plus proche).
 */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  function niceTicks(a, b, n) {
    const span = b - a;
    if (span <= 0) return [a];
    const step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const err = step0 / mag;
    const step = (err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1) * mag;
    const out = [];
    for (let v = Math.ceil(a / step) * step; v <= b + step * 1e-9; v += step) out.push(+v.toPrecision(12));
    return out;
  }

  function logTicks(a, b) {
    const out = [];
    for (let e = Math.floor(Math.log10(a)); e <= Math.ceil(Math.log10(b)); e++)
      for (const m of [1, 2, 5]) { const v = m * Math.pow(10, e); if (v >= a * 0.999 && v <= b * 1.001) out.push(v); }
    return out;
  }

  function fmtNum(v) {
    const a = Math.abs(v);
    if (a === 0) return "0";
    if (a >= 1000) return v.toLocaleString("fr-FR", { maximumFractionDigits: 0 });
    if (a >= 10) return (+v.toFixed(1)).toLocaleString("fr-FR");
    if (a >= 1) return (+v.toFixed(2)).toLocaleString("fr-FR");
    return (+v.toPrecision(2)).toLocaleString("fr-FR");
  }

  function lineChart(root, o) {
    root.innerHTML = "";
    root.classList.add("lc");
    const H = o.height || 260;
    const M = { l: 52, r: 16, t: 12, b: 40 };
    const legend = document.createElement("div");
    legend.className = "lc-legend";
    if (o.series.length > 1) {
      o.series.forEach((s, i) => {
        const it = document.createElement("span");
        it.className = "lc-key";
        it.innerHTML = `<i style="background:${s.color || `var(--series-${i + 1})`}${s.dash ? ";background:repeating-linear-gradient(90deg," + (s.color || `var(--series-${i + 1})`) + " 0 5px,transparent 5px 8px)" : ""}"></i>${s.name}`;
        legend.appendChild(it);
      });
      root.appendChild(legend);
    }
    const wrap = document.createElement("div");
    wrap.className = "lc-plot";
    root.appendChild(wrap);
    const tip = document.createElement("div");
    tip.className = "lc-tip";
    tip.hidden = true;
    wrap.appendChild(tip);

    const allX = [], allY = [];
    o.series.forEach((s) => {
      const xs = s.x || o.x;
      s._x = xs;
      xs.forEach((v) => allX.push(v));
      s.y.forEach((v) => { if (v !== null && isFinite(v)) allY.push(v); });
    });
    const finite = (arr) => arr.filter((v) => isFinite(v) && (!o.yLog || v > 0));
    let xMin = o.xMin ?? Math.min(...allX), xMax = o.xMax ?? Math.max(...allX);
    const ys = finite(allY);
    let yMin = o.yMin ?? Math.min(...ys), yMax = o.yMax ?? Math.max(...ys);
    (o.refs || []).forEach((r) => { yMin = Math.min(yMin, r.y); yMax = Math.max(yMax, r.y); });
    if (!o.yLog && o.yMin === undefined) { const pad = (yMax - yMin) * 0.06 || 1; yMin -= pad; yMax += pad; }
    if (o.yLog) { yMin = o.yMin ?? Math.max(Math.min(...ys), 1e-6); }

    function draw() {
      const W = wrap.clientWidth || 600;
      const svg = wrap.querySelector("svg") || el("svg", {}, wrap);
      svg.innerHTML = "";
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      svg.setAttribute("width", W);
      svg.setAttribute("height", H);
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", o.ariaLabel || o.yLabel || "graphique");
      const iw = W - M.l - M.r, ih = H - M.t - M.b;
      const sx = o.xLog
        ? (v) => M.l + (Math.log10(v) - Math.log10(xMin)) / (Math.log10(xMax) - Math.log10(xMin)) * iw
        : (v) => M.l + (v - xMin) / (xMax - xMin) * iw;
      const sy = o.yLog
        ? (v) => M.t + ih - (Math.log10(Math.max(v, yMin)) - Math.log10(yMin)) / (Math.log10(yMax) - Math.log10(yMin)) * ih
        : (v) => M.t + ih - (v - yMin) / (yMax - yMin) * ih;
      const g = el("g", { class: "lc-axes" }, svg);
      const yt = o.yLog ? logTicks(yMin, yMax) : niceTicks(yMin, yMax, 5);
      yt.forEach((v) => {
        const y = sy(v);
        el("line", { x1: M.l, x2: M.l + iw, y1: y, y2: y, class: "lc-grid" }, g);
        const t = el("text", { x: M.l - 8, y: y + 4, class: "lc-tick", "text-anchor": "end" }, g);
        t.textContent = (o.yFmt || fmtNum)(v);
      });
      const xt = o.xLog ? logTicks(xMin, xMax) : niceTicks(xMin, xMax, Math.max(3, Math.floor(iw / 90)));
      xt.forEach((v) => {
        const x = sx(v);
        el("line", { x1: x, x2: x, y1: M.t + ih, y2: M.t + ih + 4, class: "lc-base" }, g);
        const t = el("text", { x, y: M.t + ih + 18, class: "lc-tick", "text-anchor": "middle" }, g);
        t.textContent = (o.xFmt || fmtNum)(v);
      });
      el("line", { x1: M.l, x2: M.l + iw, y1: M.t + ih, y2: M.t + ih, class: "lc-base" }, g);
      if (o.xLabel) { const t = el("text", { x: M.l + iw, y: H - 4, class: "lc-label", "text-anchor": "end" }, g); t.textContent = o.xLabel; }
      if (o.yLabel) { const t = el("text", { x: M.l - 44, y: M.t - 2, class: "lc-label", "text-anchor": "start" }, g); t.textContent = ""; svg.setAttribute("aria-label", o.yLabel); }
      (o.refs || []).forEach((r) => {
        const y = sy(r.y);
        el("line", { x1: M.l, x2: M.l + iw, y1: y, y2: y, class: "lc-ref" }, g);
        if (r.label) { const t = el("text", { x: M.l + iw - 4, y: y - 5, class: "lc-reflabel", "text-anchor": "end" }, g); t.textContent = r.label; }
      });
      (o.vrefs || []).forEach((r) => {
        if (r.x < xMin || r.x > xMax) return;
        const x = sx(r.x);
        el("line", { x1: x, x2: x, y1: M.t, y2: M.t + ih, class: "lc-ref" }, g);
        if (r.label) { const t = el("text", { x: x + 4, y: M.t + 12, class: "lc-reflabel" }, g); t.textContent = r.label; }
      });
      const clipId = "c" + Math.random().toString(36).slice(2);
      const cp = el("clipPath", { id: clipId }, svg);
      el("rect", { x: M.l, y: M.t - 2, width: iw, height: ih + 4 }, cp);
      const plot = el("g", { "clip-path": `url(#${clipId})` }, svg);
      o.series.forEach((s, i) => {
        let d = "", pen = false;
        s._x.forEach((xv, k) => {
          const yv = s.y[k];
          if (yv === null || !isFinite(yv) || (o.yLog && yv <= 0) || (o.xLog && xv <= 0)) { pen = false; return; }
          d += (pen ? "L" : "M") + sx(xv).toFixed(1) + "," + sy(yv).toFixed(1);
          pen = true;
        });
        el("path", { d, class: "lc-line", stroke: s.color || `var(--series-${i + 1})`, "stroke-dasharray": s.dash ? "6 4" : "none", fill: "none" }, plot);
      });
      const cross = el("line", { y1: M.t, y2: M.t + ih, class: "lc-cross", visibility: "hidden" }, svg);
      const dots = o.series.map((s, i) => el("circle", { r: 4, class: "lc-dot", fill: s.color || `var(--series-${i + 1})`, visibility: "hidden" }, svg));
      const hit = el("rect", { x: M.l, y: M.t, width: iw, height: ih, fill: "transparent" }, svg);
      const inv = o.xLog
        ? (px) => Math.pow(10, Math.log10(xMin) + (px - M.l) / iw * (Math.log10(xMax) - Math.log10(xMin)))
        : (px) => xMin + (px - M.l) / iw * (xMax - xMin);
      function nearest(xs, v) {
        let lo = 0, hi = xs.length - 1;
        while (hi - lo > 1) { const m = (lo + hi) >> 1; if (xs[m] <= v) lo = m; else hi = m; }
        return Math.abs(xs[lo] - v) < Math.abs(xs[hi] - v) ? lo : hi;
      }
      function move(ev) {
        const r = svg.getBoundingClientRect();
        const px = (ev.clientX - r.left) * (W / r.width);
        const xv = inv(Math.max(M.l, Math.min(M.l + iw, px)));
        const rows = [];
        let xshow = null;
        o.series.forEach((s, i) => {
          const k = nearest(s._x, xv);
          const yv = s.y[k];
          xshow = s._x[k];
          if (yv === null || !isFinite(yv)) { dots[i].setAttribute("visibility", "hidden"); return; }
          dots[i].setAttribute("cx", sx(s._x[k]));
          dots[i].setAttribute("cy", sy(yv));
          dots[i].setAttribute("visibility", "visible");
          rows.push(`<span class="lc-tkey"><i style="background:${s.color || `var(--series-${i + 1})`}"></i>${s.name}</span><b>${(o.yFmt || fmtNum)(yv)}${o.yUnit || ""}</b>`);
        });
        cross.setAttribute("x1", sx(xshow));
        cross.setAttribute("x2", sx(xshow));
        cross.setAttribute("visibility", "visible");
        tip.innerHTML = `<div class="lc-thead">${o.xName || ""} ${(o.xFmt || fmtNum)(xshow)}${o.xUnit || ""}</div>` + rows.join("");
        tip.hidden = false;
        const tx = (sx(xshow) / W) * r.width;
        tip.style.left = (tx > r.width * 0.6 ? tx - tip.offsetWidth - 12 : tx + 12) + "px";
        tip.style.top = "8px";
      }
      hit.addEventListener("pointermove", move);
      hit.addEventListener("pointerleave", () => {
        tip.hidden = true;
        cross.setAttribute("visibility", "hidden");
        dots.forEach((d) => d.setAttribute("visibility", "hidden"));
      });
    }
    draw();
    if (o.yLabel) {
      const yl = document.createElement("div");
      yl.className = "lc-ylabel";
      yl.textContent = o.yLabel;
      root.insertBefore(yl, wrap);
    }
    new ResizeObserver(() => draw()).observe(wrap);
  }

  window.lineChart = lineChart;
})();
