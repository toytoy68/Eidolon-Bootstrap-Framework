# C-TASK-G070 — Éprouver annulation et reprise concurrentes

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude. Statut : PRÊT.
Demandées pour la suite de travail d’aujourd’hui ; ne pas sacrifier les validations
pour une échéance. Finir G064/G065 puis enchaîner les lots dont la base est disponible.

Base : runtime publié, SHA exact ; uniquement données et processus temporaires.
Périmètre : docs/validation/2026-10-07/claude-g070/.
Banc borné de courses : deux exécutants, annulation avant outil/après résultat,
reçu tardif, verrou réellement détenu, interruption d'un sous-processus. Assertions
sur nombre d'appels et vérifications, états et preuves, pas uniquement sorties.
Distinguer annulation demandée, effet inconnu et résultat effectivement vérifié.
Ne pas augmenter les délais pour masquer un défaut. Livrer commandes reproductibles,
limites POSIX et contre-exemple minimal ; aucun changement runtime sans coordination.

Publier résultat, tests exécutés, limites et commit séparé. Pas de main, déploiement
ni modification Memory Engine. Si bloqué, avancer la prochaine tâche prête.
