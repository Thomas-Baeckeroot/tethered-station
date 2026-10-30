#!/usr/bin/env python3
"""
Orientation de la station par rapport au Soleil pendant le transfert
Terre → Mars, et ce qu'elle change pour les ergols cryogéniques.

Deux orientations de l'axe de rotation :
- A, « face au Soleil » : l'axe suit le Soleil ; il tourne de 180° pendant le
  transfert (anomalie vraie de 0 à 180°). Le Soleil éclaire toujours le même
  côté de chaque vaisseau : panneaux fixes, qui font aussi écran, et un côté
  à l'ombre en permanence ;
- B, « axe fixe » : axe perpendiculaire au plan de l'orbite ; aucun ergol
  pour l'orienter, mais le Soleil, dans le plan de rotation, fait le tour de
  chaque vaisseau une fois par minute (panneaux sur joints tournants).

Calculs :
1. orbite de transfert : direction du Soleil au cours du temps, vitesse de
   rotation nécessaire, écart d'un programme à vitesse constante ;
2. impulsion pour faire tourner l'axe (précession gyroscopique) : poussée
   sinusoïdale de chaque vaisseau, ou impulsions au passage de la ligne des
   nœuds ; masse d'ergols selon les propulseurs ;
3. bilan thermique des réservoirs (modèle 2D par éléments de coque, moyenné
   sur la rotation) : fuite de chaleur, ergols évaporés sur le voyage, pour
   plusieurs revêtements ; fourchette basse / centrale / haute.

Ordres de grandeur seulement : l'isolation réelle d'un Starship vers Mars
n'est pas publiée. Toute la chaleur entrante est comptée comme évaporation
(majorant : une partie réchauffe seulement le gaz du ciel du réservoir).

    .venv/bin/python sun_pointing.py        # tableau à l'écran, docs/data/soleil.json
"""
import json
import math
import os

import numpy as np

from tether_sim import G0, starship_mass_model

AU = 149.598e9
R_EARTH_ORBIT = 1.0             # UA
R_MARS_ORBIT = 1.52368          # UA
YEAR_D = 365.25636
DAY = 86400.0
S0 = 1361.0                     # W/m², constante solaire à 1 UA
SIGMA = 5.670374e-8

# Station (solution retenue)
M_SHIP = 610e3                  # kg
R_SHIP = 338.4                  # m, rayon des centres de masse des vaisseaux
RPM = 1.0
CABLE_T = 14.0                  # t, trois câbles
H_ATT = 25.0                    # m, attaches au-dessus du centre de masse

# Coque : réservoirs de 9 m de diamètre, CH4 de 22 à 35 m de la pointe, LOX
# de 35 à 46 m (tether_sim.SHIP_TANKS)
R_HULL = 4.5
TANKS = (("CH4", 22.0, 35.0), ("LOX", 35.0, 46.0))
PROP = {tk["name"]: tk["m"] for tk in starship_mass_model(610.0)["tanks"]}   # kg par réservoir
T_LIQ = {"LOX": 95.0, "CH4": 120.0}     # K, saturation vers 1,5–2 bar
H_FG = {"LOX": 210e3, "CH4": 505e3}     # J/kg, chaleur de vaporisation
DOME = math.pi * R_HULL ** 2 * 1.3      # m², dôme (bombé)


# --- 1. Orbite de transfert ----------------------------------------------------
def transfer():
    """Demi-ellipse de Hohmann : temps (jours), anomalie vraie, distance (UA)."""
    a = (R_EARTH_ORBIT + R_MARS_ORBIT) / 2
    e = (R_MARS_ORBIT - R_EARTH_ORBIT) / (R_MARS_ORBIT + R_EARTH_ORBIT)
    n = 2 * math.pi / (YEAR_D * a ** 1.5)          # rad/jour
    nu = np.linspace(0.0, math.pi, 3601)
    E = 2 * np.arctan(np.sqrt((1 - e) / (1 + e)) * np.tan(nu / 2))
    E[-1] = math.pi
    t = (E - e * np.sin(E)) / n
    r = a * (1 - e * e) / (1 + e * np.cos(nu))
    return dict(a=a, e=e, t=t, nu=nu, r=r, T_half=float(t[-1]))


