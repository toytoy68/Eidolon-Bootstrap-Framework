# Résultats enregistrés

Les valeurs ci-dessous proviennent des JSON et rapports du serveur ; aucune nouvelle inférence dans cette transmission.

| Cycle | Parent | Exemples | Correct avant → après | JSON exact avant → après | Interprétation |
|---|---|---:|---|---|---|
| 1 | pilote200 | 10000 | 54 → 129 / 160 | 52 → 127 | gain ciblé |
| 2 | cycle1 | 10000 | 129 → 124 / 160 | 127 → 121 | régression |
| 3 | cycle1 | 4800 | 246 → 234 / 320 | 242 → 231 | régression |
| 4 | cycle1 | 2400 | 302 → 308 / 384 | 298 → 304 | gain total avec recul historique |
| 5 | cycle4 | 2400 | 432 → 434 / 512 | 428 → 428 | petit gain total, bases en recul |
| 6 | cycle5 | 2400 | 502 → 475 / 608 | 496 → 469 | régression nette |
| 7 | cycle5 | 2400 | 502 → 502 / 608 | 496 → 496 | parent restauré, pas entraîné retenu |

## Sous-ensembles des cycles4–7

| Cycle | Historiques /160 | Régression /160 | Compréhension /64 | Bases /128 | Cibles /96 |
|---|---|---|---|---|---|
| 4 | 129 → 126 | 117 → 121 | 56 → 61 | — | — |
| 5 | 126 → 128 | 121 → 122 | 61 → 62 | 124 → 122 | — |
| 6 | 128 → 122 | 122 → 115 | 62 → 55 | 122 → 123 | 68 → 60 |
| 7 | 128 → 128 | 121 → 121 | 62 → 62 | 122 → 122 | 69 → 69 |

## Audit cycle8 : comparaison réelle des checkpoints

| Candidat | Challenge /160 | Horaires /96 | Acquis /32 | NLL challenge |
|---|---:|---:|---:|---:|
| cycle5-parent | 109 | 48 | 26 | 0.6022 |
| cycle7-step-40 | 107 | 48 | 26 | 0.5806 |
| cycle7-step-160 | 108 | 48 | 24 | 0.6151 |
| cycle7-step-286 | 105 | 45 | 24 | 0.6347 |

Les quatre candidats obtiennent0/24 sur plusieurs jours,30/32 fractions et17/24 conversions. Minuit7/24 puis7/24,8/24,8/24. Même jour24,24,23,20/24. Le pas40 baisse la NLL sans améliorer l’exactitude ; le pas286 perd4 bonnes réponses au total et2 sur les acquis par rapport au parent. Ces écarts ne constituent pas un test de significativité ni une preuve de généralisation.

## Pilote et performances

Pilote200/250/300/350W : pertes synthétiques après0,00311 /0,00156 /0,00267 /0,00446, depuis0,46171 ;124/126/126/125 mises à jour en environ300s. Chaque essai repart du même adaptateur. La perte synthétique ne mesure pas la justesse arithmétique.

| GPU | Limite W | 1 requête tok/s | 2 simultanées, par requête | 4 simultanées, par requête |
|---|---:|---:|---:|---:|
| V100 | 150 | 108.30 | 75.62 | 46.17 |
| V100 | 200 | 120.56 | 84.79 | 52.34 |
| V100 | 250 | 125.41 | 89.11 | 56.24 |
| V100 | 300 | 125.63 | 90.06 | 56.85 |
| RTX3080Ti | 200 | 93.14 | 67.75 | 40.52 |
| RTX3080Ti | 250 | 129.72 | 96.21 | 56.24 |
| RTX3080Ti | 300 | 136.73 | 101.53 | 59.75 |
| RTX3080Ti | 350 | 140.30 | 104.40 | 61.54 |

Même modèle GGUF/corpus annoncé ; V100300s par puissance découpées en100s par concurrence, échantillons courts (2–4 requêtes complètes selon cas), ordre ascendant ; RTX référence historique plus longue et requêtes communes appariées. Comparatif non simultané et non randomisé : ne pas attribuer tous les écarts à la seule architecture GPU. Ces débits concernent ce4B et ce protocole, pas la vitesse d’entraînement.

Les températures, puissances moyennes, nombres de requêtes, interruptions en bord de fenêtre et TTFT détaillés sont dans inventory-and-benchmarks.json. Une limite de puissance n’est pas une consommation moyenne.

## Suite proposée, non lancée

Conserver cycle5 ; revoir les erreurs et le correcteur ; petits essais horaires séparés depuis ce parent, environ75% rappel /25% cibles en tokens supervisés. Réduire le nombre de variables modifiées simultanément, validation plus discriminante, critères par famille et canaris relus ; test final réservé une seule fois après sélection. Toute extension de couches reste une expérimentation distincte, absente des cycles réalisés.
