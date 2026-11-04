#!/usr/bin/env python3
"""Déploiement des câbles (carnet § 5.3) : les trois vaisseaux partent proches,
câbles courts, et s'écartent jusqu'au triangle final pendant que les treuils
déroulent. Réutilise tether_sim.Station (vaisseaux rigides, ergols, bassin,
câbles unilatéraux) ; seule change la longueur à vide des câbles, commune aux
brins d'un côté, qui croît au cours du temps.

Le câble déroulé est réparti sur tous les segments (longueur à vide et masse
des nœuds croissent ensemble) : le détail de la sortie du tambour n'est pas
modélisé, mais le flux de quantité de mouvement y est négligeable (λ·v² < 1 N).
Le câble sort du vaisseau de tête de chaque côté, qui porte sa réserve.

Modes :
  libre   : rotation lancée à faible rayon, puis plus aucune poussée ; le moment
            cinétique se conserve (ω ∝ r⁻²), treuils à vitesse imposée ;
  tension : poussée tangentielle pendant le déroulement, ω ∝ r^(-p) ; p = 1/2
            garde une tension constante, p = 0 une vitesse de rotation constante ;
  lancer  : sans rotation, vaisseaux lancés vers l'extérieur et freinés par les
            treuils jusqu'à l'arrêt ; rotation ensuite, par poussée tangentielle.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

import run_scenarios
import tether_sim as ts

HERE = os.path.dirname(os.path.abspath(__file__))
RPM = 2 * math.pi / 60
R_END = 358.4    # rayon final du centre de masse (m)
L_END = 578.7    # longueur à vide finale (m)
W_END = 0.1 * RPM


def base_args(extra):
    """Solution retenue (610 t, chicanes, bassin), sans cible de gravité."""
    a, skip, out = list(run_scenarios.TLD3), False, []
    for x in a:
        if skip:
            skip = False
        elif x in ("--rpm", "--accel", "--g-ref-x", "--duration"):
            skip = True
        else:
            out.append(x)
    return ts.make_parser().parse_args(out + extra)


def run(o):
    w0 = o.rpm0 * RPM
    extra = ["--rpm", str(o.rpm0), "--accel", str(w0 ** 2 * o.r0), "--segments", str(o.segments),
             "--side-strands", str(o.strands), "--dv-radial", "0", "--dv-z", "0", "--droll", "0"]
    if o.ties:
        extra += ["--strand-ties", str(o.ties), "--tie-slack", "0.1", "--release-delay", "-1"]
    if o.material:
        extra += ["--material", o.material]
    st = ts.Station(base_args(extra))
    n, ns, nc = st.n, o.strands, st.n_cables
    M_ship = st.m_total / 3
    # Longueur de départ : géométrie droite, moins l'allongement sous la tension d'équilibre
    P, _ = st.points()
    d = P[st.seg[st.cable_first_seg[0] + n - 1, 1]] - P[st.seg[st.cable_first_seg[0], 0]]
    T0 = M_ship * w0 ** 2 * o.r0 / math.sqrt(3)
    EA_side = st.EA * ns
    L = np.full(3, np.linalg.norm(d) / (1 + T0 / EA_side))
    L0 = float(L[0])
    side = np.array([c % 3 for c in range(nc)])
    seg_side = np.repeat(side, n)
    st.ds0[:] = L[seg_side] / n
    st.mn[:] = st.lam * L0 / n
    st._update_stiffness()
    # Réserve de câble : portée par le vaisseau de tête de chaque côté
    lead = np.array([st.topo["cables"][c][0][0] for c in range(3)])
    tail = np.array([st.topo["cables"][c][1][0] for c in range(3)])
    node_cable = np.full(st.nf, -1)
    for c in range(nc):
        f0 = st.cable_first_seg[c]
        for s in range(n - 1):
            node_cable[st.seg[f0 + s, 1]] = c
    node_lead = lead[side[node_cable]]
    node_side = side[node_cable]
    for s_ in range(3):
        st.Mb[lead[s_]] += st.lam * ns * (o.L_end - L0)
    st.set_rigid_rotation()
    if o.dr0:
        u = st.xb * np.array([1.0, 1.0, 0.0])
        rr = np.linalg.norm(u, axis=1)[:, None]
        dv = o.dr0 * u / rr
        st.vb += dv
        if len(st.sm):
            st.vs += dv[st.sb]  # les ergols partent avec leur vaisseau
        for c in range(nc):
            # nœuds : vitesse interpolée entre celles des deux vaisseaux
            f0 = st.cable_first_seg[c]
            bA, bB = lead[side[c]], tail[side[c]]
            for s in range(n - 1):
                st.vn[st.seg[f0 + s, 1]] += dv[bA] + (dv[bB] - dv[bA]) * (s + 1) / n

    def geom():
        c = st.Mb @ st.xb / st.Mb.sum()
        v = st.Mb @ st.vb / st.Mb.sum()
        rv = (st.xb - c) * np.array([1.0, 1.0, 0.0])
        rn = np.linalg.norm(rv, axis=1)
        er = rv / rn[:, None]
        return rn, er, np.sum((st.vb - v) * er, axis=1)

    ez = np.array([0.0, 0.0, 1.0])
    rec = {k: [] for k in ("t", "r", "w", "L", "T", "Tmin", "Tmax", "slack", "tilt", "wrel", "lat", "z", "gap", "F", "sdot")}
    traj = {k: [] for k in ("t", "xb", "R", "xn", "pa")}
    F, *_ = st.spring_forces(P)
    P, rw = st.points()
    F, t_spr, stretch_, *_ = st.spring_forces(P)
    Fth = np.zeros((3, 3))
    zero3 = np.zeros((3, 3))
    Fs, Fbs, Tbs = st.slosh_forces()
    Fi, Fbi, Tbi = st.internal_forces(0.0)
    Td = st.damper_torque()
    t, step, impulse, E_brake, Tpk, t_end, t_stop = 0.0, 0, 0.0, 0.0, 0.0, None, None
    next_rec, next_traj = 0.0, 0.0
    dt = o.cfl * 2 / (2 * math.sqrt(st.k.max() / st.mn.min()))
    sdot = np.zeros(3)
    w_now, rn_m, dr_m = w0, o.r0, o.dr0
    print(f"{o.name} : {o.mode}, r0 {o.r0:g} m, {o.rpm0:g} tr/min, câble {L0:.1f} → {o.L_end:g} m, {M_ship / 1e3:.0f} t par vaisseau, dt {dt * 1e3:.3f} ms", flush=True)
    i_s, j_s = st.seg[:, 0], st.seg[:, 1]
    while True:
        if step % 200 == 0:
            dt = o.cfl * 2 / (2 * math.sqrt(st.k.max() / st.mn.min()))
        # Treuils
        Ts = np.add.reduceat(t_spr[st.cable_first_seg], np.arange(0, 3)) if ns == 1 else np.array([t_spr[st.cable_first_seg[c::3][:ns]].sum() for c in range(3)])
        K = EA_side / L
        for s_ in range(3):
            d_ = o.L_end - L[s_]
            if d_ <= 1e-3:
                sdot[s_] = 0.0
                continue
            if o.stall and o.stall[0] == s_ and o.stall[1] <= t < o.stall[1] + o.stall[2]:
                sdot[s_] = 0.0
                continue
            if o.brake:
                # frein : tension de consigne pour s'arrêter pile en bout de câble
                a_stop = dr_m ** 2 / (2 * d_ / math.sqrt(3)) if dr_m > 0 else 0.0
                Tset = max(M_ship * (w_now ** 2 * rn_m + a_stop) / math.sqrt(3), o.Tmin) * (o.brake_err if s_ == 0 else 1.0)
                # asservissement de tension : anticipation sur la vitesse de
                # séparation des deux vaisseaux, correction sur l'allongement
                u_ = st.xb[tail[s_]] - st.xb[lead[s_]]
                u_ /= np.linalg.norm(u_)
                vsep = float((st.vb[tail[s_]] - st.vb[lead[s_]]) @ u_)
                e_ = float(stretch_[st.cable_first_seg[s_]:st.cable_first_seg[s_] + n].sum())
                sdot[s_] = max(0.0, vsep + (e_ - Tset / K[s_]) / o.brake_tau)
            else:
                v = o.rate * min(1.0, t / o.ramp, math.sqrt(d_ / o.ramp_end) + 1e-3)
                sdot[s_] = v if Ts[s_] > o.Tmin else 0.0
        L += sdot * dt
        L = np.minimum(L, o.L_end)
        st.ds0_rate[:] = sdot[seg_side] / n
        st.ds0[:] = L[seg_side] / n
        st.k = st.EA / st.ds0
        # Masse sortie du tambour : passe du vaisseau de tête aux nœuds (et, pour
        # les demi-segments d'extrémité, à chaque vaisseau)
        delta = st.lam * sdot * dt / n
        dm = delta[node_side]
        m1 = st.mn + dm
        st.vn += (dm / m1)[:, None] * (st.vb[node_lead] - st.vn)
        st.mn = m1
        st.Mb[lead] -= ns * (n - 0.5) * delta
        st.Mb[tail] += ns * 0.5 * delta
        E_brake += float(Ts @ sdot) * dt
        # Poussée tangentielle (recalculée tous les 16 pas : lente)
        if step % 16 == 0:
            st._update_stiffness()
            rn, er, drn = geom()
            rn_m, dr_m = float(rn.mean()), float(drn.mean())
            w_now = st.spin_rate()
            et = np.cross(ez, er)
            done = bool(np.all(L >= o.L_end - 1e-3))
            Fth[:] = 0.0
            if done and t_stop is None:
                t_stop = t
                print(f"  fin du déroulement à t = {t:.0f} s, r = {rn_m:.1f} m, {w_now / RPM:.4f} tr/min", flush=True)
            if not done and o.p is not None:
                wt = w0 * (o.r0 / rn_m) ** o.p
                ff = (2 - o.p) * dr_m * w_now
                f = (M_ship * (ff + rn_m * o.gain * (wt - w_now))) * np.ones(3)
                f[0] *= o.thrust_err
                Fth = f[:, None] * et
            if done and o.spin_after > 0:
                wt = min(W_END, w0 + (W_END - w0) * (t - t_stop) / o.spin_after)
                f = M_ship * rn_m * ((W_END - w0) / o.spin_after * (w_now < W_END) + o.gain * (wt - w_now))
                Fth = max(f, 0.0) * et
        if t >= next_rec:
            P_, rw_ = st.points()
            Pv = st.point_velocities(rw_)
            _, ts_, _, taut, e = st.spring_forces(P_)
            axis = st.R[:, :, 0]
            rn, er, drn = geom()
            mid = st.xn[[st.cable_mid_node[c] for c in range(3)]]
            ends = [(P_[st.seg[st.cable_first_seg[c], 0]], P_[st.seg[st.cable_first_seg[c] + n - 1, 1]]) for c in range(3)]
            lat = [float(ts.point_segment_dist(mid[c:c + 1], a[None], b[None]).min()) for c, (a, b) in enumerate(ends)]
            hA, hB = st.hull_axes()
            rec["t"].append(t)
            rec["r"].append(rn.copy())
            rec["w"].append(st.spin_rate())
            rec["L"].append(L.copy())
            rec["T"].append(Ts.copy())
            rec["Tmin"].append(float(ts_[st.alive].min()))
            rec["Tmax"].append(float(ts_.max()))
            rec["slack"].append(float(np.mean(~taut)))
            rec["tilt"].append(np.degrees(np.arccos(np.clip(np.sum(axis * er, axis=1), -1, 1))))
            rec["wrel"].append(np.degrees(np.linalg.norm(st.omega_world() - np.array([0, 0, st.spin_rate()]), axis=1)))
            rec["lat"].append(max(lat))
            rec["z"].append(float(np.abs(st.xb[:, 2] - st.xb[:, 2].mean()).max()))
            rec["gap"].append(min(ts.segment_segment_dist(hA[a], hB[a], hA[b], hB[b]) for a, b in ((0, 1), (0, 2), (1, 2))) - 2 * st.args.module_radius)
            rec["F"].append(float(np.linalg.norm(Fth, axis=1).sum()))
            rec["sdot"].append(sdot.copy())
            next_rec += o.record_dt
            if int(t) % 300 == 0 and len(rec["t"]) % max(1, int(1 / o.record_dt)) == 0:
                print(f"  t = {t:6.0f} s  r {rn.mean():6.1f} m  L {L.mean():6.1f} m  ω {st.spin_rate() / RPM:.3f} tr/min  T {Ts.mean() / 1e3:7.2f} kN  détendu {np.mean(~taut):.0%}  bascule {rec['tilt'][-1].max():5.1f}°  ṡ {sdot.mean():.3f}", flush=True)
        if o.traj_dt and t >= next_traj:
            traj["t"].append(t)
            traj["xb"].append(st.xb.copy())
            traj["R"].append(st.R.copy())
            traj["xn"].append(st.xn.copy())
            traj["pa"].append(P[st.nf:].copy())
            next_traj += o.traj_dt
        st.kick(dt / 2, F, rw, Fi, Fbi + Fbs + Fth, Tbi + Tbs, Td, Fs)
        st.drift(dt)
        P, rw = st.points()
        F, t_spr, stretch_, *_ = st.spring_forces(P)
        Tpk = max(Tpk, float(t_spr.max()))
        Fs, Fbs, Tbs = st.slosh_forces()
        st.kick(dt / 2, F, rw, Fi, Fbi + Fbs + Fth, Tbi + Tbs, Td, Fs)
        st.damp(dt)
        impulse += dt * float(np.linalg.norm(Fth, axis=1).sum())
        t += dt
        step += 1
        if t_stop is not None and t_end is None:
            t_end = t_stop + o.spin_after + o.hold
        if (t_end is not None and t >= t_end) or t >= o.duration:
            break
        if not np.isfinite(st.xb).all():
            print("  divergence", flush=True)
            break
    rec = {k: np.array(v) for k, v in rec.items()}
    os.makedirs(o.out, exist_ok=True)
    base = os.path.join(o.out, o.name)
    np.savez_compressed(base + ".npz", **rec)
    if o.traj_dt:
        np.savez_compressed(base + "_traj.npz", **{k: np.array(v, dtype=np.float32) for k, v in traj.items()}, seg=st.seg, nf=st.nf,
                            att_body=st.att_body, att_r=st.att_r.astype(np.float32))
    res = dict(steps=step, t_stop=t_stop, t_end=t, r_end=float(rec["r"][-1].mean()), rpm_end=float(rec["w"][-1] / RPM),
               T_start_kN=float(rec["T"][0].mean() / 1e3), T_max_kN=float(rec["T"].max() / 1e3), T_seg_peak_kN=Tpk / 1e3,
               slack_max=float(rec["slack"].max()), tilt_max=float(rec["tilt"].max()), wrel_max=float(rec["wrel"].max()),
               lat_max=float(rec["lat"].max()), z_max=float(rec["z"].max()), gap_min=float(rec["gap"].min()),
               impulse_per_ship=impulse / 3, propellant_t_per_ship=impulse / 3 / (o.isp * ts.G0) / 1e3, E_brake_MJ=E_brake / 1e6,
               sdot_max=float(rec["sdot"].max()), M_ship_t=M_ship / 1e3, L0=L0)
    json.dump(dict(name=o.name, args=vars(o), results=res), open(base + ".json", "w"), indent=1)
    print("  " + json.dumps({k: round(v, 3) if isinstance(v, float) else v for k, v in res.items()}, ensure_ascii=False), flush=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", default="essai")
    p.add_argument("--mode", default="libre")
    p.add_argument("--r0", type=float, default=100.0, help="rayon de départ des centres de masse (m)")
    p.add_argument("--rpm0", type=float, required=True, help="vitesse de rotation de départ (tr/min)")
    p.add_argument("--p", type=float, help="loi de poussée pendant le déroulement : ω ∝ r^(−p) (absent : pas de poussée)")
    p.add_argument("--gain", type=float, default=0.01, help="poussée : gain sur l'écart de vitesse de rotation (s⁻¹)")
    p.add_argument("--rate", type=float, default=0.1, help="treuils à vitesse imposée (m/s)")
    p.add_argument("--ramp", type=float, default=120.0, help="montée en vitesse des treuils (s)")
    p.add_argument("--ramp-end", type=float, default=20.0, help="freinage final des treuils : sur ces derniers mètres")
    p.add_argument("--brake", action="store_true", help="treuils en frein : tension de consigne pour s'arrêter en bout de câble")
    p.add_argument("--brake-tau", type=float, default=1.0, help="frein : constante de temps de l'asservissement de tension (s)")
    p.add_argument("--brake-err", type=float, default=1.0, help="frein du côté 0 : facteur d'erreur sur la consigne")
    p.add_argument("--dr0", type=float, default=0.0, help="vitesse radiale de départ (m/s)")
    p.add_argument("--Tmin", type=float, default=200.0, help="tension minimale d'un côté : en dessous, les treuils s'arrêtent (N)")
    p.add_argument("--spin-after", type=float, default=0.0, help="après le déroulement : montée vers 0,1 tr/min sur cette durée (s)")
    p.add_argument("--thrust-err", type=float, default=1.0, help="poussée du vaisseau 0 : facteur d'erreur")
    p.add_argument("--stall", type=float, nargs=3, help="treuil bloqué : côté, instant, durée")
    p.add_argument("--hold", type=float, default=300.0, help="durée simulée après la fin (s)")
    p.add_argument("--L-end", type=float, default=L_END)
    p.add_argument("--segments", type=int, default=8)
    p.add_argument("--strands", type=int, default=1)
    p.add_argument("--ties", type=int, default=0)
    p.add_argument("--material")
    p.add_argument("--cfl", type=float, default=0.3)
    p.add_argument("--isp", type=float, default=300.0)
    p.add_argument("--duration", type=float, default=20000.0)
    p.add_argument("--record-dt", type=float, default=0.5)
    p.add_argument("--traj-dt", type=float, default=0.0)
    p.add_argument("--out", default=os.path.join(HERE, "out", "deploiement"))
    return p


if __name__ == "__main__":
    a = parser().parse_args()
    if a.stall:
        a.stall = [int(a.stall[0]), a.stall[1], a.stall[2]]
    run(a)
