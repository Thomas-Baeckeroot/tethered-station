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

Starships (--slosh) : ergols en pendules = ChBody ponctuels reliés à
l'articulation par un ChLinkTSDA (tige raide amortie), amortisseur latéral
par rapport à la paroi appliqué par accumulateur à chaque pas ; câbles
unilatéraux (ressort-amortisseur qui ne pousse pas) ; rupture d'un câble
(--break-*) et largage des morceaux (--release-delay) : liens retirés.

Compare le roulis autour du câble avec la simulation NumPy du même scénario
(relancée ici) et trace les deux courbes ; pour les Starships, aussi
l'inclinaison ressentie du plancher, la tension des câbles, l'écart des
ergols et la distance au centre.

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


class Unilateral(ch.ForceFunctor):
    """Câble : tire seulement (force > 0 en compression dans la convention de ChLinkTSDA)."""

    def __init__(self, k, c):
        super().__init__()
        self.k, self.c = k, c

    def evaluate(self, time, rest_length, length, vel, link):
        if length <= rest_length:
            return 0.0
        return min(0.0, -self.k * (length - rest_length) - self.c * vel)

    Evaluate = evaluate


def build_chrono(st, alpha, unilateral=False):
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

    springs, functors = [], []
    for s, (i, j) in enumerate(st.seg):
        b1, p1 = endpoint(i)
        b2, p2 = endpoint(j)
        sp = ch.ChLinkTSDA()
        sp.Initialize(b1, b2, True, p1, p2)
        sp.SetRestLength(float(st.ds0[s]))
        if unilateral:
            fn = Unilateral(float(st.k[s]), float(st.c[s]))
            functors.append(fn)
            sp.RegisterForceFunctor(fn)
        else:
            sp.SetSpringCoefficient(float(st.k[s]))
            sp.SetDampingCoefficient(float(st.c[s]))
        sysm.AddLink(sp)
        springs.append(sp)
    # Ergols : masse ponctuelle, tige = ressort raide amorti vers l'articulation
    bobs, rods = [], []
    for q in range(len(st.sm)):
        nd = ch.ChBody()
        nd.SetMass(float(st.sm[q]))
        nd.SetInertiaXX(V([1.0, 1.0, 1.0]))
        nd.SetPos(V(st.xs[q]))
        nd.SetPosDt(V(st.vs[q]))
        sysm.AddBody(nd)
        rod = ch.ChLinkTSDA()
        rod.Initialize(modules[st.sb[q]], nd, True, V(st.sh[q]), V([0, 0, 0]))
        rod.SetRestLength(float(st.sL[q]))
        rod.SetSpringCoefficient(float(st.s_k[q]))
        rod.SetDampingCoefficient(float(st.s_cr[q]))
        sysm.AddLink(rod)
        bobs.append(nd)
        rods.append(rod)

    sysm.SetSolver(ch.ChSolverSparseQR())
    sysm.SetTimestepperType(ch.ChTimestepper.Type_HHT)
    hht = ch.CastToChTimestepperHHT(sysm.GetTimestepper())
    hht.SetAlpha(alpha)
    acc = dict(ship=[b.AddAccumulator() for b in modules], bob=[b.AddAccumulator() for b in bobs])
    return sysm, modules, nodes, dict(springs=springs, functors=functors, bobs=bobs, rods=rods, acc=acc)


def lateral_damping(st, modules, ex):
    """Amortisseur latéral des ergols (comme tether_sim.slosh_forces) : force
    sur la masse, réaction sur le vaisseau au même point ; constantes sur le pas."""
    for q, nd in enumerate(ex["bobs"]):
        b = st.sb[q]
        body = modules[b]
        xs, vs = A(nd.GetPos()), A(nd.GetPosDt())
        xb, vb, om = A(body.GetPos()), A(body.GetPosDt()), A(body.GetAngVelParent())
        xh = A(body.TransformPointLocalToParent(V(st.sh[q])))
        e = (xs - xh) / np.linalg.norm(xs - xh)
        vrel = vs - (vb + np.cross(om, xs - xb))
        F = -st.s_c[q] * (vrel - (vrel @ e) * e)
        nd.EmptyAccumulator(ex["acc"]["bob"][q])
        nd.AccumulateForce(ex["acc"]["bob"][q], V(F), V(xs), False)
    for b, body in enumerate(modules):
        body.EmptyAccumulator(ex["acc"]["ship"][b])
    for q, nd in enumerate(ex["bobs"]):
        b = st.sb[q]
        F = A(nd.GetAccumulatedForce(ex["acc"]["bob"][q]))
        modules[b].AccumulateForce(ex["acc"]["ship"][b], V(-F), nd.GetPos(), False)


