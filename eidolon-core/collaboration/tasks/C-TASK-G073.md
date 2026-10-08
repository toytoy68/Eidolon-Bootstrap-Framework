# C-TASK-G073 — Contre-revue du contrôle hors ligne des rapports

Auteur : Codex/GPT. Date : 08/10/2026, Europe/Paris.
Attribution : Claude. Statut : PRÊT, non déclaré en cours.
Base de lecture : `6f46219bfe578902f892d48c7437b042b2616a10`, `feat/eidolon-core-v0.1`.
Noter le SHA exact si une base plus récente est utilisée.

Cible figée : C-035, `qualification.py`, `qualification_io.py`, CLI
`qualification-check`. Périmètre : `docs/validation/2026-10-08/claude-g073/`.

Contrôler les verdicts PASSED_SCOPE/INCOMPLETE/REJECTED et les codes de sortie
0/2/3 ; cases absentes, origines mélangées, critères postérieurs, empreintes,
mesures aux limites, unités incohérentes, JSON profond/ambigu, FIFO et fichier
remplacé pendant lecture. Un verdict cohérent n'authentifie jamais les mesures.
Vérifier l'absence d'état, d'appel réseau et de mutation du fichier. Livrer les
sondes indépendantes, empreintes avant/après et reproduction minimale des écarts.
Ne pas dupliquer la suite existante assertion par assertion.

Livrer un commit distinct, une réponse signée et les preuves réellement exécutées.
Préserver les autres contributions. Pas de main, déploiement ni modification du
Memory Engine. Si un lot est bloqué, avancer un autre lot prêt. Les fiches ne
lancent pas de session Claude.
