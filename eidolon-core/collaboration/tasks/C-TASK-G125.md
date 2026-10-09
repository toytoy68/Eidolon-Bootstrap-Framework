# C-TASK-G125 — Stockage occupé distinct de stockage indisponible

Auteur : Codex/GPT. Attribution : Claude. Date : 09/10/2026, Europe/Paris.
Base examinée : C121 / `8d2613381e833f8d7124aa34f089b2dd94f16d0a`. Statut : PRÊT selon dépendances.

Mettre en œuvre la distinction proposée en G081 après revue des codes existants : classification du verrou réel, compatibilité des contrats et diagnostic utile dans le client. Aucune nouvelle tentative automatique de commande à effets. Lecture temporairement occupée peut être réessayée explicitement. Conserver indisponible pour fichier absent/corrompu/permissions/identité différente ; tests SQLite réel occupé et indisponible. Claude possède http_api.py, conversation_api.py et UI pour ce lot.

Périmètre : Claude garde conversation/mission/API/UI ; Codex garde media_*.py, media-agents.js, tests média et paquet. Ne pas attendre le GPU pour avancer les contrats/tests. Publier preuves réellement exécutées ; aucun main, déploiement ou modification Memory Engine. La fiche ne démarre pas une session.
