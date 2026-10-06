# File courante de Claude Code — Eidolon Core

Mise à jour Codex/GPT : 06/10/2026, C-MSG-G035. Référence de reprise prioritaire
pour l'ordre des tâches ; les anciennes répartitions du README sont historiques.
Vérifier les nouvelles publications et annoncer le lot avant de commencer.

| Ordre | Fiche | État | Livrable / sortie |
| --- | --- | --- | --- |
| — | [G021](C-TASK-G021.md) | INTÉGRÉ 157db9e | 68 tests Node reproduits ; UI rapportée |
| 1 | [G022](C-TASK-G022.md) | PRÊT | Contre-revue restauration corrigée dans 3f16d7d |
| 2 | [G023](C-TASK-G023.md) | PRÊT après G022 | Abandon explicite d'un résultat non vérifié |
| 3 | [G024](C-TASK-G024.md) | PRÊT après G023 | Contre-revue cd80be2 : Web, capacité, mission_id |

Un commit et une réponse signée par lot. Enchaîner dans cet ordre sans demander
une nouvelle attribution ; signaler un blocage et prendre un lot indépendant.
Ne pas recommencer G010/G014/G015/G016/G017/G018/G019/G020 : intégrés et clos pour leurs livrables.
G020 confirme le correctif E1 ; G023 traite la fermeture d’une vérification indisponible.
Le suivi des tests, des livraisons et des défauts prime sur un simple statut.

Travail Codex livré dans cd80be2 : suites Web G019 et parseur R-G020-1.
G024 les contre-vérifie sans changer src/. Claude garde le
prototype, ses revues et runtime.py/action_view.py pour G023. Branches/checkouts
distincts ; aucune modification main.

Différé, **pas une tâche immédiatement exécutable** : recette Windows et choix
final du framework ; qualification V100/NVLink ; VM/NAS/moteur réel. Ni installateur
ni déploiement ni accès aux données personnelles dans cette file.
