# Registre des essais de modèles Eidolon

Mise à jour : 12 octobre 2026. Mesures sur VM101 Tesla V100 16 Go, via tunnel SSH depuis Core, mémoire de VM110. Les essais CPU anciens sont conservés comme observations non qualifiées.

## Protocole veille

Douze questions indépendantes par candidat, sans historique : dix résumés de fiches externes et deux questions pièges (score français absent, achat non établi). Rappel réel à chaque question, cinq extraits maximum, 4 000 caractères de contenu maximum, 800 par extrait. Identifiants, révisions et statut UNVERIFIED sont conservés dans le contexte compact.

Ollama : contexte configuré 4 096 tokens, réponse plafonnée à 512 tokens, température 0,2, seed 42, think=false. Une requête d'échauffement précède chaque série ; elle est hors moyenne. La taille effective du prompt est le prompt_eval_count retourné par Ollama. Le débit est eval_count / eval_duration, pondéré sur la durée de génération pour les moyennes ; il inclut les tokens de l'enveloppe JSON. Longueur en caractères et mots : texte de réponse seul. Temps total = rappel + requête de génération ; ce n'est pas une mesure du navigateur ni de l'API conversation complète.

Un premier protocole envoyant toute la provenance JSON a échoué sur plusieurs questions ; ses sorties restent enregistrées séparément. Le protocole compact mesure les mêmes fiches avec un contexte plus court. Aucun résultat négatif n'est effacé. Les citations automatiques vérifient les identifiants présents et la référence attendue ; leur justesse sémantique exige une lecture des réponses.

Les mesures historiques à cinq questions, sans les nouvelles fiches, excluent le rappel dans leur temps d'inférence. Elles ne sont pas directement comparables avec le temps total de la recette veille. Les valeurs absentes restent nulles.

## Résultats du contexte compact

| Modèle | Prompt moyen (tokens) | Réponse moyenne (tokens / caractères) | Génération (tokens/s) | Inférence (s) | Total avec rappel (s) | Référence exacte attendue |
|---|---:|---:|---:|---:|---:|---:|
| gemma4:12b | 1348 | 131 / 401 | 111.2 | 2.49 | 7.30 | 12/12 |
| qwen3.5:9b | 1318 | 111 / 343 | 86.9 | 1.90 | 6.71 | 4/12 |

Les 24 réponses sont du JSON valide, sans arrêt sur limite de longueur. Rappel de la fiche attendue : 12/12 pour chaque modèle. Gemma : aucune citation d'identifiant absent. Qwen : un identifiant inventé (DGX Spark), plusieurs identifiants sans révision, et une référence écrite sous une autre forme (AstaBrief avec révision 1 en prose). Le score strict porte sur information_id@revision, pas sur une mesure générale de vérité. Les deux répondent que le score français est absent et que l'achat du DGX Spark n'est pas établi.

Qwen omet également la date demandée sur les réponses llama.cpp et ProvenanceGuard, ainsi que plusieurs résumés complets. Gemma couvre mieux les éléments demandés sur cet échantillon. Gemma reste donc le profil actif ; Qwen reste une alternative rapide à améliorer pour les citations. Une seule passe par question : pas de mesure de variance ou de fiabilité à grande échelle.

Le rappel représente environ 4,82 s par appel sur cette recette ; diminuer son coût constitue une piste distincte de l'augmentation du débit du modèle.

## Historique des autres modèles GPU

| Modèle | Cas | Contexte configuré | Réponse moyenne (tokens / caractères) | Génération (tokens/s) | Inférence chaude moyenne (s), hors rappel |
|---|---:|---:|---:|---:|---:|
| gemma4:12b | 5 | 4096 | 68.4 / 182.4 | 100.8 | 3.01 |
| mistral-small3.2:24b | 5 | 4096 | 43.6 / 91.4 | 24.8 | 4.88 |
| qwen3.5:9b | 5 | 4096 | 64.8 / 181.0 | 87.3 | 1.92 |
| qwen3:14b | 5 | 4096 | 54.0 / 128.6 | 63.2 | 2.50 |

CPU antérieur : Gemma3 4B, réponse mémoire en 244,10 s avec clarification ; Qwen3 0,6B, probe en 68,29 s avec diagnostic incorrect. Non qualifiés. Mesures token/s et contexte exact indisponibles ; elles ne sont pas reconstruites.

## Fichiers

- `MODEL-BENCHMARKS.json` : registre structuré des séries et observations anciennes.
- `2026-10-12/veille-models/model-measurements.csv` : mesures par modèle et question.
- `2026-10-12/veille-models/results.json` : réponses, références et mesures détaillées.
- `2026-10-12/veille-models/oversized-context-results.json` : résultats négatifs du premier protocole, interrompu après sept réponses Gemma.
- `2026-10-12/veille-models/run.py` et `cases.json` : reproduction du protocole compact ; nécessite les fiches importées et les tunnels locaux.

## DARME — recette CPU du 12 octobre 2026

96 réponses CPU et 16 réponses témoin GPU supplémentaires sont consignées dans [le bilan DARME](2026-10-12/darme/REPORT.md), avec contexte, longueur, génération, délais, conformité du niveau, actions et citations. Aucun candidat CPU n'est qualifié pour le contrat complet en l'état. Ces mesures ne sont pas des scores de détection réseau réelle.
