"""Fluage des câbles sur l'aller-retour Terre–Mars (carnet § 2.3).

Profil de charge : aller (259 j, 610 t ou 693 t, 3,711 m/s² au pont),
séjour martien câbles détendus (pas de fluage, pas de recouvrance comptée),
retour (259 j, vaisseaux légers, gravité constante ou en rampe jusqu'à 1 g).
Tension d'un côté : référence du simulateur (campagnes `amortisseur`,
`retour`), proportionnelle à la gravité visée au pont pour une masse donnée.

Loi de fluage (régime I, vitesse de plateau, Vlasblom et Bosman 2006) :
    dε/dt = ε̇_ref · sinh(σ/σ0) / sinh(σ_ref/σ0) · exp(−Ea/R · (1/T − 1/T_ref))
σ : contrainte dans la fibre (tension / section de fibre). Points de calage
(publiés, voir CREEP_GRADES) : vitesse à 10 % de la résistance de la fibre à
20 °C (Vlasblom et al., Rio Oil & Gas 2012), vitesse à 900 MPa et 30 °C
(brevets DSM), « ×10 pour +20 °C » (même article) → Ea ≈ 82 kJ/mol.
L'extrapolation vers −70 °C sort du domaine mesuré : on donne aussi le cas
sans gain thermique (20 °C).

Température du câble : gaine blanche, axe vers le Soleil (cable_thermal.py) ;
face éclairée d'un brin Ø 6,9 cm (k = 0,05 W/m/K) : −27 °C à 1 UA, −82 °C à
1,52 UA, interpolée en loi de puissance de la distance au Soleil.

Sortie : out/creep.log, docs/data/creep.json.
"""
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
R_GAS = 8.314
EA = R_GAS * math.log(10) / (1 / 283.15 - 1 / 303.15)  # ×10 pour +20 °C autour de 20 °C
T_REF = 293.15
YEAR = 365.25

# Transfert de Hohmann Terre–Mars (sun_pointing.py)
A_AU, ECC, DAYS = 1.2618, 0.2075, 258.9


def distance_au(day, outbound=True):
    """Distance au Soleil, j jours après le départ (aller : du périhélie à
    l'aphélie ; retour : l'inverse)."""
    M = math.pi * day / DAYS + (0.0 if outbound else math.pi)
    E = M
    for _ in range(30):
        E -= (E - ECC * math.sin(E) - M) / (1 - ECC * math.cos(E))
    return A_AU * (1 - ECC * math.cos(E))


T_LIT_1AU, T_LIT_MARS = 273.15 - 27, 273.15 - 82
T_EXP = math.log(T_LIT_1AU / T_LIT_MARS) / math.log(1.52)


def cable_temp(r_au):
    """Face éclairée d'un brin (K), gaine blanche."""
    return T_LIT_1AU * r_au ** -T_EXP


# Nuances : (vitesse %/an à σ_ref MPa et 20 °C, σ0 MPa, critère de début de
# rupture par fluage (allongement de fluage, %), source)
CREEP_GRADES = {
    "SK75": (10.0, 350.0, 130.0, 10.0, "10 %/an à 10 % de la résistance (Vlasblom 2012)"),
    "SK78": (2.0, 350.0, 130.0, 10.0, "2 %/an à 10 % ; 1,3·10⁻⁵ %/s à 900 MPa et 30 °C (brevet DSM)"),
    "SK99 (comme SK78)": (2.0, 350.0, 130.0, 10.0, "fluage annoncé identique à SK78 (Marlow)"),
    "SK99 (−99 % / SK75)": (0.1, 350.0, 130.0, 10.0, "−99 % par rapport à SK75, résultat préliminaire (English Braids)"),
    "DM20": (0.03, 310.0, 97.0, 3.0, "0,03 %/an à 10 % ; 1,3·10⁻⁶ %/s à 900 MPa et 30 °C (brevet DSM)"),
}

# Câbles comparés : section de fibre par côté (cm²) ; câbles tressés :
# rendement 65 %, +33 % de section (perte d'un quart des fils tolérée) ;
# critère de résistance : 9,06 MN par côté × 3 = 27,2 MN
DESIGN_N = 27.18e6
CABLES = {
    "modèle (Dyneema plein, 3 GPa)": (DESIGN_N / 3.0e9 * 1e4, ["SK75", "SK78"]),
    "SK99 tressé, redondant (4,1 GPa)": (DESIGN_N / (4.1e9 * 0.65) * 1.33 * 1e4, ["SK99 (comme SK78)", "SK99 (−99 % / SK75)"]),
    "DM20 tressé, redondant (3,1 GPa)": (DESIGN_N / (3.1e9 * 0.65) * 1.33 * 1e4, ["DM20"]),
}


