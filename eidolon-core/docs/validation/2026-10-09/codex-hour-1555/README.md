# Session Codex du 09/10/2026, commencée à 15 h 55 Europe/Paris

## C121 intégré et contre-revue

Base C121/8d26133 intégrée dans 178ff65 avec six tâches Claude G122–G127.
integrated-suite.txt : 1 294 tests Python réussis, zéro ignoré, Memory activée,
218,436 s. Modèles synthétiques ; avertissements RemoteDisconnected de clients
de test lors des coupures HTTP, suite terminée OK.
dialogue-rechecked.json : G090-R1 corrigé, un appel modèle, réponse pending
concurrente et rejeu identique. shutdown-rechecked.json : G088-R2 corrigé,
fermeture en moins de 0,8 s avant libération de la réponse HTTP synthétique lente,
aucune réponse tardive persistée. Sondes dérivées des contre-exemples Codex,
originaux conservés dans codex-hour-1204.

## C-064 — File média durable

worker-first.txt : 13 tests dédiés réussis. worker-core.txt : 43 tests
worker/exécution/réservations réussis. worker-extended.txt et worker-final.txt :
19 tests dédiés réussis, dont huit processus concurrents, coupure réelle
os._exit(77), panne disque avant/après admission, identité d'un autre travail
avec même requête, six modes, collecte partielle et rejeu sans second import.
worker-full-suite.txt : 1 313 tests Python réussis, zéro ignoré, Memory activée,
217,846 s. Une finition d'affichage CLI des détails du résultat suit cette passe ;
les 19 tests worker ont été rejoués après cette finition.

client-node.txt : 73 tests réussis, 22 Chromium ignorés (absent ici).
Bundle client à jour (node desktop/connected/build.js --check).
bundle-tests.txt : invocation erronée d'un nom de module, aucun test exécuté.
bundle-tests-final.txt : module corrigé, dix tests du builder réussis.

Sources et limites : vraie base conversations pour propriétaire/turn/attachments,
mais current_proposal substitué par le contrat G122 dans les tests du worker
(persistance du média à raccorder par Claude). Backends simulés.
Pas de VM, Windows, GPU, moteur IA réel, main ou modification Memory Engine.
Le paquet installé et les essais intégrés sont les prochaines étapes de la séance.


## C122 intégré, revue indépendante

63 tests ciblés réussis (c122-targeted.txt) et Node conversation (c122-client-targeted.txt).
probe_c122_media_links.py reproduit G123-R1 (autre job_id à requête identique
affiché) et G099-R1 (media_links exclue du digest logique ; pas de perte physique
de sauvegarde revendiquée). probe_c122_cancel_race.js reproduit G124-R1 : réponse
d'annulation de A affichée « arrêt confirmé » tandis que la cible sélectionnée
est B. Transport scripté, aucune annulation réelle. Transmis à Claude G129.
