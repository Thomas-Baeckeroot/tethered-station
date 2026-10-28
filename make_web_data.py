#!/usr/bin/env python3
"""
Exporte les résultats de simulation (out/<campagne>/) vers les pages web
(docs/<page>/data/) : séries temporelles allégées pour les graphiques,
trajectoires dans le repère tournant pour les animations 3D, réponse en
fréquence des balayages, validation Chrono.
"""
import argparse
import glob
import json
import math
import os

import numpy as np

import tether_sim as ts

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

# Animations exportées : (campagne, scénario, début, fin, pas) en secondes
ANIMATIONS = [
    ("rotation", "B_haltere_axial", 0, 600, 1.0),
    ("rotation", "D_echelle_axial", 0, 600, 1.0),
    ("rotation", "F_triangle_axial", 0, 600, 1.0),
    ("internes", "B_amortisseur", 0, 1800, 2.0),
    ("internes", "A_cargaison", 0, 1500, 1.0),
    ("internes", "H_cargaison", 0, 1500, 1.0),
    ("internes", "G_cargaison", 0, 1500, 1.0),
    ("final", "Z_final_cargaison", 0, 1500, 1.0),
    ("final", "Z_final_perturbation", 0, 600, 1.0),
    ("final", "Z_final_cargaison_patte_oie", 0, 1500, 1.0),
    ("final", "Zp_perturbation", 0, 600, 1.0),
    ("starship", "SV2_perturbation", 0, 1800, 2.0),
    ("starship", "SV3_perturbation", 0, 600, 1.0),
    ("mission", "M_perturbation", 0, 600, 1.0),
    ("mission", "M_cargaison_laterale", 0, 1500, 1.0),
    ("ballottement", "L_libre_resonance", 0, 600, 0.5),
    ("ballottement", "L_chicanes_resonance", 0, 600, 0.5),
    ("retenue", "R_perturbation", 0, 600, 1.0),
    ("retenue", "R_cargaison_laterale", 0, 1500, 1.0),
    ("amortisseur", "T_perturbation", 0, 600, 1.0),
    ("amortisseur", "R_resonance_z", 0, 900, 0.5),
    ("amortisseur", "T_resonance_z", 0, 900, 0.5),
    ("rupture", "X_rupture_milieu", 50, 650, 0.5),
    ("rupture", "X_rupture_attache", 50, 350, 0.5),
    ("rupture", "Y_moyeu_rupture", 50, 650, 0.5),
    ("rupture", "Y_moyeu_rupture_largage", 50, 650, 0.5),
    ("rupture", "Z_moyeu_double_rupture", 50, 650, 0.5),
    ("brins", "W_brins2_rupture", 50, 350, 0.5),
]
# Pas des séries exportées (s) : plus fin pour les ruptures (fouet des brins)
SERIES_STEP = {"rupture": 0.5, "brins": 0.5, "montee": 2.0}


def r(x, nd=3):
    """Arrondi récursif pour alléger le JSON."""
    if isinstance(x, np.ndarray):
        return r(x.tolist(), nd)
    if isinstance(x, (list, tuple)):
        return [r(v, nd) for v in x]
    if isinstance(x, float):
        return None if not math.isfinite(x) else round(x, nd)
    return x


def quat(R):
    """Quaternion (x, y, z, w) d'une matrice de rotation (convention three.js)."""
    tr = np.trace(R)
    if tr > 0:
        s = 2 * math.sqrt(tr + 1)
        w, x, y, z = 0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s
    else:
        i = int(np.argmax(np.diag(R)))
        j, k = (i + 1) % 3, (i + 2) % 3
        s = 2 * math.sqrt(1 + R[i, i] - R[j, j] - R[k, k])
        q = [0.0] * 4
        q[0] = (R[k, j] - R[j, k]) / s
        q[1 + i] = 0.25 * s
        q[1 + j] = (R[j, i] + R[i, j]) / s
        q[1 + k] = (R[k, i] + R[i, k]) / s
        w, x, y, z = q
    return [x, y, z, w]