def rate(grade, sigma_mpa, T_k):
    """Vitesse de fluage (%/jour)."""
    e_ref, s_ref, s0, _, _ = CREEP_GRADES[grade]
    return (e_ref / YEAR) * math.sinh(sigma_mpa / s0) / math.sinh(s_ref / s0) * math.exp(-EA / R_GAS * (1 / T_k - 1 / T_REF))


def sim_tension(campaign, name, fallback):
    """Tension d'un côté en service (MN) relevée par le simulateur (somme des
    brins), sinon la valeur de repli."""
    p = os.path.join(HERE, "out", campaign, name + ".json")
    try:
        with open(p) as f:
            d = json.load(f)
        r = d["results"]
        strands = d.get("args", {}).get("side_strands", 1) or 1
        return 0.5 * (r["T_min_MN"] + r["T_max_MN"]) * strands, True
    except (OSError, KeyError):
        return fallback, False


def profile(T_out, T_ret_1g, ramp, dt=1.0):
    """Jours, tension d'un côté (MN), température (K) sur l'aller puis le
    retour. ramp : 'constant' (3,711 m/s²), 'lineaire' (3,711 → 9,81 sur le
    retour), 'fin' (rampe sur les 120 derniers jours), '1g' (tout le retour)."""
    days, T, temp = [], [], []
    for d in np.arange(0, DAYS, dt):
        days.append(d); T.append(T_out); temp.append(cable_temp(distance_au(d, True)))
    for d in np.arange(0, DAYS, dt):
        if ramp == "constant":
            g = 3.711
        elif ramp == "lineaire":
            g = 3.711 + (9.81 - 3.711) * d / DAYS
        elif ramp == "fin":
            g = 3.711 + (9.81 - 3.711) * max(0.0, (d - (DAYS - 120)) / 120)
        else:
            g = 9.81
        days.append(DAYS + d); T.append(T_ret_1g * g / 9.81); temp.append(cable_temp(distance_au(d, False)))
    return np.array(days), np.array(T), np.array(temp)


def creep_strain(grade, area_cm2, T_mn, temp, dt=1.0, load_factor=1.0, temp_override=None):
    sig = T_mn * load_factor * 1e6 / (area_cm2 * 1e-4) / 1e6
    tk = temp if temp_override is None else np.full_like(temp, temp_override)
    r = np.array([rate(grade, s, t) for s, t in zip(sig, tk)])
    return np.cumsum(r) * dt, sig


def load_margin(grade, area, T, temp, target, temp_override=None):
    """Facteur sur la charge permanente qui amène le fluage cumulé à `target` %."""
    lo, hi = 1.0, 100.0
    if creep_strain(grade, area, T, temp, load_factor=1.0, temp_override=temp_override)[0][-1] >= target:
        return 0.0  # critère déjà atteint sous la charge nominale
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if creep_strain(grade, area, T, temp, load_factor=mid, temp_override=temp_override)[0][-1] < target:
            lo = mid
        else:
            hi = mid
    return lo


