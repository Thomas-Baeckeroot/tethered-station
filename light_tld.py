#!/usr/bin/env python3
"""
Vaisseau habité allégé (§ 5.5) : modes hors plan et pic du balayage hors
plan, avec le bassin de la solution retenue (25 t, Ø 7,2 m, 12 m de la
pointe) ou un bassin réaccordé, sur le modèle linéaire de tld_design.py.

Paramètres de chaque cas (masse, lest, vitesse, rayon, tension et longueur
des câbles du vaisseau habité) : équilibres du simulateur (campagne allege,
relaxation). Le modèle linéaire majore de 15 à 50 % (pas d'amortissement des
câbles) : il sert à comparer et à choisir le bassin ; le simulateur tranche.

    .venv/bin/python light_tld.py > out/light_tld.log   # résumé : out/light_tld.json
"""
import itertools
import json
import math
import os

import numpy as np

import tld_design as td

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = dict(m_t=25.0, x=12.0, a=3.6, zeta=0.15)
# Bassins réaccordés simulés (campagnes allege et masses, scénarios *_bassin)
SIM_POOL = {"K100": dict(m_t=15.0, x=12.0, a=3.4, zeta=0.2), "K195": dict(m_t=35.0, x=12.0, a=4.4, zeta=0.2),
            "K300": dict(m_t=25.0, x=12.0, a=4.4, zeta=0.3), "U390": dict(m_t=19.0, x=12.0, a=4.4, zeta=0.15),
            "KL50": dict(m_t=25.0, x=12.0, a=4.4, zeta=0.3)}
# (nom, masse t, lest, tr/min, rayon du vaisseau habité m, tension MN, longueur sous charge m)
CASES = (
    ("610", 610.0, None, 1.0, 338.4, 1.31, 539.0),
    ("K100", 510.0, None, 0.9614, 366.1, 1.09, 540.85),
    ("K195", 415.0, None, 0.9285, 392.6, 0.89, 543.21),
    ("K300", 310.0, None, 0.8959, 421.6, 0.66, 547.71),
    ("U390", 220.0, None, 0.8705, 446.6, 0.47, 548.35),
    ("KL50", 220.0, dict(m_t=50.0, x=44.0), 0.8705, 446.6, 0.47, 548.35),
)


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
    for case in CASES:
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
