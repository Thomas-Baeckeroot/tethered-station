# tethered-station

Étude d'une station spatiale à gravité artificielle faite de vaisseaux reliés par des câbles, en rotation. Solution retenue : trois Starships debout (pointe vers le centre) en triangle, sur le transfert Terre–Mars (259 jours), 610 t chacun en route, gravité de Mars (3,711 m/s²) à 1 tr/min, soit R = 338,4 m. Chaque vaisseau est attaché par sa coiffe en deux points écartés de ±3,5 m ; câbles en Dyneema dimensionnés pour des vaisseaux pleins (1 600 t) à 1 g avec un facteur 3 ; réservoirs à chicanes ; bassin d'eau accordé de 25 t contre le balancement. L'étude a commencé par des modules génériques (étude préliminaire, toujours documentée).

Points à étudier : `TODO.md`.

Deux publications présentent les résultats :

- `docs/grand-public/` : article de présentation, avec animations 3D des simulations ;
- `docs/technique/` : carnet de calcul (hypothèses, dimensionnement, modèle, validation, problèmes étudiés, résultats).

Code source : https://github.com/Thomas-Baeckeroot/tethered-station. Site : http://t.baeckeroot.free.fr/tethered-station/ ([grand public](http://t.baeckeroot.free.fr/tethered-station/grand-public/), [carnet technique](http://t.baeckeroot.free.fr/tethered-station/technique/)).

