# C-TASK-G060 — Affichage des missions de recherche dans le client

Auteur : Codex/GPT, 07/10/2026, 12 h Europe/Paris. Attribution : Claude. Statut : PRÊT.
Base publiée : `7b737f4975691742b0a92143b9d3d948a1485bff`. Lire le dernier GPT-TO-CLAUDE avant démarrage.

## Périmètre

`desktop/connected/src/, desktop/connected/tests/, desktop/prototype/ et app.js généré`

Après G055, rendre lisible le type research_retrieval.synthetic et distinguer récupération synthétique complète/partielle/sans preuve. Ne jamais annoncer une vérité confirmée ou afficher une requête/texte non fourni par la projection. Garder la compatibilité des objectifs inconnus et aucune commande distante. Tests avec vraies projections Core de succès/partiel/vide ; régénérer app.js par build.js, pas de modification manuelle du bundle. Ne pas modifier HTTP ni sources Python. Qualifier tests Node vs navigateur réellement exécuté.

## Livraison

Un commit distinct avec message signé, base exacte, commandes, résultats et limites.
Ne pas écraser les preuves précédentes. Conserver G055–G057 avant ces nouveaux lots,
ou passer au lot prêt suivant si une dépendance bloque. Aucun main, déploiement,
VM utilisateur, fournisseur réel ni modification Memory Engine. Aucun nouveau feu
vert nécessaire pour ces tâches locales demandées par toytoy.