def chrono_state(st, modules, nodes, bobs=()):
    xb = np.array([A(b.GetPos()) for b in modules])
    R = np.array([np.column_stack([A(b.TransformDirectionLocalToParent(V(e))) for e in np.eye(3)]) for b in modules])
    vb = np.array([A(b.GetPosDt()) for b in modules])
    wb = np.array([A(b.GetAngVelParent()) for b in modules])
    xn = np.array([A(n.GetPos()) for n in nodes])
    vn = np.array([A(n.GetPosDt()) for n in nodes])
    xs = np.array([A(n.GetPos()) for n in bobs]).reshape(-1, 3)
    vs = np.array([A(n.GetPosDt()) for n in bobs]).reshape(-1, 3)
    # centre (comme tether_sim) : vaisseaux, ergols et moyeu, sans les nœuds des câbles
    mh = np.zeros(len(nodes))
    if st.hub_m > 0:
        mh[0] = st.mn[0]
    com = (st.Mb @ xb + mh @ xn + st.sm @ xs) / (st.Mb.sum() + mh.sum() + st.sm.sum())
    L = st.Mb @ np.cross(xb, vb) + st.mn @ np.cross(xn, vn) + st.sm @ np.cross(xs, vs)
    for b in range(len(modules)):
        L += R[b] @ (st.Ib[b] * (R[b].T @ wb[b]))
    return xb, R, com, L, xs


def seg_tension(st, s, P, Pv):
    """Tension d'un segment (ressort + amortisseur, câble qui ne pousse pas)."""
    i, j = st.seg[s]
    d = P[j] - P[i]
    ln = np.linalg.norm(d)
    if ln <= st.ds0[s]:
        return 0.0
    return max(0.0, st.k[s] * (ln - st.ds0[s]) + st.c[s] * (Pv[j] - Pv[i]) @ (d / ln))


def endpoints(st, modules, nodes):
    """Positions et vitesses des points des câbles : nœuds libres puis attaches."""
    P = [A(n.GetPos()) for n in nodes]
    Pv = [A(n.GetPosDt()) for n in nodes]
    for a in range(len(st.att_body)):
        body = modules[st.att_body[a]]
        P.append(A(body.TransformPointLocalToParent(V(st.att_r[a]))))
        Pv.append(A(body.PointSpeedLocalToParent(V(st.att_r[a]))))
    return np.array(P), np.array(Pv)


