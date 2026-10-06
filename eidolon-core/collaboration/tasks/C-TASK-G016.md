# C-TASK-G016 — Réparer les trois écarts du consommateur G012

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Destinataire : Claude Code.
Statut : prêt ; priorité avant G014/G015 si aucun lot déjà engagé.
Cible G012 : `cc9a64bda4d9fd619cf25cf8607230d31ae3d7da`.
[Revue et sondes](../../docs/validation/2026-10-06/codex-g012-integration/README.md).

Tu conserves desktop/prototype/ ; aucun changement src/ ou tests/ Python.

1. **G012-01** : accepter objective_kind=null dans les captures réelles Core,
   notamment BLOCKED/CLARIFICATION et une mission encore non liée. Ne pas
   convertir null en objectif inventé ni relâcher les autres validations.
2. **G012-02** : une fois reset proposé, aucune réponse tardive SNAPSHOT/DELTA
   ne modifie la vue ni le curseur avant l'acceptation explicite. Définir et tester
   le traitement d'un autre reset et d'une réponse de l'ancienne époque après
   acceptation. Aucun renvoi de commande ou reconstruction depuis les événements.
3. **G012-03** : REVIEW_REQUIRED reste principal, même si cancel_requested=true.
   Montrer séparément la demande, conserver l'effet inconnu et les preuves ;
   aucun texte ne doit promettre une future capture CANCELLED. Ajouter un cas UI
   montrant simultanément revue et demande d'annulation sans bouton de relance.

Critère de sortie : tests de régression échouant sur cc9a64b puis passant après
correction, démonstration locale et preuve de zéro émission. Conserver une
capture Core observée pour null ; étiqueter les fixtures dérivées. Notre sonde
historique affirme les anciens défauts : ne pas la réécrire en preuve verte,
produire tes tests séparés et expliquer les différences.

Livraison : commit distinct, message signé, rapport et preuves dans
`docs/validation/2026-10-06/claude-g016/`. Préciser environnement et tests UI
réellement exécutés. Pas de Windows, VM, GPU, réseau externe ou modèle réel.
G014/G015/G010 restent disponibles après ce lot ; aucune réactivation de copie
historique, aucun raccordement des boutons à une API réelle dans cette tâche.
