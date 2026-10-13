# G214 — Six tâches Claude, reprise 13 octobre

Base : rapport C173 (branche ccr-d3dc80a2-wouvy3, commit 9b7d05f). Le travail reste sur branches ; aucun accès VM, aucun merge main.

1. **P0 — Journal v2 M4** : contre-revue de la création native v2 sur base vierge et compatibilité de l'ouverture d'une base v1 existante ; produire sondes de non-mutation, migrations répétées et rétention.
2. **P0 — Reconciliation M7/M9/M10** : rejouer les tests d'aperçu corrigés ; vérifier la limite exacte, 999/1000 et la revue des abandons ; signaler tout risque de lecture partielle.
3. **P0 — Worker Memory** : livrer tests isolés de la chaîne planifier → revalider canonique + droits → agir, avec cas lecture échouée, ABSENT prouvé, crash et Qdrant indisponible ; aucune suppression réelle.
4. **P1 — Web W1** : contre-revue finale du patch 0004 de résolution DNS plafonnée ; confirmer le comportement lorsque 8 threads sont bloqués, puis rédiger les tests de retour à la normale.
5. **P1 — Dialogue I1** : finaliser le patch 0005 de fraîcheur par source (DARME 60 s, défaut 300 s), tester date future, fuseaux et compatibilité des anciennes observations.
6. **P1 — Index Qdrant** : mettre à jour les sondes 0007–0009 pour le découpage par passages et l'état INDEX_STALE ; conserver les corpus de calibration et test figés.

Claude possède ses patchs et sondes ; GPT possède change_journal.py, journal_migration.py, reconcile_preview.py et les modules Core partagés. Pas de modification concurrente. Rapports avec SHA et résultats exécutés. Les tâches publiées n'activent pas automatiquement Claude.
