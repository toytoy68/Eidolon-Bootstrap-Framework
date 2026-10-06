# Proposition C-TASK-G030 — journal des appels Web incertains

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G030](../../../collaboration/tasks/C-TASK-G030.md).
Statut : **conception**. Aucun code de production : `research.py`,
`research_pauses.py` et `web_transport.py` ne changent pas.
Base examinée : `258f922`. `research.py` (`7f49a5a1…`) et `research_pauses.py`
(`bde1c611…`) sont identiques à `8983d35`.

Sources, toutes dans le dépôt : `research_pauses.py` (schéma, transactions,
`user_version`), `research.py` (`_persistent`, `before_hop`),
[RESEARCH-PAUSES.md](../../RESEARCH-PAUSES.md) (« pas de journal durable
préalable des appels en vol »), [ARCHITECTURE.md](../../ARCHITECTURE.md)
(intention, verrou `lease-v2`, reçus, `confirm_no_effect`) et
[ABANDON-UNVERIFIED.md](../../ABANDON-UNVERIFIED.md).

## 1. La fenêtre, mesurée sur le code actuel

[probe_window.py](probe_window.py) lance de **vrais processus**. Un enfant fait
une recherche avec pauses durables ; le fournisseur synthétique répond 429
(`retry_after=120`) et compte ses contacts dans un fichier. L'enfant meurt
(`os._exit`) à un point choisi. Un second enfant, neuf, refait la recherche,
comme un coordinateur reconstruit. [Sortie](probe_window-output.txt).

| Arrêt brutal du premier processus | Second run | Contacts du fournisseur |
| --- | --- | --- |
| aucun | `RETRY_WAIT` | 1 |
| pendant l'échange (requête reçue, réponse jamais vue) | `RATE_LIMITED` | **2** |
| 429 reçu, avant l'écriture de la pause | `RATE_LIMITED` | **2** |
| après l'écriture de la pause | `RETRY_WAIT` | 1 |

Les deux lignes à 2 contacts sont la fenêtre : rien sur disque ne dit qu'un
appel était en cours, donc le coordinateur reconstruit **recontacte à
l'aveugle**. Le journal doit faire passer ces deux lignes à 1 contact.

## 2. Trois choses à ne pas confondre

| Situation | Ce qu'on sait | Conséquence proposée |
| --- | --- | --- |
| **Inconnu** : intention écrite, aucun résultat commis | la requête a pu partir, consommer un quota, être refusée | le périmètre est bloqué jusqu'à revue |
| **Refus observé** : 429/403/challenge reçu et commis | le pair a refusé | pause, comme aujourd'hui |
| **Non envoyé** : le processus sait qu'aucun octet de la requête n'est parti | aucun contact | appel clos `NOT_SENT`, rien à revoir |

« Non envoyé » n'est écrit que par le processus qui l'a constaté lui-même :
refus de politique, DNS, connexion refusée **avant** l'envoi de la requête,
annulation avant l'échange. La reprise ne le **déduit jamais** d'une
absence. Une revue humaine ne prouve pas non plus l'absence d'effet. Elle
accepte l'incertitude, et le dossier le dit.

Un délai ou une erreur **observés** après l'envoi closent l'appel comme
`FAILED_OBSERVED`, sans pause, comme aujourd'hui. Le journal corrige la
fenêtre de crash ; il ne change pas la sémantique réseau.

## 3. Identités et contenu minimisé

- `run_id` : aléatoire (128 bits) par `run()`, avec un verrou de fichier
  `web-runs/<run_id>.lock` tenu pendant tout le run.
- `call_id` = `run_id` + numéro d'ordre. `kind` vaut `PROVIDER_SEARCH`,
  `PAGE_READ` ou `HOP`. Un saut porte `parent_call_id` et `hop_index`.
- `scope_id` : le même identifiant que la pause (`provider_scope` ou
  `origin_scope`). Le blocage et la pause partagent donc une seule clé.
- Contenu gardé : `provider_id`, `query_sha256` (et `disclosure_sha256` si
  G029 est adopté), `host`/`port`, `url_sha256`, `query_sha256` de l'URL.
  **Pas de chemin, pas de requête, pas de corps, pas d'en-tête.** Le chemin
  peut porter un identifiant (`;jsessionid`, G027) et ne sert pas au blocage.
