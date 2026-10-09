# C-TASK-G075 — Recette des planificateurs depuis le paquet installé (C-034–C-041)

Claude, 08/10/2026. Commit : `b1d0db9c27400c9fa0f40ead8d3737c9e2b7e12a` (contient
C-039–C-041). Python 3.11.15. Les SHA de l'archive et de la roue sont dans
[recipe.txt](recipe.txt).

```sh
python3 recipe_g075.py <racine du dépôt> <sha du commit>     # → recipe.txt (≈ 3 min)
```

Méthode :

- Complément de G069, sans refaire la recette serveur/client.
- Le paquet est construit hors réseau depuis l'archive reproductible du commit,
  puis installé dans un venv jetable. Chaque commande tourne depuis un dossier
  neutre, sans `PYTHONPATH`.
- Un **faux planificateur** sur 127.0.0.1 sert les deux candidats et compte les
  requêtes qu'il **reçoit** :
  - Ollama : `/api/chat` ;
  - llama-server : `/v1/chat/completions`, clé dans `G075_KEY`.
- Les attentes viennent des enregistrements de mission et des documents de
  recette, jamais du texte du modèle.
- Aucun modèle réel, aucun téléchargement, aucune activation du client.

**Résultat : PASS, 32/32 contrôles. Aucun processus restant.**

## Missions CLI, pour chaque candidat

| Cas | Constat |
| --- | --- |
| `model-config-check` | manifestes `ollama-chat/4` et `openai-chat-llamacpp/4`, 0 requête |
| plan valide puis reprise | `SUCCEEDED`, appel vérifié, **1** requête ; reprise d'une mission terminée : **0** requête, mission identique |
| configuration changée (mission créée avec `num_predict`/`max_tokens` 512, reprise avec 513) | `BLOCKED / CONFIGURATION_CHANGED`, 0 requête |
| clé absente (llama-server) | `BLOCKED / MODEL_UNAVAILABLE` **avant envoi**, 0 requête, clé absente de la sortie |
| plan hors catalogue (`shell.execute`) | `BLOCKED / PREFLIGHT_REFUSED`, 1 requête, aucun outil, aucune relance |
| sortie tronquée (arrêt `length`) | `BLOCKED / MODEL_UNAVAILABLE`, 1 requête, aucun outil, aucune relance |

La clé n'est envoyée qu'au faux serveur, en `Bearer`.

## `model-probe` et `model-probe-inspect`, pour chaque candidat

| Cas | Constat |
| --- | --- |
| `--plan-only` | `PLANNED`, 4 cas, 3 tentatives au plus, 0 requête, sans clé |
| essai valide | `COMPLETE / PASSED_CASES`, **3** requêtes reçues (`planner_attempts` 1, 1, 1, 0 : la mémoire vide n'appelle pas) ; inspection `CONSISTENT` |
| arrêt technique (503) | `STOPPED / FAILED_CASES` (retour 3), **1** requête, 3 cas non lancés, `started = recorded = 1` ; inspection `CONSISTENT`, `run_status STOPPED` |
| plans refusés | `COMPLETE / FAILED_CASES` (retour 3), 3 requêtes : un `FAIL` n'arrête pas les cas indépendants |
| marqueur `MODEL-PROBE-INCOMPLETE` ajouté à côté d'un rapport `PASSED_CASES` | inspection `INCOMPLETE` (retour 2) : le marqueur l'emporte |
| bilan de cas modifié après coup | diagnostic constant (retour 2) |
| dossier de sortie existant | refusé avant tout appel |
| essai tué (SIGKILL du groupe) pendant le 1er cas, 1 requête reçue | inspection `INCOMPLETE`, `started_cases = null`, `recorded_cases = 0`, `unrecorded_cases_may_have_started = true` |

Sous *audit hook* et espion d'environnement, `model-probe-inspect` n'ouvre aucun
socket, aucune base SQLite (ni Store ni Runtime) et ne lit pas la clé.

## Remarque

Une réponse arrêtée par la longueur (`done_reason` / `finish_reason` =
`length`) est classée `MODEL_UNAVAILABLE`, comme une panne de transport. Le refus
est sûr, mais l'opérateur peut croire le serveur indisponible, alors qu'il
faudrait plutôt augmenter `num_predict` / `max_tokens`.

Proposition : conserver le code de l'adaptateur (`INCOMPLETE`) dans le message ou
dans un champ distinct. Le statut ne change pas.

## Limites

- Faux serveur seulement. Aucun moteur, poids, GPU ni durée n'est qualifié ;
  `hardware_qualified` reste false.
- Construction avec `SETUPTOOLS_USE_DISTUTILS=stdlib`, propre à ce conteneur
  (voir G069).
- Linux, en root, loopback seulement.
