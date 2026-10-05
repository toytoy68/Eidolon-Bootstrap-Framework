# Adaptateur candidat `openai-chat-llamacpp/1` — API chat de llama-server

Auteur : Claude, 05/10/2026, fiche [C-TASK-G004](../collaboration/tasks/C-TASK-G004.md).
Base : `c0fa5ba`. Statut : module **candidat**, non raccordé à la CLI, jamais
choisi par défaut. La démonstration Core garde le modèle déterministe. Aucun
moteur n'est retenu par ce lot (voir [l'étude des moteurs](INFERENCE-RUNTIME-COMPARISON.md)).

Module : [`src/eidolon_core/openai_chat_model.py`](../src/eidolon_core/openai_chat_model.py).
Tests : [`tests/test_openai_chat_model.py`](../tests/test_openai_chat_model.py), 20 tests.
Démo : `PYTHONPATH=src:. python -m examples.openai_chat_demo`.

## Version de référence

llama.cpp, **release `b11418`** (tag officiel, commit
`9871df5911a03a813518bcd623ee2eba91bf32aa`), lue le 05/10/2026 vers 15 h 30
depuis `raw.githubusercontent.com`. Le site de documentation n'est pas consulté :
le contrat est celui du dépôt à ce tag.

| Fichier au tag | SHA-256 (12 car.) | Utilisé pour |
| --- | --- | --- |
| `tools/server/README.md` | `180acdc268c1` | Endpoint, `response_format`, `usage`, port et hôte par défaut, `--api-key` |
| `tools/server/server-task.cpp` | `aa752f0ba1ce` | Forme de la réponse non streamée, `finish_reason`, calcul de `usage` |
| `tools/server/server-common.cpp` | `ec18ae0203a0` | Lecture de `response_format`, forme des erreurs |
| `tools/server/server-context.cpp` | `17552eda0b9f` | Origine du champ `model` de la réponse |
| `tools/server/server-http.cpp` | `24ede172e526` | En-tête d'authentification, enveloppe `{"error": …}` |

Le README le dit lui-même : « no strong claims of compatibility with OpenAI API
spec is being made ». Cet adaptateur vise **llama-server à cette version**, pas
tout serveur dit compatible OpenAI. Avant un essai réel, relire ces fichiers à
la version installée.

## Documenté, lu dans le code, décidé

| Point | Source | Choix de l'adaptateur | Testé ici |
| --- | --- | --- | --- |
| `POST /v1/chat/completions`, `messages`, non streamé | doc README | `stream: false`, deux messages (système, utilisateur) | Simulé, loopback |
| Sortie JSON contrainte | doc README ; code `server-common.cpp` | `response_format = {"type": "json_object", "schema": <plan v1>}` (voir l'écart ci-dessous) | Corps inspecté |
| Forme de la réponse | code `server-task.cpp` : `object = "chat.completion"`, `choices[0].message`, `finish_reason`, `usage`, `model` | Exactement un choix, rôle `assistant`, contenu texte non vide | Simulé, loopback |
| `finish_reason` | code : `"stop"`, `"length"`, `"tool_calls"` | `stop` seul accepté ; `length` → `INCOMPLETE` ; `tool_calls` → `TOOL_CALL_REFUSED` ; autre ou absent → `BAD_RESPONSE` | Simulé |
| Champ `model` de la réponse | code `server-context.cpp` : nom du modèle **chargé par le serveur**, pas celui demandé | Doit égaler `config.model` : l'opérateur y met le nom (ou l'alias) servi | Simulé |
| `usage` | code : `total_tokens = completion_tokens + prompt_tokens` | Entiers ≥ 0 et cohérents ; total ≤ `context_tokens` déclaré ; complétion ≤ `max_tokens` | Simulé |
| Erreurs | code : `{"error": {"code", "message", "type"}}`, statuts 400/401/403/404/500/501/503 | Tout statut ≠ 200 refusé ; `exceed_context_size_error` → `CONTEXT_EXCEEDED`, 401 → `AUTHENTICATION` | Simulé, loopback |
| Authentification | doc `--api-key` ; code : `Authorization` (préfixe `Bearer ` retiré) ou `X-Api-Key` | `Authorization: Bearer <clé>`, clé lue dans une **variable d'environnement nommée** au moment de l'appel | Loopback |
| `refusal` | Non documenté par llama-server (champ de la spec OpenAI) | Refusé s'il est présent et non vide (`REFUSED`) | Simulé |
| `reasoning_content` | doc README (raisonnement séparé) | Jamais lu comme plan : un contenu vide avec raisonnement donne `EMPTY_OUTPUT` | Simulé |

**Écart doc/code relevé.** L'exemple du README écrit
`{"type": "json_schema", "schema": {...}}`. Or, pour le type `json_schema`, le
code lit `response_format.json_schema.schema` (forme OpenAI). Un schéma placé
comme dans l'exemple serait ignoré, et le serveur accepterait alors « n'importe
quel objet ». L'adaptateur emploie donc la forme que le code lit sans ambiguïté :
`{"type": "json_object", "schema": …}`. Constat de lecture, non vérifié sur un
serveur réel.

## Configuration

```python
from eidolon_core.openai_chat_model import OpenAIChatConfig, OpenAIChatModel
model = OpenAIChatModel(OpenAIChatConfig(
    endpoint="http://127.0.0.1:8080",   # obligatoire ; llama-server écoute 127.0.0.1:8080 par défaut
    model="nom-servi",                   # obligatoire ; doit égaler le champ "model" renvoyé
    options={"temperature": 0, "seed": 7, "max_tokens": 512},
    context_tokens=8192,                 # facultatif : contexte déclaré du serveur
    api_key_env="LLAMA_API_KEY"))        # facultatif : NOM de variable, jamais la clé
```