- `revision`, `state`, `intent_at_ms`, `ended_at_ms`, `code` (statut HTTP ou
  code d'erreur borné).

## 4. États et transitions

```text
                 ┌──────────── NOT_SENT (constaté par le processus)
INTENT ──────────┼──────────── RECEIVED  (+ pause dans la même transaction si refus)
 (commis avant   ├──────────── FAILED_OBSERVED (délai/erreur vus après envoi)
  l'échange)     └─(crash)──── vu à la reprise : UNCERTAIN ── revue ── RESOLVED_UNKNOWN
```

- `INTENT` est écrit dans une transaction `BEGIN IMMEDIATE`, **avant**
  l'échange, avec `PRAGMA synchronous=FULL` (déjà utilisé).
- `UNCERTAIN` n'est pas écrit au moment du crash. C'est la **lecture** d'un
  `INTENT` sans fin dont le verrou du run est libre. Si le verrou est tenu, le
  processus est vivant : l'état lu est `IN_FLIGHT`.
- `RESOLVED_UNKNOWN` exige `call_id`, la révision attendue, un acteur et une
  raison. L'acteur reste un **libellé local** : la reprise ne le remplit
  jamais. La revue n'appelle rien (`request_sent=false`) ; elle rend seulement
  le périmètre de nouveau éligible aux contrôles normaux.
- La revue peut aussi transformer l'incertain en **pause** (« je considère
  que c'était un refus ») : c'est une pause normale, avec sa propre révision.

### Invariants

1. Aucun échange sans `INTENT` commis pour son périmètre.
2. Un périmètre qui a un `INTENT` ouvert (vivant ou non) ou un `UNCERTAIN`
   bloque tout nouvel échange, **comme une pause ACTIVE**. Le message diffère :
   `WEB_CALL_IN_FLIGHT` ou `WEB_CALL_UNCERTAIN`.
3. La fin d'un appel et la pause qu'elle crée sont **une seule transaction**.
4. Un état terminal ne change plus. Une nouvelle tentative est un nouvel appel.
5. Une révision périmée est refusée (`STALE_WEB_CALL`), comme `STALE_PAUSE`.
6. Le temps qui passe ne débloque rien.
7. Une ligne illisible bloque (lecture refusée), elle ne vaut jamais « libre ».

## 5. Base dédiée ou base des pauses partagée

| Critère | Base dédiée | **Base des pauses partagée** (recommandée) |
| --- | --- | --- |
| Fin d'appel + pause atomiques | non : deux fichiers, donc un ordre d'écriture et un état intermédiaire de plus à la reprise | **oui** : une transaction SQLite |
| Réserver la place de pause dans l'intention | non | **oui** : une intention compte jusqu'à 2 places tant qu'elle est ouverte |
| Ancien binaire | il ignore la nouvelle base et recontacte | `user_version=2` : le code actuel **refuse** une base qu'il ne connaît pas (`version not in (0, 1)` → `UNSUPPORTED_PAUSE_DATABASE`) |
| Couplage | indépendants | une corruption bloque pauses et appels ensemble ; c'est voulu, les deux gardent le même périmètre |
| Rétention, coût | séparés | à traiter ensemble (L-G028-1 s'aggrave sans index) |

Le refus de l'ancien binaire a été vérifié : ouvrir une base marquée
`user_version=2` avec le code actuel donne `PauseStorageError:
UNSUPPORTED_PAUSE_DATABASE`.

La réservation règle aussi la course de la dernière place (L-G019-1 et G024) :
le second écrivain est refusé **à l'intention**, avant tout échange, au lieu
de perdre son observation après coup.

Le choix d'un seul fichier évite de s'appuyer sur l'atomicité de transactions
réparties sur plusieurs bases attachées, que je n'ai pas vérifiée ici.

## 6. Matrice des pannes

« Aujourd'hui » est mesuré quand la colonne cite la sonde ; sinon, c'est une
lecture du code.

| Panne | Aujourd'hui | Avec le journal |
| --- | --- | --- |
| crash avant l'intention | rien d'envoyé, rien d'écrit | idem : pas d'appel, rien à revoir |
| crash après l'intention, avant l'échange | — (pas d'intention) | `UNCERTAIN` par prudence : la reprise ne sait pas si l'échange a démarré |
| crash pendant l'échange | **recontact** (sonde) | `UNCERTAIN`, 0 nouveau contact |
| crash après le 429, avant la pause | **recontact** (sonde) | `UNCERTAIN`, 0 nouveau contact |
| crash après la pause | bloqué (sonde) | `RECEIVED` + pause, déjà atomiques |
| réponse tronquée avec statut validé | statut gardé, corps rejeté (audit 06/10) | `RECEIVED` avec code ; 429/403 restent des pauses |
| réponse tronquée sans statut | erreur de transport | `FAILED_OBSERVED` (le pair a été contacté) |
| quota concurrent, dernière place | observation perdue, blocage RAM | second refusé à l'intention, 0 contact |
| deux processus, même périmètre | deux contacts possibles | `WEB_CALL_IN_FLIGHT` pour le second |
| horloge qui recule | `PAUSE_CLOCK_REGRESSION` à l'écriture | idem ; une fin refusée laisse l'intention ouverte, donc `UNCERTAIN` |
| horloge qui avance | délai minimal échu plus tôt, pas de levée | idem ; l'incertain ne dépend pas de l'horloge |
| disque plein à l'intention | — | refus avant l'échange (`PAUSE_STORAGE_UNAVAILABLE`) |
| disque plein à la fin | blocage RAM seul ; un coordinateur reconstruit recontacte | intention restée ouverte : le reconstruit est bloqué |
| processus encore vivant | — | verrou tenu : `IN_FLIGHT`, pas de revue possible |
| restauration d'une ancienne copie | pauses récentes perdues | intentions récentes perdues aussi : **limite**, non détectable par la base seule |
| corruption d'une ligne | `INVALID_PAUSE_RECORD`, refus | idem pour les appels |
| ancien coordinateur, base v2 | — | refus `UNSUPPORTED_PAUSE_DATABASE` |
| coordinateur **sans** pauses (`pauses=None`) | aucun journal | aucun journal : **limite** à annoncer |

## 7. Premier lot proposé (borné)

1. Protocole `eidolon-research-pauses/2` : tables `web_calls` et
   `web_call_events`, index sur `(scope_id, state)` ; migration explicite
   v1 → v2 dans une transaction ; pas de retour en v1.
2. API :
   - `begin_call(kind, scopes, descriptor)` : contrôle pause, appel ouvert et
     capacité (réservation), puis écrit l'`INTENT` ;
   - `finish_call(call_id, outcome, pause=None)` : fin et pause en une
     transaction ;
   - `not_sent(call_id, code)` ;
   - `inspect_calls()` ;
   - `resolve_uncertain(call_id, expected_revision, actor, reason, as_pause=False)`.
3. Raccordement :
   - fournisseur : intention avant `provider.search`, fin après ;
   - lecture : une intention par saut dans `before_hop` (WebReader), et une
     seule transaction à la fin de la lecture pour clore tous les sauts. Le
     transport ne change pas ;
   - un lecteur injecté sans `read_guarded` donne une intention unique sur
     l'origine initiale ; les sauts suivants restent hors journal (limite).
4. CLI : `research-calls` (inspection), `research-resolve <call_id> --revision
   N --actor … --reason …`. Aucune relance.

Hors lot : rétention, purge, sauvegarde cohérente, lien avec la mission Core.

## 8. Tests multi-processus synthétiques discriminants

Chaque test **échoue sur le code actuel** ou fixe un comportement nouveau.
Processus réels, `os._exit`, fournisseur et pair HTTP simulés, `127.0.0.1` ou
doubles seulement.

| # | Test | Code actuel | Attendu |
| --- | --- | --- | --- |
| T1 | crash après 429, avant la pause | 2 contacts (sonde) | 1 contact, `WEB_CALL_UNCERTAIN` |
| T2 | crash pendant l'échange | 2 contacts (sonde) | 1 contact, `UNCERTAIN` |
| T3 | crash après l'intention, avant l'échange | — | `UNCERTAIN`, 0 contact |
| T4 | processus A vivant (verrou tenu), B sur le même périmètre | 2 contacts | B : `WEB_CALL_IN_FLIGHT`, 0 contact ; revue de A refusée |
| T5 | A et B sur la dernière place de pause | observation perdue | B refusé à l'intention, 0 contact |
| T6 | panne SQLite injectée à `finish_call`, puis coordinateur reconstruit | recontact | bloqué, `UNCERTAIN` |
| T7 | revue avec une révision périmée | — | `STALE_WEB_CALL`, rien ne change |
| T8 | revue valide | — | `RESOLVED_UNKNOWN`, 0 contact pendant la revue ; le run suivant contacte une fois |
| T9 | code actuel (v1) ouvert sur une base v2 | — | `UNSUPPORTED_PAUSE_DATABASE` |
| T10 | la base ne contient ni requête, ni chemin, ni paramètre secret | — | recherche d'octets : absents |
| T11 | DNS refusé, politique refusée, annulation avant échange | aucun journal | `NOT_SENT`, aucun blocage |
| T12 | redirection : crash entre le saut 1 et le saut 2 | recontact | origines des sauts ouverts `UNCERTAIN` ; saut 2 jamais lancé |

## 9. Limites

- **Pas d'« exactement une fois »**. Le journal transforme un recontact
  aveugle en blocage revu ; il n'empêche pas un double contact décidé par un
  humain.
- Prudence assumée : un crash entre l'intention et l'échange bloque un
  périmètre qui n'a peut-être reçu aucun octet.
- Un ancien binaire **sans** pauses, du SQL direct, un fichier supprimé ou une
  ancienne copie restaurée échappent au journal.
- Le verrou de fichier suppose un système de fichiers local, comme `lease-v2`.
- Un adaptateur de fournisseur qui fait lui-même plusieurs requêtes HTTP compte
  comme **un** appel.
- Aucun test de coupure électrique réelle.

## 10. Questions ouvertes (pour Codex, puis toytoy si besoin)

- **Q-G030-A** : stocker le chemin minimisé (comme le rapport v2) pour aider
  la revue, ou seulement origine et empreintes, comme proposé ici ?
- **Q-G030-B** : une intention ouverte d'un processus **vivant** doit-elle
  bloquer les autres coordinateurs (sérialisation par périmètre), ou seulement
  être signalée ?
- **Q-G030-C** : migration v1 → v2 automatique à l'ouverture, ou commande
  explicite ? Je propose la commande explicite : une ouverture ne devrait pas
  rendre la base illisible pour l'ancien binaire sans geste humain.
