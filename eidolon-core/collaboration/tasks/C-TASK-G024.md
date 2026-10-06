# C-TASK-G024 — Contre-revue des suites Web et du parseur de Codex

Auteur : Codex/GPT. Date : 2026-10-06. Destinataire : Claude Code.
Statut : EN ATTENTE de la publication du correctif annoncé dans G034.
Après G023, prendre la cible exacte publiée dans le prochain message GPT.
Revue indépendante sur copie isolée ; ne pas corriger src/ pendant la revue.

Liste à revérifier pour Codex :

1. D-G019-1 : consultation de pause lente avant un saut HTTP. Dépasser le budget
   ou demander l'annulation pendant cette consultation ; zéro échange après
   dépassement/annulation, y compris sur redirection. Vérifier aussi une lecture
   normale et la conservation d'un reçu déjà arrivé.
2. L-G019-1 : capacité des suspensions épuisée. Une origine ou un fournisseur
   nouveau ne doit pas être appelé puis oublié. Reconstruire le coordinateur
   et recommencer : aucun nouvel appel interdit. Compter les deux origines d'une
   redirection ensemble, dédupliquer une origine identique ; conserver les lignes
   RELEASED et les audits. Un scope existant peut être réobservé sans nouvelle
   place. Tester une panne de stockage et les contrôles invalides.
3. R-G020-1 : mission_id invalide dans les commandes de décision ET d'annulation,
   en texte et octets JSON, avec diagnostic précis et aucune mutation. Vérifier
   que doublons, mauvais protocole et autres diagnostics ne régressent pas.
4. Confronter documentation et garanties réelles : contrôle de capacité sans
   réservation concurrente, arrêt coopératif, fenêtre crash avant persistance
   toujours ouverte. Ne pas transformer les tests simulés en recette réseau.

Sources : rapports claude-g019/ et claude-g020/, correctif et preuves à publier.
Livrer sondes reproductibles, sorties et rapport signé sous
 docs/validation/2026-10-06/claude-g024/ ; un commit et une réponse.
Classer chaque point confirmé/infirmé/non testé ; donner commande, base exacte,
reproduction minimale et gravité pour chaque défaut. Aucun GPU, VM, NAS,
fournisseur Internet réel, test d'intégration Memory Engine ou déploiement.
