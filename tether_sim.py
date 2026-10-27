#!/usr/bin/env python3
"""
Station à gravité artificielle : modules massifs reliés par des câbles, en
rotation, en orbite haute (gravité terrestre / effet de marée négligés :
n²/ω² ~ 7e-5 à 1600 km et 1 tr/min).

Modèle :
- repère inertiel centré sur le centre de masse, rotation autour de z ;
- modules = corps rigides (cylindres pleins équivalents) avec leur inertie
  propre et des points d'attache décalés du centre de masse ;
- câbles = chaînes de masses reliées par des ressorts UNILATÉRAUX (tirent, ne
  poussent pas), amortissement interne (Kelvin-Voigt), AUCUNE raideur en
  torsion (câble tressé, ou émerillon au point d'attache) ;
- masses internes mobiles (équipage, cargaison) : masses ponctuelles
  asservies (ressort-amortisseur raide) à une trajectoire imposée dans le
  repère du module ; les forces sont internes, la réaction s'applique au
  module ;
- amortisseur interne optionnel (ballottement des liquides) : sphère
  isotrope couplée visqueusement à la rotation du module (amortisseur de
  nutation de Kane) ;
- intégration « kick-drift-kick » ; rotation libre des corps par
  décomposition symétrique autour des axes principaux (symplectique,
  conserve |L| exactement) ; amortissement des câbles appliqué de façon
  exacte à part ;
- options : moyeu central (masse ponctuelle) relié à chaque module par un
  rayon légèrement prétendu ; rupture d'un câble (un segment cesse de porter
  à un instant donné, son énergie élastique est comptée comme dissipée).

Dimensionnement : rayon R = a/ω² déduit de la gravité et de la vitesse de
rotation visées (au centre de masse des modules), longueur des câbles déduite
de R ; section dimensionnée pour une gravité de conception (1 g par défaut)
avec un facteur de sécurité.

Diagnostics : gravité ressentie, tension, roulis des modules autour du câble
(= rotation de la pièce autour de la verticale), inclinaison du plancher par
rapport à la gravité apparente, vitesse de rotation parasite ressentie,
bilan d'énergie (énergie + dissipée) et moment cinétique.
"""
import argparse
import json
import math
import os

import numpy as np

G0 = 9.80665

# Matériaux : module d'Young E (Pa), masse volumique (kg/m³), résistance (Pa)
MATERIALS = {
    "dyneema": dict(E=100e9, rho=970.0, sigma=3.0e9),
    "kevlar": dict(E=112e9, rho=1440.0, sigma=3.0e9),
    "steel": dict(E=200e9, rho=7850.0, sigma=1.5e9),
}

# Orientation de l'axe long du module dans le repère local (e_r radial,
# e_t tangentiel, e_z axe de rotation) : axes principaux du corps
# (b1 = axe long, b2, b3), repère direct.
ORIENTATIONS = {
    "tangential": lambda er, et, ez: (et, ez, er),
    "axial": lambda er, et, ez: (ez, er, et),
    "radial": lambda er, et, ez: (er, et, ez),
}
# Axe du corps servant à mesurer le roulis autour du câble, et son angle
# nominal dans le plan (e_t, e_z)
ROLL_REF = {"tangential": (0, 0.0), "axial": (0, math.pi / 2), "radial": (1, 0.0)}

# --- Starship en route : modèle de masse et ballottement des ergols --------
# Coordonnée x le long de l'axe, depuis la pointe (0) vers les moteurs (50 m).
# Éléments rigides : (nom, masse t, x0, x1, rayon, coque mince ?) ; la charge
# utile (équipage, cargaison) occupe la section sous la coiffe.
SHIP_PARTS = (("coiffe", 25.0, 0.0, 14.0, 3.0, True), ("fût", 55.0, 14.0, 50.0, 4.5, True),
              ("moteurs", 25.0, 44.0, 50.0, 2.5, False), ("charge", 115.0, 4.0, 20.0, 4.0, False))
# Réservoirs : (nom, masse volumique kg/m³, fond en m depuis la pointe, longueur m, part des ergols)
SHIP_TANKS = (("LOX", 1141.0, 46.0, 11.0, 3.6 / 4.6), ("CH4", 422.0, 35.0, 13.0, 1.0 / 4.6))
SHIP_TANK_RADIUS = 4.5
SLOSH_XI = 1.841  # premier zéro de J1' (premier mode latéral)


def slosh_tank(m, depth, a=SHIP_TANK_RADIUS):
    """Pendule équivalent du premier mode de ballottement latéral d'un
    réservoir cylindrique à fond plat (Abramson 1966, NASA SP-106) : masse
    ballottante, longueur du pendule, hauteur de l'articulation H et de la
    masse hb au-dessus du fond, masse fixe et sa hauteur (même centre de masse
    que le liquide au repos). Fréquence : √(g/L) sous une gravité g le long de
    l'axe, soit ω² = 1,841·(g/a)·tanh(1,841·d/a)."""
    x = SLOSH_XI * depth / a
    ms = m * a / (2.199 * depth) * math.tanh(x)
    L = a / (SLOSH_XI * math.tanh(x))
    H = depth - a / SLOSH_XI * (math.tanh(x / 2) - 1 / math.sinh(x))
    hb = H - L
    mf = m - ms
    hf = (m * depth / 2 - ms * hb) / mf
    return dict(m=m, depth=depth, ms=ms, L=L, H=H, hb=hb, mf=mf, hf=hf)


def starship_mass_model(M_t, slosh=True, tld=None):
    """Starship en route : structure et charge utile (SHIP_PARTS), ergols
    restants (rapport de mélange 3,6) posés au fond de leurs réservoirs par la
    gravité artificielle. Partie rigide : éléments de structure, charge, masse
    fixe des liquides (ponctuelle : le liquide ne tourne pas avec le
    réservoir autour de l'axe) et, si slosh=False, masses ballottantes figées
    à leur position d'équilibre. Positions en m depuis la pointe.

    tld : amortisseur à liquide accordé, dict(m_t, x, a, zeta) : bassin d'eau
    cylindrique de rayon a dont le fond est à x de la pointe ; son eau est
    prise sur la charge utile (masse totale inchangée). Toujours libre."""
    rigid = []  # (masse kg, x, I_axe propre, I_transverse propre)
    for name, m_t, x0, x1, r, shell in SHIP_PARTS:
        if name == "charge" and tld:
            m_t -= tld["m_t"]
        m, ell = m_t * 1e3, x1 - x0
        rigid.append((m, (x0 + x1) / 2, m * r * r * (1.0 if shell else 0.5), m * (r * r * (0.5 if shell else 0.25) + ell * ell / 12)))
    prop = (M_t - sum(p[1] for p in SHIP_PARTS)) * 1e3
    tanks, pend = [], []
    for name, rho, x_bottom, length, frac in SHIP_TANKS:
        m = prop * frac
        depth = m / (rho * math.pi * SHIP_TANK_RADIUS ** 2)
        if depth > length:
            raise ValueError(f"réservoir {name} : {depth:.1f} m de liquide pour {length:g} m de réservoir")
        tk = slosh_tank(m, depth)
        tk.update(name=name, x_hinge=x_bottom - tk["H"], x_bob=x_bottom - tk["hb"], x_fixed=x_bottom - tk["hf"])
        tanks.append(tk)
        rigid.append((tk["mf"], tk["x_fixed"], 0.0, 0.0))
        if slosh:
            pend.append(tk)
        else:
            rigid.append((tk["ms"], tk["x_bob"], 0.0, 0.0))
    if tld:
        m = tld["m_t"] * 1e3
        tk = slosh_tank(m, m / (1000.0 * math.pi * tld["a"] ** 2), tld["a"])
        x_bottom = tld["x"]
        tk.update(name="eau", zeta=tld["zeta"], a=tld["a"], x_hinge=x_bottom - tk["H"], x_bob=x_bottom - tk["hb"], x_fixed=x_bottom - tk["hf"])
        tanks.append(tk)
        rigid.append((tk["mf"], tk["x_fixed"], 0.0, 0.0))
        pend.append(tk)
    M_r = sum(p[0] for p in rigid)
    x_c = sum(p[0] * p[1] for p in rigid) / M_r
    I_ax = sum(p[2] for p in rigid)
    I_tr = sum(p[3] + p[0] * (p[1] - x_c) ** 2 for p in rigid)
    x_tot = (M_r * x_c + sum(t["ms"] * t["x_bob"] for t in pend)) / (M_r + sum(t["ms"] for t in pend))
    return dict(M_rigid=M_r, x_c=x_c, I_ax=I_ax, I_tr=I_tr, x_tot=x_tot, tanks=tanks, pendulums=pend)


def build_topology(name, spread):
    """Angles des modules, points d'attache (décalages selon e_t, e_z),
    câbles ((corps, attache), (corps, attache)), part de M·a reprise par un
    câble, et dR/dL (variation du rayon par mètre de câble)."""
    if name == "dumbbell":
        return dict(angles=[0.0, math.pi], attach=[(0.0, 0.0)],
                    cables=[((0, 0), (1, 0))], tfac=1.0, dRdL=0.5)
    if name == "ladder":  # haltère à deux câbles parallèles, écartés selon l'axe de rotation
        s = 15.0 if spread is None else spread
        return dict(angles=[0.0, math.pi], attach=[(0.0, s), (0.0, -s)],
                    cables=[((0, 0), (1, 0)), ((0, 1), (1, 1))], tfac=0.5, dRdL=0.5)
    angles = [math.pi / 2 + 2 * math.pi * i / 3 for i in range(3)]
    if name == "triangle":
        return dict(angles=angles, attach=[(0.0, 0.0)],
                    cables=[((i, 0), ((i + 1) % 3, 0)) for i in range(3)],
                    tfac=1 / math.sqrt(3), dRdL=1 / math.sqrt(3))
    if name == "triangle2":  # deux points d'attache par module, écartés selon e_t (palonnier)
        s = 20.0 if spread is None else spread
        return dict(angles=angles, attach=[(s, 0.0), (-s, 0.0)],
                    cables=[((i, 0), ((i + 1) % 3, 1)) for i in range(3)],
                    tfac=1 / math.sqrt(3), dRdL=1 / math.sqrt(3))
    raise ValueError(name)


# --- programmes de mouvement des masses internes ---------------------------
def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return 0.5 * (1 - math.cos(math.pi * u))


