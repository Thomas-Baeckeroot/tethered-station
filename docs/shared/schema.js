/* Schémas des configurations (SVG, couleurs par variables CSS).
 *
 * drawSchema(container, {topology, module, spread, caption})
 *   topology : dumbbell | ladder | triangle | triangle2
 *   module   : tangential | axial | radial (orientation de l'axe long)
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

  function topView(cfg) {
    const W = 300, H = 290, cx = 150, cy = 148, Rpx = 100;
    const s = Rpx / R, ex = 3.4;
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
    const h = (cfg.module === "radial" ? LEN / 2 : A) + (cfg.bridle || 0);
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
    if (cfg.topology === "ladder") {
      const [p, q] = cables[0];
      el("text", { x: (p[0] + q[0]) / 2, y: (p[1] + q[1]) / 2 - 6, class: "sc-small", "text-anchor": "middle" }, svg, "2 câbles superposés");
    }
    // Modules
    angles.forEach((th, b) => {
      const c = P(th, R, 0);
      const g = el("g", { transform: `translate(${c[0]},${c[1]}) rotate(${-th})` }, svg);
      const L = LEN * s * ex, D = 2 * A * s * ex;
      if (cfg.module === "tangential") el("rect", { x: -D / 2, y: -L / 2, width: D, height: L, rx: D / 2, class: "sc-module" }, g);
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
    el("text", { x: 8, y: H - 8, class: "sc-small" }, svg, "modules agrandis ×3,4");
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
    const s = ex * 0.9;
    const L = LEN * s, D = 2 * A * s;
    const h0 = (cfg.module === "radial" ? LEN / 2 : A) * s;
    const h = h0 + (cfg.bridle || 0) * s;
    // Module 0 vu le long de e_t : e_r vers la droite, e_z vers le haut
    let shape, floor;
    if (cfg.module === "tangential") {
      shape = el("circle", { cx: modX, cy, r: D / 2, class: "sc-module" }, svg);
      floor = [modX + D * 0.18, cy - D * 0.42, modX + D * 0.18, cy + D * 0.42];
    } else if (cfg.module === "axial") {
      shape = el("rect", { x: modX - D / 2, y: cy - L / 2, width: D, height: L, rx: D / 2, class: "sc-module" }, svg);
      floor = [modX + D * 0.18, cy - L * 0.45, modX + D * 0.18, cy + L * 0.45];
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
    el("text", { x: 8, y: H - 8, class: "sc-small" }, svg, cfg.topology === "triangle2" ? "2 attaches, écartées de ±" + (cfg.spread ?? 20) + " m en profondeur" : "câble non à l'échelle");
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

  window.drawSchema = drawSchema;
})();
