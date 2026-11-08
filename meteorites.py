#!/usr/bin/env python3
"""
Coupures de câble par les météorites pendant le transfert (carnet § 7.1).

Flux interplanétaire cumulé de Grün et al. (1985) à 1 UA (prudent vers Mars),
sur la surface latérale des câbles π·d·L. Une particule coupe un câble rond
quand elle mesure de 20 à 50 % de son diamètre ; masse volumique 1 à 2,5 g/cm³.
Pour N brins par côté (même section au total), chaque brin a un diamètre
d/√N et la longueur exposée est N fois plus grande.

    .venv/bin/python meteorites.py > out/meteorites.log
"""
import math

DAYS = 259
L_SIDE = 579.0      # m, longueur d'un côté
SIDES = 3


def flux(m):
    """Flux cumulé F(> m) (m⁻² s⁻¹), m en grammes (Grün et al. 1985)."""
    return ((2.2e3 * m ** 0.306 + 15) ** -4.38 + 1.3e-9 * (m + 1e11 * m ** 2 + 1e27 * m ** 4) ** -0.36
            + 1.3e-16 * (m + 1e6 * m ** 2) ** -0.85)


def cuts(d, n=1):
    """Coupures attendues par voyage (fourchette) pour n brins de diamètre d (m) par côté."""
    vals = []
    for frac in (0.2, 0.5):
        for rho in (1.0, 2.5):
            dp = frac * d * 100                     # cm
            m = rho * math.pi / 6 * dp ** 3         # g
            vals.append(n * SIDES * L_SIDE * math.pi * d * DAYS * 86400 * flux(m))
    return min(vals), max(vals)


def main():
    cases = [("Câble Ø 13,2 cm (référence : tressé, gainé, redondant)", 0.132, 1), ("Câble Ø 10,7 cm (fibre pleine idéale)", 0.107, 1),
             ("2 brins Ø 9,3 cm par côté", 0.132 / math.sqrt(2), 2),
             ("3 brins Ø 7,6 cm par côté (retenue)", 0.132 / math.sqrt(3), 3),
             ("3 brins Ø 6,2 cm par côté (fibre pleine idéale)", 0.107 / math.sqrt(3), 3),
             ("Fil Ø 2 mm, même longueur", 0.002, 1)]
    print(f"Coupures attendues par voyage ({DAYS} j, {SIDES} × {L_SIDE:.0f} m, flux à 1 UA) :")
    for name, d, n in cases:
        lo, hi = cuts(d, n)
        print(f"  {name:45s} : {lo:.1e} à {hi:.1e}")
    # Deux brins d'un même côté coupés par deux impacts indépendants pendant le voyage
    lo, hi = cuts(0.107 / math.sqrt(3), 3)
    print(f"  deux brins du même côté, impacts indépendants : < {(hi / 3) ** 2:.0e}")


if __name__ == "__main__":
    main()
