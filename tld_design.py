#!/usr/bin/env python3
"""
Dimensionnement de l'amortisseur à liquide accordé (TLD) : modèle linéaire
hors plan de slosh_modes.py, avec amortissement, et réponse en fréquence de
l'inclinaison ressentie du plancher à une force latérale appliquée sur un
pont (4 t oscillantes, accélération limitée à 1 m/s², comme les balayages du
simulateur).

Comme dans le simulateur, la masse oscillante est ancrée au centre de masse
de la partie rigide, et l'inclinaison ressentie est l'angle entre le
plancher et la force spécifique sur la structure : inclinaison du vaisseau +
accélération latérale de son centre de masse / gravité locale.

Le régime permanent n'a pas de sens ici (la structure n'est presque pas
amortie) : la réponse est calculée en temps, avec le même programme de
balayage que le simulateur (0,004 → 0,4 Hz en 5 400 s, ±3,5 m, ≤ 1 m/s²).

Usage : tld_design.py [--json docs/data/tld.json]
"""
import argparse
import json
import math

import numpy as np

import tether_sim as ts
from slosh_modes import OMEGA, R_TOT, H, T_CABLE, L_CABLE

import scipy.linalg as sla

M_INT = 4e3
SWEEP = dict(amp=3.5, f1=0.4, duration=5460.0)


def system(mass_t=610, free=True, zeta_prop=0.03, tld=None, omega=OMEGA, R_tot=R_TOT, x_att=None,
           T_cable=T_CABLE, L_cable=L_CABLE, ballast=None):
    """Matrices M, C, K, vecteur de force et ligne d'observation du plancher.
    Par défaut, la solution retenue (610 t, attaches à H = 25 m au-dessus du
    centre de masse) ; sinon vaisseau de mass_t (lest éventuel), attaches à
    x_att de la pointe, centre de masse au rayon R_tot, câbles de tension
    T_cable et de longueur L_cable, vitesse omega (masses inégales, § 5.5)."""
    OMEGA = omega
    sm = ts.starship_mass_model(mass_t, slosh=free, tld=tld, ballast=ballast)
    if x_att is None:
        x_att = sm["x_tot"] - H
    hr = sm["x_c"] - x_att
    Mr, Ir = sm["M_rigid"], sm["I_tr"]
    ra = R_tot - (sm["x_tot"] - x_att)
    pend = sm["pendulums"]
    n = 2 + len(pend)
    M, K, C = np.zeros((n, n)), np.zeros((n, n)), np.zeros((n, n))
    M[0, 0], M[0, 1], M[1, 0], M[1, 1] = Mr, Mr * hr, Mr * hr, Mr * hr ** 2 + Ir
    K[0, 0] = 2 * T_cable / L_cable
    K[1, 1] = OMEGA ** 2 * (ra * Mr * hr + Ir + Mr * hr ** 2)
    for i, t in enumerate(pend):
        m, l, L = t["ms"], t["x_hinge"] - x_att, t["L"]
        v = np.zeros(n)
        v[0], v[1], v[2 + i] = 1.0, l, L
        M += m * np.outer(v, v)
        K[1, 1] += m * OMEGA ** 2 * (ra + l) * l
        K[2 + i, 2 + i] += m * OMEGA ** 2 * (ra + l + L) * L
        ws = math.sqrt(OMEGA ** 2 * (ra + l + L) / L)
        # amortisseur sur la vitesse latérale relative à la paroi : L·(φ̇ − θ̇)
        dv = np.zeros(n)
        dv[1], dv[2 + i] = -L, L
        C += 2 * t.get("zeta", zeta_prop) * ws * m * np.outer(dv, dv)
    s_d = hr
    f = np.zeros(n)
    f[0], f[1] = 1.0, s_d
    g_d = OMEGA ** 2 * (ra + s_d)
    return M, C, K, f, s_d, g_d, sm


