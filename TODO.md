# À étudier ou développer

Liste de travail, par priorité pour le scénario Terre–Mars. Les limites du modèle sont aussi listées au § 15 du carnet technique.

## Priorité haute

- **Mise en rotation après l'injection vers Mars** : rapprochement des trois vaisseaux, déroulement des câbles sans détente, montée à 1 tr/min (poussée des moteurs ou du RCS, durée, ergols consommés, risque de mou dans les câbles).
- **Rupture d'un câble** : énergie élastique stockée ≈ ½·T·ε·L (0,5 MJ par câble en route, 3,8 MJ à 1 600 t et 1 g). Trajectoire du brin libéré (fouet), survie du triangle réduit à deux câbles (le roulis redevient neutre ?), séparation sûre.
- **Vaisseaux de masses inégales** (vaisseau d'équipage contre cargos) : triangle déséquilibré, centre de rotation décalé, gravité différente d'un vaisseau à l'autre.
- **Pattes d'oie** : répartir chaque câble sur plusieurs points d'ancrage du nez, écartés aussi selon l'axe de rotation, pour raidir le balancement hors plan (complément ou alternative au bassin).
- **Amortir davantage le mode couplé du LOX (≈ 0,26 Hz)** : avec le bassin, c'est lui qui fixe le pic restant (0,44 à 0,46°) ; chicanes plus efficaces ou second bassin accordé sur ce mode.
- **Bassin d'eau en eau peu profonde, non linéaire** : au pire rythme, la masse équivalente se déplace de 25 à 31 cm pour 0,61 m de profondeur. Vérifier par un modèle d'écoulement en eau peu profonde (déferlement, ressaut, efficacité des grilles), et la tenue de l'accord quand le niveau baisse (l'eau sert aussi de réserve).
- **Fluage des câbles sur 259 jours** : chiffrer avec les données fabricant (Dyneema DM20 / SK99, Vectran) à la température réelle du câble ; allongement inégal → compensation par treuils.

## Priorité moyenne

- **Câble réaliste** : tresse à brins multiples (type Hoytether), gaine ; perte de brins par micrométéorites ; masse 24 t (Dyneema SK99 redondant) à 47 t (Kevlar) d'après le § 2.3 du carnet.
- **Ancrages sur la coiffe** : capacité des points d'attache du Starship (non publiée) ; en route 1,31 MN par câble et 2,26 MN par vaisseau (9,1 et 15,7 MN à 1 600 t et 1 g).
- **Thermique des câbles** : passage soleil/ombre à chaque tour, dilatation négative du Dyneema, choix de la gaine.
- **Câbles ANCF continus dans Chrono** : modes de câble rapides, raideur en torsion (rappel de roulis négligé aujourd'hui, ce qui va dans le sens de la sécurité).
- **Flexibilité de la coque** et modes de ballottement supérieurs (aujourd'hui : structure rigide, premier mode seulement, réservoirs à fond plat).
- **Ailerons du Starship** dans l'inertie (orientation préférée faible).

## Priorité basse

- Contrôle actif : RCS pour corriger l'axe de rotation et amortir les balancements (le choix actuel est passif).
- Gradient de gravité complet en orbite terrestre (repère de Hill) ; en transit héliocentrique, l'effet est négligeable.
- Amarrage d'un véhicule en route (non prévu par le scénario).
- Vieillissement des câbles : rayonnement, micrométéorites, fluage sous charge permanente (lié au fluage ci-dessus).

## Pages

- Après toute nouvelle campagne : mettre à jour la synthèse (§ 1), les limites (§ 15) et la section Reproduire (§ 16) du carnet ; le bilan et « Ce qu'il reste à étudier » de la page grand public ; ce fichier et le README.
