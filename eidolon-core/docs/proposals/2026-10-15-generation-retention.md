# Rétention des générations Qdrant : proposition sans suppression (Claude, G252-7)

Auteur : Claude. Date : 15/10/2026. Base Memory : `9a61648`.
Statut : **proposition**. Aucun `delete`, aucun `drop`. Ne clôt pas G201 Q3.
Expérience : [patch Memory 0046](../../collaboration/memory-patches/0046-claude-g252-generation-retention.patch)
(`tests/claude_memory_eval/generation_retention.py`, réservé aux tests).

## 1. Inventaire : les états possibles d'une génération

| État | Comment on le reconnaît | Exemple |
| --- | --- | --- |
| Active | cible de l'alias | après `rebuild` réussi |
| Préparée | collection `alias__<hex>` en cours de construction, pas encore cible | `rebuild` en cours |
| Échouée | collection sans descripteur valide, ou incomplète | `rebuild` interrompu (le cas de G201 Q3) |
| Retirée | ancienne cible, descripteur valide et complète, remplacée par une bascule auditée | génération précédente |
| Étrangère | nom qui ne suit pas `alias__<32 hex>` | collection d'un autre usage |

## 2. Preuves nécessaires avant de proposer un retrait

Toutes sont exigées. **Une seule inconnue garde la génération.**

| Preuve | Source | Si inconnue |
| --- | --- | --- |
| l'alias désigne exactement une génération, lue maintenant | Qdrant `get_aliases` | `KEEP_UNCERTAIN` pour toutes |
| ce n'est pas la cible | idem | `KEEP_ACTIVE` |
| descripteur et complétude connus | descripteur, comptage | `KEEP_UNCERTAIN` |
| aucun lecteur actif | registre de l'hôte | `KEEP_READERS` |
| date de retrait **et** référence d'audit de la bascule | journal d'audit de l'hôte | `KEEP_UNCERTAIN` |
| délai de grâce écoulé (fourni par l'hôte) | horloge de l'hôte | `KEEP_RECENT` |

Une génération échouée n'a pas d'historique de retrait. Elle est gardée
(`KEEP_FAILED_EVIDENCE`) jusqu'à ce qu'un humain l'examine.

## 3. Classificateur expérimental

`classify(facts, now=…, grace_seconds=…)` est une fonction pure :

- aucun client, aucune horloge lue ;
- le meilleur verdict possible est **`REVIEW_CANDIDATE`**, c'est-à-dire une
  demande de décision humaine ;
- 6 tests : la génération active n'est jamais candidate ; toute inconnue
  la garde ; un alias incertain protège tout ; délai, lecteurs et
  construction échouée sont respectés ; noms étrangers et entrées
  invalides sont refusés ; le module ne contient aucun appel de
  suppression.

## 4. Étapes suivantes, à décider

1. L'hôte tient un **journal d'audit** des bascules d'alias. Il est
   indispensable pour prouver un retrait.
2. Un **registre des lecteurs**, même grossier (compteur par génération).
3. Une API d'administration séparée (Q2) qui ne supprime qu'avec une
   décision humaine signée, rejouable et auditée, sur le modèle de
   `recover_clock`.
