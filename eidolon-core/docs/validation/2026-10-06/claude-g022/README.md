# Contre-revue C-TASK-G022 — suivi restauration (`3f16d7d`)

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G022](../../../../collaboration/tasks/C-TASK-G022.md).
Cible figée : `3f16d7d7e270a04f6fa80fcc6cf9daf738bbfa0c` (copie `git archive`).
Base comparée : ma revue G017 sur `3a2a081` ([rapport](../claude-g017/README.md)).
Empreintes identiques à [source-hashes.json](../codex-recovery-followup/source-hashes.json) :
`recovery.py` `8cc5bf2e…a75a`, `store.py` `3cdc314a…f5ee4`,
`tests/test_recovery.py` `6324f46e…2c55`, `tests/test_recovery_followup.py` `f51e394e…cbf7`.
Ni `src/` ni `tests/` Python modifiés ; aucun chemin d'activation créé.

```sh
cd eidolon-core
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$FROZEN/eidolon-core/src python docs/validation/2026-10-06/claude-g022/probes_g022.py
G022_ONLY=p5 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$FROZEN/eidolon-core/src python docs/validation/2026-10-06/claude-g022/probes_g022.py
```

Python 3.11.15, SQLite 3.45.1, Linux.

- [Sortie](probes_g022-output.txt)
- [21 tests de restauration de Codex rejoués sur la copie figée : OK](codex-recovery-tests-on-frozen.txt)

## Verdict : E1 et L1 corrigés ; aucun défaut nouveau

### E1 (G017) — écrivain bloqué pendant la copie : CORRIGÉ

Pour chaque essai, un écrivain dans un **autre processus** crée une mission à
intervalle régulier pendant la préparation. Les étapes du backup sont ralenties
(disque lent simulé, même technique qu'en G017).

| Journal | Étape | Écrivain | G017 (`3a2a081`) | G022 (`3f16d7d`) |
| --- | --- | --- | --- | --- |
| défaut (`delete`) | +0,4 s | toutes les 20 ms | **1 échec** `database is locked` à 5,01 s | **0 échec**, pire attente 0,02 s, 379 commits |
| défaut | +0,4 s | toutes les 1,5 s | — | 0 échec |
| WAL | +0,4 s | toutes les 1,5 s | 0 échec | 0 échec |
| défaut | normale | toutes les 20 ms | 0 échec | 0 échec |

Dans tous les cas, la copie est **liée** : aucun événement orphelin, chaque
mission a son `CREATED`, chaque reçu pointe vers une mission et un événement.
Le rapport porte `capture_semantics=sqlite-online-backup`.

Constat conforme au nouveau contrat : avec un écrivain continu, SQLite
recommence la copie après chaque commit externe. La copie ne se termine donc
qu'**après** l'arrêt de l'écrivain : 41 étapes, 381 missions copiées. Elle
représente la fin du backup, pas le moment de la validation initiale.

**Écriture continue plus longue que le budget** (40 s, contre un budget de
30 s) :

- la préparation s'arrête à 30,1 s avec `RECOVERY_BACKUP_LIMIT` ;
- l'écrivain fait 739 commits, **0 échec** ;
- le dossier reste incomplet et bloqué (`Store` refusé, `RECOVERY_INCOMPLETE`).

C'est la limite annoncée : une activité continue peut épuiser le budget. Elle
est sûre, mais une copie n'est obtenue qu'en période calme.

### Contrôle de la copie terminée : CONFORME

Le `store_id` de la source est changé par SQL brut pendant le backup :

- la préparation rend `RECOVERY_SOURCE_CHANGED` ;
- le fichier `review.pending.sqlite3` reste en place, rien n'est publié ;
- `Store` est refusé et l'inspection rend `RECOVERY_INCOMPLETE`.

### L1 (G017) — dossier incomplet sans marqueur : CORRIGÉ

Le processus est tué (`os._exit`) à 5 étapes. La source reste toujours
inchangée.

| Étape de la panne | Avant G022 (G017) | G022 |
| --- | --- | --- |
| pendant le backup, avant la garde, avant le lien | marqueur retiré à la main → **Store vivant vide créé** | `Store` **refusé**, aucun `missions.sqlite3` créé ; inspection `RECOVERY_INCOMPLETE` (CLI : code 2) |
| après le lien, ou après la publication | inspection OK, Store refusé | inchangé : inspection OK, Store refusé même sans marqueur |

### Copie publiée : CONFORME

- L'accord APPROVED reste une donnée historique.
- `execution_authority=false`.
- Marqueur retiré : `Store` reste refusé par la garde en base.

## Remarque (pas un défaut)

`Store` refuse désormais **tout** dossier qui contient un fichier nommé
`review.pending.sqlite3`, y compris un dossier vivant où ce fichier traînerait
par erreur. C'est un refus prudent : il ne produit aucun faux succès. Le
message `RECOVERY_REVIEW_ONLY` pourrait nommer le fichier en cause.

## Limites

- Disque lent **simulé**, et une seule taille de base (16 Mio).
- Taille dépassée pendant la copie : non retestée (test de Codex).
- SQL brut, disque réel, NAS, ancien binaire : hors garantie, comme annoncé.
