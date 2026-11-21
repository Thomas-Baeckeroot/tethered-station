/* Vue depuis un hublot du vaisseau habité (three.js r128, UMD).
 *
 * drawPorthole(container, opts)
 *
 * Repère tournant de la station : z = axe de rotation, pointé vers le Soleil ;
 * les trois vaisseaux sont dans le plan (x, y), pointe vers le centre. Dans ce
 * repère, vaisseaux et câbles sont immobiles et le ciel tourne d'un tour par
 * minute autour de z, en sens inverse de la station. Tout est à l'échelle :
 * pointe à 324,4 m du centre (pont principal à 338,4 m, centre de masse à
 * 358,4 m), ferrures à 13 m de la pointe et à ±4,8 m de l'axe, trois brins par
 * côté écartés d'environ 0,8 m. Côté Soleil (+z) : isolant argenté et panneaux
 * fixes ; côté ombre (−z) : tuiles noires du bouclier thermique, ailerons dans
 * le plan de rotation. Le ciel est un tirage aléatoire, pas un vrai catalogue.
 */
(function () {
  "use strict";

  const OMEGA = 2 * Math.PI / 60;          // 1 tr/min
  const R_TIP = 324.4;                      // m, pointe des vaisseaux
  const X_ATT = 13, SPREAD = 4.8;           // ferrures : distance à la pointe, écart à l'axe
  const REDUCE = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

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

  /* Étoiles : fond uniforme, plus une bande de Voie lactée (grand cercle
     incliné, densité plus forte d'un côté). Pas de scintillement : pas d'air. */
  function starField(n, nBand) {
    const r = rand(20261121), R = 9000;
    const pos = [], col = [], size = [];
    const gauss = () => Math.sqrt(-2 * Math.log(r() + 1e-12)) * Math.cos(2 * Math.PI * r());
    const tint = (k) => {                   // k : 0 bleuté, 0,5 blanc, 1 orangé
      if (k < 0.5) return [0.78 + 0.44 * k, 0.86 + 0.28 * k, 1.0];
      return [1.0, 1.0 - 0.22 * (k - 0.5), 1.0 - 0.5 * (k - 0.5)];
    };
    const push = (v, b, s, k) => {
      const c = tint(k);
      pos.push(v.x * R, v.y * R, v.z * R);
      col.push(c[0] * b, c[1] * b, c[2] * b);
      size.push(s);
    };
    for (let i = 0; i < n; i++) {
      const z = 2 * r() - 1, ph = 2 * Math.PI * r(), s = Math.sqrt(1 - z * z);
      const m = Math.pow(r(), 4.5);                     // beaucoup d'étoiles faibles, peu de brillantes
      push(new THREE.Vector3(s * Math.cos(ph), s * Math.sin(ph), z), 0.22 + 0.95 * m, 1.3 + 2.6 * m, r());
    }
    // Voie lactée : pôle galactique incliné de 60° sur l'axe de rotation (ordre de grandeur réel
    // pour un axe dans le plan de l'écliptique)
    const pole = new THREE.Vector3(Math.sin(1.05), 0.25, Math.cos(1.05)).normalize();
    const u = new THREE.Vector3(0, 0, 1).cross(pole).normalize(), w = pole.clone().cross(u);
    for (let i = 0; i < nBand; i++) {
      let lon = 2 * Math.PI * r();
      if (r() < 0.45) lon = 0.9 * gauss();               // plus dense vers le centre galactique
      const lat = 0.11 * gauss() * (r() < 0.7 ? 1 : 2.2);
      const v = u.clone().multiplyScalar(Math.cos(lat) * Math.cos(lon))
        .add(w.clone().multiplyScalar(Math.cos(lat) * Math.sin(lon)))
        .add(pole.clone().multiplyScalar(Math.sin(lat)));
      push(v, 0.10 + 0.22 * Math.pow(r(), 3), 1.1 + 0.5 * r(), 0.35 + 0.4 * r());
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    g.setAttribute("size", new THREE.Float32BufferAttribute(size, 1));
    const mat = new THREE.ShaderMaterial({
      uniforms: { pr: { value: 1 } },
      vertexShader: `attribute float size; attribute vec3 color; varying vec3 vC; uniform float pr;
        void main() { vC = color; gl_PointSize = size * pr; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `varying vec3 vC;
        void main() { float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.0, d); gl_FragColor = vec4(vC * a * a, 1.0); }`,
      blending: THREE.AdditiveBlending, depthWrite: false, transparent: true,
    });
    return new THREE.Points(g, mat);
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
    // Cadrage retenu : hublot du pont principal (14,5 m de la pointe), à 70° du côté Soleil vers la ferrure,
    // regard vers le vaisseau 1 (48° au-dessus de l'horizontale du pont) ; haut de l'image = côté Soleil.
    const o = Object.assign({ side: 70, az: 90, el: 48, up: "sun", fov: 76, xCam: 14.5, roll: 0, exposure: 1, glint: 1 }, opts);
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

    const sky = starField(2600, 9000);
    sky.material.uniforms.pr.value = pr;
    const skyHolder = new THREE.Group();
    skyHolder.add(sky);
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

    let phase = o.phase || 0, last = performance.now(), visible = true, raf = null;
    const render = () => {
      skyHolder.rotation.z = -phase;       // le ciel tourne en sens inverse de la station
      renderer.render(scene, camera);
    };
    const loop = (now) => {
      raf = requestAnimationFrame(loop);
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      phase += dt * OMEGA;
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
    return { setPhase(p) { phase = p; render(); }, camera, scene, render };
  }

  window.drawPorthole = drawPorthole;
})();
