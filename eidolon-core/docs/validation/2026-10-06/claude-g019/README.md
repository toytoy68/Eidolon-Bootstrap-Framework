# Contre-revue C-TASK-G019 — suspensions Web persistantes (C-002c)

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G019](../../../../collaboration/tasks/C-TASK-G019.md).
Cible figée : `dc16ce1be8c4040d7bc84e5f35fa15c0c94f88a1`, extraite par `git archive`.
Empreintes identiques à [source-hashes.json](../codex-research-pauses/source-hashes.json)
(5/5) : `research_pauses.py` `4ddd688f…3cbe`, `research.py` `f5fac2a2…4ecf`,
`cli.py` `51f23698…f21b`, `tests/test_research_pauses.py` `fc1fa85a…54d0`,
`examples/research_pauses_demo.py` `f23c308d…7880`.
Ni `src/` ni `tests/` Python modifiés.

```sh
cd eidolon-core
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$FROZEN/eidolon-core/src:$FROZEN/eidolon-core \
  python docs/validation/2026-10-06/claude-g019/probes_g019.py
```

Python 3.11.15, SQLite 3.45.1, Linux. **Aucun réseau** : le vrai
`WebReader`/`fetch` reçoit un résolveur et un pair HTTP simulés, qui comptent
chaque échange. Bases de pauses temporaires ; `research-release` n'a touché que
ces copies.

- [Sortie des sondes](probes_g019-output.txt)
- [23 tests de Codex rejoués sur la copie figée : OK](codex-pauses-tests-on-frozen.txt)
- Ce n'est **pas** une validation d'exploitation Internet.

Classement : **DÉFAUT** · **LIMITE** (déclarée ; « aggravée » si la sonde
montre plus que l'annonce) · **PROPOSITION** · **CONFORME**.

## Résultat

**Les pauses tiennent** :

- persistance après reconstruction, délais minimums, révision périmée ;
- nouvelle pause après une levée ;
- redirection atomique ;
- refus d'un saut vers une origine en pause ;
- pannes de stockage sans repli ;
- audit sans corps ni requête.

**Un défaut** : une consultation lente lance quand même une requête après
dépassement du budget. **Une limite aggravée** : capacité pleine.

### 1. Persistance, délais, révision, audit (question 1) — CONFORME

- 429 avec `Retry-After: 30` : pause de 30 s. Le coordinateur reconstruit rend
  `RETRY_WAIT`, **1 seul échange** au total.
- Levée à +10 s : `RETRY_DELAY_PENDING`. Un 429 ultérieur avec RA=5 **garde le
  plus long minimum** (+30 s). Levée avec l'ancienne révision : `STALE_PAUSE`.
- Levée valide : `request_sent=false`, **0 échange** pendant la levée.
- Nouveau 403 après levée : nouvelle pause (révision 4). Ensuite `RETRY_WAIT`,
  2 échanges au total.
- Journal : `OBSERVED, OBSERVED, RELEASED, OBSERVED`. Le texte de la requête et
  le corps HTTP n'apparaissent ni dans la base de pauses ni dans les rapports.
- `Retry-After` ambigu :
  - 429 : revue requise, minimum prudent de 60 s ;
  - 503 : revue requise, sans minimum, donc levée explicite possible tout de
    suite (conforme au contrat).
- Fournisseur en 429, RA=120 : il n'est interrogé **qu'une fois** sur deux
  coordinateurs reconstruits.

### 2. Redirection et capacité (question 2)

- **Redirection, CONFORME** : 302 puis 429 sur `mirror.example`. Les deux
  origines sont en pause, en 2 événements `OBSERVED` de même horodatage (même
  transaction). Une origine neuve qui redirige **vers** l'origine en pause :
  1 seul échange, le saut est arrêté **avant** la connexion (`RETRY_WAIT`).
- **L-G019-1 — LIMITE aggravée (P2)**. La table est pleine (256 lignes, les
  pauses levées comptent) et une nouvelle origine répond 429 :
  - `PAUSE_CAPACITY_REACHED` est levé **après** l'échange ;
  - un coordinateur reconstruit **recontacte** l'origine, et ainsi de suite :
    2 échanges sur 2 lancements ;
  - une origine qui ne refuse pas reste lue normalement.

  Le contrat annonce « capacité atteinte = erreur bloquante » et « observation
  non persistée possible ». Mais ici l'état est **permanent** (rien n'est
  purgé). Une fois 256 périmètres vus, chaque nouvelle origine qui refuse est
  recontactée à chaque reconstruction.

  **Propositions** :
  - vérifier la place disponible **avant** de lire une origine inconnue, et
    refuser la lecture si la table est pleine ;
  - ou ne compter que les pauses actives.

