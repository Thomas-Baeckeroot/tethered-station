#!/usr/bin/env python3
"""Tests rapides du simulateur (quelques minutes en tout) :

  .venv/bin/python -m unittest discover tests

Ils vérifient la géométrie de la solution retenue, la conservation de
l'énergie et du moment cinétique, le modèle de masse, l'amortissement des
câbles et quelques options,
sans relancer les campagnes (plusieurs heures)."""
import json
import math
import os
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import run_scenarios as rs  # noqa: E402
import tether_sim as ts  # noqa: E402


def simule(nom, args, dossier):
    ts.run(ts.make_parser().parse_args(["--name", nom, "--out", dossier, "--quiet"] + args))
    with open(os.path.join(dossier, nom + ".json")) as fh:
        return json.load(fh)


class Geometrie(unittest.TestCase):
    def test_solution_retenue(self):
        st = ts.Station(ts.make_parser().parse_args(rs.TLD))
        self.assertAlmostEqual(st.R_ref, 338.4, delta=0.1)           # rayon au pont principal
        self.assertAlmostEqual(st.area * 1e4, 135.9, delta=0.3)      # câble de référence, cm² par côté
        for shp in st.ships:                                          # masse du vaisseau conservée
            m = shp["M_rigid"] + sum(p["ms"] for p in shp["pendulums"])
            self.assertAlmostEqual(m / 1e3, 610.0, delta=0.01)
            self.assertAlmostEqual(shp["x_tot"], 33.96, delta=0.05)

    def test_bassin_dans_un_seul_vaisseau(self):
        st = ts.Station(ts.make_parser().parse_args(rs.TLD + ["--tld-ships", "0"]))
        ref = ts.Station(ts.make_parser().parse_args(rs.TLD))
        self.assertEqual([len(s["pendulums"]) for s in st.ships], [3, 2, 2])
        for a, b in zip(st.ships, ref.ships):                         # eau figée : même masse, même centre de masse
            self.assertAlmostEqual(a["x_tot"], b["x_tot"], places=6)
            self.assertAlmostEqual(a["M_rigid"] + sum(p["ms"] for p in a["pendulums"]),
                                   b["M_rigid"] + sum(p["ms"] for p in b["pendulums"]), delta=1e-6)


class AmortissementCables(unittest.TestCase):
    def taux(self, segments):
        """Taux de décroissance de la vitesse d'écartement de deux vaisseaux, amortissement des câbles seul."""
        st = ts.Station(ts.make_parser().parse_args(rs.TLD3 + ["--segments", str(segments), "--quiet"]))
        st.relax(verbose=False)
        st.vn[:], st.vb[:], st.pi[:] = 0.0, 0.0, 0.0
        e = (st.xb[1] - st.xb[0]) / np.linalg.norm(st.xb[1] - st.xb[0])
        st.vb[0], st.vb[1] = -0.5 * e, 0.5 * e
        n = int(3.0 / st.dt)
        rel = np.empty(n)
        for k in range(n):
            st.damp(st.dt)
            rel[k] = (st.vb[1] - st.vb[0]) @ e
        t = (np.arange(n) + 1) * st.dt
        visé = 3 * st.c[0] / st.n / (st.Mb[0] / 2)                   # trois brins en parallèle, masse réduite des deux coques
        # ζ vaut pour le côté entier, quel que soit le nombre de brins
        k_side = 3 * st.EA / (st.ds0[0] * st.n)
        self.assertAlmostEqual(3 * st.c[0] / st.n, 2 * st.args.zeta * math.sqrt(k_side * st.M / 2), delta=1e-6 * st.c[0])
        p = np.abs(st.mn @ st.vn + st.Mb @ st.vb).max() / st.Mb[0]
        return -np.polyfit(t[t > 1.2], np.log(rel[t > 1.2]), 1)[0], visé, p

    def test_taux_independant_du_decoupage(self):
        # mode lent (câble étiré d'un bout à l'autre) : même taux avec 16 et 48 segments, proche du taux visé
        r16, visé, p16 = self.taux(16)
        r48, _, p48 = self.taux(48)
        self.assertAlmostEqual(r48 / r16, 1.0, delta=0.005)
        self.assertAlmostEqual(r16 / visé, 1.0, delta=0.05)
        self.assertLess(max(p16, p48), 1e-12)                         # quantité de mouvement conservée


class Simulations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_conservation(self):
        # haltère générique libre : énergie et moment cinétique conservés
        r = simule("cons", ["--topology", "dumbbell", "--module", "axial", "--duration", "60"], self.tmp.name)["results"]
        self.assertLess(r["dE_max"], 1e-7)
        self.assertLess(r["dL_max"], 1e-7)

    def test_corde_et_equilibre(self):
        # équilibre de la solution retenue : longueur et tension d'un côté, fréquence de corde (§ 12)
        info = simule("equ", rs.TLD + ["--duration", "20"], self.tmp.name)
        self.assertAlmostEqual(info["L_eq"], 579.6, delta=0.2)
        self.assertAlmostEqual(info["T_eq"] / 1e6, 1.39, delta=0.01)
        lam = ts.MATERIALS["sk99"]["rho"] * info["area_cm2"] * 1e-4
        f1 = math.sqrt(info["T_eq"] / lam) / (2 * info["L_eq"])
        self.assertAlmostEqual(f1, 0.265, delta=0.005)

    def test_impulsions_groupees(self):
        # pivotement vers le Soleil à vitesse réelle, un tour sur deux : angle et impulsion conformes
        args = rs.TLD + ["--dv-radial", "0", "--dv-z", "0", "--droll", "0", "--precess-rate", "0.695",
                         "--precess-pulse", "15", "--precess-group", "2", "--duration", "130"]
        pr = simule("piv", args, self.tmp.name)["results"]["precess"]
        self.assertAlmostEqual(pr["angle_deg"] / pr["angle_pred_deg"], 1.0, delta=1e-3)
        self.assertAlmostEqual(pr["impulse_ratio"], 1.0, delta=1e-3)


if __name__ == "__main__":
    unittest.main()
