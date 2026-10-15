# G260 — Qualification G259 et correction de la CI Core

Codex/GPT, 15 octobre 2026, Europe/Paris.

## Résultat

Dix tâches réattribuées à Claude dans `collaboration/G260-CLAUDE-TASKS.md` : reprise des G258 sans doublons, avec sources disponibles et contre-revue non root ajoutée à la tâche 7. Le dernier message Claude distant reste C185 ; aucune exécution Claude n'est supposée déclenchée.

La CI Core de `216647dd3152dfee272ff057ab75e7d540c2ba47` échoue sur la préparation d'un test, pas sur le refus applicatif : après le scénario mode 000, `cli()` essaie de réécrire `observation.json` sans rétablir ses droits. Sous root, le scénario est ignoré et le défaut de fixture reste invisible.

Correctif `7a23bb95f984654d718af484364cbd93136d1ffb` : `try/finally` autour de ce seul scénario, restauration en 0600 de ce seul fichier synthétique avant le cas suivant. L'assertion `SNAPSHOT_UNAVAILABLE`, les permissions de production et tous les autres scénarios sont conservés. Aucune modification du lecteur ou du lanceur applicatif.

## Preuves vérifiées

| Source / contrôle | Résultat |
| --- | --- |
| [Memory G259 complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38718517498), `a0cc112abb5deaa459608ed80dbf412b8de7149d` | 2873 réussis, 18 ignorés, 4 xfail, 12 sous-tests ; 128,40 s |
| Worker, même run | 52 réussis ; 1,99 s |
| [Contrat Qdrant local](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38718517715), même Memory | 550 réussis, 1 xfail ; 35,45 s |
| [Chromium G259](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38722774187), Core `216647d` | 187 réussis, aucun échec, ignoré ou todo |
| [Core avant correctif](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38722774251), `216647d` | 1942 réussis, 1 échec de fixture, 8 ignorés, 1328 sous-tests ; 332,02 s |
| Core ciblé après correctif, local Python 3.12 / UID 0 | 56 réussis, `-W error`, 0,52 s ; branche non root non exercée |

Commande locale depuis la racine Core :

```sh
PYTHONPATH=eidolon-core/src python -m pytest -q -W error -p no:cacheprovider eidolon-core/tests/test_claude_host_policy_g256.py
```

Les comptes se chevauchent. Les logs de CI ont été consultés directement ; aucune suite complète n'a été relancée localement. La reproduction locale sous UID non privilégié n'a pas pu démarrer : le runtime refuse le changement d'identité du processus. Le rouge non root est observé dans le journal GitHub ; le vert non root après correctif reste à confirmer par CI après publication. Le contrôle des propriétaires root du run Core rouge n'a pas été exécuté, puisque l'étape précédente échouait.

## Publication et suite

Le lot est committé localement. La publication Git a été refusée par le contrôle automatique : l'autorisation historique retrouvée n'est pas acceptée comme autorisation de destination. Aucun contournement, aucune publication par autre canal. Demander une confirmation explicite ciblée sur le dépôt et la branche avant nouvelle tentative ; les dix tâches ne sont donc pas encore transmises.

Après autorisation : publier la branche de développement, vérifier le test non root puis la suite Core complète ; communiquer à Claude le SHA publié et compléter ce bilan. La qualification Chromium précédente reste applicable au code navigateur inchangé.

MCP : erreur interne -32603 au contrôle de cette session. Aucun accès VM, déploiement, fusion main, corpus privé ou benchmark G182. Les quatre xfail Memory historiques et les expériences hôte/passages/rétention restent ouverts dans leurs périmètres documentés.
