#!/usr/bin/env python3
"""Campagne de déploiement (carnet § 5.4) : catalogue des scénarios de
deploy_sim.py et export vers docs/data/deploiement.json.

  deploy_campaign.py run [--jobs 2] [noms...]   lance les scénarios (~20 h de calcul en tout)
  deploy_campaign.py export                     écrit docs/data/deploiement.json

La montée de 0,1 à 1 tr/min vient de la campagne montee_lente de run_scenarios.py.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "deploiement")

LIN = "--r0 60 --rpm0 0.0169 --p -1 --eps 0.25 --rate 0.03 --Tmin 10 --traj-dt 60"
CST = "--r0 60 --rpm0 0.1 --p 0 --rate 0.02 --Tmin 20 --traj-dt 60"
TROIS = "--r0 60 --rpm0 0.1 --p 0 --rate 0.05 --Tmin 20 --strands 3 --segments 12 --strand-long 1 --traj-dt 60"
MI = "--r0 60 --rpm0 0.05 --p 0 --Tmin 10 --spin-after 3600 --traj-dt 60"
LANCER = "--r0 60 --brake --dr0 0.5 --Tmin 50 --duration 6000 --traj-dt 20"

RUNS = {
    # Premier passage, treuils à 0,1 m/s
    "D_libre": "--mode libre --rpm0 1.28 --traj-dt 20",
    "D_tension": "--mode tension --r0 60 --rpm0 0.245 --p 0.5 --traj-dt 20",
    "D_tension_bloque": "--mode tension --r0 60 --rpm0 0.245 --p 0.5 --stall 0 1000 120 --traj-dt 20",
    "D_vitesse": "--mode vitesse --r0 60 --rpm0 0.1 --p 0 --traj-dt 20",
    "D_lancer": f"--mode lancer {LANCER} --rpm0 0.001 --spin-after 1800",
    "D_lancer_frein": f"--mode lancer {LANCER} --rpm0 0.001 --spin-after 1800 --brake-err 1.2",
    "D_lancer_rot": f"--mode lancer {LANCER} --rpm0 0.00286 --p -2",
    "D_lancer_rot_frein": f"--mode lancer {LANCER} --rpm0 0.00286 --p -2 --brake-err 1.2",
    # Déroulement lent
    "D2_lin": f"--mode lent {LIN}",
    "D2_lin_bloque": f"--mode lent {LIN} --stall 0 8000 600",
    "D2_lin_panne": f"--mode lent {LIN} --thrust-out 8000 1800",
    "D2_cst_bloque": f"--mode lent {CST} --stall 0 5000 600",
    "D3_libre": f"--mode lent {TROIS}",
    "D3_ent": f"--mode lent {TROIS} --ties 1",
    # Vitesse constante moitié moindre, puis 0,05 → 0,1 tr/min à plein rayon
    "D4_mi": f"--mode lent {MI} --rate 0.03 --duration 24000",
    "D4_mi_bloque": f"--mode lent {MI} --rate 0.03 --stall 0 8000 600 --duration 25000",
    "D4_mi_ent": f"--mode lent {MI} --rate 0.05 --strands 3 --segments 12 --strand-long 1 --ties 1 --duration 16000",
}

M_SHIP = 610.7   # t, vaisseau et câbles
VE = 300 * 9.80665   # m/s, impulsion spécifique 300 s
V_FINALE = 37.53     # m/s, ωR à 1 tr/min
ergols = lambda dv: M_SHIP * (1 - math.exp(-dv / VE))

CHAMPS = ("t_stop t_end r_end rpm_end T_start_kN T_max_kN T_seg_peak_kN tilt_max wrel_max lat_max "
          "impulse_per_ship propellant_t_per_ship propellant_start_t dv_start E_brake_MJ sdot_max ratio_max "
          "tie_T_max_kN").split()


def lance(noms, jobs):
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")
    os.makedirs(OUT, exist_ok=True)
    attente, actifs = list(noms), []
    while attente or actifs:
        actifs = [p for p in actifs if p.poll() is None]
        while attente and len(actifs) < jobs:
            n = attente.pop(0)
            cmd = ["nice", "-n", "19", sys.executable, os.path.join(HERE, "deploy_sim.py"), "--name", n] + RUNS[n].split()
            with open(os.path.join(OUT, n + ".log"), "w") as log:
                actifs.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=HERE))
        time.sleep(5)


def echantillon(z, n=400):
    """Séries allégées : maximum par intervalle pour l'inclinaison et la tension, valeur courante sinon."""
    t = z["t"]
    bords = np.linspace(0, len(t), min(n, len(t)) + 1).astype(int)
    tilt = z["tilt"].max(axis=1) if z["tilt"].ndim > 1 else z["tilt"]
    r = z["r"].mean(axis=1) if z["r"].ndim > 1 else z["r"]
    w = z["w"].mean(axis=1) if z["w"].ndim > 1 else z["w"]
    a, b = bords[:-1], bords[1:]
    pic = lambda x: [round(float(x[i:j].max()), 4) for i, j in zip(a, b)]
    return {
        "t_h": [round(float(t[j - 1]) / 3600, 4) for j in b],
        "r": [round(float(r[j - 1]), 2) for j in b],
        "rpm": [round(float(w[j - 1]) * 30 / np.pi, 5) for j in b],
        "T_kN": pic(z["T"].max(axis=1) / 1e3),
        "tilt": pic(tilt),
    }


