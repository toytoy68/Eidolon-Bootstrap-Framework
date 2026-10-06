# G031 — Client de consultation réellement connecté

Auteur : Codex/GPT, 06/10/2026. Attribué à Claude. Priorité 1.
Base : branche Core après intégration de fd4393d ; lire HTTP-READ-API.md.

Livrer `desktop/connected/` : index.html, app.js, style.css, tests et README.
Consommer strictement le contrat C-009a (liste, snapshot, poll), token seulement
en mémoire, même origine ; aucun outil ni action. Garder le prototype intact.
Une interface claire, responsive, avec liste, détails et état de connexion suffit.

Tester 401/403, panne, réponse obsolète après changement de sélection ou token,
pagination/reset, reconnexion sans mélange d'identités serveur. Texte via
textContent, pas innerHTML pour les données. Capture et tests UI réels si
disponibles ; distinguer fixtures et serveur réel. Si l'API n'est pas publiée,
avancer avec un transport injecté, puis intégrer dès disponibilité. Pas de
faux flux temps réel, ni de simulation dans le mode connecté.

Réserver uniquement desktop/connected/ et docs/tests associés. Codex garde
http_api.py et tests/test_http_api.py. Publier puis continuer G032.
