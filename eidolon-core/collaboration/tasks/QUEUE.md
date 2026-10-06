# File courante de Claude Code — Eidolon Core

Mise à jour Codex/GPT : 06/10/2026, C-MSG-G034. Référence de reprise prioritaire
pour l'ordre des tâches ; les anciennes répartitions du README sont historiques.
Vérifier les nouvelles publications et annoncer le lot avant de commencer.

| Ordre | Fiche | État | Livrable / sortie |
| --- | --- | --- | --- |
| 1 | [G021](C-TASK-G021.md) | PRÊT | Cohérence du total de missions affichées |
| 2 | [G022](C-TASK-G022.md) | PRÊT après G021 | Contre-revue restauration corrigée dans 3f16d7d |
| 3 | [G023](C-TASK-G023.md) | PRÊT après G022 | Abandon explicite d'un résultat non vérifié |
| 4 | [G024](C-TASK-G024.md) | ATTENTE correctif GPT | Contre-revue Web, capacité et diagnostic mission_id |

Un commit et une réponse signée par lot. Enchaîner dans cet ordre sans demander
une nouvelle attribution ; signaler un blocage et prendre un lot indépendant.
Ne pas recommencer G010/G014/G015/G016/G017/G018/G019/G020 : intégrés et clos pour leurs livrables.
G020 confirme le correctif E1 ; G023 traite la fermeture d’une vérification indisponible.
Le suivi des tests, des livraisons et des défauts prime sur un simple statut.

Travail Codex : suites Web G019 et parseur R-G020-1 ; research.py,
research_pauses.py, commands.py, tests et docs associés. Claude garde le
prototype, ses revues et runtime.py/action_view.py pour G023. Branches/checkouts
distincts ; aucune modification main.

Différé, **pas une tâche immédiatement exécutable** : recette Windows et choix
final du framework ; qualification V100/NVLink ; VM/NAS/moteur réel. Ni installateur
ni déploiement ni accès aux données personnelles dans cette file.
