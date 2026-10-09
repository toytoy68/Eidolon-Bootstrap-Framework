# C-TASK-G123 — Route et affichage des résultats média dans le chat

Auteur : Codex/GPT. Attribution : Claude. Date : 09/10/2026, Europe/Paris.
Base examinée : C121 / `8d2613381e833f8d7124aa34f089b2dd94f16d0a`. Statut : PRÊT selon dépendances.

Après G122 et le contrat worker Codex, raccorder result_view au serveur et à la page. Le lien proposition → ticket → travail provient uniquement du serveur ; refuser un autre travail même si sa requête est identique. Montrer attente, refus, effet incertain, collecte partielle et résultat non vérifié. Aucun chemin ni secret dans la réponse. Pas de téléchargement improvisé. Tester rechargement, ticket étranger, travail absent, source supprimée et HTML en texte. Ne pas modifier media-agents.js sans coordination.

Périmètre : Claude garde conversation/mission/API/UI ; Codex garde media_*.py, media-agents.js, tests média et paquet. Ne pas attendre le GPU pour avancer les contrats/tests. Publier preuves réellement exécutées ; aucun main, déploiement ou modification Memory Engine. La fiche ne démarre pas une session.
