#!/usr/bin/env python3
"""Tests rapides du simulateur (quelques minutes en tout) :

  .venv/bin/python -m unittest discover tests

Ils vérifient la géométrie de la solution retenue, la conservation de
l'énergie et du moment cinétique, le modèle de masse et quelques options,
sans relancer les campagnes (plusieurs heures)."""
import json
import math
import os
import sys
import tempfile
import unittest

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
