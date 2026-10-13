# G215 — Nouvelles tâches Claude, après C174

Date : 13 octobre 2026. Lancement par demande utilisateur. Ne pas confondre publication de tâches et exécution d'une session Claude.

1. **P0 / Worker Memory** : transformer le worker de référence en suite d'acceptation contractuelle pour le futur worker réel, sans modifier les fichiers GPT. Maintenir les 12 scénarios de sécurité et les tests par sabotage.
2. **P0 / Passage P1** : contre-revue de la nouvelle vérification d'identité de passage (document, révision, paramètres de découpage, empreinte, identifiant). Ajouter des sondes de falsification et de citation périmée.
3. **P0 / Journal M4** : rejouer la suite sur la création native v2 et sur une ancienne base v1, vérifier migrations, high-water mark SQLite et absence de modification implicite.
4. **P1 / Aperçu M11** : proposer une API de snapshot cohérent, lecture du journal avant canonique, avec vérification de génération, absence prouvée et gestion des écritures concurrentes.
5. **P1 / Core I1/W1** : finaliser les correctifs d'horodatage par source (DARME 60 s, défaut 300 s) et DNS plafonné à huit threads, avec tests de régression.
6. **P1 / Qdrant** : continuer l'étude des passages en production, des états INDEX_PENDING/STALE/UNAVAILABLE et du seuil d'abstention sur jeu de calibration distinct.

Livrables : commits sur branche Claude, rapports, tests et risques résiduels. Aucune VM, aucune fusion main, aucun changement de données de production. Respecter les propriétaires de fichiers.
