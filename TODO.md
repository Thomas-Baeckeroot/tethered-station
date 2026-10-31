# À étudier ou développer

Liste de travail, par priorité pour le scénario Terre–Mars. Les limites du modèle sont aussi listées au § 16 du carnet technique.

## Priorité haute

- **Ancrages du nez et chemin d'effort** (relecture du 31 octobre 2026, carnet § 2.4) : position et capacité des points de levage non publiées, faits pour un vaisseau vide sous 1 g (≈ 1 MN) ; ici 2,4 MN par vaisseau en route, 15,7 MN au dimensionnement, plus les à-coups d'une rupture. Coque en traction : chemin de l'effort à travers la coiffe et la soute non pressurisées jusqu'aux réservoirs. Dégagement câbles–ailerons avant.
- **Arrivée à Mars** : arrêt de la rotation, rentrée des câbles, séparation, retrait ou largage de ce qui ne survit pas à l'entrée (isolant côté Soleil, panneaux, ferrures, housse) ; variante allégée : rendre ses ergols au vaisseau habité.
- **Corrections de trajectoire en route** : poussées synchronisées des trois vaisseaux, ou arrêt de la rotation.
- **Bassin dans l'ogive** : diamètre utile à 12 m de la pointe (≈ 4,2 m de rayon pour une ogive tangente de 17 m, longueur à confirmer) ; couvercle pour les ruptures (plancher à 16–37°, à-coups de 2 à 5 m/s²).
- **Déploiement avant la mise en rotation** : rapprochement des trois vaisseaux, déroulement des câbles sous 0,1 tr/min (quelques kN de tension), treuils. La montée de 0,1 à 1 tr/min est simulée (carnet § 5.4 : α = 0,05·ω², 30 min, 21 t d'ergols, plancher à 2,6°).
- **Câbles doublés** (meilleure parade simulée contre la rupture, carnet § 7.4) : ferrures (communes aux deux brins, imposées par la stabilité en roulis, § 7.4 ; un arrachement les emporte ensemble), entretoises, emmêlement du brin rompu avec le brin sain.
- **Moyeu et rayons doublés** (carnet § 7.3 ; confort vérifié, campagne `moyeu`) : déploiement des côtés et des rayons depuis le moyeu, treuils ; les rayons, réglés pour 1 tr/min, sont presque détendus pendant la montée.
- **Premier retour du brin rompu** : il touche une coiffe 6 s après la rupture, même avec coupe-câbles. Frein anti-retour près des attaches (comme pour les amarres de navires), protection de la coiffe, ou brin captif (câbles doublés).
- **Contact câble–coque** : absent du modèle (brins qui frappent les coques, câbles qui s'enroulent autour d'une coiffe quand un vaisseau tournoie) ; nécessaire pour la suite d'une rupture sans moyeu.
- **Vaisseau habité allégé** (carnet § 5.5, campagne `allege`) : transfert de moitié (0,93 tr/min) avec un bassin réaccordé de 35 t, ou transfert complet avec 50 t de lest bas et bassin réaccordé : pire rythme ≈ 0,6° (0,46° au départ), mais la cargaison déplacée reste 2 à 4 fois plus sensible. À faire : bassin à niveau réglable si le transfert a lieu en route ; non-linéarité de l'eau dans un bassin peu profond (35 cm d'excursion pour 0,58 m) ; résidu à 0,23 Hz porté par le roulis des cargos pleins.
- **Pattes d'oie** : répartir chaque câble sur plusieurs points d'ancrage du nez, écartés aussi selon l'axe de rotation, pour raidir le balancement hors plan (complément ou alternative au bassin).
- **Chicanes du LOX à ζ = 8 %** (carnet § 6.2 : pire cas 0,46° → 0,32°) : vérifier qu'un anneau juste sous la surface libre, dont le niveau ne change pas en route, atteint cet amortissement. Pics restants ≈ 0,3° vers 0,1 Hz et 0,36 Hz (mode d'étirement des câbles).
- **Bassin d'eau en eau peu profonde, non linéaire** : au pire rythme, la masse équivalente se déplace de 25 à 31 cm pour 0,61 m de profondeur. Vérifier par un modèle d'écoulement en eau peu profonde (déferlement, ressaut, efficacité des grilles), et la tenue de l'accord quand le niveau baisse (l'eau sert aussi de réserve).
- **Thermique face au Soleil** (carnet § 5.6, `sun_pointing.py`, modèle 2D) : valeur réelle de la conductance des tuiles et de leur feutre sous vide et à froid (0,1 à 0,6 W/m²·K supposés), qui fixe le refroidissement net ; montage des panneaux (dos chaud à 50 °C, ≈ 500 W/m² : voile ou mâts) ; régulation des ergols, qui gèleraient (CH4 à 90,7 K) sans ≈ 1 kW de chauffage ; échanges par le dôme commun ; stratification du gaz du ciel.
- **Propulseurs à gaz chauds** pour le pivotement de l'axe (66 à 94 t de méthane-oxygène sur le voyage, impulsions de 20 N au passage de la ligne des nœuds) : le Starship n'a aujourd'hui que des propulseurs à gaz froid (180 à 430 t).
- **Fluage des câbles sur 259 jours** : chiffrer avec les données fabricant (Dyneema DM20 / SK99, Vectran) à la température réelle du câble ; allongement inégal → compensation par treuils.