def schedule_error(tr):
    """Écart entre la direction du Soleil et un axe qui tourne à vitesse
    constante (180° en T_half), le meilleur décalage de départ choisi."""
    lin = math.pi * tr["t"] / tr["T_half"]
    err = tr["nu"] - lin
    off = (err.max() + err.min()) / 2
    return float(np.degrees(err.max() - off)), float(np.degrees(off))


# --- 2. Impulsion pour faire tourner l'axe ---------------------------------------
def station_L():
    """Moment cinétique de la station autour de son axe."""
    w = RPM * 2 * math.pi / 60
    sh = starship_mass_model(M_SHIP / 1e3)
    pend = sum(tk["ms"] * (tk["x_bob"] - sh["x_tot"]) ** 2 for tk in sh["pendulums"])
    I_own = sh["I_tr"] + sh["M_rigid"] * (sh["x_c"] - sh["x_tot"]) ** 2 + pend
    # câbles : chaque côté relie les nez (rayon R − h) ; r² moyen le long de la corde
    ra = R_SHIP - H_ATT
    d, half = ra * math.cos(math.pi / 3), ra * math.sin(math.pi / 3)
    I_cab = CABLE_T * 1e3 * (d * d + half * half / 3)
    I = 3 * (M_SHIP * R_SHIP ** 2 + I_own) + I_cab
    return dict(omega=w, I=I, L=I * w, I_own_frac=3 * I_own / I, I_cab_frac=I_cab / I)


def precession_impulse(L, dtheta, mode="sinus", half_width_deg=15.0):
    """Impulsion totale (somme des |F| dt) pour faire tourner le moment
    cinétique L de dtheta, par des poussées perpendiculaires au plan de
    rotation, au centre de masse des vaisseaux (bras R_SHIP).

    - « sinus » : chaque vaisseau pousse en continu, F ∝ cos ψ (ψ : angle à la
      ligne des nœuds), solution de moindre norme quadratique : J = (4/π)·Δθ·L/R ;
    - « noeuds » : chaque vaisseau ne pousse qu'à ±δ de la ligne des nœuds
      (axe autour duquel le plan tourne), force constante : J = Δθ·L/R · δ/sin δ.
      À la limite δ → 0 : changement de plan au nœud, J = Δθ·L/R."""
    base = dtheta * L / R_SHIP
    if mode == "sinus":
        return 4 / math.pi * base
    d = math.radians(half_width_deg)
    return base * d / math.sin(d)


THRUSTERS = (  # (nom, Isp s)
    ("gaz froid, oxygène des réservoirs", 65.0),
    ("gaz froid, méthane des réservoirs", 110.0),
    ("gaz chauds (méthane + oxygène brûlés)", 300.0),
)


# --- 3. Bilan thermique ---------------------------------------------------------
def view_strip(p, n, y0, y1, zs):
    """Facteur de forme 2D d'un élément (position p, normale n, dans le plan
    (y, z) de la section) vers une bande y0 < y < y1 à la hauteur zs, coque
    convexe (le plan tangent suffit pour l'auto-occultation)."""
    def ang(q):
        d = q - p
        return math.atan2(n[0] * d[1] - n[1] * d[0], n @ d)
    a0, a1 = ang(np.array([y0, zs])), ang(np.array([y1, zs]))
    a0, a1 = max(-math.pi / 2, min(math.pi / 2, a0)), max(-math.pi / 2, min(math.pi / 2, a1))
    return abs(math.sin(a1) - math.sin(a0)) / 2


def solve_surface(Qa, eps, path, Ti, P):
    """Température extérieure To et flux entrant q (W/m²) d'un élément de
    coque : Qa = ε σ To⁴ + q. Chemins : « mli » q = ε* σ (To⁴ − Ti⁴) ;
    « tuile » q = U (To − Ti) ; « nu » : paroi du réservoir, To = Ti."""
    if path == "nu":
        return Ti, Qa - eps * SIGMA * Ti ** 4
    def q(To):
        return P["eps_mli"] * SIGMA * (To ** 4 - Ti ** 4) if path == "mli" else P["U_tile"] * (To - Ti)
    lo, hi = 1.0, 600.0
    for _ in range(80):
        To = (lo + hi) / 2
        if eps * SIGMA * To ** 4 + q(To) > Qa:
            hi = To
        else:
            lo = To
    return To, q(To)


