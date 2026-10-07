# C-TASK-G069 — Recette indépendante du paquet installé

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude. Statut : PRÊT.
Demandées pour la suite de travail d’aujourd’hui ; ne pas sacrifier les validations
pour une échéance. Finir G064/G065 puis enchaîner les lots dont la base est disponible.

Base : dernière publication Core, noter SHA et empreinte de l'archive.
Périmètre : docs/validation/2026-10-07/claude-g069/ et nouveau script de recette
isolé sous ce dossier. Construire hors réseau, installer en venv temporaire,
exécuter CLI recherche/reprise/diagnostics et catalogue HTTP sur loopback.
Vérifier ressources Desktop embarquées dans l'archive, aucune dépendance implicite
au checkout/PYTHONPATH, état source inchangé et arrêt de tous les processus créés.
Une absence d'outil est un blocage documenté, pas un PASS ni une installation
système. Pas de VM, SSH réel, Windows, GPU ou fournisseur réel.

Publier résultat, tests exécutés, limites et commit séparé. Pas de main, déploiement
ni modification Memory Engine. Si bloqué, avancer la prochaine tâche prête.
