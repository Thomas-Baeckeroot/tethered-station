#!/usr/bin/env python3
"""
Campagnes de scénarios : lance tether_sim.py en parallèle (un processus par
scénario), puis agrège les résultats dans out/<campagne>/summary.md et une
figure de comparaison.

Campagnes :
- rotation : stabilité en rotation selon la topologie et l'orientation des
  modules (effet Djanibekov, roulis autour du câble) ;
- internes : mouvements internes (cargaison, équipage, balayage en fréquence)
  sur les configurations stables A, G, H, + atténuations (patte d'oie,
  amortisseur interne).
"""
import argparse
import json
import os
import subprocess
import sys
import time

import tether_sim as ts

HERE = os.path.dirname(os.path.abspath(__file__))

A = ["--topology", "dumbbell", "--module", "tangential"]
G = ["--topology", "triangle2", "--module", "axial", "--spread", "20"]
H = ["--topology", "triangle", "--module", "tangential"]
FINAL = ["--topology", "triangle2", "--module", "tangential", "--spread", "20"]
CARGO = ["--motion", "cargo", "--motion-mass-t", "50", "--motion-amp", "15", "--duration", "1500"]
WALK = ["--motion", "walk", "--motion-mass-t", "4", "--motion-amp", "15", "--motion-speed", "1.2", "--duration", "1800"]
SWEEP = ["--motion", "sweep", "--motion-mass-t", "4", "--motion-amp", "15", "--duration", "3660"]
TRAJ = ["--traj-dt", "0.5"]
PERT = ["--duration", "1800", "--dv-lateral", "0.2"]

# Modules au gabarit du Starship (Ø9 m, 50 m), 1 600 t (vaisseau plein)
SS = ["--module-radius", "4.5", "--module-length", "50"]
# Vertical : axe long radial, câbles aux points d'ancrage du nez (±3,5 m)
SV3 = ["--topology", "triangle2", "--module", "radial", "--spread", "3.5"] + SS
SV2 = ["--topology", "dumbbell", "--module", "radial"] + SS
SV2L = ["--topology", "ladder", "--module", "radial", "--spread", "3.5"] + SS
# Horizontal : axe long tangentiel, attaches aux deux extrémités, avec ou sans mâts de 20 m
SH3 = ["--topology", "triangle2", "--module", "tangential", "--spread", "20", "--bridle", "20"] + SS
SH3n = ["--topology", "triangle2", "--module", "tangential", "--spread", "20"] + SS
# Déplacements latéraux limités au rayon d'un pont (Ø9 m)
LAT = ["--motion-amp", "3.5", "--motion-axis", "t"]
LATZ = ["--motion-amp", "3.5", "--motion-axis", "z"]
# Mission Terre → Mars : triangle vertical, masse après l'injection vers Mars
# (mission_mass.py : 610 t), câbles dimensionnés pour le vaisseau chargé
# (1 600 t à 1 g), gravité de Mars au pont principal (14 m de la pointe)
DECK = ["--g-ref-x", "14"]
# Câbles sur les points de capture du Starship V3 (13 m de la pointe, ±4,8 m) ;
# --bridle -4 place l'attache du cylindre homogène (campagne mission) à 21 m
# au-dessus de son centre de masse, comme sur le vrai vaisseau (34 − 13 m)
ANCHOR = ["--spread", f"{ts.ANCHOR_SPREAD:g}", "--attach-x", f"{ts.ANCHOR_X:g}", "--bridle", "-4"]
POOL = ["--tld-mass-t", f"{ts.POOL['m_t']:g}", "--tld-x", f"{ts.POOL['x']:g}", "--tld-radius", f"{ts.POOL['a']:g}",
        "--tld-zeta", f"{ts.POOL['zeta']:g}"]
# Câble de référence : Dyneema SK99 tressé, gainé, redondant (carnet § 2.3)
CABLE = ["--material", "sk99"]
MISSION = SV3 + ["--mass-t", "610", "--design-mass-t", "1600", "--accel", "3.711"] + DECK + ANCHOR + CABLE
# Ballottement des ergols : modèle de masse du Starship, ergols figés ou libres
# (pendules d'Abramson), parois raidies (ζ = 0,1 %) ou chicanes (ζ = 3 %) ;
# balayage prolongé jusqu'à 0,4 Hz pour couvrir le mode de ballottement
FROZEN = MISSION + ["--slosh", "frozen"]
FREE = MISSION + ["--slosh", "free", "--slosh-zeta", "0.001"]
BAFFLED = MISSION + ["--slosh", "free", "--slosh-zeta", "0.03"]
SWEEP_L = ["--motion", "sweep", "--motion-mass-t", "4", "--duration", "5460", "--sweep-f1", "0.4"]
RESO = ["--motion", "periodic", "--motion-mass-t", "4", "--motion-amp", "0.38", "--motion-axis", "z",
        "--motion-period", "3.90", "--motion-stop", "240", "--duration", "600"]

TLD = BAFFLED + POOL
# 4 t oscillant hors plan au rythme du balancement principal (≈ 9 s) pendant 3 min
RESO8 = ["--motion", "periodic", "--motion-mass-t", "4", "--motion-amp", "3.5", "--motion-axis", "z",
         "--motion-period", "9.0", "--motion-stop", "240", "--duration", "900"]

