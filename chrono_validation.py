#!/usr/bin/env python3
"""
Validation croisée avec Project Chrono (PyChrono 10).

Même station et même état initial que tether_sim (équilibre en rotation et
perturbations calculés par tether_sim), mais dynamique intégrée par un moteur
indépendant :
- modules = ChBody (inertie, orientation par quaternions, couple gyroscopique) ;
- câble = chaîne de ChBody ponctuels reliés par des ChLinkTSDA
  (ressort-amortisseur), attachés aux modules aux mêmes points décalés ;
- intégrateur implicite HHT + solveur direct creux.

Compare le roulis autour du câble avec la simulation NumPy du même scénario
(relancée ici) et trace les deux courbes.

Usage (environnement Chrono du projet) :
    tools/chrono-env/bin/python chrono_validation.py --name B --module axial --duration 300
"""
import math
import os
import sys
import time

import numpy as np
import pychrono as ch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tether_sim as ts  # noqa: E402


def quat_from_matrix(R):
    """Quaternion (w, x, y, z) d'une matrice de rotation."""
    tr = np.trace(R)
    if tr > 0:
        s = 2 * math.sqrt(tr + 1)
        return 0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s
    i = int(np.argmax(np.diag(R)))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = 2 * math.sqrt(1 + R[i, i] - R[j, j] - R[k, k])
    q = [0.0, 0.0, 0.0, 0.0]
    q[0] = (R[k, j] - R[j, k]) / s
    q[1 + i] = 0.25 * s
    q[1 + j] = (R[j, i] + R[i, j]) / s
    q[1 + k] = (R[k, i] + R[i, k]) / s
    return tuple(q)


def V(v):
    return ch.ChVector3d(float(v[0]), float(v[1]), float(v[2]))


def A(v):
    return np.array([v.x, v.y, v.z])


def build_chrono(st, alpha):
    sysm = ch.ChSystemNSC()
    sysm.SetGravitationalAcceleration(V([0, 0, 0]))
    modules = []
    om = st.omega_world()
    for b in range(st.nb):
        body = ch.ChBody()
        body.SetMass(float(st.Mb[b]))
        body.SetInertiaXX(V(st.Ib[b]))
        body.SetPos(V(st.xb[b]))
        body.SetRot(ch.ChQuaterniond(*quat_from_matrix(st.R[b])))
        body.SetPosDt(V(st.vb[b]))
        body.SetAngVelParent(V(om[b]))
        sysm.AddBody(body)
        modules.append(body)
    nodes = []
    for i in range(st.nf):
        nd = ch.ChBody()
        nd.SetMass(float(st.mn[i]))
        nd.SetInertiaXX(V([1.0, 1.0, 1.0]))
        nd.SetPos(V(st.xn[i]))
        nd.SetPosDt(V(st.vn[i]))
        sysm.AddBody(nd)
        nodes.append(nd)

    def endpoint(p):
        if p < st.nf:
            return nodes[p], V([0, 0, 0])
        a = p - st.nf
        return modules[st.att_body[a]], V(st.att_r[a])

    for s, (i, j) in enumerate(st.seg):
        b1, p1 = endpoint(i)
        b2, p2 = endpoint(j)
        sp = ch.ChLinkTSDA()
        sp.Initialize(b1, b2, True, p1, p2)
        sp.SetRestLength(float(st.ds0[s]))
        sp.SetSpringCoefficient(float(st.k[s]))
        sp.SetDampingCoefficient(float(st.c[s]))
        sysm.AddLink(sp)

    sysm.SetSolver(ch.ChSolverSparseQR())
    sysm.SetTimestepperType(ch.ChTimestepper.Type_HHT)
    hht = ch.CastToChTimestepperHHT(sysm.GetTimestepper())
    hht.SetAlpha(alpha)
    return sysm, modules, nodes


def chrono_state(st, modules, nodes):
    xb = np.array([A(b.GetPos()) for b in modules])
    R = np.array([np.column_stack([A(b.TransformDirectionLocalToParent(V(e))) for e in np.eye(3)]) for b in modules])
    vb = np.array([A(b.GetPosDt()) for b in modules])
    wb = np.array([A(b.GetAngVelParent()) for b in modules])
    xn = np.array([A(n.GetPos()) for n in nodes])
    vn = np.array([A(n.GetPosDt()) for n in nodes])
    com = (st.Mb @ xb + st.mn @ xn) / (st.Mb.sum() + st.mn.sum())
    L = st.Mb @ np.cross(xb, vb) + st.mn @ np.cross(xn, vn)
    for b in range(len(modules)):
        L += R[b] @ (st.Ib[b] * (R[b].T @ wb[b]))
    return xb, R, com, L


