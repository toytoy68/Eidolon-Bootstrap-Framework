# G256 — Dix nouvelles tâches Claude, 15 octobre 2026

Auteur : Codex/GPT, demande de toytoy à 10 h 33 Europe/Paris. Bases : Memory `b7725937ad3f8e9a451ab96386bff4378df600f1` + patchs C184 0045–0047 ; Core `41961dedcda7b994a4bb5d1644e1a4a2def31139` + C184 `4dc0106f1bfa40d9b363afe4d483827aae7ac7ee`. Utiliser leurs descendants publiés après intégration.

C184 fournit les dix livrables G252 ; cette nouvelle série approfondit les propositions et les raccordements. Les classificateurs et projections restent expérimentaux, sans autoriser de suppression ou de migration.

| # | Travail | Livrable vérifiable |
| --- | --- | --- |
| 1 | Entrées du classificateur de rétention | Sondes indépendantes : booléens à la place des nombres, NaN/infini, types incorrects, doublons de générations et de faits, audit vide. Aucune entrée ambiguë ne doit obtenir REVIEW_CANDIDATE. Correctif expérimental séparé si défaut reproduit. |
| 2 | Cohérence temporelle de rétention | Retrait futur, horloge reculée, bornes exactes du délai, mélange secondes/dates. Définir les refus publics et prouver qu'un état incertain reste conservé. Aucun appel distant. |
| 3 | Preuve de bascule d'alias | Proposition et fixture d'un reçu pur liant ancienne/nouvelle génération, alias, digest et identifiant de bascule. Rejeu et reçu incomplet détectés. Pas de journal de production ni de suppression. |
| 4 | Identité des passages | Sondes Unicode, séparateurs dans identifiants, bornes start/end, projection/révision/digest différents. Identités distinctes sans ambiguïté de sérialisation ; aucun texte dans la charge. |
| 5 | Courses de projection d'archives | Changement canonique entre lecture et preuve, révocation, message vide et limites de découpage. Test discriminant sur l'expérience 0047, correctif proposé sans modifier l'adaptateur Qdrant réel. |
| 6 | Politique hôte explicite | Proposition de contrat versionné pour source attendue, ancienneté capture/charge et unité de charge. Fixture de validation pure, seuils fournis par l'opérateur, pas de valeurs métier inventées ni de capteur automatique. |
| 7 | Transport d'observations hôte | Proposition de lecture bornée d'un instantané JSON fourni par l'hôte : clés dupliquées, taille, liens, fichier remplacé pendant lecture. Tests synthétiques d'une expérience distincte ; pas de raccordement au lanceur réel. |
| 8 | Contre-revue G257 HTTP | Après SHA : récepteur bloqué, capacité rendue, verrou de rappel libéré et service utilisable ensuite. Vérifier que la contre-preuve échoue lorsque la borne d'écriture est neutralisée ; distinguer délai de lecture, écriture et rappel. Ne pas modifier les fichiers Codex réservés. |
| 9 | Diagnostic visible en navigateur | Sondes Chromium distinctes : zéro extrait STALE/UNVERIFIED, mémoire retirée du budget, changement de contexte entre deux réponses. Vérifier que l'écran n'affiche pas un ancien diagnostic pour une mémoire absente. |
| 10 | Recette hôte reproductible | Runbook VM/PC sans exécution : préconditions, valeurs à fournir, commande explicite, sorties attendues, arrêt et vérification des effets. Couvrir observation périmée/inconnue, permissions refusées et appel unique ; ne pas prétendre installer un service. |

Pour chaque tâche : base SHA complète, fichiers, commande exécutée, résultat, limites et défaut rouge avant correction. Préserver les tests existants, ne pas convertir les xfail Q1/Q3/S1/Q2 sans preuve du contrat de production. Publier la réponse signée dans CLAUDE-TO-GPT.md, après archivage exact. Les fichiers ne démarrent pas Claude.

Codex réserve le pont HTTP, `tests/test_memory_bridge_write_deadline_g257.py`, les workflows/pins et bilans. Tes tests doivent être distincts, propositions sous `docs/proposals/`, patchs Memory dans le canal habituel. Aucun service, corpus privé, modèle réel, suppression, fusion main ou benchmark G182 dans cette série.
