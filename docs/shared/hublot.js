/* Vue depuis un hublot du vaisseau habité (three.js r128, UMD).
 *
 * drawPorthole(container, opts) → { setOmega(w), setLights(on), setPhase(p), ... }
 *
 * Repère tournant de la station : z = axe de rotation, pointé vers le Soleil ;
 * les trois vaisseaux sont dans le plan (x, y), pointe vers le centre. Dans ce
 * repère, vaisseaux et câbles sont immobiles et le ciel tourne d'un tour par
 * minute autour de z, en sens inverse de la station. Tout est à l'échelle :
 * pointe à 324,4 m du centre (pont principal à 338,4 m, centre de masse à
 * 358,4 m), ferrures à 13 m de la pointe et à ±4,8 m de l'axe, trois brins par
 * côté écartés d'environ 0,8 m. Côté Soleil (+z) : isolant argenté et panneaux
 * fixes ; côté ombre (−z) : tuiles noires du bouclier thermique, ailerons avant
 * repliés.
 *
 * Ciel : vraies étoiles (window.ETOILES, Bright Star Catalogue, make_stars.py),
 * Soleil vu à la longitude écliptique 5° (dans les Poissons, vers le milieu d'un
 * voyage parti fin 2028) ; Voie lactée et Nuages de Magellan en lueur diffuse
 * placée sur le vrai plan galactique. Sans catalogue : tirage aléatoire.
 * Éclairage de la cabine : allumée, l'œil adapté à la lumière et les reflets sur
 * la vitre ne laissent passer que les étoiles les plus brillantes ; éteinte,
 * l'œil s'adapte (accéléré : une douzaine de secondes au lieu de 20 à 30 min).
 */
