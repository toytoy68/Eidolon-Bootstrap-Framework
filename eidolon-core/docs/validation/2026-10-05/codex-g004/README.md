# Validation intégrée G004 — Codex/GPT — 05/10/2026

## Bases et portée

Core C-005a : `5c169cbe0d96417c286c29374e60396d897bf319`.
Livraison Claude G004 : `da145db`, intégrée avec son historique, puis correctifs
et sept tests de frontière Codex dans le commit introduisant ce bilan.
Python 3.12.14, Linux/POSIX. Données synthétiques, transports simulés et faux
serveurs HTTP loopback. Aucune connexion aux machines personnelles.

Le serveur llama.cpp b11418 n'a pas été lancé. Sa lecture documentaire reste
celle de Claude, conservée dans OPENAI-CHAT-ADAPTER.md ; les tests ici ne
prouvent ni la compatibilité réelle ni la qualité d'un modèle ou d'un GPU.

## Résultats reproduisibles

Depuis `eidolon-core/` :

```sh
PYTHONPATH=src:. python -m unittest tests.test_openai_chat_model tests.test_openai_chat_boundaries -v
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
PYTHONPATH=src:. python -m examples.openai_chat_demo
```

- `claude-tests-reproduced.txt` : 20 tests de Claude reproduits avant durcissement.
- `before.txt` : sondes avant correctif, sans publication d'une clé ; réflexion
  de clé, enveloppes ambiguës et budgets invalides acceptés, dépassement numérique.
- `adapter-tests.txt` : 27 tests réussis, dont sept tests de frontière ajoutés.
- `core-tests.txt` : 197 tests découverts, **191 réussis**, 6 intégrations opt-in
  sautées ; ces six tests sont exécutés séparément ci-dessous.
- `demo.txt` : mission complète via HTTP loopback, SUCCEEDED / ACHIEVED, un outil
  local et son résultat vérifié ; ce n'est pas une réponse d'un vrai modèle.

Les tests de réflexion contrôlent la mission, les événements et les octets SQLite,
y compris erreur HTTP, erreur JSON sous HTTP 200, finish_reason, contenu textuel,
contenu JSON échappé et ligne de statut HTTP mal formée. La protection ne prétend
pas détecter tout secret obfusqué ; les transports Python restent de confiance.

## Intégration mémoire réelle sur corpus synthétique

Copie isolée du moteur : `7d99ded07b7e10aa8029655ce4a939af6e0a6c44`, dépôt
inchangé avant/après. `memory-tests.txt` : **6 tests réussis**, API réelle de rappel
et corpus temporaires préparés par les services coordonnés du moteur.

```sh
EIDOLON_MEMORY_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="src:.:$EIDOLON_MEMORY_SOURCE" \
  python -m unittest tests.test_memory_engine -v
```

Définir EIDOLON_MEMORY_SOURCE vers une copie isolée et installer ses dépendances
comme documenté dans le README Core. Aucun fichier canonique utilisateur modifié.

## Différé

Serveur llama.cpp/Ollama, modèle, GPU V100/NVLink, VM100, Internet/LAN/NAS et
Windows réels non testés. L'adaptateur reste optionnel, hors CLI. Aucun moteur
choisi, aucun seuil P2P adopté. C-TASK-G005 prépare la contre-revue C-005a par
Claude ; aucune réponse à cette nouvelle fiche n'est présumée.
