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
  exacte à part.

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


def make_program(kind, amp, t0=60.0, speed=1.2, period=None, f0=0.004, f1=0.25, t1=None, a_max=1.0):
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
        w = 2 * math.pi / period
        A = min(amp, a_max / w ** 2)
        return lambda t: 0.0 if t < t0 else A * math.sin(w * (t - t0)) * smooth((t - t0) / period)
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
        self.args = args
        M = args.mass_t * 1e3
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
        topo = build_topology(args.topology, args.spread)
        self.topo = topo
        self.T_design = M * args.design_g * G0 * topo["tfac"]
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
            xb.append(self.R_target * er)
            R0.append(R)
            up.append(R.T @ -er)  # « haut » du module (vers le centre), repère du corps
            for st, sz in topo["attach"]:
                att_body.append(b)
                att_r.append(R.T @ (-self.h * er + st * et + sz * ez))
        self.xb = np.array(xb)
        self.R = np.array(R0)
        self.R_init = self.R.copy()
        self.up_body = np.array(up)
        self.att_body = np.array(att_body)
        self.att_r = np.array(att_r)
        self.Mb = np.array([M - (m_int if b in self.motion_modules else 0.0) for b in range(nb)])

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
                                    t1=args.duration - 60) if args.motion != "none" else None
        self.ki = self.mi * (2 * math.pi * 2.0) ** 2  # asservissement à 2 Hz
        self.ci = 2 * 0.7 * self.mi * (2 * math.pi * 2.0)
        self.xi = np.zeros((len(self.mi), 3))
        self.vi = np.zeros((len(self.mi), 3))

        # Amortisseur interne (sphère de Kane) : inertie J, constante de temps τ
        self.J = args.damper_frac * It
        self.cd = self.J / args.damper_tau if self.J > 0 else 0.0
        self.hs = np.zeros((nb, 3))

        # Câbles : nœuds libres, puis points d'attache (sans masse, portés par les corps)
        n = args.segments
        assert n >= 2
        P0, _ = self._attach_points(self.xb, self.R)
        xn, mn, segs, ds0 = [], [], [], []
        self.cable_first_seg, self.cable_mid_node = [], []
        for (bA, kA), (bB, kB) in topo["cables"]:
            iA, iB = bA * na + kA, bB * na + kB
            pA, pB = P0[iA], P0[iB]
            ds = np.linalg.norm(pB - pA) / n
            chain = [-(iA + 1)]
            for s in range(1, n):
                xn.append(pA + (pB - pA) * s / n)
                mn.append(self.lam * ds)
                chain.append(len(xn) - 1)
            chain.append(-(iB + 1))
            self.cable_first_seg.append(len(segs))
            self.cable_mid_node.append(chain[n // 2])
            segs += list(zip(chain[:-1], chain[1:]))
            ds0 += [ds] * n
            self.Mb[bA] += self.lam * ds / 2
            self.Mb[bB] += self.lam * ds / 2
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

        # Segments nœud-nœud en deux groupes sans nœud partagé (amortissement)
        i, j = self.seg[:, 0], self.seg[:, 1]
        att_i, att_j = i >= nf, j >= nf
        nn = ~(att_i | att_j)
        pos = np.arange(len(segs)) % n
        self.nn_groups = [np.where(nn & (pos % 2 == p))[0] for p in (0, 1)]
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
        return self.mn.sum() + self.Mb.sum() + self.mi.sum()

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
        taut = stretch > 0
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

    def damper_torque(self):
        """Couple visqueux entre la sphère interne et le module (sur la sphère)."""
        if self.cd == 0:
            return np.zeros((self.nb, 3))
        return self.cd * (self.omega_world() - self.hs / self.J)

    # --- intégration ----------------------------------------------------
    def kick(self, h, F, rw, Fi, Fbi, Tbi, Td):
        self.vn += h * F[: self.nf] / self.mn[:, None]
        Fb, Tb = self.wrench(F[self.nf:], rw)
        self.vb += h * (Fb + Fbi) / self.Mb[:, None]
        Lw = np.einsum("bij,bj->bi", self.R, self.pi) + h * (Tb + Tbi - Td)
        self.pi = np.einsum("bji,bj->bi", self.R, Lw)
        if len(self.mi):
            self.vi += h * Fi / self.mi[:, None]
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
        for k, h in ((0, dt / 2), (1, dt / 2), (2, dt), (1, dt / 2), (0, dt / 2)):
            self._rotate(k, h)

    def kinetic(self):
        ke = 0.5 * (self.mn @ np.sum(self.vn ** 2, axis=1) + self.Mb @ np.sum(self.vb ** 2, axis=1)
                    + np.sum(self.pi ** 2 / self.Ib))
        if len(self.mi):
            ke += 0.5 * self.mi @ np.sum(self.vi ** 2, axis=1)
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
            J = np.where(l > self.ds0[grp], mu * vrel * (1 - np.exp(-self.c[grp] * dt / mu)), 0.0)
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
        J = np.where(l > self.ds0[self.as_idx], mu * vrel * (1 - np.exp(-cs * dt / mu)), 0.0)
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
        avec lui."""
        w2 = self.omega ** 2
        mf = self.mn.min()
        dt = 1.6 / (2 * math.sqrt(self.k.max() / mf))
        Mb_tot = self.Mb.copy()
        np.add.at(Mb_tot, self.bi, self.mi)
        Mtot = self.mn.sum() + Mb_tot.sum()
        xy = np.array([1.0, 1.0, 0.0])
        for it in range(15):
            vn = np.zeros_like(self.xn)
            vb = np.zeros_like(self.xb)
            for step in range(100000):
                P, rw = self.points()
                F, *_ = self.spring_forces(P)
                Fn = F[: self.nf] + self.mn[:, None] * w2 * self.xn * xy
                Fb, _ = self.wrench(F[self.nf:], rw)
                Fb += Mb_tot[:, None] * w2 * self.xb * xy
                vn = 0.995 * (vn + Fn / mf * dt)
                vb = 0.995 * (vb + Fb / mf * dt)
                self.xn += vn * dt
                self.xb += vb * dt
                # La translation d'ensemble est instable dans le repère tournant
                # (centrifuge sur le centre de masse décalé, aucun câble ne s'y
                # oppose) : on recentre le centre de masse à chaque pas.
                com = (self.mn @ self.xn + Mb_tot @ self.xb) / Mtot
                self.xn -= com
                self.xb -= com
                if step % 1000 == 999 and max(np.abs(vn).max(), np.abs(vb).max()) < 1e-8:
                    break
            R = np.linalg.norm(self.xb[:, :2], axis=1).mean()
            if verbose:
                print(f"  itération {it}: R = {R:.5f} m (visé {self.R_target:.5f})")
            if abs(R - self.R_target) < 1e-4:
                break
            self.ds0 += (self.R_target - R) / self.topo["dRdL"] / self.n
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
        if self.cd:
            self.hs[:] = self.J * w

    # --- diagnostics ----------------------------------------------------
    def energy(self):
        P, _ = self.points()
        _, _, stretch, taut, _ = self.spring_forces(P)
        return self.kinetic() + 0.5 * np.sum(np.where(taut, self.k * stretch ** 2, 0.0))

    def angular_momentum(self):
        L = (self.mn @ np.cross(self.xn, self.vn) + self.Mb @ np.cross(self.xb, self.vb)
             + np.einsum("bij,bj->i", self.R, self.pi))
        if len(self.mi):
            L += self.mi @ np.cross(self.xi, self.vi)
        if self.cd:
            L += self.hs.sum(axis=0)
        return L

    def local_inertia(self, b=0):
        """Inerties du module dans le repère local (e_r, e_t, e_z) à l'état initial."""
        th = self.topo["angles"][b]
        er = np.array([math.cos(th), math.sin(th), 0.0])
        ez = np.array([0.0, 0.0, 1.0])
        et = np.cross(ez, er)
        Iw = self.R_init[b] @ np.diag(self.Ib) @ self.R_init[b].T
        return [float(v @ Iw @ v) for v in (er, et, ez)]


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
    st.vn[st.cable_mid_node[0]] += args.dv_lateral * ez
    vcm = (st.mn @ st.vn + st.Mb @ st.vb + st.mi @ st.vi) / st.m_total
    st.vn -= vcm
    st.vb -= vcm
    st.vi -= vcm


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
    p(f"Cible           : {args.g:g} g à {args.rpm:g} tr/min → rayon au centre de masse des modules R = {st.R_target:.1f} m "
      f"(1 g avec ce rayon : {rpm_1g:.2f} tr/min)")
    p(f"Topologie       : {args.topology}, {st.nb} modules de {args.mass_t:g} t ({args.module}, cylindre Ø{2 * args.module_radius:g} m × {args.module_length:g} m), "
      f"attache à {st.h:g} m du centre de masse")
    p(f"Câble           : dimensionné pour {args.design_g:g} g (facteur {args.safety:g}) : section {st.area * 1e4:.1f} cm² "
      f"(Ø équiv. {2 * math.sqrt(st.area / math.pi) * 100:.1f} cm), {args.material}, T_conception = {st.T_design / 1e6:.2f} MN")
    if args.motion != "none":
        p(f"Masse interne   : {args.motion_mass_t:g} t, programme « {args.motion} », amplitude {args.motion_amp:g} m selon l'axe {args.motion_axis}, "
          f"module(s) {args.motion_modules}")
    if st.cd:
        p(f"Amortisseur     : sphère interne J = {args.damper_frac:g}·I_transverse, τ = {args.damper_tau:g} s")
    p("Relaxation vers l'équilibre en rotation...")
    st.relax(verbose=not args.quiet)
    L0 = st.ds0[: st.n].sum()
    P, _ = st.points()
    _, t_eq, stretch, _, _ = st.spring_forces(P)
    L_eq = L0 + stretch[: st.n].sum()
    cable_mass = st.lam * st.ds0.sum()
    p(f"Équilibre       : câble {L0:.2f} m à vide, {L_eq:.2f} m sous charge (+{(L_eq - L0) * 100:.0f} cm), "
      f"tension {t_eq[0] / 1e6:.2f} MN, masse de câble totale {cable_mass / 1000:.1f} t, v tangentielle {st.omega * st.R_eq:.1f} m/s")

    # Prédictions analytiques
    # - roulis autour du câble (tangage verrouillé) : φ'' = ω² (I_t − I_z)/I_r · φ
    # - balancements (câble long, point d'attache libre latéralement) :
    #   dans le plan Ω² = M·a·h / I_z ; hors plan Ω² = (M·a·h + ω²(I_z − I_r)) / I_t
    I_r, I_t, I_z = st.local_inertia()
    w2 = st.omega ** 2
    s2 = w2 * (I_t - I_z) / I_r
    if abs(I_t - I_z) < 1e-9 * I_r:
        roll_pred = "neutre (I_t = I_z) : aucun couple de rappel"
    elif s2 > 0:
        roll_pred = f"INSTABLE, temps de doublement ≈ {math.log(2) / math.sqrt(s2):.1f} s"
    else:
        roll_pred = f"stable, période ≈ {2 * math.pi / math.sqrt(-s2):.1f} s"
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
    rec ={k: [] for k in ("t", "g", "T", "tilt", "roll", "wrel", "z", "plane", "E", "L", "s")}
    traj = {k: [] for k in ("t", "xb", "R", "xn", "pa", "xi")}
    P, rw = st.points()
    F, *_ = st.spring_forces(P)
    Fi, Fbi, Tbi = st.internal_forces(0.0)
    Td = st.damper_torque()
    w_diss = 0.0
    i_s, j_s = st.seg[:, 0], st.seg[:, 1]
    nb = st.nb
    for step in range(n_steps + 1):
        t = step * dt
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
            Fb = Fb + Fbi  # force spécifique de la structure : câbles + réaction des masses internes
            Fn = np.linalg.norm(Fb, axis=1)
            up = np.einsum("bij,bj->bi", st.R, st.up_body)
            tilt = np.degrees(np.arccos(np.clip(np.sum(up * Fb, axis=1) / Fn, -1, 1)))
            com = (st.mn @ st.xn + st.Mb @ st.xb + st.mi @ st.xi) / Mtot
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
            if not args.quiet and step % (rec_every * 2000) == 0:
                print(f"  t = {t:7.1f} s  roulis max {np.degrees(np.abs(roll)).max():6.2f}°  plancher {tilt.max():6.2f}°", flush=True)
        if traj_every and step % traj_every == 0:
            traj["t"].append(t)
            traj["xb"].append(st.xb.copy())
            traj["R"].append(st.R.copy())
            traj["xn"].append(st.xn.copy())
            traj["pa"].append(P[st.nf:].copy())
            traj["xi"].append(st.xi.copy())
        st.kick(dt / 2, F, rw, Fi, Fbi, Tbi, Td)
        st.drift(dt)
        P, rw = st.points()
        F, *_ = st.spring_forces(P)
        Fi, Fbi, Tbi = st.internal_forces(t + dt)
        Td = st.damper_torque()
        st.kick(dt / 2, F, rw, Fi, Fbi, Tbi, Td)
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
                tilt_static_pred=tilt_static, damper=bool(st.cd), args=vars(args))
    if traj_every:
        os.makedirs(args.out, exist_ok=True)
        np.savez_compressed(os.path.join(args.out, name + "_traj.npz"),
                            **{k: np.array(v, dtype=np.float32) for k, v in traj.items()},
                            seg=st.seg, nf=st.nf, att_body=st.att_body, att_r=st.att_r.astype(np.float32),
                            Ib=st.Ib, module=args.module, module_radius=args.module_radius,
                            module_length=args.module_length, omega=st.omega, bi=st.bi, ai=st.ai)
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


def report(st, rec, E0, L0v, args, info, p):
    t = rec["t"]
    forced = args.motion != "none"
    dE = (rec["E"] - E0) / E0
    dL = np.linalg.norm(rec["L"] - L0v, axis=1) / np.linalg.norm(L0v)
    roll_abs = np.abs(rec["roll"]).max(axis=1)
    freqs, spec_g, f_g = spectrum_peak(t, rec["g"][:, 0], fmin=0.1)
    _, spec_tilt, f_tilt = spectrum_peak(t, rec["tilt"][:, 0], fmin=0.01)
    t1, t10, t45, t90 = (first_crossing(t, roll_abs, x) for x in (1, 10, 45, 90))
    growth = (math.log(2) * (t10 - t1) / math.log(10)) if (t1 is not None and t10 is not None and t10 > t1) else None
    res = dict(g_min=float(rec["g"].min()), g_max=float(rec["g"].max()), g_mean=float(rec["g"].mean()),
               T_max_MN=float(rec["T"].max() / 1e6), T_min_MN=float(rec["T"].min() / 1e6),
               tilt_max=float(rec["tilt"].max()), roll_max=float(roll_abs.max()),
               roll_final=float(np.abs(rec["roll"][-200:]).mean()) if len(t) > 200 else None,
               roll_turns=float(np.abs(rec["roll"][-1]).max() / 360), wrel_max=float(rec["wrel"].max()),
               plane_max=float(rec["plane"].max()), z_max=float(np.abs(rec["z"]).max()),
               t_roll_1=t1, t_roll_10=t10, t_roll_45=t45, t_roll_90=t90, doubling_time=growth,
               f_bungee=f_g, f_tilt=f_tilt, dE_max=None if forced else float(np.abs(dE).max()), dL_max=float(dL.max()))
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
    p(f"Conservation    : " + (f"énergie {res['dE_max']:.1e}, " if res["dE_max"] is not None else "énergie n/a (système forcé), ")
      + f"moment cinétique {res['dL_max']:.1e}")

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
    np.savez_compressed(base + ".npz", t=t, roll=rec["roll"], tilt=rec["tilt"], wrel=rec["wrel"], g=rec["g"],
                        s=rec["s"], T=rec["T"], z=rec["z"])
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
    p.add_argument("--damper-frac", type=float, default=0.0, help="amortisseur interne : inertie de la sphère / inertie transverse du module")
    p.add_argument("--damper-tau", type=float, default=30.0, help="amortisseur interne : constante de temps (s)")
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
