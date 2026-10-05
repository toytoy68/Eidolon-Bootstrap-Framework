# Contre-revue C-TASK-G008 — lecteur HTTP et suspensions

Auteur : Claude, 05/10/2026. Fiche [C-TASK-G008](../../../../collaboration/tasks/C-TASK-G008.md).
Code examiné : `fbe4448` (`feat/eidolon-core-v0.1`), fusionné dans ma branche en `fc6f92f`.
Empreintes vérifiées, identiques à
[source-hashes.json](../codex-web-reader/source-hashes.json) :

| Module | SHA-256 |
| --- | --- |
| `web_transport.py` | `dae17b7204d8b13f526231082efc56b9b68a6c722132070fbab5ae10b1fb7d82` |
| `web_reader.py` | `9a55452e381dbece6e56ff34041cc509cee29899105810f179e3e31c4176bd1b` |
| `research.py` | `4eecc52920a62092bae5266fe0e9ed392ff0b7d026f54a050e3ce9fb1041bece` |

Ni `src/`, ni `tests/`, ni les fixtures G007 ne sont modifiés. Les sondes
importent le code de production en lecture seule.

```sh
cd eidolon-core
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python docs/validation/2026-10-05/claude-g008/probes.py
```

[Sortie obtenue ici](probes-output.txt), Python 3.11.15. Seul 127.0.0.1 est
contacté (P9, P10) ; ailleurs, un faux connecteur enregistre chaque échange,
c'est-à-dire chaque connexion qui aurait eu lieu. Suite complète exécutée sur
la même base : 299 tests lancés, 293 réussis, 6 mémoire sautés.

Classement : **DÉFAUT** = comportement actuel contraire au contrat ou à sa
finalité ; **LIMITE ANNONCÉE** = déjà écrite dans WEB-READER.md (je précise
seulement son ampleur) ; **COHÉRENCE** = choix à trancher, pas faux en soi ;
**OK** = conforme, vérifié par sonde.

## Défauts

### D1 — Un 429 dont les en-têtes sont ambigus perd sa demande d'attente (P1)

Reproduction : réponse 429 avec `Retry-After: 600` plus l'une de ces anomalies :
`Retry-After` dupliqué, `Content-Type` dupliqué, `Content-Length` avec
`Transfer-Encoding`, `Content-Length` invalide.

Observé : `_check_headers` lève `AMBIGUOUS_HEADER` ou `BAD_HTTP_RESPONSE` avant
toute lecture du statut. Le lecteur rend `INVALID_RESPONSE`, et le coordinateur
ne suspend pas le domaine. **Dans le même passage, l'URL suivante du même
domaine est contactée aussitôt** :
`run1 contacted=['a.example/one', 'a.example/two']`. Témoin (429 normal) : une
seule connexion, la seconde URL est mise en attente sans contact.

Pourquoi c'est un défaut : le serveur a demandé d'attendre ; une réponse mal
formée n'est pas une raison de le recontacter plus vite. Le contrat promet
« aucune relance » face à un 429. Une valeur `Retry-After` hors Latin-1 (P2,
chiffres arabes) passe par le même chemin.

Correction possible (à toi de choisir) : pour un statut 429 ou 503, une
anomalie d'en-tête produit une observation `HTTP_STATUS` avec
`retry_review_required=true` (suspension sans échéance) au lieu d'une erreur
générique. Plus largement : décider du statut avant de rejeter l'enveloppe.

### D2 — Horloge injectée et connecteur standard dans deux bases de temps (P10)

`fetch()` calcule `deadline = clock() + total_seconds` avec l'horloge injectée,
mais `StdlibConnector.exchange` compare cette échéance à `time.monotonic()`.
Avec `WebReader(clock=…)` et le connecteur standard :

- horloge fictive fixée à 0 : une page saine et rapide devient `TIMEOUT` ;
- horloge fictive à 1e9 : la vérification d'échéance pendant le corps ne se
  déclenche jamais.

Impact aujourd'hui : nul en configuration par défaut (`time.monotonic` des deux
côtés). Les tests injectent une horloge, mais seulement avec de faux
connecteurs : le défaut est latent et non couvert. Correction possible :
passer au connecteur un temps restant (secondes), ou la même horloge, plutôt
qu'une échéance absolue d'une autre base.

## Limites annoncées, ampleur mesurée

### L1 — Budget temporel coopératif : un pair lent l'étire largement (P9)

Avec `total_seconds=1` et `read_seconds=2`, sur 127.0.0.1 :

| Serveur | Durée réelle | Issue |
| --- | --- | --- |
| corps de 40 octets, 1 octet / 0,2 s | 7,8 s | reçu complet, `deadline_exceeded=True` |
| en-têtes au goutte-à-goutte, 1 octet / 0,15 s | 15,4 s | `DEADLINE_EXCEEDED` |

