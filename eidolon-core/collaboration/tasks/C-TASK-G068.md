# C-TASK-G068 — Préparer la qualification du producteur de rotation

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude. Statut : PRÊT.
Demandées pour la suite de travail d’aujourd’hui ; ne pas sacrifier les validations
pour une échéance. Finir G064/G065 puis enchaîner les lots dont la base est disponible.

Base : G063 et lecteur C-028/C-030 courant, SHA noté.
Périmètre : nouveau docs/proposals/2026-10-07-retention-integration/ uniquement.
Créer un banc de compatibilité qui produit puis relit les exports via le lecteur
Core, avec 100 actives, missions non terminales protégées, dépassement explicite,
WAL, coupure aux frontières et reprise répétée. Comparer limites producteur/lecteur
(taille, nombre, événements, entier sûr JS). Documenter les écarts et une migration
schema2→3 réversible avant retrait, sans activer ni migrer un vrai journal.
Ne pas recopier un second lecteur ; importer les composants existants. Ne pas
modifier research_guard/query_history/research_archive : intégration réservée Codex.

Publier résultat, tests exécutés, limites et commit séparé. Pas de main, déploiement
ni modification Memory Engine. Si bloqué, avancer la prochaine tâche prête.
