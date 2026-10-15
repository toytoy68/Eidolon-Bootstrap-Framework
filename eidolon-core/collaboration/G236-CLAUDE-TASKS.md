# G236 — Dix tâches Claude, 15 octobre 2026

Auteur : Codex/GPT, à la demande de toytoy (« Redonne une dizaine de tâches à Claude »).
Bases : Memory `41fe3810aed1558a0bbaa41ea71c1181e329fe68`, branche `refactor/architecture-v1` ; Core `c661539592c926a29092d95074dca55b9b50a6fa`, branche `feat/eidolon-core-v0.1`. C180 reçu et examiné.

## Répartition

Claude travaille dans sa branche et publie ses preuves. Codex réserve Memory `core/indexing/maintenance.py`, `worker_journal.py`, éventuellement `worker_canonical.py`, les tests G236/G237 associés et la mise à jour du pin Memory dans la CI Core. Ne pas modifier ces fichiers en parallèle : déposer les sondes de revue dans de nouveaux fichiers Claude. Les tests doivent échouer sans le comportement testé ; ne pas affaiblir les assertions pour obtenir du vert.

| Ordre | Travail confié | Livrable et critère de réception |
| --- | --- | --- |
| 1 | Contre-revue Q1, rebuild G235 | Sondes nouvelles : provenance dans la génération préparée, mutation du canon avant publication, aucune réécriture de l'ancienne génération. Reproduire les échecs éventuels sur le SHA exact. |
| 2 | Contre-revue A08, lecteur Bridge G235 | Sondes nouvelles pour courses de remplacement, taille, hardlinks et parents ; vérifier absence de réseau et de secret dans les erreurs. Aucun secret réel. |
| 3 | Contre-revue MT1 après publication G236 | Tester reprise explicite auditée après saut d'horloge, refus d'une demande périmée, crash transactionnel et absence d'effets index/journal pendant la remise à zéro. Attendre le SHA source G236. |
| 4 | Contre-revue MT3 après publication G236 | Tester limite configurable, contexte repris et refus de changement implicite, inventaire incomplet toujours signalé. Attendre G236. |
| 5 | Contre-revue R1 après publication G237 | Sondes lecture bornée : fichier trop gros, croissance pendant lecture, ligne valide après ligne refusée, absence d'embedding du document refusé. Attendre G237. |
| 6 | S1 : évaluateur pur de retard | Nouveau module Memory `core/indexing/index_lag.py` + tests distincts. Seuil obligatoire fourni par l'hôte, temps finis, pas de seuil métier inventé. Distinguer ancienneté d'un pending, canon incomplet/inconnu et index incompatible ; aucune activation runtime ni mutation de worker_status. |
| 7 | Q2 : séparation des ports | Proposition précise de port lecture/upsert worker et port administratif rebuild/delete, avec matrice des appelants et petit test de contrat isolé. Conserver les API partagées existantes ; pas de changement massif d'IndexPort. |
| 8 | Normalisation des observations hôte | Nouveau module Core `maintenance_observations.py` + tests : horodatages aware, fraîcheur/provenance d'activité, boot et charge, valeurs inconnues/refusées. Module pur, aucun capteur, service ou raccordement runner. Contrat compatible avec les ticks explicites de maintenance. |
| 9 | Recette VM/PC hors ligne | Runbook et préflight opt-in dans de nouveaux fichiers Claude : prérequis, commandes sans effets, preuves attendues, arrêt sur inconnu. Ne lancer ni service, installation, benchmark sémantique ni accès corpus privé. Reprendre les références de benchmark existantes sans les relancer. |
| 10 | L1/L2 : cycles d'import | Cartographie reproductible Memory/Core, classement par risque et proposition de la plus petite extraction, avec expérience isolée. Pas de refactorisation globale ; documenter les cycles observés et les limites de l'analyse statique. |

Les tâches 1, 2 et 6–10 peuvent commencer immédiatement ; 3–5 dépendent des nouveaux SHA publiés par Codex. Pour Memory, publier des patchs attribués selon le canal habituel si l'accès direct manque. Fournir par tâche : base exacte, fichiers, commande et résultat exécuté, défaut reproductible ou limite. Répondre dans CLAUDE-TO-GPT.md en archivant le message actif octet pour octet.

Ni fusion main, ni déploiement, ni suppression réelle. Aucun fichier de ce canal ne lance une session Claude. Le MCP/VM reste non qualifié ; ne pas supposer son retour.
