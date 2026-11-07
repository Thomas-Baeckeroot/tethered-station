# tethered-station

Étude d'une station spatiale à gravité artificielle faite de vaisseaux reliés par des câbles, en rotation. Solution retenue : trois Starships debout (pointe vers le centre) en triangle, sur le transfert Terre–Mars (259 jours), 610 t chacun en route, gravité de Mars (3,711 m/s²) à 1 tr/min, soit R = 338,4 m. Chaque vaisseau est attaché par les deux points de capture de sa coiffe (13 m de la pointe, ±4,8 m de l'axe, position estimée d'après le Starship V3) ; câbles en Dyneema dimensionnés pour des vaisseaux pleins (1 600 t) à 1 g avec un facteur 3 ; réservoirs à chicanes ; bassin d'eau accordé de 25 t contre le balancement. L'étude a commencé par des modules génériques (étude préliminaire, toujours documentée).

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
| `run_scenarios.py` | Campagnes de scénarios en parallèle : `rotation`, `internes`, `final` (étude préliminaire), `starship`, `mission`, `ballottement`, `retenue`, `amortisseur`, `rupture`, `brins`, `moyeu`, `montee`, `montee_lente`, `lox`, `masses`, `soleil`, `allege`, `sensibilite`, `brins3`, `retour`, `entretoises` |
| `mission_mass.py` | Masse d'un Starship après l'injection vers Mars |
| `slosh_modes.py` | Modèle linéaire hors plan (vaisseau + ergols) : modes couplés |
| `tld_design.py` | Dimensionnement du bassin d'eau accordé (modèle linéaire amorti, balayage en temps) |
| `lox_search.py` | Mode couplé du LOX : chicanes plus efficaces ou second bassin (même modèle linéaire) |
| `light_tld.py` | Vaisseau habité allégé : modes hors plan et pic du balayage, bassin d'origine ou réaccordé (modèle linéaire généralisé aux masses inégales) |
| `sun_pointing.py` | Orientation face au Soleil : direction du Soleil sur le transfert, impulsion pour faire pivoter l'axe, bilan thermique des réservoirs (modèle 2D) selon l'orientation et les revêtements ; écrit `docs/data/soleil.json` |
| `creep.py` | Fluage des câbles sur l'aller-retour (loi d'Eyring calée sur les données publiées DSM, température le long du transfert, retour en rampe jusqu'à 1 g) ; écrit `out/creep.log` et `docs/data/creep.json` |
| `snapback.py` | Trajet du brin rompu dans le repère du vaisseau 0 (campagne `entretoises`) ; écrit `docs/data/snapback.json` |
| `meteorites.py` | Coupures de câble ou de brin par les météorites (flux de Grün) ; écrit `out/meteorites.log` si on y redirige sa sortie |
| `cable_thermal.py` | Câbles face au Soleil : température de gaine, écart entre face éclairée et face à l'ombre |
| `deploy_sim.py` | Déroulement des câbles sur `tether_sim` : longueur à vide variable, poussée selon ω ∝ r^(−p), lancer freiné |
| `deploy_campaign.py` | Catalogue des scénarios de déroulement (`run`) et export vers `docs/data/deploiement.json` (`export`) |
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
.venv/bin/python run_scenarios.py rupture      # rupture d'un câble, moyeu et rayons, coupe-câbles (~1 h 30)
.venv/bin/python run_scenarios.py brins3       # retenue : trois brins par côté, ruptures d'un et deux brins (~5 h)
.venv/bin/python run_scenarios.py brins        # étude préalable : deux brins par côté, disposition (~2 h)
.venv/bin/python run_scenarios.py moyeu        # confort avec moyeu et rayons doublés (~2 h 30)
.venv/bin/python run_scenarios.py montee       # mise en rotation de 0,1 à 1 tr/min (~1 h 30)
.venv/bin/python run_scenarios.py montee_lente # montée de 0,1 à 1 tr/min en 2 h 30 et 6 h (~3 h)
.venv/bin/python deploy_campaign.py run --jobs 2 # déroulement des câbles (17 scénarios, ~20 h)
.venv/bin/python deploy_campaign.py export     # → docs/data/deploiement.json
.venv/bin/python run_scenarios.py lox          # chicanes du LOX à 8 % ou second bassin (~1 h 30)
.venv/bin/python run_scenarios.py masses       # transfert d'ergols : 220 / 805 / 805 t à 0,862 tr/min (~1 h)
.venv/bin/python run_scenarios.py allege       # transferts partiels, lest bas, bassins réaccordés (~10 h)
.venv/bin/python light_tld.py                  # vaisseau allégé : modes et bassin réaccordé (modèle linéaire)
.venv/bin/python lox_search.py                 # mode du LOX (modèle linéaire)
.venv/bin/python run_scenarios.py soleil       # pivotement de l'axe vers le Soleil, 1 000 fois accéléré (~40 min)
.venv/bin/python sun_pointing.py               # orientation face au Soleil : impulsion, bilan thermique
.venv/bin/python run_scenarios.py sensibilite  # vaisseaux pleins, câble réaliste
.venv/bin/python run_scenarios.py retour       # retour à 1 g, vaisseaux de 250 t : tensions et ruptures de brins (~2 h)
.venv/bin/python creep.py                      # fluage des câbles sur l'aller-retour
.venv/bin/python run_scenarios.py entretoises  # retour du brin rompu : bras, longe, entretoises (~5 h)
.venv/bin/python snapback.py                   # trajet du brin rompu vu du vaisseau 0 → docs/data/snapback.json
.venv/bin/python tld_design.py                 # dimensionnement du bassin (modèle linéaire)
.venv/bin/python slosh_modes.py                # modes couplés vaisseau + ergols (modèle linéaire)
.venv/bin/python meteorites.py > out/meteorites.log  # coupures par les météorites
.venv/bin/python cable_thermal.py              # thermique des câbles (--brins 3 pour un brin)
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

