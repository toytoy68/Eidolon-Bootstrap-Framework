# Contre-revue C-TASK-G017 — copies historiques de restauration (C-008d)

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G017](../../../../collaboration/tasks/C-TASK-G017.md).
Cible figée : `3a2a08127382c577c1aca2a80ccac1d6a1200cdf`, extraite par `git archive`.
Empreintes identiques à [source-hashes.json](../codex-recovery-review/source-hashes.json) (5/5) :
`recovery.py` `4d47088f…88f4`, `store.py` `18f18800…f8a3`, `cli.py` `f0cf67bb…8117`,
`tests/test_recovery.py` `8123aec6…4613`, `examples/recovery_demo.py` `c0d16827…2e13`.
Ni `src/`, ni `tests/` Python modifiés ; aucun chemin d'activation créé.

```sh
cd eidolon-core
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$FROZEN/eidolon-core/src \
  python docs/validation/2026-10-06/claude-g017/probes_g017.py
```

Python 3.11.15, SQLite 3.45.1, Linux. États synthétiques temporaires. Injections :

- `os._exit` dans un processus enfant, à cinq étapes de `prepare_review` ;
- un mandataire autour de la connexion source en lecture seule (même technique
  que le test WAL de Codex), qui ralentit chaque pas de backup pour simuler un
  disque lent ;
- les manipulations de dossier nommées par la fiche.

[Sortie des sondes](probes_g017-output.txt) ·
[16 tests de Codex rejoués sur la copie figée : OK](codex-targeted-tests-on-frozen.txt).

Classement : **ÉCART** · **LIMITE** (déclarée) · **PROPOSITION** · **CONFORME**.

## Résultat

**Les gardes tiennent** sur tous les chemins Core ordinaires, et l'inspection
ne fuit rien. Deux points sont à traiter :

- **E1** : un écrivain vivant peut **échouer**, pas seulement attendre, pendant
  la copie d'une base dans son mode de journal par défaut ;
- **L1** : un état incomplet dont on retire le marqueur à la main devient un
  Store vivant vide.

### 1. Capture cohérente, source intacte (question 1)

Un écrivain dans un autre processus crée une mission toutes les 20 ms pendant
la préparation ; une table de remplissage de 16 Mio allonge le backup.

| Journal de la source | Pas de backup | Préparation | Écrivain | Copie |
| --- | --- | --- | --- | --- |
| défaut (`delete`, celui que crée `Store`) | normal | 0,1 s | 0 échec, pire attente 0,08 s | liée |
| défaut (`delete`) | +0,4 s (disque lent simulé) | 7,3 s | **1 échec `database is locked`** à 5,01 s | liée |
| WAL | +0,4 s | 7,3 s | 0 échec, pire attente 0,02 s | liée |

« Copie liée » veut dire : aucun événement orphelin, chaque mission a son
`CREATED`, chaque reçu pointe vers une mission et un événement présents.

- Sans écrivain, la source est **identique octet pour octet**. Copie :
  `RECOVERY-REVIEW-ONLY` et `missions.sqlite3` seulement.
  `simulation.sqlite3` n'est pas copiée (`artifacts_restored=[mission_sqlite_only]`).

**E1 — ÉCART (limite sous-estimée)**. `Store` ne passe jamais la base en WAL :
le mode réel par défaut est donc `delete`. Dans ce mode, la transaction de
lecture épinglée pendant tout le backup empêche tout commit. Un écrivain
attend son délai SQLite de **5 s**, puis **échoue** ; or le budget du backup
est de **30 s**.

Le contrat dit « Sans WAL, une lecture peut retarder un écrivain ». C'est
inexact pour le cas par défaut : au-delà de 5 s, l'écrivain échoue.

Conséquence probable, par lecture de code (non exécutée ici) : une mission en
cours dans `run` qui échoue en sauvegardant passe dans le gestionnaire
d'exception de `run`. Son propre `save` échoue aussi (verrou toujours tenu),
et la mission reste dans son dernier état durable.

Rien n'est perdu ni mélangé : la copie reste cohérente.

**Pistes, à ton choix** :

- passer les bases Core en WAL ;
- ou ramener le budget du backup sous le délai d'attente des écrivains ;
- ou exiger une source arrêtée, et corriger la phrase du contrat.

### 2. Nouvelle identité et double garde (question 2) — CONFORME

