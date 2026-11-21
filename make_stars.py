"""Ciel réel de la vue du hublot : extrait compact du Yale Bright Star Catalogue.

Source : Bright Star Catalogue, 5e édition révisée (Hoffleit et Warren, 1991,
VizieR V/50), fichier texte à colonnes fixes ``bsc5.dat`` :
http://tdc-www.harvard.edu/catalogs/bsc5.dat.gz (miroir du CDS).

Usage : python make_stars.py chemin/vers/bsc5.dat [--mag-max 6.3]

Écrit ``docs/shared/etoiles.js`` : ``window.ETOILES = {n, mag_max, data}``,
``data`` en base64, 6 octets par étoile (petit-boutiste) :
  uint16 ascension droite J2000 (× 65536 / 360°),
  int16  déclinaison J2000 (× 32767 / 90°),
  int8   magnitude V × 20,
  int8   indice B−V × 50 (0 si inconnu).
Résolution ≈ 0,005° en position, 0,05 en magnitude : plus fin que l'œil.
"""
import argparse
import base64
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "docs", "shared", "etoiles.js")


def parse(path, mag_max):
    stars = []
    with open(path, encoding="latin-1") as f:
        for line in f:
            if len(line) < 114 or not line[75:77].strip() or not line[102:107].strip():
                continue                    # objets sans position J2000 (novae, doublons retirés)
            ra = 15 * (int(line[75:77]) + int(line[77:79]) / 60 + float(line[79:83]) / 3600)
            dec = int(line[84:86]) + int(line[86:88]) / 60 + int(line[88:90]) / 3600
            if line[83] == "-":
                dec = -dec
            v = float(line[102:107])
            bv = float(line[109:114]) if line[109:114].strip() else 0.0
            if v <= mag_max:
                stars.append((ra, dec, v, bv))
    stars.sort(key=lambda s: s[2])          # brillantes d'abord
    return stars


def main():
    ap = argparse.ArgumentParser(description="Extrait compact du Bright Star Catalogue pour hublot.js")
    ap.add_argument("catalog", help="bsc5.dat (texte, colonnes fixes)")
    ap.add_argument("--mag-max", type=float, default=6.3, help="magnitude limite (≤ 6,35)")
    a = ap.parse_args()
    stars = parse(a.catalog, min(a.mag_max, 6.35))
    buf = bytearray()
    for ra, dec, v, bv in stars:
        buf += struct.pack("<Hhbb", round(ra / 360 * 65536) % 65536, round(dec / 90 * 32767),
                           round(v * 20), max(-127, min(127, round(bv * 50))))
    b64 = base64.b64encode(bytes(buf)).decode()
    with open(OUT, "w") as f:
        f.write("/* Étoiles jusqu'à la magnitude %.1f : Bright Star Catalogue, 5e éd. révisée\n"
                "   (Hoffleit et Warren 1991, VizieR V/50), extrait par make_stars.py. */\n" % a.mag_max)
        f.write('window.ETOILES = { n: %d, mag_max: %.2f, data: "%s" };\n' % (len(stars), a.mag_max, b64))
    print(f"{len(stars)} étoiles (V ≤ {a.mag_max}), {len(buf)} octets, {os.path.getsize(OUT)} octets écrits dans {OUT}")
    print("plus brillantes :", [(round(s[0], 1), round(s[1], 1), s[2]) for s in stars[:5]])


if __name__ == "__main__":
    main()
