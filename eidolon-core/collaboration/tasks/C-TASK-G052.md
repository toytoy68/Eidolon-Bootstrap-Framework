# C-TASK-G052 — Contre-revue budget et seuil des reçus

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude Code. État : PRÊT.
Demande explicite toytoy : poursuivre et renouveler la file lorsqu’elle est vide.

Cible disponible GitHub : `7d8efb92ba1b893f48f28a9cfbdcb9d0b09f7323` ; intégrer la branche feat avant travail.

Examiner max_invocations, réservation avant effet, reprises sans remboursement et configuration figée. Vérifier atomicité receipt_hash_required_from, anciens reçus et suppression du hash récent. Documenter la limite contre une réécriture cohérente de toute la base.

Livrer un commit, preuves reproductibles, résultats réels et limites dans docs/validation/2026-10-07/claude-g052/, puis message signé CLAUDE-TO-GPT. Les revues ne modifient pas les sources Codex sans coordination ; joindre un diff proposé. Ne pas modifier main ni déployer. Aucun nouveau feu vert requis dans ce périmètre.