- Options limitées à `temperature`, `seed`, `max_tokens`, `top_p`, `top_k`,
  nombres finis. Pas de `stream`, `tools` ni options libres.
- Configuration immuable, y compris après sérialisation pour un processus
  spawn. `model_id = openai-chat/<modèle>@<empreinte>` ; l'empreinte couvre
  endpoint, modèle, options, contexte, budgets, délai, schéma, prompt système,
  `allow_non_loopback` et le **nom** de la variable de clé. Remplacer la
  configuration change le `model_id`, donc bloque la reprise d'une mission existante.
- Budgets mesurés avant tout envoi : 64 000 octets de requête, 256 000 de
  réponse, 64 000 de sortie (borne de `parse_plan`), plus `max_tokens`.

## Sécurité et confidentialité

- Le prompt contient la requête et **tout le contexte mémoire rappelé**. Seules
  les adresses `localhost`, `127.0.0.1` et `::1` sont acceptées, sauf
  `allow_non_loopback=True`, qui représente une configuration opérateur approuvée.
- Une clé API hors loopback exige `https` : une clé en clair sur le réseau
  local serait lisible sur le chemin.
- La valeur de la clé ne figure ni dans la configuration, ni dans le manifeste,
  ni dans le `model_id`, ni dans la mission ou son journal (testé). Elle vit
  seulement dans l'environnement du processus qui fait l'appel.
- Pas de proxy, pas de redirection suivie, réponse lue au plus à la borne + 1 octet.
- Aucun endpoint ne vient de la réponse du modèle ; aucun appel d'outil n'est
  exécuté ni relayé.

## Effet sur la mission

Toute défaillance lève `OpenAIChatError(code, message)`, jamais un plan vide.
Dans Core : défaillance de transport ou du serveur → `BLOCKED/MODEL_UNAVAILABLE`,
reprenable (testé) ; texte rendu mais invalide → `FAILED/MODEL_INVALID` (testé) ;
plan bien formé hors mission ou outil interdit → `BLOCKED` sans aucun appel (testé).

Codes : `TRANSPORT`, `HTTP_STATUS`, `AUTHENTICATION`, `CONTEXT_EXCEEDED`,
`RESPONSE_TOO_LARGE`, `BAD_RESPONSE`, `MODEL_ERROR`, `MODEL_MISMATCH`,
`TOOL_CALL_REFUSED`, `REFUSED`, `INCOMPLETE`, `EMPTY_OUTPUT`, `OUTPUT_TOO_LARGE`,
`PROMPT_TOO_LARGE`, `MISSING_SECRET`.

## Limites

Python standard uniquement. Pas de streaming, d'outils, d'images ni de
raisonnement exploité. Le faux serveur des tests imite la forme documentée ;
aucun llama.cpp, GPU ou modèle n'a été lancé, et VM100 n'a pas été contactée.
Les compteurs `usage` et `timings` ne sont pas conservés dans la mission :
le contrat `Model.propose -> str` ne les transporte pas. Le schéma de sortie
restreint la forme, pas le sens. Le prompt système et le schéma sont ceux de
l'adaptateur Ollama, importés pour que les deux candidats restent comparables.

Proposition, sans décision : une authentification réelle plus forte qu'une
clé partagée (TLS mutuel ou tunnel) pourra se discuter au brainstorming. Elle
ne bloque pas ce transport simulé.

## Révision d'intégration Codex/GPT — contrat `/2`, 05/10/2026

Le code serveur de référence reste b11418. L'identifiant du contrat adaptateur
passe à `openai-chat-llamacpp/2` ; une mission utilisant l'ancien contrat bloque
à la reprise pour configuration différente. La lecture documentaire de Claude
ci-dessus reste attribuée à son auteur, sans essai llama.cpp réel supplémentaire.

Les erreurs distantes ne sont plus copiées dans le diagnostic : elles peuvent
refléter une clé d'en-tête. Les codes locaux et le statut HTTP restent visibles.
Une erreur du parseur HTTP est également convertie en diagnostic local sans
texte brut ni chaîne de cause contenant la réponse distante.
Une complétion reflétant littéralement la clé utilisée, y compris après décodage
des chaînes JSON du plan, est refusée avant sauvegarde. Les sondes utilisent une
clé synthétique et vérifient mission, événements et octets SQLite. Cette protection
n'est pas un détecteur général de secrets obfusqués ; les extensions de transport
Python restent de confiance et ne doivent pas journaliser leurs en-têtes.

La clé doit comporter 1 à 8192 caractères ASCII imprimables sans espace, et ne
pas contenir de retour à la ligne. Codes ajoutés : INVALID_SECRET et
SECRET_IN_RESPONSE. L'enveloppe exige des clés JSON uniques, des valeurs finies,
un texte UTF-8 valide, `usage` présent et cohérent, des types `tool_calls` et
`refusal` valides. Le schéma renvoyé par `body()` est une copie indépendante.

Bornes choisies **par cet adaptateur**, pas annoncées comme limites universelles
du serveur : max_tokens entier 1–1 000 000, seed entier −1 à 2³²−1, top_k entier
0–1 000 000, top_p entre 0 et 1, temperature entre 0 et 10. Aucune limite négative
illimitée ni budget fractionnaire. Endpoint borné, sans contrôles, port valide ;
les nombres trop grands donnent ContractError plutôt qu'une exception de conversion.

[Preuves et limites du lot intégré](validation/2026-10-05/codex-g004/README.md).
