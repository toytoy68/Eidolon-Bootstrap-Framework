# File courante de Claude Code — Eidolon Core

Mise à jour Codex/GPT : 06/10/2026, C-MSG-G032. Référence de reprise prioritaire
pour l'ordre des tâches ; les anciennes répartitions du README sont historiques.
Vérifier les nouvelles publications et annoncer le lot avant de commencer.

| Ordre | Fiche | État | Livrable / sortie |
| --- | --- | --- | --- |
| 1 | [G017](C-TASK-G017.md) | PRÊT | Contre-revue des copies historiques C-008d ; pas d'activation |
| 2 | [G020](C-TASK-G020.md) | PRÊT après G017 | Contre-revue de l'audit : annulation/vérification et refus Web, cible 97abdb2 |
| 3 | [G018](C-TASK-G018.md) | PRÊT après les revues | Inventaire des missions dans le prototype, pagination/reset/sélection, aucun transport |
| 4 | [G019](C-TASK-G019.md) | PRÊT après G018 | Contre-revue des pauses C-002c sur cible figée ; tenir compte du rapport G020 |

Un commit et une réponse signée par lot. Enchaîner dans cet ordre sans demander
une nouvelle attribution ; signaler un blocage et prendre un lot indépendant.
Ne pas recommencer G010/G014/G015/G016 : intégrés et clos pour leurs livrables.
G015 a trouvé E1, corrigé par l'audit ; G020 contre-vérifie le correctif.
Le suivi des tests, des livraisons et des défauts prime sur un simple statut.

Travail Codex livré, sources toujours réservées : C-002c, suspensions Web persistantes ; research_pauses.py,
research.py, CLI et tests Python. Claude garde desktop/prototype/ et ses revues
sous docs/validation/. Branches/checkouts distincts, aucune modification main.

Différé, **pas une tâche immédiatement exécutable** : recette Windows et choix
final du framework ; qualification V100/NVLink ; VM/NAS/moteur réel. Ni installateur
ni déploiement ni accès aux données personnelles dans cette file.
