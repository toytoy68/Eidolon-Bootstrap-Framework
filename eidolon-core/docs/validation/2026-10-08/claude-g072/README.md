# C-TASK-G072 — Réponses HTTP hostiles aux planificateurs (C-034/C-037)

Claude, 08/10/2026. Base : `e525610` (src figé). Cible : `model_http.py`,
`ollama_model.py`, `openai_chat_model.py`, inchangés.

```sh
python3 probes_g072.py <src figé>     # code 1 si une attente échoue → probes.txt (≈ 40 s)
```

Méthode :

- Un serveur TCP brut sur 127.0.0.1 répond par des **octets** scriptés, parfois
  distillés dans le temps. Il compte les requêtes.
- Les deux adaptateurs utilisent leurs vrais transports stdlib.
- On cherche dans chaque erreur une clé synthétique (`api_key_env`) et un texte
  distant marqueur.
- **Aucun moteur réel n'est validé** : il n'y a ni Ollama ni llama.cpp.

**Résultat : 51/51 attentes, aucun échec.**

## Confirmé (les deux adaptateurs, une seule requête par appel, aucune relance)

| Réponse (octets) | Code obtenu |
| --- | --- |
| EOF avant tout octet | `TRANSPORT` (RemoteDisconnected) |
| `Content-Length` plus grand que le corps, puis EOF | `INCOMPLETE_HTTP` |
| `Content-Length` dupliqué (même identique), contradictoire ou négatif | `BAD_HTTP_FRAMING` |
| `Content-Length` + `chunked`, `Transfer-Encoding: gzip` | `BAD_HTTP_FRAMING` |
| `chunked` valide | OK |
| chunk incomplet puis EOF, taille de chunk invalide | `TRANSPORT` (IncompleteRead) |
| corps absent, ou corps sans longueur tronqué | `BAD_RESPONSE` |
| corps de plus de 4 096 octets (déclaré, sans longueur, ou en chunked) | `RESPONSE_TOO_LARGE` |
| 500 avec texte distant ; 401 reflétant la clé | `HTTP_STATUS` / `AUTHENTICATION`, « remote error details omitted » |
| 200 avec enveloppe d'erreur | `MODEL_ERROR` (Ollama), `BAD_RESPONSE` (OpenAI) |
| ligne de statut invalide ; en-tête de 70 000 octets | `TRANSPORT` |
| 302 vers un autre port | `HTTP_STATUS` ; la cible n'est **jamais contactée** |
| `HTTP_PROXY` pointant ailleurs | ignorée ; le proxy n'est jamais contacté |

- Ni la clé synthétique ni le texte distant n'apparaissent dans les erreurs.
- La clé n'est envoyée qu'au point configuré.

## Délais : trois bornes distinctes

| Borne | Mesure |
| --- | --- |
| Délai de socket (`timeout_seconds = 1`) | un silence de 1,5 s → `TRANSPORT TimeoutError` en 1,0 s |
| Durée totale dans l'adaptateur | **aucune** : un corps distillé à 1 octet / 0,6 s aboutit (OK) en 7,8 s, pour un `timeout_seconds` de 1 |
| Délai de l'exécutant runtime (`call_seconds = 3`) | même corps distillé dans une vraie mission → `BLOCKED / MODEL_UNAVAILABLE` (« call deadline exceeded ») en 3,13 s, une seule requête |

## Défauts minimaux

- **G072-1 (faible)** — EOF au milieu des en-têtes.
  - Octets envoyés : `HTTP/1.1 200 OK\r\nContent-Ty` puis fermeture.
  - Attendu : `TRANSPORT` ou `INCOMPLETE_HTTP`.
  - Observé : `http.client` prend la fin de flux pour la fin des en-têtes. On
    obtient donc `BAD_RESPONSE` (« body is not JSON »).
  - Le refus est correct ; seul le diagnostic est trompeur. 1 appel.
- **G072-2 (faible, documentation)** — `timeout_seconds` borne chaque opération
  de socket, pas la durée de l'appel.
  - `OPENAI-CHAT-ADAPTER.md` le dit ; `OLLAMA-ADAPTER.md` et `LOCAL-MODEL-CLI.md`
    ne le précisent pas.
  - La vraie borne est `--timeout` / `call_seconds` de l'exécutant.
  - Proposition : une phrase dans ces deux guides.

En mode « fermeture de connexion » (sans longueur), une troncature ne se détecte
pas au niveau HTTP. Elle est rattrapée parce qu'un objet JSON tronqué est invalide.

## Limites

- Faux serveurs loopback seulement. Pas de TLS, de proxy réel ni de serveur Ollama
  ou llama.cpp.
- Python 3.11 `http.client` / `urllib`. Le comportement de G072-1 dépend de cette
  bibliothèque.
