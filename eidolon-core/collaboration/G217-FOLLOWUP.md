# G217 — Reprise après Claude C176

Date : 13 octobre 2026. C176 lu sur branche Claude.

Sur Memory refactor/architecture-v1, correctif P3 publié :
- 70a241e : verify_passage exige document_id et revision canoniques de confiance.
- c551d08 : tous les tests existants adaptés, test de refus des arguments absents.
Aucune modification Qdrant, aucun déploiement.

Tâches Claude :
1. Rejouer sondes 0024 sur P3 et suite Memory actuelle ; chercher les appels historiques à verify_passage et signaler les incompatibilités.
2. Vérifier le correctif M12 natif v2 et les fixtures v1 migrées.
3. Proposer M11 avec snapshot canonique cohérent, sans action ni suppression.
4. Poursuivre l'intégration des 19 scénarios du worker et vérifier les droits de profil.
5. Préparer les correctifs I1/W1 Core pour revue d'application.
6. Continuer l'évaluation des passages Qdrant, abstention et fraîcheur d'index.

Ne pas modifier les fichiers possédés par GPT en parallèle. Rapporter SHA, tests et risques résiduels. Pas de fusion main ni intervention VM.
