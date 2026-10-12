# DARME : service permanent déterministe et conseil Core facultatif

Décision opérateur validée par toytoy le **12 octobre 2026 à 06 h 10 Europe/Paris**. Rédaction : Codex/GPT. Base examinée : `e4f1c5f13f81c5dd3827e3ce5d5dbec6f7ead85e`, branche `feat/eidolon-core-v0.1`. Statut : architecture adoptée ; mise en service permanente restant à développer et à recetter.

## Décision

DARME sera un service logiciel permanent indépendant du serveur conversationnel Core et du LLM. Le modèle actif de Core pourra être sollicité ponctuellement comme conseiller, sans autorité d'exécution. Aucun second LLM chargé en permanence n'est requis pour le premier déploiement.

Le service logiciel assure la collecte authentifiée, normalisation et retrait des secrets, règles de détection, sévérité, état du badge, santé et expiration des sondes, journal, notifications et reprise. Il doit fonctionner sans Core conversationnel, sans Memory et sans GPU. La perte de télémétrie est explicitement inconnue ; une alerte connue reste visible.

Le conseiller reçoit des événements bornés et des références mémoire non fiables, pour expliquer une alerte, résumer un ensemble d'événements et proposer des vérifications. Il ne peut ni réduire la sévérité, modifier le badge, acquitter, débloquer, modifier le pare-feu, redémarrer ou éteindre une machine, ni obtenir un shell. Ses propositions sont du texte, pas des permissions.

Une éventuelle remédiation future appartient à un contrôleur séparé, soumis à une politique déterministe, aux limites de périmètre, expiration, protection du canal d'administration, journal et rollback testés. Cette décision ne qualifie ni n'active une remédiation automatique.

## Résultats qui motivent la décision

Sources : [bilan](validation/2026-10-12/darme/REPORT.md), [audit et travaux](validation/2026-10-12/darme/AUDIT.md), [catalogue](validation/2026-10-12/darme/MODEL-CATALOG.md), [recette et résultats détaillés](validation/2026-10-12/darme/).

Six petits modèles CPU ont produit 96 réponses : 14 scénarios par modèle et deux répétitions, CPU VM101 avec AVX2, deux threads, GPU désactivé et vérifié. Niveaux attendus conservés sur 16 réponses : Qwen3 0.6B 4, Qwen3 1.7B 6, Qwen3.5 0.8B 4, Granite4 350M 8, SmolLM2 1.7B 4, Gemma3 1B 12. Aucun ne satisfait le contrat complet dans ce protocole et avec ces réglages. Cela ne disqualifie pas tous les petits modèles ni d'autres rôles plus simples.

Gemma4 12B, modèle actuellement actif dans Core, sert de témoin GPU : 16/16 niveaux conservés, 16/16 action=none, aucun identifiant cité absent, environ 1,02 s d'inférence et 126,9 tokens/s. La fiche attendue est citée exactement dans 8 des 14 cas avec mémoire ; certaines réponses s'appuient sur l'événement seul. Ces résultats limités ne constituent pas une certification de sécurité ni une comparaison CPU/GPU équitable.

Le triage testé conserve une sévérité fournie par un détecteur supposé authentifié ; il ne mesure pas la découverte d'intrusions réelles. Quantifications différentes, sorties plafonnées à 220 tokens, prompt unique, corpus synthétique limité et peu de répétitions : critiques attendues de Claude.

Huit fiches de sécurité datées et sourcées ont été importées dans le corpus Memory servi à Core (189 informations au total), statut UNVERIFIED/PENDING_REVIEW. L'import et le rappel sont vérifiés ; les recommandations ne valent pas qualification des mécanismes encore absents.

Deux défauts du noyau ont été corrigés : saturation dégrade la visibilité ; les chemins du journal via ancêtres symboliques sont refusés. 27 tests ciblés et 1 470 tests Core complets passent (six ignorés). Le journal temporaire de performance était en tmpfs : ne pas extrapoler son débit au stockage durable.

## Premier déploiement à construire

1. Processus et compte DARME isolés, sans sudo ; stockage dédié et limites CPU/RAM/disque.
2. Collecteurs passifs journald et ports locaux, avec curseurs, authenticité, déduplication et protection contre rejeu.
3. Heartbeats avec fraîcheur/TTL, file et journal bornés, gestion explicite du disque plein et de la reprise.
4. API de statut authentifiée avec dates, couverture et état des sources ; acquittement hors LLM.
5. Notifications et badge, puis recette VM et Windows de perte/reprise et sauvegarde/restauration.
6. Conseil Core facultatif : file bornée, une requête simultanée au plus, déduplication, timeout et limitation de fréquence ; aucune boucle LLM par paquet.
7. IDS, CrowdSec et remédiation évalués dans des lots ultérieurs selon visibilité et recette.

État réel : aucun service DARME permanent, API DARME ou collecteur réel installé. Les unités d'essai ne sont pas un service de protection. Les corrections et documents sont publiés et synchronisés ; Core et Memory restent actifs.

## Contre-analyse demandée à Claude

Ne pas confirmer par principe. Examiner :
- la séparation déterministe/LLM, frontières de confiance, santé, journal et protections de l'administration ;
- le protocole, la formulation du prompt et du schéma, pertinence des critères, faux négatifs, citations, troncatures et biais de quantification ;
- les trois options : logiciel seul ; logiciel + conseil Core ponctuel (adoptée) ; logiciel + petit modèle spécialisé CPU ;
- la contention avec le dialogue Core, délai et indisponibilité GPU, vie privée des journaux et coût de maintenance ;
- un autre placement possible (processus, conteneur/LXC ou VM dédiée), sans supposer de droits Proxmox ou de visibilité SPAN acquis ;
- si une alternative apporte un bénéfice concret : architecture, modèle/checkpoint/licence/runtime, ressources estimées explicitement non mesurées, critères d'acceptation, protocole indépendant, migration et retour arrière.

Livrable attendu : fiche signée C-MSG distincte et document d'analyse, avec accords, objections, alternative éventuelle, preuves réellement rejouées et plan priorisé. La décision actuelle reste la référence tant qu'une alternative n'est pas adoptée. Une revue n'active aucun service ni action réseau.
