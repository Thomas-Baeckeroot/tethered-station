#!/usr/bin/env python3
"""
Masse d'un Starship après l'injection vers Mars (transfert de Hohmann).

Hypothèses :
- orbites de la Terre et de Mars circulaires et coplanaires (Hohmann idéal :
  vitesse d'excès hyperbolique minimale ; une fenêtre réelle demande un peu
  plus, d'où la plage de sensibilité) ;
- départ d'une orbite basse circulaire, vaisseau plein : 1 600 t au total
  (structure + charge + ergols) ;
- poussée des 3 Raptor Vacuum (Isp 380 s, 3 × 2,6 MN), dirigée selon la
  vitesse ; la poussée finie est intégrée numériquement (pertes par gravité),
  et comparée à l'impulsion idéale (équation de Tsiolkovski).

Sortie : tableau à l'écran et docs/data/mission.json pour les pages.
"""
import json
import math
import os

import numpy as np
from scipy.integrate import solve_ivp

G0 = 9.80665
MU_SUN = 1.32712440018e20       # m³/s²
MU_EARTH = 3.986004418e14       # m³/s²
R_EARTH = 6378.137e3            # m, rayon équatorial
R_EARTH_ORBIT = 149.598e9       # m, demi-grand axe (fiche NASA)
R_MARS_ORBIT = 227.956e9        # m, demi-grand axe (fiche NASA)
MU_MARS = 4.2828e13             # m³/s²
DAY = 86400.0

M0 = 1600e3                     # kg, vaisseau plein en orbite basse
ISP = 380.0                     # s, Raptor Vacuum
THRUST = 3 * 2.6e6              # N, 3 Raptor Vacuum


def hohmann():
    """Vitesses d'excès hyperbolique au départ et à l'arrivée, durée du transfert."""
    r1, r2 = R_EARTH_ORBIT, R_MARS_ORBIT
    a = (r1 + r2) / 2
    v1, v2 = math.sqrt(MU_SUN / r1), math.sqrt(MU_SUN / r2)
    vp = math.sqrt(MU_SUN * (2 / r1 - 1 / a))
    va = math.sqrt(MU_SUN * (2 / r2 - 1 / a))
    return dict(v_inf_depart=vp - v1, v_inf_arrivee=v2 - va, duree_j=math.pi * math.sqrt(a ** 3 / MU_SUN) / DAY)


def impulsive_dv(alt, v_inf):
    """Δv impulsionnel depuis une orbite circulaire d'altitude donnée."""
    r = R_EARTH + alt
    return math.sqrt(v_inf ** 2 + 2 * MU_EARTH / r) - math.sqrt(MU_EARTH / r)


def finite_burn(alt, v_inf, isp=ISP, thrust=THRUST, m0=M0):
    """Intègre la poussée (dirigée selon la vitesse) jusqu'à l'énergie visée.
    Renvoie la masse finale, la durée de combustion et le Δv dépensé."""
    r0 = R_EARTH + alt
    v0 = math.sqrt(MU_EARTH / r0)
    eps_target = v_inf ** 2 / 2
    mdot = thrust / (G0 * isp)

    def f(t, y):
        x, yy, vx, vy, m = y
        r = math.hypot(x, yy)
        v = math.hypot(vx, vy)
        a = thrust / m
        return [vx, vy, -MU_EARTH * x / r ** 3 + a * vx / v, -MU_EARTH * yy / r ** 3 + a * vy / v, -mdot]

    def reached(t, y):
        return (y[2] ** 2 + y[3] ** 2) / 2 - MU_EARTH / math.hypot(y[0], y[1]) - eps_target
    reached.terminal = True

    sol = solve_ivp(f, (0, 5000), [r0, 0.0, 0.0, v0, m0], events=reached, rtol=1e-10, atol=1e-6, max_step=1.0)
    t_b = sol.t_events[0][0]
    m_f = sol.y_events[0][0][4]
    return dict(m_final=m_f, duree_s=t_b, dv=G0 * isp * math.log(m0 / m_f))


def main():
    h = hohmann()
    v_inf = h["v_inf_depart"]
    print(f"Hohmann Terre → Mars : v∞ départ {v_inf / 1e3:.3f} km/s, v∞ arrivée {h['v_inf_arrivee'] / 1e3:.3f} km/s, "
          f"durée {h['duree_j']:.0f} jours")
    rows = []
    for alt in (200e3, 400e3, 1600e3):
        dv = impulsive_dv(alt, v_inf)
        m_imp = M0 * math.exp(-dv / (G0 * ISP))
        fb = finite_burn(alt, v_inf)
        rows.append(dict(alt_km=alt / 1e3, dv_impulsionnel=dv, m_impulsionnel_t=m_imp / 1e3, m_final_t=fb["m_final"] / 1e3,
                         dv_reel=fb["dv"], perte_gravite=fb["dv"] - dv, duree_s=fb["duree_s"]))
        print(f"  orbite {alt / 1e3:5.0f} km : Δv idéal {dv:6.0f} m/s → {m_imp / 1e3:5.0f} t ; poussée finie "
              f"{fb['dv']:6.0f} m/s (pertes {fb['dv'] - dv:3.0f} m/s, {fb['duree_s']:.0f} s) → {fb['m_final'] / 1e3:5.0f} t")

    # Sensibilité (orbite de 400 km) : impulsion spécifique, fenêtre de tir réelle
    sens = []
    for label, isp, vi in (("Isp 380 s (Raptor Vacuum)", 380, v_inf),
                           ("Isp 365 s (6 moteurs)", 365, v_inf),
                           ("v∞ 3,5 km/s (fenêtre moyenne)", 380, 3500.0),
                           ("v∞ 4,0 km/s (fenêtre défavorable)", 380, 4000.0)):
        fb = finite_burn(400e3, vi, isp=isp)
        sens.append(dict(cas=label, isp=isp, v_inf=vi, m_final_t=fb["m_final"] / 1e3))
        print(f"  sensibilité : {label:34s} → {fb['m_final'] / 1e3:5.0f} t")

    out = dict(m0_t=M0 / 1e3, isp=ISP, poussee_MN=THRUST / 1e6, hohmann=h, orbites=rows, sensibilite=sens)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "data", "mission.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    print(f"→ {path}")


if __name__ == "__main__":
    main()