def export_series(campaign, dest, step=1.0):
    os.makedirs(os.path.join(dest, "series"), exist_ok=True)
    summary = {}
    for path in sorted(glob.glob(os.path.join(OUT, campaign, "*.json"))):
        name = os.path.basename(path)[:-5]
        info = json.load(open(path))
        if "args" in info:  # prédictions recalculées avec les formules à jour
            info["tilt_static_pred"] = ts.static_tilt_prediction(argparse.Namespace(**info["args"]), info["h"])
            info["roll_prediction"] = ts.roll_prediction_from_info(info)
            info["results"]["doubling_time"] = ts.doubling_from_info(info)
        summary[name] = info
        d = np.load(os.path.join(OUT, campaign, name + ".npz"))
        t = d["t"]
        # Maxima par vaisseau (masses inégales : le vaisseau habité seul compte)
        info["results"]["tilt_max_ship"] = r(d["tilt"].max(axis=0), 4)
        info["results"]["g_min_ship"] = r(d["g"].min(axis=0), 5)
        info["results"]["g_max_ship"] = r(d["g"].max(axis=0), 5)
        k = max(1, int(round(step / (t[1] - t[0]))))
        ser = dict(t=r(t[::k], 1), roll=r(d["roll"][::k].T, 2), tilt=r(d["tilt"][::k].T, 3),
                   wrel=r(d["wrel"][::k].T, 3), g=r(d["g"][::k].T, 5))
        if "s" in d.files:
            ser["s"] = r(d["s"][::k], 2)
        if "slosh" in d.files and d["slosh"].size:
            ser["slosh"] = r(d["slosh"][::k].T, 3)
        if info.get("motion") == "sweep":
            ser["sweep"] = sweep_response(d, info, f1=info["args"].get("sweep_f1", 0.25))
        if "break" in info or info.get("hub_mass_t"):
            # Tension de crête par câble (MN), distance des vaisseaux au centre,
            # vitesse de rotation d'ensemble, distances aux coques
            ser["Tc"] = r(d["Tc"][::k].T / 1e6, 3)
            ser["rship"] = r(d["rship"][::k].T, 1)
            ser["rpm"] = r(d["wsys"][::k] * 60 / (2 * math.pi), 4)
            ser["gap"] = r(d["gap"][::k].min(axis=1), 1)
            if d["clear"].size:
                ser["clear"] = r(d["clear"][::k].T, 1)
                ser["vwhip"] = r(d["vwhip"][::k], 1)
        if "spin" in info:
            # Mise en rotation : vitesse (tr/min), poussée totale (kN), tension
            # des côtés (MN)
            ser["rpm"] = r(d["wsys"][::k] * 60 / (2 * math.pi), 4)
            ser["thrust"] = r(d["thrust"][::k] / 1e3, 2)
            ser["T"] = r(d["T"][::k] / 1e6, 4)
        with open(os.path.join(dest, "series", name + ".json"), "w") as fh:
            json.dump(ser, fh, separators=(",", ":"))
    return summary


def sweep_response(d, info, f0=0.004, f1=0.25, t0=60.0):
    """Amplitude de l'inclinaison du plancher (angle ≥ 0 : max sur la
    fenêtre) et du roulis (demi-amplitude crête à crête) du module 0 en
    fonction de la fréquence instantanée du balayage."""
    t = d["t"]
    t1 = info["args"]["duration"] - 60
    tilt = d["tilt"][:, 0]
    roll = d["roll"][:, 0]
    s = d["s"]
    out = []
    # fenêtres contiguës : chaque fréquence prend le maximum entre les
    # milieux de ses voisines (au moins ±0,75 période), pour ne manquer aucun pic
    fs = np.geomspace(f0 * 1.05, f1 * 0.98, 60)
    tc = t0 + (fs - f0) / (f1 - f0) * (t1 - t0)
    edges = np.concatenate([[tc[0]], (tc[1:] + tc[:-1]) / 2, [tc[-1]]])
    for k, f in enumerate(fs):
        half = 0.75 / f
        m = (t > min(edges[k], tc[k] - half)) & (t < max(edges[k + 1], tc[k] + half))
        if m.sum() < 10:
            continue
        out.append([f, float(tilt[m].max()), float(np.ptp(roll[m]) / 2), float(np.ptp(s[m]) / 2)])
    return r(out, 4)


