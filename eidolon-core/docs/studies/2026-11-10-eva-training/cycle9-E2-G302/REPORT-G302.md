# G302 — Eva E2 terminé : rappel horaire harmonisé, gain insuffisant

Codex/GPT,10/11/2026,Europe/Paris. Base : `d0778fa02e500d6778695a8711fbf6ffd4e5c226`, branche `feat/eidolon-core-v0.1`. Suite expressément autorisée par toytoy après E1. Lot documentaire pris et livré, canal Claude préservé.

## Résultats vérifiés

| Rapport sur les mêmes questions | Parent cycle5 | E1 | E2 |
| --- | ---: | ---: | ---: |
| Horaires | 79/320 | 83/320 | 84/320 |
| Acquis | 26/32 | 25/32 | 25/32 |
| Total | 105/352 | 108/352 | 109/352 |

E2 sélection : horaires39→41/160, acquis26→25/32, total65→66/192 ; deux gains horaires, zéro perte horaire, p exact exploratoire0,5. Règle fixée avant essai : gain>=6 horaires et p<=0,05, perte acquis<=1, perte par strate<=1. Le candidat est refusé ; parent conservé expérimentalement, aucune promotion.

Rapport E2 : cinq gains horaires,zéro perte horaire,p exact exploratoire0,0625. Cette valeur ne valide pas l'amélioration ; +1 réponse face à E1 ne permet pas d'attribuer un bénéfice fiable à l'harmonisation. Tous les scores de contenu sont ici identiques aux scores JSON exacts, zéro troncature avant/après.

| Strate,32 cas chacune | Parent | E1 | E2 |
| --- | ---: | ---: | ---: |
| jour0 court gabarit0 | 32 | 32 | 32 |
| jour0 court gabarit1 | 26 | 28 | 28 |
| jour1 court gabarit0 | 14 | 15 | 15 |
| jour1 court gabarit1 | 7 | 8 | 9 |
| jour1 long gabarit0 | 0 | 0 | 0 |
| jour1 long gabarit1 | 0 | 0 | 0 |
| jour2 court gabarit0 | 0 | 0 | 0 |
| jour2 court gabarit1 | 0 | 0 | 0 |
| jour2 long gabarit0 | 0 | 0 | 0 |
| jour2 long gabarit1 | 0 | 0 | 0 |

Durée courte<=1500min ; combinaison jour0-long physiquement exclue. Aucun progrès sur durées longues ni jour2. Régression acquise dans la famille6 :3→2/4, les autres familles inchangées.

## Ce qui a été modifié

Même parent cycle5, mêmes878 exemples, IDs, questions, ordre, attendus et jeux d'évaluation que E1. Seules101 réponses horaires du groupe replay ont été réécrites avec time_steps de C298. Même V100200W, FP16/NF4 double quantification, LoRA r8alpha16, LR initial3e-6, masquage assistant et pondération par tokens. Diff de données et quatre tests de politique vérifiés avant lancement.

Le texte plus long entraîne408paquets512 et102updates, contre400/100 pour E1 ; tokens supervisés :47334 rappel +12775 cibles=60109, soit21,253% cibles contre25,131% E1. Cette comparaison ne maintient donc pas le budgettoken, la pondération relative des groupes, le placement dans les paquets ni exactement la trajectoire du scheduler. Ce n'est pas une isolation causale parfaite du seul format. Les jeux sont réutilisés depuis E1 avec générations neuves, pas de nouveau test aveugle.

Le final-test-reserved du cycle8 n'a pas été évalué ni entraîné. E2 reprend les splits d'E1 sans nouvelle lecture du lot réservé ; lors de la préparation E1 il avait été lu par CPU uniquement pour exclusion d'opérandes/questions.

## Intégrité et répétabilité entre chargements

Même boot qualifié `f006076b-6010-48c7-8104-046b21152e0f`. Préflight antérieur :memtester4GiB complet avecmlock, copies RAM2x zérocompteur source/destination et doubles hashes source, parent conforme. Pas de réparation matérielle prouvée ni de réglage BIOS changé.

Smoke4updates réussi, puis copies RAM2x et hashes source2x refaits au chargement réel. Avant toute mise à jour réelle,352 réponses parent et8canaris nouvellement générés sont EXACTEMENT identiques aux sorties E1 avant : même V100/précision/configuration, aucun cache, chargements indépendants. Voir [preuve](run/baseline-equivalence.json). Ce contrôle est plus fort que l'E-bruit intra-processus d'E1 ; il reste limité à ce boot et ces questions.

À la clôture : service inactif/succès,aucun processus de calcul GPU,aucun guard-trip,aucune alerte noyau Oops/BUG/Hardware Error/Xid/Machine check détectée. Les14 SHA256 de result-saved.json ont été recalculés conformes,dont poids et sauvegarde complète102. Snapshots20/40/60/80/100/102 et tous les journaux/données conservés sur X399. Aucune extinction ni reboot effectué.

## Lecture ligne par ligne

[Les six changements de justesse](paired-changes.json) contiennent les cinq gains horaires et la perte acquise :
- Trois gains corrigent la conversion HH:MM→minutes (13:37,11:48,02:55).
- Deux gains corrigent le nombre de jours après minuit.
- La perte acquise transforme une division correcte681549/209=3261 en3259.

Les explications gagnantes ne déroulent pas systématiquement toutes les étapes time_steps entraînées. L'observation ne prouve donc pas l'acquisition de l'algorithme complet. Les échecs jour2 restent le prochain objet de diagnostic, pas une raison suffisante pour augmenter plusieurs hyperparamètres à la fois.

Canaris relus : quatre réponses identiques,quatre modifiées (désaccord,fiction,personnalité,débat). Pas d'effondrement conversationnel évident sur ces huit sondes. La réponse personnalité propose de stimuler les plantes par fréquences sonores : cadre fictif de la question, mais formulation scientifique non étayée, à ne pas convertir en capacité validée. Réponse mémoire générique inchangée ; aucune validation générale.

## Télémétrie et conservation

Maxima enregistrés pendant le run complet : GPU36°C,HBM39°C,CPU Tdie43,375°C,secteur342,8W. Moyennes incluant évaluations :GPU81,09W,secteur221,70W. Pic GPU échantillonné227,858W malgré limite configurée200W ; le réglage n'est pas une borne instantanée démontrée. Pas de comparaison d'énergie d'entraînement à partir de ces moyennes globales.

[Rapport serveur exact](Rapport_Eva_cycle9_E2.txt),[résultats](resultat-final.json),[manifeste serveur](result-saved.json),[données statistiques](dataset-preparation.json),[canaris](run/canaries-rank0.jsonl),[sources figées](sources/train.py.txt). Copies publiques expurgées des UUID GPU/adressesLAN ; source-index.json distingue empreintes originales et publiques. Ne pas appliquer les hashes serveur aux copies expurgées.

Aucun E3 automatique. Prochaine étape proposée : revue des erreurs longues/jour2 et d'un protocole qui départage conversion, retenue de jours et soustractions1440, avant nouvel essai. L'objectif reste l'amélioration du LLM ; aucun outil Core de calcul substitué.
