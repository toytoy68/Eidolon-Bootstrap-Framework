# Adaptateur Ollama optionnel — `ollama-chat/1`

Auteur : Claude, 05/10/2026, fiche [C-CLAUDE-002](../collaboration/tasks/C-CLAUDE-002.md).
Base : `9620c47`. Statut : module livré **non raccordé à la CLI** et **non choisi
par défaut**. La démonstration utilise toujours `DeterministicModel`.
Liens : C-007, `contracts.Model`, C-BRAIN-006.

Module : [`src/eidolon_core/ollama_model.py`](../src/eidolon_core/ollama_model.py).
Tests : [`tests/test_ollama_model.py`](../tests/test_ollama_model.py), 14 tests.

## Sources du protocole

`docs.ollama.com` est bloqué par le proxy de la session. J'ai donc lu les mêmes
pages dans le dépôt officiel `ollama/ollama`, branche `main` au commit
`42e911bc3d05798cad729cb474bf62f378cb2e26`, le 05/10/2026 vers 12 h 20 UTC :

| Fichier du dépôt | SHA-256 du fichier lu | Utilisé pour |
| --- | --- | --- |
| `docs/api.md` (il annonce son déménagement vers docs.ollama.com/api) | `33c374a5…1b8ab7dd193b1ba1` | `POST /api/chat`, paramètres, réponse non streamée, `format` en schéma JSON |
| `docs/api/errors.mdx` | `908e7544…c64cb8be2b5c49a` | Codes HTTP et objet `{"error": "..."}` |
| `docs/api/introduction.mdx` | `72b82a2f…aad608411fa52de66cdffbf` | URL locale `http://localhost:11434/api`, URL cloud `https://ollama.com/api` |
| `docs/faq.mdx` | `7fc6dd68…97fdc79a1c07a4d1` | Écoute par défaut sur 127.0.0.1:11434, changée par `OLLAMA_HOST` |

## Documenté, choisi, testé

| Point | Documenté par Ollama | Choix de l'adaptateur | Testé ici |
| --- | --- | --- | --- |
| Appel | `POST /api/chat`, `model`, `messages`, `stream:false`, `format`, `options` | Exactement ces cinq clés ; jamais `tools` | Transport simulé |
| Sortie structurée | `format` accepte un schéma JSON | Schéma du plan v1 envoyé ; `parse_plan` reste seul juge | Corps de requête inspecté |
| Réponse | `message.role/content`, `done`, `done_reason`, compteurs | `done` doit être vrai ; `done_reason` absent ou `"stop"` | Simulé et loopback |
| Nom de modèle | Étiquette `latest` si absente | `nom` et `nom:latest` équivalents ; autre modèle refusé | Simulé |
| Erreurs | Statut HTTP et `{"error": ...}` ; erreur en cours de flux en NDJSON | Tout statut ≠ 200 refusé ; flux non utilisé, NDJSON refusé | Simulé et loopback |
| `done_reason: "length"` | Non documenté dans les pages lues | Refusé (`INCOMPLETE`) : un plan tronqué n'atteint jamais le parseur | Simulé seulement |
| `tool_calls` | Documenté pour le mode outils | Refusé (`TOOL_CALL_REFUSED`) : l'adaptateur n'exécute ni ne relaie rien | Simulé |

Aucun essai contre un vrai serveur Ollama, un GPU ou un modèle. Les réussites
ci-dessus valident l'adaptateur contre **un faux serveur** qui suit la
documentation. Elles ne qualifient ni Ollama ni un modèle.

## Configuration

```python
from eidolon_core.ollama_model import OllamaConfig, OllamaModel
model = OllamaModel(OllamaConfig(
    endpoint="http://127.0.0.1:11434",   # obligatoire, pas de valeur par défaut
    model="nom:étiquette",               # obligatoire, aucun modèle choisi par Core
    options={"temperature": 0, "seed": 7, "num_predict": 512},
    timeout_seconds=60))
```

