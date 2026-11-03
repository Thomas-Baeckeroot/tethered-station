#!/usr/bin/env python3
"""Retour du brin rompu vers le vaisseau 0 (notebook § 7.4) : position du brin
rompu dans le repère du vaisseau 0 (distance à la pointe le long de l'axe,
écart latéral dans le plan de rotation, + vers l'avant du mouvement), toutes
les secondes pendant 12 s après la rupture, pour quelques scénarios de la
campagne `entretoises` : référence (coupe-câbles à 1 s), bras de déport de
11 m, longe qui retient le morceau, entretoises tous les 48 m.

Lit out/entretoises/<nom>_traj.npz et <nom>.json, écrit docs/data/snapback.json.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCEN = [("E_reference", "Coupe-câbles seuls"), ("E_bras_16m", "Bras de déport (attaches à ±16 m)"),
        ("E_longe", "Longe : morceau retenu à la ferrure"), ("E_rupture", "Entretoises tous les 48 m")]
TIMES = np.arange(0, 12.01, 1.0)
WIN = dict(ax=(-90.0, 75.0), y=(-45.0, 45.0))


def chain_positions(d, i, ns, f0=0):
    """Positions des points du câble 0 (attache, nœuds, attache) à l'image i."""
    seg, nf = d["seg"], int(d["nf"])
    idx = [seg[f0][0]] + [seg[f0 + s][1] for s in range(ns)]
    xn, pa = d["xn"][i], d["pa"][i]
    return np.array([xn[k] if k < nf else pa[k - nf] for k in idx])


def scenario(name):
    base = os.path.join(HERE, "out", "entretoises", name)
    d = np.load(base + "_traj.npz")
    info = json.load(open(base + ".json"))
    brk = info["break"]
    ns = info["args"]["segments"]
    x_c = info["ship"]["x_c"]
    k_brk = brk["seg"]                       # segment rompu (câble 0 : indices 0..ns-1)
    rel = brk.get("released")
    t = d["t"]
    # brins intacts du même côté : câbles 3 et 6, confondus avec le câble 0 au départ
    frames = []
    for dt in TIMES:
        i = int(np.argmin(np.abs(t - (brk["t"] + dt))))
        R, xb = d["R"][i][0], d["xb"][i][0]

        def body(P):
            r = (P - xb) @ R
            return np.column_stack([r[:, 0] + x_c, r[:, 1]])

        P = body(chain_positions(d, i, ns))
        Q = body(chain_positions(d, i, ns, f0=3 * ns))
        # morceaux du brin rompu : rupture entre les points k_brk et k_brk+1 ;
        # largage : segments d'attache coupés (extrémités retirées)
        cut = {k_brk}
        if rel and t[i] >= rel["t"]:
            cut |= set(rel["segs"])
        pieces, cur = [], [0]
        for s in range(ns):
            if s in cut:
                pieces.append(cur)
                cur = [s + 1]
            else:
                cur.append(s + 1)
        pieces.append(cur)
        # morceaux qui passent dans la fenêtre élargie (le morceau côté vaisseau 1 en sort)
        near = [pc for pc in pieces if len(pc) > 1 and np.any((np.abs(P[pc, 0]) < 200) & (np.abs(P[pc, 1]) < 150))]
        polys = [[[round(float(P[k, 0]), 1), round(float(P[k, 1]), 1)] for k in pc] for pc in near]
        frames.append(dict(dt=float(dt), broken=polys,
                           intact=[[round(float(q[0]), 2), round(float(q[1]), 2)] for q in Q[: ns // 2 + 1]]))
    res = info["results"]["break"]
    return dict(contact_t=res["contact_t"], clear_min=res["clear_min"], tilt_max=info["results"]["tilt_max"],
                T_max_MN=res["T_max_MN"], spread=info["args"]["spread"], x_attach=info["args"]["attach_x"],
                frames=frames)


def main():
    out = dict(window=WIN, hull=dict(radius=4.5, length=50.0, nose=14.0, x_c=None), scenarios={})
    for name, label in SCEN:
        if not os.path.exists(os.path.join(HERE, "out", "entretoises", name + "_traj.npz")):
            print(f"absent : {name}")
            continue
        sc = scenario(name)
        sc["label"] = label
        out["scenarios"][name] = sc
        print(f"{name:12s} contact {sc['contact_t']} s, distance min {sc['clear_min']:.1f} m, plancher {sc['tilt_max']:.1f}°")
    del out["hull"]["x_c"]
    path = os.path.join(HERE, "docs", "data", "snapback.json")
    with open(path, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"écrit : {path} ({os.path.getsize(path) / 1e3:.0f} ko)")


if __name__ == "__main__":
    main()
