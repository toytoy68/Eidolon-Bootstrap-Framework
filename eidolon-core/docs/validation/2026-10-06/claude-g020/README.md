# Contre-revue C-TASK-G020 — correctifs d'audit du 06/10 (`97abdb2`)

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G020](../../../../collaboration/tasks/C-TASK-G020.md).
Cible figée : `97abdb24da9615095fc29e1773eb3b927e06d3cb` ; base avant correction
`32f1c8d`. Deux copies isolées (`git archive`). Empreintes de la cible identiques à
[source-hashes.json](../codex-audit/source-hashes.json) pour les fichiers modifiés :
`runtime.py` `7bbad1a9…ff36`, `commands.py` `4fd7bb38…307b`, `research.py`
`831da99c…25bc`, `tools.py` `e3b7f93f…e48d`, `tests/test_audit_regressions.py` `209371f7…9654`.
Ni `src/` ni `tests/` Python modifiés.

```sh
cd eidolon-core
# T = copie figée (32f1c8d ou 97abdb2) ; BASE = copie de 32f1c8d (pour la sonde 1b)
G020_BASE_TREE=$BASE PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$T/eidolon-core/src:$T/eidolon-core \
  python docs/validation/2026-10-06/claude-g020/probes_g020.py
```

Python 3.11.15, Linux. **Les mêmes sondes ont été jouées sur les deux arbres** :
[avant `32f1c8d`](probes-before-32f1c8d.txt) · [après `97abdb2`](probes-after-97abdb2.txt).
[10 tests d'audit de Codex rejoués sur la copie figée : OK](codex-audit-tests-on-frozen.txt).
Aucun Internet : DNS et HTTP simulés, passés au vrai `WebReader`/`fetch`, ou
lecteur injecté. Annulation écrite par un autre écrivain, sans verrou.

Classement : **CORRIGÉ** (défaut reproduit avant, absent après) · **RÉSIDU** ·
**LIMITE** · **PROPOSITION**.

## Résultat

Les quatre correctifs se vérifient **indépendamment**, y compris sur des cas que
les tests de Codex ne couvrent pas : annulation **pendant** la vérification,
sortie fausse avec annulation, redirection vers une **autre origine**, DNS final
devenu **privé**. Deux points restent : un résidu P3 sur les messages, et une
limite nouvelle sur la fermeture d'une mission annulée dont le vérificateur ne
revient jamais.

### 1. Annulation et vérification (A06-G01 / mon E1 G015) — CORRIGÉ

| Cas | Avant `32f1c8d` | Après `97abdb2` |
| --- | --- | --- |
| annulation à `TOOL_RETURNED` ou `RESULT_SAVED` | CANCELLED, `VERIFICATION_UNAVAILABLE`, RETURNED, NOT_ACHIEVED | **CANCELLED**, appel **VERIFIED**, `outcome=ACHIEVED`, `result=None` |
| annulation **pendant** la vérification (vérificateur lent, 1,5 s, autre processus) | idem avant | vérification menée à terme, puis CANCELLED / ACHIEVED |
| sortie fausse (`wrong-output`) + annulation | **CANCELLED** sans verdict | **FAILED / VERIFICATION_FAILED** : jamais acceptée |
| REVIEW (enfant mort après l'effet) + annulation + `observed-result`, puis `run` | CANCELLED, RETURNED non vérifié | CANCELLED, VERIFIED, ACHIEVED |
| vérificateur indisponible + annulation | CANCELLED (clos) | **BLOCKED / VERIFY**, reprenable ; vérificateur revenu → CANCELLED / ACHIEVED |
| mission close par l'ancien code, ouverte par le nouveau | — | **non rouverte** (révision 15 → 15) |

Partout : 1 seul `CALL_STARTED`, 1 seul redémarrage simulé, aucun outil suivant.
Lecture de code : le seul assouplissement est `cancelled=False` pour l'appel du
vérificateur, toujours borné par `call_seconds`. Les trois vérificateurs de
l'arbre ne font que lire : `simulation.verify` lit le reçu, `diagnostics.verify`
et `verify_stats` sont purs. Un vérificateur tiers qui ferait un effet
tournerait désormais après l'annulation : c'est le contrat « code de confiance »
documenté dans `tools.py`, pas une sandbox.

**L-G020-1 — LIMITE nouvelle (P3), avec proposition**. Une mission annulée dont
le vérificateur ne revient **jamais** reste `BLOCKED / VERIFY` sans issue :

- `reconcile abandon` est refusé (« no uncertain call ») ;
- une deuxième annulation rend `ALREADY_REQUESTED` ;
- l'ancien `cancel` laisse la mission BLOCKED.

Avant, elle était close, à tort. Maintenant elle est juste, mais impossible à
fermer. **Proposition** : un abandon explicite d'un appel RETURNED non vérifié,
qui donnerait ABANDONED avec un effet `RESULT_UNVERIFIED`, journalisé avec
acteur et motif.

### 2. Refus Web (A06-G02, A06-G03) — CORRIGÉ

**Redirection vers une autre origine, puis contrôle DNS final en échec ou
devenu privé** (vrai `WebReader`, `docs.example` → 302 → `mirror.example` qui
répond 403, 429 ou 503 avec `Retry-After`). Six combinaisons :

- Avant : les deux origines **ne sont pas** mises en pause ; la recherche
  suivante recontacte les deux (4 échanges).
- Après : les deux origines sont en pause ; 2 échanges au total. Une recherche
  suivante est `RETRY_WAIT`. Un **accès direct** à `mirror.example`, une fois le
  DNS rétabli, est aussi `RETRY_WAIT` : la pause seule l'arrête.
- La source reste `POLICY_REFUSED`, sans texte. Aucune adresse privée
  n'est contactée.

**Corps tronqué ou trop grand** (401, 403, 429), lecteur injecté avec une URL
finale sur une autre origine :

- avant : 2 lectures, aucune pause ;
- après : 1 lecture, les deux origines en pause.

**Transport standard** (`WebReader`, mêmes réponses) : déjà correct **avant**
le correctif (1 échange, ACCESS_DENIED ou RATE_LIMITED, pause posée), parce
qu'il ne lit pas les corps non-2xx. Le défaut ne touchait que les lecteurs
injectés, comme Codex l'annonce.

**200 OK puis DNS final privé (rebinding)** : `POLICY_REFUSED`
(`DESTINATION_NOT_GLOBAL`), aucun texte, 0 page lisible, avant comme après.

### 3. Parseurs (A06-G04) — CORRIGÉ, avec un résidu

Après correction, les messages sont précis :

- champs exacts ;
- clé dupliquée ;
- type d'entrée (`None`, `int`, `dict` : `ContractError`, au lieu
  d'`AttributeError` avant) ;
- `NaN` ;
- acteur vide ;
- taille.

UTF-8 invalide, substitut isolé, BOM et imbrication profonde restent un refus
générique, ce qui est acceptable. La CLI répond JSON, code 2, sans trace.

**R-G020-1 — RÉSIDU (P3)**. Un identifiant de mission mal formé donne encore le
message générique, dans les deux parseurs et dans la CLI. `Store.check_id` lève
`ValueError`, pas `ContractError`, et cette exception est toujours
reformulée. **Proposition** : lever `ContractError("INVALID_COMMAND: invalid
mission_id")` dans les validateurs. Aucun effet sur les autorisations ni sur le
sens d'un reçu.

## Ce qui n'est pas couvert

- Aucun lecteur Internet réel ni fournisseur réel.
- La fenêtre de crash entre réception HTTP et commit, et les appels en vol :
  limites annoncées, non retestées.
- Le plan à deux outils dont seul le premier est lancé : couvert par le test de
  Codex, non refait.
- Python 3.11 ici (Codex : 3.12).
