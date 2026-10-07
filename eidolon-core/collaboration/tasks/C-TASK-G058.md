# C-TASK-G058 — Contre-revue indépendante de l’historique C-019

Auteur : Codex/GPT, 07/10/2026, 12 h Europe/Paris. Attribution : Claude. Statut : PRÊT.
Base publiée : `7b737f4975691742b0a92143b9d3d948a1485bff`. Lire le dernier GPT-TO-CLAUDE avant démarrage.

## Périmètre

`docs/validation/2026-10-07/claude-g058/`

Tester schéma 1→2 explicite, crash avant commit/appel, doublons/orphelins, pagination/reset, SQLite occupé, bornes, modes privés et absence de hash brut exporté. Exercer des sondes indépendantes sur base figée, pas seulement rejouer les tests. Aucune modification des sources Core ; fournir des reproductions minimales et distinguer altération isolée de réécriture SQL cohérente hors garantie.

## Livraison

Un commit distinct avec message signé, base exacte, commandes, résultats et limites.
Ne pas écraser les preuves précédentes. Conserver G055–G057 avant ces nouveaux lots,
ou passer au lot prêt suivant si une dépendance bloque. Aucun main, déploiement,
VM utilisateur, fournisseur réel ni modification Memory Engine. Aucun nouveau feu
vert nécessaire pour ces tâches locales demandées par toytoy.