Prévisualisation locale des pages : `docs/_preview/build.sh`, puis `python3 -m http.server 8765 --bind 127.0.0.1` dans `docs/_preview/`.

## Résultats principaux

Solution retenue (610 t, ergols libres, chicanes, bassin ; gravité de Mars au pont principal, à 14 m de la pointe) : roulis 0,08° après une perturbation ; 50 t déplacées de 3,5 m sur un pont : 0,70° ; marche de l'équipage : 0,21° ; pire balancement entretenu par 4 t : 3,0° sans bassin, 0,43° avec le bassin de 25 t, 0,30° si les chicanes du LOX amortissent 8 % au lieu de 3 %. Déroulement des câbles à 3 cm/s sous 0,05 tr/min (5 h, jamais détendus ; treuil bloqué 10 min : 26 kN), puis mise en rotation de 0,1 à 1 tr/min : 21 t d'ergols quelle que soit la durée, plancher penché de 2,6° en 30 min, 0,21° en 6 h, sans résonance. De l'arrêt à 1 tr/min : 24,7 t. Câbles : 5,1 % de leur résistance en route, chaque côté fait de trois brins de tiers de section (même masse, 15 t) avec des coupe-câbles : la rupture d'un brin ne déforme pas la station, le plancher repasse sous 3° en 82 s, et une seconde rupture du même côté reste supportable. Un câble réaliste (tressé, gainé, brins redondants) pèse 25 t pour les trois en Dyneema SK99, jusqu'à 51 t en Kevlar.

Historique de l'étude :

