/* La cabine du pont principal : passager, expériences de pesanteur, hublot.
 *
 * drawCabin(figure) : `figure` contient .cabin-scene > svg.cabin-svg et
 * .cabin-window (vue three.js de hublot.js), les boutons [data-lights],
 * [data-compare], [data-preset], le curseur [data-rpm] et les sorties [data-out].
 *
 * Coupe dans le plan de rotation (vue le long de l'axe, depuis le Soleil) :
 * le haut est le centre de la station, la droite le sens de la rotation.
 * Physique exacte dans le repère tournant, pour un plancher à R = 338,4 m :
 *  - pesanteur ω²r, qui décroît vers le haut ;
 *  - pendule de 1 m dans le plan de rotation : θ'' = −ω² (a / L) sin θ, a = rayon
 *    du pivot (pendule centrifuge ; un peu plus lent que √(g/L) au niveau de la masse) ;
 *  - bille lâchée : ligne droite dans le repère inertiel, à la vitesse du point de
 *    lâcher ; vue de la cabine, elle recule (force de Coriolis) ;
 *  - balance de cuisine (force, étalonnée pour 9,806 65 m/s²) et balance à plateaux
 *    (compare deux masses). Les balances ne sont pas à l'échelle ; le reste l'est.
 * Comparaison : les mêmes expériences sur Terre (9,81 m/s², sans rotation).
 */
