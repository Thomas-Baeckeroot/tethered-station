/* Schéma du déploiement retenu (SVG statique, couleurs par variables CSS).
 *
 * drawDeployment(container, bilan, {tech})
 *   Cinq étapes, triangle à l'échelle (rayon réel de 60 à 355 m). bilan : bloc
 *   « bilan » de data/deploiement.json. tech : ajoute vitesses et tensions.
 *   Cinq colonnes si la place le permet ; sinon une étape par ligne, pour que le
 *   texte reste lisible sur téléphone (redessiné si la largeur franchit NARROW).
 */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const NARROW = 720;   // px de conteneur : en dessous, une étape par ligne
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
    const narrow = root.clientWidth > 0 && root.clientWidth < NARROW;
    const col = 192, row = 150;
    const W = narrow ? 380 : 960, H = narrow ? 5 * row : 322, sc = narrow ? 0.22 : 0.26;
    // Boîte de l'étape i, centre du triangle, abscisse du texte et ordonnées de ses lignes
    const box = (i) => narrow ? { x: 2, y: 2 + i * row, w: 376, h: row - 6 } : { x: 2 + i * col, y: 2, w: col - 6, h: H - 4 };
    const centre = (B) => narrow ? [B.x + 80, B.y + 52] : [B.x + B.w / 2, 88];
    const text = (B) => narrow
      ? { x: B.x + 166, h: B.y + 20, rpm: B.y + 40, t: B.y + 56, tag: B.y + 72, lab: B.y + 96, e: B.y + 112, bar: B.y + 122 }
      : { x: B.x + 10, h: 22, rpm: 218, t: 236, tag: 254, lab: 278, e: 294, bar: 302 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", style: `width:100%;height:auto;display:block${narrow ? ";max-width:560px;margin:0 auto" : ""}`,
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
      { h: "3 · Dérouler", r: 200, rpm: "0,05 tr/min", t: "5 h", e: "compté à l'étape 4", ep: d, sim: true, out: true, spin: 1, arc: 62, tag: o.tech ? "treuils 0,03 m/s" : "3 cm/s" },
      { h: "4 · Plein rayon", r: 355, rpm: "0,05 → 0,1 tr/min", t: "1 h", e: fr(d - b.depart_t, 2) + " t (3 et 4)", ep: d, sim: true, spin: 2, tag: o.tech ? "≈ 330 N par vaisseau" : "" },
      { h: "5 · Monter", r: 355, rpm: "0,1 → 1 tr/min", t: "6 h ou plus", e: fr(b.montee_t, 1) + " t", ep: b.montee_t + d, sim: true, spin: 3, tag: o.tech ? "α = 0,004·ω²" : "" },
    ];
    ET.forEach((s, i) => {
      const B = box(i), [cx, cy] = centre(B), T = text(B), g = el("g", {});
      const barW = B.x + B.w - T.x - 10;
      g.appendChild(el("rect", { x: B.x, y: B.y, width: B.w, height: B.h, rx: 5, class: "dp-col" + (s.sim ? " dp-sim" : "") }));
      g.appendChild(el("text", { x: T.x, y: T.h, class: "dp-h" }, s.h));
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
        // Sens de rotation ; étape 3 (s.arc) : hors du triangle, entre deux vaisseaux, pour ne pas croiser les câbles
        const r0 = s.arc || 30, t0 = s.arc ? Math.PI / 3 : 0, t1 = t0 - (25 + s.spin * 20) * Math.PI / 180;
        g.appendChild(el("path", { d: `M${cx + r0 * Math.cos(t0)} ${cy + r0 * Math.sin(t0)}A${r0} ${r0} 0 0 0 ${cx + r0 * Math.cos(t1)} ${cy + r0 * Math.sin(t1)}`, class: "dp-arrow", "marker-end": "url(#dp-m)" }));
      }
      const L = (y, c, t) => g.appendChild(el("text", { x: T.x, y, class: c }, t));
      L(T.rpm, "dp-b", s.rpm);
      L(T.t, "dp-t", s.t);
      if (s.tag) L(T.tag, "dp-t", s.tag);
      L(T.lab, "dp-t", "ergols, par vaisseau");
      if (s.e) L(T.e, "dp-b", s.e);
      g.appendChild(el("rect", { x: T.x, y: T.bar, width: barW, height: 6, rx: 3, class: "dp-track" }));
      if (s.ep) g.appendChild(el("rect", { x: T.x, y: T.bar, width: barW * s.ep / (b.montee_t + d), height: 6, rx: 3, class: "dp-bar" }));
      svg.appendChild(g);
    });
    root.appendChild(svg);
    return narrow;
  }
  window.drawDeployment = (root, b, o) => {
    let mode = draw(root, b, o);
    if (window.ResizeObserver) new ResizeObserver(() => {
      if (root.clientWidth > 0 && (root.clientWidth < NARROW) !== mode) mode = draw(root, b, o);
    }).observe(root);
  };
})();
