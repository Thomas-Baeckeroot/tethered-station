#!/usr/bin/env python3
"""
Mode couplé du LOX (≈ 0,26 Hz), pic restant avec le bassin de 25 t : pic
hors plan du modèle linéaire (tld_design.py) avec des chicanes plus
efficaces, ou avec un second bassin accordé sur ce mode.

    .venv/bin/python lox_search.py > out/lox_search.log   # résumé : out/lox_search.json
"""
import itertools
import json
import os

import numpy as np

import tld_design as td

HERE = os.path.dirname(os.path.abspath(__file__))
T1 = dict(m_t=25, x=12, a=3.6, zeta=0.15)  # bassin de la solution retenue


def peak(tld, **kw):
    v = td.sweep(tld, **kw)
    i = v[:, 1].argmax()
    return float(v[i, 1]), float(v[i, 0])


def main():
    out = {"ref": peak(T1)}
    print("bassin seul, chicanes 3 % :", out["ref"], flush=True)
    for z in (0.05, 0.08, 0.12):
        out[f"chicanes_{z}"] = peak(T1, zeta_prop=z)
        print(f"chicanes {z:.0%} :", out[f"chicanes_{z}"], flush=True)
    best = None
    for m, x, a, z in itertools.product((8, 15, 25), (12, 30, 46), np.arange(1.2, 3.01, 0.2), (0.1, 0.2)):
        T2 = dict(m_t=m, x=x, a=float(a), zeta=z)
        pk, f = peak([T1, T2])
        f2, d2 = td.tld_freq(m, x, float(a))
        print(f"second bassin {m} t à {x} m, Ø {2 * a:.1f} m, profondeur {d2:.2f} m, accord {f2:.3f} Hz, ζ {z} → pic {pk:.3f}° à {f:.3f} Hz", flush=True)
        if best is None or pk < best[0]:
            best = (pk, m, x, float(a), z, f2, d2)
    out["best"] = best
    print("meilleur :", best)
    with open(os.path.join(HERE, "out", "lox_search.json"), "w") as fh:
        json.dump(out, fh)


if __name__ == "__main__":
    main()
