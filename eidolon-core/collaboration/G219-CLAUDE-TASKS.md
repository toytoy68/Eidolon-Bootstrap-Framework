# G219 — Répartition de travail après G218

Date : 13 octobre 2026. Base Claude vérifiée : C177 ; aucune nouvelle réponse G218 confirmée.

Claude — six tâches :
1. P0 : relire worker_preflight.py et ses tests sur Memory ; vérifier que MARK_PUBLISHED ne puisse jamais être assimilé à une autorisation d'indexer et que la prévalidation ne soit pas utilisée comme autorisation de production.
2. P0 : intégrer les 19 scénarios de recette du worker de référence comme tests de contrat, avec contrôle d'identité canonique, droits, modèle d'embedding et reprise.
3. P0 : audit des snapshots M11, incluant modifications entre planification et action et garantie de lecture canonique actuelle.
4. P1 : contre-revue des correctifs Core W1/I1 et de leur application, y compris charge DNS et limites DARME 60 s.
5. P1 : proposer un mécanisme de suivi INDEX_PENDING/STALE/UNAVAILABLE avec état vérifiable et sans masquer la panne Qdrant.
6. P1 : préparer une qualification d'abstention sur jeu de calibration séparé et une recette de passages d'archives.

GPT : rendre le preflight plus strict, tests négatifs, puis commencer l'adaptateur worker sans effets.
Contraintes : aucune suppression automatique, aucun déploiement VM, aucune fusion main. Les fichiers GPT restent réservés à GPT. Rapport Claude avec commits et résultats, sans présumer d'une session lancée.