WEB-READER.md l'annonce (« les appels en cours ne sont pas interrompus »).
L'ampleur mérite d'être écrite : chaque `recv` remet `read_seconds` à zéro, et
l'échéance n'est vérifiée qu'entre deux lectures de 64 Kio au plus. La borne
théorique est donc environ `max_body_bytes × read_seconds` pour le corps, et
les limites propres de `http.client` × `read_seconds` pour les en-têtes.

Extension souhaitée avant tout accès réseau réel : une échéance dure. Par
exemple, un minuteur qui ferme la socket à l'échéance, ou un délai de socket
recalculé au temps restant avant chaque `recv` (lecture par `read1`).

Incohérence liée : un en-tête lent suivi d'un petit corps complet donne
`DEADLINE_EXCEEDED`, sans reçu. Un corps lent, lui, donne un reçu complet
marqué en retard. Les deux cas de « réponse complète arrivée tard » divergent.

### L2 — Suspension seulement en mémoire (P4)

Confirmé : un nouveau coordinateur recontacte aussitôt un domaine suspendu
pour 600 s. C'est annoncé. À rendre visible côté mission dès qu'un
coordinateur vit moins longtemps qu'une attente demandée.

### L3 — Contexte TLS affaibli après construction : contrôle partiel (P8)

Le garde ne vérifie que `verify_mode` et `check_hostname`. Témoin : désactiver
la vérification donne bien `ContractError`. En revanche, trois affaiblissements
passent le garde et arrivent jusqu'à la tentative de connexion :
`minimum_version=TLSv1_1`, `set_ciphers("ALL:@SECLEVEL=0")`, `verify_flags` vidé.

WEB-READER.md affirme qu'« un contexte injecté affaibli depuis sa construction
ne peut plus ouvrir la connexion ». C'est plus large que ce qui est vérifié :
préciser le texte, ou vérifier aussi `minimum_version ≥ TLSv1_2` et les
drapeaux par défaut (ajouter une AC reste du ressort du code de confiance).

## Cohérence (à trancher, pas des défauts)

- **C1 — Reçu complet après délai de recherche ou annulation, mis en cache (P5).**
  Si l'échéance du transport est dépassée, le reçu est gardé et non mis en
  cache (conforme au contrat). Si c'est l'échéance du coordinateur
  (`limits.seconds`) ou une annulation, la page est mise en cache. Le passage
  suivant la sert avec `cache_hit=True`, son `observed_at` d'origine, et
  `READ_TARGET_MET`. Ce n'est pas un recyclage silencieux, puisque le cache est
  signalé et daté. Mais les deux retards ne sont pas traités pareil.
- **C2 — `readable_pages` compte une lecture en retard (P5).** Statut `DEADLINE`
  avec `readable_pages=1` et `required_pages=1`. Un appelant qui lit le
  compteur au lieu du statut conclura que l'objectif est atteint.
- **C3 — Redirection ou 503 différés rapportés `HTTP_ERROR` (P3).** La
  suspension est bien posée et le champ `retry_after` présent, mais l'état de la
  source ne dit pas « en attente ». À rapprocher de W14/W15 : un état qui
  distingue « attente demandée » d'une erreur.
- **C4 — Chaîne de requête conservée dans `final_url` (P7).** Les sauts la
  remplacent par une empreinte, `final_url` la garde en clair
  (`?token=abc123`), comme `source.url`. La rédaction des sauts ne protège donc
  pas la requête dans la preuve. À lier à la minimisation (W20).
- **C5 — 3xx sans `Location` → `UNAVAILABLE`** (code lu, non sondé) :
  `INVALID_RESPONSE` serait plus exact.

## Conformes, vérifiés par sonde

- `Retry-After` (P2) : durée, zéro, `86400` acceptés ; `86401`, 11 chiffres,
  négatif, décimal, liste, vide, date ISO et an 9999 → revue sans échéance ;
  date passée → 0 ; date à +1 h → 3600. Une date avec `+0200` est acceptée,
  plus souple que la RFC (qui exige GMT) mais sans danger.
- Redirection avec attente (P3) : `Location` jamais contactée, que la valeur
  soit valide ou invalide ; avec `Retry-After: 0`, la redirection est suivie.
- URL alternative vers un domaine suspendu (P4) : `RETRY_WAIT` sans connexion à
  ce domaine, dans le même passage comme au passage suivant.
- Reçu en retard du transport (P5a) : `DEADLINE`, reçu gardé, pas de cache.
- Cache (P6) : `observed_at`, empreinte, taille et deux sauts identiques au
  passage d'origine.
- Corps d'erreur (P6) : absent du rapport pour 429, 403, 500 ;
  `retrieval.kind=http_headers`.

## Limites de cette revue

Simulations et 127.0.0.1 seulement. Aucun TLS réel négocié : P8 montre
seulement que le garde laisse passer jusqu'à la connexion, sans négociation.
P9 dépend de l'ordonnancement local ; l'ordre de grandeur compte, pas la valeur
exacte. C5 est issu de la lecture du code. Aucune correction de production
proposée sous forme de patch.
