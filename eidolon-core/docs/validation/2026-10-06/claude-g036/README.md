# G036 — reçus de commande dans le client connecté : preuves

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G036](../../../../collaboration/tasks/C-TASK-G036.md).
Base : `0890820` (C-009b reçus, C-009e à C-009g intégrés). Fichiers modifiés :
`desktop/connected/` seulement. `http_api.py`, `receipt_lookup.py` et les
tests Python ne sont pas touchés.

[Résultat des tests : 29/29](node-tests.txt), dont :

- **6 tests sur transport scripté** :
  - FOUND d'une approbation historique puis d'une révocation, la capture
    actuelle restant REVOKED et l'objet capture inchangé à l'octet près ;
  - reçu d'annulation REQUESTED sur une mission encore NEW ;
  - NOT_FOUND ;
  - erreurs : `RECEIPT_MISSION_MISMATCH`, `RECEIPT_UNAVAILABLE` (la session
    reste connectée), puis `STORE_CHANGED` (consultation bloquée jusqu'à la
    reconnexion) ;
  - 5 formes de clé invalides **jamais envoyées** ;
  - réponses refusées : un identifiant non renvoyé à l'identique, ou
    `authorizes_resend: true` ;
  - réponse arrivée après un changement de sélection ou une déconnexion :
    ignorée.
- **3 tests sur le vrai serveur** avec le jeu bêta C-009g :
  - les trois `receipt_queries`, une clé absente, la clé d'une autre mission ;
  - un autre Store derrière la même adresse donne `STORE_CHANGED`, puis la
    reconnexion efface l'affichage ;
  - parcours **Chromium** : reçu trouvé, clé absente, clé invalide, aucun
    bouton de commande.
- Les 20 tests G031 restent verts, après le passage des outils communs dans
  `tests/helpers.js`.

Captures (serveur réel, données synthétiques) :

- [approbation historique APPROVED, capture actuelle REVOKED](g036-receipt-found.png)
- [clé invalide refusée sans envoi](g036-receipt-invalid.png)

## Règles appliquées

- La requête est construite par la session : `store_id` vient de
  `/v1/health`, `mission_id` de la sélection. Seules les deux clés sont
  saisies, et elles sont vérifiées localement.
- La réponse doit renvoyer **à l'identique** les quatre identifiants et les
  quatre drapeaux `false`. Pour FOUND, le reçu doit porter les mêmes
  identifiants. Sinon elle est refusée, sans affichage.
- Le reçu est gardé à part (`state.receipt`), effacé à chaque changement de
  sélection, à la déconnexion et à l'effacement d'identité.
- `RECEIPT_UNAVAILABLE` (503) ne met pas la session hors ligne. Les autres
  503 continuent de le faire.

## Limites

- Il n'y a pas d'inventaire des reçus : il faut connaître la clé. C'est le
  contrat C-009b.
- Le libellé « Capture actuelle » compare au seul statut de décision (reçu
  de décision) ou au statut de mission (reçu d'annulation). Ce n'est pas un
  audit de l'historique.
- Chromium headless sous Linux seulement ; ni Windows ni tunnel.
