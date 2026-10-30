/* Schémas « station face au Soleil » (SVG animés, couleurs par variables CSS).
 *
 * drawSunOrbit(container, {compare, propellant_t})
 *   Vue de dessus du transfert Terre → Mars : la station (vue par la tranche)
 *   garde son axe pointé vers le Soleil. compare : ajoute l'axe fixe (B) à
 *   côté. propellant_t : ergols pour 180° (affiché au prorata de l'angle).
 * drawShipSection(container, {tech})
 *   Coupe d'un vaisseau : côté Soleil isolé, tuiles à l'ombre qui rayonnent,
 *   panneaux en ailes. tech : valeurs du bilan, et la même coupe en axe fixe.
 * drawStationSun(container, {pulses})
 *   La station en perspective, axe vers le Soleil, vaisseaux qui tournent ;
 *   pulses : petites poussées au passage de la ligne des nœuds.
 * Animations : lancées quand la figure est visible, arrêtées sinon ; image
 * fixe si l'utilisateur préfère réduire les animations.
 */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const REDUCE = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const STYLE = `
.so-sun { fill: #f2b01e; } .so-ray { stroke: #e0a100; stroke-width: 1.6; }
.so-orbit { fill: none; stroke: var(--line); stroke-width: 1.2; }
.so-path { fill: none; stroke: var(--muted); stroke-width: 1.4; stroke-dasharray: 5 4; }
.so-planet { stroke: var(--surface); stroke-width: 1.5; }
.so-lit { stroke: #e0a100; stroke-width: 3; stroke-linecap: round; }
.so-dark { stroke: #2a2f36; stroke-width: 3; stroke-linecap: round; }
.so-ghost { stroke: var(--muted); stroke-width: 1.2; stroke-linecap: round; opacity: 0.45; }
.so-axis { stroke: var(--accent); stroke-width: 1.8; fill: none; }
.so-axis-ghost { stroke: var(--muted); stroke-width: 1.3; stroke-dasharray: 3 3; fill: none; }
.so-head { fill: var(--accent); } .so-head-m { fill: var(--muted); } .so-head-c { fill: var(--steel, var(--series-1)); } .so-head-i { fill: var(--ink); }
.so-ring { fill: none; stroke: var(--accent); stroke-width: 1.5; }
.so-ship { stroke: var(--accent); stroke-width: 6; stroke-linecap: round; }
.so-ship-back { stroke: var(--accent); stroke-width: 6; stroke-linecap: round; opacity: 0.45; }
.so-panel { stroke: #1f3b63; stroke-width: 3.2; }
.so-panel-top { stroke: #e0a100; stroke-width: 1.2; }
.so-cable { stroke: var(--ink); stroke-width: 1; }
.so-node { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 4 4; }
.so-puff { stroke: var(--ink); stroke-width: 2; }
.so-hull-in { fill: color-mix(in srgb, var(--steel, var(--series-1)) 22%, var(--surface)); stroke: var(--steel, var(--series-1)); stroke-width: 1; }
.so-mli { fill: none; stroke: #c3ccd7; stroke-width: 8; }
.so-mli-edge { fill: none; stroke: var(--muted); stroke-width: 0.8; }
.so-tile { fill: none; stroke: #2a2f36; stroke-width: 8; }
.so-tile-hot { fill: none; stroke: #b4471a; stroke-width: 8; }
.so-veil { stroke: #c3ccd7; stroke-width: 1.6; }
.so-boom { stroke: var(--muted); stroke-width: 1.4; }
.so-cold { stroke: var(--steel, var(--series-1)); stroke-width: 1.5; fill: none; }
.so-hot { stroke: #d24b17; stroke-width: 1.5; fill: none; }
.so-title { font: 600 13px var(--f-display); fill: var(--ink); letter-spacing: 0.02em; }
.so-t { font: 400 10.5px var(--f-mono); fill: var(--ink-2); }
.so-s { font: 400 9.5px var(--f-mono); fill: var(--muted); }
.so-big { font: 600 12px var(--f-mono); fill: var(--ink); }
`;

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
    const id = "so" + Math.random().toString(36).slice(2);
    const defs = el("defs", {}, svg);
    for (const [k, c] of [["a", "so-head"], ["m", "so-head-m"], ["c", "so-head-c"], ["i", "so-head-i"]]) {
      const m = el("marker", { id: `${id}-${k}`, viewBox: "0 0 10 10", refX: 8, refY: 5, markerWidth: 7, markerHeight: 7,
        markerUnits: "userSpaceOnUse", orient: "auto-start-reverse" }, defs);
      el("path", { d: "M0,0 L10,5 L0,10 z", class: c }, m);
    }
    return [svg, (k) => `url(#${id}-${k})`];
  }

  const fr = (v, d = 0) => v.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });

  /* Boucle d'animation : ne tourne que si la figure est visible. */
  function animate(node, frame) {
    if (REDUCE) { frame(null); return { set: () => {} }; }
    let raf = 0, last = null, visible = false;
    const loop = (ts) => {
      const dt = last === null ? 0 : Math.min(0.1, (ts - last) / 1000);
      last = ts;
      frame(dt);
      raf = requestAnimationFrame(loop);
    };
    const start = () => { if (!raf) { last = null; raf = requestAnimationFrame(loop); } };
    const stop = () => { if (raf) cancelAnimationFrame(raf); raf = 0; };
    if ("IntersectionObserver" in window) {
      new IntersectionObserver((es) => { visible = es[0].isIntersecting; visible ? start() : stop(); }, { threshold: 0.15 }).observe(node);
    } else start();
    frame(0);
    return { start, stop, get running() { return !!raf; } };
  }

  /* --- Transfert de Hohmann ------------------------------------------------ */
  const ORB = (() => {
    const r1 = 1.0, r2 = 1.52368, a = (r1 + r2) / 2, e = (r2 - r1) / (r2 + r1);
    const n = 2 * Math.PI / (365.25636 * Math.pow(a, 1.5));
    return { a, e, n, T: Math.PI / n, r1, r2 };
  })();
  function anomaly(day) {
    const M = Math.min(Math.PI, ORB.n * day);
    let E = M;
    for (let i = 0; i < 12; i++) E -= (E - ORB.e * Math.sin(E) - M) / (1 - ORB.e * Math.cos(E));
    const nu = 2 * Math.atan2(Math.sqrt(1 + ORB.e) * Math.sin(E / 2), Math.sqrt(1 - ORB.e) * Math.cos(E / 2));
    return { nu, r: ORB.a * (1 - ORB.e * Math.cos(E)) };
  }

  function orbitPanel(mode, aria, title) {
    const W = 360, H = 300, k = 100, cx = 182, cy = 216;
    const [svg, mk] = svgBox(W, H, aria);
    el("text", { x: 10, y: 18, class: "so-title" }, svg, title);
    // Orbites (moitié haute) et transfert
    for (const [r, lab, dx] of [[ORB.r1, "orbite de la Terre", 0], [ORB.r2, "orbite de Mars", 0]]) {
      el("path", { d: `M ${cx + r * k} ${cy} A ${r * k} ${r * k} 0 0 0 ${cx - r * k} ${cy}`, class: "so-orbit" }, svg);
      void lab; void dx;
    }
    let d = "";
    for (let i = 0; i <= 90; i++) {
      const nu = Math.PI * i / 90, r = ORB.a * (1 - ORB.e * ORB.e) / (1 + ORB.e * Math.cos(nu));
      d += (i ? " L " : "M ") + (cx + r * k * Math.cos(nu)).toFixed(1) + " " + (cy - r * k * Math.sin(nu)).toFixed(1);
    }
    el("path", { d, class: "so-path" }, svg);
    // Soleil
    for (let i = 0; i < 8; i++) {
      const t = i * Math.PI / 4;
      el("line", { x1: cx + 11 * Math.cos(t), y1: cy + 11 * Math.sin(t), x2: cx + 16 * Math.cos(t), y2: cy + 16 * Math.sin(t), class: "so-ray" }, svg);
    }
    el("circle", { cx, cy, r: 8, class: "so-sun" }, svg);
    el("text", { x: cx, y: cy + 30, class: "so-t", "text-anchor": "middle" }, svg, "Soleil");
    el("circle", { cx: cx + ORB.r1 * k, cy, r: 5, class: "so-planet", fill: "#3f7fd1" }, svg);
    el("text", { x: cx + ORB.r1 * k, y: cy + 18, class: "so-t", "text-anchor": "middle" }, svg, "Terre, départ");
    el("circle", { cx: cx - ORB.r2 * k, cy, r: 4.5, class: "so-planet", fill: "#c4572e" }, svg);
    el("text", { x: cx - ORB.r2 * k + 4, y: cy + 18, class: "so-t", "text-anchor": "start" }, svg, "Mars, arrivée");
    el("text", { x: cx - ORB.r2 * k + 4, y: cy + 30, class: "so-s", "text-anchor": "start" }, svg, "jour 259");
    const P = (day) => { const { nu, r } = anomaly(day); return [cx + r * k * Math.cos(nu), cy - r * k * Math.sin(nu), nu, r]; };

    // Station : A = vue par la tranche (axe vers le Soleil) ; B = vue de face (axe vertical)
    function glyph(g, day, ghost) {
      const [x, y, nu] = P(day);
      const u = [-Math.cos(nu), Math.sin(nu)];          // vers le Soleil (écran)
      const w = [-u[1], u[0]];
      if (mode === "A") {
        const L = ghost ? 9 : 13, o = ghost ? 0 : 2.2;
        if (ghost) {
          el("line", { x1: x - w[0] * L, y1: y - w[1] * L, x2: x + w[0] * L, y2: y + w[1] * L, class: "so-ghost" }, g);
          return;
        }
        el("line", { x1: x - w[0] * L + u[0] * o, y1: y - w[1] * L + u[1] * o, x2: x + w[0] * L + u[0] * o, y2: y + w[1] * L + u[1] * o, class: "so-lit" }, g);
        el("line", { x1: x - w[0] * L - u[0] * o, y1: y - w[1] * L - u[1] * o, x2: x + w[0] * L - u[0] * o, y2: y + w[1] * L - u[1] * o, class: "so-dark" }, g);
        el("line", { x1: x + u[0] * 4, y1: y + u[1] * 4, x2: x + u[0] * 26, y2: y + u[1] * 26, class: "so-axis", "marker-end": mk("a") }, g);
        // axe s'il restait fixe (direction du départ)
        if (nu > 0.35) el("line", { x1: x, y1: y, x2: x - 24, y2: y, class: "so-axis-ghost", "marker-end": mk("m") }, g);
      } else {
        const R = ghost ? 6 : 10;
        el("circle", { cx: x, cy: y, r: R, class: ghost ? "so-ghost" : "so-ring", fill: "none" }, g);
        if (ghost) return;
        for (let i = 0; i < 3; i++) {
          const t = i * 2 * Math.PI / 3 + day * 0.6;
          el("circle", { cx: x + R * Math.cos(t), cy: y + R * Math.sin(t), r: 2.2, fill: "var(--accent)" }, g);
        }
        el("circle", { cx: x, cy: y, r: 1.4, fill: "var(--accent)" }, g);
      }
    }
    const gGhost = el("g", {}, svg);
    for (const dd of [0, 65, 130, 195, 259]) glyph(gGhost, dd, true);
    const gNow = el("g", {}, svg);
    const legend = el("g", {}, svg);
    if (mode === "A") {
      el("line", { x1: 12, y1: 40, x2: 30, y2: 40, class: "so-axis", "marker-end": mk("a") }, legend);
      el("text", { x: 36, y: 43, class: "so-s" }, legend, "axe de rotation, pointé vers le Soleil");
      el("line", { x1: 12, y1: 54, x2: 30, y2: 54, class: "so-axis-ghost", "marker-end": mk("m") }, legend);
      el("text", { x: 36, y: 57, class: "so-s" }, legend, "s'il restait fixe");
      el("line", { x1: 14, y1: 68, x2: 28, y2: 68, class: "so-lit" }, legend);
      el("text", { x: 36, y: 71, class: "so-s" }, legend, "face éclairée : panneaux");
    } else {
      el("circle", { cx: 21, cy: 44, r: 6, class: "so-ring" }, legend);
      el("text", { x: 36, y: 47, class: "so-s" }, legend, "station vue de face, axe vertical");
      el("text", { x: 36, y: 60, class: "so-s" }, legend, "le Soleil tourne autour de chaque");
      el("text", { x: 36, y: 72, class: "so-s" }, legend, "vaisseau une fois par minute");
    }
    return { svg, draw: (day) => { gNow.replaceChildren(); glyph(gNow, day, false); } };
  }

  function drawSunOrbit(container, opts = {}) {
    container.replaceChildren();
    const panels = [orbitPanel("A", "Transfert vers Mars vu de dessus : l'axe de la station suit le Soleil",
      opts.compare ? "A · face au Soleil" : "Le voyage vu de dessus")];
    if (opts.compare) panels.push(orbitPanel("B", "Transfert vers Mars vu de dessus : axe fixe, perpendiculaire à l'orbite", "B · axe fixe"));
    const row = document.createElement("div");
    row.className = opts.compare ? "sc-row" : "";
    panels.forEach((p) => row.appendChild(p.svg));
    container.appendChild(row);
    const ctrl = document.createElement("div");
    ctrl.className = "ctrl";
    const btn = document.createElement("button");
    btn.className = "btn ghost";
    btn.type = "button";
    const range = document.createElement("input");
    Object.assign(range, { type: "range", min: 0, max: Math.round(ORB.T), step: 1, value: 0 });
    range.setAttribute("aria-label", "jour du voyage");
    const out = document.createElement("span");
    out.className = "readout";
    ctrl.append(btn, range, out);
    container.appendChild(ctrl);
    let day = 0, playing = !REDUCE;
    const show = () => {
      panels.forEach((p) => p.draw(day));
      const { nu, r } = anomaly(day);
      const ang = nu * 180 / Math.PI;
      let s = `Jour ${fr(day)} · Soleil à ${fr(r, 2)} UA · l'axe a tourné de ${fr(ang)}°`;
      if (opts.propellant_t) s += ` · ergols ≈ ${fr(opts.propellant_t * ang / 180)} t`;
      out.textContent = s;
      range.value = Math.round(day);
      btn.textContent = playing ? "❚❚ pause" : "▶ lecture";
    };
    btn.addEventListener("click", () => { playing = !playing; if (playing && day >= ORB.T - 0.5) day = 0; show(); });
    range.addEventListener("input", () => { day = +range.value; playing = false; show(); });
    animate(container, (dt) => {
      if (dt && playing) {
        day += dt * 26;                                 // 10 s pour le voyage
        if (day >= ORB.T) { day = ORB.T; playing = false; }
      }
      show();
    });
    if (REDUCE) { day = 120; show(); }
  }

  /* --- Coupe d'un vaisseau ---------------------------------------------------- */
  function sectionPanel(mode, tech) {
    const W = 400, H = 330, cx = 200, cy = 176, R = 50;
    const A = mode === "A";
    const [svg, mk] = svgBox(W, H, A ? "Coupe d'un vaisseau, station face au Soleil" : "Coupe d'un vaisseau, axe fixe");
    el("text", { x: 10, y: 18, class: "so-title" }, svg, tech ? (A ? "A · face au Soleil" : "B · axe fixe") : "Coupe d'un vaisseau");
    el("text", { x: 10, y: 32, class: "so-s" }, svg, "vue depuis le centre");
    const pt = (r, a) => [cx + r * Math.cos(a * Math.PI / 180), cy - r * Math.sin(a * Math.PI / 180)];
    const arc = (r, a0, a1) => {                         // angles en degrés, sens trigonométrique
      const [x0, y0] = pt(r, a0), [x1, y1] = pt(r, a1);
      return `M ${x0.toFixed(1)} ${y0.toFixed(1)} A ${r} ${r} 0 ${Math.abs(a1 - a0) > 180 ? 1 : 0} 0 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
    };
    const lab = (x, y, t, anchor = "start", cls = "so-t") => el("text", { x, y, class: cls, "text-anchor": anchor }, svg, t);
    const lead = (x0, y0, r, a) => { const [x1, y1] = pt(r, a); el("line", { x1: x0, y1: y0, x2: x1, y2: y1, class: "so-boom" }, svg); };
    const wing = [R + 20, R + 118], yp = cy - 22;
    // Soleil
    if (A) {
      el("circle", { cx: W - 34, cy: 36, r: 9, class: "so-sun" }, svg);
      lab(W - 50, 40, "Soleil, toujours de ce côté", "end");
      for (const x of [cx - 26, cx, cx + 26]) el("line", { x1: x, y1: 56, x2: x, y2: cy - R - 12, class: "so-ray", "marker-end": mk("a") }, svg);
      for (const f of [0.3, 0.7]) {
        const x = cx + wing[0] + f * (wing[1] - wing[0]);
        el("line", { x1: x, y1: 56, x2: x, y2: yp - 6, class: "so-ray", "marker-end": mk("a") }, svg);
      }
    } else {
      el("path", { d: `M ${cx + 92} ${cy} A 92 92 0 1 1 ${cx + 91.9} ${cy - 4}`, class: "so-orbit", "marker-end": mk("m") }, svg);
      el("circle", { cx: cx + 92, cy: cy - 6, r: 8, class: "so-sun" }, svg);
      lab(W - 8, 48, "le Soleil fait le tour", "end");
      lab(W - 8, 60, "du vaisseau en une minute", "end", "so-s");
    }
    // Coque : ergols, isolant côté Soleil, tuiles côté ombre
    el("circle", { cx, cy, r: R - 4, class: "so-hull-in" }, svg);
    el("path", { d: arc(R, 0, 180), class: "so-mli" }, svg);
    el("path", { d: arc(R + 4, 0, 180), class: "so-mli-edge" }, svg);
    for (let a = 180; a < 360; a += 15) el("path", { d: arc(R, a + 1.2, a + 13.8), class: A ? "so-tile" : "so-tile-hot" }, svg);
    lab(cx, cy - 4, "ergols", "middle", "so-big");
    lab(cx, cy + 10, "liquides", "middle");
    lab(cx, cy + 23, "−180 °C", "middle", "so-s");
    // Panneaux en ailes, voile réfléchissant dessous
    if (A) for (const sg of [-1, 1]) {
      const x0 = cx + sg * wing[0], x1 = cx + sg * wing[1];
      el("line", { x1: cx + sg * R * 0.8, y1: yp + 10, x2: x0, y2: yp + 2, class: "so-boom" }, svg);
      el("line", { x1: x0, y1: yp, x2: x1, y2: yp, class: "so-panel" }, svg);
      el("line", { x1: x0, y1: yp - 2, x2: x1, y2: yp - 2, class: "so-panel-top" }, svg);
      el("line", { x1: x0, y1: yp + 6, x2: x1, y2: yp + 6, class: "so-veil" }, svg);
    }
    if (A) {
      lab(cx + wing[1], yp + 22, "panneaux solaires", "end");
      lab(cx + wing[1], yp + 34, tech ? "fixes + voile" : "fixes", "end", "so-s");
    }
    // Isolant et tuiles, avec traits de rappel
    const xl = cx - R - 80, yl = A ? 76 : cy - R - 6;
    lab(xl, yl, "isolant argenté", "middle");
    lab(xl, yl + 12, tech ? "α/ε = 0,12/0,80" : "côté Soleil", "middle", "so-s");
    lead(xl + 22, yl + 16, R + 6, 135);
    lab(cx - R - 70, cy + R + 10, A ? "tuiles noires" : "tuiles noires", "middle");
    lab(cx - R - 70, cy + R + 22, A ? "à l'ombre" : "au soleil, par moments", "middle", "so-s");
    lead(cx - R - 30, cy + R + 6, R + 4, 215);
    if (A) {
      for (const a of [-115, -90, -65]) {
        const t = a * Math.PI / 180, [x0, y0] = pt(R + 8, a), [x1, y1] = pt(R + 44, a);
        const mx = (x0 + x1) / 2 + 5 * Math.sin(t), my = (y0 + y1) / 2 + 5 * Math.cos(t);
        el("path", { d: `M ${x0} ${y0} Q ${mx} ${my} ${x1} ${y1}`, class: "so-cold", "marker-end": mk("c") }, svg);
      }
      lab(cx, H - 30, tech ? "les tuiles rayonnent ≈ 1 kW vers le ciel à −270 °C," : "la chaleur s'échappe vers l'espace à −270 °C :", "middle");
      lab(cx, H - 16, tech ? "plus que toutes les fuites réunies : il faut même chauffer un peu" : "les ergols restent froids d'eux-mêmes", "middle", "so-s");
    } else {
      for (const a of [-115, -90, -65]) {
        const [x0, y0] = pt(R + 40, a), [x1, y1] = pt(R + 8, a);
        el("line", { x1: x0, y1: y0, x2: x1, y2: y1, class: "so-hot", "marker-end": mk("a") }, svg);
      }
      lab(cx, H - 30, "les tuiles chauffées conduisent la chaleur", "middle");
      lab(cx, H - 16, "jusqu'aux ergols : 5 à 25 kW par vaisseau", "middle", "so-s");
    }
    return svg;
  }

  function drawShipSection(container, opts = {}) {
    container.replaceChildren();
    const row = document.createElement("div");
    row.className = opts.tech ? "sc-row" : "";
    row.appendChild(sectionPanel("A", !!opts.tech));
    if (opts.tech) row.appendChild(sectionPanel("B", true));
    container.appendChild(row);
  }

  /* --- La station en perspective, axe vers le Soleil ---------------------------- */
  function drawStationSun(container, opts = {}) {
    container.replaceChildren();
    const W = 360, H = 320, cx = 226, cy = 166, rx = 38, ry = 118;
    const [svg, mk] = svgBox(W, H, opts.pulses ? "Pivotement de l'axe par petites poussées au passage de la ligne des nœuds"
      : "La station en perspective, axe de rotation pointé vers le Soleil");
    container.appendChild(svg);
    el("text", { x: 10, y: 18, class: "so-title" }, svg, opts.pulses ? "Faire tourner l'axe" : "La station face au Soleil");
    // Soleil et rayons
    el("circle", { cx: 26, cy, r: 11, class: "so-sun" }, svg);
    for (let i = 0; i < 8; i++) {
      const t = i * Math.PI / 4;
      el("line", { x1: 26 + 14 * Math.cos(t), y1: cy + 14 * Math.sin(t), x2: 26 + 19 * Math.cos(t), y2: cy + 19 * Math.sin(t), class: "so-ray" }, svg);
    }
    // Plan de rotation et axe
    el("ellipse", { cx, cy, rx, ry, class: "so-orbit" }, svg);
    el("line", { x1: cx - 6, y1: cy, x2: 52, y2: cy, class: "so-axis", "marker-end": mk("a") }, svg);
    el("text", { x: 58, y: cy - 8, class: "so-t" }, svg, "axe de rotation");
    el("text", { x: 58, y: cy + 16, class: "so-s" }, svg, "pointé vers le Soleil");
    if (opts.pulses) {
      el("line", { x1: cx, y1: cy - ry - 22, x2: cx, y2: cy + ry + 22, class: "so-node" }, svg);
      el("text", { x: cx - 6, y: cy + ry + 20, class: "so-s", "text-anchor": "end" }, svg, "ligne des nœuds");
      // l'axe pivote autour de la verticale
      el("path", { d: `M 70 ${cy + 40} Q 92 ${cy + 62} 122 ${cy + 56}`, class: "so-axis-ghost", "marker-end": mk("m") }, svg);
      el("text", { x: 58, y: cy + 82, class: "so-s" }, svg, "l'axe pivote d'un cheveu");
      el("text", { x: 58, y: cy + 94, class: "so-s" }, svg, "à chaque poussée");
    } else {
      el("path", { d: `M ${cx + rx + 10} ${cy - 40} A ${rx + 10} ${ry + 10} 0 0 1 ${cx + rx + 6} ${cy + 46}`, class: "so-axis-ghost", "marker-end": mk("m") }, svg);
      el("text", { x: cx + rx + 16, y: cy + 4, class: "so-s" }, svg, "1 tour/min");
    }
    const g = el("g", {}, svg);
    const P = (phi, f) => [cx + f * rx * Math.cos(phi), cy - f * ry * Math.sin(phi)];
    let phi0 = 0.4;
    const frame = (dt) => {
      if (dt) phi0 += dt * 2 * Math.PI / 9;          // un tour en 9 s
      g.replaceChildren();
      const ph = [0, 1, 2].map((i) => phi0 + i * 2 * Math.PI / 3);
      const noses = ph.map((p) => P(p, 0.62));
      for (let i = 0; i < 3; i++) {
        const [a, b] = [noses[i], noses[(i + 1) % 3]];
        el("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], class: "so-cable" }, g);
      }
      ph.forEach((p) => {
        const front = Math.cos(p) > 0;
        const [x0, y0] = P(p, 0.62), [x1, y1] = P(p, 1.0);
        el("line", { x1: x0 - 9, y1: y0, x2: x1 - 9, y2: y1, class: "so-panel" }, g);
        el("line", { x1: x0 - 10.5, y1: y0, x2: x1 - 10.5, y2: y1, class: "so-panel-top" }, g);
        el("line", { x1: x0, y1: y0, x2: x1, y2: y1, class: front ? "so-ship" : "so-ship-back" }, g);
        if (opts.pulses) {
          const s = Math.sin(p);
          if (Math.abs(s) > Math.cos(15 * Math.PI / 180)) {
            const [xm, ym] = P(p, 0.85), dir = s > 0 ? 1 : -1;
            el("line", { x1: xm + dir * 10, y1: ym, x2: xm + dir * 40, y2: ym, class: "so-puff", "marker-end": mk("i") }, g);
          }
        }
      });
    };
    if (opts.pulses) {
      el("text", { x: W - 8, y: 40, class: "so-t", "text-anchor": "end" }, svg, "petite poussée en haut");
      el("text", { x: W - 8, y: 52, class: "so-s", "text-anchor": "end" }, svg, "≈ 20 N pendant 5 s");
      el("text", { x: W - 8, y: H - 12, class: "so-s", "text-anchor": "end" }, svg, "poussée opposée en bas");
    }
    if (REDUCE) phi0 = Math.PI / 2;
    animate(svg, frame);
  }

  window.drawSunOrbit = drawSunOrbit;
  window.drawShipSection = drawShipSection;
  window.drawStationSun = drawStationSun;
})();
