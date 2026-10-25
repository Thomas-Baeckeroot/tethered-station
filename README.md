# tethered-station

Étude d'une station spatiale à gravité artificielle : modules habités massifs (100 à 1 600 t) reliés par des câbles, en rotation, en orbite haute. Cible actuelle : 0,38 g (Mars) à 1 tr/min, soit un rayon de 340 m ; câbles dimensionnés pour 1 g avec un facteur de sécurité de 3.

Deux publications présentent les résultats :

- `docs/grand-public/` : article de présentation, avec animations 3D des simulations ;
- `docs/technique/` : carnet de calcul (hypothèses, dimensionnement, modèle, validation, problèmes étudiés, résultats).

Versions publiées (Artifacts claude.ai, privées tant qu'elles ne sont pas partagées) : [grand public](https://claude.ai/artifact/AhFHVxf86G4P5S4H4s9cXx), [carnet technique](https://claude.ai/artifact/5dVec5xiSvaZwkLvLzXFMi). Pour republier : `docs/stage_publish.sh <dossier>` prépare une copie de chaque page avec ses données.

## Contenu

| Fichier | Rôle |
|---|---|
| `tether_sim.py` | Simulateur multicorps (NumPy) : modules rigides, câbles unilatéraux discrétisés, masses internes mobiles, amortisseur interne |
| `run_scenarios.py` | Campagnes de scénarios en parallèle : `rotation`, `internes`, `final` |
| `chrono_validation.py` | Validation croisée avec Project Chrono (PyChrono 10) |
| `make_web_data.py` | Export des résultats vers `docs/data/` (séries, trajectoires 3D, validation) |
| `docs/shared/` | Visualiseur 3D (three.js), graphiques SVG, schémas des configurations |

## Utilisation

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python tether_sim.py --help
.venv/bin/python tether_sim.py --topology triangle2 --module tangential --bridle 20 --duration 600

.venv/bin/python run_scenarios.py rotation     # 8 scénarios de stabilité (~8 min sur M1 Max)
.venv/bin/python run_scenarios.py internes     # mouvements internes (~30 min)
.venv/bin/python run_scenarios.py final        # configuration retenue
.venv/bin/python make_web_data.py              # met à jour docs/data/
```

Validation Chrono (environnement conda local, non versionné) :

```bash
mkdir -p tools && cd tools
curl -Ls https://micro.mamba.pm/api/micromamba/osx-arm64/latest | tar -xj bin/micromamba
MAMBA_ROOT_PREFIX=$PWD/mamba-root ./bin/micromamba create -y -p $PWD/chrono-env \
    -c projectchrono -c conda-forge python=3.12 pychrono=10.0.0 numpy matplotlib
cd .. && tools/chrono-env/bin/python chrono_validation.py --name B --module axial --duration 300
```

Prévisualisation locale des pages : `docs/_preview/build.sh`, puis `python3 -m http.server` dans `docs/_preview/`.

## Résultats principaux

- Un câble ne transmet pas de couple : un module attaché en un point peut tourner librement autour de son câble. Son roulis obéit à φ̈ = ω²(I_t − I_z)/I_r · φ, si bien qu'un module dont l'axe long est parallèle à l'axe de rotation est instable (temps de doublement 7,1 s).
- Haltère : I_Y ≈ I_Z (écart de 0,1 %), donc l'inertie des modules décide de l'axe intermédiaire. L'effet Djanibekov est possible : avec deux câbles parallèles, la station entière se retourne toutes les ~150 s. Le triangle (I_Z = I_X + I_Y) n'y est pas sujet.
- Deux points d'attache écartés de ±20 m par module stabilisent même un module mal orienté.
- 50 t de cargaison déplacées de 15 m inclinent le plancher de 4,4° (attache unique), 1,6° (deux attaches), 0,7° (deux attaches surélevées de 20 m).
- Les balancements des modules sont très peu amortis : 4 t oscillant à la fréquence la plus défavorable inclinent le plancher de 3,9° avec une attache unique, 0,7° avec deux attaches surélevées ; la marche ordinaire donne 0,2 à 0,6°.
- Configuration retenue : triangle, modules tangentiels, deux attaches surélevées par module ; rotation dans le plan de l'orbite (sinon précession par gradient de gravité, ~28°/jour à 1 600 km).
- Validation : énergie et moment cinétique conservés à 10⁻⁸ ou mieux ; Project Chrono reproduit les mêmes trajectoires (écart de temps de doublement 0,03 à 0,13 %).
