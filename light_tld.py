#!/usr/bin/env python3
"""
Vaisseau habité allégé (§ 5.5) : modes hors plan et pic du balayage hors
plan, avec le bassin de la solution retenue (25 t, Ø 7,2 m, 12 m de la
pointe) ou un bassin réaccordé, sur le modèle linéaire de tld_design.py.

Paramètres de chaque cas (vitesse, rayon, tension et longueur des câbles du
vaisseau habité) : équilibres du simulateur (relaxation), avec les câbles de
la solution retenue et 3,711 m/s² au pont principal du vaisseau habité ; la
vitesse est cherchée pour que la longueur à vide des câbles ne change pas.
Le modèle linéaire majore de 15 à 50 % (pas d'amortissement des câbles) : il
sert à comparer et à choisir le bassin ; le simulateur tranche.

    .venv/bin/python light_tld.py > out/light_tld.log   # résumé : out/light_tld.json
"""
import itertools
import json
import math
import os

import numpy as np

import tether_sim as ts
import tld_design as td
from run_scenarios import UNEQ

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = dict(m_t=25.0, x=12.0, a=3.6, zeta=0.15)
# Bassins réaccordés simulés (campagnes allege et masses, scénarios *_bassin)
SIM_POOL = {"K100": dict(m_t=15.0, x=12.0, a=3.4, zeta=0.2), "K195": dict(m_t=35.0, x=12.0, a=4.4, zeta=0.2),
            "K300": dict(m_t=25.0, x=12.0, a=4.4, zeta=0.3), "U390": dict(m_t=19.0, x=12.0, a=4.4, zeta=0.15),
            "KL50": dict(m_t=25.0, x=12.0, a=4.4, zeta=0.3)}
# (nom, masses t, lest du vaisseau habité)
LIGHT = (("610", "610,610,610", None), ("K100", "510,660,660", None), ("K195", "415,708,708", None),
         ("K300", "310,760,760", None), ("U390", "220,805,805", None), ("KL50", "220,805,805", dict(m_t=50.0, x=44.0)))


def equilibrium(masses, rpm, ballast=None):
    """Relaxation du simulateur (modèle de la campagne masses) : longueur à vide
    des câbles, rayon du centre de masse du vaisseau habité, tension et
    longueur sous charge de ses câbles."""
    a = list(UNEQ)
    a[a.index("--masses-t") + 1] = masses
    a[a.index("--rpm") + 1] = f"{rpm:.6f}"
    if ballast:
        a += ["--ballast-t", f"{ballast['m_t']:g}", "--ballast-x", f"{ballast['x']:g}"]
    st = ts.Station(ts.make_parser().parse_args(a + ["--quiet"]))
    st.relax(verbose=False)
    P, _ = st.points()
    _, t_s, stretch, _, _ = st.spring_forces(P)
    L0 = st.ds0[: st.n].sum()
    return dict(L0=float(L0), R=float(st.R_target), T=float(t_s[st.cable_first_seg[0]]), L=float(L0 + stretch[: st.n].sum()))


def light_cases():
    """Vitesse de chaque cas : câbles de longueur à vide inchangée (secante)."""
    ref = equilibrium(LIGHT[0][1], 1.0)
    cases = []
    for name, masses, bal in LIGHT:
        r0, r1 = 1.0, 0.9
        e0, e1 = equilibrium(masses, r0, bal), equilibrium(masses, r1, bal)
        for _ in range(12):
            if abs(e1["L0"] - ref["L0"]) < 1e-3:
                break
            r0, r1, e0 = r1, r1 - (e1["L0"] - ref["L0"]) * (r1 - r0) / (e1["L0"] - e0["L0"]), e1
            e1 = equilibrium(masses, r1, bal)
        m0 = float(masses.split(",")[0])
        print(f"{name}: {r1:.4f} tr/min, vaisseau habité à R = {e1['R']:.1f} m, câbles {e1['L0']:.2f} m à vide "
              f"({e1['L']:.2f} m sous charge, {e1['T'] / 1e6:.3f} MN)", flush=True)
        cases.append((name, m0, bal, r1, e1["R"], e1["T"] / 1e6, e1["L"]))
    return cases


def kw(case, x_att=9.0):
    _, m, bal, rpm, R, T, L = case
    return dict(mass_t=m, ballast=bal, omega=rpm * 2 * math.pi / 60, R_tot=R, x_att=x_att, T_cable=T * 1e6, L_cable=L)


def modes(case, tld):
    M, C, K, *_ = td.system(tld=tld, **kw(case))
    w2 = np.linalg.eigvals(np.linalg.solve(M, K)).real
    return np.sqrt(np.sort(w2[w2 > 0])) / (2 * math.pi)


def peak(case, tld):
    v = td.sweep(tld, **kw(case))
    i = v[:, 1].argmax()
    return float(v[i, 1]), float(v[i, 0])


def main():
    out = {}
    cases = light_cases()
    out["cases"] = {c[0]: dict(rpm=c[3], R=c[4], T_MN=c[5], L=c[6]) for c in cases}
    for case in cases:
        name = case[0]
        x_att = None if name == "610" else 9.0
        k = kw(case, x_att)
        f0 = modes(case, None) if name != "610" else None
        sw0 = td.sweep(None, **k)
        sw1 = td.sweep([POOL], **k)
        p0, p1 = sw0[:, 1].max(), sw1[:, 1].max()
        f_pool, d_pool = td.tld_freq(POOL["m_t"], POOL["x"], POOL["a"])
        print(f"{name}: modes sans bassin {np.round(modes(case, []), 3)} Hz ; pic sans bassin {p0:.2f}° à {sw0[sw0[:, 1].argmax(), 0]:.3f} Hz, "
              f"avec bassin {p1:.2f}° à {sw1[sw1[:, 1].argmax(), 0]:.3f} Hz", flush=True)
        best = None
        for m, a, z in itertools.product((15.0, 25.0, 35.0), np.arange(3.0, 4.41, 0.2), (0.1, 0.15, 0.2, 0.3)):
            T = dict(m_t=m, x=12.0, a=float(a), zeta=z)
            v = td.sweep([T], **k)
            pk = float(v[:, 1].max())
            if best is None or pk < best[0]:
                best = (pk, m, float(a), z, m * 1e3 / (1000 * math.pi * a * a))
        print(f"   bassin réaccordé : {best[1]:g} t, Ø {2 * best[2]:.1f} m, profondeur {best[4]:.2f} m, ζ {best[3]:g} → pic {best[0]:.2f}°", flush=True)
        out[name] = dict(modes=[float(v) for v in modes(case, [])], peak_none=float(p0), peak_pool=float(p1),
                         sweep_none=sw0.tolist(), sweep_pool=sw1.tolist(), best=best)
        if name in SIM_POOL:
            v = td.sweep([SIM_POOL[name]], **k)
            out[name]["peak_sim_pool"] = float(v[:, 1].max())
            print(f"   bassin simulé {SIM_POOL[name]} → pic {out[name]['peak_sim_pool']:.2f}°", flush=True)
    with open(os.path.join(HERE, "out", "light_tld.json"), "w") as fh:
        json.dump(out, fh)


if __name__ == "__main__":
    main()