def make_program(kind, amp, t0=60.0, speed=1.2, period=None, f0=0.004, f1=0.25, t1=None, a_max=1.0, stop=None):
    """Renvoie s(t) : déplacement (m) de la masse interne le long de son axe.
    - cargo : centre → +amp → −amp → centre, déplacements de 120 s, paliers ;
    - walk : allers-retours entre −amp et +amp à la vitesse de marche, accélération limitée (équipage) ;
    - periodic : sinusoïde de période donnée (recherche de résonance) ;
    - sweep : sinusoïde à fréquence croissante f0 → f1 entre t0 et t1,
      amplitude limitée pour que l'accélération reste ≤ a_max."""
    if kind == "cargo":
        steps = [(t0, 0.0, amp), (600.0, amp, -amp), (1200.0, -amp, 0.0)]

        def s(t):
            x = 0.0
            for ts, a, b in steps:
                if t >= ts:
                    x = a + (b - a) * smooth((t - ts) / 120.0)
            return x
        return s
    if kind == "walk":
        # Allers-retours entre −amp et +amp à la vitesse de marche, avec une
        # accélération limitée à a_walk au démarrage et à l'arrêt (un
        # demi-tour instantané imposerait une secousse irréaliste au module)
        a_walk = 0.5

        def profile(D):
            """Traversée de longueur D, départ et arrivée à l'arrêt :
            renvoie (durée, position(u))."""
            ta = min(speed / a_walk, math.sqrt(D / a_walk))
            vmax = a_walk * ta
            T = 2 * ta + (D - a_walk * ta * ta) / vmax

            def x(u):
                if u < ta:
                    return 0.5 * a_walk * u * u
                if u < T - ta:
                    return 0.5 * a_walk * ta * ta + vmax * (u - ta)
                return D - 0.5 * a_walk * (T - u) ** 2
            return T, x

        T1, first = profile(amp)  # centre → +amp
        TL, leg = profile(2 * amp)  # traversées complètes

        def s(t):
            if t < t0:
                return 0.0
            u = t - t0
            if u < T1:
                return first(u)
            k, r = divmod(u - T1, TL)
            return amp - leg(r) if int(k) % 2 == 0 else -amp + leg(r)
        return s
    if kind == "periodic":
        # Sinusoïde démarrée et (si stop) arrêtée en douceur sur une période
        w = 2 * math.pi / period
        A = min(amp, a_max / w ** 2)
        return lambda t: 0.0 if t < t0 or (stop and t > stop) else (
            A * math.sin(w * (t - t0)) * smooth((t - t0) / period) * (smooth((stop - t) / period) if stop else 1.0))
    if kind == "sweep":
        def s(t):
            if t < t0 or t > t1:
                return 0.0
            tau = t - t0
            T = t1 - t0
            f = f0 + (f1 - f0) * tau / T
            phase = 2 * math.pi * (f0 * tau + 0.5 * (f1 - f0) * tau ** 2 / T)
            A = min(amp, a_max / (2 * math.pi * f) ** 2)
            # Rampes d'entrée et de sortie de 60 s (pas d'à-coup à l'arrêt)
            return A * math.sin(phase) * smooth(tau / 60.0) * smooth((t1 - t) / 60.0)
        return s
    raise ValueError(kind)


