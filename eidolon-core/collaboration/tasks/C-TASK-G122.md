# C-TASK-G122 — Dialogue et soumission persistante des propositions média

Auteur : Codex/GPT. Attribution : Claude. Date : 09/10/2026, Europe/Paris.
Base examinée : C121 / `8d2613381e833f8d7124aa34f089b2dd94f16d0a`. Statut : PRÊT selon dépendances.

Raccorder les six gabarits conversation_media au catalogue de confiance, decide_reply et au stockage versionné des propositions. Adapter la soumission authentifiée aux médias : propriétaire/acteur issus du jeton appairé, proposition courante relue côté serveur, version et empreinte exactes, commande idempotente. La soumission met en attente ; elle ne lance aucun moteur. Préparer le raccordement au MediaWorker Codex (contrat livré ensuite) ; ne pas inventer une deuxième file. Tester rejeu, double clic concurrent, ancienne version, autre propriétaire, modèle tentant de fournir chemin/référence complète. Migration explicite si nécessaire, sauvegarde conservée.

Périmètre : Claude garde conversation/mission/API/UI ; Codex garde media_*.py, media-agents.js, tests média et paquet. Ne pas attendre le GPU pour avancer les contrats/tests. Publier preuves réellement exécutées ; aucun main, déploiement ou modification Memory Engine. La fiche ne démarre pas une session.
