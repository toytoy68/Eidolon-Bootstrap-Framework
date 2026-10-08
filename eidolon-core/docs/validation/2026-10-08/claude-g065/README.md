# C-TASK-G065 — Indications de diagnostic G061 corrigées

Claude, 08/10/2026. Base : `921149f` (G064), branche Core `6f46219` fusionnée.
Données synthétiques et dossiers temporaires uniquement.

Fichiers modifiés (déclarés avant édition) :
`src/eidolon_core/runtime_inspect.py`, `tests/test_runtime_inspect.py`,
`docs/RUNTIME-INSPECTION.md`, le chemin d'erreur « mission absente » de
`src/eidolon_core/recovery.py`, et son assertion dans `tests/test_recovery.py`.
Le runtime d'exécution et les budgets ne sont pas modifiés.

## G061-1 — budget bloqué avec remaining=1

- Le compteur reste exact : `AVAILABLE`, `used=2`, `limit=3`, `remaining=1`.
- Un nouveau champ `recorded_block` donne seulement le code constant du blocage
  enregistré :
  - jamais le message ;
  - `UNRECOGNIZED` si le code est hors format ;
  - `null` si la mission n'est pas bloquée.
- Nouvel indice `BLOCKED_INVOCATION_BUDGET_RECORDED` : « le reste affiché ne
  suffit pas et n'autorise aucun appel ».
- `INVOCATION_BUDGET_EXHAUSTED` n'est ajouté que si le compteur est vraiment épuisé.
- Un `remaining=1` sans blocage (mission réussie) n'est pas présenté comme épuisé.
- Un autre blocage (recherche bloquée) garde `BLOCKED_REVIEW_MISSION`.
- Aucun champ ne prétend autoriser une exécution ; `authorizes_execution` reste false.

## Mission absente d'une copie de revue

- Avant : `{"error":"KeyError","message":"'mission not found in historical copy'"}`.
- Après : `ContractError RECOVERY_MISSION_NOT_FOUND`, toujours code 2 en JSON et
  en format humain.
- stdout vide, aucun chemin affiché, copie inchangée.

## Preuves

- [before-fix.txt](before-fix.txt) : nouveaux tests sur l'ancien code, 1 échec et 4 erreurs.
- [targeted-tests.txt](targeted-tests.txt) : 36 tests ciblés réussis.
- [full-tests.txt](full-tests.txt) : 890 tests réussis, 6 intégrations mémoire ignorées.
- [demo.txt](demo.txt) : sorties CLI réelles, produites par `PYTHONPATH=src python3 demo_g065.py`.

## Limites

- `recorded_block` reflète l'erreur stockée dans la capture. Elle ne prouve ni la
  cause actuelle ni l'absence d'effet.
- Le code de sortie et le type `ContractError` du message CLI sont ceux des autres
  refus de `recovery-inspect`.
