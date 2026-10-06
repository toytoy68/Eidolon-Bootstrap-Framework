# C-TASK-G013 — Préserver le suivi des commandes incertaines du prototype

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Destinataire : Claude Code.
Statut : prêt, priorité avant G012. Source : ta livraison G009 `111da40`.
[Revue et sonde](../../docs/validation/2026-10-06/codex-g009-review/README.md).

## Reproduction

accuse-perdu → Autoriser → étape Core (accusé perdu) → rétablir → étape Core
(rejeu) : accord APPROVED mais commande unknown k0-0, ce qui est correct.
Révoquer ou demander l'annulation écrase ensuite client.command par une nouvelle
clé sending ; Consulter le reçu ne permet plus de résoudre k0-0. La trace brute
reste dans outbox, mais pas son suivi actif. Même risque de remplacement avec
deux révocations/annulations avant leur accusé.

## Correction attendue

Conserver une identité et un état par commande jusqu'à résolution de son reçu,
sans assimiler les événements de mission à une réponse à cette commande.
Associer chaque ACK/RECEIPT à sa clé, y compris réponse tardive et doublon.
Une nouvelle commande ne peut pas effacer l'incertitude de la précédente.
Le choix d'affichage est libre : liste des commandes en cours ou présentation
équivalente, sans perdre la direction graphique. Ne pas bloquer par principe
une demande d'annulation utile ; son suivi peut être indépendant de l'accord.
Une retransmission sensible reste interdite tant que le reçu n'est pas réconcilié.

Tests indépendants : unknown accord + revoke, unknown accord + cancel, double
clic revoke/cancel, réponses hors ordre, doublon de reçu, reçu pour clé inconnue.
Une réponse tardive ne doit ni résoudre la mauvaise commande ni réémettre une
action. Garder les autres scénarios G009 verts et expliquer la politique des
commandes résolues/purgées pour éviter une rétention RAM illimitée.

Fichiers : desktop/prototype/model.js, app.js et tests/doc du prototype.
Preuves : docs/validation/2026-10-06/claude-g013/. Aucun src/ ou tests/ Python,
aucun serveur réel, aucune VM/Windows/donnée privée. Codex conserve le contrat
serveur et publie C-008a en lecture seule ; ces commandes restent simulées.
Commit distinct avant G012, réponse signée dans ton canal ; pas besoin de
nouvelle confirmation de toytoy pour cette correction dans le périmètre.
