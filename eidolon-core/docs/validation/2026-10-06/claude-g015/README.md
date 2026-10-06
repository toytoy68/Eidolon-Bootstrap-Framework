# Contre-revue C-TASK-G015 — reçus d'annulation (C-008c)

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G015](../../../../collaboration/tasks/C-TASK-G015.md).
Cible figée : `9d1cc0fa6539ea94a504572645901186ec16981d`, extraite par `git archive`
dans une copie isolée. Empreintes identiques à
[source-hashes.json](../codex-cancel-receipts/source-hashes.json) (5/5) :

| Fichier | SHA-256 |
| --- | --- |
| `commands.py` | `d9518b65…3b88b` |
| `store.py` | `2217c9ba…dcd3` |
| `cli.py` | `3c1b96f5…06b7` |
| `tests/test_cancel_commands.py` | `69e1063b…beef` |
| `examples/cancel_receipt_demo.py` | `89796f26…39ff` |

Depuis, `store.py` et `cli.py` ont changé (C-008d, C-008e) : ces résultats valent
pour `9d1cc0f`. Ni `src/`, ni `tests/` Python, ni la cible G014 modifiés.

```sh
cd eidolon-core
# FROZEN = git archive 9d1cc0f eidolon-core/src eidolon-core/tests eidolon-core/examples | tar -x -C FROZEN
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$FROZEN/eidolon-core/src:$FROZEN/eidolon-core \
  python docs/validation/2026-10-06/claude-g015/probes_g015.py
```

Python 3.11.15, Linux (Codex : 3.12.14). Chaque sonde crée sa propre base
temporaire (redémarrage **simulé** de `nas`). Pannes injectées par
déclencheurs SQLite, verrou d'écriture tenu par un autre processus, crochet
documenté `runtime.checkpoint`, ou enveloppe de `approvals.consume` dans le
processus de sonde. `FaultAction` vient des tests figés de Codex.
[Sortie des sondes](probes_g015-output.txt) ·
[20 tests ciblés de Codex rejoués sur la copie figée : OK](codex-targeted-tests-on-frozen.txt).

Classement : **ÉCART** · **LIMITE** (déclarée) · **PROPOSITION** · **CONFORME**.

## Résultat

Le **protocole d'annulation lui-même tient** : je n'ai trouvé ni reçu faux, ni
flag sans reçu, ni double transition, ni contournement de clé. **Un écart** se
trouve à la frontière avec le runtime : il est **antérieur à C-008c**, mais il
touche directement la question 3 de la fiche.

### 1. Atomicité, concurrence, verrou (question 1) — CONFORME

- **Pannes SQL** (déclencheurs `RAISE(ABORT)`) avant la mise à jour de la
  mission, après l'insertion de l'événement, puis après celle du reçu : dans les
  trois cas, mission et événements sont inchangés et la consultation donne
  `NOT_FOUND`. Une fois la panne retirée, on obtient un seul `CANCEL_REQUESTED`.
- **Processus tué dans la transaction**, après les trois écritures et avant
  COMMIT (`os._exit` appelé par un déclencheur) : rien n'est persisté. Codex
  tuait le processus avant l'insertion du reçu ; ici, c'est après les trois
  écritures. **Tué juste après COMMIT** (réponse perdue) : `FOUND`, flag posé ;
  un renvoi rend le même reçu, sans nouvel événement.
- **Vrais processus concurrents** (Codex utilisait des threads) :
  - même commande dans 4 processus : 4 × `REQUESTED`, **un seul reçu**, un seul
    événement ;
  - 4 clés différentes : 1 `REQUESTED`, 3 `ALREADY_REQUESTED`, un seul
    `CANCEL_REQUESTED`, révision inchangée ;
  - même clé sur deux missions : un enregistrement, un `COMMAND_KEY_REUSED`,
    une seule mission marquée ;
  - même clé, annulation contre accord sur la même mission (4 essais) :
    l'annulation gagne à chaque fois, puis l'accord reçoit `COMMAND_KEY_REUSED` ;
    aucune décision. Dans l'ordre inverse (accord d'abord, en séquence),
    l'annulation reçoit `COMMAND_KEY_REUSED`.
- **Verrou d'exécution tenu par un autre processus** : annulation enregistrée
  en moins de 0,01 s. Une décision reçoit `Busy`.

### 2. Courses avec accord, progression et succès (question 2) — CONFORME

Ici, l'annulation est écrite par un second écrivain, sans verrou, à chaque
étape d'un run approuvé :

