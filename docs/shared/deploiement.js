/* Schéma du déploiement retenu (SVG statique, couleurs par variables CSS).
 *
 * drawDeployment(container, bilan, {tech})
 *   Cinq étapes, triangle à l'échelle (rayon réel de 60 à 355 m). bilan : bloc
 *   « bilan » de data/deploiement.json. tech : ajoute vitesses et tensions.
 */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const fr = (v, d) => v.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
  const STYLE = `
.dp-col { fill: var(--surface); stroke: var(--line); }
.dp-sim { fill: color-mix(in srgb, var(--series-1) 7%, var(--surface)); }
.dp-ship { stroke: var(--accent); stroke-width: 5; stroke-linecap: round; }
.dp-cable { stroke: var(--ink); stroke-width: 1.1; fill: none; }
.dp-liq { fill: var(--series-1); }
.dp-arrow { stroke: var(--series-3); stroke-width: 1.8; fill: none; }
.dp-head { fill: var(--series-3); }
.dp-ctr { fill: var(--muted); }
.dp-h { font: 600 13px var(--f-display, sans-serif); fill: var(--ink); }
.dp-t { font: 400 11px var(--f-mono, monospace); fill: var(--ink-2); }
.dp-b { font: 600 11px var(--f-mono, monospace); fill: var(--ink); }
.dp-bar { fill: var(--accent); }
.dp-track { fill: var(--line); }`;
  const el = (tag, attrs, txt) => {
    const e = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
    if (txt !== undefined) e.textContent = txt;
    return e;
  };

  function draw(root, b, o) {
    o = o || {};
    root.innerHTML = "";
    const W = 960, H = 322, col = 192, cy = 112, sc = 76 / 355;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", style: "width:100%;height:auto;display:block",
      "aria-label": "Cinq étapes du déploiement : raccordement, calage des ergols, déroulement, rotation à plein rayon, montée à 1 tour par minute." });
    svg.appendChild(el("style", {}, STYLE));
    const defs = el("defs", {});
    const mk = el("marker", { id: "dp-m", viewBox: "0 0 8 8", refX: 7, refY: 4, markerWidth: 7, markerHeight: 7, orient: "auto" });
    mk.appendChild(el("path", { d: "M0 0L8 4L0 8Z", class: "dp-head" }));
    defs.appendChild(mk);
    svg.appendChild(defs);

    const d = b.D4_mi.deroulement_t;
    const ET = [
      { h: "1 · Raccorder", r: 60, rpm: "sans rotation", t: "non simulé", e: "—", ep: 0, sim: false, tag: "câbles courts, 63 m" },
      { h: "2 · Caler les ergols", r: 60, rpm: "0,05 tr/min", t: "≈ 3 h", e: fr(b.depart_t, 2) + " t", ep: b.depart_t, sim: false, liq: true, spin: 1, tag: "estimé" },
      { h: "3 · Dérouler", r: 200, rpm: "0,05 tr/min", t: "5 h", e: "compté à l'étape 4", ep: d, sim: true, out: true, spin: 1, tag: o.tech ? "treuils 0,03 m/s" : "3 cm/s" },
      { h: "4 · Plein rayon", r: 355, rpm: "0,05 → 0,1 tr/min", t: "1 h", e: fr(d - b.depart_t, 2) + " t (3 et 4)", ep: d, sim: true, spin: 2, tag: o.tech ? "≈ 330 N par vaisseau" : "" },
      { h: "5 · Monter", r: 355, rpm: "0,1 → 1 tr/min", t: "6 h ou plus", e: fr(b.montee_t, 1) + " t", ep: b.montee_t + d, sim: true, spin: 3, tag: o.tech ? "α = 0,004·ω²" : "" },
    ];
    ET.forEach((s, i) => {
      const x = 2 + i * col, g = el("g", {}), cx = x + col / 2 - 2;
      g.appendChild(el("rect", { x, y: 2, width: col - 6, height: H - 4, rx: 5, class: "dp-col" + (s.sim ? " dp-sim" : "") }));
      g.appendChild(el("text", { x: x + 10, y: 22, class: "dp-h" }, s.h));
      // Triangle à l'échelle ; vaisseaux de 50 m, pointe vers le centre
      const P = [90, 210, 330].map((a) => { const t = a * Math.PI / 180; return [Math.cos(t), Math.sin(t)]; });
      const at = (rho, c, n) => [cx + c * rho * sc, cy + n * rho * sc];
      // Câbles aux points d'attache (21 m au-dessus du centre de masse), coque de −34 à +16 m
      g.appendChild(el("polygon", { points: P.map(([c, n]) => at(s.r - 21, c, n).join(",")).join(" "), class: "dp-cable" }));
      P.forEach(([c, n]) => {
        const [x1, y1] = at(s.r - 34, c, n), [x2, y2] = at(s.r + 16, c, n);
        g.appendChild(el("line", { x1, y1, x2, y2, class: "dp-ship" }));
        if (s.liq) { const [lx, ly] = at(s.r + 16, c, n); g.appendChild(el("circle", { cx: lx, cy: ly, r: 3, class: "dp-liq" })); }
        if (s.out) {
          const [ax, ay] = at(s.r + 36, c, n), [bx, by] = at(s.r + 110, c, n);
          g.appendChild(el("line", { x1: ax, y1: ay, x2: bx, y2: by, class: "dp-arrow", "marker-end": "url(#dp-m)" }));
        }
      });
      g.appendChild(el("circle", { cx, cy, r: 1.8, class: "dp-ctr" }));
      if (s.spin) {
        const a = (25 + s.spin * 20) * Math.PI / 180, r0 = 30;
        g.appendChild(el("path", { d: `M${cx + r0} ${cy}A${r0} ${r0} 0 0 0 ${cx + r0 * Math.cos(a)} ${cy - r0 * Math.sin(a)}`, class: "dp-arrow", "marker-end": "url(#dp-m)" }));
      }
      const L = (y, c, t) => g.appendChild(el("text", { x: x + 10, y, class: c }, t));
      L(218, "dp-b", s.rpm);
      L(236, "dp-t", s.t);
      if (s.tag) L(254, "dp-t", s.tag);
      L(278, "dp-t", "ergols, par vaisseau");
      if (s.e) L(294, "dp-b", s.e);
      g.appendChild(el("rect", { x: x + 10, y: 302, width: col - 26, height: 6, rx: 3, class: "dp-track" }));
      if (s.ep) g.appendChild(el("rect", { x: x + 10, y: 302, width: (col - 26) * s.ep / (b.montee_t + d), height: 6, rx: 3, class: "dp-bar" }));
      svg.appendChild(g);
    });
    root.appendChild(svg);
  }
  window.drawDeployment = draw;
})();
