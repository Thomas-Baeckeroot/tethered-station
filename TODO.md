# À étudier ou développer

Liste de travail, par priorité pour le scénario Terre–Mars. Les limites du modèle sont aussi listées au § 16 du carnet technique.

## Priorité haute

- **Déploiement avant la mise en rotation** : rapprochement des trois vaisseaux, déroulement des câbles sous 0,1 tr/min (quelques kN de tension), treuils. La montée de 0,1 à 1 tr/min est simulée (carnet § 5.4 : α = 0,05·ω², 30 min, 20 t d'ergols, plancher à 2,6°).
- **Câbles doublés** (meilleure parade simulée contre la rupture, carnet § 7.4) : ferrures (communes aux deux brins, imposées par la stabilité en roulis, § 7.4 ; un arrachement les emporte ensemble), entretoises, emmêlement du brin rompu avec le brin sain.
- **Moyeu et rayons doublés** (carnet § 7.3 ; confort vérifié, campagne `moyeu`) : déploiement des côtés et des rayons depuis le moyeu, treuils ; les rayons, réglés pour 1 tr/min, sont presque détendus pendant la montée.
- **Premier retour du brin rompu** : il touche une coiffe 6 s après la rupture, même avec coupe-câbles. Frein anti-retour près des attaches (comme pour les amarres de navires), protection de la coiffe, ou brin captif (câbles doublés).
- **Contact câble–coque** : absent du modèle (brins qui frappent les coques, câbles qui s'enroulent autour d'une coiffe quand un vaisseau tournoie) ; nécessaire pour la suite d'une rupture sans moyeu.
- **Vaisseau habité allégé** (carnet § 5.5) : le transfert complet des ergols (220 / 805 / 805 t, 0,87 tr/min) rend son plancher six fois plus sensible, et son balancement hors plan (0,072 Hz) échappe au bassin : 4,6°, 1,25° avec un bassin réaccordé à la limite de la coque. Simuler le transfert de moitié (415 / 708 / 708 t, 0,93 tr/min) ou un lest bas.
- **Pattes d'oie** : répartir chaque câble sur plusieurs points d'ancrage du nez, écartés aussi selon l'axe de rotation, pour raidir le balancement hors plan (complément ou alternative au bassin).
- **Chicanes du LOX à ζ = 8 %** (carnet § 6.2 : pire cas 0,46° → 0,32°) : vérifier qu'un anneau juste sous la surface libre, dont le niveau ne change pas en route, atteint cet amortissement. Pics restants ≈ 0,3° vers 0,1 Hz et 0,36 Hz (mode d'étirement des câbles).
- **Bassin d'eau en eau peu profonde, non linéaire** : au pire rythme, la masse équivalente se déplace de 25 à 31 cm pour 0,61 m de profondeur. Vérifier par un modèle d'écoulement en eau peu profonde (déferlement, ressaut, efficacité des grilles), et la tenue de l'accord quand le niveau baisse (l'eau sert aussi de réserve).
- **Thermique face au Soleil** (carnet § 5.6, `sun_pointing.py`, modèle 2D) : valeur réelle de la conductance des tuiles et de leur feutre sous vide et à froid (0,1 à 0,6 W/m²·K supposés), qui fixe le refroidissement net ; montage des panneaux (dos chaud à 50 °C, ≈ 500 W/m² : voile ou mâts) ; régulation des ergols, qui gèleraient (CH4 à 90,7 K) sans ≈ 1 kW de chauffage ; échanges par le dôme commun ; stratification du gaz du ciel.
- **Propulseurs à gaz chauds** pour le pivotement de l'axe (63 à 89 t de méthane-oxygène sur le voyage, impulsions de 18 N au passage de la ligne des nœuds) : le Starship n'a aujourd'hui que des propulseurs à gaz froid (170 à 410 t).
- **Fluage des câbles sur 259 jours** : chiffrer avec les données fabricant (Dyneema DM20 / SK99, Vectran) à la température réelle du câble ; allongement inégal → compensation par treuils.

## Priorité moyenne

- **Entretoises entre brins, tronçons remplaçables, maillage triangulaire** (carnet § 7.5) : brin rompu captif sans coupe-câbles ; raccords ; filet de 9 triangles autour du moyeu.
- **Absorbeurs d'énergie aux attaches** (sangles à déchirement) : plafonner les à-coups ; course nécessaire.
- **Câble réaliste** : tresse à brins multiples (type Hoytether), gaine ; perte de brins par micrométéorites ; masse 24 t (Dyneema SK99 redondant) à 47 t (Kevlar) d'après le § 2.3 du carnet.
- **Ancrages sur la coiffe** : capacité des points d'attache du Starship (non publiée) ; en route 1,31 MN par câble et 2,26 MN par vaisseau (9,1 et 15,7 MN à 1 600 t et 1 g).
- **Thermique des câbles** : gaine blanche (≈ −70 °C au soleil à 1 UA) plutôt que métallisée (+78 °C) ; constante de temps ≈ 6 h, donc pas de cycles dus à la rotation (carnet § 7.5). Reste la dilatation négative du Dyneema et l'ombre des vaisseaux.
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
