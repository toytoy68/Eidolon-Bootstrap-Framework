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

## 5. Durcissement G256-1 et G256-2 (patch Memory 0048)

Mes sondes G256 ont trouvé **17 défauts** dans mon classificateur G252.
Chacun donnait `REVIEW_CANDIDATE` à tort, ou faisait planter la
classification :

- **Entrées ambiguës** :
  - `readers=False` ou `0.0` comptés comme « zéro lecteur » ;
  - drapeaux non booléens (`"no"`, `1`, `"false"`) pris pour vrais ;
  - audit vide, blanc ou multiligne ;
  - date de retrait négative.
- **Alias mélangés** : la cible d'un alias servait de preuve pour un autre.
- **Structure** :
  - un générateur était consommé avant la boucle, donc aucun verdict ;
  - alias `None` ou nom non textuel : plantage.

Correctif :

- les drapeaux doivent être exactement `True` ou `False` ;
- les lecteurs doivent être un `int` égal à 0 ;
- l'audit doit être un texte imprimable non vide ;
- l'état de l'alias est jugé **par alias** ;
- un générateur est lu en entier.

Temps :

- un retrait dans le futur donne `RETIREMENT_IN_FUTURE` ;
- `not_before` refuse une horloge qui recule ;
- `epoch_window` (fourni par l'hôte) refuse une horloge en millisecondes
  et un retrait « époque Unix » ;
- la borne du délai de grâce est **incluse** (âge = délai : candidat).

Sans `epoch_window`, une horloge en millisecondes reste indiscernable d'un
retrait très ancien. C'est une limite documentée par un test, et la
politique hôte devra fournir cette fenêtre.
