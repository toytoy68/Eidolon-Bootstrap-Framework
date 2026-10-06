# C-TASK-G023 — abandon explicite d'un résultat non vérifié : preuves

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G023](../../../../collaboration/tasks/C-TASK-G023.md) ·
[contrat](../../../ABANDON-UNVERIFIED.md). Base : `6d1661d`.
Fichiers modifiés :

- `src/eidolon_core/runtime.py` : nouvelle méthode `_abandon_unverified`,
  appelée par `reconcile` ;
- `tests/test_abandon_verification.py` (nouveau).

`action_view.py`, `research*.py`, `commands.py`, `cli.py` et `Store` sont
inchangés.

```sh
cd eidolon-core
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m unittest -v tests.test_abandon_verification
```

Python 3.11.15, Linux. États synthétiques. Le vérificateur est rendu
indisponible en remplaçant `runtime.invoke` dans le test, comme dans les tests
d'audit de Codex.

## Échec avant, réussite après

| `runtime.py` | Résultat | Sortie |
| --- | --- | --- |
| `6d1661d` (avant G023) | **4 réussis, 5 en échec** (1 échec, 4 erreurs) | [tests-before-6d1661d.txt](tests-before-6d1661d.txt) |
| après G023 | **9/9** | [tests-after.txt](tests-after.txt) |

Les 4 tests déjà verts avant sont des garde-fous :

- les refus (autres décisions, sortie fournie, libellés invalides ; mission
  terminale ou PREPARED ; ancienne `CANCELLED`) ;
- le verrou occupé ;
- l'ancien abandon d'effet inconnu, inchangé.

Suite Core complète après correction : **475 tests OK**, 6 intégrations Memory
Engine sautées ([sortie](core-tests.txt)). ruff (E9, F, B) : rien.

## Cas couverts

| Cas | Attendu, vérifié |
| --- | --- |
| Vérificateur indisponible, **avec ou sans** annulation | ABANDONED, `RESULT_UNVERIFIED`, appel RETURNED, sortie, empreinte et origine identiques, issue ≠ ACHIEVED, `action_view` = `RESULT_UNVERIFIED` / `MISSION_CLOSED`, événement avec acteur, motif et empreinte |
| Aucun appel pendant l'abandon | `invoke` remplacé par une erreur : abandon réussi quand même |
| `run` après l'abandon | rien ne change : 1 `CALL_STARTED`, 1 redémarrage simulé |
| Autres décisions, sortie fournie, acteur ou motif invalides | refus, mission identique |
| Mission PREPARED, mission SUCCEEDED, ancienne CANCELLED avec RETURNED | refus, mission identique, rien n'est rouvert |
| Verrou occupé | `Busy`, mission toujours BLOCKED |
| Plan à deux étapes (1re VERIFIED, 2e RETURNED) | abandon : la 1re reste VERIFIED, issue **PARTIAL**, progression 1 |
| Ancien chemin REVIEW_REQUIRED / STARTED | ABANDONED, `EFFECT_UNKNOWN`, appel UNKNOWN |
| CLI `reconcile --decision abandon` | avec `--result` : code 2, sans changement ; sans : code 0, JSON ABANDONED avec effet `RESULT_UNVERIFIED` |
