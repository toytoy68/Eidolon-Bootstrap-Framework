# C-TASK-G081 — Recette stockage occupé versus indisponible

Auteur : Codex/GPT. Date : 08/10/2026, Europe/Paris. Attribution : Claude.
Statut : PRÊT. Base : `0b439f02683f475e81d8ef8926d2548aa2a75396`, branche Core autorisée.

Analyser G067-3 : observer codes HTTP et client sous contention SQLite, WAL, fichier absent/corrompu. Proposer contrat compatible BUSY/STATE_UNAVAILABLE et matrice états/retry. Rapport et sondes seulement : pas de changement du protocole sans coordination Codex.

Finir les lots engagés G072–G077 avant de changer de fichiers. Déclarer la base
exacte, publier un commit isolé avec résultats exécutés et limites. Pas de main,
déploiement, accès aux données personnelles ou modification Memory Engine.
Une fiche ne démarre pas automatiquement la session Claude.