# Rupture d'un câble (côté 0, entre les vaisseaux 0 et 1) à t = 60 s ; parade :
# moyeu central de 20 t relié au nez de chaque vaisseau par un rayon prétendu
# à 15 % de la tension d'un côté
BRK = ["--break-cable", "0", "--break-time", "60"]
HUB = ["--hub-mass-t", "20", "--spoke-tension", "0.15"]
HUB2 = HUB + ["--hub-spokes", "2"]
# Mise en rotation après l'injection : de 0,1 à 1 tr/min, poussée tangentielle
# sur chaque vaisseau (propulseurs d'attitude, Isp 300 s), sans perturbation
SPIN = ["--spin-from", "0.1", "--dv-radial", "0", "--dv-z", "0", "--droll", "0"]
# Masses inégales : ergols du vaisseau habité transvasés dans les cargos
# (220 / 805 / 805 t), attaches sur les points de capture, vaisseau habité à 3,711 m/s² au pont principal : 0,862 tr/min (light_tld.py)
UNEQ = SV3 + DECK + ANCHOR + CABLE + ["--design-mass-t", "1600", "--accel", "3.711", "--slosh", "free", "--slosh-zeta", "0.03"] + POOL + [
    "--masses-t", "220,805,805", "--target-ship", "0", "--rpm", "0.8621"]


# Sensibilité de la solution retenue : V3 aux réservoirs pleins (1 820 t au
# départ, 693 t en route, câbles dimensionnés pour 1 820 t) ; câble idéal
# (Dyneema plein, sans tresse ni redondance : 15 t, EA ÷1,5, masse linéique ÷1,7)
V3FULL = [a if a not in ("610", "1600") else {"610": "693", "1600": "1820"}[a] for a in TLD]
DYN = TLD + ["--material", "dyneema"]
PREC_R = TLD + ["--dv-radial", "0", "--dv-z", "0", "--droll", "0", "--precess-rate", "0.695", "--precess-pulse", "15"]
TLD_Z30 = [a if a != f"{ts.POOL['zeta']:g}" else "0.3" for a in TLD]
# Solution retenue, câbles à trois brins par côté (tiers de section, même
# masse de câble), sur une ferrure commune, coupe-câbles à 1 s
TLD3 = TLD + ["--side-strands", "3", "--release-delay", "1"]

# Retour vers la Terre en fin de rampe : vaisseaux légers (250 t : structure,
# charge réduite, ergols d'atterrissage), 1 g au pont principal avec les mêmes
# câbles (R = 338,4 m au pont : 1,626 tr/min), trois brins par côté
RET = [{"610": "250", "3.711": "9.81"}.get(a, a) for a in TLD3] + ["--rpm", "1.626"]
# Protection contre le retour du brin rompu (§ 7.4) : entretoises entre les
# trois brins d'un côté tous les 48 m (élingues à 0,1 m de jeu), sans
# coupe-câbles (les morceaux restent tenus) ; câble découpé en 48 segments
TRAJF = ["--traj-dt", "0.25"]  # trajectoires assez fines pour suivre le brin rompu (figure du § 7.4)
TIES = ["--segments", "48", "--strand-ties", "4", "--tie-slack", "0.1", "--release-delay", "-1"]

# 4 t oscillant hors plan pendant 4 min au pire rythme du vaisseau habité
# allégé de 195 t avec le bassin d'origine (0,082 Hz, période 12,2 s)
RESO_K = ["--motion", "periodic", "--motion-mass-t", "4", "--motion-amp", "3.5", "--motion-axis", "z",
          "--motion-period", "12.2", "--motion-stop", "240", "--duration", "900"]


def UNEQ_K(masses, rpm):
    """Masses inégales (même modèle que UNEQ) : masses et vitesse données."""
    a = list(UNEQ)
    a[a.index("--masses-t") + 1] = masses
    a[a.index("--rpm") + 1] = rpm
    return a


def _pname(P):
    """Nom de scénario d'une période : 1.88 → 1_88, 1.865 → 1_865."""
    v = f"{P:.3f}"
    return (v[:-1] if v.endswith("0") else v).replace(".", "_")