class Station:
    def __init__(self, args):
        mat = MATERIALS[args.material]
        if getattr(args, "accel", None):
            args.g = args.accel / G0  # tout le reste du code raisonne en g
        self.args = args
        M = args.mass_t * 1e3
        M_design = (getattr(args, "design_mass_t", None) or args.mass_t) * 1e3
        a, ell = args.module_radius, args.module_length
        m_int = args.motion_mass_t * 1e3 if args.motion != "none" else 0.0
        self.motion_modules = [int(b) for b in args.motion_modules.split(",")] if args.motion != "none" else []
        # La structure porte la masse totale moins la masse mobile ; inertie
        # de la structure = cylindre plein de masse M − m.
        Ms = M - m_int
        It = Ms * (3 * a * a + ell * ell) / 12
        self.Ib = np.array([Ms * a * a / 2, It, It])  # axe long, puis transverses
        self.M = M
        self.omega = args.rpm * 2 * math.pi / 60
        self.R_target = args.g * G0 / self.omega ** 2
        self.h = (ell / 2 if args.module == "radial" else a) + args.bridle
        # Starship à ergols : partie rigide (origine du corps = son centre de
        # masse) + pendules de ballottement ; l'attache reste à h du centre de
        # masse total, comme dans le modèle homogène
        h_att, M_rigid, self.ship = self.h, M, None
        slosh = getattr(args, "slosh", "off")
        if slosh != "off":
            if args.module != "radial":
                raise ValueError("le modèle de ballottement suppose des vaisseaux debout (--module radial)")
            tld = None
            if getattr(args, "tld_mass_t", 0) > 0:
                tld = dict(m_t=args.tld_mass_t, x=args.tld_x, a=args.tld_radius, zeta=args.tld_zeta)
            self.ship = starship_mass_model(args.mass_t, slosh=slosh == "free", tld=tld)
            M_rigid = self.ship["M_rigid"]
            h_att = self.h + self.ship["x_c"] - self.ship["x_tot"]
            self.Ib = np.array([self.ship["I_ax"], self.ship["I_tr"], self.ship["I_tr"]])
        topo = build_topology(args.topology, args.spread)
        # Moyeu central : un point d'attache de plus au milieu du nez de chaque
        # module, et un rayon vers le moyeu (câbles d'indice 3 à 5)
        self.hub_m = getattr(args, "hub_mass_t", 0.0) * 1e3
        if self.hub_m > 0:
            if not args.topology.startswith("triangle"):
                raise ValueError("le moyeu suppose une topologie en triangle")
            n_sides = len(topo["cables"])
            if getattr(args, "hub_spokes", 1) == 2:
                # rayons doublés : un depuis chacun des deux points d'attache du nez
                topo["cables"] = topo["cables"] + [((b, k), ("hub", 0)) for b in range(len(topo["angles"])) for k in range(len(topo["attach"]))]
            else:
                k_hub = len(topo["attach"])
                topo["attach"] = topo["attach"] + [(0.0, 0.0)]
                topo["cables"] = topo["cables"] + [((b, k_hub), ("hub", 0)) for b in range(len(topo["angles"]))]
            topo["spokes"] = list(range(n_sides, len(topo["cables"])))
        self.topo = topo
        self.T_design = M_design * args.design_g * G0 * topo["tfac"]
        self.area = self.T_design * args.safety / mat["sigma"]
        self.EA = mat["E"] * self.area
        self.lam = mat["rho"] * self.area

        # Modules
        nb, na = len(topo["angles"]), len(topo["attach"])
        self.nb = nb
        xb, R0, att_body, att_r, up = [], [], [], [], []
        for b, th in enumerate(topo["angles"]):
            er = np.array([math.cos(th), math.sin(th), 0.0])
            ez = np.array([0.0, 0.0, 1.0])
            et = np.cross(ez, er)
            R = np.column_stack(ORIENTATIONS[args.module](er, et, ez))
            # centre de masse total du module (ergols compris) au rayon visé
            xb.append((self.R_target - ((self.ship["x_tot"] - self.ship["x_c"]) if self.ship else 0.0)) * er)
            R0.append(R)
            up.append(R.T @ -er)  # « haut » du module (vers le centre), repère du corps
            for st, sz in topo["attach"]:
                att_body.append(b)
                att_r.append(R.T @ (-h_att * er + st * et + sz * ez))
        self.xb = np.array(xb)
        self.R = np.array(R0)
        self.R_init = self.R.copy()
        self.up_body = np.array(up)
        self.att_body = np.array(att_body)
        self.att_r = np.array(att_r)
        self.Mb = np.array([M_rigid - (m_int if b in self.motion_modules else 0.0) for b in range(nb)])

        # Ballottement : un pendule sphérique par réservoir et par module. Tige
        # = ressort raide (3 Hz) ; amortisseur latéral 2ζω·m par rapport à la
        # paroi (ζ ~ 1e-4 parois lisses, ~1e-3 avec raidisseurs, 2 à 5 % avec
        # chicanes) ; tige amortie seulement si ζ > 0 (sinon système conservatif).
        zeta = getattr(args, "slosh_zeta", 0.0)
        sb, sm, sL, sh, se, sz = [], [], [], [], [], []
        for b in range(nb if self.ship else 0):
            for tk in self.ship["pendulums"]:
                sb.append(b)
                sm.append(tk["ms"])
                sL.append(tk["L"])
                sh.append([tk["x_hinge"] - self.ship["x_c"], 0.0, 0.0])
                se.append([tk["x_bob"] - self.ship["x_c"], 0.0, 0.0])
                sz.append(tk.get("zeta", zeta))
        self.sb = np.array(sb, dtype=int)
        self.sm = np.array(sm)
        self.sL = np.array(sL)
        self.sh = np.array(sh).reshape(-1, 3)
        self.s_eq = np.array(se).reshape(-1, 3)
        r_bob = self.R_target + (self.s_eq[:, 0] - ((self.ship["x_tot"] - self.ship["x_c"]) if self.ship else 0.0))
        self.s_w = np.sqrt(self.omega ** 2 * r_bob / self.sL) if len(sm) else np.zeros(0)
        self.s_zeta = np.array(sz)
        self.s_c = 2 * self.s_zeta * self.sm * self.s_w
        w_rod = 2 * math.pi * 3.0
        self.s_k = self.sm * w_rod ** 2
        self.s_cr = 2 * 0.7 * self.sm * w_rod * (self.s_zeta > 0)
        self.xs = np.zeros((len(sm), 3))
        self.vs = np.zeros((len(sm), 3))

        # Masses internes mobiles : axe de déplacement dans le repère du corps
        self.mi = np.array([m_int] * len(self.motion_modules))
        self.bi = np.array(self.motion_modules, dtype=int)
        axes = []
        for b in self.motion_modules:
            if args.motion_axis == "long":
                axes.append(np.array([1.0, 0.0, 0.0]))
            else:
                th = topo["angles"][b]
                er = np.array([math.cos(th), math.sin(th), 0.0])
                ez = np.array([0.0, 0.0, 1.0])
                v = {"r": er, "t": np.cross(ez, er), "z": ez}[args.motion_axis]
                axes.append(self.R[b].T @ v)
        self.ai = np.array(axes).reshape(-1, 3)
        self.program = make_program(args.motion, args.motion_amp, speed=args.motion_speed, period=args.motion_period,
                                    f1=getattr(args, "sweep_f1", 0.25), t1=args.duration - 60,
                                    stop=getattr(args, "motion_stop", None)) if args.motion != "none" else None
        self.ki = self.mi * (2 * math.pi * 2.0) ** 2  # asservissement à 2 Hz
        self.ci = 2 * 0.7 * self.mi * (2 * math.pi * 2.0)
        self.xi = np.zeros((len(self.mi), 3))
        self.vi = np.zeros((len(self.mi), 3))

        # Amortisseur interne (sphère de Kane) : inertie J, constante de temps τ
        self.J = args.damper_frac * It
        self.cd = self.J / args.damper_tau if self.J > 0 else 0.0
        self.hs = np.zeros((nb, 3))

        # Câbles : nœuds libres (moyeu compris), puis points d'attache (sans
        # masse, portés par les corps)
        n = args.segments
        assert n >= 2
        P0, _ = self._attach_points(self.xb, self.R)
        xn, mn, segs, ds0 = [], [], [], []
        self.hub_nodes = []
        if self.hub_m > 0:
            xn.append(np.zeros(3))
            mn.append(self.hub_m)
            self.hub_nodes.append(0)
        self.cable_first_seg, self.cable_mid_node = [], []
        for ends in topo["cables"]:
            # extrémité : (indice dans la chaîne, position) ; attache < 0, nœud libre ≥ 0
            ch_end = [(self.hub_nodes[k], xn[self.hub_nodes[k]]) if b == "hub" else (-(b * na + k + 1), P0[b * na + k])
                      for b, k in ends]
            (cA, pA), (cB, pB) = ch_end
            ds = np.linalg.norm(pB - pA) / n
            chain = [cA]
            for s in range(1, n):
                xn.append(pA + (pB - pA) * s / n)
                mn.append(self.lam * ds)
                chain.append(len(xn) - 1)
            chain.append(cB)
            self.cable_first_seg.append(len(segs))
            self.cable_mid_node.append(chain[n // 2])
            segs += list(zip(chain[:-1], chain[1:]))
            ds0 += [ds] * n
            # demi-segments d'extrémité : masse reportée sur le corps ou le moyeu
            for (b, k), (c, _) in zip(ends, ch_end):
                if b == "hub":
                    mn[c] += self.lam * ds / 2
                else:
                    self.Mb[b] += self.lam * ds / 2
        nf = len(xn)
        self.nf = nf
        self.seg = np.array([[p if p >= 0 else nf - p - 1 for p in s] for s in segs])
        self.xn = np.array(xn)
        self.mn = np.array(mn)
        self.vn = np.zeros_like(self.xn)
        self.vb = np.zeros_like(self.xb)
        self.pi = np.zeros_like(self.xb)  # moment cinétique propre, repère du corps
        self.n = n
        self.n_cables = len(topo["cables"])
        self.ds0 = np.array(ds0)
        self._update_stiffness()
        # Segments qui portent (rupture : un segment cesse de porter)
        self.alive = np.ones(len(segs), dtype=bool)
        # Rayons du moyeu : allongement de prétension visé (fraction de la
        # tension nominale d'un côté du triangle)
        spokes = topo.get("spokes", [])
        self.spoke_seg = np.array([self.cable_first_seg[c] + s for c in spokes for s in range(n)], dtype=int)
        self.side_seg = np.setdiff1d(np.arange(len(segs)), self.spoke_seg)
        # (rayons doublés : chacun porte la moitié de la prétension)
        self.spoke_eps = (getattr(args, "spoke_tension", 0.0) * M * args.g * G0 * topo["tfac"] / self.EA
                          / (2 if getattr(args, "hub_spokes", 1) == 2 else 1))

        # Segments nœud-nœud en groupes sans nœud partagé (amortissement exact
        # par paires) : coloriage glouton des arêtes (deux groupes pour une
        # chaîne, un de plus autour du moyeu)
        i, j = self.seg[:, 0], self.seg[:, 1]
        att_i, att_j = i >= nf, j >= nf
        nn = ~(att_i | att_j)
        groups, used = [], []
        for s in np.where(nn)[0]:
            for g, u in zip(groups, used):
                if i[s] not in u and j[s] not in u:
                    g.append(s)
                    u.update((i[s], j[s]))
                    break
            else:
                groups.append([s])
                used.append({i[s], j[s]})
        self.nn_groups = [np.array(g, dtype=int) for g in groups]
        # Segments d'attache : (point d'attache, nœud)
        self.as_idx = np.where(~nn)[0]
        self.as_att = np.where(att_i[self.as_idx], i[self.as_idx], j[self.as_idx]) - nf
        self.as_node = np.where(att_i[self.as_idx], j[self.as_idx], i[self.as_idx])

        # Pas de temps : stabilité de Verlet dt < 2/ω_max, ω_max ≈ 2·sqrt(k/m_min)
        self.dt = args.cfl * 2 / (2 * math.sqrt(self.k.max() / self.mn.min()))

    def _update_stiffness(self):
        self.k = self.EA / self.ds0
        # Amortissement : ζ visé sur le mode bungee d'un haltère ; ressorts en série → c_seg = N·c_eff
        k_cable = self.EA / (self.ds0 * self.n)
        self.c = 2 * self.args.zeta * np.sqrt(k_cable * self.M / 2) * self.n

    @property
    def m_total(self):
        return self.mn.sum() + self.Mb.sum() + self.mi.sum() + self.sm.sum()

    # --- cinématique ----------------------------------------------------
    def _attach_points(self, xb, R):
        rw = np.einsum("aij,aj->ai", R[self.att_body], self.att_r)
        return xb[self.att_body] + rw, rw

    def points(self):
        pa, rw = self._attach_points(self.xb, self.R)
        return np.concatenate([self.xn, pa]), rw

    def omega_world(self):
        return np.einsum("bij,bj->bi", self.R, self.pi / self.Ib)

    def point_velocities(self, rw):
        om = self.omega_world()
        va = self.vb[self.att_body] + np.cross(om[self.att_body], rw)
        return np.concatenate([self.vn, va])

    # --- forces ---------------------------------------------------------
    def spring_forces(self, P):
        i, j = self.seg[:, 0], self.seg[:, 1]
        d = P[j] - P[i]
        l = np.linalg.norm(d, axis=1)
        e = d / l[:, None]
        stretch = l - self.ds0
        taut = (stretch > 0) & self.alive
        t = np.where(taut, self.k * stretch, 0.0)
        f = t[:, None] * e
        F = np.zeros_like(P)
        np.add.at(F, i, f)
        np.add.at(F, j, -f)
        return F, t, stretch, taut, e

    def wrench(self, F_att, rw):
        Fb = np.zeros((self.nb, 3))
        Tb = np.zeros((self.nb, 3))
        np.add.at(Fb, self.att_body, F_att)
        np.add.at(Tb, self.att_body, np.cross(rw, F_att))
        return Fb, Tb

    def internal_forces(self, t):
        """Asservissement des masses internes : force sur chaque masse, et
        torseur de réaction sur les modules (force, couple)."""
        Fb = np.zeros((self.nb, 3))
        Tb = np.zeros((self.nb, 3))
        if len(self.mi) == 0:
            return np.zeros((0, 3)), Fb, Tb
        eps = 0.01
        s = self.program(t)
        sd = (self.program(t + eps) - self.program(t - eps)) / (2 * eps)
        b = self.bi
        ra = np.einsum("bij,bj->bi", self.R[b], self.ai * s)
        xa = self.xb[b] + ra
        va = self.vb[b] + np.cross(self.omega_world()[b], ra) + np.einsum("bij,bj->bi", self.R[b], self.ai * sd)
        F = self.ki[:, None] * (xa - self.xi) + self.ci[:, None] * (va - self.vi)
        np.add.at(Fb, b, -F)
        np.add.at(Tb, b, np.cross(ra, -F))
        return F, Fb, Tb

    def slosh_forces(self):
        """Pendules de ballottement : tige (ressort raide, amorti si ζ > 0)
        entre l'articulation et la masse, amortisseur latéral par rapport au
        point de la paroi qui coïncide avec la masse. Renvoie la force sur
        chaque masse et le torseur de réaction sur les modules."""
        Fb = np.zeros((self.nb, 3))
        Tb = np.zeros((self.nb, 3))
        if len(self.sm) == 0:
            return np.zeros((0, 3)), Fb, Tb
        b = self.sb
        om = self.omega_world()[b]
        rh = np.einsum("bij,bj->bi", self.R[b], self.sh)
        d = self.xs - (self.xb[b] + rh)
        l = np.linalg.norm(d, axis=1)
        e = d / l[:, None]
        vh = self.vb[b] + np.cross(om, rh)
        F_rod = -(self.s_k * (l - self.sL) + self.s_cr * np.einsum("ij,ij->i", self.vs - vh, e))[:, None] * e
        rp = self.xs - self.xb[b]
        vrel = self.vs - (self.vb[b] + np.cross(om, rp))
        F_lat = -self.s_c[:, None] * (vrel - np.einsum("ij,ij->i", vrel, e)[:, None] * e)
        np.add.at(Fb, b, -(F_rod + F_lat))
        np.add.at(Tb, b, np.cross(rh, -F_rod) + np.cross(rp, -F_lat))
        return F_rod + F_lat, Fb, Tb

    def slosh_offsets(self):
        """Écart latéral (m) de chaque masse ballottante par rapport à l'axe
        de son réservoir."""
        if len(self.sm) == 0:
            return np.zeros(0)
        b = self.sb
        d = self.xs - (self.xb[b] + np.einsum("bij,bj->bi", self.R[b], self.sh))
        ax = self.R[b][:, :, 0]
        return np.linalg.norm(d - np.einsum("ij,ij->i", d, ax)[:, None] * ax, axis=1)

    def damper_torque(self):
        """Couple visqueux entre la sphère interne et le module (sur la sphère)."""
        if self.cd == 0:
            return np.zeros((self.nb, 3))
        return self.cd * (self.omega_world() - self.hs / self.J)

    # --- intégration ----------------------------------------------------
    def kick(self, h, F, rw, Fi, Fbi, Tbi, Td, Fs=None):
        self.vn += h * F[: self.nf] / self.mn[:, None]
        Fb, Tb = self.wrench(F[self.nf:], rw)
        self.vb += h * (Fb + Fbi) / self.Mb[:, None]
        Lw = np.einsum("bij,bj->bi", self.R, self.pi) + h * (Tb + Tbi - Td)
        self.pi = np.einsum("bji,bj->bi", self.R, Lw)
        if len(self.mi):
            self.vi += h * Fi / self.mi[:, None]
        if len(self.sm):
            self.vs += h * Fs / self.sm[:, None]
        if self.cd:
            self.hs += h * Td

    def _rotate(self, k, h):
        """Flot exact de H_k = π_k²/(2 I_k) : rotation autour de l'axe k du corps."""
        th = h * self.pi[:, k] / self.Ib[k]
        c, s = np.cos(th), np.sin(th)
        p, q = (k + 1) % 3, (k + 2) % 3
        Rk = np.zeros((self.nb, 3, 3))
        Rk[:, k, k] = 1.0
        Rk[:, p, p] = c
        Rk[:, q, q] = c
        Rk[:, q, p] = s
        Rk[:, p, q] = -s
        self.R = self.R @ Rk
        self.pi = np.einsum("bji,bj->bi", Rk, self.pi)

    def drift(self, dt):
        self.xn += dt * self.vn
        self.xb += dt * self.vb
        self.xi += dt * self.vi
        self.xs += dt * self.vs
        for k, h in ((0, dt / 2), (1, dt / 2), (2, dt), (1, dt / 2), (0, dt / 2)):
            self._rotate(k, h)

    def kinetic(self):
        ke = 0.5 * (self.mn @ np.sum(self.vn ** 2, axis=1) + self.Mb @ np.sum(self.vb ** 2, axis=1)
                    + np.sum(self.pi ** 2 / self.Ib))
        if len(self.mi):
            ke += 0.5 * self.mi @ np.sum(self.vi ** 2, axis=1)
        if len(self.sm):
            ke += 0.5 * self.sm @ np.sum(self.vs ** 2, axis=1)
        if self.cd:
            ke += 0.5 * np.sum(self.hs ** 2) / self.J
        return ke

    def damp(self, dt):
        """Amortissement exact par segment tendu : la vitesse relative le long
        du segment décroît en exp(-c·dt/μ) (μ = masse réduite, masse effective
        du corps au point d'attache). En explicite, c/m ~ 2e3 s⁻¹ imposerait un
        pas minuscule ; ici c'est inconditionnellement stable. Renvoie
        l'énergie dissipée."""
        ke0 = self.kinetic()
        for grp in self.nn_groups:
            i, j = self.seg[grp, 0], self.seg[grp, 1]
            d = self.xn[j] - self.xn[i]
            l = np.linalg.norm(d, axis=1)
            e = d / l[:, None]
            mu = self.mn[i] * self.mn[j] / (self.mn[i] + self.mn[j])
            vrel = np.einsum("ij,ij->i", self.vn[j] - self.vn[i], e)
            J = np.where((l > self.ds0[grp]) & self.alive[grp], mu * vrel * (1 - np.exp(-self.c[grp] * dt / mu)), 0.0)
            imp = J[:, None] * e
            np.add.at(self.vn, i, imp / self.mn[i][:, None])
            np.add.at(self.vn, j, -imp / self.mn[j][:, None])
        # Segments d'attache : nœud ↔ corps rigide
        a, nd = self.as_att, self.as_node
        b = self.att_body[a]
        rw = np.einsum("aij,aj->ai", self.R[b], self.att_r[a])
        d = self.xn[nd] - (self.xb[b] + rw)
        l = np.linalg.norm(d, axis=1)
        e = d / l[:, None]
        u = np.einsum("aji,aj->ai", self.R[b], np.cross(rw, e))
        m_eff = 1 / (1 / self.Mb[b] + np.sum(u ** 2 / self.Ib, axis=1))
        va = self.vb[b] + np.cross(self.omega_world()[b], rw)
        vrel = np.einsum("ij,ij->i", self.vn[nd] - va, e)
        mu = 1 / (1 / self.mn[nd] + 1 / m_eff)
        cs = self.c[self.as_idx]
        J = np.where((l > self.ds0[self.as_idx]) & self.alive[self.as_idx], mu * vrel * (1 - np.exp(-cs * dt / mu)), 0.0)
        imp = J[:, None] * e
        np.add.at(self.vn, nd, -imp / self.mn[nd][:, None])
        Fb = np.zeros((self.nb, 3))
        Tb = np.zeros((self.nb, 3))
        np.add.at(Fb, b, imp)
        np.add.at(Tb, b, np.cross(rw, imp))
        self.vb += Fb / self.Mb[:, None]
        Lw = np.einsum("bij,bj->bi", self.R, self.pi) + Tb
        self.pi = np.einsum("bji,bj->bi", self.R, Lw)
        return ke0 - self.kinetic()

    # --- équilibre en rotation ------------------------------------------
    def relax(self, verbose=True):
        """Relaxation dynamique dans le repère tournant à ω fixé (masses
        fictives uniformes, fort amortissement, orientation des modules
        figée — équilibre symétrique), puis ajustement de la longueur à vide
        des câbles pour placer le centre de masse des modules à R_target.
        Les masses internes sont au centre du module (s = 0) et comptées
        avec lui ; les masses ballottantes sont à leur position d'équilibre.
        R est mesuré au centre de masse total de chaque module."""
        w2 = self.omega ** 2
        mf = self.mn.min()
        dt = 1.6 / (2 * math.sqrt(self.k.max() / mf))
        Mb_tot = self.Mb.copy()
        np.add.at(Mb_tot, self.bi, self.mi)
        Mtot = self.mn.sum() + Mb_tot.sum() + self.sm.sum()
        xy = np.array([1.0, 1.0, 0.0])
        rs = np.einsum("bij,bj->bi", self.R[self.sb], self.s_eq)
        Mmod = Mb_tot.copy()
        np.add.at(Mmod, self.sb, self.sm)

        def module_com():
            c = Mb_tot[:, None] * self.xb
            np.add.at(c, self.sb, self.sm[:, None] * (self.xb[self.sb] + rs))
            return c / Mmod[:, None]
        for it in range(40):
            vn = np.zeros_like(self.xn)
            vb = np.zeros_like(self.xb)
            for step in range(100000):
                P, rw = self.points()
                F, *_ = self.spring_forces(P)
                Fn = F[: self.nf] + self.mn[:, None] * w2 * self.xn * xy
                Fb, _ = self.wrench(F[self.nf:], rw)
                Fb += Mmod[:, None] * w2 * module_com() * xy
                vn = 0.995 * (vn + Fn / mf * dt)
                vb = 0.995 * (vb + Fb / mf * dt)
                self.xn += vn * dt
                self.xb += vb * dt
                # La translation d'ensemble est instable dans le repère tournant
                # (centrifuge sur le centre de masse décalé, aucun câble ne s'y
                # oppose) : on recentre le centre de masse à chaque pas.
                com = (self.mn @ self.xn + Mmod @ module_com()) / Mtot
                self.xn -= com
                self.xb -= com
                if step % 1000 == 999 and max(np.abs(vn).max(), np.abs(vb).max()) < 1e-8:
                    break
            R = np.linalg.norm(module_com()[:, :2], axis=1).mean()
            # Rayons : longueur à vide recalée sur la géométrie pour garder
            # l'allongement de prétension visé ; seuls les côtés fixent R
            spoke_ok = True
            if len(self.spoke_seg):
                P, _ = self.points()
                i, j = self.seg[self.spoke_seg, 0], self.seg[self.spoke_seg, 1]
                l = np.linalg.norm(P[j] - P[i], axis=1)
                eps = l.sum() / self.ds0[self.spoke_seg].sum() - 1
                spoke_ok = abs(eps - self.spoke_eps) < max(0.01 * self.spoke_eps, 1e-7)
            if verbose:
                print(f"  itération {it}: R = {R:.5f} m (visé {self.R_target:.5f})"
                      + (f", allongement des rayons {eps:.2e} (visé {self.spoke_eps:.2e})" if len(self.spoke_seg) else ""))
            if abs(R - self.R_target) < 1e-4 and spoke_ok:
                break
            self.ds0[self.side_seg] += (self.R_target - R) / self.topo["dRdL"] / self.n
            if len(self.spoke_seg):
                self.ds0[self.spoke_seg] = l / (1 + self.spoke_eps)
            self._update_stiffness()
        self.R_eq = R

    def set_rigid_rotation(self):
        w = np.array([0.0, 0.0, self.omega])
        self.vn = np.cross(w, self.xn)
        self.vb = np.cross(w, self.xb)
        self.pi = self.Ib * np.einsum("bji,j->bi", self.R, w)
        if len(self.mi):
            # Masse interne à l'équilibre : le ressort fournit la force centripète
            r = self.xb[self.bi] * np.array([1.0, 1.0, 0.0])
            self.xi = self.xb[self.bi] + r * (self.omega ** 2 * self.mi / (self.ki - self.omega ** 2 * self.mi))[:, None]
            self.vi = np.cross(w, self.xi)
        if len(self.sm):
            # Masses ballottantes à l'équilibre : la tige, légèrement tendue,
            # fournit la force centripète
            b = self.sb
            rh = np.einsum("bij,bj->bi", self.R[b], self.sh)
            u = np.einsum("bij,bj->bi", self.R[b], self.s_eq - self.sh)
            u /= np.linalg.norm(u, axis=1)[:, None]
            x0 = self.xb[b] + rh + self.sL[:, None] * u
            stretch = self.sm * self.omega ** 2 * np.linalg.norm(x0[:, :2], axis=1) / (self.s_k - self.sm * self.omega ** 2)
            self.xs = x0 + stretch[:, None] * u
            self.vs = np.cross(w, self.xs)
        if self.cd:
            self.hs[:] = self.J * w

    # --- diagnostics ----------------------------------------------------
    def energy(self):
        P, _ = self.points()
        _, _, stretch, taut, _ = self.spring_forces(P)
        E = self.kinetic() + 0.5 * np.sum(np.where(taut, self.k * stretch ** 2, 0.0))
        if len(self.sm):
            rh = np.einsum("bij,bj->bi", self.R[self.sb], self.sh)
            l = np.linalg.norm(self.xs - self.xb[self.sb] - rh, axis=1)
            E += 0.5 * np.sum(self.s_k * (l - self.sL) ** 2)
        return E

    def angular_momentum(self):
        L = (self.mn @ np.cross(self.xn, self.vn) + self.Mb @ np.cross(self.xb, self.vb)
             + np.einsum("bij,bj->i", self.R, self.pi))
        if len(self.mi):
            L += self.mi @ np.cross(self.xi, self.vi)
        if len(self.sm):
            L += self.sm @ np.cross(self.xs, self.vs)
        if self.cd:
            L += self.hs.sum(axis=0)
        return L

    def hull_axes(self):
        """Axe de chaque coque (pointe, arrière), en repère inertiel."""
        L = self.args.module_length
        x_c = self.ship["x_c"] if self.ship else L / 2
        ax = self.R[:, :, 0]
        return self.xb - x_c * ax, self.xb + (L - x_c) * ax

    def spin_rate(self, com):
        """Vitesse de rotation d'ensemble ω = L_z / I_z (rad/s), I_z compté
        comme si tout tournait d'un bloc autour du centre de masse."""
        ez = np.array([0.0, 0.0, 1.0])
        rp = lambda x: np.sum(((x - com) * np.array([1.0, 1.0, 0.0])) ** 2, axis=1)
        Iz = self.mn @ rp(self.xn) + self.Mb @ rp(self.xb) + self.sm @ rp(self.xs) + self.mi @ rp(self.xi)
        Iz += np.einsum("bi,i,bi->", self.R[:, 2, :], self.Ib, self.R[:, 2, :])
        return float(self.angular_momentum() @ ez / Iz)

    def local_inertia(self, b=0):
        """Inerties du module dans le repère local (e_r, e_t, e_z) à l'état initial."""
        th = self.topo["angles"][b]
        er = np.array([math.cos(th), math.sin(th), 0.0])
        ez = np.array([0.0, 0.0, 1.0])
        et = np.cross(ez, er)
        Iw = self.R_init[b] @ np.diag(self.Ib) @ self.R_init[b].T
        return [float(v @ Iw @ v) for v in (er, et, ez)]


def roll_prediction(topology, spread, I_r, I_t, I_z, omega, T, L):
    """Roulis d'un module autour de la verticale (tangage verrouillé) :
    I_r φ'' = (ω² (I_t − I_z) − k_att) φ, où k_att est la raideur apportée par
    des attaches écartées de ±s :
    - triangle2 (câbles vers les deux voisins, à ±30° de la verticale) : la
      composante tangentielle T/2 de chaque câble agit au bras de levier s·φ
      → T·s, plus la raideur latérale des câbles 2·T·s²/L (second ordre) ;
    - ladder (câbles parallèles) : 2·T·s²/L ne retient que le roulis
      différentiel des deux modules ; le roulis commun (toute la station
      autour de la ligne) reste libre → k_att = 0."""
    k_att = 0.0
    if topology == "triangle2":
        s = 20.0 if spread is None else spread
        k_att = T * s + 2 * T * s * s / L
    s2 = (omega ** 2 * (I_t - I_z) - k_att) / I_r
    if abs(I_t - I_z) < 1e-9 * I_r and k_att == 0:
        return "neutre (I_t = I_z) : aucun couple de rappel"
    if s2 > 0:
        return f"INSTABLE, temps de doublement ≈ {math.log(2) / math.sqrt(s2):.1f} s"
    return f"stable, période ≈ {2 * math.pi / math.sqrt(-s2):.1f} s"


def doubling_time(t1, t10, t45, duration):
    """Temps de doublement du roulis, déduit du passage de 1° à 10°, si la
    croissance est bien exponentielle : de 10° à 45°, il faut alors moins de
    temps que de 1° à 10° (ln 4,5 / ln 10 ≈ 0,65 fois), contre ≈ 3,9 fois
    pour une dérive linéaire (roulis neutre). Sans passage à 45°, la
    croissance n'est retenue que si la simulation s'est arrêtée trop tôt
    pour trancher."""
    if t1 is None or t10 is None or t10 <= t1:
        return None
    d = t10 - t1
    if (t45 - t10 if t45 is not None else duration - t10) > 2 * d:
        return None
    return math.log(2) * d / math.log(10)


def doubling_from_info(info):
    r = info["results"]
    return doubling_time(r["t_roll_1"], r["t_roll_10"], r.get("t_roll_45"), info["args"]["duration"])


def roll_prediction_from_info(info):
    """Même prédiction, recalculée à partir du .json d'un scénario."""
    a = info["args"]
    M = a["mass_t"] * 1e3
    I_r, I_t, I_z = (x * M for x in info["I_local_over_M"])
    return roll_prediction(a["topology"], a.get("spread"), I_r, I_t, I_z, a["rpm"] * 2 * math.pi / 60, info["T_eq"], info["L_eq"])


def static_tilt_prediction(args, h):
    """Inclinaison statique du plancher (°) quand la masse interne est à
    l'amplitude max : le module tourne jusqu'à ce que le couple de rappel des
    câbles équilibre le décalage δ du centre de masse.
    - attache unique (ou déplacement hors du plan) : tan θ = δ/h ;
    - palonnier du triangle (attaches à ±s le long de e_t, câbles à 30° de la
      verticale) avec déplacement tangentiel : raideur k = T(s + √3·h),
      T = M·a/√3, d'où θ = √3·δ/(s + √3·h) ;
    - déplacement radial (entre les ponts d'un module vertical) : aucune
      inclinaison, le centre de masse reste sous l'attache."""
    if args.motion == "none":
        return None
    if args.motion_axis == "r" or (args.motion_axis == "long" and args.module == "radial"):
        return 0.0
    delta = args.motion_mass_t * args.motion_amp / args.mass_t
    tangential_move = (args.motion_axis == "t") or (args.motion_axis == "long" and args.module == "tangential")
    if args.topology == "triangle2" and tangential_move:
        s = 20.0 if args.spread is None else args.spread
        return math.degrees(math.sqrt(3) * delta / (s + math.sqrt(3) * h))
    return math.degrees(math.atan(delta / h))


def apply_perturbation(st, args):
    """Perturbations sur le module 0 (vitesses, roulis, câble), puis
    quantité de mouvement totale ramenée à zéro."""
    er0 = st.xb[0] * np.array([1.0, 1.0, 0.0])
    er0 /= np.linalg.norm(er0)
    ez = np.array([0.0, 0.0, 1.0])
    dv = args.dv_radial * er0 + args.dv_z * ez
    st.vb[0] += dv
    Iw0 = st.R[0] @ np.diag(st.Ib) @ st.R[0].T
    Lw0 = st.R[0] @ st.pi[0] + Iw0 @ (args.droll * er0)
    st.pi[0] = st.R[0].T @ Lw0
    # Les masses internes du module 0 suivent sa coque (sinon l'asservissement
    # encaisse l'écart de vitesse : secousse parasite au démarrage)
    k0 = st.bi == 0
    st.vi[k0] += dv + np.cross(args.droll * er0, st.xi[k0] - st.xb[0])
    # Idem pour les ergols : la poussée est donnée au vaisseau entier
    k0 = st.sb == 0
    st.vs[k0] += dv + np.cross(args.droll * er0, st.xs[k0] - st.xb[0])
    st.vn[st.cable_mid_node[0]] += args.dv_lateral * ez
    vcm = (st.mn @ st.vn + st.Mb @ st.vb + st.mi @ st.vi + st.sm @ st.vs) / st.m_total
    st.vn -= vcm
    st.vb -= vcm
    st.vi -= vcm
    st.vs -= vcm


def point_segment_dist(P, A, B):
    """Distances (m × b) des points P (m, 3) aux segments [A, B] (b, 3)."""
    AB = B - A
    u = np.einsum("mbi,bi->mb", P[:, None, :] - A[None], AB) / np.sum(AB * AB, axis=1)
    u = np.clip(u, 0.0, 1.0)
    return np.linalg.norm(P[:, None, :] - (A[None] + u[..., None] * AB[None]), axis=2)


def segment_segment_dist(p1, q1, p2, q2):
    """Distance minimale entre les segments [p1, q1] et [p2, q2]."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1 @ d1, d2 @ d2, d2 @ r
    c, b = d1 @ r, d1 @ d2
    den = a * e - b * b
    s = np.clip((b * f - c * e) / den, 0.0, 1.0) if den > 1e-12 else 0.0
    t = (b * s + f) / e
    if t < 0.0:
        t, s = 0.0, np.clip(-c / a, 0.0, 1.0)
    elif t > 1.0:
        t, s = 1.0, np.clip((b - c) / a, 0.0, 1.0)
    return float(np.linalg.norm(p1 + s * d1 - (p2 + t * d2)))


def roll_angles(xb, R, com, eL, module):
    """Roulis de chaque module autour du câble (rad, relatif à l'orientation
    nominale) et position hors plan (m)."""
    qk, q_nom = ROLL_REF[module]
    r = xb - com
    zc = r @ eL
    r = r - zc[:, None] * eL
    er = r / np.linalg.norm(r, axis=1)[:, None]
    et = np.cross(eL, er)
    q = R[:, :, qk]
    return np.arctan2(q @ eL, np.sum(q * et, axis=1)) - q_nom, zc


def run(args):
    st = Station(args)
    name = args.name or f"{args.topology}_{args.module}"
    p = print if not args.quiet else (lambda *a, **k: None)
    rpm_1g = math.sqrt(G0 / st.R_target) * 60 / (2 * math.pi)
    p(f"=== {name} ===")
    p(f"Cible           : {args.g * G0:.3f} m/s² ({args.g:.4f} g) à {args.rpm:g} tr/min → rayon au centre de masse des modules R = {st.R_target:.1f} m "
      f"(1 g avec ce rayon : {rpm_1g:.2f} tr/min)")
    p(f"Topologie       : {args.topology}, {st.nb} modules de {args.mass_t:g} t ({args.module}, cylindre Ø{2 * args.module_radius:g} m × {args.module_length:g} m), "
      f"attache à {st.h:g} m du centre de masse")
    p(f"Câble           : dimensionné pour {args.design_mass_t or args.mass_t:g} t à {args.design_g:g} g (facteur {args.safety:g}) : section {st.area * 1e4:.1f} cm² "
      f"(Ø équiv. {2 * math.sqrt(st.area / math.pi) * 100:.1f} cm), {args.material}, T_conception = {st.T_design / 1e6:.2f} MN")
    if args.motion != "none":
        p(f"Masse interne   : {args.motion_mass_t:g} t, programme « {args.motion} », amplitude {args.motion_amp:g} m selon l'axe {args.motion_axis}, "
          f"module(s) {args.motion_modules}")
    if st.cd:
        p(f"Amortisseur     : sphère interne J = {args.damper_frac:g}·I_transverse, τ = {args.damper_tau:g} s")
    if st.ship:
        sh = st.ship
        p(f"Vaisseau        : partie rigide {sh['M_rigid'] / 1e3:.0f} t, centre de masse à {sh['x_c']:.1f} m de la pointe "
          f"(total {sh['x_tot']:.1f} m), attaches à {sh['x_tot'] - st.h:.1f} m de la pointe ; I_axe = {sh['I_ax'] / st.M:.1f}·M, "
          f"I_transverse = {sh['I_tr'] / st.M:.1f}·M")
        for tk in sh["tanks"]:
            p(f"  {tk['name']:4s}          : {tk['m'] / 1e3:.0f} t sur {tk['depth']:.2f} m ; ballottant {tk['ms'] / 1e3:.1f} t, pendule {tk['L']:.2f} m, "
              f"articulation à {tk['x_hinge']:.2f} m de la pointe" + (" (figé)" if args.slosh == "frozen" else ""))
        if len(st.sm):
            p(f"  fréquences    : " + ", ".join(f"{w / (2 * math.pi):.3f} Hz" for w in st.s_w[st.sb == 0]) + " ; ζ = " + ", ".join(f"{z:g}" for z in st.s_zeta[st.sb == 0]))
    p("Relaxation vers l'équilibre en rotation...")
    st.relax(verbose=not args.quiet)
    L0 = st.ds0[: st.n].sum()
    P, _ = st.points()
    _, t_eq, stretch, _, _ = st.spring_forces(P)
    L_eq = L0 + stretch[: st.n].sum()
    cable_mass = st.lam * st.ds0.sum()
    p(f"Équilibre       : câble {L0:.2f} m à vide, {L_eq:.2f} m sous charge (+{(L_eq - L0) * 100:.0f} cm), "
      f"tension {t_eq[0] / 1e6:.2f} MN, masse de câble totale {cable_mass / 1000:.1f} t, v tangentielle {st.omega * st.R_eq:.1f} m/s")
    T_eq_cables = [float(v) for v in t_eq[st.cable_first_seg]]
    if st.hub_m > 0:
        sp = st.topo["spokes"]
        L_spoke = float(st.ds0[st.spoke_seg].sum() / len(sp))
        p(f"Moyeu           : {st.hub_m / 1e3:g} t au centre, {len(sp)} rayons de {L_spoke:.1f} m à vide, tension "
          + ", ".join(f"{T_eq_cables[c] / 1e6:.3f}" for c in sp) + " MN (côtés " + ", ".join(f"{T_eq_cables[c] / 1e6:.3f}" for c in range(sp[0])) + " MN)")

    # Prédictions analytiques
    # - roulis autour du câble : voir roll_prediction ;
    # - balancements (câble long, point d'attache libre latéralement) :
    #   dans le plan Ω² = M·a·h / I_z ; hors plan Ω² = (M·a·h + ω²(I_z − I_r)) / I_t
    I_r, I_t, I_z = st.local_inertia()
    w2 = st.omega ** 2
    roll_pred = roll_prediction(args.topology, args.spread, I_r, I_t, I_z, st.omega, t_eq[0], L_eq)
    Mah = st.M * args.g * G0 * st.h
    f_pitch = math.sqrt(Mah / I_z) / (2 * math.pi)
    f_swing = math.sqrt(max(Mah + w2 * (I_z - I_r), 0.0) / I_t) / (2 * math.pi)
    p(f"Inerties module : I_r = {I_r / st.M:.1f}·M, I_t = {I_t / st.M:.1f}·M, I_z = {I_z / st.M:.1f}·M (m²)")
    p(f"Prédiction      : roulis autour du câble {roll_pred} ; balancement dans le plan ≈ {f_pitch:.3f} Hz, hors plan ≈ {f_swing:.3f} Hz")
    tilt_static = static_tilt_prediction(args, st.h)
    if tilt_static is not None:
        delta = args.motion_mass_t * 1e3 * args.motion_amp / st.M
        p(f"Prédiction      : décalage du centre de masse {delta * 100:.0f} cm → inclinaison statique du plancher ≈ {tilt_static:.2f}°")

    st.set_rigid_rotation()
    apply_perturbation(st, args)
    Mtot = st.m_total

    dt = st.dt
    n_steps = int(args.duration / dt)
    rec_every = max(1, int(round(args.record_dt / dt)))
    traj_every = max(1, int(round(args.traj_dt / dt))) if args.traj_dt > 0 else 0
    p(f"Intégration     : dt = {dt * 1e3:.3f} ms, {n_steps} pas, {st.xn.shape[0]} nœuds, {args.duration:g} s simulées")

    E0 = st.energy()
    L0v = st.angular_momentum()
    eL = L0v / np.linalg.norm(L0v)
    rec = {k: [] for k in ("t", "g", "T", "tilt", "roll", "wrel", "z", "plane", "E", "L", "s", "slosh",
                           "Tc", "rship", "wsys", "gap", "clear", "vwhip")}
    # Rupture : segment qui cède, nœuds libres du câble rompu
    nc, ns = st.n_cables, st.n
    brk = getattr(args, "break_cable", -1)
    k_brk, brk_meta = None, None
    if brk >= 0:
        f0 = st.cable_first_seg[brk]
        k_brk = f0 + min(int(args.break_at * ns), ns - 1)
        brk_nodes = np.unique(st.seg[f0:f0 + ns][st.seg[f0:f0 + ns] < st.nf])
        p(f"Rupture         : câble {brk}, segment {k_brk - f0 + 1}/{ns} (fraction {args.break_at:g}), à t = {args.break_time:g} s")
    pairs = [(a, b) for a in range(st.nb) for b in range(a + 1, st.nb)]
    tpk = np.zeros(nc)  # tension de crête par câble depuis le dernier enregistrement
    traj = {k: [] for k in ("t", "xb", "R", "xn", "pa", "xi", "xs")}
    P, rw = st.points()
    F, *_ = st.spring_forces(P)
    Fi, Fbi, Tbi = st.internal_forces(0.0)
    Fs, Fbs, Tbs = st.slosh_forces()
    Td = st.damper_torque()
    w_diss = 0.0
    i_s, j_s = st.seg[:, 0], st.seg[:, 1]
    nb = st.nb
    for step in range(n_steps + 1):
        t = step * dt
        if k_brk is not None and brk_meta is None and t >= args.break_time:
            # Le segment cède : son énergie élastique est perdue (comptée dissipée)
            _, _, stretch, taut, _ = st.spring_forces(P)
            E_rel = 0.5 * st.k[k_brk] * stretch[k_brk] ** 2 if taut[k_brk] else 0.0
            w_diss += E_rel
            st.alive[k_brk] = False
            brk_meta = dict(t=t, cable=brk, seg=int(k_brk), E_seg_J=float(E_rel))
            F, *_ = st.spring_forces(P)
        if (brk_meta and args.release_delay >= 0 and "released" not in brk_meta
                and t >= brk_meta["t"] + args.release_delay):
            # Coupe-câbles : les deux segments d'attache du câble rompu sont
            # coupés, les morceaux sont largués
            f0 = st.cable_first_seg[brk]
            cut = [k for k in (f0, f0 + ns - 1) if st.alive[k]]
            _, _, stretch, taut, _ = st.spring_forces(P)
            w_diss += float(np.sum(np.where(taut[cut], 0.5 * st.k[cut] * stretch[cut] ** 2, 0.0)))
            st.alive[cut] = False
            brk_meta["released"] = dict(t=t, segs=[int(k) for k in cut])
            F, *_ = st.spring_forces(P)
        if step % rec_every == 0:
            # Forces réelles (ressort + amortisseur) pour les diagnostics
            Pv = st.point_velocities(rw)
            _, t_s, _, taut, e = st.spring_forces(P)
            vrel = np.einsum("ij,ij->i", Pv[j_s] - Pv[i_s], e)
            t_tot = np.where(taut, np.maximum(t_s + st.c * vrel, 0.0), 0.0)
            f = t_tot[:, None] * e
            Fd = np.zeros_like(P)
            np.add.at(Fd, i_s, f)
            np.add.at(Fd, j_s, -f)
            Fb, _ = st.wrench(Fd[st.nf:], rw)
            Fb = Fb + Fbi + Fbs  # force spécifique de la structure : câbles + réactions des masses internes et des ergols
            Fn = np.linalg.norm(Fb, axis=1)
            up = np.einsum("bij,bj->bi", st.R, st.up_body)
            tilt = np.degrees(np.arccos(np.clip(np.sum(up * Fb, axis=1) / Fn, -1, 1)))
            com = (st.mn @ st.xn + st.Mb @ st.xb + st.mi @ st.xi + st.sm @ st.xs) / Mtot
            roll, zc = roll_angles(st.xb, st.R, com, eL, args.module)
            wrel = np.degrees(np.linalg.norm(st.omega_world() - st.omega * eL, axis=1))
            if nb == 2:
                d = st.xb[1] - st.xb[0]
                plane = math.degrees(math.asin(min(1.0, abs(d @ eL) / np.linalg.norm(d))))
            else:
                nrm = np.cross(st.xb[1] - st.xb[0], st.xb[2] - st.xb[0])
                plane = math.degrees(math.acos(min(1.0, abs(nrm @ eL) / np.linalg.norm(nrm))))
            rec["t"].append(t)
            rec["g"].append(Fn / st.Mb / G0)
            rec["T"].append(t_tot[st.cable_first_seg])
            rec["tilt"].append(tilt)
            rec["roll"].append(roll)
            rec["wrel"].append(wrel)
            rec["z"].append(zc)
            rec["plane"].append(plane)
            rec["E"].append(st.energy() + w_diss)
            rec["L"].append(st.angular_momentum())
            rec["s"].append(st.program(t) if st.program else 0.0)
            rec["slosh"].append(st.slosh_offsets()[st.sb == 0])
            rec["Tc"].append(np.maximum(tpk, t_tot.reshape(nc, ns).max(axis=1)))
            tpk[:] = 0.0
            rec["rship"].append(np.linalg.norm((st.xb - com)[:, :2], axis=1))
            rec["wsys"].append(st.spin_rate(com))
            hA, hB = st.hull_axes()
            rec["gap"].append([segment_segment_dist(hA[a], hB[a], hA[b], hB[b]) - 2 * args.module_radius for a, b in pairs])
            if k_brk is not None:
                xnb = st.xn[brk_nodes]
                rec["clear"].append(point_segment_dist(xnb, hA, hB).min(axis=0) - args.module_radius)
                rec["vwhip"].append(float(np.linalg.norm(st.vn[brk_nodes] - np.cross(st.omega * eL, xnb - com), axis=1).max()))
            if not args.quiet and step % (rec_every * 2000) == 0:
                print(f"  t = {t:7.1f} s  roulis max {np.degrees(np.abs(roll)).max():6.2f}°  plancher {tilt.max():6.2f}°", flush=True)
        if traj_every and step % traj_every == 0:
            traj["t"].append(t)
            traj["xb"].append(st.xb.copy())
            traj["R"].append(st.R.copy())
            traj["xn"].append(st.xn.copy())
            traj["pa"].append(P[st.nf:].copy())
            traj["xi"].append(st.xi.copy())
            traj["xs"].append(st.xs.copy())
        st.kick(dt / 2, F, rw, Fi, Fbi + Fbs, Tbi + Tbs, Td, Fs)
        st.drift(dt)
        P, rw = st.points()
        F, t_spr, *_ = st.spring_forces(P)
        np.maximum(tpk, t_spr.reshape(nc, ns).max(axis=1), out=tpk)
        Fi, Fbi, Tbi = st.internal_forces(t + dt)
        Fs, Fbs, Tbs = st.slosh_forces()
        Td = st.damper_torque()
        st.kick(dt / 2, F, rw, Fi, Fbi + Fbs, Tbi + Tbs, Td, Fs)
        w_diss += st.damp(dt)
        if st.cd:
            w_diss += dt * np.sum(Td * (st.omega_world() - st.hs / st.J))

    rec = {k: np.array(v) for k, v in rec.items()}
    rec["roll"] = np.degrees(np.unwrap(rec["roll"], axis=0))
    info = dict(name=name, topology=args.topology, module=args.module, g=args.g, rpm=args.rpm,
                R=st.R_target, rpm_1g=rpm_1g, L0=L0, L_eq=L_eq, T_eq=float(t_eq[0]), T_design=st.T_design,
                area_cm2=st.area * 1e4, cable_mass_t=cable_mass / 1000, I_local_over_M=[I_r / st.M, I_t / st.M, I_z / st.M],
                roll_prediction=roll_pred, f_pitch_pred=f_pitch, f_swing_pred=f_swing, h=st.h,
                motion=args.motion, motion_mass_t=args.motion_mass_t, motion_amp=args.motion_amp,
                tilt_static_pred=tilt_static, damper=bool(st.cd), T_eq_cables=T_eq_cables,
                hub_mass_t=st.hub_m / 1e3, spokes=st.topo.get("spokes", []), args=vars(args))
    if brk_meta:
        info["break"] = brk_meta
    if st.ship:
        sh = st.ship
        info["ship"] = dict(M_rigid_t=sh["M_rigid"] / 1e3, x_c=sh["x_c"], x_tot=sh["x_tot"], x_attach=sh["x_tot"] - st.h,
                            I_ax_over_M=sh["I_ax"] / st.M, I_tr_over_M=sh["I_tr"] / st.M,
                            tanks=[{k: (v / 1e3 if k in ("m", "ms", "mf") else v) for k, v in tk.items()} for tk in sh["tanks"]],
                            f_slosh=[float(w / (2 * math.pi)) for w in st.s_w[st.sb == 0]], zeta=[float(z) for z in st.s_zeta[st.sb == 0]])
    if traj_every:
        os.makedirs(args.out, exist_ok=True)
        np.savez_compressed(os.path.join(args.out, name + "_traj.npz"),
                            **{k: np.array(v, dtype=np.float32) for k, v in traj.items()},
                            seg=st.seg, nf=st.nf, att_body=st.att_body, att_r=st.att_r.astype(np.float32),
                            Ib=st.Ib, module=args.module, module_radius=args.module_radius,
                            module_length=args.module_length, omega=st.omega, bi=st.bi, ai=st.ai,
                            sb=st.sb, sh=st.sh, sm=st.sm)
    report(st, rec, E0, L0v, args, info, p)


def first_crossing(t, y, thr):
    idx = np.nonzero(np.abs(y) > thr)[0]
    return float(t[idx[0]]) if len(idx) else None


def spectrum_peak(t, y, fmin=0.01, fmax=2.0):
    sig = y - y.mean()
    freqs = np.fft.rfftfreq(len(sig), t[1] - t[0])
    spec = np.abs(np.fft.rfft(sig * np.hanning(len(sig))))
    spec[(freqs < fmin) | (freqs > fmax)] = 0
    return freqs, spec, float(freqs[np.argmax(spec)])


def break_results(rec, info, args):
    """Bilan d'une rupture : fouet du brin libre, distances aux coques,
    surtensions et détentes des câbles restants, état final (5 dernières
    minutes)."""
    b = info["break"]
    t = rec["t"]
    after = t >= b["t"]
    whip = after & (t <= b["t"] + 60)
    tail = t >= t[-1] - 300
    keep = [c for c in range(rec["Tc"].shape[1]) if c != b["cable"]]
    Tk = rec["Tc"][:, keep]
    i_T = np.unravel_index(np.argmax(np.where(after[:, None], Tk, -1)), Tk.shape)
    cl = np.where(after[:, None], rec["clear"], np.inf)
    i_c = np.unravel_index(np.argmin(cl), cl.shape)
    gp = np.where(after, rec["gap"].min(axis=1), np.inf)
    dtr = t[1] - t[0]
    a = info["args"]
    E_cable = 0.5 * info["T_eq_cables"][b["cable"]] ** 2 * info["L_eq"] / (MATERIALS[a["material"]]["E"] * info["area_cm2"] * 1e-4)
    w = rec["wsys"]
    return dict(t=b["t"], cable=b["cable"], E_seg_kJ=b["E_seg_J"] / 1e3, E_cable_kJ=E_cable / 1e3,
                v_whip_max=float(rec["vwhip"][whip].max()),
                clear_min=float(cl[i_c]), clear_ship=int(i_c[1]), clear_t=float(t[i_c[0]] - b["t"]),
                gap_min=float(gp.min()), gap_t=float(t[np.argmin(gp)] - b["t"]),
                T_max_MN=float(Tk[i_T] / 1e6), T_max_cable=int(keep[i_T[1]]), T_max_t=float(t[i_T[0]] - b["t"]),
                slack_s=float(np.sum(np.any(Tk[after] <= 0, axis=1)) * dtr),
                g_min=[float(v) for v in rec["g"][after].min(axis=0) * G0], g_max=[float(v) for v in rec["g"][after].max(axis=0) * G0],
                g_final=[float(v) for v in rec["g"][tail].mean(axis=0) * G0],
                tilt_max=[float(v) for v in rec["tilt"][after].max(axis=0)], wrel_max=[float(v) for v in rec["wrel"][after].max(axis=0)],
                rpm_before=float(w[~after].mean() * 60 / (2 * math.pi)), rpm_final=float(w[tail].mean() * 60 / (2 * math.pi)),
                r_final=[float(v) for v in rec["rship"][tail].mean(axis=0)], r_max=[float(v) for v in rec["rship"][after].max(axis=0)])


def report(st, rec, E0, L0v, args, info, p):
    t = rec["t"]
    # Énergie non conservée : travail des masses asservies, ou amortissement des ergols
    forced = args.motion != "none" or bool(np.any(st.s_zeta > 0))
    dE = (rec["E"] - E0) / E0
    dL = np.linalg.norm(rec["L"] - L0v, axis=1) / np.linalg.norm(L0v)
    roll_abs = np.abs(rec["roll"]).max(axis=1)
    freqs, spec_g, f_g = spectrum_peak(t, rec["g"][:, 0], fmin=0.1)
    _, spec_tilt, f_tilt = spectrum_peak(t, rec["tilt"][:, 0], fmin=0.01)
    t1, t10, t45, t90 = (first_crossing(t, roll_abs, x) for x in (1, 10, 45, 90))
    growth = doubling_time(t1, t10, t45, args.duration)
    res = dict(g_min=float(rec["g"].min()), g_max=float(rec["g"].max()), g_mean=float(rec["g"].mean()),
               T_max_MN=float(rec["T"].max() / 1e6), T_min_MN=float(rec["T"].min() / 1e6),
               tilt_max=float(rec["tilt"].max()), roll_max=float(roll_abs.max()),
               roll_final=float(np.abs(rec["roll"][-200:]).mean()) if len(t) > 200 else None,
               roll_turns=float(np.abs(rec["roll"][-1]).max() / 360), wrel_max=float(rec["wrel"].max()),
               plane_max=float(rec["plane"].max()), z_max=float(np.abs(rec["z"]).max()),
               t_roll_1=t1, t_roll_10=t10, t_roll_45=t45, t_roll_90=t90, doubling_time=growth,
               f_bungee=f_g, f_tilt=f_tilt, dE_max=None if forced else float(np.abs(dE).max()), dL_max=float(dL.max()))
    if rec["slosh"].size:
        res["slosh_max"] = [float(v) for v in rec["slosh"].max(axis=0)]
    res["Tc_max_MN"] = [float(v) for v in rec["Tc"].max(axis=0) / 1e6]
    res["gap_min"] = float(rec["gap"].min())
    res["rpm_mean"] = float(rec["wsys"].mean() * 60 / (2 * math.pi))
    if "break" in info:
        res["break"] = break_results(rec, info, args)
    info["results"] = res

    p("\n--- Résultats ---")
    p(f"g ressenti      : {res['g_min']:.4f} à {res['g_max']:.4f} g (moyenne {res['g_mean']:.4f}, visé {args.g:g})")
    p(f"Tension         : {res['T_min_MN']:.2f} à {res['T_max_MN']:.2f} MN")
    p(f"Roulis (câble)  : max {res['roll_max']:.1f}°" + (f", 1° à {t1:.0f} s, 10° à {t10:.0f} s" if t10 else "")
      + (f", 90° à {t90:.0f} s" if t90 else "") + (f" — temps de doublement mesuré ≈ {growth:.1f} s" if growth else "")
      + (f" ; final ≈ {res['roll_final']:.1f}°" if res["roll_final"] is not None else ""))
    p(f"Plancher        : inclinaison max {res['tilt_max']:.2f}° par rapport à la gravité apparente")
    p(f"Rotation parasite: max {res['wrel_max']:.2f} °/s (rotation de la pièce en plus de la rotation de la station)")
    p(f"Plan de rotation: écart max {res['plane_max']:.3f}°, hors plan max {res['z_max']:.3f} m")
    p(f"Spectres        : bungee {f_g:.3f} Hz ; inclinaison plancher {f_tilt:.3f} Hz "
      f"(prédit : dans le plan {info['f_pitch_pred']:.3f} Hz, hors plan {info['f_swing_pred']:.3f} Hz)")
    if "slosh_max" in res:
        p("Ballottement    : écart latéral max " + ", ".join(f"{tk['name']} {v:.2f} m" for tk, v in zip(st.ship["pendulums"], res["slosh_max"])))
    p(f"Conservation    : " + (f"énergie {res['dE_max']:.1e}, " if res["dE_max"] is not None else "énergie n/a (système forcé ou amorti), ")
      + f"moment cinétique {res['dL_max']:.1e}")
    p(f"Câbles          : tension de crête " + ", ".join(f"{v:.2f}" for v in res["Tc_max_MN"]) + " MN ; écart min entre coques "
      f"{res['gap_min']:.1f} m")
    if "break" in res:
        b = res["break"]
        p(f"Rupture         : t = {b['t']:g} s, énergie du segment {b['E_seg_kJ']:.0f} kJ, énergie élastique du câble {b['E_cable_kJ']:.0f} kJ ; "
          f"brin libre jusqu'à {b['v_whip_max']:.1f} m/s")
        p(f"  coques        : brin à {b['clear_min']:.1f} m au plus près (module {b['clear_ship']}, t = {b['clear_t']:.1f} s) ; "
          f"coques à {b['gap_min']:.1f} m au plus près (t = {b['gap_t']:.0f} s)")
        p(f"  câbles restants : tension max {b['T_max_MN']:.2f} MN (câble {b['T_max_cable']}, t = {b['T_max_t']:.1f} s), "
          f"détendus {b['slack_s']:.1f} s au total")
        p(f"  après         : " + " ; ".join(f"module {k} : g {lo:.2f}–{hi:.2f} m/s², final {fin:.2f}, plancher max {tl:.0f}°, rotation parasite max {wr:.1f} °/s"
                                             for k, (lo, hi, fin, tl, wr) in enumerate(zip(b["g_min"], b["g_max"], b["g_final"], b["tilt_max"], b["wrel_max"]))))
        p(f"  rotation      : {b['rpm_before']:.3f} → {b['rpm_final']:.3f} tr/min ; distance au centre finale "
          + ", ".join(f"{v:.0f}" for v in b["r_final"]) + " m")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(4, 2, figsize=(14, 15))
    nb = st.nb
    for b in range(nb):
        ax[0, 0].plot(t, rec["g"][:, b], lw=0.6, label=f"module {b}")
        ax[1, 0].plot(t, rec["roll"][:, b], lw=0.8, label=f"module {b}")
        ax[1, 1].plot(t, rec["tilt"][:, b], lw=0.6, label=f"module {b}")
        ax[2, 0].plot(t, rec["wrel"][:, b], lw=0.6, label=f"module {b}")
        ax[2, 1].plot(t, rec["z"][:, b], lw=0.6, label=f"module {b}")
    ax[0, 0].axhline(args.g, color="k", ls="--", lw=0.6)
    ax[0, 0].set(title="Gravité ressentie (centre de masse du module)", xlabel="t (s)", ylabel="g")
    for c in range(rec["T"].shape[1]):
        ax[0, 1].plot(t, rec["T"][:, c] / 1e6, lw=0.6, label=f"câble {c}")
    ax[0, 1].set(title="Tension au point d'attache", xlabel="t (s)", ylabel="MN")
    ax[1, 0].set(title="Roulis autour du câble (rotation de la pièce autour de la verticale)", xlabel="t (s)", ylabel="°")
    ax[1, 1].set(title="Inclinaison du plancher / gravité apparente", xlabel="t (s)", ylabel="°")
    if forced:
        ax2 = ax[1, 1].twinx()
        ax2.plot(t, rec["s"], color="gray", lw=0.8, ls=":", label="position masse interne")
        ax2.set_ylabel("position masse interne (m)")
    ax[2, 0].set(title="Rotation parasite ressentie |Ω − ω·e_L|", xlabel="t (s)", ylabel="°/s")
    ax[2, 1].set(title="Déplacement hors du plan de rotation", xlabel="t (s)", ylabel="m")
    ax[3, 0].semilogy(freqs, spec_g / spec_g.max() + 1e-12, lw=0.8, label="g ressenti")
    ax[3, 0].semilogy(freqs, spec_tilt / spec_tilt.max() + 1e-12, lw=0.8, label="inclinaison plancher")
    ax[3, 0].axvline(info["f_pitch_pred"], color="k", ls="--", lw=0.6, label="balancement prédit (plan)")
    ax[3, 0].axvline(info["f_swing_pred"], color="k", ls=":", lw=0.6, label="balancement prédit (hors plan)")
    ax[3, 0].set(title="Spectres (module 0, normalisés)", xlabel="Hz", xlim=(0, 1.0), ylim=(1e-6, 2))
    if not forced:
        ax[3, 1].plot(t, dE, label="énergie + dissipée")
    ax[3, 1].plot(t, dL, label="|ΔL|/|L|")
    ax[3, 1].set(title="Conservation (erreur relative)", xlabel="t (s)")
    for a_ in ax.flat:
        a_.legend(fontsize=8)
    fig.suptitle(f"{info['name']} — {args.topology}, modules {args.mass_t:g} t ({args.module}), {args.g:g} g à {args.rpm:g} tr/min, "
                 f"R = {info['R']:.0f} m, câble {info['L0']:.0f} m, ζ = {args.zeta:g}")
    fig.tight_layout()
    os.makedirs(args.out, exist_ok=True)
    base = os.path.join(args.out, info["name"])
    fig.savefig(base + ".png", dpi=100)
    plt.close(fig)
    np.savez_compressed(base + ".npz", t=t, roll=rec["roll"], tilt=rec["tilt"], wrel=rec["wrel"], g=rec["g"], slosh=rec["slosh"],
                        s=rec["s"], T=rec["T"], z=rec["z"], Tc=rec["Tc"], rship=rec["rship"], wsys=rec["wsys"], gap=rec["gap"],
                        clear=rec["clear"], vwhip=rec["vwhip"])
    with open(base + ".json", "w") as fh:
        json.dump(info, fh, indent=2, ensure_ascii=False)
    p(f"Graphiques      : {os.path.abspath(base + '.png')}")


def make_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", help="nom du scénario (fichiers de sortie)")
    p.add_argument("--topology", choices=["dumbbell", "ladder", "triangle", "triangle2"], default="dumbbell")
    p.add_argument("--module", choices=list(ORIENTATIONS), default="tangential",
                   help="orientation de l'axe long des modules : tangential (sens du mouvement), axial (parallèle à l'axe de rotation), radial (tour)")
    p.add_argument("--mass-t", type=float, default=1600, help="masse de chaque module (t)")
    p.add_argument("--module-radius", type=float, default=6.0, help="rayon du cylindre (m)")
    p.add_argument("--module-length", type=float, default=40.0, help="longueur du cylindre (m)")
    p.add_argument("--bridle", type=float, default=0.0, help="hauteur de patte d'oie au-dessus de la coque (m)")
    p.add_argument("--spread", type=float, help="écartement des points d'attache (ladder : selon l'axe de rotation ; triangle2 : selon e_t)")
    p.add_argument("--g", type=float, default=0.38, help="gravité visée en fonctionnement (en g)")
    p.add_argument("--accel", type=float, help="gravité visée en m/s² (remplace --g ; Mars : 3.711)")
    p.add_argument("--design-mass-t", type=float, help="masse de chaque module pour dimensionner les câbles (t, défaut : --mass-t)")
    p.add_argument("--rpm", type=float, default=1.0, help="vitesse de rotation visée (tr/min)")
    p.add_argument("--design-g", type=float, default=1.0, help="gravité de dimensionnement des câbles (en g)")
    p.add_argument("--material", choices=MATERIALS, default="dyneema")
    p.add_argument("--safety", type=float, default=3.0, help="facteur de sécurité pour dimensionner la section")
    p.add_argument("--segments", type=int, default=16, help="segments par câble")
    p.add_argument("--zeta", type=float, default=0.02, help="taux d'amortissement visé du mode bungee")
    p.add_argument("--duration", type=float, default=600, help="durée simulée (s)")
    p.add_argument("--dv-radial", type=float, default=0.02, help="perturbation radiale du module 0 (m/s)")
    p.add_argument("--dv-z", type=float, default=0.02, help="perturbation hors plan du module 0 (m/s)")
    p.add_argument("--droll", type=float, default=0.002, help="perturbation de roulis du module 0 autour du câble (rad/s)")
    p.add_argument("--dv-lateral", type=float, default=0.0, help="perturbation hors plan au milieu du câble 0 (m/s)")
    p.add_argument("--motion", choices=["none", "cargo", "walk", "periodic", "sweep"], default="none",
                   help="programme de déplacement d'une masse interne")
    p.add_argument("--motion-mass-t", type=float, default=50.0, help="masse interne mobile (t)")
    p.add_argument("--motion-amp", type=float, default=15.0, help="amplitude du déplacement (m)")
    p.add_argument("--motion-axis", choices=["long", "t", "z", "r"], default="long",
                   help="axe du déplacement : axe long du module, ou direction locale t/z/r")
    p.add_argument("--motion-modules", default="0", help="modules concernés (ex. 0 ou 0,1)")
    p.add_argument("--motion-speed", type=float, default=1.2, help="vitesse de marche (programme walk, m/s)")
    p.add_argument("--motion-period", type=float, default=60.0, help="période (programme periodic, s)")
    p.add_argument("--sweep-f1", type=float, default=0.25, help="fréquence finale du balayage (Hz)")
    p.add_argument("--motion-stop", type=float, help="arrêt du programme periodic (s)")
    p.add_argument("--damper-frac", type=float, default=0.0, help="amortisseur interne : inertie de la sphère / inertie transverse du module")
    p.add_argument("--damper-tau", type=float, default=30.0, help="amortisseur interne : constante de temps (s)")
    p.add_argument("--slosh", choices=["off", "frozen", "free"], default="off",
                   help="Starship à ergols (modules radiaux) : off = cylindre homogène ; frozen = modèle de masse, ergols figés ; "
                        "free = ergols ballottants (pendules d'Abramson)")
    p.add_argument("--tld-mass-t", type=float, default=0.0, help="amortisseur à liquide accordé : masse d'eau (t), prise sur la charge utile")
    p.add_argument("--tld-x", type=float, default=46.0, help="fond du bassin, en m depuis la pointe")
    p.add_argument("--tld-radius", type=float, default=4.5, help="rayon du bassin (m) ; la profondeur, donc l'accord, en découle")
    p.add_argument("--tld-zeta", type=float, default=0.15, help="amortissement du clapotis du bassin (grilles, écrans perforés)")
    p.add_argument("--slosh-zeta", type=float, default=0.001, help="amortissement du ballottement (parois : ~1e-4 à 1e-3 ; chicanes : 0,02 à 0,05)")
    p.add_argument("--hub-mass-t", type=float, default=0.0, help="moyeu central (t) relié au nez de chaque module par un rayon (0 = sans)")
    p.add_argument("--spoke-tension", type=float, default=0.15, help="prétension des rayons, en fraction de la tension nominale d'un côté")
    p.add_argument("--break-cable", type=int, default=-1, help="câble qui rompt (indice ; −1 = aucun ; avec moyeu, 3 à 5 = rayons)")
    p.add_argument("--break-time", type=float, default=60.0, help="instant de la rupture (s)")
    p.add_argument("--release-delay", type=float, default=-1.0, help="coupe-câbles : largage des morceaux du câble rompu après ce délai (s ; −1 = jamais)")
    p.add_argument("--hub-spokes", type=int, choices=[1, 2], default=1, help="rayons par vaisseau (2 : depuis chacun des deux points d'attache du nez)")
    p.add_argument("--break-at", type=float, default=0.5, help="position de la rupture le long du câble (0 = à la première attache, 0,5 = au milieu)")
    p.add_argument("--cfl", type=float, default=0.3, help="fraction du pas de temps critique")
    p.add_argument("--record-dt", type=float, default=0.05, help="période d'échantillonnage (s)")
    p.add_argument("--traj-dt", type=float, default=0.0, help="période d'enregistrement des trajectoires pour animation (s, 0 = non)")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
    return p


def main(argv=None):
    run(make_parser().parse_args(argv))


if __name__ == "__main__":
    main()