COVERS = {  # revêtement extérieur : (α solaire, ε infrarouge, chemin)
    "acier": (0.40, 0.12, "nu"),          # acier inoxydable nu du Starship
    "mli": (0.12, 0.80, "mli"),           # isolant multicouche, voile extérieur argenté (fin de vie)
    "tuile": (0.85, 0.85, "tuile"),       # tuiles noires du bouclier thermique
}

# Panneaux solaires : bandes (y0, y1, z) dans la section, face arrière vers −z.
# « loin » : sur des mâts, hors de vue de la coque ; « ailes » : de part et
# d'autre de la coque, un peu au-dessus de son axe ; « ecran » : devant la
# coque côté Soleil, qu'ils ombragent.
PANELS = {
    "loin": (),
    "ailes": ((5.5, 17.5, 1.0), (-17.5, -5.5, 1.0)),
    "ecran": ((-6.5, 6.5, 8.0),),
}

CONFIGS = (  # (clé, libellé, orientation, côté sans tuiles, tuiles, panneaux, voiles derrière les panneaux)
    ("B_nu", "B · axe fixe, coque telle quelle (acier nu, tuiles)", "B", "acier", "tuile", "loin", 0),
    ("B_mli", "B · axe fixe, isolant sur l'acier, tuiles exposées", "B", "mli", "tuile", "loin", 0),
    ("B_mli_tout", "B · axe fixe, isolant partout (housse sur les tuiles)", "B", "mli", "mli", "loin", 0),
    ("A_nu", "A · face au Soleil, acier nu côté Soleil, tuiles à l'ombre", "A", "acier", "tuile", "loin", 0),
    ("A_mli", "A · face au Soleil, isolant côté Soleil, tuiles à l'ombre", "A", "mli", "tuile", "loin", 0),
    ("A_ailes0", "A · idem, panneaux en ailes, dos noir", "A", "mli", "tuile", "ailes", 0),
    ("A_ailes1", "A · idem, panneaux en ailes, un voile derrière", "A", "mli", "tuile", "ailes", 1),
    ("A_ecran0", "A · panneaux devant la coque, dos noir, isolant", "A", "mli", "tuile", "ecran", 0),
    ("A_ecran2", "A · panneaux devant la coque + 2 voiles, acier nu", "A", "acier", "tuile", "ecran", 2),
)

PARAMS = {  # fourchette basse / centrale / haute ; « fuite » : part du flux des voiles qui atteint la coque
    "bas": dict(eps_mli=0.002, U_tile=0.1, fuite=0.3, Q_pen=50.0, T_bay_B=230.0, T_bay_A=150.0),
    "central": dict(eps_mli=0.004, U_tile=0.3, fuite=0.6, Q_pen=150.0, T_bay_B=260.0, T_bay_A=170.0),
    "haut": dict(eps_mli=0.008, U_tile=0.6, fuite=1.0, Q_pen=300.0, T_bay_B=290.0, T_bay_A=200.0),
}
T_CABIN = 293.0                 # K, soute habitée au-dessus du dôme du CH4 (vaisseau habité)
NB = 144                        # éléments sur le pourtour


