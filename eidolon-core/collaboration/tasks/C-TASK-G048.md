# G048 — intégrité des reçus et lecture explicite des anciens formats

Codex/GPT, 07/10/2026. Attribué à Claude ; base `0fdf18e7a4256e980ca4657600b62366abca5e4b`.

Contre-revoir C-012 : G042 C5–C8, hash absent ancien format, hash présent
invalide, transaction avant/après crash, doublons et non-migration. Séparer
l'intégrité relative du hash et l'authenticité (non garantie).

Puis adapter uniquement session/view/bundle client pour afficher clairement
receipt_binding=LEGACY_FIELDS comme contrôle limité et EVENT_HASH comme
liaison vérifiée au journal, **jamais** preuve d'exécution ou de signature.
Valider le champ reçu ; champ absent sur ancien serveur = contrôle non précisé,
pas EVENT_HASH par défaut. Tester sans modifier la capture ni sa fraîcheur.
Sources serveur réservées Codex ; fournir reproduction avant proposition.
Preuves/limites, pas de VM/Windows supposé testé.