CAMPAIGNS = {
    "rotation": [
        ("A_haltere_tangentiel", A + ["--duration", "1800"]),
        ("B_haltere_axial", ["--topology", "dumbbell", "--module", "axial", "--duration", "1800"] + TRAJ),
        ("C_haltere_tour", ["--topology", "dumbbell", "--module", "radial", "--duration", "1800"]),
        ("D_echelle_axial", ["--topology", "ladder", "--module", "axial", "--spread", "15", "--duration", "1800"] + TRAJ),
        ("E_echelle_tangentiel", ["--topology", "ladder", "--module", "tangential", "--spread", "5", "--duration", "1800"]),
        ("F_triangle_axial", ["--topology", "triangle", "--module", "axial", "--duration", "1800"] + TRAJ),
        ("G_triangle_palonnier_axial", G + ["--duration", "1800"]),
        ("H_triangle_tangentiel", H + ["--duration", "1800"]),
    ],
    "internes": [
        ("A_cargaison", A + CARGO + TRAJ),
        ("G_cargaison", G + CARGO + TRAJ),
        ("H_cargaison", H + CARGO + TRAJ),
        ("A_equipage", A + WALK),
        ("G_equipage", G + WALK),
        ("H_equipage", H + WALK),
        ("A_balayage", A + SWEEP),
        ("G_balayage", G + SWEEP),
        ("H_balayage", H + SWEEP),
        ("A_cargaison_patte_oie", A + CARGO + ["--bridle", "20"]),
        ("B_amortisseur", ["--topology", "dumbbell", "--module", "axial", "--damper-frac", "0.05", "--damper-tau", "30",
                           "--duration", "1800"] + TRAJ),
    ],
    # Configuration recommandée : triangle, modules tangentiels attachés à leurs
    # deux extrémités (palonnier ±20 m le long de l'axe long)
    "final": [
        ("Z_final_perturbation", FINAL + ["--duration", "1800", "--dv-lateral", "0.2"] + TRAJ),
        ("Z_final_cargaison", FINAL + CARGO + TRAJ),
        ("Z_final_equipage", FINAL + WALK),
        ("Z_final_balayage", FINAL + SWEEP),
        ("Z_final_cargaison_3modules", FINAL + CARGO + ["--motion-modules", "0,1,2"]),
        ("Z_final_cargaison_patte_oie", FINAL + CARGO + ["--bridle", "20"] + TRAJ),
        # Z+ : attaches surélevées de 20 m (mâts ou pattes d'oie)
        ("Zp_perturbation", FINAL + ["--bridle", "20", "--duration", "1800", "--dv-lateral", "0.2"] + TRAJ),
        ("Zp_equipage", FINAL + WALK + ["--bridle", "20"]),
        ("Zp_balayage", FINAL + SWEEP + ["--bridle", "20"]),
    ],
    # Stations de Starships : vertical (axe radial) ou horizontal, 2 ou 3 vaisseaux
    "starship": [
        ("SV3_perturbation", SV3 + PERT + TRAJ),
        ("SV3_cargaison_laterale", SV3 + CARGO + LAT + TRAJ),
        ("SV3_cargaison_verticale", SV3 + CARGO),
        ("SV3_equipage", SV3 + WALK + LAT),
        ("SV3_balayage_t", SV3 + SWEEP + LAT),
        ("SV3_balayage_z", SV3 + SWEEP + LATZ),
        ("SV3_h15_balayage_t", SV3 + SWEEP + LAT + ["--bridle", "-10"]),
        ("SV3_250t_equipage", SV3 + WALK + LAT + ["--mass-t", "250"]),
        ("SV3_250t_balayage_t", SV3 + SWEEP + LAT + ["--mass-t", "250"]),
        ("SV2_perturbation", SV2 + PERT + TRAJ),
        ("SV2_cargaison_laterale", SV2 + CARGO + LAT),
        ("SV2_equipage", SV2 + WALK + LAT),
        ("SV2_balayage_t", SV2 + SWEEP + LAT),
        ("SV2L_perturbation", SV2L + PERT),
        ("SH3_perturbation", SH3 + PERT),
        ("SH3_cargaison", SH3 + CARGO),
        ("SH3_equipage", SH3 + WALK),
        ("SH3_balayage", SH3 + SWEEP),
        ("SH3n_perturbation", SH3n + PERT),
        ("SH3n_cargaison", SH3n + CARGO),
        ("SH3n_balayage", SH3n + SWEEP),
    ],
    "mission": [
        ("M_perturbation", MISSION + PERT + TRAJ),
        ("M_cargaison_laterale", MISSION + CARGO + LAT + TRAJ),
        ("M_cargaison_verticale", MISSION + CARGO),
        ("M_equipage", MISSION + WALK + LAT),
        ("M_balayage_t", MISSION + SWEEP + LAT),
        ("M_balayage_z", MISSION + SWEEP + LATZ),
        ("M_h15_balayage_t", MISSION + SWEEP + LAT + ["--bridle", "-10"]),
        ("M_h15_balayage_z", MISSION + SWEEP + LATZ + ["--bridle", "-10"]),
    ],
    "ballottement": [
        ("L_conservation", MISSION + ["--slosh", "free", "--slosh-zeta", "0", "--duration", "600", "--dv-lateral", "0.2"]),
        ("L_fige_perturbation", FROZEN + PERT),
        ("L_libre_perturbation", FREE + PERT + TRAJ),
        ("L_chicanes_perturbation", BAFFLED + PERT),
        ("L_fige_cargaison", FROZEN + CARGO + LAT),
        ("L_libre_cargaison", FREE + CARGO + LAT + TRAJ),
        ("L_libre_equipage", FREE + WALK + LAT),
        ("L_fige_balayage_t", FROZEN + SWEEP_L + LAT),
        ("L_fige_balayage_z", FROZEN + SWEEP_L + LATZ),
        ("L_libre_balayage_t", FREE + SWEEP_L + LAT),
        ("L_libre_balayage_z", FREE + SWEEP_L + LATZ),
        ("L_chicanes_balayage_t", BAFFLED + SWEEP_L + LAT),
        ("L_chicanes_balayage_z", BAFFLED + SWEEP_L + LATZ),
        # Animations : 4 t oscillant hors plan au rythme du ballottement couplé (3,90 s) pendant 3 min
        ("L_libre_resonance", FREE + RESO + ["--traj-dt", "0.25"]),
        ("L_chicanes_resonance", BAFFLED + RESO + ["--traj-dt", "0.25"]),
    ],
    # Solution retenue : mission, ergols libres, réservoirs à chicanes
    "retenue": [
        ("R_perturbation", BAFFLED + PERT + TRAJ),
        ("R_cargaison_laterale", BAFFLED + CARGO + LAT + TRAJ),
        ("R_cargaison_verticale", BAFFLED + CARGO + TRAJ),
        ("R_equipage", BAFFLED + WALK + LAT),
    ],
    # Amortisseur à liquide accordé (tld_design.py) : 25 t d'eau sous la
    # coiffe, bassin Ø 7,8 m × 0,52 m accordé sur le balancement hors plan
    "amortisseur": [
        ("T_balayage_z", TLD + SWEEP_L + LATZ),
        ("T_balayage_t", TLD + SWEEP_L + LAT),
        ("T50_balayage_z", BAFFLED + ["--tld-mass-t", "50", "--tld-x", "12", "--tld-radius", "4.4", "--tld-zeta", "0.1"] + SWEEP_L + LATZ),
        ("T560_balayage_z", [a if a != "610" else "560" for a in TLD] + SWEEP_L + LATZ),
        ("T_perturbation", TLD + PERT + TRAJ),
        ("T_cargaison_laterale", TLD + CARGO + LAT),
        ("T_equipage", TLD + WALK + LAT),
        ("R_resonance_z", BAFFLED + RESO8 + ["--traj-dt", "0.25"]),
        ("T_resonance_z", TLD + RESO8 + ["--traj-dt", "0.25"]),
        ("T_balayage_t_07", TLD + SWEEP_L + LAT + ["--sweep-f1", "0.7"]),   # au-delà de la corde : mode d'étirement, vers 0,53 Hz
        ("T_balayage_z_07", TLD + SWEEP_L + LATZ + ["--sweep-f1", "0.7"]),
        # Revue du 2026-11-06 : grilles plus serrées (ζ = 0,30, modèle
        # linéaire : 0,67° au lieu de 0,79° au pont) ; cargaison déplacée hors
        # plan (R-16) ; bassin dans le seul vaisseau habité, eau figée dans les
        # cargos, masse inchangée (R-17)
        ("T_zeta30_balayage_z", TLD_Z30 + SWEEP_L + LATZ),
        ("T_zeta30_balayage_t", TLD_Z30 + SWEEP_L + LAT),
        ("T_cargaison_hors_plan", TLD + CARGO + LATZ),
        ("T_bassin0_balayage_z", TLD + ["--tld-ships", "0"] + SWEEP_L + LATZ),
        ("T_bassin0_balayage_t", TLD + ["--tld-ships", "0"] + SWEEP_L + LAT),
        ("T_bassin0_equipage", TLD + ["--tld-ships", "0"] + WALK + LAT),
    ],
    # Rupture d'un câble, solution retenue (chicanes + bassin), puis avec moyeu
    "rupture": [
        ("X_rupture_milieu", TLD + BRK + ["--break-at", "0.5", "--duration", "1800"] + TRAJ),
        ("X_rupture_attache", TLD + BRK + ["--break-at", "0", "--duration", "900"] + TRAJ),
        ("Y_moyeu_perturbation", TLD + HUB + PERT + TRAJ),
        ("Y_moyeu_rupture", TLD + HUB + BRK + ["--break-at", "0.5", "--duration", "1800"] + TRAJ),
        ("Y_moyeu_rupture_rayon", TLD + HUB + ["--break-cable", "3", "--break-time", "60", "--break-at", "0.5", "--duration", "900"]),
        # Parades complémentaires : coupe-câbles qui larguent les morceaux 1 s
        # après la rupture ; rayons doublés (un par point d'attache du nez)
        ("Y_moyeu_rupture_largage", TLD + HUB + BRK + ["--break-at", "0.5", "--release-delay", "1", "--duration", "900"] + TRAJ),
        ("Z_moyeu_double_rupture_rayon", TLD + HUB + ["--hub-spokes", "2", "--break-cable", "3", "--break-time", "60", "--break-at", "0.5",
                                                      "--release-delay", "1", "--duration", "900"]),
        ("Z_moyeu_double_rupture", TLD + HUB + ["--hub-spokes", "2"] + BRK + ["--break-at", "0.5", "--release-delay", "1", "--duration", "900"] + TRAJ),
    ],
    # Configuration recommandée (bassin + moyeu à rayons doublés) : le moyeu
    # change-t-il le confort ?
    "moyeu": [
        ("Z_balayage_z", TLD + HUB2 + SWEEP_L + LATZ),
        ("Z_balayage_t", TLD + HUB2 + SWEEP_L + LAT),
        ("Z_cargaison_laterale", TLD + HUB2 + CARGO + LAT),
        ("Z_equipage", TLD + HUB2 + WALK + LAT),
    ],
    # Mise en rotation : α = k·ω² (inclinaison ressentie constante), α constant,
    # poussée à l'arrière plutôt qu'au centre de masse, avec moyeu
    "montee": [
        ("S_montee_k005", TLD + SPIN + ["--spin-k", "0.05", "--duration", "2100"] + TRAJ),
        ("S_montee_k02", TLD + SPIN + ["--spin-k", "0.2", "--duration", "900"]),
        ("S_montee_alpha", TLD + SPIN + ["--spin-alpha", "5.2e-5", "--duration", "2100"]),
        ("S_montee_arriere", TLD + SPIN + ["--spin-k", "0.05", "--spin-thrust-x", "45", "--duration", "2100"]),
        ("S_montee_moyeu", TLD + HUB2 + SPIN + ["--spin-k", "0.05", "--duration", "2100"]),
    ],
    # Montée lente de 0,1 à 1 tr/min : même impulsion, poussée et inclinaison
    # bien plus faibles ; passage lent sur les résonances (2 h 25 et 6 h)
    "montee_lente": [
        ("S_lente_k01", TLD + SPIN + ["--spin-k", "0.01", "--duration", "9000"]),
        ("S_lente_k004", TLD + SPIN + ["--spin-k", "0.004", "--duration", "22200"]),
    ],
    # Mode couplé du LOX (pic restant avec le bassin) : chicanes plus
    # efficaces (ζ = 8 %), ou second bassin de 8 t près des moteurs accordé
    # sur ce mode (tld_design.py, recherche out/lox_search.log)
    "lox": [
        ("V_chicanes8_balayage_z", [a if a != "0.03" else "0.08" for a in TLD] + SWEEP_L + LATZ),
        ("V_bassin2_balayage_z", TLD + ["--tld2-mass-t", "8", "--tld2-x", "46", "--tld2-radius", "1.8", "--tld2-zeta", "0.1"] + SWEEP_L + LATZ),
    ],
    # Axe face au Soleil : l'axe de rotation pivote pour suivre le Soleil
    # (0,695 °/jour en moyenne, sun_pointing.py), ici 1 000 fois plus vite
    # pour que l'effet se mesure en 20 min ; poussée continue ou impulsions au
    # passage de la ligne des nœuds. Effets (inclinaison, forces) ÷ 1 000 en vrai
    "soleil": [
        ("P_pivot_sinus", TLD + ["--dv-radial", "0", "--dv-z", "0", "--droll", "0", "--precess-rate", "695", "--duration", "1200"]),
        ("P_pivot_impulsions", TLD + ["--dv-radial", "0", "--dv-z", "0", "--droll", "0", "--precess-rate", "695",
                                      "--precess-pulse", "15", "--duration", "1200"]),
        # Vitesse réelle (0,695 °/jour) : impulsions à chaque tour, ou groupées
        # un tour sur 10 ou sur 100, poussée × 10 ou × 100 (revue R-08)
        ("P_impulsions_reel", PREC_R + ["--duration", "900"]),
        ("P_groupe10_reel", PREC_R + ["--precess-group", "10", "--duration", "1500"]),
        ("P_groupe100_reel", PREC_R + ["--precess-group", "100", "--duration", "900"]),
    ],
    # Masses inégales (transfert d'ergols vers les cargos)
    "masses": [
        ("U_perturbation", UNEQ + PERT),
        ("U_cargaison_laterale", UNEQ + CARGO + LAT),
        ("U_equipage", UNEQ + WALK + LAT),
        ("U_balayage_z", UNEQ + SWEEP_L + LATZ),
        # Bassin réaccordé sur le balancement hors plan du vaisseau habité
        # allégé (≈ 0,059 Hz au lieu de 0,106 Hz) : 15 t, Ø 8,8 m, 0,25 m
        ("U_balayage_z_bassin", UNEQ + ["--tld-mass-t", "15", "--tld-radius", "4.4", "--tld-zeta", "0.3"] + SWEEP_L + LATZ),
    ],
    # Vaisseau habité allégé : transfert partiel de ses ergols vers les
    # cargos (100, 195, 300 t, rapport de mélange conservé), vitesse de
    # rotation qui garde 3,711 m/s² à son bord pour des câbles inchangés ; ou
    # transfert complet et 50 t de charge utile descendues en bas du vaisseau
    # habité (lest, masse inchangée). Contrôle de convergence : 32 segments
    "allege": [
        (f"{k}_{sc}", base + extra)
        for k, base in (("K100", UNEQ_K("510,660,660", "0.9588")), ("K195", UNEQ_K("415,708,708", "0.9239")),
                        ("K300", UNEQ_K("310,760,760", "0.8894")),
                        ("KL50", UNEQ_K("220,805,805", "0.8644") + ["--ballast-t", "50", "--ballast-x", "44"]))
        for sc, extra in (("perturbation", PERT), ("cargaison_laterale", CARGO + LAT + TRAJ), ("equipage", WALK + LAT),
                          ("balayage_z", SWEEP_L + LATZ), ("balayage_t", SWEEP_L + LAT))
    ] + [("K195_balayage_z_seg32", UNEQ_K("415,708,708", "0.9239") + SWEEP_L + LATZ + ["--segments", "32"])]
    # Bassin réaccordé sur le balancement hors plan du vaisseau habité
    # (light_tld.py : Ø 8,8 m, toute la largeur de la coque, sauf K100) ; forçage
    # au pire rythme du bassin d'origine (K195 : 0,082 Hz) avec l'un ou l'autre
    + [(f"{k}_{sc}_bassin", base + pool + extra)
       for k, base, pool in (("K100", UNEQ_K("510,660,660", "0.9588"), ["--tld-mass-t", "25", "--tld-radius", "4.2", "--tld-zeta", "0.2"]),
                             ("K195", UNEQ_K("415,708,708", "0.9239"), ["--tld-mass-t", "25", "--tld-radius", "4.4", "--tld-zeta", "0.3"]),
                             ("K300", UNEQ_K("310,760,760", "0.8894"), ["--tld-mass-t", "25", "--tld-radius", "4.4", "--tld-zeta", "0.3"]),
                             ("KL50", UNEQ_K("220,805,805", "0.8644") + ["--ballast-t", "50", "--ballast-x", "44"],
                              ["--tld-mass-t", "25", "--tld-radius", "4.4", "--tld-zeta", "0.3"]))
       for sc, extra in (("balayage_z", SWEEP_L + LATZ), ("balayage_t", SWEEP_L + LAT))
       if sc == "balayage_z" or k in ("K195", "KL50")]
    + [("K195_resonance_z", UNEQ_K("415,708,708", "0.9239") + RESO_K + TRAJ),
       ("K195_resonance_z_bassin", UNEQ_K("415,708,708", "0.9239") + ["--tld-mass-t", "25", "--tld-radius", "4.4", "--tld-zeta", "0.3"]
        + RESO_K + TRAJ)],
    "sensibilite": [
        ("N_perturbation", V3FULL + PERT),
        ("N_cargaison_laterale", V3FULL + CARGO + LAT),
        ("N_equipage", V3FULL + WALK + LAT),
        ("N_balayage_z", V3FULL + SWEEP_L + LATZ),
        ("N_balayage_t", V3FULL + SWEEP_L + LAT),
        ("C_perturbation", DYN + PERT),
        ("C_balayage_z", DYN + SWEEP_L + LATZ),
        ("C_balayage_t", DYN + SWEEP_L + LAT),
        ("C_balayage_t_07", DYN + SWEEP_L + LAT + ["--sweep-f1", "0.7"]),
        ("C_rupture_milieu", DYN + BRK + ["--break-at", "0.5", "--duration", "1800"]),
        # amortissement des câbles ÷ 4 (ζ = 0,5 % au lieu de 2 %), jusqu'au
        # mode d'étirement (revue R-10)
        ("Q_amort05_balayage_t_07", TLD + SWEEP_L + LAT + ["--sweep-f1", "0.7", "--zeta", "0.005"]),
        ("C_brins2_rupture", DYN + BRK + ["--side-strands", "2", "--break-at", "0.5", "--release-delay", "1", "--duration", "900"]),
    ],
    # Câbles à trois brins (solution retenue) : confort en service, rupture
    # d'un brin (milieu, attache, sans coupe-câbles, câble Dyneema plein),
    # puis de deux brins du même côté, ensemble ou à 10 s d'intervalle
    "brins3": [
        ("B3_perturbation", TLD3 + PERT + TRAJ),
        ("B3_cargaison_laterale", TLD3 + CARGO + LAT),
        ("B3_equipage", TLD3 + WALK + LAT),
        ("B3_balayage_z", TLD3 + SWEEP_L + LATZ),
        ("B3_balayage_t", TLD3 + SWEEP_L + LAT),
        ("B3_rupture", TLD3 + BRK + ["--break-at", "0.5", "--duration", "900"] + TRAJ),
        ("B3_rupture_attache", TLD3 + BRK + ["--break-at", "0", "--duration", "900"]),
        ("B3_sans_largage", TLD + BRK + ["--side-strands", "3", "--break-at", "0.5", "--duration", "900"]),
        ("B3_dyneema_rupture", TLD3 + BRK + ["--material", "dyneema", "--break-at", "0.5", "--duration", "900"]),
        ("B3_double_rupture", TLD3 + BRK + ["--break-cable2", "3", "--break-at", "0.5", "--duration", "900"] + TRAJ),
        ("B3_double_rupture_10s", TLD3 + BRK + ["--break-cable2", "3", "--break-time2", "70", "--break-at", "0.5", "--duration", "900"]),
        # Perte d'une ferrure (revue R-03) : les trois brins d'un côté cèdent
        # ensemble à l'attache, morceaux largués ; sans moyeu, puis avec
        ("B3_ferrure", TLD3 + BRK + ["--break-cable2", "3", "--break-cable3", "6", "--break-at", "0", "--duration", "900"] + TRAJ),
        # Avec moyeu : avant la rupture, les trois brins d'une ferrure commune
        # équivalent à un câble ; perdre la ferrure coupe le côté et le rayon
        # qui en part (câble 3 : vaisseau 0, attache 0)
        ("Z3_ferrure", TLD + HUB2 + BRK + ["--break-cable2", "3", "--break-at", "0", "--release-delay", "1", "--duration", "900"] + TRAJ),
    ],
    # Retour en fin de rampe (250 t, 1 g) : tensions en service et après la
    # rupture d'un ou deux brins, pour les cas de charge du fluage (creep.py)
    "retour": [
        ("RT_perturbation", RET + PERT),
        ("RT_rupture", RET + BRK + ["--break-at", "0.5", "--duration", "900"]),
        ("RT_double_rupture", RET + BRK + ["--break-cable2", "3", "--break-at", "0.5", "--duration", "900"]),
    ],
    # Retour du brin rompu : référence au même découpage (coupe-câbles, sans
    # entretoises), puis entretoises tous les 24, 48 ou 97 m ; rupture au
    # milieu, près de la ferrure ou à l'attache ; double rupture ; retour à 1 g
    "entretoises": [
        ("E_reference", TLD3 + BRK + ["--segments", "48", "--break-at", "0.5", "--duration", "900"] + TRAJF),
        # parades écartées : bras de déport de 11 m (attaches à ±16 m de
        # l'axe), longe qui retient le morceau côté vaisseau
        ("E_bras_16m", TLD3 + BRK + ["--segments", "48", "--spread", "16", "--break-at", "0.5", "--duration", "900"] + TRAJF),
        ("E_longe", TLD3 + BRK + ["--segments", "48", "--release-keep", "0", "--break-at", "0.5", "--duration", "900"] + TRAJF),
        ("E_perturbation", TLD3 + TIES + PERT),
        ("E_rupture", TLD3 + TIES + BRK + ["--break-at", "0.5", "--duration", "900"] + TRAJF),
        ("E_rupture_24m", TLD3 + TIES + ["--strand-ties", "2"] + BRK + ["--break-at", "0.5", "--duration", "900"]),
        ("E_rupture_97m", TLD3 + TIES + ["--strand-ties", "8"] + BRK + ["--break-at", "0.5", "--duration", "900"]),
        ("E_rupture_ferrure", TLD3 + TIES + BRK + ["--break-at", "0.05", "--duration", "900"]),
        ("E_rupture_ferrure_24m", TLD3 + TIES + ["--strand-ties", "2"] + BRK + ["--break-at", "0.05", "--duration", "900"]),
        ("E_rupture_attache", TLD3 + TIES + BRK + ["--break-at", "0", "--duration", "900"]),
        ("E_double_rupture", TLD3 + TIES + BRK + ["--break-cable2", "3", "--break-at", "0.5", "--duration", "900"]),
        ("E_retour_rupture", RET + TIES + BRK + ["--break-at", "0.5", "--duration", "900"]),
        # entretoises et coupe-câbles ensemble (revue R-06)
        ("E_rupture_largage", TLD3 + TIES + ["--release-delay", "1"] + BRK + ["--break-at", "0.5", "--duration", "900"] + TRAJF),
    ],
    # Câbles multiples (même masse de câble) : un brin sur deux ou trois
    # rompt au milieu, les autres reprennent la charge ; brins sur la même
    # ferrure, ou écartés de 2 m selon l'axe de rotation
    "brins": [
        ("W_brins2_rupture", TLD + BRK + ["--side-strands", "2", "--break-at", "0.5", "--release-delay", "1", "--duration", "900"] + TRAJ),
        ("W_brins2_sans_largage", TLD + BRK + ["--side-strands", "2", "--break-at", "0.5", "--duration", "900"]),
        ("W_brins2_attache", TLD + BRK + ["--side-strands", "2", "--break-at", "0", "--release-delay", "1", "--duration", "900"]),
        ("W_brins2_ecartes", TLD + BRK + ["--side-strands", "2", "--strand-gap", "2", "--break-at", "0.5", "--release-delay", "1", "--duration", "900"]),
        ("W_brins3_rupture", TLD + BRK + ["--side-strands", "3", "--break-at", "0.5", "--release-delay", "1", "--duration", "900"]),
        # Recul du brin rompu le long du brin intact : câble plus finement découpé,
        # trajectoires toutes les 0,05 s, 30 s après la rupture
        ("W_brins2_recul", TLD + BRK + ["--side-strands", "2", "--break-at", "0.5", "--release-delay", "1", "--duration", "90",
                                        "--segments", "48", "--traj-dt", "0.05"]),
        # Dispositions : brins écartés dans le plan (du côté de leur voisin),
        # brins croisés sous le nez (libres, puis amarrés au croisement)
        ("W_brins2_plan", TLD + BRK + ["--side-strands", "2", "--strand-layout", "plan", "--strand-gap", "2", "--break-at", "0.5",
                                       "--release-delay", "1", "--duration", "900"]),
        ("W_brins2_croises", TLD + ["--side-strands", "2", "--strand-layout", "croise", "--duration", "900"]),
        ("W_brins2_croises_rupture", TLD + BRK + ["--side-strands", "2", "--strand-layout", "croise", "--break-at", "0.5", "--release-delay", "1",
                                                  "--duration", "900"]),
        ("W_brins2_lies", TLD + BRK + ["--side-strands", "2", "--strand-layout", "lie", "--break-at", "0.5", "--release-delay", "1",
                                       "--duration", "900"]),
    ],
    # Forçage à période fixe (4 t, 1 m/s² d'accélération) autour des modes
    # étroits que les balayages sous-estiment (revue R-02) : mode
    # d'étirement dans le plan (≈ 0,53 Hz) ; corde, LOX et roulis hors plan
    # (≈ 0,26 Hz)
    "frequences": [
        (f"F_etir_t_{_pname(P)}", TLD + ["--motion", "periodic", "--motion-mass-t", "4", "--motion-axis", "t",
                                          "--motion-amp", f"{(P / (2 * 3.141592653589793)) ** 2:.5f}", "--motion-period", f"{P:.3f}",
                                          "--motion-stop", "360", "--duration", "600"])
        for P in sorted([1.78 + 0.02 * i for i in range(10)] + [1.865, 1.87, 1.872, 1.875, 1.877, 1.879, 1.885, 1.89, 1.895]
                        + [1.98 + 0.02 * i for i in range(8)])
    ] + [
        # mode hors plan lent (≈ 4 s) : forçage plus long, la réponse croît encore à 420 s
        (f"F_corde_z_{_pname(P)}", TLD + ["--motion", "periodic", "--motion-mass-t", "4", "--motion-axis", "z",
                                           "--motion-amp", f"{(P / (2 * 3.141592653589793)) ** 2:.5f}", "--motion-period", f"{P:.3f}",
                                           "--motion-stop", "600", "--duration", "840"])
        for P in [3.40 + 0.05 * i for i in range(21)]
    ] + [
        # pics étroits de 3,65 et 4,10 s : pas de 0,01 s, forçage de 15 min
        (f"F_corde_z_{_pname(P)}", TLD + ["--motion", "periodic", "--motion-mass-t", "4", "--motion-axis", "z",
                                           "--motion-amp", f"{(P / (2 * 3.141592653589793)) ** 2:.5f}", "--motion-period", f"{P:.3f}",
                                           "--motion-stop", "900", "--duration", "1100"])
        for P in [3.62, 3.63, 3.64, 3.66, 3.67, 3.68, 4.06, 4.07, 4.08, 4.09, 4.11, 4.12, 4.13, 4.14]
    ],
}


