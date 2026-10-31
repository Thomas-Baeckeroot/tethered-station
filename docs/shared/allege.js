/* Vaisseau habité allégé : figure interactive (SVG, couleurs par variables CSS).
 *
 * drawLightShip(container, rows, {sim, peak, start})
 *   rows : data/allege.json (calcul statique tous les 5 t transvasés : masses,
 *          vitesse, rayons, h, inclinaison pour 50 t déplacées de 3,5 m,
 *          niveaux des ergols ; variantes « _lest » avec 50 t descendues à 44 m)
 *   sim  : {tr: {tilt, tilt_lest}} cargaison simulée (facultatif)
 *   peak : {tr: {actuel, bassin, pool: {m, a}}, lest: {…}} pic du balayage hors
 *          plan simulé, bassin d'origine ou réaccordé (facultatif ; interpolé
 *          entre les cas simulés)
 * Deux vues : la station de dessus (centre de rotation fixe, triangle qui se
 * déplace, configuration de départ en pointillés) et le vaisseau habité de
 * côté (ergols, lest, bassin, attaches, centre de masse, h, deux jauges).
 * Curseur, cases « lest » et « bassin réaccordé », bouton de lecture qui fait
 * varier le transfert de 0 à 390 t.
 */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const REDUCE = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const STYLE = `
.lg-ghost { fill: none; stroke: var(--muted); stroke-width: 1; stroke-dasharray: 4 4; opacity: 0.7; }
.lg-cable { stroke: var(--ink); stroke-width: 1.1; }
.lg-crew { fill: var(--accent-soft); stroke: var(--accent); stroke-width: 1.4; }
.lg-cargo { fill: color-mix(in srgb, var(--muted) 18%, var(--surface)); stroke: var(--muted); stroke-width: 1.4; }
.lg-center { stroke: var(--ink); stroke-width: 1.4; }
.lg-spin { fill: none; stroke: var(--muted); stroke-width: 1.4; }
.lg-head { fill: var(--muted); } .lg-head-a { fill: var(--accent); }
.lg-hull { fill: var(--surface); stroke: var(--ink-2); stroke-width: 1.4; }
.lg-zone { fill: color-mix(in srgb, var(--accent) 10%, var(--surface)); stroke: none; }
.lg-tank { fill: none; stroke: var(--muted); stroke-width: 1; }
.lg-lox { fill: color-mix(in srgb, #3f7fd1 55%, var(--surface)); }
.lg-ch4 { fill: color-mix(in srgb, #1baf7a 55%, var(--surface)); }
.lg-pool { fill: color-mix(in srgb, #5cc8ff 60%, var(--surface)); }
.lg-ballast { fill: color-mix(in srgb, var(--ink-2) 55%, var(--surface)); stroke: var(--ink-2); stroke-width: 1; }
.lg-engine { fill: color-mix(in srgb, var(--muted) 40%, var(--surface)); stroke: var(--muted); }
.lg-att { fill: var(--ink); }
.lg-com { fill: var(--surface); stroke: var(--accent); stroke-width: 2; }
.lg-com-ghost { fill: none; stroke: var(--muted); stroke-width: 1.2; stroke-dasharray: 2 2; }
.lg-dim { stroke: var(--accent); stroke-width: 1.4; }
.lg-g { stroke: var(--muted); stroke-width: 1.4; }
.lg-floor { stroke: var(--accent); stroke-width: 3; stroke-linecap: round; }
.lg-level { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 3 3; }
.lg-pool-ghost { fill: none; stroke: #5cc8ff; stroke-width: 1; stroke-dasharray: 3 2; }
.lg-title { font: 600 13px var(--f-display); fill: var(--ink); letter-spacing: 0.02em; }
.lg-t { font: 400 10.5px var(--f-mono); fill: var(--ink-2); }
.lg-s { font: 400 9.5px var(--f-mono); fill: var(--muted); }
.lg-b { font: 600 12px var(--f-mono); fill: var(--ink); }
.lg-acc { font: 600 12px var(--f-mono); fill: var(--accent); }
`;
  const fr = (v, d = 0) => v.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });

  function el(tag, attrs, parent, text) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }

  function svgBox(W, H, aria) {
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "sc-svg", role: "img", "aria-label": aria });
    el("style", {}, svg, STYLE);
    const id = "lg" + Math.random().toString(36).slice(2);
    const defs = el("defs", {}, svg);
    for (const [k, c] of [["m", "lg-head"], ["a", "lg-head-a"]]) {
      const m = el("marker", { id: `${id}-${k}`, viewBox: "0 0 10 10", refX: 8, refY: 5, markerWidth: 7, markerHeight: 7,
        markerUnits: "userSpaceOnUse", orient: "auto-start-reverse" }, defs);
      el("path", { d: "M0,0 L10,5 L0,10 z", class: c }, m);
    }
    const layer = el("g", {}, svg);
    return [svg, layer, (k) => `url(#${id}-${k})`];
  }

  /* Capsule de vaisseau dans un repère local : x le long de l'axe, pointe en 0. */
  function capsule(parent, k, cls) {
    const P = (x, y) => `${(x * k).toFixed(2)} ${(y * k).toFixed(2)}`;
    el("path", { d: `M ${P(0, 0)} C ${P(0, 2.9)} ${P(6.5, 4.5)} ${P(13.8, 4.5)} L ${P(50, 4.5)} L ${P(50, -4.5)} L ${P(13.8, -4.5)} `
      + `C ${P(6.5, -4.5)} ${P(0, -2.9)} ${P(0, 0)} Z`, class: cls }, parent);
  }

  function topView(row, ref, mk, g) {
    const W = 360, cx = 180, cy = 214, k = 0.33, ex = 2.4;
    g.replaceChildren();
    el("text", { x: 10, y: 18, class: "lg-title" }, g, "La station vue de dessus");
    const a = 338.4, V = [[0, a], [-a * Math.sqrt(3) / 2, -a / 2], [a * Math.sqrt(3) / 2, -a / 2]];
    const S = (p, c) => [cx + (p[0]) * k, cy - (p[1] - c) * k];
    // Configuration de départ (masses égales), en pointillés
    const g0 = V.map((p) => S(p, 0));
    el("polygon", { points: g0.map((p) => p.join(",")).join(" "), class: "lg-ghost" }, g);
    el("circle", { cx, cy, r: a * k, class: "lg-ghost" }, g);
    // Triangle actuel : centres de masse aux mêmes sommets, centre de rotation déplacé
    const pts = V.map((p) => S(p, row.cy));
    const ships = pts.map((p, i) => {
      const dx = p[0] - cx, dy = p[1] - cy, d = Math.hypot(dx, dy), u = [dx / d, dy / d];
      return { p, u, ang: Math.atan2(u[1], u[0]) * 180 / Math.PI, crew: i === 0 };
    });
    // Attaches : 9 m de la pointe ; centre de masse des cargos ≈ 34 m de la pointe
    const xcom = (i) => (i === 0 ? row.x : 34.0);
    const nose = (i) => { const s = ships[i], d = (xcom(i) - 9) * k * ex; return [s.p[0] - s.u[0] * d, s.p[1] - s.u[1] * d]; };
    for (let i = 0; i < 3; i++) {
      const A = nose(i), B = nose((i + 1) % 3);
      el("line", { x1: A[0], y1: A[1], x2: B[0], y2: B[1], class: "lg-cable" }, g);
    }
    ships.forEach((s, i) => {
      const xc = xcom(i);
      const t = el("g", { transform: `translate(${s.p[0]},${s.p[1]}) rotate(${s.ang}) translate(${-xc * k * ex},0)` }, g);
      capsule(t, k * ex, s.crew ? "lg-crew" : "lg-cargo");
    });
    // Centre de rotation et sens
    el("line", { x1: cx - 6, y1: cy, x2: cx + 6, y2: cy, class: "lg-center" }, g);
    el("line", { x1: cx, y1: cy - 6, x2: cx, y2: cy + 6, class: "lg-center" }, g);
    el("path", { d: `M ${cx + 22} ${cy} A 22 22 0 1 0 ${cx} ${cy + 22}`, class: "lg-spin", "marker-end": mk("m") }, g);
    el("text", { x: cx, y: cy + 40, class: "lg-b", "text-anchor": "middle" }, g, `${fr(row.rpm, 2)} tr/min`);
    // Étiquettes
    const lc = ships[0].p;
    el("text", { x: lc[0] + 18, y: lc[1] - 4, class: "lg-acc" }, g, `habité · ${fr(row.mh)} t`);
    el("text", { x: lc[0] + 18, y: lc[1] + 10, class: "lg-s" }, g, `à ${fr(row.R)} m · 3,71 m/s²`);
    el("line", { x1: cx, y1: cy, x2: lc[0], y2: lc[1], class: "lg-level" }, g);
    for (const [s, anchor, x] of [[ships[1], "start", 10], [ships[2], "end", W - 10]]) {
      el("text", { x, y: s.p[1] + 30, class: "lg-t", "text-anchor": anchor }, g, `cargo · ${fr(row.mc)} t`);
      el("text", { x, y: s.p[1] + 43, class: "lg-s", "text-anchor": anchor }, g, `à ${fr(row.Rc)} m`);
      el("text", { x, y: s.p[1] + 55, class: "lg-s", "text-anchor": anchor }, g, `${fr(row.gc, 2)} m/s²`);
    }
    el("text", { x: 10, y: 420, class: "lg-s" }, g, `pointillés : départ, 610 t partout · vaisseaux agrandis ×${fr(ex, 1)}`);
  }

  /* Jauge : plancher incliné (angle ×5), titre au-dessus, valeur en dessous. */
  function gauge(g, gx, gy, title, tilt, val, note) {
    el("text", { x: gx, y: gy - 30, class: "lg-s", "text-anchor": "middle" }, g, title);
    el("text", { x: gx, y: gy - 17, class: "lg-s", "text-anchor": "middle" }, g, note);
    el("line", { x1: gx - 44, y1: gy, x2: gx + 44, y2: gy, class: "lg-level" }, g);
    if (tilt == null) {
      el("text", { x: gx, y: gy + 22, class: "lg-t", "text-anchor": "middle" }, g, "non simulé");
      return;
    }
    const th = tilt * 5 * Math.PI / 180;
    el("line", { x1: gx - 44 * Math.cos(th), y1: gy + 44 * Math.sin(th), x2: gx + 44 * Math.cos(th), y2: gy - 44 * Math.sin(th), class: "lg-floor" }, g);
    el("text", { x: gx, y: gy + 24, class: "lg-acc", "text-anchor": "middle" }, g, val);
  }

  /* Valeur simulée au transfert tr : exacte sur un cas simulé, sinon
     interpolée linéairement entre les deux cas voisins (null hors bornes). */
  function interp(table, tr, key) {
    const ks = Object.keys(table).filter((k) => k !== "lest" && table[k][key] != null).map(Number).sort((a, b) => a - b);
    if (!ks.length) return [null, false];
    if (table[tr] && table[tr][key] != null) return [table[tr][key], true];
    for (let i = 0; i + 1 < ks.length; i++) {
      if (tr > ks[i] && tr < ks[i + 1]) {
        const u = (tr - ks[i]) / (ks[i + 1] - ks[i]);
        return [table[ks[i]][key] * (1 - u) + table[ks[i + 1]][key] * u, false];
      }
    }
    return [null, false];
  }

  function sideView(row, ref, lest, mk, g, simTilt, pk) {
    const W = 360, x0 = 120, y0 = 46, k = 5.6;              // pointe en (x0, y0), axe vers le bas
    const Y = (x) => y0 + x * k, X = (y) => x0 + y * k;
    g.replaceChildren();
    el("text", { x: 10, y: 18, class: "lg-title" }, g, "Le vaisseau habité de côté");
    el("text", { x: 10, y: 32, class: "lg-s" }, g, "pointe vers le centre ; pointillés : départ");
    // Coque
    const P = (x, y) => `${X(y).toFixed(1)} ${Y(x).toFixed(1)}`;
    el("path", { d: `M ${P(0, 0)} C ${P(0, 2.9)} ${P(6.5, 4.5)} ${P(13.8, 4.5)} L ${P(50, 4.5)} L ${P(50, -4.5)} L ${P(13.8, -4.5)} `
      + `C ${P(6.5, -4.5)} ${P(0, -2.9)} ${P(0, 0)} Z`, class: "lg-hull" }, g);
    // Soute habitée, bassin
    el("rect", { x: X(-4), y: Y(4), width: 8 * k, height: 16 * k, class: "lg-zone" }, g);
    const pl = (pk && pk.pool) || { m: 25, a: 3.6 }, pool = pl.m / (Math.PI * pl.a * pl.a);
    if (pk && pk.pool) el("rect", { x: X(-3.6), y: Y(12 - 25 / (Math.PI * 3.6 * 3.6)), width: 7.2 * k, height: 25 / (Math.PI * 3.6 * 3.6) * k, class: "lg-pool-ghost" }, g);
    el("rect", { x: X(-pl.a), y: Y(12 - pool), width: 2 * pl.a * k, height: pool * k, class: "lg-pool" }, g);
    // Réservoirs et ergols
    el("rect", { x: X(-4.5), y: Y(22), width: 9 * k, height: 13 * k, class: "lg-tank" }, g);
    el("rect", { x: X(-4.5), y: Y(35), width: 9 * k, height: 11 * k, class: "lg-tank" }, g);
    const dC = (row.depth && row.depth.CH4) || 0, dL = (row.depth && row.depth.LOX) || 0;
    if (dC > 0) el("rect", { x: X(-4.5), y: Y(35 - dC), width: 9 * k, height: dC * k, class: "lg-ch4" }, g);
    if (dL > 0) el("rect", { x: X(-4.5), y: Y(46 - dL), width: 9 * k, height: dL * k, class: "lg-lox" }, g);
    if (lest) el("rect", { x: X(-3.4), y: Y(42.6), width: 6.8 * k, height: 2.8 * k, rx: 2, class: "lg-ballast" }, g);
    for (const yy of [-2.6, 0, 2.6]) el("path", { d: `M ${P(46, yy - 1)} L ${P(46, yy + 1)} L ${P(50, yy + 1.4)} L ${P(50, yy - 1.4)} Z`, class: "lg-engine" }, g);
    // Attaches et câbles
    for (const s of [-1, 1]) {
      el("line", { x1: X(3.5 * s), y1: Y(9), x2: X(3.5 * s) + s * 40, y2: Y(9) - 40, class: "lg-cable" }, g);
      el("circle", { cx: X(3.5 * s), cy: Y(9), r: 2.8, class: "lg-att" }, g);
    }
    // Centres de masse : départ (pointillés) et actuel, cote h
    el("circle", { cx: x0, cy: Y(ref.x), r: 5, class: "lg-com-ghost" }, g);
    const xc = lest ? row.x_lest : row.x, h = lest ? row.h_lest : row.h;
    el("circle", { cx: x0, cy: Y(xc), r: 5.5, class: "lg-com" }, g);
    el("line", { x1: x0 - 3.5, y1: Y(xc) - 3.5, x2: x0 + 3.5, y2: Y(xc) + 3.5, class: "lg-dim" }, g);
    el("line", { x1: x0 - 3.5, y1: Y(xc) + 3.5, x2: x0 + 3.5, y2: Y(xc) - 3.5, class: "lg-dim" }, g);
    const xd = X(-4.5) - 14;
    el("line", { x1: xd, y1: Y(9), x2: xd, y2: Y(xc), class: "lg-dim", "marker-start": mk("a"), "marker-end": mk("a") }, g);
    el("text", { x: xd - 4, y: (Y(9) + Y(xc)) / 2 + 4, class: "lg-acc", "text-anchor": "end" }, g, `h = ${fr(h, 1)} m`);
    // Légendes à droite
    const lx = X(4.5) + 14, lab = (y, t, cls = "lg-t") => el("text", { x: lx, y, class: cls }, g, t);
    lab(Y(9) + 4, "attaches");
    lab(Y(12) + 4, pk && pk.pool ? `bassin ${fr(pl.m)} t, Ø ${fr(2 * pl.a, 1)} m` : "soute habitée, bassin", "lg-s");
    lab(Y(xc) + 4, "centre de masse", "lg-t");
    if (dC > 0) lab(Y(35 - dC / 2) + 4, `méthane ${fr(dC, 1)} m`, "lg-s");
    if (dL > 0) lab(Y(46 - dL / 2) + 4, `oxygène ${fr(dL, 1)} m`, "lg-s");
    if (lest) lab(Y(44) + 14, "lest : 50 t de réserves", "lg-s");
    // Gravité
    el("line", { x1: 22, y1: Y(30), x2: 22, y2: Y(40), class: "lg-g", "marker-end": mk("m") }, g);
    el("text", { x: 28, y: Y(36), class: "lg-s" }, g, "gravité");
    // Jauges : 50 t déplacées de 3,5 m (formule ; simulé si disponible), 4 t au pire rythme hors plan (simulé)
    const tilt = lest ? row.tilt_lest : row.tilt;
    el("line", { x1: 10, y1: 338, x2: W - 10, y2: 338, class: "lg-level" }, g);
    gauge(g, 90, 396, "cargaison 50 t, ±3,5 m", tilt, `${fr(tilt, 2)}°`, simTilt != null ? `simulé : ${fr(simTilt, 2)}°` : "formule du palonnier");
    if (pk) gauge(g, 270, 396, "4 t au pire rythme", pk.v, pk.v == null ? "" : `${pk.exact ? "" : "≈ "}${fr(pk.v, 2)}°`, pk.v == null ? "" : (pk.exact ? "simulé" : "interpolé"));
    el("text", { x: W - 10, y: 424, class: "lg-s", "text-anchor": "end" }, g, "angles ×5");
  }

  function drawLightShip(container, rows, opts = {}) {
    container.replaceChildren();
    const ref = rows[0];
    const row2 = document.createElement("div");
    row2.className = "sc-row";
    const [s1, g1, mk1] = svgBox(360, 430, "La station vue de dessus, selon les ergols transvasés");
    const [s2, g2, mk2] = svgBox(360, 430, "Le vaisseau habité vu de côté : ergols, centre de masse, hauteur sous les attaches");
    row2.append(s1, s2);
    container.appendChild(row2);
    const ctrl = document.createElement("div");
    ctrl.className = "ctrl";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn ghost";
    const lab = document.createElement("label");
    lab.textContent = "ergols transvasés ";
    const range = document.createElement("input");
    Object.assign(range, { type: "range", min: 0, max: 390, step: 5, value: opts.start ?? 195 });
    lab.appendChild(range);
    const lb = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    lb.append(cb, document.createTextNode(" 50 t de lest en bas"));
    const lp = document.createElement("label");
    const cp = document.createElement("input");
    cp.type = "checkbox";
    lp.append(cp, document.createTextNode(" bassin réaccordé"));
    ctrl.append(btn, lab, lb);
    if (opts.peak) ctrl.append(lp);
    const out = document.createElement("div");
    out.className = "readout";
    container.append(ctrl, out);
    let tr = +range.value, playing = false, dir = 1, raf = 0, last = null;
    const show = () => {
      const row = rows[Math.round(tr / 5)];
      const sim = opts.sim && opts.sim[row.tr];
      const simTilt = sim ? (cb.checked ? sim.tilt_lest : sim.tilt) : null;
      let pk = null;
      if (opts.peak) {
        const key = cp.checked ? "bassin" : "actuel";
        const tab = cb.checked ? (opts.peak.lest || {}) : opts.peak;
        const [v, exact] = cb.checked ? [tab[row.tr] ? tab[row.tr][key] : null, true] : interp(tab, row.tr, key);
        // Bassin dessiné : celui du cas simulé le plus proche
        let pool = null;
        if (cp.checked) {
          const ks = Object.keys(tab).filter((k) => k !== "lest" && tab[k].pool).map(Number);
          if (ks.length) pool = tab[ks.reduce((a, b) => (Math.abs(b - row.tr) < Math.abs(a - row.tr) ? b : a))].pool;
        }
        pk = { v: v ?? null, exact, pool };
      }
      topView(row, ref, mk1, g1);
      sideView(row, ref, cb.checked, mk2, g2, simTilt, pk);
      const tilt = cb.checked ? row.tilt_lest : row.tilt;
      out.textContent = `${fr(row.tr)} t transvasées : ${fr(row.mh)} / ${fr(row.mc)} / ${fr(row.mc)} t · ${fr(row.rpm, 3)} tr/min `
        + `(${fr((row.rpm - 1) * 100, 1).replace("-", "−")} %) · plancher ${fr(tilt / ref.tilt, 1)} fois plus sensible qu'au départ`;
      range.value = row.tr;
      btn.textContent = playing ? "❚❚ pause" : "▶ animer";
    };
    const loop = (ts) => {
      const dt = last === null ? 0 : Math.min(0.1, (ts - last) / 1000);
      last = ts;
      tr += dir * dt * 60;                                  // 390 t en 6,5 s
      if (tr >= 390) { tr = 390; dir = -1; }
      if (tr <= 0) { tr = 0; dir = 1; }
      show();
      raf = playing ? requestAnimationFrame(loop) : 0;
    };
    btn.addEventListener("click", () => {
      playing = !playing;
      if (playing && !REDUCE) { last = null; raf = requestAnimationFrame(loop); } else { playing = false; if (raf) cancelAnimationFrame(raf); }
      show();
    });
    range.addEventListener("input", () => { tr = +range.value; show(); });
    cb.addEventListener("change", show);
    cp.addEventListener("change", show);
    show();
  }

  window.drawLightShip = drawLightShip;
})();
