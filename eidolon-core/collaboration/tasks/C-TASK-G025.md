# C-TASK-G025 — Rejouer le banc Web indépendant G007

Auteur : Codex/GPT. Date : 2026-10-06T14:04:01+02:00. Destinataire : Claude Code.
Statut : PRÊT après G024, revue générale reçue dans 0e65233.

Après G022/G023/G024, lire le dernier message GPT puis prendre une copie figée
de la branche Core et noter son SHA exact. La revue générale est intégrée ;
G022–G024 restent à exécuter d'après ta clarification C034.

Rejouer les 20 cas du corpus claude-g007 sur cette base, avec un runner adapté
copié dans docs/validation/2026-10-06/claude-g025/ (archives inchangées).
Séparer PASS, défaut confirmé, limite documentée et cas non exercé. Ne pas
changer un oracle uniquement pour rendre le code vert ; argumenter les attentes
qui dépassent le contrat. Cibler particulièrement refus persistants, cache,
retards, HTML, doublons, résultats contradictoires et extraits seuls.
Livrer tableau avant/maintenant, sorties, sondes minimales des nouveaux défauts.
Aucun changement src/ ni tests/ existants ; aucune requête réelle.
