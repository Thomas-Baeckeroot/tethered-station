#!/usr/bin/env python3
"""
Modes hors plan d'un Starship suspendu par son nez, avec ses pendules
d'ergols (modèle linéaire de Lagrange), pour vérifier les pics de réponse des
balayages du simulateur.

Coordonnées : position latérale y de l'attache (presque libre : seule la
raideur géométrique 2T/L des deux câbles la retient), inclinaison θ du
vaisseau, angles φ_i des pendules. Chaque élément de masse situé à la
distance s sous l'attache ressent l'accélération centrifuge ω²(r_a + s) le
long du vaisseau, d'où une raideur m·ω²(r_a + s)·s en inclinaison.
"""
import math

import numpy as np
import scipy.linalg as la

import tether_sim as ts

OMEGA = 2 * math.pi / 60
R_TOT = 3.711 / OMEGA ** 2   # rayon du centre de masse des vaisseaux
H = 25.0                     # attache → centre de masse total
T_CABLE, L_CABLE = 1.31e6, 539.0


def modes(free, mass_t=610):
    sm = ts.starship_mass_model(mass_t, slosh=free)
    x_att = sm["x_tot"] - H
    hr = sm["x_c"] - x_att
    Mr, Ir = sm["M_rigid"], sm["I_tr"]
    ra = R_TOT - H
    pend = [(t["ms"], t["x_hinge"] - x_att, t["L"]) for t in sm["pendulums"]]
    n = 2 + len(pend)
    M = np.zeros((n, n))
    K = np.zeros((n, n))
    M[0, 0], M[0, 1], M[1, 0], M[1, 1] = Mr, Mr * hr, Mr * hr, Mr * hr ** 2 + Ir
    K[0, 0] = 2 * T_CABLE / L_CABLE
    K[1, 1] = OMEGA ** 2 * (ra * Mr * hr + Ir + Mr * hr ** 2)
    for i, (m, l, L) in enumerate(pend):
        v = np.zeros(n)
        v[0], v[1], v[2 + i] = 1.0, l, L          # déplacement latéral de la masse
        M += m * np.outer(v, v)
        K[1, 1] += m * OMEGA ** 2 * (ra + l) * l   # poids ramené à l'articulation
        K[2 + i, 2 + i] += m * OMEGA ** 2 * (ra + l + L) * L
    return [math.sqrt(max(e, 0.0)) / (2 * math.pi) for e in la.eigh(K, M, eigvals_only=True)]


if __name__ == "__main__":
    print("ergols figés :", ", ".join(f"{f:.3f} Hz" for f in modes(False)))
    print("ergols libres:", ", ".join(f"{f:.3f} Hz" for f in modes(True)))
