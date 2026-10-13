# G221 — Recette bêta intégrée Core ↔ Memory ↔ PC

Date : 14 octobre 2026. Statut : recette définie, NON exécutée. Ne pas activer de nouveaux services automatiquement.

## Périmètre minimal

- VM Core : service API, Mission Manager, Policy Engine, modèle local configuré, dialogue, DARME.
- VM Memory : backend canonique Markdown, bridge authentifié, Qdrant optionnel et index reconstructible.
- PC Windows : navigateur via tunnel SSH, authentification appairée, conversation texte et monitoring.
- Internet : OFF pour le premier parcours ; Web/SearXNG évalué séparément.
- Voix, caméra, agents média, robot et EidolonOS : hors critères bloquants de la première recette texte.

## Prévol obligatoire

1. Confirmer SHAs Git, branches, absence de changements locaux et sauvegardes vérifiées sur les deux VM.
2. Vérifier unités, loopback, tunnel SSH, permissions 0600/0700, horodatages UTC, espace libre et journaux.
3. Exécuter suites Python Core et Memory sur les **SHAs exacts** de la recette ; consigner échecs, xfail, skip, durée.
4. Vérifier que Memory ne réécrit pas le corpus canonique pendant un rappel.
5. Vérifier la séparation des identités, permissions et profils ; aucune permission issue du modèle, du Web ou de SOUL.

## Scénarios de recette

| ID | Scénario | Réussite |
|---|---|---|
| B01 | PC → Core, conversation texte | Réponse sourcée, identifiant de tour stable, aucun effet non autorisé |
| B02 | Core → Memory, rappel réel | Référence document/révision vérifiée ; inconnu reste inconnu |
| B03 | Memory inaccessible | Dégradation explicite, aucun faux souvenir ni succès |
| B04 | Qdrant indisponible | INDEX_UNAVAILABLE visible, canonique intact, fallback lexical explicitement signalé |
| B05 | Mission simulée approuvée | Reçu lié à mission, action, tentative, identité et preuve |
| B06 | Mission non approuvée | Refus, aucune action, aucun contournement par texte du LLM |
| B07 | Redémarrage Core pendant une mission | Reprise sans double effet, état incertain conservé |
| B08 | Redémarrage Memory pendant un rappel | Récupération et références intactes, pas de mutation implicite |
| B09 | DARME service dégradé | Badge non rassurant, date et périmètre visibles ; aucun droit d'action |
| B10 | Déconnexion PC puis reconnexion | Même historique et identités, aucune commande répétée |
| B11 | Sauvegarde/restauration sur copie isolée | Sources et reçus préservés, identité de copie distinguée |
| B12 | Web non autorisé | Aucun accès réseau et aucun quota contourné |

## Critères de sortie

- Aucun P0 ouvert sur provenance, autorisations, répétition d'effets, restauration ou fuite de données.
- Tous les scénarios B01–B12 réalisés avec preuves datées et SHAs ; les tests simulés ne remplacent pas les essais VM/PC.
- Dégradation explicite en cas de panne. Pas de fusion main ni de bascule de production avant accord.
- Rétablir MCP/Cloudflare séparément ; un tunnel Cloudflare hors service ne prouve pas une panne des services locaux.

## Journal de preuve à remplir

SHA Core : __ ; SHA Memory : __ ; VM : __ ; PC : __ ; sauvegardes : __ ;
tests Core : __ ; tests Memory : __ ; B01–B12 : __ ; incidents : __ ; décision : __.