(function () {
  "use strict";

  const G0 = 9.80665, RF = 338.4;           // pesanteur terrestre, rayon du plancher (m)
  const K = 125, FY = 372;                  // unités SVG par mètre, plancher
  const PIV = { x: 70, y: 80 }, L = 1.0, TH0 = 14 * Math.PI / 180;   // pendule
  const DROP = { x: 150, h: 1.5 };          // fil à plomb et bille
  const PLATE_H = 0.86;                     // plateau de la balance de cuisine (m)
  const REDUCE = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const NS = "http://www.w3.org/2000/svg";
  const fr = (v, d = 0) => v.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  const yOf = (hm) => FY - K * hm;          // hauteur au-dessus du plancher → y SVG

  /* Bille lâchée de h au-dessus du plancher : position (recul, hauteur) en m au temps t. */
  function dropMars(w, h, t) {
    const r0 = RF - h, wt = w * t, rho = r0 * Math.sqrt(1 + wt * wt);
    const phi = Math.atan(wt) - wt;          // < 0 : en arrière du sens de rotation
    return { dx: rho * phi, hm: RF - rho };
  }
  const dropTime = (w, h) => Math.sqrt(Math.pow(RF / (RF - h), 2) - 1) / w;

  function drawCabin(fig) {
    const svg = fig.querySelector(".cabin-svg");
    const out = (k) => fig.querySelector(`[data-out="${k}"]`);
    let rpm = 1, w = 2 * Math.PI / 60, compare = false, lights = true, porthole = null;

    /* Décor */
    const defs = el("defs", {}, svg), cp = el("clipPath", { id: "cb-inside" }, defs);
    el("rect", { x: 14, y: 72, width: 370, height: FY - 72 }, cp);
    const g = el("g", {}, svg);
    el("rect", { x: 0, y: 0, width: 640, height: 400, class: "cb-space" }, g);
    el("rect", { x: 14, y: 72, width: 370, height: FY - 72, class: "cb-wall" }, g);
    for (let x = 74; x < 384; x += 62) el("line", { x1: x, y1: 72, x2: x, y2: FY, class: "cb-panel" }, g);
    el("line", { x1: 14, y1: yOf(1.1), x2: 384, y2: yOf(1.1), class: "cb-panel" }, g);
    el("rect", { x: 6, y: 60, width: 386, height: 12, class: "cb-struct" }, g);           // plafond
    el("rect", { x: 6, y: FY, width: 386, height: 14, class: "cb-struct" }, g);           // plancher
    el("line", { x1: 14, y1: FY, x2: 384, y2: FY, class: "cb-floor" }, g);
    el("rect", { x: 6, y: 60, width: 8, height: FY - 60 + 14, class: "cb-struct" }, g);    // paroi arrière
    // paroi avant (sens de la rotation) et son hublot
    el("rect", { x: 384, y: 60, width: 10, height: yOf(1.86) - 60, class: "cb-struct" }, g);
    el("rect", { x: 384, y: yOf(1.34), width: 10, height: FY + 14 - yOf(1.34), class: "cb-struct" }, g);
    el("rect", { x: 386, y: yOf(1.86), width: 6, height: K * 0.52, class: "cb-glass" }, g);
    el("rect", { x: 190, y: 72, width: 110, height: 5, rx: 2, class: "cb-lamp" }, g);
    el("ellipse", { cx: 245, cy: 77, rx: 130, ry: 40, class: "cb-lampglow", "clip-path": "url(#cb-inside)" }, g);
    el("circle", { cx: 24, cy: FY - 10, r: 3, class: "cb-night" }, g);
    el("ellipse", { cx: 24, cy: FY - 6, rx: 70, ry: 30, class: "cb-nightglow", "clip-path": "url(#cb-inside)" }, g);
    // repères
    const t1 = el("text", { x: 24, y: 96, class: "cb-label" }, g);
    t1.textContent = "↑ centre de la station";
    const t2 = el("text", { x: 214, y: 397, class: "cb-label" }, g);
    t2.textContent = "sens de la rotation →";
    // regard du passager vers le hublot, puis vers le médaillon
    el("path", { d: "M366 170 L398 128 M366 170 L398 214", class: "cb-sight" }, g);
    el("path", { d: "M398 128 L452 88 M398 214 L452 292", class: "cb-sight" }, g);

    /* Pendule : support au plafond */
    el("rect", { x: PIV.x - 14, y: 72, width: 28, height: 6, class: "cb-obj" }, g);
    el("line", { x1: PIV.x, y1: 78, x2: PIV.x, y2: PIV.y, class: "cb-objline" }, g);
    const lblP = el("text", { x: PIV.x + 18, y: PIV.y + 66, class: "cb-label" }, g);
    lblP.textContent = "1 m";
    const pendE = el("g", { class: "cb-earth" }, g);
    const rodE = el("line", { class: "cb-earthline" }, pendE), bobE = el("circle", { r: 8, class: "cb-earthfill" }, pendE);
    const pend = el("g", {}, g);
    const rod = el("line", { class: "cb-objline" }, pend), bob = el("circle", { r: 8, class: "cb-bob" }, pend);

    /* Fil à plomb et bille */
    const yRel = yOf(DROP.h);
    el("line", { x1: DROP.x + 30, y1: FY, x2: DROP.x + 30, y2: yRel - 14, class: "cb-objline thick" }, g);
    el("line", { x1: DROP.x + 30, y1: yRel - 14, x2: DROP.x - 4, y2: yRel - 14, class: "cb-objline thick" }, g);
    el("line", { x1: DROP.x, y1: yRel - 14, x2: DROP.x, y2: FY - 10, class: "cb-plumb" }, g);
    el("path", { d: `M${DROP.x - 4} ${FY - 12} L${DROP.x + 4} ${FY - 12} L${DROP.x} ${FY - 3} Z`, class: "cb-bob" }, g);
    const hDim = el("text", { x: DROP.x - 10, y: (yRel + FY) / 2 + 28, class: "cb-label", "text-anchor": "end" }, g);
    hDim.textContent = "1,5 m";
    const trail = el("g", {}, g), trailE = el("g", { class: "cb-earth" }, g);
    const mark = el("g", {}, g);
    const markLine = el("path", { class: "cb-dim" }, mark), markTxt = el("text", { class: "cb-label", "text-anchor": "end" }, mark);
    const ballE = el("circle", { r: 5, class: "cb-earthfill cb-earth" }, g);
    const ball = el("circle", { r: 5, class: "cb-ball" }, g);

    /* Table, balance de cuisine, balance à plateaux */
    const TY = yOf(0.8);
    el("rect", { x: 196, y: TY, width: 112, height: 6, class: "cb-obj" }, g);
    el("rect", { x: 204, y: TY + 6, width: 5, height: FY - TY - 6, class: "cb-obj" }, g);
    el("rect", { x: 295, y: TY + 6, width: 5, height: FY - TY - 6, class: "cb-obj" }, g);
    el("rect", { x: 202, y: TY - 17, width: 48, height: 17, rx: 3, class: "cb-objfill" }, g);
    el("rect", { x: 206, y: TY - 20, width: 40, height: 3, class: "cb-obj" }, g);
    el("rect", { x: 214, y: TY - 40, width: 24, height: 20, rx: 2, class: "cb-mass" }, g);
    const kg1 = el("text", { x: 226, y: TY - 27, class: "cb-masstxt", "text-anchor": "middle" }, g);
    kg1.textContent = "1 kg";
    el("rect", { x: 207, y: TY - 14.5, width: 38, height: 12, rx: 1.5, class: "cb-lcd" }, g);
    const lcd = el("text", { x: 242, y: TY - 4.8, class: "cb-lcdtxt", "text-anchor": "end" }, g);
    const lcdE = el("text", { x: 252, y: TY + 22, class: "cb-label cb-earthtxt cb-earth", "text-anchor": "middle" }, g);
    lcdE.textContent = "Terre 1000 g";
    // balance à plateaux (fléau horizontal : 1 kg contre 1 kg)
    const bx = 280;
    el("rect", { x: bx - 12, y: TY - 4, width: 24, height: 4, class: "cb-obj" }, g);
    el("line", { x1: bx, y1: TY - 4, x2: bx, y2: TY - 30, class: "cb-objline thick" }, g);
    el("line", { x1: bx - 22, y1: TY - 30, x2: bx + 22, y2: TY - 30, class: "cb-objline thick" }, g);
    for (const s of [-1, 1]) {
      el("line", { x1: bx + 22 * s, y1: TY - 30, x2: bx + 22 * s, y2: TY - 22, class: "cb-objline" }, g);
      el("rect", { x: bx + 22 * s - 9, y: TY - 23, width: 18, height: 2.5, class: "cb-obj" }, g);
      el("rect", { x: bx + 22 * s - 6, y: TY - 35, width: 12, height: 12, rx: 1.5, class: "cb-mass" }, g);
    }
    const kg2 = el("text", { x: bx, y: TY - 46, class: "cb-label", "text-anchor": "middle" }, g);
    kg2.textContent = "1 kg | 1 kg";

    /* Passager debout (1,75 m), de profil, tourné vers le hublot */
    const pp = el("g", { class: "cb-person" }, g);
    el("circle", { cx: 354, cy: yOf(1.615), r: 13.5 }, pp);
    el("rect", { x: 349, y: yOf(1.52), width: 9, height: 10 }, pp);
    el("rect", { x: 337, y: yOf(1.46), width: 33, height: K * 0.62, rx: 11 }, pp);
    el("rect", { x: 341, y: yOf(0.9), width: 15, height: K * 0.9, rx: 6 }, pp);
    el("rect", { x: 350, y: yOf(0.9), width: 15, height: K * 0.9, rx: 6 }, pp);
    el("rect", { x: 341, y: FY - 8, width: 33, height: 8, rx: 3 }, pp);
    el("rect", { x: 352, y: yOf(1.43), width: 11, height: K * 0.6, rx: 5.5, class: "cb-arm" }, pp);

    /* Légende de la comparaison */
    const leg = el("g", { class: "cb-earth" }, g);
    el("line", { x1: 196, y1: 92, x2: 214, y2: 92, class: "cb-earthline" }, leg);
    const legT = el("text", { x: 219, y: 96, class: "cb-label cb-earthtxt" }, leg);
    legT.textContent = "sur Terre";

    /* État des expériences */
    let th = TH0, thd = 0, thE = TH0, thdE = 0, tDrop = 0, last = performance.now(), raf = null, visible = true;
    const HOLD = 0.9, REST = 1.8;
    const pivotA = () => RF - (FY - PIV.y) / K;            // rayon du pivot
    function stepPendulum(dt) {
      const k = w * w * pivotA() / L, kE = G0 / L, n = Math.max(1, Math.ceil(dt / 0.004)), h = dt / n;
      for (let i = 0; i < n; i++) {
        thd += -k * Math.sin(th) * h; th += thd * h;          // Euler symplectique, pas de 4 ms
        thdE += -kE * Math.sin(thE) * h; thE += thdE * h;
      }
    }
    function drawPendulum() {
      const len = K * L;
      const put = (r, b, a) => {
        const x = PIV.x + len * Math.sin(a), y = PIV.y + len * Math.cos(a);
        r.setAttribute("x1", PIV.x); r.setAttribute("y1", PIV.y); r.setAttribute("x2", x); r.setAttribute("y2", y);
        b.setAttribute("cx", x); b.setAttribute("cy", y);
      };
      put(rod, bob, -th);                    // départ du côté du sens de la rotation
      put(rodE, bobE, -thE);
    }
    function drawDrop() {
      const tf = dropTime(w, DROP.h), tfE = Math.sqrt(2 * DROP.h / G0);
      const t = Math.max(0, tDrop - HOLD);
      const pos = (tt) => { const p = dropMars(w, DROP.h, Math.min(tt, tf)); return [DROP.x + K * p.dx, yOf(p.hm) - 5]; };
      const posE = (tt) => [DROP.x, yOf(DROP.h - 0.5 * G0 * Math.min(tt, tfE) * Math.min(tt, tfE)) - 5];
      const [x, y] = pos(t), [xE, yE] = posE(t);
      ball.setAttribute("cx", x); ball.setAttribute("cy", y);
      ballE.setAttribute("cx", xE); ballE.setAttribute("cy", yE);
      // trace stroboscopique tous les 0,1 s
      const strobe = (grp, f, T) => {
        const n = Math.floor(Math.min(t, T) / 0.1);
        while (grp.childNodes.length > n) grp.removeChild(grp.lastChild);
        for (let i = grp.childNodes.length; i < n; i++) {
          const [sx, sy] = f((i + 1) * 0.1);
          el("circle", { cx: sx, cy: sy, r: 2.2, class: grp === trail ? "cb-strobe" : "cb-earthfill cb-strobeE" }, grp);
        }
      };
      strobe(trail, pos, tf);
      strobe(trailE, posE, tfE);
      const landed = t >= tf;
      mark.style.display = landed ? "" : "none";
      if (landed) {
        const dx = dropMars(w, DROP.h, tf).dx, xl = DROP.x + K * dx;
        markLine.setAttribute("d", `M${xl} ${FY + 15} L${xl} ${FY + 21} L${DROP.x} ${FY + 21} L${DROP.x} ${FY + 15}`);
        markTxt.setAttribute("x", xl - 4);
        markTxt.setAttribute("y", 397);
        markTxt.textContent = fr(100 * Math.abs(dx), 1) + " cm";
      }
      return HOLD + Math.max(tf, compare ? tfE : 0) + REST;
    }
    function readouts() {
      const gF = w * w * RF;
      out("rpm").textContent = fr(rpm, 2) + " tr/min";
      out("g").textContent = fr(gF, 2) + " m/s²";
      out("g-sub").textContent = "au plancher, soit " + fr(gF / G0, 2) + " g" + (compare ? " (Terre : 9,81 m/s²)" : "");
      const T = 2 * Math.PI / (w * Math.sqrt(pivotA() / L));
      out("p").textContent = fr(T, 2) + " s";
      out("p-sub").textContent = "période du pendule de 1 m" + (compare ? " (Terre : " + fr(2 * Math.PI * Math.sqrt(L / G0), 2) + " s)" : "");
      const m = 1000 * w * w * (RF - PLATE_H) / G0;
      out("b").textContent = fr(m) + " g";
      lcd.textContent = fr(m) + " g";
      out("b-sub").textContent = "lus par la balance de cuisine pour 1 kg" + (compare ? " (Terre : 1000 g)" : "");
      const tf = dropTime(w, DROP.h), d = Math.abs(dropMars(w, DROP.h, tf).dx);
      out("d").textContent = fr(100 * d, 1) + " cm";
      out("d-sub").textContent = "recul de la bille lâchée de 1,5 m, chute en " + fr(tf, 2) + " s" + (compare ? " (Terre : 0 cm, " + fr(Math.sqrt(2 * DROP.h / G0), 2) + " s)" : "");
      fig.querySelectorAll("[data-preset]").forEach((b) => b.setAttribute("aria-pressed", Math.abs(parseFloat(b.dataset.preset) - rpm) < 0.006 ? "true" : "false"));
    }

    let cycle = HOLD + 1 + REST;
    const frame = (dt) => {
      stepPendulum(dt);
      tDrop += dt;
      if (tDrop > cycle) tDrop = 0;
      drawPendulum();
      cycle = drawDrop();
    };
    const loop = (now) => {
      raf = requestAnimationFrame(loop);
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      frame(dt);
    };
    const start = () => { if (!raf && !REDUCE && visible) { last = performance.now(); raf = requestAnimationFrame(loop); } };
    const stop = () => { if (raf) cancelAnimationFrame(raf); raf = null; };
    const still = () => {                    // mouvement réduit : pendule écarté, bille posée avec sa trace
      th = thE = TH0; drawPendulum();
      tDrop = HOLD + 5; drawDrop();
    };

    /* Commandes */
    const setRpm = (v) => {
      rpm = Math.min(2, Math.max(0.25, v));
      w = rpm * 2 * Math.PI / 60;
      const sl = fig.querySelector("[data-rpm]");
      if (Math.abs(parseFloat(sl.value) - rpm) > 1e-9) sl.value = rpm;
      if (porthole) porthole.setOmega(w);
      readouts();
      if (REDUCE) still();
    };
    fig.querySelector("[data-rpm]").addEventListener("input", (e) => setRpm(parseFloat(e.target.value)));
    fig.querySelectorAll("[data-preset]").forEach((b) => b.addEventListener("click", () => setRpm(parseFloat(b.dataset.preset))));
    fig.querySelectorAll("[data-lights]").forEach((b) => b.addEventListener("click", () => {
      lights = b.dataset.lights === "on";
      fig.dataset.lights = lights ? "on" : "off";
      fig.querySelectorAll("[data-lights]").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
      if (porthole) porthole.setLights(lights);
    }));
    const cmp = fig.querySelector("[data-compare]");
    cmp.addEventListener("click", () => {
      compare = !compare;
      cmp.setAttribute("aria-pressed", compare ? "true" : "false");
      fig.dataset.compare = compare ? "on" : "off";
      th = thE = TH0; thd = thdE = 0; tDrop = 0;         // départ synchronisé
      readouts();
      if (REDUCE) still();
    });
    const zb = fig.querySelector("[data-zoom]");
    const toggleZoom = () => {
      const on = fig.dataset.zoom !== "on";
      fig.dataset.zoom = on ? "on" : "off";
      zb.setAttribute("aria-pressed", on ? "true" : "false");
      zb.textContent = on ? "Revenir à la cabine" : "Agrandir le hublot";
    };
    zb.addEventListener("click", toggleZoom);
    fig.querySelector(".cabin-window").addEventListener("click", toggleZoom);
    fig.dataset.lights = "on";
    fig.dataset.compare = "off";
    fig.dataset.zoom = "off";

    /* Hublot */
    const win = fig.querySelector(".cabin-window");
    if (win && window.THREE && window.drawPorthole) {
      try { porthole = window.drawPorthole(win, { lights: true }); } catch (e) { win.classList.add("no-webgl"); }
    }

    readouts();
    if (REDUCE) still(); else { drawPendulum(); drawDrop(); }
    new IntersectionObserver((es) => { visible = es[0].isIntersecting; visible ? start() : stop(); }).observe(fig);
    document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));
    start();
  }

  window.drawCabin = drawCabin;
})();
