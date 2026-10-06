# C-TASK-G030 — Préparer le journal des appels Web incertains

Auteur : Codex/GPT, 06/10/2026. Statut : PRÊT après G029.

Concevoir la prochaine tranche locale du journal préalable pour la fenêtre
réponse reçue / pause non commise. Proposition sous
`docs/proposals/2026-10-06-web-inflight/README.md`, sans code de production.

Définir états, identités, transactions et invariants pour fournisseur, lecture
et chaque saut. Comparer base dédiée et partage de la base des pauses ; décrire
quand un reçu termine un appel, comment une pause et un reçu deviennent
atomiques, et comment revue humaine + révision interdit une relance aveugle.
Ne pas confondre inconnu, refus observé et absence d'effet.

Matrice : crash avant/après intention, avant/après échange, avant/après pause,
réponse tronquée, quota concurrent, horloge, disque plein, processus encore
vivant, restauration, corruption, ancien coordinateur sans journal. Proposer
un premier lot borné et des tests multi-processus synthétiques discriminants.
Conserver URLs/requêtes minimisées dans le journal et expliciter les limites
(pas d'exactement-une-fois, ancien binaire, accès direct SQL). Pas de reprise
automatique ni d'identité humaine inventée. Aucun déploiement.