def duration_of(sargs):
    return float(sargs[sargs.index("--duration") + 1]) if "--duration" in sargs else 0.0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("campaign", choices=list(CAMPAIGNS))
    p.add_argument("--only", nargs="*", help="préfixes de scénarios à lancer")
    p.add_argument("--jobs", type=int, default=9)
    p.add_argument("--summary-only", action="store_true", help="n'agrège que les résultats existants")
    args, extra = p.parse_known_args()
    out = os.path.join(HERE, "out", args.campaign)
    os.makedirs(out, exist_ok=True)
    todo = [s for s in CAMPAIGNS[args.campaign] if not args.only or any(s[0].startswith(o) for o in args.only)]

    if not args.summary_only:
        env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")
        running, t0 = [], time.time()
        # Les scénarios les plus longs d'abord
        for name, sargs in sorted(todo, key=lambda s: -duration_of(s[1])):
            while len([r for r in running if r[1].poll() is None]) >= args.jobs:
                time.sleep(2)
            cmd = [sys.executable, os.path.join(HERE, "tether_sim.py"), "--name", name, "--out", out] + sargs + extra
            log = open(os.path.join(out, name + ".log"), "w")
            running.append((name, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)))
            print(f"lancé : {name}", flush=True)
        for name, proc in running:
            proc.wait()
            print(f"terminé : {name} (code {proc.returncode}, {time.time() - t0:.0f} s)", flush=True)

    summarize(out, [n for n, _ in CAMPAIGNS[args.campaign]])