(function () {
  "use strict";

  const OMEGA = 2 * Math.PI / 60;          // 1 tr/min
  const R_TIP = 324.4;                      // m, pointe des vaisseaux
  const X_ATT = 13, SPREAD = 4.8;           // ferrures : distance à la pointe, écart à l'axe
  const REDUCE = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const D2R = Math.PI / 180, EPS = 23.4393 * D2R;
  const LAMBDA_SUN = 5 * D2R;               // longitude écliptique du Soleil vu du vaisseau
  const LIM_LIT = 1.7, LIM_DARK = 6.3, ADAPT_S = 12;   // magnitudes limites, durée d'adaptation affichée

  function rand(seed) {                     // mulberry32 : ciel identique à chaque chargement
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* Équatorial J2000 → repère du ciel de la station (z vers le Soleil, x vers le
     pôle nord de l'écliptique, y = z × x). */
  const SUN = new THREE.Vector3(Math.cos(LAMBDA_SUN), Math.sin(LAMBDA_SUN), 0);
  const ENP = new THREE.Vector3(0, 0, 1), EY = SUN.clone().cross(ENP);
  function skyDir(raDeg, decDeg) {
    const ra = raDeg * D2R, de = decDeg * D2R;
    const x = Math.cos(de) * Math.cos(ra), y = Math.cos(de) * Math.sin(ra), z = Math.sin(de);
    const e = new THREE.Vector3(x, y * Math.cos(EPS) + z * Math.sin(EPS), -y * Math.sin(EPS) + z * Math.cos(EPS));
    return new THREE.Vector3(e.dot(ENP), e.dot(EY), e.dot(SUN));
  }

  /* Couleur d'après l'indice B−V, désaturée (l'œil voit peu la couleur des étoiles). */
  function bvColor(bv) {
    const k = [[-0.4, [0.70, 0.78, 1.0]], [0.0, [0.84, 0.89, 1.0]], [0.4, [1.0, 0.98, 0.95]],
      [0.8, [1.0, 0.92, 0.80]], [1.2, [1.0, 0.84, 0.66]], [1.8, [1.0, 0.74, 0.52]]];
    if (bv <= k[0][0]) return k[0][1];
    for (let i = 1; i < k.length; i++) if (bv <= k[i][0]) {
      const f = (bv - k[i - 1][0]) / (k[i][0] - k[i - 1][0]), a = k[i - 1][1], b = k[i][1];
      return [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])];
    }
    return k[k.length - 1][1];
  }

  function catalogStars() {
    const E = window.ETOILES, bin = atob(E.data), pos = [], col = [], mag = [];
    const u8 = (i) => bin.charCodeAt(i), i8 = (i) => (u8(i) << 24) >> 24;
    for (let k = 0; k < E.n; k++) {
      const o = 6 * k, ra = (u8(o) | (u8(o + 1) << 8)) * 360 / 65536;
      const dec = (((u8(o + 2) | (u8(o + 3) << 8)) << 16) >> 16) * 90 / 32767;
      const v = skyDir(ra, dec).multiplyScalar(9000), c = bvColor(i8(o + 5) / 50);
      pos.push(v.x, v.y, v.z);
      col.push(c[0], c[1], c[2]);
      mag.push(i8(o + 4) / 20);
    }
    return { pos, col, mag };
  }

  function randomStars(n) {
    const r = rand(20261121), pos = [], col = [], mag = [];
    for (let i = 0; i < n; i++) {
      const z = 2 * r() - 1, ph = 2 * Math.PI * r(), s = Math.sqrt(1 - z * z);
      pos.push(9000 * s * Math.cos(ph), 9000 * s * Math.sin(ph), 9000 * z);
      const c = bvColor(-0.2 + 1.6 * r());
      col.push(c[0], c[1], c[2]);
      mag.push(6.3 - 7.5 * Math.pow(r(), 6));
    }
    return { pos, col, mag };
  }

  /* Étoiles : taille et éclat selon la magnitude, coupure douce à la magnitude
     limite de l'œil (uniforme lim). Pas de scintillement : pas d'air. */
  function starField() {
    const d = window.ETOILES ? catalogStars() : randomStars(5000);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(d.pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(d.col, 3));
    g.setAttribute("mag", new THREE.Float32BufferAttribute(d.mag, 1));
    const mat = new THREE.ShaderMaterial({
      uniforms: { pr: { value: 1 }, lim: { value: LIM_DARK }, gain: { value: 1 } },
      vertexShader: `attribute float mag; attribute vec3 color; varying vec3 vC; uniform float pr, lim, gain;
        void main() {
          float vis = smoothstep(lim + 0.35, lim - 0.35, mag);
          float b = pow(10.0, -0.4 * 0.62 * (mag + 1.0));
          vC = color * gain * vis * clamp(0.15 + 1.25 * b, 0.0, 1.5);
          gl_PointSize = clamp(5.4 - 0.62 * mag, 1.7, 6.6) * pr;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          if (vis <= 0.0) gl_PointSize = 0.0;
        }`,
      fragmentShader: `varying vec3 vC;
        void main() { float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.0, d); gl_FragColor = vec4(vC * a * a * 1.6, 1.0); }`,
      blending: THREE.AdditiveBlending, depthWrite: false, transparent: true,
    });
    return new THREE.Points(g, mat);
  }

  /* Voie lactée et Nuages de Magellan : lueur diffuse sur une sphère, calculée par
     pixel à partir des coordonnées galactiques (bulbe vers le centre, bandes
     sombres irrégulières). Schématique en détail, juste en position. */
  function milkyWay() {
    const gp = skyDir(192.8595, 27.1283), gc = skyDir(266.405, -28.936);
    const lmc = skyDir(80.89, -69.76), smc = skyDir(13.19, -72.83);
    const mat = new THREE.ShaderMaterial({
      uniforms: { gp: { value: gp }, gc: { value: gc }, lmc: { value: lmc }, smc: { value: smc }, k: { value: 1 } },
      vertexShader: `varying vec3 vP; void main() { vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `varying vec3 vP; uniform vec3 gp, gc, lmc, smc; uniform float k;
        float h(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
        float n3(vec3 p) { vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
          return mix(mix(mix(h(i), h(i + vec3(1,0,0)), f.x), mix(h(i + vec3(0,1,0)), h(i + vec3(1,1,0)), f.x), f.y),
                     mix(mix(h(i + vec3(0,0,1)), h(i + vec3(1,0,1)), f.x), mix(h(i + vec3(0,1,1)), h(i + vec3(1,1,1)), f.x), f.y), f.z); }
        void main() {
          vec3 n = normalize(vP);
          float b = asin(clamp(dot(n, gp), -1.0, 1.0));
          vec3 gq = cross(gp, gc);
          float l = atan(dot(n, gq), dot(n, gc));
          float fb = 0.5 * n3(n * 7.0) + 0.3 * n3(n * 17.0) + 0.2 * n3(n * 41.0);
          float band = exp(-pow(b / (0.075 + 0.05 * fb), 2.0)) * (0.45 + 0.55 * exp(-l * l / 0.9));
          float bulge = exp(-(b * b) / 0.018 - (l * l) / 0.09);
          float rift = smoothstep(0.35, 0.75, n3(n * 11.0 + 3.1)) * exp(-pow(b / 0.05, 2.0)) * (0.4 + 0.6 * exp(-l * l / 1.2));
          float mw = (band * (0.55 + 0.6 * fb) + 0.9 * bulge) * (1.0 - 0.75 * rift);
          mw += 0.55 * exp(-pow(acos(clamp(dot(n, lmc), -1.0, 1.0)) / 0.055, 2.0));
          mw += 0.30 * exp(-pow(acos(clamp(dot(n, smc), -1.0, 1.0)) / 0.03, 2.0));
          gl_FragColor = vec4(vec3(0.93, 0.92, 0.88) * mw * 0.12 * k, 1.0);
        }`,
      side: THREE.BackSide, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true,
    });
    return new THREE.Mesh(new THREE.SphereGeometry(9500, 64, 32), mat);
  }

  /* Starship : géométrie du visualiseur (pointe en x = −25), couleurs par sommet
     selon la face : tuiles noires côté −z, isolant argenté côté +z. */
  function shipGroup(theta, seg) {
    const g = new THREE.Group();
    const silver = new THREE.Color(0xd8dde4), tile = new THREE.Color(0x141619);
    const mat = new THREE.MeshStandardMaterial({ vertexColors: true, metalness: 0.15, roughness: 0.55 });
    const geos = window.starshipGeometries(seg);    // [coiffe, fût, aileron avant +y, −y, arrière +y, −y]
    geos.forEach((geo, gi) => {
      const n = geo.attributes.normal, cols = [];
      for (let i = 0; i < n.count; i++) {
        // ailerons avant (repliés plus bas, côté tuiles) : noirs
        const k = gi === 2 || gi === 3 ? 0 : THREE.MathUtils.smoothstep(n.getZ(i), -0.12, 0.12);
        const c = tile.clone().lerp(silver, k);
        cols.push(c.r, c.g, c.b);
      }
      geo.setAttribute("color", new THREE.Float32BufferAttribute(cols, 3));
    });
    // Ailerons avant repliés de 90° vers les tuiles (charnière parallèle à l'axe, à 4,2 m) : dans le plan
    // de rotation, ils seraient traversés par les brins qui partent des ferrures à 30° de l'axe.
    [geos[2], geos[3]].forEach((geo, k) => {
      const s = k === 0 ? 1 : -1;
      geo.translate(0, -s * 4.2, 0);
      geo.rotateX(-s * Math.PI / 2);
      geo.translate(0, s * 4.2, 0);
    });
    for (const geo of geos) g.add(new THREE.Mesh(geo, mat));
    if (seg > 28) {                         // vu de près : soudures des anneaux, tous les 1,8 m
      const ringMat = new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.22 });
      for (let x = 1.8; x < 50; x += 1.8) {
        const u = x / 13.8, r = (x < 13.8 ? 4.5 * Math.sqrt(1 - (1 - u) * (1 - u)) : 4.5) + 0.01, pts = [];
        for (let k = 0; k <= 96; k++) pts.push(new THREE.Vector3(x - 25, r * Math.cos(k * Math.PI / 48), r * Math.sin(k * Math.PI / 48)));
        g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), ringMat));
      }
    }
    // Panneaux fixes, en ailes dans un plan parallèle au plan de rotation, côté Soleil :
    // cellules vers +z, voile réfléchissant dessous (dimensions schématiques)
    const cells = new THREE.MeshStandardMaterial({ color: 0x1d3556, metalness: 0.3, roughness: 0.35 });
    const veil = new THREE.MeshStandardMaterial({ color: 0xc9ced6, metalness: 0.2, roughness: 0.5 });
    const edge = new THREE.MeshStandardMaterial({ color: 0x6b7380 });
    for (const sg of [-1, 1]) {
      const p = new THREE.Mesh(new THREE.BoxGeometry(11, 14, 0.15), [edge, edge, edge, edge, cells, veil]);
      p.position.set(0, sg * 12.5, 1.2);
      g.add(p);
    }
    const er = new THREE.Vector3(Math.cos(theta), Math.sin(theta), 0);
    g.position.copy(er.multiplyScalar(R_TIP + 25));
    g.rotation.z = theta;                   // x du corps → radial, y → tangentiel, z → axe
    return g;
  }

  function stationGeometry() {
    const th = [0, 1, 2].map((i) => -Math.PI / 2 + i * 2 * Math.PI / 3);   // vaisseau 0 en bas
    const er = (t) => new THREE.Vector3(Math.cos(t), Math.sin(t), 0);
    const et = (t) => new THREE.Vector3(-Math.sin(t), Math.cos(t), 0);
    const ships = th.map((t, i) => shipGroup(t, i === 0 ? 120 : 28));   // vaisseau 0 vu de près : coque lisse
    const segs = [], plates = [];
    for (let i = 0; i < 3; i++) {
      const j = (i + 1) % 3;
      const fit = (a, b) => {               // ferrure du vaisseau a côté du vaisseau b
        const s = Math.sign(et(th[a]).dot(er(th[b]).sub(er(th[a]))));
        return er(th[a]).multiplyScalar(R_TIP + X_ATT).add(et(th[a]).multiplyScalar(s * SPREAD));
      };
      // ferrure : broche de 0,6 m sortant de la coque, plaque au bout
      const A = fit(i, j), B = fit(j, i);
      const d = B.clone().sub(A).normalize(), p = new THREE.Vector3(0, 0, 1).cross(d).normalize(), z = new THREE.Vector3(0, 0, 1);
      const out = (a, b) => et(th[a]).multiplyScalar(Math.sign(et(th[a]).dot(er(th[b]).sub(er(th[a])))));
      const A2 = A.clone().add(out(i, j).multiplyScalar(0.6)), B2 = B.clone().add(out(j, i).multiplyScalar(0.6));
      plates.push([A, A2, d], [B, B2, d.clone().negate()]);
      // trois brins aux coins d'une plaque triangulaire (≈ 0,8 m de côté)
      for (const [a, b] of [[0, 0.46], [0.4, -0.23], [-0.4, -0.23]]) {
        const o = p.clone().multiplyScalar(a).add(z.clone().multiplyScalar(b));
        segs.push(A2.clone().add(o), B2.clone().add(o));
      }
    }
    return { th, ships, segs, plates };
  }

  /* Ferrure (broche, rotule, plaque triangulaire) et brins en cylindres de 7,6 cm :
     indispensables au premier plan ; au loin, la ligne de 1 px prend le relais. */
  function hardware(st) {
    const g = new THREE.Group();
    const steel = new THREE.MeshStandardMaterial({ color: 0x9aa3ae, metalness: 0.5, roughness: 0.4 });
    const rope = new THREE.MeshStandardMaterial({ color: 0xe9e4d8, metalness: 0.0, roughness: 0.8 });
    const Y = new THREE.Vector3(0, 1, 0);
    const cyl = (a, b, r, mat) => {
      const v = b.clone().sub(a), m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, v.length(), 12, 1, true), mat);
      m.position.copy(a.clone().add(b).multiplyScalar(0.5));
      m.quaternion.setFromUnitVectors(Y, v.normalize());
      return m;
    };
    for (const [A, A2, d] of st.plates) {
      g.add(cyl(A, A2, 0.16, steel));
      const ball = new THREE.Mesh(new THREE.SphereGeometry(0.24, 16, 12), steel);
      ball.position.copy(A2);
      g.add(ball);
      const tri = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 0.08, 3), steel);
      tri.position.copy(A2.clone().add(d.clone().multiplyScalar(0.15)));
      tri.quaternion.setFromUnitVectors(Y, d);
      g.add(tri);
    }
    for (let k = 0; k < st.segs.length; k += 2) g.add(cyl(st.segs[k], st.segs[k + 1], 0.038, rope));
    return g;
  }

  function drawPorthole(container, opts = {}) {
    // Cadrage retenu : hublot du pont principal tourné dans le sens de la rotation, juste au-dessus de la
    // ferrure (côté Soleil de 0,25 m), œil à 1,6 m du plancher (12,4 m de la pointe), regard horizontal ;
    // haut de l'image = vers le centre de la station. Les voisins sont à 59° au-dessus de l'horizon, hors
    // du champ : on voit les brins qui montent vers eux depuis la plaque, 0,6 m plus bas.
    const o = Object.assign({ side: 87, az: 90, el: 0, up: "deck", fov: 64, xCam: 12.4, roll: 0, exposure: 1, glint: 1,
      lights: false, omega: OMEGA, phase0: null }, opts);
    const w0 = container.clientWidth || 480, h0 = container.clientHeight || 300;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    const pr = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(pr);
    renderer.setSize(w0, h0);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;    // adoucit l'acier en plein Soleil
    renderer.toneMappingExposure = o.exposure;
    container.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);
    const camera = new THREE.PerspectiveCamera(o.fov, w0 / h0, 0.2, 20000);

    const sky = starField(), mw = milkyWay();
    sky.material.uniforms.pr.value = pr;
    const skyHolder = new THREE.Group();
    skyHolder.add(mw, sky);
    scene.add(skyHolder);

    scene.add(new THREE.AmbientLight(0xffffff, 0.05));
    const sun = new THREE.DirectionalLight(0xfff4e6, 1.9);
    sun.position.set(0, 0, 1);             // Soleil sur l'axe de rotation
    scene.add(sun);

    const st = stationGeometry();
    st.ships.forEach((s) => scene.add(s));
    const cg = new THREE.BufferGeometry().setFromPoints(st.segs);
    scene.add(new THREE.LineSegments(cg, new THREE.LineBasicMaterial({ color: 0xb8c0cc, transparent: true, opacity: 0.85 })));
    scene.add(hardware(st));
    // Éclat des vaisseaux lointains : à 620 m, l'acier au Soleil est un point très brillant pour l'œil ;
    // un léger halo (taille fixe à l'écran) le rend, sans agrandir le vaisseau lui-même.
    const cv = document.createElement("canvas");
    cv.width = cv.height = 64;
    const cx = cv.getContext("2d"), gr = cx.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, "rgba(255,250,240,0.9)");
    gr.addColorStop(0.18, "rgba(255,245,230,0.35)");
    gr.addColorStop(1, "rgba(255,240,220,0)");
    cx.fillStyle = gr;
    cx.fillRect(0, 0, 64, 64);
    const glintMat = new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: false, opacity: o.glint });
    st.th.slice(1).forEach((t) => {
      const sp = new THREE.Sprite(glintMat);
      sp.position.set(Math.cos(t) * (R_TIP + 22), Math.sin(t) * (R_TIP + 22), 2.5);
      sp.scale.set(0.085, 0.085, 1);
      scene.add(sp);
    });

    // Caméra au hublot : vaisseau 0 (en bas, θ = −90° ; tangentiel t = +x, vers le vaisseau 1 ;
    // centre de la station = +y), sur la coiffe à xCam m de la pointe, à l'angle `side` autour de
    // l'axe du vaisseau (0 : côté Soleil +z, 90 : côté t). Regard : azimut `az` autour de l'axe
    // (même convention), élévation `el` vers le centre de la station.
    const xc = o.xCam, u = Math.min(1, xc / 13.8), rh = 4.5 * Math.sqrt(1 - (1 - u) * (1 - u));
    const D = Math.PI / 180, sa = o.side * D, az = o.az * D, el = o.el * D;
    camera.position.set((rh + 0.35) * Math.sin(sa), -(R_TIP + xc), (rh + 0.35) * Math.cos(sa));
    const dir = new THREE.Vector3(Math.cos(el) * Math.sin(az), Math.sin(el), Math.cos(el) * Math.cos(az));
    if (o.up === "deck") camera.up.set(0, 1, 0); else camera.up.set(0, 0, 1);
    camera.lookAt(camera.position.clone().add(dir));
    if (o.roll) camera.rotateZ(o.roll * D);
    skyHolder.position.copy(camera.position);

    // Phase de départ : Bételgeuse (Orion) 15° au-dessus du centre du hublot, elle descend vers l'horizon.
    let phase = o.phase || 0;
    if (o.phase0 === null && window.ETOILES) {
      const b = skyDir(88.79, 7.41), look = camera.getWorldDirection(new THREE.Vector3());
      phase = Math.atan2(b.y, b.x) - Math.atan2(look.y, look.x) - 15 * D2R;
    }
    let omega = o.omega, lights = o.lights, adapt = lights ? 0 : 1, last = performance.now(), visible = true, raf = null;
    const applyLights = () => {
      // éteinte : magnitude limite de 1,7 à 6,3 en ADAPT_S s (cônes puis bâtonnets), Voie lactée en dernier
      const e = 1 - Math.pow(1 - adapt, 2.2);
      sky.material.uniforms.lim.value = lights ? LIM_LIT : LIM_LIT + (LIM_DARK - LIM_LIT) * e;
      sky.material.uniforms.gain.value = lights ? 0.55 : 0.55 + 0.45 * e;
      mw.material.uniforms.k.value = lights ? 0 : Math.max(0, (adapt - 0.45) / 0.55);
    };
    const render = () => {
      skyHolder.rotation.z = -phase;       // le ciel tourne en sens inverse de la station
      applyLights();
      renderer.render(scene, camera);
    };
    const loop = (now) => {
      raf = requestAnimationFrame(loop);
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      phase += dt * omega;
      if (!lights && adapt < 1) adapt = Math.min(1, adapt + dt / ADAPT_S);
      render();
    };
    const start = () => { if (!raf && !REDUCE && visible) { last = performance.now(); raf = requestAnimationFrame(loop); } };
    const stop = () => { if (raf) cancelAnimationFrame(raf); raf = null; };
    render();
    const io = new IntersectionObserver((es) => { visible = es[0].isIntersecting; visible ? start() : stop(); });
    io.observe(container);
    document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));
    new ResizeObserver(() => {
      const w = container.clientWidth, h = container.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      render();
    }).observe(container);
    start();
    return {
      setPhase(p) { phase = p; render(); },
      setOmega(w) { omega = w; },
      setLights(on) { lights = !!on; adapt = lights ? 0 : (REDUCE ? 1 : 0); render(); },
      camera, scene, render,
    };
  }

  window.drawPorthole = drawPorthole;
})();
