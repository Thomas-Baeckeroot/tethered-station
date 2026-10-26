/* Visualiseur 3D des trajectoires simulées (three.js r128, UMD).
 *
 * new StationViewer(container, {theme}) puis viewer.load(animJson, seriesJson?)
 * - repère tournant (par défaut) ou inertiel ;
 * - modules agrandis (facteur réglable) pour rester visibles à l'échelle de
 *   la station ; le plancher de chaque module est une plaque colorée et une
 *   flèche indique le « haut » ressenti par l'équipage ;
 * - lecture / pause, vitesse, curseur temporel, vue d'ensemble ou suivi du
 *   module 0.
 */
(function () {
  "use strict";

  const UP_BODY = { tangential: [0, 0, -1], axial: [0, -1, 0], radial: [-1, 0, 0] };

  /* Starship (cotes du plan SN8, en mètres) le long de l'axe x du corps,
     pointe en x = −25 : coiffe ogivale, fût, ailerons avant et arrière dans
     le plan (x, y). Les ailerons rendent visible la rotation propre. */
  function starshipGeometries() {
    const geos = [];
    const prof = [];
    for (let i = 0; i <= 16; i++) {
      const u = i / 16;
      prof.push(new THREE.Vector2(Math.max(4.5 * Math.sqrt(1 - (1 - u) * (1 - u)), 0.01), -25 + 13.8 * u));
    }
    const nose = new THREE.LatheGeometry(prof, 28);
    nose.rotateZ(-Math.PI / 2);
    geos.push(nose);
    const barrel = new THREE.CylinderGeometry(4.5, 4.5, 36.2, 28, 1, false);
    barrel.translate(0, 6.9, 0);
    barrel.rotateZ(-Math.PI / 2);
    geos.push(barrel);
    const flap = (pts) => {
      for (const sgn of [1, -1]) {
        const sh = new THREE.Shape(pts.map(([r, x]) => new THREE.Vector2(x, sgn * r)));
        const geo = new THREE.ExtrudeGeometry(sh, { depth: 0.4, bevelEnabled: false });
        geo.translate(0, 0, -0.2);
        geos.push(geo);
      }
    };
    flap([[3.9, -18.6], [4.5, -11.4], [7.8, -11.4], [7.8, -15.6]]);
    flap([[4.5, 11.9], [4.5, 23.8], [8.9, 23.8], [8.9, 14.5]]);
    return geos;
  }

  function cssVar(el, name, fallback) {
    const v = getComputedStyle(el).getPropertyValue(name).trim();
    return v || fallback;
  }

  class StationViewer {
    constructor(container, opts = {}) {
      this.el = container;
      this.opts = Object.assign({ exaggeration: 3, sloshExaggeration: 15, speed: 20, follow: false, autoplay: true, rotating: true }, opts);
      this.exag = this.opts.exaggeration;
      this.speed = this.opts.speed;
      this.follow = this.opts.follow;
      this.rotating = this.opts.rotating;
      this.playing = false;
      this.time = 0;
      this.onTime = null;
      this._build();
    }

    _colors() {
      const e = this.el;
      return {
        bg: cssVar(e, "--viz-bg", "#0e1116"),
        hull: cssVar(e, "--viz-hull", "#9aa7b8"),
        floor: cssVar(e, "--viz-floor", "#ff6a2b"),
        cable: cssVar(e, "--viz-cable", "#d7dde6"),
        grid: cssVar(e, "--viz-grid", "#2a313c"),
        mass: cssVar(e, "--viz-mass", "#ffd23f"),
        up: cssVar(e, "--viz-up", "#5cc8ff"),
        liquid: cssVar(e, "--viz-liquid", "#3fd0c4"),
      };
    }

    _build() {
      const w = this.el.clientWidth || 640, h = this.el.clientHeight || 400;
      this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      this.renderer.setSize(w, h);
      this.el.appendChild(this.renderer.domElement);
      this.scene = new THREE.Scene();
      this.camera = new THREE.PerspectiveCamera(40, w / h, 1, 20000);
      this.camera.up.set(0, 0, 1);
      this.camera.position.set(520, -620, 420);
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.target.set(0, 0, 0);
      this.world = new THREE.Group();
      this.scene.add(this.world);
      this.scene.add(new THREE.AmbientLight(0xffffff, 0.55));
      const sun = new THREE.DirectionalLight(0xffffff, 0.85);
      sun.position.set(400, -300, 800);
      this.scene.add(sun);
      this._applyTheme();
      this._ro = new ResizeObserver(() => this.resize());
      this._ro.observe(this.el);
      this._mq = window.matchMedia("(prefers-color-scheme: dark)");
      this._themeHandler = () => this._applyTheme(true);
      this._mq.addEventListener("change", this._themeHandler);
      this._mo = new MutationObserver(this._themeHandler);
      this._mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
      this._last = performance.now();
      const loop = (now) => {
        this._raf = requestAnimationFrame(loop);
        const dt = Math.min(0.1, (now - this._last) / 1000);
        this._last = now;
        if (this.playing && this.anim) {
          this.time += dt * this.speed;
          if (this.time > this.tEnd) this.time = this.tStart;
          this._setFrameTime(this.time);
        }
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
      };
      this._raf = requestAnimationFrame(loop);
    }

    _applyTheme(rebuild) {
      this.c = this._colors();
      this.scene.background = new THREE.Color(this.c.bg);
      if (rebuild && this.anim) this._buildObjects();
    }

    resize() {
      const w = this.el.clientWidth, h = this.el.clientHeight;
      if (!w || !h) return;
      this.renderer.setSize(w, h);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
    }

    dispose() {
      cancelAnimationFrame(this._raf);
      this._ro.disconnect();
      this._mo.disconnect();
      this._mq.removeEventListener("change", this._themeHandler);
      this.renderer.dispose();
      this.renderer.domElement.remove();
    }

    load(anim, series) {
      this.anim = anim;
      this.series = series || null;
      const f = anim.frames;
      this.tStart = f[0].t;
      this.tEnd = f[f.length - 1].t;
      this.time = this.tStart;
      // Polylignes des câbles : chaînes de segments consécutifs
      const chains = [];
      let cur = null;
      for (const [i, j] of anim.seg) {
        if (cur && cur[cur.length - 1] === i) cur.push(j);
        else { cur = [i, j]; chains.push(cur); }
      }
      this.chains = chains;
      this._buildObjects();
      this._frameCamera();
      this._setFrameTime(this.time);
      if (this.opts.autoplay) this.play();
    }

    _frameCamera() {
      const R = this.anim.info.R;
      this.camera.position.set(R * 1.35, -R * 1.6, R * 1.15);
      this.controls.target.set(0, 0, 0);
    }

    _buildObjects() {
      this.world.clear();
      const a = this.anim, c = this.c;
      const n = a.frames[0].xb.length;
      const ex = this.exag;
      this.modules = [];
      this.slosh = [];
      const up = UP_BODY[a.module];
      const ship = a.shape === "starship";
      const hullMat = () => new THREE.MeshStandardMaterial({ color: c.hull, transparent: true, opacity: 0.35, metalness: 0.2, roughness: 0.6, depthWrite: false, side: ship ? THREE.DoubleSide : THREE.FrontSide });
      const edgeMat = () => new THREE.LineBasicMaterial({ color: c.hull, transparent: true, opacity: 0.6 });
      for (let b = 0; b < n; b++) {
        const g = new THREE.Group();
        // Coque le long de l'axe x du corps : cylindre, ou Starship (pointe en −x)
        const geos = ship ? starshipGeometries() : [new THREE.CylinderGeometry(a.radius, a.radius, a.length, 28, 1, false)];
        if (!ship) geos[0].rotateZ(-Math.PI / 2);
        for (const geo of geos) {
          g.add(new THREE.Mesh(geo, hullMat()));
          g.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 30), edgeMat()));
        }
        // Ergols ballottants : masse (sphère) au bout d'un pendule articulé sur l'axe
        if (a.slosh) a.slosh.sb.forEach((sb, k) => {
          if (sb !== b) return;
          const sh = new THREE.Vector3(...a.slosh.sh[k]);
          const ball = new THREE.Mesh(new THREE.SphereGeometry(1.3 * Math.cbrt(a.slosh.sm[k] / 100), 16, 12), new THREE.MeshStandardMaterial({ color: c.liquid }));
          const rod = new THREE.Line(new THREE.BufferGeometry().setFromPoints([sh, sh.clone()]), new THREE.LineBasicMaterial({ color: c.liquid }));
          g.add(ball);
          g.add(rod);
          this.slosh.push({ k, sh, ball, rod });
        });
        // Plancher : plaque perpendiculaire au « haut »
        const upV = new THREE.Vector3(...up);
        let floor;
        if (ship && a.module === "radial") {
          // Pont de la section habitée, sous la coiffe
          floor = new THREE.Mesh(new THREE.CylinderGeometry(a.radius * 0.95, a.radius * 0.95, 0.6, 28), new THREE.MeshStandardMaterial({ color: c.floor }));
          floor.geometry.rotateZ(-Math.PI / 2);
          floor.position.set(-6, 0, 0);
          g.add(floor);
          g.add(new THREE.ArrowHelper(upV, new THREE.Vector3(-6, 0, 0), a.radius * 1.6, c.up, a.radius * 0.5, a.radius * 0.35));
          g.scale.setScalar(ex);
          this.world.add(g);
          this.modules.push(g);
          continue;
        }
        if (a.module === "radial") {
          floor = new THREE.Mesh(new THREE.CylinderGeometry(a.radius * 0.95, a.radius * 0.95, 0.6, 28), new THREE.MeshStandardMaterial({ color: c.floor }));
          floor.geometry.rotateZ(-Math.PI / 2);
        } else {
          const sx = a.length * 0.95, s2 = a.radius * 1.5;
          const dims = up[1] !== 0 ? [sx, 0.6, s2] : [sx, s2, 0.6];
          floor = new THREE.Mesh(new THREE.BoxGeometry(...dims), new THREE.MeshStandardMaterial({ color: c.floor }));
        }
        floor.position.copy(upV.clone().multiplyScalar(-a.radius * 0.35));
        g.add(floor);
        // Flèche « haut » ressenti (vers le centre de rotation)
        const arrow = new THREE.ArrowHelper(upV, upV.clone().multiplyScalar(-a.radius * 0.35), a.radius * 1.6, c.up, a.radius * 0.5, a.radius * 0.35);
        g.add(arrow);
        g.scale.setScalar(ex);
        this.world.add(g);
        this.modules.push(g);
      }
      // Câbles
      this.cableLines = this.chains.map(() => {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3 * 64), 3));
        const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: c.cable }));
        this.world.add(line);
        return line;
      });
      // Masses internes
      this.masses = (a.bi || []).map(() => {
        const m = new THREE.Mesh(new THREE.SphereGeometry(a.radius * 0.35 * ex, 16, 12), new THREE.MeshStandardMaterial({ color: c.mass }));
        this.world.add(m);
        return m;
      });
      // Repères : axe de rotation et cercle de rayon R
      const R = a.info.R;
      const ring = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(
        Array.from({ length: 128 }, (_, i) => new THREE.Vector3(R * Math.cos(i / 64 * Math.PI), R * Math.sin(i / 64 * Math.PI), 0))),
        new THREE.LineDashedMaterial({ color: c.grid, dashSize: 8, gapSize: 8 }));
      ring.computeLineDistances();
      this.world.add(ring);
      const axis = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, -R * 0.4), new THREE.Vector3(0, 0, R * 0.4)]),
        new THREE.LineBasicMaterial({ color: c.grid }));
      this.world.add(axis);
    }

    _frameAt(t) {
      const f = this.anim.frames;
      // Recherche dichotomique + interpolation linéaire
      let lo = 0, hi = f.length - 1;
      if (t <= f[0].t) return [f[0], f[0], 0];
      if (t >= f[hi].t) return [f[hi], f[hi], 0];
      while (hi - lo > 1) { const m = (lo + hi) >> 1; if (f[m].t <= t) lo = m; else hi = m; }
      return [f[lo], f[hi], (t - f[lo].t) / (f[hi].t - f[lo].t)];
    }

    _setFrameTime(t) {
      const [A, B, u] = this._frameAt(t);
      const lerp = (p, q) => p + (q - p) * u;
      const ex = this.exag;
      const qa = new THREE.Quaternion(), qb = new THREE.Quaternion();
      const xb = A.xb.map((p, b) => p.map((v, k) => lerp(v, B.xb[b][k])));
      this.modules.forEach((g, b) => {
        g.position.set(...xb[b]);
        qa.set(...A.q[b]);
        qb.set(...B.q[b]);
        if (qa.dot(qb) < 0) qb.set(-qb.x, -qb.y, -qb.z, -qb.w);
        g.quaternion.copy(qa.slerp(qb, u));
      });
      // Points d'attache : décalage agrandi comme les modules
      const nf = this.anim.nf;
      const pts = (i) => {
        if (i < nf) return A.xn[i].map((v, k) => lerp(v, B.xn[i][k]));
        const a = i - nf, body = this._attBody(a);
        const p = A.pa[a].map((v, k) => lerp(v, B.pa[a][k]));
        return p.map((v, k) => xb[body][k] + ex * (v - xb[body][k]));
      };
      this.chains.forEach((ch, ci) => {
        const arr = this.cableLines[ci].geometry.attributes.position;
        ch.forEach((i, k) => { const p = pts(i); arr.setXYZ(k, p[0], p[1], p[2]); });
        this.cableLines[ci].geometry.setDrawRange(0, ch.length);
        arr.needsUpdate = true;
        this.cableLines[ci].geometry.computeBoundingSphere();
      });
      // Écart latéral des ergols amplifié (sloshExaggeration) pour rester visible
      if (A.sd) this.slosh.forEach(({ k, sh, ball, rod }) => {
        const d = A.sd[k].map((v, i) => lerp(v, B.sd[k][i]));
        const kx = this.opts.sloshExaggeration;
        ball.position.set(sh.x + d[0], sh.y + kx * d[1], sh.z + kx * d[2]);
        const arr = rod.geometry.attributes.position;
        arr.setXYZ(1, ball.position.x, ball.position.y, ball.position.z);
        arr.needsUpdate = true;
      });
      if (A.xi) this.masses.forEach((m, k) => {
        const body = this.anim.bi[k];
        const p = A.xi[k].map((v, d) => lerp(v, B.xi[k][d]));
        m.position.set(...p.map((v, d) => xb[body][d] + ex * (v - xb[body][d])));
      });
      this.world.rotation.z = this.rotating ? 0 : this.anim.omega * t;
      if (this.follow) {
        const p = new THREE.Vector3(...xb[0]).applyAxisAngle(new THREE.Vector3(0, 0, 1), this.world.rotation.z);
        const delta = p.clone().sub(this.controls.target);
        this.controls.target.add(delta);
        this.camera.position.add(delta);
      }
      if (this.onTime) this.onTime(t);
    }

    _attBody(a) {
      // Points d'attache rangés par module (même nombre par module)
      const n = this.anim.frames[0].xb.length;
      const per = this.anim.frames[0].pa.length / n;
      return Math.floor(a / per);
    }

    play() { this.playing = true; }
    pause() { this.playing = false; }
    seek(t) { this.time = t; this._setFrameTime(t); }
    setSpeed(s) { this.speed = s; }
    setRotating(r) { this.rotating = r; this._setFrameTime(this.time); }
    setExaggeration(e) { this.exag = e; this._buildObjects(); this._setFrameTime(this.time); }
    setFollow(f) {
      this.follow = f;
      const radial = this.anim.module === "radial";
      if (f) {
        const ex = this.exag, L = this.anim.length * ex;
        const p = new THREE.Vector3(...this.anim.frames[0].xb[0]);
        const er = p.clone().setZ(0).normalize();
        this.controls.target.copy(p);
        if (radial) {
          // Module « debout » : le haut de l'écran pointe vers le centre de rotation,
          // vue de trois quarts depuis le côté
          const et = new THREE.Vector3(0, 0, 1).cross(er);
          this._setUp(er.clone().negate());
          this.camera.position.copy(p).addScaledVector(et, L * 1.6).addScaledVector(er, -L * 0.3).add(new THREE.Vector3(0, 0, L * 1.1));
        } else {
          this.camera.position.copy(p.clone().sub(er.multiplyScalar(L * 1.6)).add(new THREE.Vector3(0, 0, L * 0.9)));
        }
        this._setFrameTime(this.time);
      } else {
        if (radial) this._setUp(new THREE.Vector3(0, 0, 1));
        this._frameCamera();
      }
    }

    _setUp(up) {
      // OrbitControls fige l'orientation « haut » à sa création : on le recrée
      this.camera.up.copy(up);
      const target = this.controls.target.clone();
      this.controls.dispose();
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.target.copy(target);
    }
  }

  /* Contrôles standard (lecture, vitesse, curseur, repère, suivi) pour un viewer. */
  function attachControls(viewer, root, opts = {}) {
    const q = (s) => root.querySelector(s);
    const btn = q("[data-play]"), slider = q("[data-time]"), label = q("[data-clock]");
    const speed = q("[data-speed]"), frame = q("[data-frame]"), follow = q("[data-follow]"), readout = q("[data-readout]");
    if (slider) {
      slider.min = viewer.tStart; slider.max = viewer.tEnd; slider.step = 0.5;
      slider.addEventListener("input", () => { viewer.seek(parseFloat(slider.value)); });
    }
    const sync = () => { if (btn) btn.textContent = viewer.playing ? "Pause" : "Lecture"; };
    if (btn) btn.addEventListener("click", () => { viewer.playing ? viewer.pause() : viewer.play(); sync(); });
    if (speed) speed.addEventListener("change", () => viewer.setSpeed(parseFloat(speed.value)));
    if (frame) frame.addEventListener("change", () => viewer.setRotating(frame.value === "rot"));
    if (follow) follow.addEventListener("change", () => viewer.setFollow(follow.checked));
    const ser = viewer.series;
    viewer.onTime = (t) => {
      if (slider && document.activeElement !== slider) slider.value = t;
      if (label) label.textContent = `t = ${Math.floor(t / 60)} min ${String(Math.floor(t % 60)).padStart(2, "0")} s`;
      if (readout && ser) {
        const i = Math.max(0, Math.min(ser.t.length - 1, Math.round((t - ser.t[0]) / (ser.t[1] - ser.t[0]))));
        const parts = [];
        parts.push(`roulis ${ser.roll[0][i].toFixed(0)}°`);
        parts.push(`plancher ${ser.tilt[0][i].toFixed(1)}°`);
        parts.push(`g ${ser.g[0][i].toFixed(3)}`);
        if (ser.s && opts.mass) parts.push(`charge ${ser.s[i] >= 0 ? "+" : ""}${ser.s[i].toFixed(0)} m`);
        readout.textContent = "Module 0 : " + parts.join(" · ");
      }
    };
    sync();
    viewer.onTime(viewer.time);
  }

  window.StationViewer = StationViewer;
  window.attachStationControls = attachControls;
})();