- **Budgets visibles** dans `config.manifest()` : octets de requête (64 000),
  de réponse HTTP (256 000) et de sortie (64 000, la borne de `parse_plan`),
  jetons de sortie (`num_predict`) et délai. La requête est mesurée **avant**
  tout envoi.
- **`model_id`** = `ollama/<modèle>@<16 premiers caractères de l'empreinte du
  manifeste>`. Le manifeste couvre l'endpoint, le modèle, les options, les
  budgets, le délai et les empreintes du schéma et du prompt système. Le
  `model_id` entre dans `Runtime.configuration()` : changer un de ces éléments
  bloque la reprise d'une mission existante (`CONFIGURATION_CHANGED`).
- Options limitées à `temperature`, `seed`, `num_predict`, `num_ctx`, `top_k`,
  `top_p`, nombres finis.
- Aucun secret n'est accepté. L'appel cloud d'Ollama demande une clé ; il n'est
  pas pris en charge par cette version.

## Frontière de confidentialité

Le prompt contient la requête **et tout le contexte mémoire rappelé**. Changer
l'endpoint revient à choisir où partent ces données. L'adaptateur refuse donc
toute adresse autre que `localhost`, `127.0.0.1` ou `::1`, sauf
`allow_non_loopback=True`. Ce drapeau représente une **configuration
opérateur approuvée**, pas un réglage de confort. Il ne doit venir ni du modèle,
ni d'une source mémoire, ni d'une requête.

Autres garde-fous du transport `UrllibTransport` : proxy système ignoré,
redirection jamais suivie (un 3xx devient une erreur), réponse lue au plus à
`max_response_bytes + 1` octets. Limites : le nom `localhost` n'est pas résolu
par l'adaptateur et peut être redéfini dans `/etc/hosts`. HTTP en clair sur le
LAN reste lisible par le réseau : pour une VM distante, préférer un tunnel ou TLS.

## Erreurs et effet sur la mission

L'adaptateur lève `OllamaError(code, message)` et ne rend jamais un plan vide
ou par défaut. Dans l'exécutant, toute exception devient un reçu d'erreur ;
le runtime en fait `BLOCKED/MODEL_UNAVAILABLE`, reprenable (testé). Un texte
rendu mais invalide est jugé par `parse_plan` : `FAILED/MODEL_INVALID` (testé).
Un plan valide qui demande un outil non autorisé finit en
`BLOCKED/PREFLIGHT_REFUSED`, sans aucun appel (testé avec `service.restart`).

Codes : `TRANSPORT` (connexion, délai), `HTTP_STATUS`, `RESPONSE_TOO_LARGE`,
`BAD_RESPONSE`, `MODEL_ERROR`, `INCOMPLETE`, `MODEL_MISMATCH`,
`TOOL_CALL_REFUSED`, `EMPTY_OUTPUT`, `OUTPUT_TOO_LARGE`, `PROMPT_TOO_LARGE`.

Le contrat `Model.propose -> str` ne transporte ni les compteurs de jetons ni
les durées. Les conserver dans la mission demande d'étendre ce contrat
(exigence transversale 2 de la TODO). Je ne l'ai pas fait ici.

## Lancement futur (non exécuté)

1. Sur la machine qui héberge Ollama : installation, téléchargement du modèle
   choisi, écoute sur 127.0.0.1 par défaut.
2. Si Core tourne ailleurs : tunnel ou proxy TLS décidé par l'opérateur, puis
   `allow_non_loopback=True` dans une configuration revue. L'adresse de VM100
   fournie par toytoy n'est pas une URL Ollama et n'a pas été contactée.
3. Raccordement CLI à faire dans les fichiers du lot Codex : une option
   explicite (par exemple `--model-config fichier.json`), jamais un choix par défaut.
4. Qualification séparée selon C-BRAIN-006 : la réussite des tests ci-dessus
   ne vaut pas qualification.

## Limites

stdlib uniquement. Pas de streaming, de mode outils, d'images ni d'appel cloud
authentifié. Le schéma `format` restreint la forme de la sortie, pas son sens :
un plan bien formé peut rester hors sujet, ce que C-001a doit refuser.