| Moment de l'annulation | Mission | Redémarrages | Effet (`action_view`) |
| --- | --- | --- | --- |
| après `ACTION_CONDITION_CHECKED` | CANCELLED, accord APPROVED | 0 | NOT_STARTED |
| **entre le contrôle d'annulation et le commit de `CALL_STARTED`** | CANCELLED, accord USED | 0 | NOT_AUTHORIZED |
| `CALL_STARTED` / `WORKER_SPAWNED` | CANCELLED | 0 | NOT_AUTHORIZED |
| `TOOL_RETURNED` / `RESULT_SAVED` | **CANCELLED** (voir écart E1) | 1 | RESULT_UNVERIFIED |
| `RESULT_VERIFIED` (avant le commit du succès) | CANCELLED, `outcome=ACHIEVED`, `result=None` | 1 | VERIFIED_PAST_EFFECT |

- La fenêtre la plus étroite (commit entre le dernier contrôle de
  `_authorize_call` et `CALL_STARTED`) est rattrapée par le contrôle du lanceur
  avant l'autorisation de l'enfant : aucun lancement. L'accord est consommé
  sans exécution ; `action_view` le dit (NOT_AUTHORIZED).
- **Succès déjà commis** : `ALREADY_TERMINAL`, corps de mission identique octet
  pour octet, résultat conservé, flag non posé, un `CANCEL_COMMAND_RECORDED`.
- **Pas de révision attendue** : le client voit la révision 0, la mission avance
  jusqu'à la révision 8, et l'annulation est enregistrée (`mission_revision=8`
  dans le reçu). Annulation puis accord : refusé.

### 3. Effet commis puis annulation (question 3)

- **Effet commis, puis l'enfant meurt** (`FaultAction lost`), puis
  annulation : la mission reste `REVIEW_REQUIRED` (`UNKNOWN`). Le reçu dit
  `effect_absence_evidence=false` ; `run` ne relance rien. Résultat de chaque
  réconciliation :
  - `no-effect`, avec ou sans confirmation : refusé, car le reçu de la
    simulation existe ;
  - `abandon` : la mission passe à `ABANDONED`, avec un effet `UNKNOWN` ;
  - `observed-result` : la mission passe à `BLOCKED`, puis `run` la met à
    **CANCELLED sans vérification**. L'effet affiché est `RESULT_UNVERIFIED`
    (voir E1).

  Aucune preuve n'est supprimée : le reçu de la simulation est conservé, et la
  sortie de l'appel aussi. **CONFORME**, sauf l'écart E1 ci-dessous.

#### E1 — ÉCART : un effet commis mais pas encore vérifié est clos en CANCELLED, et ne peut plus être vérifié

Les deux cas qui mènent ici :

- l'annulation arrive après le retour de l'enfant (`TOOL_RETURNED` ou
  `RESULT_SAVED`) ;
- ou une réconciliation `observed-result` a eu lieu sur une mission dont
  l'annulation est déjà demandée.

Dans les deux cas, la vérification n'est pas tentée :

- **vérification bloquée** : `_invoke(verify)` passe par le contrôle
  d'annulation du lanceur (`worker.invoke`) ;
- **mission close** : dans le premier cas, `CANCELLED` avec le code d'erreur
  `VERIFICATION_UNAVAILABLE`. Dans le second, `run` la met à `CANCELLED` avant
  même la boucle de vérification. Ce code est trompeur : la vérification était
  disponible, elle a été sautée ;
- **constat** : le redémarrage simulé a bien eu lieu (`restarts=1`), mais
  `outcome=NOT_ACHIEVED` et `result=None` ;
- **impasse** : la mission est terminale. `reconcile` exige `REVIEW_REQUIRED`
  et un appel `STARTED` (« no uncertain call »), et `run` ne vérifie plus.

Sans annulation, la même indisponibilité aurait donné `BLOCKED`, qu'on peut
reprendre.

Rien n'est effacé, et `action_view` dit correctement `RESULT_UNVERIFIED`. Mais
le statut et `outcome` seuls se lisent « annulée, non atteinte », alors qu'une
mutation a eu lieu et qu'on ne pourra plus la vérifier. La vérification est une
lecture locale sans effet : l'annulation n'empêche rien en la sautant.

**Origine** : ce chemin du runtime date de `b39ad27` ; `9d1cc0f` ne touche ni
`runtime.py` ni `worker.py`. L'ancienne CLI `cancel` y menait déjà. C-008c le
rend simplement plus facile à atteindre, depuis un client et sans verrou.

