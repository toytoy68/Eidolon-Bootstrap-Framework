# G214 — Six tâches Claude, reprise 13 octobre

Base : rapport C173 (branche ccr-d3dc80a2-wouvy3, commit 9b7d05f). Le travail reste sur branches ; aucun accès VM, aucun merge main.

1. **P0 — Journal v2 M4** : contre-revue de la création native v2 sur base vierge et compatibilité de l'ouverture d'une base v1 existante ; produire sondes de non-mutation, migrations répétées et rétention.
2. **P0 — Reconciliation M7/M9/M10** : rejouer les tests d'aperçu corrigés ; vérifier la limite exacte, 999/1000 et la revue des abandons ; signaler tout risque de lecture partielle.
3. **P0 — Worker Memory** : livrer tests isolés de la chaîne planifier → revalider canonique + droits → agir, avec cas lecture échouée, ABSENT prouvé, crash et Qdrant indisponible ; aucune suppression réelle.
4. **P1 — Web W1** : contre-revue finale du patch 0004 de résolution DNS plafonnée ; confirmer le comportement lorsque 8 threads sont bloqués, puis rédiger les tests de retour à la normale.
5. **P1 — Dialogue I1** : finaliser le patch 0005 de fraîcheur par source (DARME 60 s, défaut 300 s), tester date future, fuseaux et compatibilité des anciennes observations.
6. **P1 — Index Qdrant** : mettre à jour les sondes 0007–0009 pour le découpage par passages et l'état INDEX_STALE ; conserver les corpus de calibration et test figés.

Claude possède ses patchs et sondes ; GPT possède change_journal.py, journal_migration.py, reconcile_preview.py et les modules Core partagés. Pas de modification concurrente. Rapports avec SHA et résultats exécutés. Les tâches publiées n'activent pas automatiquement Claude.

## Checkpoint GPT — à vérifier par Claude

Memory refactor/architecture-v1 :
- `99eea30`, `41b3828` : réparation des tests de collecte et de permissions.
- `06e0ef8`, `9a77710` : limite preview 999 et test de frontière M10.
- `a04ea1c` : journaux neufs créés en schéma v2 (M4), sans migration automatique des anciens.
- `7847538`, `1ccd806`, `de5f3ab`, `26bcb0c` : fixture v1 explicite et adaptation des tests de migration.
- `36c8b8d` : contrat de réception du futur worker.

**Demande prioritaire :** vérifier la suite Memory sur cette base, notamment l'ouverture d'une ancienne base v1, les numéros AUTOINCREMENT, le refus des permissions publiques et la création native v2. Les tests sont publiés mais pas encore exécutés dans notre environnement. Ne pas modifier les fichiers GPT simultanément.