def hull_heat(cfg, S, P, crew=True, T_liq=None, tilt_deg=0.0):
    """Chaleur entrant dans chaque réservoir (W), moyenne sur une rotation,
    pour un flux solaire S (W/m²). Repère de la section : y tangentiel (dans
    le plan de rotation), z selon l'axe de rotation ; le Soleil est en +z
    (orientation A) ou tourne dans le plan (x, y) (orientation B). Tuiles :
    demi-circonférence centrée sur −z (côté opposé au Soleil en A)."""
    T_liq = T_liq or T_LIQ
    _, _, orient, side, tiles, panels, layers = cfg
    E_back = shade_flux(S, layers) * (P["fuite"] if layers else 1.0)
    beta = (np.arange(NB) + 0.5) * 2 * math.pi / NB      # angle depuis +y
    heat = {}
    for tank, x0, x1 in TANKS:
        Ti, Q = T_liq[tank], 0.0
        dA = 2 * math.pi * R_HULL / NB * (x1 - x0)
        for b in beta:
            n = np.array([math.cos(b), math.sin(b)])
            p = R_HULL * n
            cover = tiles if n[1] < 0 else side
            alpha, eps, path = COVERS[cover]
            if orient == "B":
                Qa = alpha * S * abs(n[0]) / math.pi        # moyenne de max(0, n·s) sur un tour
            else:
                # axe écarté du Soleil de tilt_deg, dans le plan de la section
                # (cas le plus défavorable : le bord des tuiles s'éclaire)
                t = math.radians(tilt_deg)
                lit = max(0.0, n[0] * math.sin(t) + n[1] * math.cos(t))
                for y0, y1, zp in PANELS[panels]:
                    if zp > p[1] and abs(y0 + y1) < 1e-9 and y0 <= p[0] <= y1:
                        lit = 0.0                           # à l'ombre de l'écran
                Qa = alpha * S * lit
                Qa += eps * E_back * sum(view_strip(p, n, y0, y1, zp) for y0, y1, zp in PANELS[panels])
            _, q = solve_surface(Qa, eps, path, Ti, P)
            Q += q * dA
        heat[tank] = Q
    # Dômes : avant du CH4 (soute), arrière du LOX (baie des moteurs), sous isolant
    T_up = T_CABIN if crew else (P["T_bay_B"] if orient == "B" else P["T_bay_A"])
    T_bay = P["T_bay_B"] if orient == "B" else P["T_bay_A"]
    heat["CH4"] += DOME * P["eps_mli"] * SIGMA * (T_up ** 4 - T_liq["CH4"] ** 4)
    heat["LOX"] += DOME * P["eps_mli"] * SIGMA * (T_bay ** 4 - T_liq["LOX"] ** 4)
    # Supports, conduites, moteurs : moitié à chaque réservoir
    heat["CH4"] += P["Q_pen"] / 2
    heat["LOX"] += P["Q_pen"] / 2
    return heat


def boiloff(cfg, P, tr, crew=True, n_t=120):
    """Ergols évaporés sur le transfert (kg par réservoir), plafonnés à ce que
    contient le réservoir, et jour où le premier réservoir se vide (None s'il
    tient) ; une chaleur nette négative (refroidissement) n'évapore rien."""
    ts = np.linspace(0, tr["T_half"], n_t + 1)
    r = np.interp(ts, tr["t"], tr["r"])
    out = {"LOX": 0.0, "CH4": 0.0}
    empty = None
    for k in range(n_t):
        rm = (r[k] + r[k + 1]) / 2
        h = hull_heat(cfg, S0 / rm ** 2, P, crew)
        dt = (ts[k + 1] - ts[k]) * DAY
        for tank in out:
            dm = max(h[tank], 0.0) * dt / H_FG[tank]
            if out[tank] + dm >= PROP[tank] and empty is None:
                empty = ts[k] + (PROP[tank] - out[tank]) / dm * (ts[k + 1] - ts[k])
            out[tank] = min(PROP[tank], out[tank] + dm)
    q1 = hull_heat(cfg, S0 / R_EARTH_ORBIT ** 2, P, crew)
    q2 = hull_heat(cfg, S0 / R_MARS_ORBIT ** 2, P, crew)
    return out, q1, q2, empty


def shade_flux(S, layers, eps_v=0.05, eps_back=0.85, alpha=0.92, eps_front=0.85, eta=0.20):
    """Flux infrarouge émis vers la coque par la face arrière d'un écran :
    panneau solaire (rayonne des deux faces) suivi de voiles aluminisés
    parallèles, sans fuite par les bords (majorant). Renvoie W/m²."""
    if layers == 0:
        Tp = ((alpha - eta) * S / ((eps_front + eps_back) * SIGMA)) ** 0.25
        return eps_back * SIGMA * Tp ** 4
    # résistance radiative (par unité de σ) de la face arrière du panneau à l'espace
    Rch = (1 / eps_back + 1 / eps_v - 1) + (layers - 1) * (2 / eps_v - 1) + 1 / eps_v
    Tp = ((alpha - eta) * S / (eps_front * SIGMA)) ** 0.25          # dos presque isolé
    for _ in range(50):
        q = SIGMA * Tp ** 4 / Rch
        Tp = (((alpha - eta) * S - q) / (eps_front * SIGMA)) ** 0.25
    return SIGMA * Tp ** 4 / Rch


