# C-TASK-G067 — Contre-revue des lectures SQLite bornées

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude. Statut : PRÊT.
Demandées pour la suite de travail d’aujourd’hui ; ne pas sacrifier les validations
pour une échéance. Finir G064/G065 puis enchaîner les lots dont la base est disponible.

Base : dernière branche Core publiée, SHA exact dans le rapport.
Périmètre : docs/validation/2026-10-07/claude-g067/ seulement.
Auditer ReadOnlyStore, MissionList et ClientSync face à tables vides/altérées,
corps volumineux, journaux WAL, auteur concurrent et budget SQL consommé.
Établir si un refus peut migrer/créer des fichiers ou retourner une page partielle
comme complète. Mesurer temps et nombre d'octets pour cas synthétiques bornés.
Aucune boucle illimitée, données utilisateur ou modification Core ; défaut minimal
reproductible, empreintes avant/après, distinguer délais SQL et blocage stockage.

Publier résultat, tests exécutés, limites et commit séparé. Pas de main, déploiement
ni modification Memory Engine. Si bloqué, avancer la prochaine tâche prête.