def sweep(tld=None, dt=0.1, **kw):
    """Balayage en temps : renvoie (fréquences, pic glissant de
    l'inclinaison ressentie en °), comme sweep_response de make_web_data."""
    M, C, K, f, s_d, g_d, _ = system(tld=tld, **kw)
    n = len(f)
    Mi = np.linalg.inv(M)
    A = np.block([[np.zeros((n, n)), np.eye(n)], [-Mi @ K, -Mi @ C]])
    # entrées : accélération de la masse interne (réaction −m·s̈ au point
    # d'ancrage) et son décalage s (couple −m·g·s sur l'inclinaison)
    Bf = np.concatenate([np.zeros(n), Mi @ (-M_INT * f)])
    e1 = np.zeros(n)
    e1[1] = 1.0
    Bs = np.concatenate([np.zeros(n), Mi @ (-M_INT * g_d * e1)])
    B = np.column_stack([Bf, Bs])
    E = sla.expm(np.block([[A, B], [np.zeros((2, 2 * n + 2))]]) * dt)
    Ph, Ga = E[:2 * n, :2 * n], E[:2 * n, 2 * n:]
    T = SWEEP["duration"]
    prog = ts.make_program("sweep", SWEEP["amp"], f1=SWEEP["f1"], t1=T - 60)
    t = np.arange(0, T, dt)
    sv = np.array([prog(x) for x in t])
    acc = np.gradient(np.gradient(sv, dt), dt)
    x = np.zeros(2 * n)
    tilt = np.empty(len(t))
    for k in range(len(t)):
        q, qd = x[:n], x[n:]
        qdd = Mi @ (-K @ q - C @ qd - M_INT * acc[k] * f - M_INT * g_d * sv[k] * e1)
        tilt[k] = abs(q[1] + (qdd[0] + s_d * qdd[1]) / g_d)
        x = Ph @ x + Ga @ np.array([acc[k], sv[k]])
    tilt = np.degrees(tilt)
    out = []
    f0, f1, t0, t1 = 0.004, SWEEP["f1"], 60.0, T - 60
    # fenêtres contiguës, comme sweep_response de make_web_data
    fs = np.geomspace(f0 * 1.05, f1 * 0.98, 120)
    tc = t0 + (fs - f0) / (f1 - f0) * (t1 - t0)
    edges = np.concatenate([[tc[0]], (tc[1:] + tc[:-1]) / 2, [tc[-1]]])
    for k, fr in enumerate(fs):
        half = 0.75 / fr
        m = (t > min(edges[k], tc[k] - half)) & (t < max(edges[k + 1], tc[k] + half))
        out.append([fr, tilt[m].max()])
    return np.array(out)


def tld_freq(m_t, x, a):
    """Fréquence propre (réservoir fixe) du bassin : gravité locale le long de l'axe."""
    tk = ts.slosh_tank(m_t * 1e3, m_t * 1e3 / (1000 * math.pi * a * a), a)
    sm = ts.starship_mass_model(610)
    r = R_TOT + (x - tk["hb"] - sm["x_tot"])
    return math.sqrt(OMEGA ** 2 * r / tk["L"]) / (2 * math.pi), m_t * 1e3 / (1000 * math.pi * a * a)


def search(x_list=(12.0, 20.0, 46.0), m_list=(25.0, 50.0, 75.0), a_list=np.arange(2.0, 4.41, 0.2),
           z_list=(0.05, 0.08, 0.12, 0.16, 0.20, 0.25, 0.30)):
    """Pour chaque emplacement et masse d'eau : rayon (donc accord) et
    amortissement minimisant le pic du balayage hors plan."""
    rows = []
    for x in x_list:
        for m in m_list:
            best = None
            for a in a_list:
                for z in z_list:
                    pk = sweep(dict(m_t=m, x=x, a=float(a), zeta=z))[:, 1].max()
                    if best is None or pk < best[0]:
                        best = (pk, float(a), z)
            pk, a, z = best
            f, d = tld_freq(m, x, a)
            rows.append(dict(x=x, m_t=m, a=a, zeta=z, depth=d, f=f, peak=float(pk)))
            print(f"bassin à {x:4.0f} m, {m:3.0f} t : Ø {2 * a:3.1f} m, profondeur {d:4.2f} m, accord {f:.3f} Hz, ζ {z:.2f} → pic {pk:.2f}°", flush=True)
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", help="écrit la recherche et les courbes de balayage")
    args = p.parse_args()
    ref = {k: sweep(**kw) for k, kw in (("figés", dict(free=False)), ("chicanes", {}), ("libres", dict(zeta_prop=0.001)))}
    for k, v in ref.items():
        i = v[:, 1].argmax()
        print(f"sans amortisseur, ergols {k} : pic {v[i, 1]:.2f}° à {v[i, 0]:.3f} Hz")
    rows = search()
    if args.json:
        json.dump(dict(ref={k: v.tolist() for k, v in ref.items()}, search=rows), open(args.json, "w"))


if __name__ == "__main__":
    main()
