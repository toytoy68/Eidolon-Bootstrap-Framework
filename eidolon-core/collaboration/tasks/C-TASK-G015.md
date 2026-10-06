# C-TASK-G015 — Contre-revue des reçus d'annulation

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Destinataire : Claude Code.
Statut : prêt après G012/G014 ; pas besoin d'interrompre un lot déjà pris.
Cible : C-008c, commit `9d1cc0fa6539ea94a504572645901186ec16981d`.
[Contrat](../../docs/CANCEL-RECEIPTS.md) ·
[preuves/empreintes](../../docs/validation/2026-10-06/codex-cancel-receipts/README.md).

Sondes indépendantes sur copies temporaires, sans correctif src/tests Python :

1. Flag, événement, reçu atomiques en cas de panne avant/après commit. Même
   commande simultanée : même reçu ; même clé pour autre mission/type : conflit,
   sans annulation supplémentaire. Le verrou d'exécution ne bloque pas submit.
2. Course avec approbation, progression et succès : demande avant commit de
   succès l'empêche ; succès déjà commis intact. Aucun besoin de révision
   attendue pour demander l'arrêt de la mission entière explicitement nommée.
3. Effet commis par l'enfant puis annulation : aucune absence d'effet déduite,
   aucune disparition de preuve ni relance ; REVIEW_REQUIRED reste traitable
   par les chemins de réconciliation existants.
4. Interprétation client : REQUESTED / ALREADY_REQUESTED / ALREADY_TERMINAL,
   reçu historique, deux types de receipt.protocol dans la consultation commune.
   Aucun événement ni reçu seul ne doit devenir une permission ou un succès.

Signaler les vrais écarts séparément des limites déclarées : identité locale
non authentifiée, restauration ancienne, pas de reçu run, pas de délai dur,
rétention sans quota. Les exceptions SQLite peuvent encore remonter dans la CLI ;
diagnostic uniforme inscrit à la TODO, pas présenté comme corrigé.

Livraison : rapport et sondes dans docs/validation/2026-10-06/claude-g015/,
message signé et commit distinct. Aucun outil externe, poste Windows, VM/NAS,
modèle réel ou Memory Engine canonique. Ne pas modifier la cible figée G014,
qui garde sa contre-revue C-008b distincte de ce lot.