- Un câble ne transmet pas de couple : un module attaché en un point peut tourner librement autour de son câble. Son roulis obéit à φ̈ = ω²(I_t − I_z)/I_r · φ, si bien qu'un module dont l'axe long est parallèle à l'axe de rotation est instable (temps de doublement 7,1 s).
- Haltère : I_Y ≈ I_Z (écart de 0,1 %), donc l'inertie des modules décide de l'axe intermédiaire. L'effet Djanibekov est possible : avec deux câbles parallèles, la station entière se retourne toutes les ~150 s. Le triangle (I_Z = I_X + I_Y) n'y est pas sujet.
- Deux points d'attache écartés de ±20 m par module stabilisent même un module mal orienté.
- 50 t de cargaison déplacées de 15 m inclinent le plancher de 4,4° (attache unique), 1,6° (deux attaches), 0,7° (deux attaches surélevées de 20 m).
- Les balancements des modules sont très peu amortis : 4 t oscillant à la fréquence la plus défavorable inclinent le plancher de 3,9° avec une attache unique, 0,7° avec deux attaches surélevées ; la marche ordinaire donne 0,2 à 0,6°.
- Configuration retenue : triangle, modules tangentiels, deux attaches surélevées par module ; rotation dans le plan de l'orbite (sinon précession par gradient de gravité, ~28°/jour à 1 600 km).
- Starships (Ø9 × 50 m, 1 600 t) : vertical (nez vers le centre, câbles aux points d'ancrage du nez) en triangle, chaque câble attaché du côté de son voisin. Roulis ≤ 0,1° ; 50 t déplacées de 3,5 m sur un pont : 0,23° ; changer de pont : aucun effet ; pire résonance 0,57° (contre 0,86° à l'horizontale avec mâts, 2,6° sans). À deux vaisseaux verticaux, rien ne fixe l'orientation autour du câble : dérive libre (206° en 30 min après une poussée de 0,11°/s).
- Mission Terre–Mars : trois Starships pleins (1 600 t) en orbite basse ; après l'injection vers Mars (Hohmann, 3,6 km/s), ≈ 610 t chacun (560 à 650 t selon l'orbite, l'Isp et la fenêtre). Gravité de Mars 3,711 m/s² au pont principal (14 m de la pointe) → R = 338,4 m au pont, 358,4 m au centre de masse, câbles de 579 m (563 m dans le modèle homogène). Câbles pour 1 600 t à 1 g : 5,1 % de leur résistance en route. Modèle homogène, attaches aux points de capture (h = 21 m) : perturbation 0,11° ; 50 t sur un pont : 0,67° ; changement de pont et marche : sans effet mesurable ; pire résonance 1,83° hors du plan de rotation (période 8 s), 2,8° si le centre de masse remonte (h = 15 m).
- Ballottement des ergols (`--slosh free`, pendules d'Abramson, NASA SP-106) : 139 t de LOX et 47 t de CH4 ballottent par vaisseau. Mode couplé du LOX à 0,25 Hz (vérifié par `slosh_modes.py`). Sans chicanes (ζ ≈ 0,1 %), il résonne et met des minutes à s'éteindre : jusqu'à 4,6° au pire rythme. Avec chicanes (ζ = 3 %), il s'éteint en 20 s, mais le pire balancement double presque (3,0° contre 1,7° ergols figés) car le liquide n'accompagne plus la coque. Cargaison et marche quasi inchangées.
- Amortisseur à liquide accordé (`--tld-mass-t`, dimensionné par `tld_design.py`) : bassin de 25 t d'eau, Ø 7,8 m × 0,52 m, à 12 m de la pointe, accordé à 0,103 Hz, ζ = 0,15. Pire balayage hors plan → 0,43° (mode du LOX ; le balancement lui-même 0,31°) ; dans le plan, 0,55° à 0,34 Hz sur le mode d'étirement des câbles, qui disparaît avec le câble réaliste, plus raide ; peu sensible à l'accord, à ζ (0,10–0,30) et à la masse du vaisseau (560 t : 0,48°). Placé côté moteurs, il serait presque inutile.
- Rupture d'un câble (`--break-cable`, `--break-at`, `--release-delay`) : un câble de 11 cm ne craint presque pas les météorites (≈ 10⁻⁶ coupure par voyage, flux de Grün) ; un fil de 2 mm, si (0,3 à 29 %). Sans parade, la rupture d'un câble unique ouvre le triangle : les câbles restants tiennent (8,8 MN, 32 % de la résistance), mais la station « respire » (période 45 s), à-coups de 2 g et vaisseaux qui tournoient ; la rotation tombe à 0,56 tr/min. Alternative (`--hub-mass-t 20 --hub-spokes 2`) : moyeu central relié au nez de chaque vaisseau par deux rayons de 333 m (38 t en tout), plus coupe-câbles qui larguent les morceaux : la station garde sa forme et sa rotation (2,0 MN au plus, secousses d'une vingtaine de secondes) ; avec un seul rayon par vaisseau, la perte d'un rayon libère le moyeu (à-coup de 11,4 MN).
- **Trois brins par côté** (solution retenue, `--side-strands 3 --release-delay 1`, campagne `brins3`, carnet § 7.4) : brins de tiers de section (Ø 6,2 cm, 9,06 MN de résistance), même masse de câble, sur une plaque triangulaire à rotule à chaque ferrure (partage égal après une rupture, pas d'ombre mutuelle), coupe-câbles à chaque extrémité. Confort en service inchangé. Un brin casse : les deux autres montent à 0,89 MN (10 % de leur résistance ; 50 % dans le cas de dimensionnement, facteur 2), plancher à 10° puis sous 5° en 43 s et sous 3° en 82 s, rotation inchangée. Deux brins du même côté, ensemble ou à 10 s d'intervalle : dernier brin à 2,1 MN (23 %), plancher à 23° (13° à 10 s), sous 3° en 30–50 s, rotation inchangée. Sans coupe-câbles : la station tient, mais les morceaux fouettent près des coques (roulis 2,6°, rotation parasite 4 °/s). Météorites : 4·10⁻⁷ à 5·10⁻⁵ coupure de brin par voyage (`meteorites.py`). Ferrures et coupe-câbles : 1 à 2 t estimées, contre 38 t pour le moyeu.
- **Retour du brin rompu et entretoises** (`--strand-ties`, campagne `entretoises`, `snapback.py`, carnet § 7.4) : la moitié détendue d'un brin rompu dérive (centrifuge + Coriolis) et balaie en diagonale la coque du vaisseau dont la ferrure est à l'avant, 3–4 s après la rupture ; un bras de déport de 11 m ne fait que retarder le contact, une longe le fait pendre contre la coque. Des entretoises entre les trois brins tous les 24–48 m (élingues de la tension d'un brin, ≈ 0,5 t pour la station) le retiennent : plus de contact (6 m au plus près), plancher 8,8° au lieu de 10,5° (7,2° tous les 24 m), rien de changé en service. Reste exposée une rupture entre la ferrure et la première entretoise.
- Deux brins par côté (`--side-strands 2`, campagne `brins`, étude préalable) : de demi-section, sur les mêmes ferrures, même masse de câble. Si un brin casse, l'autre monte à 2,0 MN (14 % de sa résistance, 67 % dans le cas de dimensionnement), le triangle garde sa forme et la rotation ; plancher à 16° pendant quelques secondes, sous 3° en 65 s (7,5 min avec le moyeu). Coupe-câbles indispensables (sans eux, les morceaux fouettent pendant des dizaines de minutes). Les brins d'un côté doivent partir ensemble de la ferrure de ce côté (`--strand-layout`, schéma du § 7.5) : superposés, la rupture de l'un fait rouler les vaisseaux (14°, 4° permanents) ; croisés sous le nez, le roulis n'est presque plus retenu et la rupture d'un brin extérieur fait chavirer les vaisseaux ; croisés et amarrés au croisement, le plancher reste penché de 3° après une rupture. La moitié du brin rompu qui revient vers la ferrure commune glisse 2 à 3 s le long du brin intact à 15 m/s (`W_brins2_recul`) : une plaque pivotante sur la ferrure garde les brins écartés sans décentrer l'effort.
- Confort avec le moyeu (campagne `moyeu`) : résonances inchangées ; cargaison sur un pont 0,20° au lieu de 0,70° (les rayons doublés forment une seconde patte d'oie).
- Mise en rotation (`--spin-from 0.1 --spin-k 0.05`) : α = k·ω² garde constante l'inclinaison de la gravité apparente ; 1 tr/min en 30 min, 21 t d'ergols (Isp 300 s), plancher à 2,6° puis 0,04°, câbles toujours tendus. Quatre fois plus vite : 10°. À α constant : 28° au départ, liquides déplacés de 1 à 2,7 m. Poussée à l'arrière : −4 % d'ergols, 4,3°.
- Mode couplé du LOX (campagne `lox`, `lox_search.py`) : chicanes à ζ = 8 % → pire cas hors plan 0,43° → 0,30° (balancement à 0,13 Hz et étirement des câbles à 0,36 Hz) ; un second bassin de 8 t fait moins bien.
- Transfert d'ergols (`--masses-t 220,805,805 --target-ship 0 --rpm 0.8621`) : vaisseau habité à 462 m (pont à 455 m), cargos à 308 m et pivotés de 8,7°, câbles 0,48 / 1,76 MN ; le vaisseau habité devient sept fois plus sensible (cargaison 4,9°), M·h passant de 12 800 à 1 600 t·m ; la marche (aller-retour de 16 s) tombe sur son balancement à 0,06 Hz : 5,2°. Balancement hors plan à 0,059 Hz, loin de l'accord du bassin : 5,9° au pire rythme, 1,5° avec un bassin réaccordé (15 t, Ø 8,8 m, 0,25 m), où l'eau se déplace de 1,2 m.
- Transferts partiels et lest (campagne `allege`, `--ballast-t`) : le balancement hors plan ralentit (0,106 → 0,086 Hz après 195 t) et décroche du bassin : pire rythme 0,69° (100 t), 1,49° (195 t), 3,00° (300 t). Bassin réaccordé (25 t, Ø 8,4 puis 8,8 m) : 0,51°, 0,60°, 1,02°. Tout transvasé avec 50 t de réserves descendues à 44 m (h 7,4 → 14,7 m) : 1,96°, 0,67° avec bassin réaccordé. Cargaison 50 t : 0,89°, 1,23°, 2,17°, 2,66° lesté (0,70° au départ, formule du palonnier à 2–12 %) ; marche 0,17°, 0,34°, 0,84°, 0,63° lesté. Le modèle linéaire (`light_tld.py`) suit le simulateur à 1–8 % ; 32 segments au lieu de 16 : même pic (1,49°).
- Cas de charge réels et fluage (`creep.py`, campagne `retour`, carnet § 2.6) : le critère « 1 600 t à 1 g » n'arrive jamais. Retour en rampe jusqu'à 1 g avec des vaisseaux de 250 t (1,626 tr/min, mêmes câbles) : 1,46 MN par côté, comme à l'aller ; un brin rompu : 0,94 MN sur les deux autres, plancher 8,7° ; deux brins : 2,3 MN, 19°. Fluage sur l'aller-retour (loi d'Eyring calée sur les données DSM, contrôlée sur l'article offshore) : SK99 tressé 0,31 % à 20 °C (10⁻⁴ % à la température réelle du câble), facteur ≈ 5 contre la rupture par fluage sans compter le froid ; DM20 0,003 % ; Vectran négligeable.
- Validation : énergie et moment cinétique conservés à 10⁻⁸ ou mieux ; Project Chrono reproduit les mêmes trajectoires (écart de temps de doublement 0,02 à 0,13 %) et, sur la solution retenue, les pics de rupture à 10 % près (un brin sur trois : plancher 10,0° contre 10,2°, brins restants 0,88 contre 0,89 MN ; deux brins du même côté : 24° contre 23°, 2,06 contre 2,10 MN).

- Face au Soleil (`sun_pointing.py`, campagne `soleil`, carnet § 5.6) : l'axe suit le Soleil (180° en 259 jours, 1,08 à 0,47 °/jour). Impulsion 2,8·10⁸ N·s en poussée continue, 2,2·10⁸ par impulsions à ±15° de la ligne des nœuds (20 N, 5 s, deux fois par tour) : 66 à 94 t de méthane-oxygène brûlés. Le simulateur (1 000 fois accéléré) retrouve l'angle et l'impulsion à 10⁻³ près. Thermique : avec l'axe fixe, les tuiles éclairées conduisent 5 à 26 kW vers les ergols (réservoirs vides en quelques semaines ; 11 à 70 t par vaisseau avec une housse) ; face au Soleil, les tuiles à l'ombre refroidissent les ergols de 0,6 à 1 kW nets (≈ 1 kW de chauffage pour que le CH4 ne gèle pas).

## Participer

Le projet est ouvert : chacun peut le cloner, refaire les calculs, tester d'autres hypothèses ou approfondir un point de `TODO.md`. Remarques (issues) et contributions (pull requests) sont bienvenues.

```sh
git clone https://github.com/Thomas-Baeckeroot/tethered-station.git
cd tethered-station
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run_scenarios.py retenue   # 4 scénarios, ~10 à 30 min
```

## Licence

Code (scripts Python, JavaScript, shell) : [MIT](LICENSE). Textes, figures et données des pages (`docs/`) : [CC BY 4.0](docs/LICENSE).
