# G218 — Nouvelle répartition après Claude C177

Date : 13 octobre 2026. C177 vérifié sur branche Claude.

Décisions confirmées : DARME 60 secondes, observations générales 300 secondes ; pas de suppression automatique de Qdrant ; mémoire canonique Markdown.

Six tâches Claude :
1. P0 — Rejouer la suite Memory après l'intégration du correctif M11 ; valider lecture canonique après journal, concurrence et absence prouvée.
2. P0 — Préparer les 19 scénarios du worker comme tests de contrat réutilisables ; documenter l'interface minimale pour GPT, sans toucher aux modules GPT.
3. P0 — Audit des migrations v1/v2 et du verrouillage multiprocessus, y compris crash pendant initialisation.
4. P1 — Étudier l'intégration progressive de passages dans Qdrant (génération distincte, identité de découpeur, relecture canonique) et préparer des sondes.
5. P1 — Proposer une stratégie de calibration d'abstention et de fraîcheur sur jeux distincts ; aucun réglage sur le corpus final figé.
6. P1 — Revoir l'intégration des patchs Core I1/W1, tests de charge DNS et observations périmées, sans modifier les fichiers de GPT simultanément.

GPT : intégration M11 et tests, puis revue Core I1/W1 et premier worker isolé.
Pas de fusion main, pas de VM, pas de changement de corpus de référence. Chaque livraison indique SHA, tests et risques.