def exporte():
    S = {}
    for n in RUNS:
        p = os.path.join(OUT, n + ".json")
        if not os.path.exists(p):
            print("absent :", n)
            continue
        d = json.load(open(p))
        r = d["results"]
        S[n] = {k: r.get(k) for k in CHAMPS}
        a = d["args"]
        S[n]["args"] = {k: a.get(k) for k in ("r0", "rpm0", "p", "rate", "strands", "segments", "strand_long", "ties")}
        # Lancement : rotation de départ à r0, plus la vitesse radiale du lancer
        depart = ergols(a["rpm0"] * math.pi / 30 * a["r0"] + a.get("dr0", 0.0))
        S[n]["ergols_t"] = round(r["propellant_t_per_ship"] + depart, 3)
        with np.load(os.path.join(OUT, n + ".npz")) as z:
            if n in ("D2_lin", "D2_lin_bloque", "D2_cst_bloque", "D_vitesse", "D4_mi", "D4_mi_bloque"):
                S[n]["serie"] = echantillon(z)
            # Durée sous 5 N à la ferrure. Le champ slack des .npz d'avant le correctif de
            # deploy_sim.py surestime la détente : il voit ≈ 100 N de moins que la tension réelle.
            dt = np.diff(z["t"], prepend=0.0)
            S[n]["t_detente_s"] = round(float(dt[z["T"].min(axis=1) < 5].sum()), 0)
            lat = z["lat"]
            S[n]["lat_end"] = round(float(lat[-1].max() if lat.ndim > 1 else lat[-1]), 3)
    M = {}
    for n, c in (("S_montee_k005", "montee"), ("S_lente_k01", "montee_lente"), ("S_lente_k004", "montee_lente")):
        d = json.load(open(os.path.join(HERE, "out", c, n + ".json")))
        s = d["results"]["spin"]
        with np.load(os.path.join(HERE, "out", c, n + ".npz")) as z:
            F = float(z["thrust"].max())
        M[n] = {"t_reach": s["t_reach"], "propellant_t": s["propellant_t"], "impulse_Ns": s["impulse_Ns"],
                "tilt_max_on": s["tilt_max_on"], "tilt_max_after": s["tilt_max_after"],
                "tilt_max": d["results"]["tilt_max"], "F_max_kN_total": F / 1e3, "k": d["args"]["spin_k"]}
    montee = M["S_lente_k004"]["propellant_t"] / 3   # par vaisseau, 0,1 → 1 tr/min
    bilan = {"ideal_t": round(ergols(V_FINALE), 2), "montee_t": round(montee, 2), "depart_t": S["D4_mi"]["propellant_start_t"]}
    for n in ("D_vitesse", "D2_lin", "D4_mi"):
        bilan[n] = {"deroulement_t": S[n]["ergols_t"], "total_t": round(S[n]["ergols_t"] + montee, 2),
                    "total_3_t": round(3 * (S[n]["ergols_t"] + montee), 1)}
    dest = os.path.join(HERE, "docs", "data", "deploiement.json")
    json.dump({"deroulement": S, "montee": M, "bilan": bilan}, open(dest, "w"), ensure_ascii=False, separators=(",", ":"))
    print(json.dumps(bilan, ensure_ascii=False))
    print(dest, os.path.getsize(dest), "octets")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=("run", "export"))
    p.add_argument("noms", nargs="*")
    p.add_argument("--jobs", type=int, default=2)
    o = p.parse_args()
    if o.action == "run":
        lance(o.noms or list(RUNS), o.jobs)
    else:
        exporte()
