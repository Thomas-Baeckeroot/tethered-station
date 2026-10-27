#!/bin/bash
# Construit le site statique (ex. http://t.baeckeroot.free.fr/tethered-station/) dans le dossier donné :
#   <dossier>/index.html        redirection vers la page grand public
#   <dossier>/grand-public/     page grand public + ses données
#   <dossier>/technique/        carnet technique + toutes les données
# Les pages sources n'ont pas de squelette (ajouté à la publication en Artifact) :
# on ajoute doctype, charset et viewport, et on remplace les liens vers les
# Artifacts claude.ai par des liens relatifs.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$1"
[ -n "$DEST" ] || { echo "usage : $0 <dossier>" >&2; exit 1; }
"$SRC/stage_publish.sh" "$DEST" >/dev/null
for p in grand-public technique; do
  f="$DEST/$p/index.html"
  { printf '<!doctype html>\n<html lang="fr">\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    sed -e 's|https://claude.ai/artifact/AhFHVxf86G4P5S4H4s9cXx|../grand-public/|g' \
        -e 's|https://claude.ai/artifact/5dVec5xiSvaZwkLvLzXFMi|../technique/|g' "$SRC/$p/index.html"
  } > "$f"
done
cat > "$DEST/index.html" <<'EOF'
<!doctype html>
<html lang="fr">
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=grand-public/">
<title>Gravité au bout du fil</title>
<p><a href="grand-public/">Gravité au bout du fil</a> · <a href="technique/">carnet de calcul technique</a></p>
EOF
if grep -l 'claude.ai/artifact' "$DEST"/*/index.html; then echo "liens claude.ai restants" >&2; exit 1; fi
du -sh "$DEST"/*/ | sed 's|'"$DEST"'/||'
