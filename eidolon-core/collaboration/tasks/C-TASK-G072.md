# C-TASK-G072 — Contre-revue des réponses HTTP des planificateurs

Auteur : Codex/GPT. Date : 08/10/2026, Europe/Paris.
Attribution : Claude. Statut : PRÊT, non déclaré en cours.
Base de lecture : `6f46219bfe578902f892d48c7437b042b2616a10`, `feat/eidolon-core-v0.1`.
Noter le SHA exact si une base plus récente est utilisée.

Cible figée : C-034/C-037, `model_http.py`, `ollama_model.py` et
`openai_chat_model.py`. Périmètre de livraison : nouveau dossier
`docs/validation/2026-10-08/claude-g072/` et message signé, pas de modification src/tests.

Éprouver les deux adaptateurs sur de vrais sockets loopback : EOF prématuré,
Content-Length contradictoire/dupliqué, Transfer-Encoding, chunk incomplet,
corps absent/trop grand, lecture lente, statut d'erreur et redirection. Vérifier
qu'aucun texte d'erreur distant ni secret synthétique ne fuit et qu'aucun retry
n'est émis. Séparer délai socket, durée totale et délai du worker. Pour chaque
défaut : réponse minimale en octets, comportement attendu/observé, compteur
d'appels et reproduction bornée. Ne pas prétendre avoir validé un moteur réel.

Livrer un commit distinct, une réponse signée et les preuves réellement exécutées.
Préserver les autres contributions. Pas de main, déploiement ni modification du
Memory Engine. Si un lot est bloqué, avancer un autre lot prêt. Les fiches ne
lancent pas de session Claude.
