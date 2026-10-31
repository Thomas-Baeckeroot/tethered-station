#!/usr/bin/env python3
"""
Thermique d'un câble, station face au Soleil (carnet § 2.3 et § 7.5).

L'axe de rotation suit le Soleil : les câbles, dans le plan de rotation, sont
éclairés de côté en permanence, toujours sur la même face. Température d'équilibre
(câble isotherme), constante de temps, puis écart entre la face éclairée et la
face à l'ombre (conduction 2D dans la section, rayonnement en surface) et
l'écart d'allongement qui en résulte (dilatation négative du Dyneema).

    .venv/bin/python cable_thermal.py > out/cable_thermal.log
"""
import math

import numpy as np

SIGMA = 5.670374e-8
S1 = 1361.0                 # W/m², 1 UA
R_MARS = 1.52368            # UA
D = 0.12                    # m, câble tressé gainé (12 à 13 cm selon la redondance)
M_L = 24e3 / (3 * 538.6)    # kg/m, Dyneema SK99 redondant, gaine comprise
C_P = 1200.0                # J/kg/K, polyéthylène vers 200 K
CTE = -12e-6                # 1/K, dilatation axiale du Dyneema
EPS_LOAD = 0.0011           # allongement de la fibre en route (≈ 3,1 % de la rupture, 3,5 % à rupture)
SHEATHS = {"blanche": (0.20, 0.90), "métallisée nue": (0.10, 0.05)}   # (α, ε)


def t_iso(alpha, eps, S):
    """Câble isotherme éclairé de côté : α S D absorbé, ε σ T⁴ π D émis."""
    return (alpha * S / (math.pi * eps * SIGMA)) ** 0.25


def section(k, alpha=0.20, eps=0.90, S=S1, foil=None, nr=20, nt=72, tol=1e-4):
    """Section circulaire en volumes finis (r, θ), Soleil en θ = 0. foil = (k, épaisseur) :
    feuille conductrice sous la peinture, qui répartit la chaleur sur le pourtour.
    Renvoie les températures de surface (K) par angle."""
    R = D / 2
    dr, dth = R / nr, 2 * math.pi / nt
    r = (np.arange(nr) + 0.5) * dr
    th = np.arange(nt) * dth
    q_in = alpha * S * np.maximum(np.cos(th), 0.0)
    T = np.full((nr, nt), t_iso(alpha, eps, S))
    g_foil = foil[0] * foil[1] / (R * dth) if foil else 0.0
    for _ in range(200000):
        err = 0.0
        for i in range(nr):
            a_out = k * (r[i] + dr / 2) * dth / dr if i < nr - 1 else 0.0
            a_in = k * (r[i] - dr / 2) * dth / dr if i > 0 else 0.0
            a_th = k * dr / (r[i] * dth)
            num = a_th * (np.roll(T[i], -1) + np.roll(T[i], 1))
            ap = a_in + a_out + 2 * a_th
            if i > 0:
                num = num + a_in * T[i - 1]
            if i < nr - 1:
                num = num + a_out * T[i + 1]
            else:   # surface : absorbé − émis (linéarisé autour de T), feuille conductrice
                h = 4 * eps * SIGMA * T[i] ** 3
                num = num + R * dth * (q_in - eps * SIGMA * T[i] ** 4 + h * T[i]) + g_foil * (np.roll(T[i], -1) + np.roll(T[i], 1))
                ap = ap + R * dth * h + 2 * g_foil
            new = num / ap
            err = max(err, float(np.abs(new - T[i]).max()))
            T[i] = new
        if err < tol:
            break
    return T[-1]


def main():
    c = lambda t: t - 273.15
    print("Câble isotherme, éclairé de côté :")
    for name, (a, e) in SHEATHS.items():
        print(f"  gaine {name} (α/ε = {a}/{e}) : {c(t_iso(a, e, S1)):+.0f} °C à 1 UA, {c(t_iso(a, e, S1 / R_MARS ** 2)):+.0f} °C près de Mars")
    T0 = t_iso(0.2, 0.9, S1)
    tau = M_L * C_P / (4 * 0.9 * SIGMA * T0 ** 3 * math.pi * D)
    print(f"  constante de temps (gaine blanche, {M_L:.1f} kg/m) : {tau / 3600:.1f} h")
    print(f"\nSection Ø {D * 100:.0f} cm, gaine blanche, face éclairée / face à l'ombre :")
    for k in (0.05, 0.1, 0.3):
        for S, where in ((S1, "1 UA"), (S1 / R_MARS ** 2, "Mars")):
            s = section(k, S=S)
            dT = s.max() - s.min()
            print(f"  k = {k:4.2f} W/m/K, {where} : {c(s.max()):+.0f} / {c(s.min()):+.0f} °C, écart {dT:.0f} K, "
                  f"écart d'allongement {abs(CTE) * dT * 100:.3f} % ({abs(CTE) * dT / EPS_LOAD * 100:.0f} % de l'allongement en route)")
    for t in (0.1e-3, 0.3e-3):
        s = section(0.1, foil=(200.0, t))
        m = 2700 * math.pi * D * t * 538.6
        print(f"  k = 0,1 + feuille d'aluminium {t * 1e3:.1f} mm ({m:.0f} kg par câble) : {c(s.max()):+.0f} / {c(s.min()):+.0f} °C, écart {s.max() - s.min():.0f} K")


if __name__ == "__main__":
    main()
