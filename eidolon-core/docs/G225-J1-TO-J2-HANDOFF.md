# G225 — Point de reprise après le jalon J1

Date : 14 octobre 2026. Derniers résultats CI vérifiés via GitHub Actions.

## Jalon atteint

- Core, run 38531549417, SHA 366ecce836ed19ef52e437f4104f664e5962f3ba : **1660 passed, 6 skipped, 5 warnings, 1297 subtests passed**.
- Memory, run 38532433571, SHA 4532bc7504f5bebc44f05b37b0258c4a6e002c50 : **2214 passed, 3 skipped, 12 subtests passed**.
- Les 6 skips Core sont des essais d'intégration Memory réelle optionnelle ; au moins un groupe de skips Memory concerne l'absence de qdrant_client dans la CI.

## Liste prioritaire engagée

1. **P0** Qualifier les skips d'intégration Core ↔ Memory : non exécutés, besoin d'environnement isolé commun.
2. **P0** Worker : ajouté `worker_gate.py`, vérification des empreintes, révisions, profil, modèle et permission ; tests verts en CI. Ce module reste purement déclaratif.
3. **P0** Adapter Qdrant réel : à développer, sans suppression automatique.
4. **P0** Restaurer MCP et recette B01–B12 : indisponible, aucun déploiement.
5. **P1** Avertissements Core : cinq, dont concurrence HTTP et fork() multithread ; audit restant.
6. **P1** Benchmarks modèle et rappel réel : en attente VM.

## Prochain jalon

J2 : worker testable en isolation contre le contrat de 19 scénarios, avec relecture canonique immédiate, contrôle d'accès par profil et accusé d'indexation. Aucun droit d'action ne doit découler d'un simple booléen `verified` ou d'une réponse LLM.

Ne pas fusionner main ni modifier la production avant recette VM.
