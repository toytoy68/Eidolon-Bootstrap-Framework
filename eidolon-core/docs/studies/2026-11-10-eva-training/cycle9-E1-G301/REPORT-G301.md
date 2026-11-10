# G301 — Eva cycle9 E1 : petit gain horaire, candidat non retenu

Codex/GPT, 10 novembre 2026, Europe/Paris. Base examinée : `3ae9d8a468581b2494388d0968e81871fd9fce00`, branche `feat/eidolon-core-v0.1`. En réponse à C298/G299/G300 et à la reprise conditionnelle explicitement autorisée par toytoy. Lot documentaire pris et livré ; aucun fichier Claude modifié.

## Résultat

100 mises à jour effectives, V100 seule plafonnée à 200 W, FP16/NF4 double quantification, LoRA r8 alpha16, LR initial 3e-6. Parent cycle5 et base inchangés. Le candidat entraîné est conservé comme expérience, pas promu.

| Jeu | Parent | Candidat |
| --- | ---: | ---: |
| Sélection : horaires | 39/160 | 40/160 |
| Sélection : acquis | 26/32 | 25/32 |
| Rapport indépendant : horaires | 79/320 | 83/320 |
| Rapport indépendant : acquis | 26/32 | 25/32 |
| Rapport total | 105/352 | 108/352 |

Rapport horaire : quatre gains et zéro perte, test exact apparié exploratoire p=0,125 ; ce gain ne permet pas de conclure à une amélioration fiable. La règle de sélection exigeait au moins +6 horaires, p<=0,05, perte acquis<=1 et perte par strate<=1. Candidat refusé : seulement +1 sur la sélection, p=1. La colonne APRÈS évalue bien les poids entraînés même lorsque le parent reste la référence expérimentale.

## Strates indépendantes

Chaque cellule contient 32 cas, seuil durée courte <=1500 minutes.

| Strate | Parent | Candidat |
| --- | ---: | ---: |
| jour0 court gabarit0 | 32 | 32 |
| jour0 court gabarit1 | 26 | 28 |
| jour1 court gabarit0 | 14 | 15 |
| jour1 court gabarit1 | 7 | 8 |
| jour1 long gabarit0 | 0 | 0 |
| jour1 long gabarit1 | 0 | 0 |
| jour2 court gabarit0 | 0 | 0 |
| jour2 court gabarit1 | 0 | 0 |
| jour2 long gabarit0 | 0 | 0 |
| jour2 long gabarit1 | 0 | 0 |

Les cas longs et sur deux jours ne progressent pas. La perte acquise concerne la famille6 (3→2/4). Les autres familles acquises restent identiques. Le bénéfice observé reste local aux durées courtes.

## Intégrité et répétabilité

Après le redémarrage, boot `f006076b-6010-48c7-8104-046b21152e0f` : deux copies RAM avec tous les compteurs source/destination à zéro, memtester4GiB complet avec mlock réussi, deux SHA256 successifs de chaque fichier source conformes, adaptateur parent conforme. Les preuves d'échec du boot précédent restent conservées : aucun diagnostic définitif de la cause matérielle, aucune modification BIOS. Une qualification bornée ne garantit pas la stabilité de toute la RAM ni des démarrages futurs.

E-bruit : deux générations neuves de 192 questions +8 canaris, aucun cache, mêmes paramètres/V100/parent. Zéro différence de réponse ou de score, canaris égaux. Limite : un seul processus et un seul chargement de la base ; ce n'est pas une répétition entre deux chargements indépendants. E1 utilise 384 tokens maximaux pour ses évaluations, contre192 pour les questions E-bruit : E-bruit ne mesure donc pas exactement tout le protocole E1. Le seuil +6 reste une précaution exploratoire, pas un intervalle de bruit estimé entre redémarrages.

Premier lancement E-bruit échoué avant chargement pour un chemin relatif imbriqué ; chemin absolu corrigé, traces conservées. Aucun contournement des gardes. Test court4 mises à jour réussi avant E1 réel, espaces de sauvegarde séparés.

À la clôture : service inactif/succès, aucun processus de calcul GPU, aucun guard-trip et aucune alerte noyau Oops/BUG/Hardware Error/Xid/Machine check détectée sur ce boot. Les12 empreintes du manifeste result-saved ont été recalculées et vérifiées, y compris rapport, résultats, poids et état complet100. Les snapshots20/40/60/80/100 et tous les journaux restent sur X399.

## Données et méthode

878 exemples,400 paquets512,100 mises à jour,163208 tokens non rembourrés,50833 tokens supervisés. Rappel cycles4+5 :38058 (74,869%) ; nouvelles cibles :12775 (25,131%). Format time_steps de C298. Nouveaux exemples jours0/1/2 :22/22/21, plus3 bornes4320min correctement étiquetées jour3. L'équilibre en nombre d'exemples ne garantit pas l'équilibre en tokens par strate.

Gabarit1 non utilisé pour les nouvelles cibles E1, sans garantie de nouveauté dans le préentraînement. Opérandes horaires et questions dédupliqués contre les jeux précédents et entre les nouveaux splits. Le final-test-reserved a été lu par CPU uniquement pour l'exclusion des opérandes/questions, jamais généré ni utilisé en entraînement. Son contenu n'est pas publié.

Méthode de masque assistant et pondération par tokens conservée. Paquets par concaténation d'exemples entiers : attention causale entre exemples inchangée, limite connue. Sauvegardes complètes tous20 pas. Pas de reprise automatique des sorties partielles : une continuation éventuelle exige une décision et une qualification explicites.

## Canaris et télémétrie

Relecture des16 sorties avant/après : six paires textuellement identiques ; deux variations de formulation sur personnalité et débat, sans échec évident sur ces sondes. L'explication de mémoire reste générique et imprécise avant comme après. Huit sondes ne valident ni personnalité, ni conversation générale.

Maxima enregistrés : GPU36°C, HBM39°C, CPU Tdie43,375°C, secteur341,7W. Puissance GPU maximum échantillonnée219,08W malgré la limite configurée200W : cette limite n'est pas une preuve d'un plafond instantané strict. Moyennes pendant l'ensemble du run (évaluations comprises) : GPU81,19W, secteur222,05W ; ne pas les présenter comme consommation du seul entraînement.

## Preuves et suite

[Rapport serveur exact](Rapport_Eva_cycle9_E1.txt), [résultat JSON](resultat-final.json), [sélection](checkpoint-selection.json), [canaris](run/canaries-rank0.jsonl), [préparation](dataset-preparation.json), [preuve E-bruit](noise-proof.json), [qualification](requalification/cpu-preflight.json), [sources figées](sources/train.py.txt). Les UUID GPU et adresses LAN sont masqués dans les copies publiques ; source-index.json distingue les SHA256 serveur et publication. result-saved.json conserve les hashes originaux serveur, il ne sert pas à vérifier les copies publiques expurgées.

Proposition pour revue Claude, non lancée : analyser les erreurs ligne par ligne sur les jours1/2 puis essayer E2 en harmonisant uniquement le rappel horaire au format time_steps, avec séparation des comparaisons de format et de justesse. Ne pas augmenter simultanément LR, quantité de cibles et nombre de pas. Aucun E2/E3 exécuté, aucune adoption automatique, aucun arrêt ni redémarrage machine. Parent expérimental conservé.