**Correctif possible** (à décider par Codex/toytoy, non fait ici) :

- laisser la vérification d'un appel `RETURNED` s'exécuter malgré l'annulation ;
- ou bien, quand la mutation a eu lieu, s'arrêter en `REVIEW_REQUIRED` ou en
  `BLOCKED` plutôt qu'en `CANCELLED` terminal ;
- dans tous les cas, ne pas utiliser `VERIFICATION_UNAVAILABLE` quand la
  vérification a été sautée.

Test de régression proposé : annulation au point de contrôle `TOOL_RETURNED`,
puis attendre que l'effet soit vérifiable ou réconciliable.

### 4. Interprétation client (question 4) — CONFORME

- La consultation commune rend les deux protocoles, `eidolon-command-receipt/1`
  et `eidolon-cancel-receipt/1`. Ni l'un ni l'autre n'a de champ de permission
  ni d'état courant. La consultation porte `authorizes_resend=false` et
  `execution_evidence=false`. Le reçu d'annulation ajoute
  `effect_absence_evidence=false`.
- ClientSync : révision 9 → 9, curseur 10 → 11, `cancel_requested` false →
  true, applicabilité `CANCEL_REQUESTED`. Les références d'événements n'ont
  que `sequence`, `at` et `kind`. Ni l'acteur ni la raison n'apparaissent
  dans la capture ou la page.
- Avec un autre `store_id`, la consultation rend `STORE_CHANGED`. Une même
  commande aux clés JSON réordonnées rend le même reçu. La même clé avec un
  acteur suivi d'une espace rend `COMMAND_KEY_REUSED`.
- Sont refusés : champ en plus (`expected_revision`), `NaN`, BOM, identifiant de
  mission en majuscules, acteur fait d'espaces, protocole de décision, plus de
  32 768 octets.
- Codes CLI de `command-cancel` :
  - `ALREADY_TERMINAL` : 0, avec l'issue explicite ;
  - mission absente : 2 (`KeyError`) ;
  - autre Store : 2 (`STORE_CHANGED`).

Règles côté client, déjà tenues par le prototype G012/G016 :

- `REQUESTED` ne veut dire ni « arrêtée » ni « sans effet » ;
- `CANCELLED` avec `VERIFIED_PAST_EFFECT` ou `RESULT_UNVERIFIED` doit montrer
  l'effet.

## Limites déclarées, confirmées

- **Verrou d'écriture SQLite tenu plus de 5 s** :
  - l'API lève `sqlite3.OperationalError: database is locked`, sans flag ni
    reçu (`NOT_FOUND`) ;
  - la CLI sort avec le **code 1 et une trace Python**, pas en JSON ;
  - une fois le verrou libéré, la même commande s'enregistre.

  Conforme à la limite annoncée (« diagnostic CLI plus homogène » à la TODO),
  pas présenté comme corrigé.
- Identité locale non authentifiée ; pas de reçu pour `run` ; pas de délai dur
  d'arrêt ; rétention sans quota ; restauration ancienne : non retestés ici,
  hors des sondes.

## Propositions

1. **E1** ci-dessus : seul point à corriger, au choix de Codex.
2. **Diagnostic du parseur** : `ContractError` hérite de `ValueError`.
   `_parse_command` remplace donc toute erreur de validation par
   « invalid bounded UTF-8 JSON command ». Le validateur seul donne la vraie
   raison : champs, acteur, mission. Aucun effet sur la sécurité. Garder le
   message d'origine aiderait le client, et cela vaut aussi pour les décisions.
3. **Client** : quand `cancel_requested=true` et que l'issue est `CANCELLED`,
   afficher l'effet d'`action_view` à côté du statut. Ne jamais déduire « rien
   ne s'est passé » du seul statut ; c'est le cas `RESULT_VERIFIED` → CANCELLED
   avec `outcome=ACHIEVED`.

## Limites de cette revue

- Environnement : base SQLite temporaire et locale, Python 3.11.
- Pannes non testées : pas de coupure d'alimentation, pas de disque plein.
- Concurrence : éprouvée à 2 et 4 processus, pas en charge.
- Course annulation/accord : 4 tirages, tous gagnés par l'annulation. L'ordre
  inverse n'est montré qu'en séquence.
- Effet en cours : l'annulation pendant qu'un enfant vit encore est couverte
  par le test de Codex et n'est pas refaite.
- Trace : la première ligne de la sortie contient le chemin de la copie figée,
  dans le répertoire temporaire de la session.
