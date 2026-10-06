# C-TASK-G014 — Contre-revue des reçus de décisions locales

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Destinataire : Claude Code.
Statut : prêt **après G013/G012** ; ne pas interrompre le lot prototype pris.
Cible : commit introduisant C-MSG-G024, base de développement `37604a1`.
[Contrat](../../docs/COMMAND-RECEIPTS.md) ·
[Empreintes et preuves](../../docs/validation/2026-10-06/codex-command-receipts/README.md).
Figer le SHA relu ; ne pas attribuer ces résultats à une base plus récente.

## Revue indépendante demandée

Lire commands.py, les changements store/actions/cli et la démo. Construire des
sondes distinctes des 22 tests livrés sur copies temporaires :

1. Décision, événement et reçu atomiques avant/après coupure, erreur SQL et
   conflit de clé entre missions concurrentes. Chercher un reçu faux ou une
   décision persistée sans reçu sur le nouveau chemin command-submit.
2. Même clé/contenu après progression, clé réutilisée avec autre contenu,
   annulation à révision constante, configuration/proposition obsolète et clé
   soumise pendant run. Ni duplication ni contournement des vérifications.
3. Consultation après commit perdu, réponse historique APPROVED après revoke,
   NOT_FOUND pendant une émission en cours. Un client peut-il conclure à tort
   qu'il peut réémettre, annuler une révocation ou déclarer un succès ?
4. Restaurations/clones de base, confidentialité des enveloppes et compatibilité
   JSON/JS : distinguer défaut inédit et limite expressément documentée.

Ne pas demander à ce lot de fournir une identité distante : client_id/actor
restent des libellés locaux. Les reçus cancel/run et l'API réseau sont différés.
Ne pas assimiler le reçu à une autorisation de lancement ou une preuve d'effet.
Tu peux proposer des ajustements du contrat client à partir des exemples,
mais ne branche pas des actions réelles au prototype.

## Livraison

Rapport signé, cas reproductibles et commandes exactes dans
`docs/validation/2026-10-06/claude-g014/`, message dans ton canal, commit dédié.
Aucun correctif dans src/, tests/ Python ou fixtures de production ; déposer
les écarts pour que Codex corrige puis demande une contre-revue ciblée.
Windows/GPU/VM et données privées hors périmètre. G011 (Web) et G010 (étude
Windows) restent ouverts ; ce lot n'annonce aucune réponse de ta part.
