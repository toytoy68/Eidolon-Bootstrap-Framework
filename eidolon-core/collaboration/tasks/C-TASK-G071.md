# C-TASK-G071 — Contre-revue de la consultation HTTP des archives

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude. Statut : PRÊT.
Demandées pour la suite de travail d’aujourd’hui ; ne pas sacrifier les validations
pour une échéance. Finir G064/G065 puis enchaîner les lots dont la base est disponible.

Après publication C-030, base exacte contenant archive_page.py.
Périmètre : docs/validation/2026-10-07/claude-g071/ ; aucun fichier client G066
ni source API. Tester authentification avant lecture, Host/Origin, corps strict,
curseurs périmés/autre Store, pagination exhaustive, erreurs de fichiers privés,
symlink/FIFO, catalogue changé entre pages, capacité saturée et limites de lecture.
Aucune requête, annotation, chemin local, identifiant de mission ou export brut
ne doit sortir ; tous les champs d'autorité restent false. Empreintes avant/après.
Rejouer l'API réelle loopback, pas uniquement des fonctions simulées. Pas de
contournement de l'authentification ni de connexion à un service utilisateur.

Publier résultat, tests exécutés, limites et commit séparé. Pas de main, déploiement
ni modification Memory Engine. Si bloqué, avancer la prochaine tâche prête.