def fmt(v, f="{:.1f}"):
    return "—" if v is None else f.format(v)


def summarize(out, names):
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = []
    fig, ax = plt.subplots(3, 1, figsize=(13, 12), sharex=True)
    for name in names:
        path = os.path.join(out, name + ".json")
        if not os.path.exists(path):
            continue
        info = json.load(open(path))
        if "args" in info:  # prédictions recalculées avec les formules à jour
            sys.path.insert(0, HERE)
            import tether_sim
            info["tilt_static_pred"] = tether_sim.static_tilt_prediction(argparse.Namespace(**info["args"]), info["h"])
            info["roll_prediction"] = tether_sim.roll_prediction_from_info(info)
            info["results"]["doubling_time"] = tether_sim.doubling_from_info(info)
        r = info["results"]
        rows.append(f"| {name} | {info['L0']:.0f} m | {info['roll_prediction']} | {fmt(r['doubling_time'])} | "
                    f"{r['roll_max']:.1f}° | {fmt(r.get('roll_final'))}° | {fmt(r['t_roll_90'], '{:.0f}')} | {r['tilt_max']:.2f}° | "
                    f"{fmt(info.get('tilt_static_pred'), '{:.2f}')}° | {r['wrel_max']:.2f} | "
                    f"{r['g_min']:.3f}–{r['g_max']:.3f} | {fmt(r['dE_max'], '{:.0e}')} | {r['dL_max']:.0e} |")
        d = np.load(os.path.join(out, name + ".npz"))
        ax[0].plot(d["t"], np.abs(d["roll"]).max(axis=1), lw=0.8, label=name)
        ax[1].plot(d["t"], d["tilt"].max(axis=1), lw=0.6, label=name)
        ax[2].plot(d["t"], d["wrel"].max(axis=1), lw=0.6, label=name)
    ax[0].set(title="Roulis autour du câble (max sur les modules)", ylabel="°", yscale="symlog")
    ax[1].set(title="Inclinaison du plancher par rapport à la gravité apparente (max sur les modules)", ylabel="°")
    ax[2].set(title="Rotation parasite ressentie (max sur les modules)", ylabel="°/s", xlabel="t (s)")
    for a in ax:
        a.legend(fontsize=7, ncol=2)
        a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "comparaison.png"), dpi=100)
    plt.close(fig)

    header = ("| Scénario | Câble à vide | Prédiction roulis | Doublement mesuré (s) | Roulis max | Roulis final | 90° atteint à (s) | "
              "Plancher max | Plancher prédit (statique) | Rotation parasite max (°/s) | g ressenti | Dérive énergie | Dérive L |\n"
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    md = header + "\n" + "\n".join(rows) + "\n"
    brk = []
    for name in names:
        path = os.path.join(out, name + ".json")
        if os.path.exists(path):
            r = json.load(open(path))["results"]
            if "break" in r:
                b = r["break"]
                brk.append(f"| {name} | {b['E_cable_kJ']:.0f} | {b['v_whip_max']:.0f} | {b['clear_min']:.1f} (module {b['clear_ship']}, +{b['clear_t']:.0f} s) | "
                           f"{b['T_max_MN']:.2f} | {b['slack_s']:.0f} | " + " / ".join(f"{lo:.1f}–{hi:.1f}" for lo, hi in zip(b["g_min"], b["g_max"]))
                           + " | " + " / ".join(f"{v:.0f}" for v in b["wrel_max"]) + f" | {b['rpm_before']:.2f} → {b['rpm_final']:.2f} | "
                           + " / ".join(f"{v:.0f}" for v in b["r_final"]) + f" | {b['gap_min']:.0f} |")
    if brk:
        md += ("\n| Rupture | Énergie du câble (kJ) | Brin libre max (m/s) | Brin au plus près d'une coque (m) | Tension max restante (MN) | "
               "Détente (s) | g après (m/s², par module) | Rotation parasite max (°/s) | tr/min | Distance finale au centre (m) | Coques au plus près (m) |\n"
               "|---|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(brk) + "\n")
    with open(os.path.join(out, "summary.md"), "w") as fh:
        fh.write(md)
    print(md)


if __name__ == "__main__":
    main()