def main():
    p = ts.make_parser()
    p.add_argument("--chrono-dt", type=float, default=0.002, help="pas de temps Chrono (s)")
    p.add_argument("--alpha", type=float, default=-0.02, help="paramètre α de HHT (0 = pas de dissipation numérique)")
    args = p.parse_args()
    if args.motion != "none":
        raise SystemExit("masses internes pilotées : non reprises dans Chrono")
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
    ships = st.ships is not None
    brk = args.break_cable
    sysm, modules, nodes, ex = build_chrono(st, args.alpha, unilateral=ships or brk >= 0)
    k_brk = cut = None
    if brk >= 0:
        f0 = st.cable_first_seg[brk]
        k_brk = f0 + min(int(args.break_at * st.n), st.n - 1)
        cut = [f0, f0 + st.n - 1]

    rec = {k: [] for k in ("t", "roll", "dL", "tilt", "T", "slosh", "rship")}
    n_steps = int(round(args.duration / args.chrono_dt))
    every = max(1, int(round(args.record_dt / args.chrono_dt)))
    removed = set()
    t_break = None
    t0 = time.time()
    for k in range(n_steps + 1):
        tc = k * args.chrono_dt
        if k_brk is not None and t_break is None and tc >= args.break_time:
            sysm.RemoveLink(ex["springs"][k_brk])
            removed.add(k_brk)
            t_break = tc
        if t_break is not None and args.release_delay >= 0 and tc >= t_break + args.release_delay:
            for s_ in cut:
                if s_ not in removed:
                    sysm.RemoveLink(ex["springs"][s_])
                    removed.add(s_)
        if ships:
            lateral_damping(st, modules, ex)
        if k % every == 0:
            xb, R, com, L, xs = chrono_state(st, modules, nodes, ex["bobs"])
            roll, _ = ts.roll_angles(xb, R, com, eL, args.module)
            rec["t"].append(tc)
            rec["roll"].append(roll)
            rec["dL"].append(np.linalg.norm(L - L0) / np.linalg.norm(L0))
            if ships:
                # Inclinaison ressentie : plancher / force spécifique sur la structure (= accélération du centre de masse rigide)
                up = np.einsum("bij,bj->bi", R, st.up_body)
                a = np.array([A(b.GetPosDt2()) for b in modules])
                na = np.linalg.norm(a, axis=1)
                rec["tilt"].append(np.where(na > 0, np.degrees(np.arccos(np.clip(np.sum(up * a, axis=1) / np.where(na > 0, na, 1), -1, 1))), 0.0))
                P, Pv = endpoints(st, modules, nodes)
                rec["T"].append([0.0 if s_ in removed else seg_tension(st, s_, P, Pv) for s_ in st.cable_first_seg])
                b0 = st.sb == 0
                xh = np.array([A(modules[0].TransformPointLocalToParent(V(h))) for h in st.sh[b0]])
                d = xs[b0] - xh
                ax = R[0][:, 0]
                rec["slosh"].append(np.linalg.norm(d - np.outer(d @ ax, ax), axis=1))
                rec["rship"].append(np.linalg.norm((xb - com)[:, :2], axis=1))
        sysm.DoStepDynamics(args.chrono_dt)
    t_ch = time.time() - t0
    t = np.array(rec["t"])
    roll = np.degrees(np.unwrap(np.array(rec["roll"]), axis=0))
    dL = np.array(rec["dL"])

    def growth(tt, rr):
        ra = np.abs(rr).max(axis=1)
        t1 = ts.first_crossing(tt, ra, 1)
        t10 = ts.first_crossing(tt, ra, 10)
        return (math.log(2) * (t10 - t1) / math.log(10)) if (t1 and t10 and t10 > t1) else None

    def interp(key, arr):
        return np.column_stack([np.interp(t, ref["t"], ref[key][:, b]) for b in range(arr.shape[1])])

    g_np, g_ch = growth(ref["t"], ref["roll"]), growth(t, roll)
    # Écart entre les deux courbes (interpolées sur la grille Chrono)
    diff = np.abs(roll - interp("roll", roll)).max()
    summary = dict(name=name, duration=args.duration, chrono_dt=args.chrono_dt, alpha=args.alpha,
                   doubling_numpy=g_np, doubling_chrono=g_ch, roll_max_numpy=float(np.abs(ref["roll"]).max()),
                   roll_max_chrono=float(np.abs(roll).max()), max_abs_diff_deg=float(diff),
                   dL_chrono=float(dL.max()), cpu_numpy_s=t_np, cpu_chrono_s=t_ch)
    extra = {}
    if ships:
        for key in ("tilt", "T", "slosh", "rship"):
            extra[key] = np.array(rec[key])
        after = t >= (args.break_time if brk >= 0 else 0.0)
        summary.update(starship=True, break_cable=brk, break_time=args.break_time if brk >= 0 else None,
                       tilt_max_numpy=float(ref["tilt"][:, 0].max()), tilt_max_chrono=float(extra["tilt"][:, 0].max()),
                       T_max_numpy_MN=float(ref["T"].max() / 1e6), T_max_chrono_MN=float(extra["T"].max() / 1e6),
                       slosh_max_numpy=[float(v) for v in ref["slosh"].max(axis=0)],
                       slosh_max_chrono=[float(v) for v in extra["slosh"].max(axis=0)],
                       rship_max_numpy=float(ref["rship"][ref["t"] >= (args.break_time if brk >= 0 else 0)].max()),
                       rship_max_chrono=float(extra["rship"][after].max()),
                       tilt_diff_max=float(np.abs(extra["tilt"] - interp("tilt", extra["tilt"])).max()),
                       T_diff_max_MN=float(np.abs(extra["T"] - interp("T", extra["T"])).max() / 1e6))
    print(summary)
    import json
    with open(os.path.join(out, name + "_validation.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    np.savez_compressed(os.path.join(out, name + "_chrono.npz"), t=t, roll=roll, **extra)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = 4 if ships else 2
    fig, ax = plt.subplots(rows, 1, figsize=(11, 3.5 * rows), sharex=True)
    for b in range(roll.shape[1]):
        ax[0].plot(ref["t"], ref["roll"][:, b], lw=1.6, alpha=0.6, label=f"NumPy — module {b}")
        ax[0].plot(t, roll[:, b], lw=0.9, ls="--", label=f"Chrono — module {b}")
    ax[0].set(ylabel="roulis (°)", title=f"{name} : roulis autour du câble — tether_sim (NumPy) vs Project Chrono "
                                          f"(doublement {g_np and round(g_np, 2)} s vs {g_ch and round(g_ch, 2)} s)")
    ax[0].legend(fontsize=8)
    if ships:
        ax[1].plot(ref["t"], ref["tilt"][:, 0], lw=1.6, alpha=0.6, label="NumPy")
        ax[1].plot(t, extra["tilt"][:, 0], lw=0.9, ls="--", label="Chrono")
        ax[1].set(ylabel="plancher, vaisseau 0 (°)")
        ax[1].legend(fontsize=8)
        for c in range(extra["T"].shape[1]):
            ax[2].plot(ref["t"], ref["T"][:, c] / 1e6, lw=1.6, alpha=0.6)
            ax[2].plot(t, extra["T"][:, c] / 1e6, lw=0.9, ls="--")
        ax[2].set(ylabel="tension, 1er segment (MN)")
    ax[-1].plot(t, np.abs(roll - interp("roll", roll)).max(axis=1), lw=0.8)
    ax[-1].set(xlabel="t (s)", ylabel="|écart| roulis (°)", yscale="log", title="Écart entre les deux moteurs")
    fig.tight_layout()
    fig.savefig(os.path.join(out, name + "_validation.png"), dpi=100)


if __name__ == "__main__":
    main()
