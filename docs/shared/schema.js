/* Schémas des configurations (SVG, couleurs par variables CSS).
 *
 * drawSchema(container, {topology, module, spread, bridle, radius, length, ship, caption})
 *   topology : dumbbell | ladder | triangle | triangle2
 *   module   : tangential | axial | radial (orientation de l'axe long)
 *   ship     : "starship" pour dessiner la silhouette du vaisseau (nez du
 *              côté négatif de l'axe long, vers le centre s'il est radial)
 *   hub      : true pour un moyeu central relié au nez de chaque module
 * Deux vues : dessus (plan de rotation) et côté (module 0, vu le long de la
 * direction de déplacement). Modules agrandis pour rester lisibles.
 */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const A = 6, LEN = 40, R = 340;

  function el(tag, attrs, parent, text) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }

  function arrowDefs(svg, id) {
    const defs = el("defs", {}, svg);
    const m = el("marker", { id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" }, defs);
    el("path", { d: "M0,0 L10,5 L0,10 z", class: "sc-arrowhead" }, m);
  }

  /* Silhouette de Starship (cotes du plan SN8, en mètres) dans un repère
     local : x le long de l'axe (pointe en −25), y transversal. k = px/m. */
  function starship(parent, k, flaps) {
    const g = el("g", {}, parent);
    const P = (x, y) => `${(x * k).toFixed(2)} ${(y * k).toFixed(2)}`;
    el("path", { d: `M ${P(-25, 0)} C ${P(-25, 2.9)} ${P(-18.5, 4.5)} ${P(-11.2, 4.5)} L ${P(25, 4.5)} L ${P(25, -4.5)} L ${P(-11.2, -4.5)} `
      + `C ${P(-18.5, -4.5)} ${P(-25, -2.9)} ${P(-25, 0)} Z`, class: "sc-module" }, g);
    if (flaps) for (const sgn of [1, -1]) {
      el("path", { d: `M ${P(-18.6, 3.9 * sgn)} L ${P(-11.4, 4.5 * sgn)} L ${P(-11.4, 7.8 * sgn)} L ${P(-15.6, 7.8 * sgn)} Z`, class: "sc-module" }, g);
      el("path", { d: `M ${P(11.9, 4.5 * sgn)} L ${P(23.8, 4.5 * sgn)} L ${P(23.8, 8.9 * sgn)} L ${P(14.5, 8.9 * sgn)} Z`, class: "sc-module" }, g);
    }
    return g;
  }

  function topView(cfg) {
    const W = 300, H = 290, cx = 150, cy = 148, Rpx = 100;
    const s = Rpx / R, ex = cfg.exag || 3.4;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "sc-svg", role: "img", "aria-label": "Vue de dessus" });
    const aid = "a" + Math.random().toString(36).slice(2);
    arrowDefs(svg, aid);
    el("circle", { cx, cy, r: Rpx, class: "sc-orbit" }, svg);
    el("circle", { cx, cy, r: 3, class: "sc-center" }, svg);
    // Flèche de rotation (sens trigonométrique)
    const ra = 26;
    el("path", { d: `M ${cx + ra} ${cy} A ${ra} ${ra} 0 1 0 ${cx} ${cy + ra}`, class: "sc-spin", "marker-end": `url(#${aid})` }, svg);
    el("text", { x: cx + 32, y: cy + 30, class: "sc-small" }, svg, "1 tr/min");
    const tri = cfg.topology.startsWith("triangle");
    const angles = tri ? [90, 210, 330] : [0, 180];
    const spread = cfg.spread ?? (cfg.topology === "triangle2" ? 20 : cfg.topology === "ladder" ? 15 : 0);
    const a = cfg.radius ?? A, len = cfg.length ?? LEN;
    const h = (cfg.module === "radial" ? len / 2 : a) + (cfg.bridle || 0);
    const P = (th, rr, tt) => {
      const t = th * Math.PI / 180, er = [Math.cos(t), Math.sin(t)], et = [-Math.sin(t), Math.cos(t)];
      return [cx + (er[0] * rr + et[0] * tt) * s, cy - (er[1] * rr + et[1] * tt) * s];
    };
    const att = angles.map((th) => {
      if (cfg.topology === "triangle2") return [P(th, R - ex * h, ex * spread), P(th, R - ex * h, -ex * spread)];
      return [P(th, R - ex * h, 0)];
    });
    // Câbles
    const cables = [];
    if (tri) for (let i = 0; i < 3; i++) {
      const j = (i + 1) % 3;
      cables.push(cfg.topology === "triangle2" ? [att[i][0], att[j][1]] : [att[i][0], att[j][0]]);
    } else cables.push([att[0][0], att[1][0]]);
    cables.forEach(([p, q]) => el("line", { x1: p[0], y1: p[1], x2: q[0], y2: q[1], class: "sc-cable" }, svg));
    if (cfg.hub) {
      angles.forEach((th) => { const q = P(th, R - ex * h, 0); el("line", { x1: cx, y1: cy, x2: q[0], y2: q[1], class: "sc-cable" }, svg); });
      el("circle", { cx, cy, r: 4.5, class: "sc-attach" }, svg);
      el("text", { x: cx + 8, y: cy - 8, class: "sc-small" }, svg, "moyeu");
    }
    if (cfg.topology === "ladder") {
      const [p, q] = cables[0];
      el("text", { x: (p[0] + q[0]) / 2, y: (p[1] + q[1]) / 2 - 6, class: "sc-small", "text-anchor": "middle" }, svg, "2 câbles superposés");
    }
    // Modules
    angles.forEach((th, b) => {
      const c = P(th, R, 0);
      const g = el("g", { transform: `translate(${c[0]},${c[1]}) rotate(${-th})` }, svg);
      const L = len * s * ex, D = 2 * a * s * ex;
      if (cfg.ship === "starship" && cfg.module !== "axial") starship(g, s * ex, true).setAttribute("transform", cfg.module === "tangential" ? "rotate(90)" : "");
      else if (cfg.module === "tangential") el("rect", { x: -D / 2, y: -L / 2, width: D, height: L, rx: D / 2, class: "sc-module" }, g);
      else if (cfg.module === "radial") el("rect", { x: -L / 2, y: -D / 2, width: L, height: D, rx: D / 2, class: "sc-module" }, g);
      else el("circle", { r: D / 2, class: "sc-module" }, g);
      if (att[b].length === 2) {
        const [p, q] = att[b];
        el("line", { x1: p[0], y1: p[1], x2: q[0], y2: q[1], class: "sc-spreader" }, svg);
      }
      att[b].forEach((p) => el("circle", { cx: p[0], cy: p[1], r: 2.6, class: "sc-attach" }, svg));
      const lab = P(th, R + 34, 0);
      el("text", { x: lab[0], y: lab[1] + 4, class: "sc-small", "text-anchor": "middle" }, svg, `M${b}`);
    });
    el("text", { x: 8, y: 16, class: "sc-title" }, svg, "Vue de dessus");
    if (ex === 1) {
      // Barre d'échelle de 200 m, graduée tous les 100 m
      const x0 = 8, y0 = H - 22, w = 200 * s;
      el("line", { x1: x0, y1: y0, x2: x0 + w, y2: y0, class: "sc-cable" }, svg);
      [0, 0.5, 1].forEach((f) => el("line", { x1: x0 + f * w, y1: y0 - 4, x2: x0 + f * w, y2: y0 + 4, class: "sc-cable" }, svg));
      el("text", { x: x0 + w / 2, y: H - 6, class: "sc-small", "text-anchor": "middle" }, svg, "100 m");
      el("text", { x: x0 + w, y: H - 6, class: "sc-small", "text-anchor": "middle" }, svg, "200 m");
    } else el("text", { x: 8, y: H - 8, class: "sc-small" }, svg, `modules agrandis ×${String(ex).replace(".", ",")}`);
    return svg;
  }

  function sideView(cfg) {
    const W = 300, H = 290, ex = 3.2;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "sc-svg", role: "img", "aria-label": "Vue de côté du module 0" });
    const aid = "b" + Math.random().toString(36).slice(2);
    arrowDefs(svg, aid);
    const cy = 150, axisX = 30, modX = 222;
    // Axe de rotation
    el("line", { x1: axisX, y1: 40, x2: axisX, y2: 250, class: "sc-axis" }, svg);
    el("text", { x: axisX + 6, y: 48, class: "sc-small" }, svg, "axe de rotation");
    const a = cfg.radius ?? A, len = cfg.length ?? LEN;
    const s = ex * 0.9 * (cfg.module === "radial" ? LEN / Math.max(len, LEN) : 1);
    const L = len * s, D = 2 * a * s;
    const h0 = (cfg.module === "radial" ? len / 2 : a) * s;
    const h = h0 + (cfg.bridle || 0) * s;
    // Module 0 vu le long de e_t : e_r vers la droite, e_z vers le haut
    let shape, floor;
    if (cfg.module === "tangential") {
      shape = el("circle", { cx: modX, cy, r: D / 2, class: "sc-module" }, svg);
      floor = [modX + D * 0.18, cy - D * 0.42, modX + D * 0.18, cy + D * 0.42];
    } else if (cfg.module === "axial") {
      shape = el("rect", { x: modX - D / 2, y: cy - L / 2, width: D, height: L, rx: D / 2, class: "sc-module" }, svg);
      floor = [modX + D * 0.18, cy - L * 0.45, modX + D * 0.18, cy + L * 0.45];
    } else if (cfg.ship === "starship") {
      // Starship vertical : ponts perpendiculaires à l'axe, section habitée sous la coiffe
      starship(el("g", { transform: `translate(${modX},${cy})` }, svg), s, false);
      for (const x of [-9, -3, 3]) el("line", { x1: modX + x * s, y1: cy - D * 0.45, x2: modX + x * s, y2: cy + D * 0.45, class: "sc-deck" }, svg);
      floor = [modX - 6 * s, cy - D * 0.45, modX - 6 * s, cy + D * 0.45];
    } else {
      shape = el("rect", { x: modX - L / 2, y: cy - D / 2, width: L, height: D, rx: D / 2, class: "sc-module" }, svg);
      floor = [modX + L * 0.36, cy - D * 0.4, modX + L * 0.36, cy + D * 0.4];
    }
    el("line", { x1: floor[0], y1: floor[1], x2: floor[2], y2: floor[3], class: "sc-floor" }, svg);
    // Points d'attache et câbles (vers le centre, à gauche)
    const zs = cfg.topology === "ladder" ? [-(cfg.spread ?? 15), cfg.spread ?? 15] : [0];
    zs.forEach((z) => {
      const ax = modX - h, ay = cy - z * s;
      el("line", { x1: axisX + 26, y1: ay, x2: ax, y2: ay, class: "sc-cable" }, svg);
      if (cfg.bridle) {
        // Mât ou patte d'oie : de la coque au point d'attache surélevé
        el("line", { x1: modX - h0, y1: ay - D * 0.25, x2: ax, y2: ay, class: "sc-spreader" }, svg);
        el("line", { x1: modX - h0, y1: ay + D * 0.25, x2: ax, y2: ay, class: "sc-spreader" }, svg);
      }
      el("circle", { cx: ax, cy: ay, r: 2.6, class: "sc-attach" }, svg);
    });
    // Coupure du câble (pas à l'échelle)
    el("path", { d: `M ${axisX + 70} ${cy - 10} l 6 20 M ${axisX + 78} ${cy - 10} l 6 20`, class: "sc-break" }, svg);
    // Gravité apparente : vers l'extérieur
    el("line", { x1: modX + 34, y1: cy + 74, x2: modX + 66, y2: cy + 74, class: "sc-g", "marker-end": `url(#${aid})` }, svg);
    el("text", { x: modX + 50, y: cy + 92, class: "sc-small", "text-anchor": "middle" }, svg, "« bas »");
    el("text", { x: modX, y: cy + (cfg.module === "axial" ? L / 2 + 18 : D / 2 + 18), class: "sc-small", "text-anchor": "middle" }, svg, "M0");
    el("text", { x: 8, y: 16, class: "sc-title" }, svg, "Vue de côté (M0)");
    el("text", { x: 8, y: H - 8, class: "sc-small" }, svg, cfg.topology === "triangle2" ? "2 attaches, écartées de ±" + String(cfg.spread ?? 20).replace(".", ",") + " m en profondeur" : "câble non à l'échelle");
    return svg;
  }

  function drawSchema(container, cfg) {
    container.classList.add("sc");
    container.innerHTML = "";
    const row = document.createElement("div");
    row.className = "sc-row";
    row.appendChild(topView(cfg));
    row.appendChild(sideView(cfg));
    container.appendChild(row);
    if (cfg.caption) {
      const c = document.createElement("p");
      c.className = "sc-caption";
      c.innerHTML = cfg.caption;
      container.appendChild(c);
    }
  }

  /* Brins doublés au nez de M0 (§ 7.4), une disposition par carte, trois vues :
     - dessus : quel brin va à quelle ferrure (M1 à gauche, M2 à droite) ;
     - dans l'axe du vaisseau, vu du centre (e_t à droite, axe de rotation
       vers le haut), vaisseau roulé de φ en service : couple de rappel ?
     - même vue après la rupture d'un brin du côté de M1 : couple de roulis ?
     Chaque brin tire sa ferrure vers son voisin ; dans l'axe, on ne voit que
     cette traction tangentielle (une flèche par brin). Un brin croisé amarré
     au croisement tire vers le nœud, sur l'axe : aucun couple. */
  const FX = 4.8;   // points de capture à ±4,8 m de l'axe (§ 2.5)
  const STRAND_LAYOUTS = {
    // fit : ferrures [e_t, e_z] (m) ; strands : [ferrure, côté (−1 : M1, +1 : M2)] ;
    // le brin 0 rompt ; phiBreak : vue après rupture roulée (stabilité) ou non (choc)
    ferrure: { fit: [[-FX, 0], [FX, 0]], strands: [[0, -1], [0, -1], [1, 1], [1, 1]], phiBreak: 0 },
    plan: { fit: [[-FX - 1, 0], [-FX + 1, 0], [FX - 1, 0], [FX + 1, 0]], strands: [[0, -1], [1, -1], [2, 1], [3, 1]], phiBreak: 0 },
    axe: { fit: [[-FX, 1], [-FX, -1], [FX, 1], [FX, -1]], strands: [[0, -1], [1, -1], [2, 1], [3, 1]], phiBreak: 0 },
    croise: { fit: [[-FX, 0], [FX, 0]], strands: [[0, -1], [1, -1], [1, 1], [0, 1]], phiBreak: 18 },
    lie: { fit: [[-FX, 0], [FX, 0]], strands: [[0, -1], [1, -1], [1, 1], [0, 1]], phiBreak: 18, knot: true },
  };

  function drawStrandLayout(container, layout, labels) {
    const L = STRAND_LAYOUTS[layout];
    const W = 176, H = 402, cx = 88, k = 9, u = 17, phiS = 18;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "sc-svg", role: "img", "aria-label": labels.aria || "" });
    const id = "s" + Math.random().toString(36).slice(2);
    const defs = el("defs", {}, svg);
    for (const c of ["ink", "good", "bad"]) {
      const m = el("marker", { id: `${id}-${c}`, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 8, markerHeight: 8, markerUnits: "userSpaceOnUse",
        orient: "auto-start-reverse" }, defs);
      el("path", { d: "M0,0 L10,5 L0,10 z", class: `sc-head-${c}` }, m);
    }
    const crossed = ([f, side]) => Math.sign(L.fit[f][0]) !== side;
    const viaKnot = (st) => L.knot && crossed(st);

    // Vue de dessus : nez pointé vers le bas (vers le centre), ferrures sur la barre
    const yb = 32;
    const clip = el("clipPath", { id: `${id}-clip` }, defs);
    el("rect", { x: 0, y: 0, width: W, height: yb + 1 }, clip);
    const nose = el("g", { "clip-path": `url(#${id}-clip)` }, svg);
    starship(nose, k, false).setAttribute("transform", `translate(${cx},${yb - 25 * k}) rotate(-90)`);
    const ts = L.fit.map(([t]) => t);
    el("line", { x1: cx + Math.min(...ts) * k, y1: yb, x2: cx + Math.max(...ts) * k, y2: yb, class: "sc-spreader" }, svg);
    const seen = {};
    L.strands.forEach(([f, side]) => {
      const key = `${f}${side}`, n = seen[key] = (seen[key] || 0) + 1;
      const twin = L.strands.filter(([g, s2]) => g === f && s2 === side).length > 1;
      const off = twin ? (n === 1 ? -1.8 : 1.8) : 0;  // brins sur la même ferrure : légèrement écartés pour rester visibles
      const dx = side * 0.5, dy = 0.866, len = (108 - yb) / dy;
      const x0 = cx + L.fit[f][0] * k + off * dy, y0 = yb - off * dx;
      el("line", { x1: x0, y1: y0, x2: x0 + dx * len, y2: y0 + dy * len, class: "sc-cable" }, svg);
    });
    L.fit.forEach(([t]) => el("circle", { cx: cx + t * k, cy: yb, r: 2.4, class: "sc-attach" }, svg));
    if (L.knot) el("circle", { cx, cy: yb + FX / 0.577 * k, r: 3.6, class: "sc-knot" }, svg);
    el("text", { x: 4, y: 13, class: "sc-small" }, svg, "dessus");
    el("text", { x: W - 4, y: 13, class: "sc-small", "text-anchor": "end" }, svg, "nez de M0");
    el("text", { x: 4, y: 50, class: "sc-small" }, svg, "M1 ↙");
    el("text", { x: W - 4, y: 50, class: "sc-small", "text-anchor": "end" }, svg, "↘ M2");
    if (labels.top) el("text", { x: cx, y: 124, class: "sc-small", "text-anchor": "middle" }, svg, labels.top);

    // Vues dans l'axe : y0 = haut du panneau
    function axial(y0, title, phiDeg, broken, label) {
      el("line", { x1: 4, y1: y0, x2: W - 4, y2: y0, class: "sc-sep" }, svg);
      el("text", { x: 4, y: y0 + 13, class: "sc-small" }, svg, title);
      const cy = y0 + 66, ph = phiDeg * Math.PI / 180, c = Math.cos(ph), s = Math.sin(ph);
      const P = ([t, z]) => [t * c - z * s, t * s + z * c];  // roulis (sens trigonométrique)
      const S = ([x, z]) => [cx + x * k, cy - z * k];
      el("circle", { cx, cy, r: 4.5 * k, class: "sc-module" }, svg);
      if (phiDeg) el("line", { x1: cx - 52, y1: cy, x2: cx + 52, y2: cy, class: "sc-axis" }, svg);
      // barre et ferrures roulées
      const tmin = Math.min(...ts), tmax = Math.max(...ts);
      const [a, b] = [S(P([tmin, 0])), S(P([tmax, 0]))];
      el("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], class: "sc-bar" }, svg);
      L.fit.forEach((f) => {
        if (f[1]) { const [p, q] = [S(P([f[0], 0])), S(P(f))]; el("line", { x1: p[0], y1: p[1], x2: q[0], y2: q[1], class: "sc-bar" }, svg); }
      });
      // tractions tangentielles : flèche fine pour un brin, épaisse pour deux
      // (ou pour le brin qui reprend la charge du brin rompu)
      let tau = 0;
      const pulls = {};
      L.strands.forEach((st, i) => {
        if (broken && i === 0) return;
        const mult = broken && st[1] === L.strands[0][1] && L.strands.findIndex((x, j) => j > 0 && x[1] === L.strands[0][1]) === i ? 2 : 1;
        const key = viaKnot(st) ? `k${st[0]}` : `${st[0]}${st[1]}`;
        pulls[key] = pulls[key] || { st, n: 0 };
        pulls[key].n += mult;
      });
      Object.values(pulls).forEach(({ st, n }) => {
        const [f, side] = st;
        const r = P(L.fit[f]), p = S(r);
        if (viaKnot(st)) {
          // patte d'oie vers le nœud, sur l'axe : traction dirigée vers l'axe
          el("line", { x1: p[0], y1: p[1], x2: cx, y2: cy, class: "sc-cable" }, svg);
          const d = Math.hypot(cx - p[0], cy - p[1]);
          el("line", { x1: p[0], y1: p[1], x2: p[0] + (cx - p[0]) / d * u, y2: p[1] + (cy - p[1]) / d * u, class: "sc-force", "marker-end": `url(#${id}-ink)` }, svg);
          return;
        }
        tau += -r[1] * side * n;  // couple autour de l'axe du vaisseau : −z·F_t
        el("line", { x1: p[0], y1: p[1], x2: p[0] + side * u, y2: p[1], class: n > 1 ? "sc-force sc-force2" : "sc-force", "marker-end": `url(#${id}-ink)` }, svg);
      });
      if (L.knot) el("circle", { cx, cy, r: 3.6, class: "sc-knot" }, svg);
      L.fit.forEach((f) => { const p = S(P(f)); el("circle", { cx: p[0], cy: p[1], r: 2.4, class: "sc-attach" }, svg); });
      if (broken) {
        // brin rompu : tireté, décalé s'il partageait sa ferrure avec le brin restant
        const [f, side] = L.strands[0], p = S(P(L.fit[f]));
        const y = p[1] - (L.strands.some(([g, s2], j) => j > 0 && g === f && s2 === side) ? 6 : 0);
        el("line", { x1: p[0], y1: y, x2: p[0] + side * u, y2: y, class: "sc-cut" }, svg);
        el("text", { x: p[0] + side * (u + 2), y: y + 3.5, class: "sc-small sc-bad", "text-anchor": side < 0 ? "end" : "start" }, svg, "×");
      }
      // couple résultant : arc sous la coque (vert s'il ramène, rouge s'il fait rouler)
      if (Math.abs(tau) > 1e-6) {
        const good = phiDeg && tau * ph < 0, cls = good ? "good" : "bad", ra = 50;
        const [a0, a1] = tau < 0 ? [55, 125] : [125, 55];
        const pt = (deg) => [cx + ra * Math.cos(deg * Math.PI / 180), cy + ra * Math.sin(deg * Math.PI / 180)];
        const [p0, p1] = [pt(a0), pt(a1)];
        el("path", { d: `M ${p0[0]} ${p0[1]} A ${ra} ${ra} 0 0 ${tau < 0 ? 1 : 0} ${p1[0]} ${p1[1]}`, class: `sc-torque sc-${cls}`, "marker-end": `url(#${id}-${cls})` }, svg);
      }
      el("text", { x: cx, y: cy + 64, class: "sc-small", "text-anchor": "middle" }, svg, label);
    }
    axial(130, `en service, roulé de ${phiS}°`, phiS, false, labels.service);
    axial(265, L.phiBreak ? `après rupture, roulé` : "juste après rupture", L.phiBreak, true, labels.rupture);
    container.classList.add("sc");
    container.innerHTML = "";
    container.appendChild(svg);
  }

  /* Brins voisins (§ 7.4) : à gauche, recul du brin rompu le long du brin
     intact (côté M0–M1 étiré, vue de dessus, centre de la station en haut :
     la force centrifuge pousse vers le bas) ; à droite, palonnier pivotant
     sur la ferrure commune, en service et après la rupture d'un brin. */
  function drawStrandRecoil(container) {
    const W = 320, H = 380, x0 = 26, x1 = 294, xm = (x0 + x1) / 2;
    const mk = (title, sub, aria) => {
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "sc-svg", role: "img", "aria-label": aria });
      const id = "r" + Math.random().toString(36).slice(2);
      const defs = el("defs", {}, svg);
      for (const c of ["ink", "bad"]) {
        const m = el("marker", { id: `${id}-${c}`, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, markerUnits: "userSpaceOnUse",
          orient: "auto-start-reverse" }, defs);
        el("path", { d: "M0,0 L10,5 L0,10 z", class: `sc-head-${c}` }, m);
      }
      el("text", { x: 8, y: 17, class: "sc-title" }, svg, title);
      el("text", { x: 8, y: 32, class: "sc-small" }, svg, sub);
      return [svg, (c) => `url(#${id}-${c})`];
    };

    // Recul
    const [a, A] = mk("Recul du brin rompu", "côté M0–M1 vu de dessus, étiré", "Recul du brin rompu le long du brin intact, en trois instants");
    el("text", { x: W - 8, y: 46, class: "sc-small", "text-anchor": "end" }, a, "↑ centre de la station");
    const row = (y, label) => {
      el("text", { x: 8, y: y - 26, class: "sc-small" }, a, label);
      el("line", { x1: x0, y1: y, x2: x1, y2: y, class: "sc-cable" }, a);
      el("circle", { cx: x0, cy: y, r: 3, class: "sc-attach" }, a);
      el("circle", { cx: x1, cy: y, r: 3, class: "sc-attach" }, a);
      el("text", { x: x0 - 6, y: y + 4, class: "sc-small", "text-anchor": "end" }, a, "M0");
      el("text", { x: x1 + 6, y: y + 4, class: "sc-small" }, a, "M1");
    };
    const red = (d) => el("path", { d, class: "sc-broken" }, a);
    const arrow = (xa, ya, xb, yb, c = "bad") => el("line", { x1: xa, y1: ya, x2: xb, y2: yb, class: c === "bad" ? "sc-broken-arrow" : "sc-force", "marker-end": A(c) }, a);
    // t = 0
    let y = 96;
    row(y, "t = 0 : un brin cède au milieu");
    red(`M ${x0} ${y + 4} L ${x1} ${y + 4}`);
    el("text", { x: xm, y: y + 8, class: "sc-small sc-bad", "text-anchor": "middle" }, a, "×");
    el("text", { x: xm, y: y + 24, class: "sc-small", "text-anchor": "middle" }, a, "255 kJ libérés");
    // t + 1 s : forces sur chaque moitié, centrifuge (vers le bas) et Coriolis
    y = 206;
    row(y, "t + 1 s : recul à 15 m/s, coupe-câbles");
    red(`M ${x0 + 14} ${y + 4} L ${xm - 22} ${y + 4}`);
    arrow(x0 + 40, y + 4, x0 + 14, y + 4);
    red(`M ${xm + 22} ${y + 6} Q ${xm + 80} ${y + 10} ${x1 - 16} ${y + 30}`);
    arrow(x1 - 44, y + 23, x1 - 16, y + 30);
    el("text", { x: x0 + 44, y: y - 7, class: "sc-small" }, a, "15 m/s");
    el("text", { x: x1 - 8, y: y - 7, class: "sc-small", "text-anchor": "end" }, a, "s'écarte en 1 s");
    arrow(xm - 52, y + 12, xm - 52, y + 28, "ink");
    arrow(xm - 40, y + 28, xm - 40, y + 12, "ink");
    el("text", { x: xm - 46, y: y + 42, class: "sc-small", "text-anchor": "middle" }, a, "se contrarient");
    arrow(xm + 50, y + 14, xm + 50, y + 30, "ink");
    arrow(xm + 62, y + 14, xm + 62, y + 30, "ink");
    el("text", { x: xm + 56, y: y + 42, class: "sc-small", "text-anchor": "middle" }, a, "s'ajoutent");
    // t + 3 s
    y = 316;
    row(y, "t + 3 s : la moitié côté M0 arrive à la ferrure");
    red(`M ${x0 + 2} ${y + 3} q 6 6 12 0 q 6 -7 12 1 L ${xm - 40} ${y + 9}`);
    arrow(x0 + 30, y + 5, x0 + 6, y + 3);
    el("circle", { cx: x0 + 10, cy: y + 2, r: 14, class: "sc-zone" }, a);
    el("text", { x: x0 + 26, y: y - 8, class: "sc-small" }, a, "zone à protéger");
    red(`M ${xm + 60} ${y + 30} Q ${xm + 100} ${y + 34} ${x1 - 8} ${y + 42}`);
    el("text", { x: x1 - 8, y: y + 26, class: "sc-small", "text-anchor": "end" }, a, "déjà loin");

    // Palonnier
    const [b] = mk("Parade : palonnier", "détail d'une ferrure, non à l'échelle", "Palonnier pivotant sur la ferrure commune, en service et après la rupture d'un brin");
    const plate = (y, broken) => {
      const px = 70, L = 56, e = 20;
      // coque et ferrure
      el("rect", { x: 8, y: y - 34, width: 26, height: 68, rx: 6, class: "sc-module" }, b);
      el("line", { x1: 34, y1: y, x2: px, y2: y, class: "sc-spreader" }, b);
      // en service, palonnier symétrique ; après rupture du brin du haut, il
      // tourne jusqu'à aligner le brin restant sur son axe
      const th = broken ? -Math.atan2(e, L) : 0;
      const R = ([u, v]) => [px + u * Math.cos(th) - v * Math.sin(th), y + u * Math.sin(th) + v * Math.cos(th)];
      const c1 = R([L, -e]), c2 = R([L, e]);
      el("path", { d: `M ${px} ${y} L ${c1[0]} ${c1[1]} L ${c2[0]} ${c2[1]} Z`, class: "sc-plate" }, b);
      if (broken) {
        el("path", { d: `M ${c1[0]} ${c1[1]} l 34 -6`, class: "sc-broken" }, b);
        el("text", { x: c1[0] + 38, y: c1[1] - 3, class: "sc-small sc-bad" }, b, "×");
        el("line", { x1: c2[0], y1: c2[1], x2: W - 8, y2: c2[1], class: "sc-cable" }, b);
        el("text", { x: W - 8, y: y + 18, class: "sc-small", "text-anchor": "end" }, b, "le brin restant tire par l'axe");
      } else {
        for (const c of [c1, c2]) el("line", { x1: c[0], y1: c[1], x2: W - 8, y2: c[1], class: "sc-cable" }, b);
        el("line", { x1: W - 40, y1: c1[1], x2: W - 40, y2: c2[1], class: "sc-dim" }, b);
        el("text", { x: W - 44, y: y + 4, class: "sc-small", "text-anchor": "end" }, b, "0,5 à 1 m");
      }
      for (const c of [c1, c2]) el("circle", { cx: c[0], cy: c[1], r: 2.4, class: "sc-attach" }, b);
      el("circle", { cx: px, cy: y, r: 4, class: "sc-knot" }, b);
      el("text", { x: px, y: y + 18, class: "sc-small", "text-anchor": "middle" }, b, "axe");
    };
    el("text", { x: 8, y: 70, class: "sc-small" }, b, "en service");
    plate(116, false);
    el("text", { x: 8, y: 184, class: "sc-small" }, b, "brins écartés sur 579 m, un seul point");
    el("text", { x: 8, y: 198, class: "sc-small" }, b, "d'effort : l'axe du palonnier");
    el("text", { x: 8, y: 222, class: "sc-small" }, b, "après rupture d'un brin");
    plate(282, true);
    el("text", { x: 8, y: 350, class: "sc-small" }, b, "le palonnier pivote : ni couple de");
    el("text", { x: 8, y: 364, class: "sc-small" }, b, "roulis, ni inclinaison permanente");

    container.innerHTML = "";
    container.appendChild(a);
    container.appendChild(b);
  }

  /* Ferrure à trois brins (§ 7.4) : à gauche, plaque triangulaire sur
     rotule vue dans l'axe du côté, Soleil selon l'axe de rotation ; à droite,
     vue de côté, en service puis après la rupture d'un brin : la plaque
     bascule autour d'un axe parallèle aux deux brins restants, qui restent
     symétriques et se partagent la charge. */
  function drawStrandFitting3(container) {
    const W = 320, H = 330;
    const mk = (title, sub, aria) => {
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "sc-svg", role: "img", "aria-label": aria });
      const id = "f" + Math.random().toString(36).slice(2);
      const defs = el("defs", {}, svg);
      for (const c of ["ink", "bad"]) {
        const m = el("marker", { id: `${id}-${c}`, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, markerUnits: "userSpaceOnUse",
          orient: "auto-start-reverse" }, defs);
        el("path", { d: "M0,0 L10,5 L0,10 z", class: `sc-head-${c}` }, m);
      }
      el("text", { x: 8, y: 17, class: "sc-title" }, svg, title);
      el("text", { x: 8, y: 32, class: "sc-small" }, svg, sub);
      return [svg, (c) => `url(#${id}-${c})`];
    };

    // Vue dans l'axe du côté
    const [a, A] = mk("Ferrure à rotule", "vue dans l'axe du côté, non à l'échelle", "Plaque triangulaire à trois brins sur une rotule, vue dans l'axe du côté");
    const cx = 160, cy = 168, s = 130, rc = s / Math.sqrt(3);
    const P = [[cx, cy - rc], [cx - s / 2, cy + rc / 2], [cx + s / 2, cy + rc / 2]];
    for (const x of [cx - 90, cx, cx + 90]) el("line", { x1: x, y1: 46, x2: x, y2: 74, class: "sc-force", "marker-end": A("ink") }, a);
    el("text", { x: cx + 100, y: 62, class: "sc-small" }, a, "Soleil");
    // colonnes d'ombre : aucune ne tombe sur un autre brin
    for (const [x, y] of P) el("line", { x1: x, y1: y + 10, x2: x, y2: H - 70, class: "sc-dim", "stroke-dasharray": "3 3" }, a);
    el("path", { d: `M ${P[0][0]} ${P[0][1]} L ${P[1][0]} ${P[1][1]} L ${P[2][0]} ${P[2][1]} Z`, class: "sc-plate" }, a);
    for (const [x, y] of P) el("circle", { cx: x, cy: y, r: 8, class: "sc-attach" }, a);
    el("circle", { cx, cy, r: 5, class: "sc-knot" }, a);
    el("text", { x: cx + 9, y: cy + 4, class: "sc-small" }, a, "rotule");
    el("line", { x1: P[1][0], y1: P[1][1] + 20, x2: P[2][0], y2: P[2][1] + 20, class: "sc-dim" }, a);
    el("text", { x: cx, y: P[1][1] + 34, class: "sc-small", "text-anchor": "middle" }, a, "0,5 à 1 m");
    el("text", { x: 8, y: H - 52, class: "sc-small" }, a, "↕ axe de rotation   ↔ plan de rotation");
    el("text", { x: 8, y: H - 34, class: "sc-small" }, a, "ombres en pointillés : aucun brin dans");
    el("text", { x: 8, y: H - 20, class: "sc-small" }, a, "l'ombre d'un autre, tous à même température");

    // Vue de côté, en service et après rupture
    const [b, B] = mk("Après la rupture d'un brin", "vue de côté, le côté part vers la droite", "Plaque à rotule vue de côté, en service puis après la rupture d'un brin");
    const px = 104, up = 44, dn = 22;
    const nose = (y) => {
      el("rect", { x: 8, y: y - 40, width: 26, height: 80, rx: 6, class: "sc-module" }, b);
      el("line", { x1: 34, y1: y, x2: px, y2: y, class: "sc-spreader" }, b);
    };
    // en service : plaque perpendiculaire au côté
    let y = 100;
    el("text", { x: 8, y: 52, class: "sc-small" }, b, "en service");
    nose(y);
    el("rect", { x: px - 3, y: y - up, width: 6, height: up + dn, class: "sc-plate" }, b);
    el("line", { x1: px, y1: y - up, x2: W - 8, y2: y - up, class: "sc-cable" }, b);
    el("line", { x1: px, y1: y + dn, x2: W - 8, y2: y + dn, class: "sc-cable" }, b);
    el("circle", { cx: px, cy: y - up, r: 2.6, class: "sc-attach" }, b);
    el("circle", { cx: px, cy: y + dn, r: 2.6, class: "sc-attach" }, b);
    el("circle", { cx: px, cy: y, r: 4, class: "sc-knot" }, b);
    el("text", { x: W - 8, y: y - up - 6, class: "sc-small", "text-anchor": "end" }, b, "brin du haut");
    el("text", { x: W - 8, y: y + dn + 14, class: "sc-small", "text-anchor": "end" }, b, "deux brins, l'un derrière l'autre");
    // après rupture : la plaque bascule de 90° autour de la rotule
    y = 236;
    el("text", { x: 8, y: 178, class: "sc-small" }, b, "après rupture du brin du haut");
    nose(y);
    el("rect", { x: px - up, y: y - 3, width: up + dn, height: 6, class: "sc-plate" }, b);
    el("path", { d: `M ${px - up} ${y} q -6 -20 6 -34 l 26 -6`, class: "sc-broken" }, b);
    el("text", { x: px - up + 38, y: y - 40, class: "sc-small sc-bad" }, b, "× largué");
    el("line", { x1: px + dn, y1: y, x2: W - 8, y2: y, class: "sc-cable" }, b);
    el("circle", { cx: px + dn, cy: y, r: 2.6, class: "sc-attach" }, b);
    el("circle", { cx: px, cy: y, r: 4, class: "sc-knot" }, b);
    el("path", { d: `M ${px + 30} ${y - 40} A 34 34 0 0 1 ${px + 36} ${y - 12}`, class: "sc-force", fill: "none", "marker-end": B("ink") }, b);
    el("text", { x: px + 42, y: y - 30, class: "sc-small" }, b, "bascule");
    el("text", { x: W - 8, y: y + 16, class: "sc-small", "text-anchor": "end" }, b, "deux brins, à parts égales");
    el("text", { x: 8, y: H - 34, class: "sc-small" }, b, "symétriques par rapport à l'axe de bascule,");
    el("text", { x: 8, y: H - 20, class: "sc-small" }, b, "les deux brins restants gardent la même longueur");

    container.innerHTML = "";
    container.appendChild(a);
    container.appendChild(b);
  }

  /* Points de capture du Starship V3 (§ 2.5) : vue de côté du nez dans le
     plan de rotation (à l'échelle), puis coupe à hauteur des points de capture
     vue depuis la pointe. Cotes estimées d'après les photos du Ship 39. */
  function drawCatchPoints(container) {
    const W = 320, H = 360;
    const mk = (title, sub, aria) => {
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "sc-svg", role: "img", "aria-label": aria });
      const id = "c" + Math.random().toString(36).slice(2);
      const defs = el("defs", {}, svg);
      const m = el("marker", { id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, markerUnits: "userSpaceOnUse",
        orient: "auto-start-reverse" }, defs);
      el("path", { d: "M0,0 L10,5 L0,10 z", class: "sc-head-ink" }, m);
      el("text", { x: 8, y: 17, class: "sc-title" }, svg, title);
      el("text", { x: 8, y: 32, class: "sc-small" }, svg, sub);
      return [svg, `url(#${id})`];
    };
    const XA = 13, SA = 4.8, RH = 4.5, LO = 14;            // attache, demi-écart, rayon, hauteur de la coiffe
    const rho = (RH * RH + LO * LO) / (2 * RH);
    const rad = (x) => x >= LO ? RH : Math.sqrt(rho * rho - (LO - x) ** 2) + RH - rho;

    // a) vue de côté, pointe vers le centre de la station (en haut)
    const [a, Aa] = mk("Points de capture", "vue de côté, dans le plan de rotation, à l'échelle", "Nez du Starship vu de côté : points de capture, câbles, bassin");
    const k = 10.5, cx = 160, y0 = 66, Y = (x) => y0 + x * k, X = (r) => cx + r * k, XM = 22;
    let d = "";
    for (let x = 0; x <= XM + 1e-9; x += 0.25) d += `${d ? "L" : "M"} ${X(rad(x)).toFixed(1)} ${Y(x).toFixed(1)} `;
    for (let x = XM; x >= -1e-9; x -= 0.25) d += `L ${(2 * cx - X(rad(x))).toFixed(1)} ${Y(x).toFixed(1)} `;
    el("path", { d: d + "Z", class: "sc-module" }, a);
    // ailerons avant déployés (hors du plan, en pointillés)
    for (const sg of [1, -1]) {
      const p = [[rad(4) + 0.1, 4], [rad(10.5), 10.5], [8.2, 10.5], [8.2, 7.5]].map(([r, x]) => `${cx + sg * r * k} ${Y(x)}`);
      el("path", { d: `M ${p.join(" L ")} Z`, class: "sc-axis", fill: "none" }, a);
    }
    el("text", { x: 8, y: Y(15.5), class: "sc-small" }, a, "- - aileron");
    el("text", { x: 8, y: Y(15.5) + 12, class: "sc-small" }, a, "(replié en vol)");
    // bassin et pont principal
    el("rect", { x: cx - 3.9 * k, y: Y(12) - 0.52 * k, width: 7.8 * k, height: 0.52 * k, class: "sc-plate" }, a);
    el("text", { x: cx, y: Y(12) - 0.52 * k - 3, class: "sc-small", "text-anchor": "middle" }, a, "bassin");
    el("line", { x1: X(-RH) + 2, y1: Y(14), x2: X(RH) - 2, y2: Y(14), class: "sc-floor" }, a);
    el("text", { x: cx, y: Y(14) + 13, class: "sc-small", "text-anchor": "middle" }, a, "pont principal (14 m)");
    // câbles à 30° de l'axe, vers les voisins
    const t30 = Math.tan(Math.PI / 6);
    for (const sg of [1, -1]) {
      const x2 = 2.6, r2 = SA + (XA - x2) * t30;
      el("line", { x1: cx + sg * SA * k, y1: Y(XA), x2: cx + sg * r2 * k, y2: Y(x2), class: "sc-cable", "marker-end": Aa }, a);
      el("rect", { x: cx + sg * RH * k - (sg > 0 ? 0 : 0.3 * k), y: Y(XA) - 2.5, width: 0.3 * k + 1, height: 5, class: "sc-attach" }, a);
      el("circle", { cx: cx + sg * SA * k, cy: Y(XA), r: 3.2, class: "sc-knot" }, a);
      el("circle", { cx: cx + sg * 3.5 * k, cy: Y(9), r: 3.2, class: "sc-axis", fill: "none" }, a);
    }
    el("text", { x: W - 8, y: Y(1.6), class: "sc-small", "text-anchor": "end" }, a, "vers le voisin");
    el("text", { x: cx, y: 52, class: "sc-small", "text-anchor": "middle" }, a, "↑ centre de la station");
    // cotes
    el("line", { x1: cx, y1: Y(0), x2: cx, y2: Y(XA), class: "sc-dim", "stroke-dasharray": "2 3" }, a);
    const yd = Y(XA) + 40;
    el("line", { x1: X(-SA), y1: yd, x2: X(SA), y2: yd, class: "sc-dim" }, a);
    for (const sg of [1, -1]) el("line", { x1: X(sg * SA), y1: Y(XA) + 5, x2: X(sg * SA), y2: yd + 4, class: "sc-dim", "stroke-dasharray": "2 3" }, a);
    el("text", { x: cx + 4, y: Y(7.2), class: "sc-small" }, a, "13 m");
    el("text", { x: X(SA) + 6, y: yd + 4, class: "sc-small" }, a, "±4,8 m");
    el("text", { x: 8, y: H - 34, class: "sc-small" }, a, "○ pointillé : ancrage du modèle précédent");
    el("text", { x: 8, y: H - 20, class: "sc-small" }, a, "(9 m, ±3,5 m) · centre de masse à 34 m ↓");

    // b) coupe à 13 m de la pointe, vue depuis la pointe
    const [b] = mk("Coupe au niveau des points", "vue depuis la pointe, à l'échelle", "Coupe du nez : bouclier, points de capture, ailerons");
    const k2 = 15, bx = 160, by = 190, R2 = RH * k2;
    const pt = (r, deg) => [bx + r * k2 * Math.sin(deg * Math.PI / 180), by - r * k2 * Math.cos(deg * Math.PI / 180)];
    el("circle", { cx: bx, cy: by, r: R2, class: "sc-module" }, b);
    // bouclier : moitié côté vent (en bas), à l'ombre
    el("path", { d: `M ${bx - R2} ${by} A ${R2} ${R2} 0 0 0 ${bx + R2} ${by}`, fill: "none", stroke: "var(--ink)", "stroke-width": 5 }, b);
    el("text", { x: bx, y: by + R2 + 18, class: "sc-small", "text-anchor": "middle" }, b, "bouclier (tuiles), à l'ombre");
    el("text", { x: bx, y: by - R2 - 30, class: "sc-small", "text-anchor": "middle" }, b, "acier, côté Soleil");
    el("text", { x: 8, y: 52, class: "sc-small" }, b, "↑ axe de rotation, vers le Soleil");
    // ailerons à ±70° du côté sous le vent : déployés (pointillés), repliés
    for (const sg of [1, -1]) {
      const h = pt(RH, sg * 70), e = pt(RH + 3.7, sg * 70);
      el("line", { x1: h[0], y1: h[1], x2: e[0], y2: e[1], class: "sc-axis", "stroke-width": 3 }, b);
      const f = pt(RH + 0.35, sg * 22);
      el("path", { d: `M ${h[0]} ${h[1]} A ${(RH + 0.2) * k2} ${(RH + 0.2) * k2} 0 0 ${sg > 0 ? 0 : 1} ${f[0]} ${f[1]}`, fill: "none", stroke: "var(--muted)",
        "stroke-width": 4 }, b);
    }
    el("text", { x: W - 8, y: by - R2 - 2, class: "sc-small", "text-anchor": "end" }, b, "aileron replié");
    el("text", { x: W - 8, y: by - 26, class: "sc-small", "text-anchor": "end" }, b, "déployé");
    // points de capture et départ des câbles dans le plan de rotation
    for (const sg of [1, -1]) {
      el("rect", { x: bx + sg * R2 - (sg > 0 ? 0 : 0.3 * k2), y: by - 3, width: 0.3 * k2, height: 6, class: "sc-attach" }, b);
      el("circle", { cx: bx + sg * SA * k2, cy: by, r: 3.6, class: "sc-knot" }, b);
      el("line", { x1: bx + sg * (SA * k2 + 4), y1: by, x2: bx + sg * (W / 2 - 10), y2: by, class: "sc-cable" }, b);
    }
    el("text", { x: 8, y: by + 16, class: "sc-small" }, b, "câble");
    el("text", { x: W - 8, y: by + 16, class: "sc-small", "text-anchor": "end" }, b, "câble");
    el("text", { x: 8, y: H - 34, class: "sc-small" }, b, "ailerons à 20° du plan des câbles ;");
    el("text", { x: 8, y: H - 20, class: "sc-small" }, b, "repliés, ils restent hors de leur chemin");

    container.innerHTML = "";
    container.appendChild(a);
    container.appendChild(b);
  }

  window.drawSchema = drawSchema;
  window.drawStrandLayout = drawStrandLayout;
  window.drawStrandRecoil = drawStrandRecoil;
  window.drawStrandFitting3 = drawStrandFitting3;
  window.drawCatchPoints = drawCatchPoints;
})();