### 3. Stockage absent, corrompu, en erreur (question 3) — CONFORME, une limite confirmée

- **Fichier supprimé** : `PauseStorageError`, le fichier n'est pas recréé.
  Ensuite, le même coordinateur est bloqué en mémoire (« prior write
  uncertain ») : **0 recherche fournisseur, 0 échange**.
- **Enregistrement corrompu** par SQL brut : `INVALID_PAUSE_RECORD`, 0 échange.
- **Fichier quelconque** à la place de la base : `PAUSE_STORAGE_UNAVAILABLE`.
- **Panne de stockage pendant le contrôle de saut** du lecteur : l'erreur
  remonte. Pas de `READER_ERROR` maquillé, 0 échange, puis le coordinateur
  reste bloqué.
- **Base verrouillée plus de 5 s** juste après un 429 : erreur, et le
  coordinateur reconstruit recontacte l'origine (2 échanges). Cela confirme la
  limite déclarée « réponse non persistée ». Même mécanisme que L-G019-1.

### 4. Levée, politique, budget, horloges (question 4)

- **Levée et politique** : après une levée, si l'origine résout vers une
  adresse privée, on obtient `POLICY_REFUSED`, 0 échange. La levée n'autorise
  rien d'autre. CONFORME.
- **Horloge murale reculée** de 120 s : nouvelle observation et levée
  refusées (`PAUSE_CLOCK_REGRESSION`), la pause existante reste. **Avancée**
  au-delà du minimum : la pause reste active, il faut une levée explicite.
  CONFORME au contrat.

**D-G019-1 — DÉFAUT (P3) : une requête part après dépassement du budget.**
La consultation lente est simulée : chaque lecture de pause « coûte » 6 s sur
l'horloge monotone du coordinateur, ce qui correspond à une base verrouillée
proche du délai SQLite de 5 s.

| Budget | Résultat |
| --- | --- |
| 10 s | 0 échange, `DEADLINE` : conforme |
| 13 s | **1 échange** au bout de 18 s, source `READ`, statut final `DEADLINE` |

Cause, par lecture du code : `before_hop` vérifie `stop()`, **puis** consulte la
pause (lente), et ne revérifie pas le budget avant l'échange. La boucle
principale, elle, revérifie après sa propre consultation. Le délai propre au
transport (30 s) ne rattrape pas l'écart.

Le défaut est **toujours présent sur la tête actuelle** (`6c75004`, même
`before_hop`). **Correctif proposé** : rappeler `stop()` après
`_persistent('active', …)` dans `before_hop`. **Test proposé** : celui de cette
sonde, avec un budget de 13 s.

### 5. Cache et annulation (question 5) — CONFORME aux limites annoncées

- **Origine mise en pause par un autre coordinateur après une lecture en
  cache** : le même coordinateur relit son **cache** (`cache_hit`, 0 nouvel
  échange) ; un coordinateur neuf rend `RETRY_WAIT`. C'est la limite annoncée
  « cache RAM relu ».
- **Annulation après le premier saut d'une redirection** : 1 seul échange,
  `CANCELLED`.

### 6. CLI — CONFORME

- `research-pauses` : 0.
- Levée avec une révision périmée : 2, `STALE_PAUSE`, sans trace.
- Levée valide : 0.
- Base absente : 2, et la base **n'est pas créée**.

## Croisement avec G020 (sans l'attribuer à cette cible)

À `dc16ce1`, les défauts A06-G02 et A06-G03 sont présents :

- A06-G02 : refus perdu si le DNS final échoue ;
- A06-G03 : corps tronqué d'un lecteur injecté.

Ils ont été reproduits **avant/après** dans
[G020](../claude-g020/README.md) (base `32f1c8d`, qui contient ce lot) et sont
corrigés dans `97abdb2`. Ils ne sont pas recomptés ici.

## Limites déclarées, non contestées

Appels déjà en vol, absence de journal préalable, SQL brut, clone ou
restauration, rétention sans purge, option désactivée dans les anciens
exemples, actor non authentifié, DNS encore appelé avant un blocage.

## Limites de cette revue

- Lenteur de consultation et horloges **simulées**.
- Pas de vrai fournisseur ni de vrai site.
- Concurrence entre coordinateurs non chargée.