Site statique : `docs/build_site.sh <dossier>` construit `index.html`, `grand-public/` et `technique/` (squelette HTML complet, liens relatifs entre les pages), à copier tel quel sur le serveur (ex. http://t.baeckeroot.free.fr/tethered-station/).

## Contenu

| Fichier | Rôle |
|---|---|
| `tether_sim.py` | Simulateur multicorps (NumPy) : vaisseaux rigides (modèle de masse par éléments, pendules de ballottement, bassin d'eau accordé), câbles unilatéraux discrétisés, masses internes mobiles, amortisseur interne |
| `run_scenarios.py` | Campagnes de scénarios en parallèle : `rotation`, `internes`, `final` (étude préliminaire), `starship`, `mission`, `ballottement`, `retenue`, `amortisseur` |
| `mission_mass.py` | Masse d'un Starship après l'injection vers Mars |
| `slosh_modes.py` | Modèle linéaire hors plan (vaisseau + ergols) : modes couplés |
| `tld_design.py` | Dimensionnement du bassin d'eau accordé (modèle linéaire amorti, balayage en temps) |
| `chrono_validation.py` | Validation croisée avec Project Chrono (PyChrono 10) |
| `make_web_data.py` | Export des résultats vers `docs/data/` (séries, trajectoires 3D, validation) |
| `docs/shared/` | Visualiseur 3D (three.js), graphiques SVG, schémas des configurations |
| `docs/stage_publish.sh` | Prépare les copies publiables des deux pages |

## Utilisation

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python tether_sim.py --help
.venv/bin/python tether_sim.py --topology triangle2 --module tangential --bridle 20 --duration 600

.venv/bin/python run_scenarios.py rotation     # 8 scénarios de stabilité (~8 min sur M1 Max)
.venv/bin/python run_scenarios.py internes     # mouvements internes (~30 min)
.venv/bin/python run_scenarios.py final        # configuration retenue
.venv/bin/python run_scenarios.py starship     # Starships (Ø9 × 50 m) : vertical ou horizontal, 2 ou 3 vaisseaux (~30 min)
.venv/bin/python mission_mass.py               # masse d'un Starship après l'injection vers Mars
.venv/bin/python run_scenarios.py mission      # mission Terre–Mars : 610 t, 3,711 m/s², câbles pour 1 600 t (~30 min)
.venv/bin/python run_scenarios.py ballottement # ergols figés / libres / chicanes (~50 min)
.venv/bin/python run_scenarios.py retenue      # solution retenue : ergols libres, réservoirs à chicanes
.venv/bin/python run_scenarios.py amortisseur  # bassin d'eau accordé (~3 h)
.venv/bin/python tld_design.py                 # dimensionnement du bassin (modèle linéaire)
.venv/bin/python slosh_modes.py                # modes couplés vaisseau + ergols (modèle linéaire)
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

Solution retenue (610 t, ergols libres, chicanes) : roulis 0,09° après une perturbation ; 50 t déplacées de 3,5 m sur un pont : 0,61° ; changement de pont et marche : 0,19° ; pire balancement entretenu par 4 t : 2,7° sans bassin, 0,46° avec le bassin de 25 t. Câbles : 4,8 % de leur résistance en route ; un câble réaliste (tressé, gainé, brins redondants) pèse 24 t pour les trois en Dyneema SK99, jusqu'à 47 t en Kevlar.

Historique de l'étude :

- Un câble ne transmet pas de couple : un module attaché en un point peut tourner librement autour de son câble. Son roulis obéit à φ̈ = ω²(I_t − I_z)/I_r · φ, si bien qu'un module dont l'axe long est parallèle à l'axe de rotation est instable (temps de doublement 7,1 s).
- Haltère : I_Y ≈ I_Z (écart de 0,1 %), donc l'inertie des modules décide de l'axe intermédiaire. L'effet Djanibekov est possible : avec deux câbles parallèles, la station entière se retourne toutes les ~150 s. Le triangle (I_Z = I_X + I_Y) n'y est pas sujet.
- Deux points d'attache écartés de ±20 m par module stabilisent même un module mal orienté.
- 50 t de cargaison déplacées de 15 m inclinent le plancher de 4,4° (attache unique), 1,6° (deux attaches), 0,7° (deux attaches surélevées de 20 m).
- Les balancements des modules sont très peu amortis : 4 t oscillant à la fréquence la plus défavorable inclinent le plancher de 3,9° avec une attache unique, 0,7° avec deux attaches surélevées ; la marche ordinaire donne 0,2 à 0,6°.
- Configuration retenue : triangle, modules tangentiels, deux attaches surélevées par module ; rotation dans le plan de l'orbite (sinon précession par gradient de gravité, ~28°/jour à 1 600 km).
- Starships (Ø9 × 50 m, 1 600 t) : vertical (nez vers le centre, câbles aux points d'ancrage du nez) en triangle, chaque câble attaché du côté de son voisin. Roulis ≤ 0,1° ; 50 t déplacées de 3,5 m sur un pont : 0,23° ; changer de pont : aucun effet ; pire résonance 0,57° (contre 0,86° à l'horizontale avec mâts, 2,6° sans). À deux vaisseaux verticaux, rien ne fixe l'orientation autour du câble : dérive libre (205° en 30 min après une poussée de 0,11°/s).
- Mission Terre–Mars : trois Starships pleins (1 600 t) en orbite basse ; après l'injection vers Mars (Hohmann, 3,6 km/s), ≈ 610 t chacun (560 à 650 t selon l'orbite, l'Isp et la fenêtre). Gravité de Mars 3,711 m/s² → R = 338,4 m. Câbles pour 1 600 t à 1 g : 4,8 % de leur résistance en route. Roulis 0,14° ; 50 t sur un pont : 0,58° ; changement de pont et marche : sans effet mesurable ; pire résonance 1,44° hors du plan de rotation (période 8 s), 2,8° si le centre de masse remonte (h = 15 m).
- Ballottement des ergols (`--slosh free`, pendules d'Abramson, NASA SP-106) : 139 t de LOX et 47 t de CH4 ballottent par vaisseau. Mode couplé du LOX à 0,25 Hz (vérifié par `slosh_modes.py`). Sans chicanes (ζ ≈ 0,1 %), il résonne et met des minutes à s'éteindre : jusqu'à 4,3° au pire rythme. Avec chicanes (ζ = 3 %), il s'éteint en 20 s, mais le pire balancement double (2,7° contre 1,3° ergols figés) car le liquide n'accompagne plus la coque. Cargaison et marche quasi inchangées.
- Amortisseur à liquide accordé (`--tld-mass-t`, dimensionné par `tld_design.py`) : bassin de 25 t d'eau, Ø 7,2 m × 0,61 m, à 12 m de la pointe, accordé à 0,117 Hz, ζ = 0,15. Pire balayage hors plan 2,70° → 0,46°, dans le plan 1,28° → 0,44° ; peu sensible à l'accord, à ζ (0,08–0,20) et à la masse du vaisseau (560 t : 0,50°). Placé côté moteurs, il serait presque inutile.
- Validation : énergie et moment cinétique conservés à 10⁻⁸ ou mieux ; Project Chrono reproduit les mêmes trajectoires (écart de temps de doublement 0,03 à 0,13 %).

## Licence

Code (scripts Python, JavaScript, shell) : [MIT](LICENSE). Textes, figures et données des pages (`docs/`) : [CC BY 4.0](docs/LICENSE).