def main():
    lines = []

    def out(s=""):
        print(s); lines.append(s)

    T610, ok1 = sim_tension("amortisseur", "T_perturbation", 1.387)
    T_ret, ok2 = sim_tension("retour", "RT_perturbation", 1.47)
    T693 = T610 * 693 / 610
    out(f"Tensions d'un côté : aller 610 t {T610:.3f} MN{'' if ok1 else ' (repli)'}, 693 t {T693:.3f} MN ; "
        f"retour 250 t à 1 g {T_ret:.3f} MN{'' if ok2 else ' (repli : campagne retour absente)'}")
    out(f"Loi de fluage : Ea = {EA / 1e3:.0f} kJ/mol ; face éclairée {cable_temp(1.0) - 273.15:.0f} °C à 1 UA, "
        f"{cable_temp(1.52) - 273.15:.0f} °C à 1,52 UA")
    # Vérification contre l'article offshore (Vlasblom 2012, tableau 2) : 270 MPa à 16 °C
    for g, yrs, ref in (("SK78", 5, "1,7 %"), ("DM20", 25, "< 0,3 %")):
        e = rate(g, 270.0, 289.15) * yrs * YEAR
        out(f"Contrôle {g} : 270 MPa, 16 °C, {yrs} ans → {e:.2f} % (publié : {ref})")
    out()

    res = {"cables": {}, "profils": {}, "meta": {"T610": T610, "T693": T693, "T_ret_1g": T_ret, "Ea_kJ": EA / 1e3}}
    ramps = [("constant", "retour à 3,711 m/s²"), ("lineaire", "rampe 3,711 → 9,81 m/s² sur le retour"),
             ("fin", "rampe sur les 120 derniers jours"), ("1g", "retour entier à 1 g")]
    for cname, (area, grades) in CABLES.items():
        out(f"== {cname} : {area:.0f} cm² de fibre par côté, contrainte en route {T610 * 1e6 / (area * 1e-4) / 1e6:.0f} MPa (610 t), "
            f"{T693 * 1e6 / (area * 1e-4) / 1e6:.0f} MPa (693 t), {T_ret * 1e6 / (area * 1e-4) / 1e6:.0f} MPa (retour à 1 g)")
        res["cables"][cname] = {"area_cm2": area, "grades": {}}
        for g in grades:
            gres = {}
            out(f"  {g} — {CREEP_GRADES[g][4]}")
            for key, label in ramps:
                for T_out, mlab in ((T610, "610 t"), (T693, "693 t")):
                    days, T, temp = profile(T_out, T_ret, key)
                    e_cold, sig = creep_strain(g, area, T, temp)
                    e_warm, _ = creep_strain(g, area, T, temp, temp_override=T_REF)
                    m05 = load_margin(g, area, T, temp, 0.5)
                    mrup = load_margin(g, area, T, temp, CREEP_GRADES[g][3])
                    m05w = load_margin(g, area, T, temp, 0.5, temp_override=T_REF)
                    mrupw = load_margin(g, area, T, temp, CREEP_GRADES[g][3], temp_override=T_REF)
                    f = lambda m: f"{m:.1f}" if m else "atteint"
                    out(f"    aller {mlab}, {label:40s} : fluage {e_cold[-1]:.2e} % (à 20 °C : {e_warm[-1]:.3f} %) ; "
                        f"facteur sur la charge pour 0,5 % : {f(m05)} (20 °C : {f(m05w)}), "
                        f"pour le début de rupture ({CREEP_GRADES[g][3]:g} %) : {f(mrup)} (20 °C : {f(mrupw)})")
                    gres[f"{key}_{mlab[:3]}"] = dict(creep_cold=e_cold[-1], creep_20C=e_warm[-1], margin05=m05, margin05_20C=m05w,
                                                     margin_rupt=mrup, margin_rupt_20C=mrupw, sigma_max=float(sig.max()))
                    if mlab == "610 t" and cname.startswith("SK99") and g.endswith("SK78)"):
                        res["profils"][key] = dict(days=days[::5].tolist(), T=T[::5].round(4).tolist(),
                                                   temp=(temp[::5] - 273.15).round(1).tolist(),
                                                   creep_20C=creep_strain(g, area, T, temp, temp_override=T_REF)[0][::5].round(5).tolist())
            res["cables"][cname]["grades"][g] = gres
        out()

    # Mode dégradé : brins perdus au départ de l'aller (pire cas), les
    # restants portent tout le côté jusqu'à l'arrivée (693 t, à 20 °C)
    out("Mode dégradé, brins rompus au départ et non réparés, 259 jours à 693 t (fluage à 20 °C / sur la trajectoire) :")
    days = np.arange(0, DAYS, 1.0)
    temp = np.array([cable_temp(distance_au(d)) for d in days])
    for cname, (area, grades) in CABLES.items():
        for g in grades:
            for left, lab in ((2, "un brin rompu"), (1, "deux brins rompus")):
                T = np.full_like(days, T693)
                a = area * left / 3
                e_c = creep_strain(g, a, T, temp)[0][-1]
                e_w = creep_strain(g, a, T, temp, temp_override=T_REF)[0][-1]
                sig = T693 * 1e6 / (a * 1e-4) / 1e6
                out(f"  {cname:34s} {g:22s} {lab:18s} : {sig:4.0f} MPa, fluage {e_w:.3f} % / {e_c:.1e} %")
                res["cables"][cname]["grades"][g][f"degrade_{left}"] = dict(sigma=sig, creep_20C=e_w, creep_cold=e_c)
    out()
    out("Vectran HT : fluage < 0,4 % entre 40 et 58 % de la résistance (fabricant) ; durée de vie en fluage > 40 ans "
        "à 25 % de la résistance (NASA, sangles d'habitats gonflables). Ici < 6 % : négligeable.")

    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(os.path.join(HERE, "out", "creep.log"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(HERE, "docs", "data", "creep.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, separators=(",", ":"))
    print("→ out/creep.log, docs/data/creep.json")


if __name__ == "__main__":
    main()
