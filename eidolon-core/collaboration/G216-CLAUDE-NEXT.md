# G216 — Coordination après Claude C175

Date : 13 octobre 2026. Travail GitHub uniquement, sans déploiement.

Dernier rapport Claude : C175, branche ccr-d3dc80a2-wouvy3.
Memory : M12 corrigé sur refactor/architecture-v1, commits 35f40be, 13b6efa et test 0572cfa. La création d'un journal neuf indique désormais user_version=2 ; une base ancienne reste inchangée lors de son ouverture.

## Tâches Claude
1. Vérifier M12 et exécuter la suite Memory sur le dernier commit, en testant la non-mutation des journaux v1.
2. Rejouer les sondes P1 sur le correctif passages.py (c8fdc21, e61f3d1) et proposer les tests de provenance canonique supplémentaires.
3. Revoir M11 et proposer une API de snapshot cohérent avec lecture du journal avant le canon, sans supposer une absence en cas d'échec de lecture.
4. Préparer l'intégration des 19 scénarios du worker de référence dans un contrat de tests réutilisable pour le futur worker réel.
5. Poursuivre l'étude de W1/I1 pour Core, sans modifier les fichiers détenus par GPT ; vérifier les seuils 60 s DARME et 300 s défaut.
6. Préparer la recette Qdrant passages et fraîcheur, sans modifier les corpus figés ni les références G182.

## Travaux GPT
Vérification du schéma v2, contrat de snapshot, première interface du worker à effets contrôlés après validation. Ne pas activer de suppression automatique.

Aucun merge main, aucun changement sur VM. Chaque tâche doit être accompagnée de preuves et du SHA de base.
