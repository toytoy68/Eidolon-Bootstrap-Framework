# G221 — Rapport unique des dix tâches priorisées

Date : 14 octobre 2026. Auteur : GPT. Travaux exécutés via connecteur GitHub, **sans accès VM ni exécution de suite complète**. Claude indisponible jusqu'au lendemain soir.

## Résultat

| # | Priorité | Tâche | État et preuve |
|---|---|---|---|
| 1 | P0 | Geler les invariants et planifier | FAIT — Memory d1ca5e2, document G221-TEN-TASKS |
| 2 | P0 | WAIT sans fausse revue | CODE + TEST PUBLIÉS — 08abfb5, a49a54e |
| 3 | P0 | Actions de plan non falsifiables par duck typing | CODE + TEST PUBLIÉS — e4d75d7, c75d8b7 |
| 4 | P0 | Préserver candidats bloqués par revue globale | CODE + TEST PUBLIÉS — a64ab72, cc4979e |
| 5 | P0 | Contrôle des identifiants de diagnostic worker | CODE + TEST PUBLIÉS — f6b489b, 6505bb0, a50973f ; correction de conception : plusieurs intentions peuvent viser le même document |
| 6 | P0 | Métadonnées canoniques obligatoires et valides | CODE + TEST PUBLIÉS — cddbe6d, d25bef3 |
| 7 | P0 | Aucune réparation silencieuse de schéma SQLite ancien | CODE + TEST PUBLIÉS — 9819e06, 005e3aa |
| 8 | P1 | Budget Web : fermeture SQLite et horloge valide | CODE + TEST PUBLIÉS — Core 22a9e2c, 9c26539 |
| 9 | P0 | Recette Core ↔ Memory ↔ PC | DOCUMENT PUBLIÉ — Core 487db61, 12 scénarios B01–B12 |
| 10 | P0 | Rapport consolidé et suivi | CE DOCUMENT |

## Validation et limites

- **Commits GitHub :** publications confirmées via connecteur. SHAs ci-dessus.
- **Tests nouveaux :** ajoutés au dépôt mais **non exécutés** dans cette séance. Les anciennes statistiques de tests Claude ne valident pas ces commits.
- **Accès terminal :** `git ls-remote` a échoué sur résolution DNS github.com ; impossible de cloner pour exécuter pytest localement.
- **VM / Qdrant réel / Windows :** aucun accès, aucune modification, aucun essai. Le tunnel Cloudflare était précédemment hors service.
- **Aucune fusion main**, aucune activation de worker, aucun accès Web réel, aucune suppression automatique.

## Risques résiduels P0

1. Tests complets Core et Memory sur SHAs figés, puis contre-revue indépendante.
2. Le worker de synchronisation avec effets Qdrant et relecture canonique n'est pas encore implémenté.
3. Les contrôles d'autorisation du budget Web ne sont pas intégrés au Policy Engine.
4. Les diagnostics INDEX_* sont des états calculés sur paramètres fournis, pas une télémétrie Qdrant réelle.
5. Le parcours PC → Core → Memory → LLM et la reprise après crash ne sont pas qualifiés ensemble.
6. I1/W1 Core de Claude restent à intégrer et requalifier.
7. L'indexation par passages, les embeddings réels et l'abstention calibrée restent ouverts.

## Décision de passage

Les tâches 1, 9 et 10 sont livrées comme documents ; les tâches 2 à 8 ont des changements de code et des tests **publiés, non qualifiés**. Le lot G221 ne doit pas être déployé en production sans les tests et la revue. Priorité suivante : restaurer l'accès VM/MCP, exécuter les suites complètes, corriger les régressions, puis intégrer le worker et effectuer B01–B12.
