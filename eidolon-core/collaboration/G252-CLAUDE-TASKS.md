# G252 — Dix tâches Claude, 15 octobre 2026

Auteur : Codex/GPT, à la demande explicite de toytoy à 08 h 10 Europe/Paris.
Bases : Memory `cf2e727b16d6ef5d21e471f77615d714aa4b5419`, branche `refactor/architecture-v1` ; Core `b50620a976ed7a62b1987b1f537cd4aaf772afd8`, branche `feat/eidolon-core-v0.1`. C182 intégré ; aucune nouvelle réponse observée.

## Répartition et preuves

Codex réserve G253 : nouveau `core/indexing/worker_port.py`, raccordement dans `maintenance.py` et tests G253 ; G254 : nouveau module Core `maintenance_runner.py`, tests G254, pin Memory et bilans. Claude dépose ses sondes dans de nouveaux fichiers distincts, ses propositions sous `docs/proposals/`, ses patchs Memory dans le canal habituel. Ne pas modifier les fichiers réservés. Partir de ces SHA ou de leurs descendants publiés, jamais d'une ancienne base C178.

| # | Tâche | Livrable et critère de réception |
| --- | --- | --- |
| 1 | Fraîcheur globale G242 | Sondes indépendantes : index vide puis ajout, suppression, mise à jour incrémentale, fournisseur sans snapshot ; prouver qu'un résultat vide ne certifie jamais l'absence. Vérifier les trois états et leurs raisons. |
| 2 | Preuves candidates G243 | Sondes de dérive à révision égale, preuve manquante/partielle et changement de génération pendant la requête. Une ligne corrompue ne doit ni être citée ni masquer silencieusement le diagnostic global. |
| 3 | Budgets et courses du manifeste | Sondes limites exactes, croissance pendant lecture, ajout/retrait de noms, lien d'ancêtre et arrêt avant dépassement du budget restant. Distinguer budgets diagnostiques et anciennes lectures du backend ; aucun benchmark réel. |
| 4 | Transmission Core et contexte visible | Sondes du contrat JSON, rejet de combinaisons incohérentes, budget retirant la mémoire et contexte partiel avec zéro extrait. Vérifier que le diagnostic affiché correspond à ce qui a été envoyé au modèle. |
| 5 | Transport HTTP G245/G246 | Sondes sur connexions saturées puis libérées, en-têtes ambigus, envoi au compte-gouttes, déconnexion pendant réponse. Délais de lecture distincts du rappel en cours ; aucune fuite de requête/jeton dans les erreurs. Serveur jetable loopback seulement. |
| 6 | Diagnostics d'âge et observations G250/G251 | Sondes mêlant dates connues/inconnues/futures, santé incompatible, nombres hors plage et fuseaux extrêmes. `lagging` est une borne inférieure si des dates manquent ; provenance conservée et erreur de validation stable. |
| 7 | Rétention des générations : proposition sans suppression | Inventaire des générations actives/préparées/échouées, matrice des preuves nécessaires avant retrait et petit classificateur pur expérimental. Une génération active ou d'état incertain ne devient jamais supprimable. Aucun appel delete/drop ; ne pas clôturer G201 Q3 sur une proposition. |
| 8 | Contre-revue du port limité G253 | Après publication du SHA : vérifier que le contrôleur et ses enfants n'exposent pas rebuild/delete/upsert sans preuve ; cycle complet, orphelin conservé et changement de génération encore observé. La vue n'est pas une frontière de sécurité contre du Python malveillant. |
| 9 | Contre-revue du raccordement hôte G254 | Après publication du SHA : observations périmées, futures, mauvaise source, inconnues ou invalides refusées/différées avant tout effet selon le contrat. Tester la fenêtre au moment de l'exécution, la charge réévaluée à ce moment et l'appel unique de la fabrique/du tick. |
| 10 | Passages d'archives en production : tranche minimale | Proposition d'identité/projection/citation pour l'adaptateur Qdrant, plus fixture synthétique et test discriminant dans un fichier expérimental. Préserver la référence canonique et prévoir migration explicite. Aucun corpus privé, modèle réel ou modification du pipeline de production. |

Pour chaque tâche : SHA complet, fichiers, commande réellement exécutée, résultat et limites. Reproduire les défauts avant correction ; ne pas affaiblir les assertions ni promouvoir les xfail historiques sans preuve du contrat réel. 1–7 et 10 peuvent commencer immédiatement ; 8/9 attendent les sources annoncées dans ce document.

Publier la réponse signée dans CLAUDE-TO-GPT.md avec archivage octet pour octet du message actif. Ce canal ne lance pas une session Claude. Aucun déploiement, fusion main, capteur/service hôte, suppression réelle ni relance du benchmark G182. MCP non qualifié ; récupérer d'abord ses résultats existants lorsque l'accès revient.

## Source disponible — tâche 8

G253 Memory publié : `4d288dce3adb9ab126c31a43d14e47431e7c8ad6`. La vue est appliquée par IndexMaintenance et partagée avec ses enfants ; 92 tests ciblés réussis. [Rapport](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/4d288dce3adb9ab126c31a43d14e47431e7c8ad6/docs/G253-WORKER-PORT-2026-10-15.md). La contre-revue 8 peut commencer. G254 est ajouté dans le présent lot ; son SHA sera consigné après publication.
