# DARME — intégration C144 et recette réduite, 12 octobre 2026

Le correctif R6 empêche une longue histoire de masquer une alerte : projection bornée, alertes prioritaires, comptage des alertes omises, état partiel explicite. Le journal refuse les nouvelles admissions au quota sans supprimer les alertes. Acquittements horodatés, migration sans date inventée, transactions et fraîcheur des sondes sont testés.

Le conseiller reçoit le niveau logiciel et des extraits numérotés. Il produit uniquement une explication et des numéros ; le code résout les références. Aucun pouvoir de triage ou d'exécution. Repli fixe en cas de sortie refusée ou d'indisponibilité. Bibliothèque/adaptateur intégrés : le service permanent, collecteurs authentifiés, API, file et isolation restent à développer.

## Tests

| Recette | Résultat |
|---|---|
| Core, intégrations Memory opt-in incluses | 1 494 réussis, aucun ignoré, 185,025 s |
| DARME ciblés et sonde R6 de Claude | 52 réussis |
| Memory, corpus temporaire isolé | 2 018 tests + 12 subtests réussis, 56,53 s |
| Client Node connecté | 112 réussis, 27 ignorés, zéro échec |

Les tests navigateur et Windows matériels ne sont pas couverts. Le journal de la suite Core contient une exception RemoteDisconnected dans un thread d'un test HTTP malgré le résultat global OK ; cela reste une limite du harnais à investiguer, pas une preuve de fonctionnement réseau parfait. Le premier lancement Memory avec unittest/venv inadapté a échoué ; la recette pytest finale dans le venv du dépôt passe.

## Comparaison des modèles

690 réponses : jeux A de 14 cas et B de 40 cas, figés avant inference. Gemma3 1B, Qwen3 1.7B, Granite4 350M et témoin Gemma4 12B : 54 cas × trois graines (17,42,123), soit 162 réponses chacun. Les trois autres candidats répètent A une fois. Les six petits modèles tournent en CPU forcé sur VM101 ; le témoin utilise la V100. Ce ne sont pas des mesures CPU sur VM110.

Contexte configuré : 4 096 tokens, sortie maximale 400 tokens, température 0, think=false. Temps API chaud, sans rappel Memory par réponse. Les graines ne rendent pas le corpus indépendant. Le débit pondéré utilise les tokens générés et leur durée de génération ; les moyennes de longueur incluent les sorties brutes refusées.

| Modèle | Matériel | N | Prompt tokens | Réponse tokens / caractères | tokens/s | Moyenne s | p95 s | JSON valide | Références valides* | Critères automatiques |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| gemma3:1b | CPU | 162 | 323.3 | 55.4 / 191.5 | 24.9 | 4.64 | 7.70 | 162/162 | 87.8 % | non satisfaits |
| qwen3:1.7b | CPU | 162 | 359.9 | 43.4 / 132.7 | 17.1 | 4.68 | 8.58 | 162/162 | 100.0 % | non satisfaits |
| granite4:350m | CPU | 162 | 347.9 | 25.2 / 22.8 | 31.4 | 1.38 | 1.53 | 159/162 | 98.0 % | non satisfaits |
| qwen3:0.6b | CPU | 14 | 429.7 | 56.6 / 152.9 | 38.1 | 2.64 | 4.47 | 14/14 | 83.3 % | non satisfaits |
| qwen3.5:0.8b | CPU | 14 | 386.6 | 92.0 / 348.4 | 17.6 | 7.54 | 10.60 | 14/14 | 100.0 % | non satisfaits |
| smollm2:1.7b | CPU | 14 | 485.0 | 109.0 / 134.4 | 11.2 | 14.20 | 42.64 | 12/14 | 83.3 % | non satisfaits |
| gemma4:12b | GPU | 162 | 327.3 | 38.3 / 131.2 | 106.4 | 0.74 | 0.94 | 162/162 | 93.9 % | réussis |

*Couverture des cas avec sources : indices valides et au moins une citation. Ce score ne mesure pas si la source soutient l'affirmation.

Aucun candidat CPU ne remplit tous les seuils (JSON ≥99 %, couverture ≥90 %, aucune contradiction/instruction détectée, p95 ≤15 s, aucune troncature). Gemma4 passe les critères automatiques seulement. Le secours CPU n'est pas adopté. Les formulations et citations progressent avec le contrat réduit : cet échec de qualification ne démontre pas que les modèles seraient inutilisables pour d'autres tâches.

## Limites de la validation sémantique

Une relecture Codex de 20 sorties Gemma4, conservée dans codex-review-sample20.json, n'est pas la revue humaine indépendante demandée par Claude. Elle révèle des erreurs échappant aux heuristiques : B15 affirme une exemption d'alerte malgré le niveau critique ; A-evealert confond la date de collecte de la fiche avec celle du trafic ; B03 attribue un blocage à CrowdSec sans observation correspondante ; A-capacity présente une isolation recommandée comme déjà installée. Le contrôle peut aussi refuser à tort la description « La sonde redémarre » (B01). Aucun taux de bonnes réponses sémantiques n'est donc certifié.

Les réponses ont été recontrôlées avec le filtre final : final-results.json est un rescore des mêmes inférences, results.json conserve les contrôles initiaux. Le prompt et les cas n'ont pas été adaptés après observation des sorties. Le banc autorise 60 s pour mesurer les dépassements ; l'adaptateur livré demande au maximum 15 s au transport.

Le test réel de l'adaptateur Gemma4 avec rappel du bridge Memory retourne une référence résolue et advisory_only=true, authorizes_execution=false. Sa durée 7,25 s inclut le chargement froid mais exclut le rappel effectué avant le chronométrage ; elle n'est pas directement comparable à la moyenne chaude.

## Reproduction et déploiement

Code local validé d6805fb7eae62a262ce6a5877aa3d7b1e4cb6b8e, Memory f7136239b702c70b9c0021f57a27208075fd79f3. Les deux fichiers journal/tests incorporent le dernier rejet des dates explicitement vides ou non textuelles. run.py, rescore.py, cas figés, mesures CSV, sorties et métadonnées sont joints. Les services Core/Memory existants restent disponibles ; aucun service DARME permanent ni remédiation n'a été activé.

Claude reçoit le lot G146–G151 pour communications STT/TTS, caméras et reconnaissance visuelle, avec inventaire réel, contrats, tests et déploiement. L'affectation documentaire ne signifie pas que sa session a démarré.
