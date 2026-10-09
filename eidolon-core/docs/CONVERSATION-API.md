# API de conversation et de soumission

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G087.
Code : [conversation_api.py](../src/eidolon_core/conversation_api.py),
[client_credentials.py](../src/eidolon_core/client_credentials.py).
Tests : [test_conversation_api.py](../tests/test_conversation_api.py).
S'appuie sur G084 (contrat), G085 (dépôt) et G086 (dialogue).

## Identité : un client appairé, jamais le jeton de lecture

- L'opérateur appaire un client **sur le serveur** :

  ```text
  python -m eidolon_core.conversation_api --state <état> pair --client-id pc-toytoy --actor toytoy
  ```

  Le jeton `ecc_…` est affiché **une seule fois**. Seule son empreinte SHA-256
  est conservée, dans `<état>/conversations/clients.sqlite3` (0600, fichier
  régulier, jamais un lien). `revoke --client-id …` le révoque.
- L'identité du client (`client_id`) et l'acteur viennent **du jeton**, jamais
  de la requête :
  - une soumission qui annonce un autre client donne `CLIENT_MISMATCH` ;
  - une soumission qui annonce un autre acteur donne `ACTOR_MISMATCH`.
- Le **jeton de lecture** est refusé sur chaque route (403
  `READ_TOKEN_NOT_ALLOWED`). Un jeton absent, inconnu ou révoqué donne 401.
- Sans client appairé, l'API ne démarre pas (`CREDENTIALS_MISSING`). Aucune
  route de commande ne fonctionne avec une identité simulée.
- **Cloisonnement** : un client ne voit que ses conversations. Une conversation
  étrangère et une conversation absente reçoivent la même réponse, 404. Il
  n'annule que les missions issues de **ses** soumissions.

## Routes (POST JSON uniquement, sous `/v1/conversations/`)

| Route | Corps | Effet |
| --- | --- | --- |
| `open` | `client_key` | ouvre la conversation (même clé, même conversation) |
| `recent` | `limit` (1 à 50, 10 par défaut) | conversations **non vides de ce client**, la plus récente d'abord, pour reprendre après un rechargement (G092) ; lecture seule |
| `turn` | `conversation_id`, `client_turn_key`, `text` | un tour, puis la réponse décidée par Core (G086) ; un tour rejoué n'appelle pas le modèle |
| `page` | `conversation_id`, `after`, `limit` | lecture paginée, reprise après une reconnexion |
| `submit` | soumission `eidolon-proposal-submission/1` complète | **crée** la mission de la proposition figée, puis rend un reçu ; elle **ne la lance pas** (`execution: NOT_STARTED_BY_SUBMISSION`) |
| `receipt` | `command_key` | retrouve un reçu après une réponse perdue (`authorizes_resend: false`) |
| `resolve` | `command_key`, `mission_id` ou `null`, `reason` | décision humaine sur une soumission `UNCERTAIN` (G085) |
| `cancel` | `command_key`, `mission_id`, `reason` | **demande** d'annulation (`CANCELLATION_REQUESTED_NOT_CONFIRMED`) ; seul le runtime confirme l'arrêt |

Codes HTTP :

| Code | Cas |
| --- | --- |
| 400 | JSON ou champs invalides (clés en double, champ en trop) |
| 401 / 403 | identité refusée |
| 404 | inconnu ou étranger |
| 405 | méthode autre que POST |
| 409 | conflit : proposition périmée ou changée, déjà soumise, clé réutilisée, Store changé |
| 413 | requête trop grande (100 000 octets au plus : 8 000 caractères dans tout encodage JSON valide) |
| 415 | corps qui n'est pas du JSON |
| 503 | stockage occupé ou indisponible |

Toute erreur porte `authorizes_execution: false`.

## Hôte et montage

- `ConversationAPI.handle(méthode, chemin, en-têtes, corps)` ne dépend d'aucun
  transport. Le serveur de lecture (`http_api`, Codex) pourra la monter sur la
  **même origine**, comme l'exige la CSP du client (`connect-src 'self'`).
  Le correctif de montage sera proposé avec G088, quand le client en aura
  besoin.
- `ConversationServer` est un hôte de test en boucle locale. Il vérifie Host et
  Origin, n'écrit aucun journal d'accès et ajoute les en-têtes de sécurité.

## Preuves

`python3 -m unittest tests.test_conversation_api` : 11 tests sur HTTP réel
(127.0.0.1), notamment :

- parcours complet `open` → `turn` → `submit` → mission `NEW` → `run` →
  `SUCCEEDED` → `receipt` → `page` ;
- jeton de lecture refusé sur 4 routes ;
- jetons absent, inventé ou révoqué ;
- deux clients cloisonnés ;
- 3 soumissions identiques donnent un reçu et une mission ;
- proposition changée ou périmée : 409 ;
- **réponse perdue**, puis reçu retrouvé et renvoi sans seconde mission ;
- annulation demandée, alors que la mission reste `NEW`, puis `CANCELLED` par
  le runtime ;
- Host, Origin, méthode, type de contenu, JSON, champs et taille ;
- appairage en CLI : jeton affiché une fois et absent du fichier.

## Limites

- Hôte de test seulement : pas encore monté dans `http_api` (G088, avec Codex).
- Le lancement de la mission créée relève du runtime ou du worker existant ; il
  sera raccordé dans la recette G089.
- Pas de limite de débit par client. Les budgets et les quotas viendront en
  G091.
