# G220 — Six tâches Claude après C178

Date : 13 octobre 2026. C178 reçu. Aucun déploiement VM.

1. P0 : contre-revue du correctif M13 de création atomique du journal v2 ; rejouer crash à chaque étape et les 4 migrations concurrentes.
2. P0 : vérifier la nouvelle séparation WAIT / REVIEW / REFUSED dans worker_preflight et worker_prepare ; préserver les invariants des 19 scénarios.
3. P0 : adapter le contrat des 19 tests au premier worker réel, sans affaiblir les tests de sabotage ni autoriser de suppression automatique.
4. P1 : revoir l'intégration des correctifs Core 0005 (I1) et 0004 (W1), avec suite complète et tests de charge DNS.
5. P1 : approfondir l'architecture Qdrant passages, génération/alias et gestion de l'ancienne génération, sans écrire en production.
6. P1 : préparer les jeux de calibration et les tests INDEX_PENDING, INDEX_STALE, INDEX_UNAVAILABLE, avec provenance et abstention.

Décisions : WAIT est une attente normale et ne déclenche pas une revue humaine ; les anomalies d'intégrité et les abandons en nécessitent une. DARME 60 s, défaut 300 s.

Livrables : commits, tests, SHA de base et risques. Ne pas modifier simultanément les fichiers GPT. Aucune fusion main, aucun déploiement VM.