def main():
    p = ts.make_parser()
    p.add_argument("--chrono-dt", type=float, default=0.002, help="pas de temps Chrono (s)")
    p.add_argument("--alpha", type=float, default=-0.02, help="paramètre α de HHT (0 = pas de dissipation numérique)")
    args = p.parse_args()
    args.quiet = True
    name = args.name or f"{args.topology}_{args.module}"
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "validation")
    os.makedirs(out, exist_ok=True)

    # 1) Référence NumPy (même scénario)
    args.out = out
    args.name = name + "_numpy"
    t0 = time.time()
    ts.run(args)
    t_np = time.time() - t0
    ref = np.load(os.path.join(out, args.name + ".npz"))

    # 2) Même état initial pour Chrono
    st = ts.Station(args)
    st.relax(verbose=False)
    st.set_rigid_rotation()
    ts.apply_perturbation(st, args)
    L0 = st.angular_momentum()
    eL = L0 / np.linalg.norm(L0)
    sysm, modules, nodes = build_chrono(st, args.alpha)

    rec_t, rec_roll, rec_dL = [], [], []
    n_steps = int(round(args.duration / args.chrono_dt))
    every = max(1, int(round(args.record_dt / args.chrono_dt)))
    t0 = time.time()
    for k in range(n_steps + 1):
        if k % every == 0:
            xb, R, com, L = chrono_state(st, modules, nodes)
            roll, _ = ts.roll_angles(xb, R, com, eL, args.module)
            rec_t.append(sysm.GetChTime())
            rec_roll.append(roll)
            rec_dL.append(np.linalg.norm(L - L0) / np.linalg.norm(L0))
        sysm.DoStepDynamics(args.chrono_dt)
    t_ch = time.time() - t0
    t = np.array(rec_t)
    roll = np.degrees(np.unwrap(np.array(rec_roll), axis=0))
    dL = np.array(rec_dL)

    def growth(tt, rr):
        ra = np.abs(rr).max(axis=1)
        t1 = ts.first_crossing(tt, ra, 1)
        t10 = ts.first_crossing(tt, ra, 10)
        return (math.log(2) * (t10 - t1) / math.log(10)) if (t1 and t10 and t10 > t1) else None

    g_np, g_ch = growth(ref["t"], ref["roll"]), growth(t, roll)
    # Écart entre les deux courbes (interpolées sur la grille Chrono)
    roll_np = np.column_stack([np.interp(t, ref["t"], ref["roll"][:, b]) for b in range(roll.shape[1])])
    diff = np.abs(roll - roll_np).max()
    summary = dict(name=name, duration=args.duration, chrono_dt=args.chrono_dt, alpha=args.alpha,
                   doubling_numpy=g_np, doubling_chrono=g_ch, roll_max_numpy=float(np.abs(ref["roll"]).max()),
                   roll_max_chrono=float(np.abs(roll).max()), max_abs_diff_deg=float(diff),
                   dL_chrono=float(dL.max()), cpu_numpy_s=t_np, cpu_chrono_s=t_ch)
    print(summary)
    import json
    with open(os.path.join(out, name + "_validation.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    np.savez_compressed(os.path.join(out, name + "_chrono.npz"), t=t, roll=roll)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for b in range(roll.shape[1]):
        ax[0].plot(ref["t"], ref["roll"][:, b], lw=1.6, alpha=0.6, label=f"NumPy — module {b}")
        ax[0].plot(t, roll[:, b], lw=0.9, ls="--", label=f"Chrono — module {b}")
    ax[0].set(ylabel="roulis (°)", title=f"{name} : roulis autour du câble — tether_sim (NumPy) vs Project Chrono "
                                          f"(doublement {g_np and round(g_np, 2)} s vs {g_ch and round(g_ch, 2)} s)")
    ax[0].legend(fontsize=8)
    ax[1].plot(t, np.abs(roll - roll_np).max(axis=1), lw=0.8)
    ax[1].set(xlabel="t (s)", ylabel="|écart| (°)", yscale="log", title="Écart entre les deux moteurs")
    fig.tight_layout()
    fig.savefig(os.path.join(out, name + "_validation.png"), dpi=100)


if __name__ == "__main__":
    main()
