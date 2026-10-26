#!/bin/bash
# Prépare une copie publiable de chaque page (index.html + shared/ + data/ utiles)
# dans le dossier donné en argument.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$1"
rm -rf "$DEST" && mkdir -p "$DEST"
for p in grand-public technique; do
  mkdir -p "$DEST/$p/shared" "$DEST/$p/data/series" "$DEST/$p/data/anim"
  cp "$SRC/$p/index.html" "$DEST/$p/"
  cp "$SRC"/shared/*.js "$DEST/$p/shared/"
  cp "$SRC/data/summary.json" "$DEST/$p/data/"
done
# Grand public : uniquement les données référencées
for n in Zp_perturbation D_echelle_axial B_haltere_axial B_amortisseur Z_final_cargaison_patte_oie SV2_perturbation M_cargaison_laterale; do
  cp "$SRC/data/anim/$n.json" "$DEST/grand-public/data/anim/"
  cp "$SRC/data/series/$n.json" "$DEST/grand-public/data/series/"
done
for n in A_cargaison Z_final_cargaison A_equipage Zp_equipage SV3_balayage_z SH3_balayage SH3n_balayage; do
  cp "$SRC/data/series/$n.json" "$DEST/grand-public/data/series/"
done
# Technique : tout
cp "$SRC"/data/series/*.json "$DEST/technique/data/series/"
cp "$SRC"/data/anim/*.json "$DEST/technique/data/anim/"
cp "$SRC/data/validation.json" "$SRC/data/mission.json" "$DEST/technique/data/"
du -sh "$DEST"/*