def main():
    tr = transfer()
    rate = np.degrees(np.gradient(tr["nu"], tr["t"]))
    err_lin, off_lin = schedule_error(tr)
    print(f"Transfert : a = {tr['a']:.4f} UA, e = {tr['e']:.4f}, durée {tr['T_half']:.1f} jours")
    print(f"  direction du Soleil : 180° ; {rate[0]:.3f}°/jour au départ, {rate[-1]:.3f}°/jour à l'arrivée, "
          f"{180 / tr['T_half']:.3f}°/jour en moyenne")
    print(f"  axe tournant à vitesse constante : écart max ±{err_lin:.1f}° (axe calé {off_lin:+.1f}° au départ)")
    for d in (30, 60, 90, 120, 150, 180, 210, 240):
        print(f"    jour {d:3d} : Soleil à {np.degrees(np.interp(d, tr['t'], tr['nu'])):5.1f}°, r = {np.interp(d, tr['t'], tr['r']):.3f} UA")

    st = station_L()
    v = st["omega"] * R_SHIP
    print(f"\nStation : I = {st['I']:.3e} kg·m² (vaisseaux autour de leur centre {st['I_own_frac']:.2%}, câbles "
          f"{st['I_cab_frac']:.2%}), L = {st['L']:.3e} N·m·s, v = {v:.1f} m/s")
    Om = math.pi / (tr["T_half"] * DAY)
    tau = Om * st["L"]
    print(f"  rotation moyenne de l'axe {Om:.3e} rad/s → couple {tau:.0f} N·m ; "
          f"force moyenne (sinus) {4 / math.pi * tau / R_SHIP:.1f} N au total")
    cases = []
    for label, dth, mode, hw in (("poussée continue (sinus), 180°", math.pi, "sinus", 0),
                                 ("impulsions aux nœuds ±15°, 180°", math.pi, "noeuds", 15.0),
                                 ("impulsions aux nœuds ±30°, 180°", math.pi, "noeuds", 30.0),
                                 ("impulsions aux nœuds ±15°, 160° (tolérance ±10°)", math.radians(160), "noeuds", 15.0)):
        J = precession_impulse(st["L"], dth, mode, hw)
        props = [J / (isp * G0) / 1e3 for _, isp in THRUSTERS]
        cases.append(dict(cas=label, J=J, ergols_t=props))
        print(f"  {label:50s} J = {J:.3e} N·s → " + ", ".join(f"{m:5.0f} t" for m in props) + " (gaz froid O2, CH4, gaz chauds)")
    # poussée d'un vaisseau pendant une impulsion aux nœuds (±15°)
    hw = math.radians(15.0)
    F_pulse = math.pi * tau / (6 * R_SHIP * math.sin(hw))
    dJ = F_pulse * (2 * hw / st["omega"])
    print(f"  impulsions ±15° : {F_pulse:.1f} N pendant {2 * hw / st['omega']:.1f} s, toutes les 30 s par vaisseau ({dJ:.0f} N·s)")

    print("\nÉcran : flux infrarouge vers la coque (W/m²), sans fuite par les bords")
    shade = {}
    for layers in (0, 1, 2, 3):
        a, b = shade_flux(S0, layers), shade_flux(S0 / R_MARS_ORBIT ** 2, layers)
        shade[layers] = (a, b)
        print(f"  panneau + {layers} voile(s) : {a:6.1f} à 1 UA, {b:6.1f} près de Mars")

    print("\nFuite de chaleur par vaisseau (kW, 1 UA → 1,52 UA) et ergols évaporés sur le voyage (t par vaisseau, habité / cargo)")
    res = {}
    for cfg in CONFIGS:
        key = cfg[0]
        res[key] = dict(libelle=cfg[1])
        line = f"  {cfg[1]:72s}"
        for pk, P in PARAMS.items():
            bo, q1, q2, empty = boiloff(cfg, P, tr, crew=True)
            boc, _, _, _ = boiloff(cfg, P, tr, crew=False)
            res[key][pk] = dict(q1_kW=(q1["LOX"] + q1["CH4"]) / 1e3, q2_kW=(q2["LOX"] + q2["CH4"]) / 1e3,
                                q1_tank={k: v / 1e3 for k, v in q1.items()},
                                habite_t=(bo["LOX"] + bo["CH4"]) / 1e3, vide_j=empty, cargo_t=(boc["LOX"] + boc["CH4"]) / 1e3,
                                total3_t=(bo["LOX"] + bo["CH4"] + 2 * (boc["LOX"] + boc["CH4"])) / 1e3)
            r_ = res[key][pk]
            line += f" | {pk}: {r_['q1_kW']:6.2f}→{r_['q2_kW']:6.2f} kW, {r_['habite_t']:4.0f}/{r_['cargo_t']:4.0f} t" + (f" (vide j{empty:.0f})" if empty else "")
        print(line)
    # Orientation A retenue : refroidissement net ; température d'équilibre de
    # chaque réservoir (réservoirs indépendants, sans échange par le dôme commun)
    eq = {}
    print("\nA · isolant côté Soleil, tuiles à l'ombre : chaleur nette par réservoir à la température nominale, équilibre")
    cfg = next(c for c in CONFIGS if c[0] == "A_mli")
    for pk, P in PARAMS.items():
        eq[pk] = {}
        for crew in (True, False):
            for dist in (R_EARTH_ORBIT, R_MARS_ORBIT):
                S = S0 / dist ** 2
                q = hull_heat(cfg, S, P, crew)
                Teq = {}
                for tank in ("LOX", "CH4"):
                    lo, hi = 20.0, 200.0
                    for _ in range(50):
                        Tm = (lo + hi) / 2
                        h = hull_heat(cfg, S, P, crew, dict(T_LIQ, **{tank: Tm}))[tank]
                        lo, hi = (Tm, hi) if h > 0 else (lo, Tm)
                    Teq[tank] = (lo + hi) / 2
                k = ("habite" if crew else "cargo") + ("_1UA" if dist == 1 else "_mars")
                eq[pk][k] = dict(q_W={t: v for t, v in q.items()}, T_eq=Teq)
                print(f"  {pk:7s} {k:12s}: LOX {q['LOX']:+5.0f} W (équilibre {Teq['LOX']:5.1f} K), "
                      f"CH4 {q['CH4']:+5.0f} W (équilibre {Teq['CH4']:5.1f} K)")

    # Gaz évaporé réutilisé : impulsion qu'il fournirait, oxygène respiré
    # Tolérance de pointage : axe écarté du Soleil, bord des tuiles éclairé
    print("\nA · isolant côté Soleil : chaleur nette par vaisseau (W) selon l'écart de l'axe au Soleil, à 1 UA")
    pointing = {}
    for tilt in (0, 5, 10, 15, 20):
        pointing[tilt] = {pk: sum(hull_heat(cfg, S0, P, True, tilt_deg=tilt).values()) for pk, P in PARAMS.items()}
        print(f"  {tilt:2d}° : " + ", ".join(f"{pk} {v:+6.0f}" for pk, v in pointing[tilt].items()))

    print("\nRéemploi du gaz évaporé (orientation B, isolant partout, fourchette centrale)")
    bo = res["B_mli_tout"]["central"]["total3_t"] * 1e3
    for name, isp in THRUSTERS:
        print(f"  {name:40s} : {bo * isp * G0:.2e} N·s")
    print(f"  oxygène respiré : 0,84 kg/personne/jour → {0.84 * tr['T_half'] / 1e3 * 100:.0f} t pour 100 personnes")

    out = dict(transfert=dict(a_UA=tr["a"], e=tr["e"], duree_j=tr["T_half"], taux_depart=float(rate[0]), taux_arrivee=float(rate[-1]),
                              ecart_lineaire_deg=err_lin,
                              courbe=[[float(np.interp(d, tr["t"], tr["t"])), float(np.degrees(np.interp(d, tr["t"], tr["nu"]))),
                                       float(np.interp(d, tr["t"], tr["r"]))] for d in np.linspace(0, tr["T_half"], 53)]),
               station=dict(I=st["I"], L=st["L"], v=v, couple=tau, F_moy=4 / math.pi * tau / R_SHIP, F_impulsion=F_pulse,
                            dJ_impulsion=dJ),
               pivotement=cases, propulseurs=[dict(nom=n, isp=i) for n, i in THRUSTERS],
               ecran={str(k): v for k, v in shade.items()}, thermique=res, equilibre=eq, pointage=pointing, parametres=PARAMS)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "data", "soleil.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    print(f"→ {path}")


if __name__ == "__main__":
    main()