- `Store(copie)` est refusé. **Marqueur retiré**, la garde en base suffit.
- **Store déjà construit sur un dossier vivant, puis fichier remplacé** par la
  copie gardée, sans marqueur dans ce dossier. Tous ces appels sont refusés :
  `get`, `ClientSync.snapshot`, `CancelCommands.submit` avec la nouvelle
  identité, `lookup_receipt`, `run` sur la mission APPROVED, `decide`,
  `ActionRuntime(store).run`. **0 redémarrage**. Seuls des fichiers `.lock` et
  `simulation.sqlite3` existent dans ce dossier vivant ; aucun effet.
- Un accord APPROVED reste visible uniquement comme `proposal_status_at_snapshot`,
  sans aucun chemin d'exécution.

**L1 — LIMITE (manipulation manuelle), avec proposition**. Après une panne
**avant publication**, il reste seulement le marqueur et
`review.pending.sqlite3`. Si quelqu'un « nettoie » ce marqueur, `Store(dest)`
crée un **Store vivant vide**, `missions.sqlite3`, à côté du fichier en
attente. Ces trois cas de panne le reproduisent :

- pendant le backup ;
- après le backup et avant la garde ;
- après la garde et avant le lien.

Aucun historique n'est activé et aucun accord ne revient ; la publication
devient seulement impossible. Mais le dossier ressemble désormais à un état
Core ordinaire. Et un fichier en attente écrit avant la garde garde l'ancien
`store_id` : le renommer à la main donnerait un clone sans garde.

**Proposition** : que `Store` refuse aussi un dossier qui contient
`review.pending.sqlite3`.

### 3. Arrêt avant et après publication (question 3) — CONFORME

Le processus est tué (`os._exit`) à cinq étapes : pendant le backup, avant la
garde, avant le lien, entre lien et retrait du nom temporaire, et après la
publication avant la réponse.

- La source reste inchangée, et `Store(dest)` est refusé dans tous les cas.
- Relancer la préparation vers la même destination donne `FileExistsError` :
  rien n'est écrasé.
- L'inspection ne réussit que si `missions.sqlite3` existe, c'est-à-dire après
  le lien. Avant cela, elle échoue, et la CLI répond `STORAGE_UNAVAILABLE`.
- **Proposition** : sur un dossier qui contient seulement le fichier en attente,
  répondre `RECOVERY_INCOMPLETE` plutôt qu'un diagnostic de stockage
  générique, qui suggère « reçus/renvoi ».

### 4. Inspection (question 4) — CONFORME

- Le texte de la requête n'apparaît pas, ni le chemin source.
- L'acteur et le motif de la **préparation** apparaissent, c'est voulu.
- Une identité changée par SQL brut donne `RECOVERY_REPORT_MISMATCH`.
- Une mission APPROVED s'affiche `BLOCKED` / `APPROVED` / `PREPARED`, « au
  moment de la capture ».

### 5. CLI et erreurs SQLite (question 5) — CONFORME

- **Sur une copie gardée**, toutes ces commandes rendent le code 2
  `RECOVERY_REVIEW_ONLY`, sans trace ni fichier créé : `show`, `run` (texte et
  `action-sim`), `cancel`, `command-cancel`, `command-receipt`,
  `client-snapshot`. Seul `recovery-inspect` rend 0.
- **Verrou d'écriture tenu par un autre processus** : `command-cancel` et
  `cancel` rendent le code 2 `STORAGE_UNAVAILABLE`, avec `cause_type`, sans
  trace ni texte SQL brut. Ensuite, la consultation dit `NOT_FOUND` : cohérent.
  La limite G015 sur la trace Python est donc corrigée à cette cible.
- **Fichier corrompu** (`show`, `recovery-inspect`, préparation depuis cette
  source) : `STORAGE_UNAVAILABLE`, destination non créée.

## Limites déclarées, non contestées

SQL brut, ancien binaire, restauration manuelle hors outil, liens durs et
`fsync` sur NAS, coupure électrique : non couverts par une garantie, comme
annoncé. Budget du backup coopératif, comme annoncé : ici 7,3 s, sans
dépassement testé (Codex le couvre).

## Limites de cette revue

- Disque lent **simulé** par une pause dans le rappel de progression, pas une
  vraie lenteur.
- Effet de E1 sur un `run` en cours déduit du code, non exécuté.
- Une seule taille de base (environ 16 Mio) ; pas de concurrence en charge.
- Pistes d'activation : aucune proposée dans ce lot. Ce sera dans le
  brainstorming si toytoy le demande.
