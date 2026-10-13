# G212 — Missions Claude après C172
Date : 13 octobre 2026. Statut : demandes publiées, pas de session Claude lancée.

Décision C172-Q1 : fraîcheur configurable par source, 300 secondes par défaut. Pour les métriques Darme, utiliser une limite plus courte, configurée et testée ; une mesure sans date ou trop ancienne ne doit pas être décrite comme actuelle.

Priorités Claude :
1. P0 : rejouer la suite Memory sur les corrections M2, M4, M7, M9, avec sondes indépendantes. Contrôler la conservation de sqlite_sequence, la compatibilité des journaux v1, le cas exact de la limite et l'obligation de revue avant abandon.
2. P0 : préparer une recette isolée du worker en trois étapes : planification, vérification canonique et permissions, action. Aucun retrait Qdrant automatique. Inclure pannes et reprises.
3. P1 : revoir les patchs Core I1 et W1 v2, notamment seuils par source, plafonnement des résolutions DNS, erreurs de refus et régressions.
4. P1 : poursuivre les sondes Qdrant 0007 à 0009, sans modifier les références figées.

GPT : corrections Memory et tests sur branche refactor/architecture-v1 ; application des correctifs Core après revue.

Ne pas fusionner main, ne pas toucher aux VM, ne pas relancer les benchmarks de production.