## Priorité moyenne

- **Avitaillement en orbite basse** : 3 × 1 380 t d'ergols (V3 pleins : 4 800 t), plusieurs dizaines de vols de ravitailleurs ; hypothèse de programme.
- **Télécommunications** : antennes orientables (la Terre s'écarte de l'axe pointé vers le Soleil), compensant la rotation.
- **Physiologie** : efficacité de 0,38 g contre la perte osseuse et musculaire, non démontrée chez l'humain.
- **Entretoises entre brins, tronçons remplaçables, maillage triangulaire** (carnet § 7.5) : brin rompu captif sans coupe-câbles ; raccords ; filet de 9 triangles autour du moyeu.
- **Absorbeurs d'énergie aux attaches** (sangles à déchirement) : plafonner les à-coups ; course nécessaire.
- **Câble réaliste** : simulé en Dyneema SK99 tressé, gainé, redondant (`--material sk99`, 136 cm², 25 t ; campagne `sensibilite`, carnet § 6.3) : même confort, rupture d'un brin identique. Restent : le module réel d'une tresse (plus faible que la fibre, il ramènerait le mode d'étirement des câbles vers 0,36 Hz), la tresse à brins multiples (type Hoytether) et la perte de brins par micrométéorites ; en Kevlar, 51 t.
- **Câbles pour la seule gravité de Mars** : le critère actuel (1 600 t à 1 g, facteur 3) permettrait de simuler la gravité terrestre, au retour par exemple. Si l'on y renonce : 1 600 t sous la gravité de Mars au pont (3,9 m/s² au centre de masse), facteur 3, donnent 36 cm² (Ø 6,8 cm), 6 t au lieu de 15 t (SK99 réaliste : 10 t au lieu de 25 t) ; dimensionnés pour la masse en route (610 à 693 t), 14 à 16 cm² (Ø 4,2 à 4,5 cm), 2 à 3 t. À vérifier avant de choisir : ce n'est plus la charge statique qui dimensionne, mais (1) la rupture : avec deux brins par côté, le brin restant monte à ≈ 2,8 fois sa tension normale, soit 36 % de sa résistance pour le câble « 1 600 t, gravité de Mars », 83 à 94 % pour le câble « masse en route » ; sans parade, la crête (≈ 6 fois la tension normale) romprait ce dernier, et la rupture deviendrait une cascade ; (2) le fluage sur 259 jours, qui croît très vite avec la charge : 13 % de la résistance en route au lieu de 5 %, voire 30 % ; (3) le mode d'étirement des câbles, qui descend comme √A : 0,36 Hz aujourd'hui, ≈ 0,23 Hz (sur le mode du LOX, 0,26 Hz) puis ≈ 0,14 Hz (près du balancement et du bassin, 0,12 Hz) ; (4) les météorites, plus menaçantes pour un câble plus fin ; (5) les à-coups de la mise en rotation et des corrections de trajectoire. À simuler : campagne avec `--design-g 0.40` (et `--design-mass-t`), confort, brins doublés, rupture.
- **Ancrages sur la coiffe** : capacité des points d'attache du Starship (non publiée) ; en route 1,39 MN par câble et 2,41 MN par vaisseau (9,1 et 15,7 MN à 1 600 t et 1 g).
- **Thermique des câbles** (`cable_thermal.py`, carnet § 7.5) : gaine blanche (≈ −70 °C à 1 UA) plutôt que métallisée (+78 °C) ; face au Soleil, éclairement constant, pas de cycles. Reste l'écart face éclairée / face à l'ombre (40 à 105 K, autant d'allongement que la charge en route) : à vérifier sur une vraie tresse (conductivité transverse dans le vide, pas de tresse, glissement des torons) ; feuille d'aluminium sous la peinture en option.
- **Câbles ANCF continus dans Chrono** : modes de câble rapides, raideur en torsion (rappel de roulis négligé aujourd'hui, ce qui va dans le sens de la sécurité).
- **Flexibilité de la coque** et modes de ballottement supérieurs (aujourd'hui : structure rigide, premier mode seulement, réservoirs à fond plat).
- **Ailerons du Starship** dans l'inertie (orientation préférée faible).

## Priorité basse

- Contrôle actif : RCS pour amortir les balancements (le choix actuel est passif ; le pivotement de l'axe vers le Soleil est simulé, § 5.6).
- Gradient de gravité complet en orbite terrestre (repère de Hill) ; en transit héliocentrique, l'effet est négligeable.
- Amarrage d'un véhicule en route (non prévu par le scénario).
- Vieillissement des câbles : rayonnement, micrométéorites, fluage sous charge permanente (lié au fluage ci-dessus).

## Pages

- **Site bilingue français / anglais** : version anglaise des deux pages (et du README), avec un sélecteur de langue ; `build_site.sh` à adapter.

- Après toute nouvelle campagne : mettre à jour la synthèse (§ 1), les limites (§ 16) et la section Reproduire (§ 17) du carnet ; le bilan et « Ce qu'il reste à étudier » de la page grand public ; ce fichier et le README.
