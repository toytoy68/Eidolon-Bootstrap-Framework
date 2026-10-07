# C-TASK-G053 — Premier lot Tauri 2 en consultation

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude Code. État : PRÊT.
Demande explicite toytoy : poursuivre et renouveler la file lorsqu’elle est vide.

Cible disponible GitHub : `7d8efb92ba1b893f48f28a9cfbdcb9d0b09f7323` ; intégrer la branche feat avant travail.

C-D14 rapporte le choix utilisateur Tauri. Préparer dans desktop/tauri un prototype minimal de consultation et son contrat de sécurité, après lecture des docs officielles actuelles. Respecter le contrat same-origin Core : ne pas contourner CORS. Aucune commande distante, permission IPC pour une page distante, plugin privilégié, installation système, autostart ou déploiement. Décrire précisément les limites de navigation loopback et la connexion à une instance locale. Garder le client existant. Si le prototype exécutable exige des décisions manquantes, livrer le squelette et les décisions explicites ; ne pas inventer un appairage. Qualifier séparément compilation, lancement Linux et Windows réel.

Livrer un commit, preuves reproductibles, résultats réels et limites dans docs/validation/2026-10-07/claude-g053/, puis message signé CLAUDE-TO-GPT. Les revues ne modifient pas les sources Codex sans coordination ; joindre un diff proposé. Ne pas modifier main ni déployer. Aucun nouveau feu vert requis dans ce périmètre.