def export_anim(campaign, name, ta, tb, step, dest):
    path = os.path.join(OUT, campaign, name + "_traj.npz")
    if not os.path.exists(path):
        print(f"  (pas de trajectoire pour {name})")
        return None
    d = np.load(path)
    t = d["t"].astype(float)
    k = max(1, int(round(step / (t[1] - t[0]))))
    idx = np.where((t >= ta) & (t <= tb))[0][::k]
    w = float(d["omega"])
    frames = []
    for i in idx:
        # Repère tournant : rotation de −ω·t autour de z
        a = -w * t[i]
        Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
        xb = d["xb"][i] @ Rz.T
        xn = d["xn"][i] @ Rz.T
        pa = d["pa"][i] @ Rz.T
        q = [quat(Rz @ d["R"][i][b]) for b in range(len(xb))]
        fr = dict(t=round(float(t[i]), 1), xb=r(xb, 2), q=r(q, 5), xn=r(xn, 2), pa=r(pa, 2))
        if d["xi"].shape[1]:
            fr["xi"] = r(d["xi"][i] @ Rz.T, 2)
        if "xs" in d.files and d["xs"].shape[1]:
            # Ergols : écart de chaque masse ballottante à son articulation, repère du vaisseau
            Rb = d["R"][i][d["sb"]]
            off = d["xs"][i] - d["xb"][i][d["sb"]] - np.einsum("bij,bj->bi", Rb, d["sh"])
            fr["sd"] = r(np.einsum("bji,bj->bi", Rb, off), 4)
        frames.append(fr)
    info = json.load(open(os.path.join(OUT, campaign, name + ".json")))
    radius, length = float(d["module_radius"]), float(d["module_length"])
    extent = float(np.linalg.norm(d["xb"][idx][:, :, :2], axis=2).max() + length)
    anim = dict(name=name, seg=d["seg"].tolist(), nf=int(d["nf"]), module=str(d["module"]),
                radius=radius, length=length, omega=w,
                shape="starship" if (radius, length) == (4.5, 50.0) else "cylinder",
                bi=d["bi"].tolist(),
                slosh=dict(sb=d["sb"].tolist(), sh=r(d["sh"], 3), sm=r(d["sm"] / 1e3, 1)) if "sb" in d.files and len(d["sb"]) else None,
                info=dict(topology=info["topology"], module=info["module"], R=info["R"], extent=round(extent, 1),
                                               motion=info.get("motion"), motion_mass_t=info.get("motion_mass_t")),
                frames=frames)
    if "break" in info:
        anim["cut"] = dict(seg=info["break"]["seg"], t=round(info["break"]["t"], 2))
        if "released" in info["break"]:
            anim["release"] = dict(segs=info["break"]["released"]["segs"], t=round(info["break"]["released"]["t"], 2))
    if info.get("hub_mass_t"):
        anim["hub"] = [0]  # le moyeu est le premier nœud libre
    os.makedirs(os.path.join(dest, "anim"), exist_ok=True)
    with open(os.path.join(dest, "anim", name + ".json"), "w") as fh:
        json.dump(anim, fh, separators=(",", ":"))
    return len(frames)


def export_validation(dest):
    res = {}
    for path in sorted(glob.glob(os.path.join(OUT, "validation", "*_validation.json"))):
        v = json.load(open(path))
        name = v["name"]
        ch = np.load(os.path.join(OUT, "validation", name + "_chrono.npz"))
        npy = np.load(os.path.join(OUT, "validation", name + "_numpy.npz"))
        k = max(1, int(round(0.5 / (ch["t"][1] - ch["t"][0]))))
        kn = max(1, int(round(0.5 / (npy["t"][1] - npy["t"][0]))))
        v["chrono"] = dict(t=r(ch["t"][::k], 1), roll=r(ch["roll"][::k].T, 2))
        v["numpy"] = dict(t=r(npy["t"][::kn], 1), roll=r(npy["roll"][::kn].T, 2))
        res[name] = v
    conv = {}
    for name in ("B_conv_ref", "B_conv_seg32", "B_conv_cfl015"):
        p = os.path.join(OUT, "validation", name + ".json")
        if os.path.exists(p):
            conv[name] = json.load(open(p))["results"]
    with open(os.path.join(dest, "validation.json"), "w") as fh:
        json.dump(dict(chrono=res, convergence=conv), fh, separators=(",", ":"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dest", default=os.path.join(HERE, "docs", "data"))
    args = p.parse_args()
    os.makedirs(args.dest, exist_ok=True)
    summary = {}
    for campaign in ("rotation", "internes", "final", "starship", "mission", "ballottement", "retenue", "amortisseur", "rupture",
                     "moyeu", "montee", "lox", "masses", "brins"):
        if os.path.isdir(os.path.join(OUT, campaign)):
            summary[campaign] = export_series(campaign, args.dest, SERIES_STEP.get(campaign, 1.0))
            print(f"séries : {campaign} ({len(summary[campaign])} scénarios)")
    with open(os.path.join(args.dest, "summary.json"), "w") as fh:
        json.dump(r(summary, 5), fh, separators=(",", ":"), ensure_ascii=False)
    for campaign, name, ta, tb, step in ANIMATIONS:
        n = export_anim(campaign, name, ta, tb, step, args.dest)
        if n:
            print(f"animation : {name} ({n} images)")
    export_validation(args.dest)
    print("validation exportée")


if __name__ == "__main__":
    main()
