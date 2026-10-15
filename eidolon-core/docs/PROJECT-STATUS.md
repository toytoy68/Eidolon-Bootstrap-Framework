# Eidolon — État consolidé du dépôt

## G268 — Corrections C189/C190 reçues, 15 octobre 2026

**G264 et G266 entièrement répondus et intégrés.** Memory source 02ac2e9, huit patchs 0059–0066 ; historique Claude d97ad38 conservé dans Core. Les trois anomalies G267 sont corrigées. Codex ajoute la distinction CLI usage/BLOCKED et protège le contrôle final de copie contre une substitution d'ancêtre. 470 tests Memory ciblés et 265 Core ciblés réussis, exclusions locales explicites ; CI complète en cours. [Bilan](G268-C189-C190-INTEGRATION-2026-10-15.md).

Deux contre-revues ciblées G268 proposées à Claude ; les anciens statuts G264/G266 ci-dessous sont historiques. Compte C187 toujours proposé ; aucun déploiement.

## G266/G267 — C188 reçu et contre-vérifié, 15 octobre 2026

**G262 entièrement répondu**, C188 2e0a9d7 reçu sur 99e6113 ; historique intégré. [Dix nouvelles tâches G266](../collaboration/G266-CLAUDE-TASKS.md), G264 encore ouverte. Memory 527accc publie 0055–0058 et corrige switched_at non représentable (huit rouges, neuf verts). 312 expérimentaux locaux verts avec limites explicites ; 142 outils Core verts, une exclusion UID ; CI complète confirmée : Memory 3002 réussis (19 ignorés, 4 xfail, 12 sous-tests), Core 2025 réussis (8 ignorés, 1328 sous-tests), propriétaires root 5, Chromium 205 sans exclusion. Core source 66784ca, Memory source 527accc ; comptes chevauchants. [Sources et preuves](G267-C188-INTEGRATION-2026-10-15.md).

Trois défauts confirmés dans les outils expérimentaux C188, attribués à G266-1/4/5 : ancêtre symbolique de copie suivi, modèle de cache via lien accepté PASS, budget NaN accepté PASS. **Ces outils ne qualifient pas une migration réelle en l’état.** Aucun compte, service ou déploiement activé.

## G264/G265 — Diagnostic et nouvelle répartition, 15 octobre 2026

[Dix nouvelles tâches G264](../collaboration/G264-CLAUDE-TASKS.md) publiées en Core 8ee8cb6 ; G262 toujours ouverte, dernier reçu C187. Memory **5cfb648** ajoute le diagnostic explicite `--check-storage`, sans jeton/modèle/réseau/provisionnement. Les dix tâches G264 sont désormais disponibles. **Quatre workflows G265 verts : Memory 2944 +12 sous-tests, worker 52, Qdrant isolé 550/1 xfail et serveur 18 ; Core 0d88b5e épinglé sur ce Memory : 1991 +1328 sous-tests, propriétaires 5.** Les 22 nouveaux cas G265 et les 26 G263 passent ; exclusions historiques consignées. [Contrat, sources et preuves](G265-STORAGE-CHECK-2026-10-15.md). Aucun compte/service réel ni déploiement.

## G263 — Rappel readonly explicite, 15 octobre 2026

Memory `86950c87fbff54169010042fa1e8887c9bf7465e` publié ; Core épingle cette source. Même verrou exclusif ouvert en lecture seule sur Linux local, répertoires préexistants exigés, absence/ambiguïté refusées. **Quatre workflows verts : Memory 2922 +12 sous-tests, worker 52, Qdrant isolé 550/1 xfail, serveur 18 ; Core aacf51f : 1991 +1328 sous-tests, propriétaires 5. Les 26 nouveaux cas readonly passent sous UID ordinaire.** Exclusions et xfail historiques consignés. [Contrat, qualification et limites](G263-READONLY-RECALL-2026-10-15.md). Dix tâches Claude G262 maintenues ; aucun nouveau retour après C187. Aucune activation du compte ou du montage réel.

## G261/G262 — Publication et qualification finales, 15 octobre 2026

Auteur : Codex/GPT. **Quatre workflows verts ; dix nouvelles tâches Claude G262 publiées.** [Bilan, sources exactes et liens de preuve](G262-PUBLICATION-2026-10-15.md).

| Source qualifiée | Résultat |
| --- | --- |
| Memory f534315 | 2896 réussis, 18 ignorés, 4 xfail, 12 sous-tests ; worker 52 réussis |
| Contrat Qdrant ciblé f534315 | 550 réussis, 1 xfail |
| Core 70fc0c6 avec pin Memory f534315 | 1991 réussis, 8 ignorés, 1328 sous-tests ; propriétaires root 5 réussis |
| Chromium 70fc0c6 | 202 réussis, aucun échec, ignoré ou todo |

C186/C187 intégrés en conservant les commits Claude et les trois patchs originaux 0052–0054. G258 entièrement répondu ; G260 annulé. [Dix tâches G262](../collaboration/G262-CLAUDE-TASKS.md) disponibles, aucune nouvelle réponse supposée.

Fixture de permissions G260 confirmée sous utilisateur ordinaire. Diagnostic UI G261 et bundle qualifiés dans Chromium : état futur générique et STALE/UNVERIFIED visibles malgré partial faux/absent, uniquement pour la mémoire envoyée. Les limites du runtime local restent consignées dans [le rapport d'intégration](G261-C186-QUALIFICATION-2026-10-15.md), complété par la CI réelle.

Compte dédié C187 recommandé, pas adopté ni activé : [blocage readonly](G261-C187-SERVICE-ACCOUNT-REVIEW.md), ouverture a+b de .write.lock même préexistant. Préparations et contre-revues G262 en attente de Claude. TODO et QUEUE actualisés.

Les exclusions et xfail restent explicites ; aucune nouvelle recette serveur Qdrant/VM/PC/modèle réel. Aucun main, déploiement, compte créé, migration ou relance G182. MCP indisponible au dernier contrôle. Les bilans ci-dessous sont historiques.

## Historique — G260 avant récupération de la branche Claude

Auteur : Codex/GPT. [Bilan, preuves et limites](G260-QUALIFICATION-2026-10-15.md).

- G259 Memory confirmé : **2873 tests réussis**, 18 ignorés, 4 xfail, 12 sous-tests ; contrat ciblé 550 réussis/1 xfail et worker 52 réussis.
- G259 Chromium confirmé : **187 réussis**, aucun ignoré/todo.
- Core G259 : **1942 réussis et un échec** de préparation de fixture non root. Correctif local G260 `7a23bb9` : restauration des droits de l'instantané synthétique après le scénario mode 000, assertion du refus conservée. **56 tests ciblés verts sous root** ; validation non root après correctif encore requise.
- **Dix tâches Claude réattribuées** dans [G260](../collaboration/G260-CLAUDE-TASKS.md), reprenant G258 sans doublons. Dernier retour distant C185.
- **Publication bloquée par contrôle automatique**, correctif et tâches seulement locaux à ce point. Attente de confirmation explicite de la destination avant publication et CI. Aucun déploiement ni fusion main ; MCP toujours en erreur interne.

## Historique — G256–G259

Les états ci-dessous sont les bilans précédents ; le point courant figure ci-dessus.

Bilan G256–G257, 15 octobre 2026. Auteur : Codex/GPT. Reprise demandée par toytoy à 10 h 33 Europe/Paris.

## Livré

- **C184 reçu et intégré** : les dix livrables G252 sont présents, avec historique Claude conservé. Huit tests Core +15 sous-tests et 21 tests Memory vérifiés localement avec `-W error`. Une fuite de fichier dans un test de rétention a été corrigée sans changer les assertions ; le patch original est intact. Les résultats de mutation C184 sont rapportés par Claude, non réexécutés ici.
- **[Dix nouvelles tâches G256](../collaboration/G256-CLAUDE-TASKS.md)** : durcissement des expériences de rétention/passages, preuve de bascule, contrats de politique/observations hôte, contre-revue HTTP, diagnostic navigateur et recette hôte. Toutes les sources sont disponibles. Leur réponse reste à recevoir ; le fichier ne lance aucune session.
- **G257 : écriture HTTP sous pression TCP éprouvée**. Deux vrais clients loopback, sans lecture ou lecture lente, provoquent un TimeoutError d'écriture avec une réponse de 120 Kio sous le plafond de 128 Kio. Le serveur rend sa capacité et le verrou de rappel ; la requête suivante réussit. En neutralisant le délai d'écriture par une mutation temporaire, les deux sondes échouent. Source restaurée octet pour octet, puis 43 tests transport réussis avec `-W error`. Aucun changement applicatif nécessaire.

[Contrat, harnais, contre-preuve et limites G257](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/81084e04c794eb591e42e944a61560425b839dba/docs/G257-WRITE-DEADLINE-2026-10-15.md).

## Sources et qualification

Memory `81084e04c794eb591e42e944a61560425b839dba` ; Core `4f9d05addf4a5ecaa3d80de798bff936610a780f`, épinglé sur ce Memory. Fusion C184 `1ac42920a7b122930cb45b6e2364b50696313684`, avec Claude `4dc0106f1bfa40d9b363afe4d483827aae7ac7ee` comme second parent. Les bilans ultérieurs sont documentaires.

| Validation | Résultat vérifié |
| --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38707295169) | 2793 réussis, 18 ignorés, 4 xfail, 12 sous-tests ; 166,89 s |
| Contrat worker, même workflow | 52 réussis ; 2,30 s |
| [Memory ciblé](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38707295039) | 470 réussis, 1 xfail ; 33,59 s |
| [Core avec pin final](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38707433831) | 1887 réussis, 8 ignorés, 1328 sous-tests ; 303,19 s |
| Propriétaires du jeton, étape root du même workflow | 5 réussis ; 0,06 s |
| [Dernière qualification Chromium](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38693852896) | 172 réussis, zéro échec/ignoré, source Core b244a867 |
| [Dernière recette serveur Qdrant](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38692288647) | 18 réussis, zéro ignoré, source Memory 42117af6 |

Le code applicatif n'est pas modifié par ce lot. Comparaisons Git effectuées : code Core/navigateur et workflow Chromium identiques à b244a867 ; code Memory et harnais serveur identiques à leur dernière qualification. Les filtres de chemins ne relancent pas ces deux workflows pour des ajouts de tests seuls ; leurs résultats ne sont pas attribués à de nouveaux runs. Les comptes se chevauchent. Les 18 exclusions Memory sont exercées sur le serveur dédié ; 8 exclusions Core correspondent à 6 dépendances d'identité optionnelles et 2 contrôles de propriétaire exécutés sous root.

## Limites et suite

L'expérience G257 qualifie le délai de l'opération d'envoi socket ; elle ne borne pas un rappel déjà bloqué et ne promet pas de délai global comprenant lecture, rappel, en-têtes et corps. La réponse et les conditions réseau sont synthétiques ; aucune recette VM/PC n'est revendiquée.

Rétention et passages restent sous `tests/claude_memory_eval`, sans suppression ni modification de l'adaptateur Qdrant de production. L'intégration des propositions n'adopte pas leurs politiques pour la production. Leur validation d'entrées et leurs courses sont confiées à G256. Les quatre xfail historiques restent ouverts (passages, rétention, ancien worker_status S1 et API administrative Q2).

MCP recontrôlé vers 10 h 40 Europe/Paris : erreur interne -32603. Aucun service, déploiement, capteur automatique, corpus privé ou benchmark G182 lancé. Suite : recevoir G256, expliciter les politiques/source hôte, puis recette VM/PC lorsque l'accès et les préconditions sont réunis. Estimations globales inchangées.

## Historique — G252–G255

Les statuts suivants décrivent les lots précédents ; le bilan courant est ci-dessus.


Bilan G252–G255, 15 octobre 2026, Codex/GPT. Demande de toytoy à 08 h 10 Europe/Paris : nouvelle série Claude et poursuite des travaux.

**Dix nouvelles tâches Claude publiées ; deux lots Codex livrés et réception C183 intégrée.** Les dix livrables reçus précédemment via C181/C182 appartenaient à la série G236. C183 est arrivé pendant la qualification : il répond à G251 et ne clôt pas cette nouvelle série.

## Travail livré

- **G252 : [dix tâches Claude](../collaboration/G252-CLAUDE-TASKS.md)** avec bases exactes, fichiers réservés et critères de réception. Six contre-revues des nouveaux contrats, étude de rétention sans suppression, contre-revues G253/G254 et tranche expérimentale pour les passages d'archives. Toutes les sources nécessaires sont publiées. Le fichier ne lance pas une session Claude.
- **G253 : [port limité de maintenance](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/9a61648d48550a3cf2df92f4126d81de4a732994/docs/G253-WORKER-PORT-2026-10-15.md)**. Le contrôleur, le worker et les scanners partagent une vue qui expose six membres, sans méthode d'administration. Les sous-classes étendues sont à nouveau restreintes. L'hôte garde son adaptateur séparé ; permissions, preuves et reprise durable restent appliquées.
- **G254 : [appel hôte explicite](G254-HOST-MAINTENANCE-2026-10-15.md)**. Capture, provenance déclarée et âges sont validés avant la fabrique. La charge et la fenêtre sont évaluées à l'heure fournie pour l'appel. Un appel produit un tick ; aucune répétition automatique après erreur. Les heures de capture/d'appel et la provenance sont conservées.

Huit sondes G253 et 26 sondes G254 ajoutées. Vérification ciblée : 93 tests Memory ; 48 tests Core et 14 sous-tests. Les tests d'intégration utilisent le vrai contrôleur, journal et Qdrant local : indexation autorisée, refus de permission et reports pour charge inconnue/haute/périmée ou sortie de fenêtre. Le premier tick enregistre la borne de passe ; l'indexation est vérifiée sur un second appel hôte explicite.

## G255 — Réception C183 et contrôle indépendant

Les contributions Claude `e55ef954faf7f24d393811a108fbe9a2b8cdf928` sont fusionnées avec leurs deux parents et conservées dans leur forme originale. Patchs Memory 0043/0044 : cinq sondes supplémentaires du rappel et de la saturation HTTP, toutes réussies localement. Les sabotages décrits dans C183 sont des résultats rapportés par Claude, non réexécutés ici.

Deux des quatre sondes Core de Claude échouaient avant son correctif : une date de démarrage/activité à l'époque Unix paraissait ancienne, et une horloge hôte en 1970 était acceptée. Un plancher de validité opérationnelle au 1er janvier 2000 UTC évite ces sentinelles ; ce n'est pas un seuil de retard métier. Un troisième défaut a été reproduit indépendamment : une charge datée de 1970 restait acceptable si l'hôte autorisait cent ans d'ancienneté. Elle reste désormais inconnue quelle que soit cette limite. Trois sondes indépendantes complètent les quatre originales ; 40 ciblés +14 sous-tests réussis avec `-W error`.

## Qualification finale

Memory source `99aa52eee334fdd984f55fd571356c9b7e2948f9` ; Core source `b244a867249ecd09b3c1b913538b148e54f35e40`, épinglée sur ce Memory. Les quatre workflows déclenchés sur ces sources sont verts ; résultats vérifiés dans leurs journaux. Chromium porte sur ce même Core. Le serveur Qdrant n'est pas relancé par ces seuls ajouts de tests : sa dernière preuve porte sur `42117af68e33ad36ea47e6112b12420147fd03bf`, avec code applicatif et harnais serveur identiques. Les commits de bilan ultérieurs sont documentaires.

| Validation | Résultat observé |
| --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38693753319) | 2770 réussis, 18 ignorés, 4 xfail, 12 sous-tests ; 173,53 s |
| Contrat worker, même workflow | 52 réussis ; 2,78 s |
| [Qdrant ciblé](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38693753521) | 447 réussis, 1 xfail ; 32,13 s |
| [Serveur Qdrant HTTP](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38692288647) | 18 réussis, aucun ignoré ; 77,35 s |
| [Core et pin final](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38693852771) | 1879 réussis, 8 ignorés, 1313 sous-tests ; 334,18 s |
| Propriétaires du jeton, étape root du même workflow | 5 réussis, aucun ignoré ; 0,08 s |
| [Chromium](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38693852896) | 172 réussis, 0 échec, 0 ignoré ; workflow vert |

Les comptes se chevauchent. Les 18 exclusions Memory sont exécutées séparément sur serveur ; les 8 exclusions Core couvrent 6 dépendances d'identité optionnelles et 2 sondes de propriétaire exécutées en root. Le workflow Core ordinaire conserve 140 tests Node réussis et 26 ignorés ; Chromium est qualifié séparément sans exclusion.

## Limites et suite

La vue n'est pas un sandbox contre du Python malveillant dans le même processus ; l'adaptateur administratif garde ses anciennes API. La source d'observation est une étiquette de provenance, pas une authentification. L'heure est déclarée par l'hôte : aucune borne murale n'est garantie si la fabrique ou le tick se bloque. Une erreur après construction peut laisser des effets ; elle n'est pas rejouée automatiquement.

La livraison ajoute un point d'entrée de code, pas un service installé. Le choix des capteurs, des politiques hôte, de leurs délais et le raccordement au lanceur réel restent à réaliser puis à qualifier sur VM/PC. Aucun corpus privé ni modèle réel utilisé, aucun seuil métier de retard calibré, aucune suppression ou fusion main. L'échéance d'écriture d'une réponse HTTP n'est pas encore éprouvée avec un récepteur réellement bloqué ; les réponses de test tiennent dans les tampons du noyau. Les quatre xfail historiques (passages, rétention, ancien worker_status S1 et API administrative Q2) restent suivis.

MCP recontrôlé vers 08 h 27 Europe/Paris : erreur interne -32603. Suite : contre-revues G252, choix explicite de la politique/source hôte puis recette VM/PC ; récupérer les résultats G182 existants avant toute nouvelle mesure. Les estimations globales ne sont pas modifiées.

## Historique — bilan G251 et lots antérieurs

Les statuts ci-dessous décrivent les lots précédents. Le bilan courant figure au-dessus.


Bilan G242–G251, 15 octobre 2026.

Auteur : Codex/GPT, avec intégration attribuée des livrables Claude C182.
Début de session : 06 h 03 Europe/Paris. Validation finale : 06 h 59 Europe/Paris.
Branches : Memory `refactor/architecture-v1`, Core `feat/eidolon-core-v0.1`.

[Rapport Memory et contrat de fraîcheur](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/cf2e727b16d6ef5d21e471f77615d714aa4b5419/docs/G251-SESSION-2026-10-15.md).

## Résultat livré

- **Rappel indexé vérifiable** : diagnostic global même sans résultat, distinction entre instantané concordant, canon modifié et preuve indisponible. Le digest d'un candidat doit correspondre aux octets canoniques ; une modification à révision inchangée ne peut plus produire une citation sur cette ancienne preuve.
- **Diagnostic transmis jusqu’à l’interface** : validation du contrat, contexte envoyé au modèle et avertissement visible. Un rappel vide n'est jamais présenté comme la preuve qu'un souvenir n'existe pas. Le budget de contexte peut exclure la mémoire ; dans ce cas aucun diagnostic ne prétend avoir été transmis.
- **Pont HTTP borné** : capacité de traitement, échéance totale de lecture, en-têtes et JSON stricts, réponses bornées. Test du trajet Memory → HTTP → BridgeMemory → Dialogue avec vrai transport et Qdrant local.
- **Navigateur réellement exécuté** : workflow Chromium dédié, absence de navigateur bloquante et zéro exclusion exigé. Le premier compte Node a été rectifié : 140 réussis +26 ignorés, et non 166 réussis. La première qualification verte exécute les 172 cas ; la dernière source est requalifiée ci-dessous.
- **Dix livrables Claude reçus** : C181 puis C182, cinq patchs 0038–0042 et historique conservés. Contre-revues MT1/MT3/R1, évaluateur pur de retard, expérience de ports, observations hôte, préflight et runbook. Deux extractions adoptées ; les deux groupes cycliques passent de 38/2 à 13/12 modules sur la base courante, sans prétendre supprimer tous les cycles.
- **Corrections indépendantes** : dix cas rouges sur le préflight et la provenance corrigés. G250 ajoute deux cas rouges : avec une date inconnue, l'âge maximal reste inconnu ; les retards connus restent comptés comme borne inférieure. G251 corrige huit autres cas rouges : entiers non représentables et dates hors plage refusés par les erreurs publiques prévues ; une date UTC haute valide ne déborde plus lors de la comparaison de tolérance. Aucun seuil métier n’est inventé.

## Preuves finales

Source Memory : `797e102833fb47953a222aa13d518e8377db5c3d`.
Source Core : `b9a7b9056e6bbbade095da8caae921fef1dbeba5`, épinglée sur ce Memory.
La qualification Chromium porte sur le même commit Core final.
Les commits de bilan ultérieurs ne modifient pas ces sources testées.

| Qualification | Résultat observé |
| --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38683777246) | 2757 réussis, 18 ignorés, 4 xfail, 12 sous-tests ; 182,37 s |
| Contrat worker, étape du même workflow | 52 réussis, 2,95 s |
| [Qdrant ciblé](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38683777218) | 434 réussis, 1 xfail, 32,02 s |
| [Serveur Qdrant HTTP](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38683777155) | 18 réussis, aucun ignoré, 73,52 s |
| [Core avec pin Memory final](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38683823710) | 1846 réussis, 8 ignorés, 1313 sous-tests ; 290,20 s |
| Contrôle du jeton avec vrais changements d'UID, même workflow Core | 5 réussis, aucun ignoré, 0,06 s |
| [Chromium](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38683823617) | 172 réussis, 0 échec, 0 ignoré ; workflow vert |

Environnements CI : Python 3.13 ; client Qdrant 1.19.1 dans les suites Memory complète et ciblée, 1.15.1 épinglé dans la recette serveur Qdrant 1.15.4 et dans Core. Chromium utilise Playwright 1.62.1. Les modèles restent synthétiques.

Les comptes se chevauchent et ne s'additionnent pas. Les 18 exclusions de la suite Memory sont exécutées séparément sur serveur. Les 8 exclusions Core comprennent 6 dépendances d'identité optionnelles et 2 sondes de propriétaire exécutées dans l'étape root. Le workflow Core ordinaire conserve 140 tests Node réussis et 26 ignorés ; le workflow Chromium couvre les parcours navigateur.

Les échecs intermédiaires sont conservés dans les rapports : QdrantClient utilisé à tort comme gestionnaire de contexte dans trois nouveaux tests serveur (G244 : remplacé par `closing`) ; commande `rg` absente après les 172 succès navigateur (G248 : remplacée par Node). Les workflows corrigés ont été réexécutés. Aucun résultat rouge n'est rebaptisé succès.

## Limites et suite

Quatre xfail restent ouverts : passages d'archives dans l'adaptateur Qdrant de production (G201 Q1), rétention des générations en échec (G201 Q3), ancien diagnostic `worker_status` S1 et API administrative `delete` Q2 (G220). Le xfail de fraîcheur G201 Q2 est résolu ; il ne faut pas le confondre avec celui de l'API G220 Q2.

La concordance d'un digest ne prouve ni pertinence sémantique, ni vérité, ni exhaustivité de la recherche. Le nouveau contrôle du canon coûte une lecture du corpus sous verrou coopératif, bornée par son budget ; il ne borne ni toutes les anciennes lectures du backend, ni la RSS, ni les écrivains externes non coopératifs. L'échéance HTTP couvre la lecture de requête, pas un rappel ou embedding déjà en cours. Le préflight vérifie des métadonnées nécessaires, pas le contenu du jeton ou l'authentification effective.

Les modèles et corpus utilisés ici sont synthétiques. Le point d'entrée actuel du bridge reste lexical tant qu'un hôte ne configure pas explicitement un rappel indexé. Les nouvelles observations hôte et l'évaluateur de retard sont purs, sans capteur ni activation automatique ; le seuil reste à calibrer par l'hôte. Aucun nouveau benchmark sémantique ni recette sur PC/VM installé. MCP contrôlé de nouveau vers 06 h 50 Europe/Paris : erreur interne `-32603`, état VM non qualifié.

Ordre de travaux suivant : contre-revue des nouveaux contrats de rappel et de transport ; raccordement explicite des observations et de la politique hôte ; décision documentée sur les ports puis qualification hors ligne VM/PC, en récupérant d'abord les résultats G182 existants. Les quatre écarts historiques restent suivis. Aucun déploiement, fusion main ou suppression de production effectué ; estimations globales inchangées.

## Historique — bilan G241 et lots antérieurs

Les statuts et mentions d’attente ci-dessous sont conservés comme historique. Le bilan courant figure au-dessus.

Mise à jour : 15 octobre 2026, lot G241, Codex/GPT.

**Lots G236–G241 publiés, C181 intégré et quatre workflows finaux verts. Dix tâches confiées à Claude : 1/2 reçues, 3–10 ouvertes.**

## Validation finale G241

Source Memory testée : `21d24121850e71b64c73163fd04e3a5ab231b970`.
Source Core testée : `799377c49e21fd4d0aab3e018b86b33db94d17ad`, avec ce pin Memory.
[Rapport Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/587d4a9b50357401d9150c46d977b2d72648835a/docs/G241-C181-INTEGRATION-2026-10-15.md).

| Validation publiée | Résultat réel |
| --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38664190711) | **2638 réussis, 15 ignorés, 5 xfail, 12 sous-tests**, 167,64 s |
| Contrat réel du worker, même workflow | **52 réussis**, 2,71 s |
| [Qdrant ciblé et sondes Claude](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38664190616) | **331 réussis, 1 xfail Q2**, 25,31 s |
| [Serveur HTTP et backlog 1200](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38664190548) | **15 réussis, aucun ignoré, -W error**, 71,42 s |
| [Core avec Memory G241](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38664324275) | **1789 réussis, 9 ignorés, 1299 sous-tests**, 270,37 s, aucun avertissement pytest |
| Propriétaires/bornes/liens, étape root du même workflow Core | **5 réussis, aucun ignoré, -W error**, 0,11 s |

Les 15 exclusions Memory sont les cas serveur exécutés séparément. Les 9 exclusions Core comprennent 7 dépendances d'identité optionnelles et 2 propriétaires vérifiés avec succès dans l'étape root. Comptes chevauchants, non additionnés. Les 5 xfail historiques restent ouverts ; les avertissements Node des actions GitHub sont distincts de pytest.

Livré : reprise d'horloge auditée/idempotente, borne d'orphelins configurable, lectures worker bornées, diagnostic d'incompatibilité préservé, recettes HTTP avec pertes réelles de réponse et reprise d'un arriéré de 1200 documents. C181 et son historique sont intégrés, sondes supplémentaires en CI. Le défaut initial du proxy et le faux échec d'ordonnancement de la sonde Claude sont documentés, corrigés et requalifiés.

Suite : contre-revues MT1/MT3/R1, ancienneté S1, séparation des ports, observations hôte, proposition sur les cycles d'import et recette VM/PC. Le canal MCP renvoie toujours une erreur interne au dernier contrôle. Aucun runtime activé, corpus privé, nouveau benchmark sémantique, suppression de production, déploiement ou fusion main.

Les sections suivantes détaillent les étapes précédentes ; les mentions d'attente y sont historiques.

## G239–G241 — Derniers lots

Code applicatif Memory : `fb1b78d4a0adad2f90b0078cd874405258a0511d` (G239).
Dernière base de tests Memory, épinglée Core : `21d24121850e71b64c73163fd04e3a5ab231b970` (G241).
Historique Claude intégré : `6487f2112e59c206997a049fe0037fc1f38b1e61`, dont C181/0037.

G239 conserve INDEX_INCOMPATIBLE dans les scanners et le contrôleur, sans promotion incertaine. [Suite Memory](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38663335034) : 2635 réussis, 9 cas serveur ignorés dans la suite générale, 5 xfail, 12 sous-tests, 155,01 s ; contrat réel 52 réussis. Les cas serveur sont exécutés séparément.

[Recette G238 HTTP](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38662940807) : 9 réussis avec -W error (13,17 s), vrai serveur Qdrant 1.15.4 jetable. G240 : backlog 1200 et panne au milieu d'une page réussis ; premier run 11 réussis et 2 échecs de harnais, car le proxy coupait la réponse du descripteur avant le document attendu. G241 sépare les deux frontières d'effet, 15 cas serveur au total : **résultat corrigé à confirmer**. Aucun modèle réel ou VM.

C181 confirme Q1/W1/A08. Trois sondes Memory ajoutées au workflow ciblé. Un faux échec d'ordonnancement du test de verrou est reproduit puis corrigé ; les mutants sans preuve/sans verrou échouent toujours (3 et 1 échecs), sources restaurées. Core conserve les cinq sondes Claude inchangées ; deux changements d'UID bloqués localement par EINVAL seront exécutés dans une étape CI root sur fichiers synthétiques. [Guide de préparation du jeton](MEMORY-BRIDGE-CREDENTIALS.md).

[Dix tâches Claude](../collaboration/G236-CLAUDE-TASKS.md) : 1/2 reçues via C181, 3–10 ouvertes. La nouvelle réponse ne clôt pas MT1/MT3/R1 par revue indépendante. MCP toujours en erreur au dernier contrôle ; aucune commande VM. [Réponse complète](../collaboration/GPT-TO-CLAUDE.md).

Les sections suivantes retracent les étapes précédentes ; les comptes ne s'additionnent pas.

## G236–G238 — Suite active

- Memory G236 `8a93466038a80fbaaf3eadc136d139c9739c863e` : reprise d'horloge explicite/auditée, défaut durable, reçu idempotent et budget d'orphelins configurable. Migration du checkpoint contrôleur 1→2 ; retour à un ancien binaire incompatible avec ce nouveau checkpoint.
- Memory G237 `096e7bcc81258cc50510e6b0fa9e0d85ebc3e7af` : lectures worker bornées à 8 Mio/fichier par défaut, politique partagée avec le scanner, dépassements conservés pour revue sans bloquer les lignes saines. Pas de borne de RSS revendiquée.
- Memory G238 `6e7ef5c65c397ee85c0d777f69677c51dbbbb2c6` : neuf cas sur serveur Qdrant HTTP jetable à exécuter dans un nouveau workflow. Binaire 1.15.4 vérifié par SHA-256 ; aucun serveur existant utilisé. **Résultat en attente**, exclusions locales explicites.

| Validation observée | Résultat |
| --- | --- |
| [Memory G236](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38662055230) | 2594 réussis, 5 xfail, 12 sous-tests ; contrat réel 35 réussis |
| [Qdrant G236](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38662055164) | 287 réussis, 1 xfail |
| [Core G236](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38662300287) | 1786 réussis, 7 ignorés, 1299 sous-tests, aucun avertissement pytest ; 250,09 s |
| [Memory G237](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38662413157) | 2619 réussis, 5 xfail, 12 sous-tests ; 134,04 s ; contrat réel 52 réussis |
| [Qdrant G237](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38662413171) | 312 réussis, 1 xfail ; 55,61 s |

Les comptes se chevauchent. Core est maintenant épinglé sur G237 ; nouvelle CI à confirmer. [Dix tâches Claude](../collaboration/G236-CLAUDE-TASKS.md), dont contre-revues des trois correctifs, S1, ports, observations hôte, recette VM/PC et cycles d'import. Nouvelle réponse non encore observée. Codex réserve la distinction incompatibilité/panne dans les scanners (G239).

Le MCP a encore retourné une erreur interne lors d'un contrôle de statut ; aucun état live de VM n'est affirmé. Ne pas relancer G182 avant lecture de ses résultats existants. Aucun déploiement, runtime activé, fusion main ou suppression réelle.

Les sections suivantes sont historiques.

## G235 — Suite de la relecture Claude

Code Memory : `507fbb140676dab2b870b582733f0bd421a3b845`.
Code Core : `b8eadc04b2994c27df5d295ea796de4c39bfef68`.
Claude intégré : `2dd8de86def61c811a0d4b6f0d53057c90cfe9c3`, historique complet préservé.
[Réponse à Claude](../collaboration/GPT-TO-CLAUDE.md) et
[rapport Memory](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/41fe3810aed1558a0bbaa41ea71c1181e329fe68/docs/G235-CLAUDE-REVIEW-2026-10-15.md).

La reconstruction Qdrant conserve maintenant ses preuves : la maintenance ne
ré-encode plus chaque document après rebuild. Lecture canonique ancrée sous verrou,
points écrits dans la génération préparée, anciennes générations conservées.
Un seul worker journal applicatif subsiste ; les anciennes expériences sont
exclusivement sous tests. Les sondes de Claude sur le vrai chemin entrent en CI.
Les deux mutations des gardes finaux sont détectées, reproduction indépendante.

Le secret BridgeMemory est lu par descripteurs, sans lien, dans un dossier privé
0700 avec fichier 0600 du propriétaire, régulier et sans hardlink. Lecture bornée
à 4096 octets, contrôle après lecture, aucun réseau si refus. **Avant activation,
vérifier le dossier du jeton : un parent 0755 est maintenant refusé.** Aucun secret
réel ni permission de production modifiés. Ce lecteur cible le pont Linux.

Preuves locales : 361 tests Memory ciblés +5 xfail ; 29 tests Core ciblés verts.
Q1 reproduit rouge avec la sonde Claude ; les 10 nouveaux tests du secret étaient
rouges avant correction. Contributions Claude I1/W1 et corpus de calibration
intégrés sans retoucher leurs résultats attendus ni leurs empreintes.

| Validation publiée | Résultat |
| --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38647247658) | **2567 réussis, 5 xfail et 12 sous-tests réussis**, 280,22 s |
| Contrat du vrai worker, même workflow | **35 réussis**, 2,61 s |
| [Qdrant et sondes Claude](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38647247571) | **260 réussis, 1 xfail (Q2)**, 18,63 s |
| [Core avec Memory G235](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38647296057) | **1786 réussis, 7 ignorés et 1299 sous-tests réussis**, 347,34 s |

Core : aucun avertissement pytest ; 7 exclusions connues (numpy/ONNX/OpenCV et modèles
d’identité optionnels). Avertissements Node des actions GitHub distincts de pytest.
Comptes ciblés/complets chevauchants, non additionnés.

Les xfail sont des exigences ouvertes, pas des réussites : fraîcheur dans le rappel,
passages de production, nettoyage des générations ratées, ancienneté S1 et API delete Q2.
La dernière correspond à une primitive du contrat IndexPort ; aucune suppression
n'est exécutée par le worker/cycle. Aucun nettoyage automatique autorisé par les tests.

Prochain lot : reprise explicite/auditée après saut d'horloge (MT1), borne d'orphelins
configurable (MT3), puis raccordement de l'hôte et recette serveur/corpus/modèles réels.
S1 et séparation du port administratif Q2 restent ouverts ; cycles d'import en dette.
Revue complémentaire Q1/A08 demandée. Aucun déploiement VM, fusion main ou activation.
Les résultats suivants sont historiques et leurs comptes ne s'additionnent pas.


## G234 — Projection de l'index et contrat réel

Memory testé : `274c3fc6ce95434f6fc759eb9a1cb4c6c211dabf`.
Core épinglé dessus : `833fea3d3041bf80a214045c4c7f8f64797c7d89`.
[Rapport et matrice des 19 scénarios](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/29f9c7bde2e9eec517d5b9898c6d6c017172bc06/docs/G234-PROJECTION-CONTRACT-2026-10-14.md).

Le descripteur Qdrant et les points vérifiés identifient la projection réelle :
contenu entier de l'Information, pas passages. Une projection inconnue, un ancien
schéma ou un modèle incompatible est refusé avant la récupération du journal.
Un changement pendant l'embedding ne permet plus de réétiqueter le descripteur.
Une mutation canonique dans l'autorisation est détectée avant l'écriture ; une
incompatibilité en cours de page ne fait plus avancer le curseur au-delà de la ligne.

**Compatibilité : le schéma 1 nécessite un nouvel alias et une reconstruction
explicite**, puis de nouveaux checkpoints. Aucun ancien index n'a été modifié.
Le rapport décrit la procédure préparatoire ; elle reste à qualifier sur serveur.

32 nouveaux cas ; 28 échecs démontrés avant fonctionnalité et deux régressions
complémentaires reproduites avant correction. Après correction, 247 tests ciblés
passent localement avec -W error. Les 32 sont inclus dans ce compte.

| Validation publiée | Résultat |
| --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38638977007) | **2502 tests et 12 sous-tests réussis**, 92,34 s |
| Worker expérimental, même workflow | **19 réussis**, 1,01 s ; distinct du pipeline réel |
| [Qdrant et workers](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38638976951) | **247 réussis**, 13,25 s |
| [Core avec Memory G234](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38639019833) | **1763 tests et 1299 sous-tests réussis, 7 ignorés, aucun avertissement pytest**, 308,59 s |

Les sept exclusions concernent numpy/ONNX/OpenCV et les modèles d’identité
optionnels. Les avertissements Node des actions GitHub sont distincts de pytest.
Les comptes se chevauchent et ne s’additionnent pas.

La matrice relie chaque scénario historique aux essais du vrai chemin local et
signale les écarts : revue DELETE séparée, absence de délai WAIT/CLOSE_ABANDONED,
et gardes par intention au lieu de preview/preflight. **Le contrat historique
complet n'est pas déclaré qualifié.** Les 19 tests avec doubles restent inchangés.
La relecture Claude est demandée et lancée par toytoy ; aucun retour nouveau reçu.

Suite : consolider le contrat réel avec la contre-revue, raccorder l'hôte et
qualifier serveur Qdrant/corpus/modèles réels, puis VM/PC. MCP indisponible au dernier
constat ; aucune activation runtime, suppression ou fusion main. Les sections
suivantes conservent les résultats historiques, sans additionner leurs comptes.


## G233 — Arriérés et orchestration, suite de 22 h 36

Memory publié : `53f7bf01a811f65a418d1f07cb42b9734f585213`.
[Rapport, API et limites](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/26976e3de795b0cd184e3abbac3536517857cb50/docs/G233-INDEX-MAINTENANCE-2026-10-14.md).

Les deux étapes prévues après G232 sont implémentées. Le worker parcourt les
arriérés par séquence, avec borne fixe ; les intentions à revoir n’empêchent
plus les lignes saines suivantes d’être traitées. L’ancien run_once conserve
son refus des listes tronquées. Un Markdown malformé est maintenant conservé
en revue au lieu d’interrompre le parcours entier.

Le cycle IndexMaintenance relie les deux passages du worker, le scanner canonique,
le scanner inverse et le bilan, avec checkpoints durables. Il conserve les revues,
reprend après coupure et diffère le travail selon fenêtre, inactivité, délai après
démarrage et charge fournie par l’hôte. Une bascule de génération impose un nouveau
cycle. Une saturation de revues se termine par REVIEW_REQUIRED, sans clôture forcée.

246 tests ciblés passent avec -W error, puis 40 cas G233 finaux. Preuves : arriéré de
1005 revues avec lignes saines en fin de file, arrêt réel après effet du worker et
avant checkpoint du contrôleur, reprise sans nouvel embedding, cycle périodique
retrouvant un nouveau document. CI Memory et Core confirmées.
Core testé : `59cb703f29527e66f15e627586350a97e7b9f1ea`, épinglé sur Memory ci-dessus.

| Validation du code publié | Résultat |
| --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38635265838) | **2470 tests et 12 sous-tests réussis**, 125,77 s |
| Worker expérimental, même workflow | **19 réussis**, 1,35 s ; contrat distinct du cycle G233 |
| [Qdrant/worker/scanners/maintenance](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38635266047) | **215 réussis**, 8,90 s |
| [Core avec Memory G233](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38635366123) | **1763 tests et 1299 sous-tests réussis, 7 ignorés, aucun avertissement pytest**, 397,33 s |

Les sept tests ignorés nécessitent numpy, ONNX ou OpenCV et les modèles d’identité
optionnels. Les avertissements Node des actions GitHub sont distincts de pytest.
Aucun échec. Les lots se chevauchent : leurs comptes ne s’additionnent pas. Les
commits documentaires ultérieurs ne changent pas le code qualifié.

L’API exécute une étape par appel ; aucun service permanent n’est activé. Les
observations d’activité/charge/démarrage et les appels sont à raccorder explicitement
à l’hôte de production. CYCLE_COMPLETE décrit le travail observé, pas une preuve
permanente de synchronisation distribuée.

Suite J2 : contrat historique complet et identité du découpeur, contre-revue,
raccordement hôte et qualification serveur/corpus/modèles réels, coût des verrous,
puis recette VM/PC. La suppression effective reste désactivée. Les lots suivants
sont conservés comme preuves historiques.


## G232 — Inventaire inverse, suite de 21 h 32

Memory publié : `e4d38ee3d4b56ec0a24ddec9939b2466ec5b9af4`.
[Rapport et limites](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/0c23815fd25ceefa69614e06fc89c0466d52fdf8/docs/G232-ORPHAN-REVIEW-2026-10-14.md).

Inventaire paginé d’une génération Qdrant concrète, checkpoint atomique page/curseur,
absence canonique vérifiée par descripteur. Les points étrangers ou malformés ne
sont pas masqués par un filtre. Les points historiques sans provenance restent
à revoir et ne deviennent pas candidats à la suppression.

La revue relit absence, droits, intentions et preuve complète du point. Un document
réapparu, une nouvelle intention ou un point modifié écartent le candidat ; une
bascule de génération impose un nouveau passage. Aucun DELETE n’est exécuté ou
enregistré dans le journal. Le checkpoint conserve des observations, pas des
permissions de suppression.

44 nouveaux tests réussis avec `-W error` ; 185 tests ciblés réussis avant le dernier
contrôle de non-mutation. Deux arrêts réels de sous-processus avant/après commit
prouvent la reprise sur SQLite/Qdrant local sur disque. Les trois CI finales ont réussi.
Core `dd8b3245b0aca937f53e176d24e9fa21649a4793` est épinglé sur cette révision Memory pour sa suite d’intégration.

| Validation du code publié | Résultat |
| --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38625545805) | **2430 tests et 12 sous-tests réussis**, 98,74 s |
| Worker expérimental, même workflow | **19 réussis**, 1,16 s ; contrat distinct du scanner/consommateur |
| [Qdrant/worker/scanners ciblés](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38625545759) | **175 réussis**, 7,61 s |
| [Core avec Memory G232](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38625669151) | **1763 tests et 1299 sous-tests réussis, 7 ignorés, aucun avertissement pytest**, 447,42 s |

Les sept tests ignorés nécessitent numpy, ONNX ou OpenCV et les modèles d’identité
optionnels. Les avertissements Node des actions GitHub restent distincts de pytest.
Aucun échec. Les lots se chevauchent : leurs comptes ne s’additionnent pas. Les
commits documentaires ultérieurs ne changent pas le code qualifié.


EXHAUSTED signifie fin du curseur, pas instantané global : les ajouts derrière
le curseur nécessitent un passage périodique supplémentaire. La latence réseau
sous verrou doit être mesurée sur le serveur réel.

Suite J2 : consommation paginée des gros arriérés sans famine derrière les intentions
à revoir, puis orchestration des scans/worker et politique de revue, contrat historique
complet, serveur/corpus/modèles réels et recette VM/PC. L’exécution des suppressions
reste désactivée. Les lots suivants sont conservés comme preuves historiques.


## G231 — Balayage reprenable, suite de 21 h 08

Memory publié : `855a9eb325a306543afdf7a703fb8b37ec739c9b`.
[Rapport et limites](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/bef722294aa5ac7481e851218a18b8e743845a9c/docs/G231-RESUMABLE-SCAN-2026-10-14.md).

Le scanner retrouve les upserts canoniques absents du journal, en pages avec
checkpoint SQLite. Les inventaires initial/final détectent les modifications
derrière le curseur ; une coupure après commit du journal ne crée pas de doublon.
Une file pleine suspend le parcours au document concerné, puis la reprise suit
le traitement ou la revue du journal. Aucun point Qdrant n'est écrit par le scanner.

33 nouveaux tests passent avec `-W error` ; 146 tests ciblés ont également passé
avant le dernier cas de checkpoint. Suite complète locale avant ce dernier cas :
2379 réussis, 12 sous-tests, 6 échecs AF_UNIX connus. Ces six cas passent ensuite en CI Linux.
Core `066f128650554b5c803c57e15eb9c3f126cf299d` est épinglé sur la nouvelle révision Memory pour sa suite d'intégration.

| Validation du code publié | Résultat |
| --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38622854670) | **2386 tests et 12 sous-tests réussis**, 96,01 s |
| Worker expérimental, même workflow | **19 réussis**, 1,24 s ; contrat distinct du scanner/consommateur |
| [Qdrant/worker/scanner ciblés](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38622854503) | **131 réussis**, 9,20 s |
| [Core avec Memory G231](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38622998001) | **1763 tests et 1299 sous-tests réussis, 7 ignorés, aucun avertissement pytest**, 456,96 s |

Les sept tests ignorés requièrent numpy, ONNX ou OpenCV et les modèles d’identité
optionnels. Les avertissements Node des actions GitHub sont distincts de pytest.
Aucun échec ; les lots se chevauchent et leurs comptes ne s’additionnent pas.
Les commits documentaires ultérieurs ne changent pas le code qualifié.


Les captures initiale/finale lisent toute la collection sous verrou, avec budgets
d'entrées/octets ; les pages seules sont limitées à 100 documents par défaut.
COMPLETE décrit le passage canonique, pas la synchronisation finale de l'index.
Un nouveau passage périodique est explicitement demandé par `restart=True`.
Le journal dessert une seule configuration d’indexation active ; des index
indépendants nécessitent des journaux dédiés.

Suite J2 : inventaire inverse des points orphelins et absence prouvée, orchestration
scanner/worker, contrat historique complet, serveur Qdrant réel et coût sur le
corpus réel. La recette VM/PC reste dépendante des accès. Les lots ci-dessous sont
conservés comme preuves historiques.

## G230 — Suite du 14 octobre après 19 h 55

**Publication et qualification terminées** : Memory `180f3a7`, Core `e7cba2b`.
Les commits documentaires suivants ne changent pas le code testé.

| Validation | Résultat |
| --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38611998863) | **2353 tests et 12 sous-tests réussis**, 258,42 s |
| Worker expérimental, même workflow | **19 réussis**, 1,84 s ; contrat distinct du nouveau consommateur |
| [Qdrant/worker ciblés](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38611998817) | **98 réussis**, 2,59 s |
| [Core avec Memory G230](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38612137486) | **1763 tests et 1299 sous-tests réussis, 7 ignorés, aucun avertissement pytest**, 286,59 s |

Les sept tests ignorés nécessitent les moteurs/modèles d'identité optionnels.
Les huit avertissements `fork` de G229 ont disparu. Les avertissements Node des
actions GitHub restent distincts de pytest. Aucun échec ; lots chevauchants,
comptes non additionnables.

Memory publié : `180f3a72064636964e718e2d81e88e198aeac01f`. Consommateur borné du
journal raccordé au worker verrouillé, reprise après accusé perdu/arrêt du processus
sans ré-embedding, transitions conditionnelles SQLite et vérification durable
avant récupération d'INTENT. Planification avec digest/modèle/génération disponible.
[Rapport Memory](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/180f3a72064636964e718e2d81e88e198aeac01f/docs/G230-JOURNAL-RECOVERY-2026-10-14.md).

38 nouveaux tests passent ; une reprise après arrêt réel est vérifiée sur Qdrant
local sur disque. Suite complète locale : 2346 réussis, 12 sous-tests, 6 échecs
AF_UNIX connus, avant l'ajout du dernier test interprocessus. Les six échecs passent ensuite en CI Linux.

Core : `spawn` remplace le `fork` résiduel dans la sonde du registre ; 44 tests
et 18 sous-tests ciblés réussis avec `-W error`. La CI complète est épinglée
sur la nouvelle révision Memory et a réussi. Aucun runtime ou service n'est activé.

J2 reste ouvert : inventaire/pagination, couverture intégrale des 19 scénarios,
coordination alias/droits et recette du serveur Qdrant réel. L’inventaire existant
`build_manifest` lit toute la collection : son raccordement périodique doit réutiliser
le lecteur par descripteur et définir une reprise qui ne perd aucun document
modifié entre deux pages. Les résultats G229
ci-dessous restent des preuves historiques sur les anciens SHAs.

## Décision et périmètre

Toytoy a validé à 18 h 18 Europe/Paris cet ordre : cohérence Memory/Qdrant,
intégration Core, qualification, bilan, puis recette VM/PC. Claude annoncé
à nouveau disponible vers **22 h 58** ; cela ne programme ni ne lance une session.
Pas de fusion main, déploiement VM ou modification du corpus réel.

## État par composant

| Composant | État du code | Limite restante |
| --- | --- | --- |
| Core dialogue/missions/SOUL/autorisations | Intégrés dans la branche de développement | Modèle réel et recette intégrée VM/PC |
| Memory canon/journal | Implémentés et testés en isolation | Coordination journal/index et reprise multi-services |
| Worker Qdrant | Verrou et preuve complète G229 ; consommation bornée du journal et reprise G230 | Contrat complet de 19 scénarios sur le chemin réel, réconciliation et serveur réel |
| Dashboard Claude jusqu'à C178 | Fusion publiée, historique conservé | Vraie recette Windows |
| Monitoring Memory distant | Module intégré dans la branche publiée | Provisionnement SSH privé et recette VM non faits |
| GPU dashboard | Contrat et rendu sur exemples intégrés | Collecteur réel non raccordé par ce lot |
| Voix/vision | Services existants ; lexique et prononciation Claude intégrés | Micro/caméra physiques et contention GPU |
| Identité | Prototypes, adaptateurs et simulateur intégrés | Aucun droit accordé, aucun capteur ni modèle activé |
| Recherche Web et index documentaire | Prototypes optionnels intégrés, hors runtime par défaut | Politique/budgets durables et recette réseau |
| Image/vidéo | Modules, adaptateurs et parcours de préparation existants | Moteurs/configuration et recette de bout en bout |

## G229 — intégration de Claude

Base Core : `bb3bef6fc933f5482582418e0e3a35087e411bf4`.
Branche Claude intégrée : `2b52d8c31f58c62b8ea4afe0e440196dc9b07eed`.
Les 90 commits propres à Claude sont intégrés par une fusion à deux parents ;
les 31 commits Core postérieurs à leur ancêtre commun restent conservés.
Aucun conflit source. Un conflit documentaire introduit par notre déclaration
G229 dans ECHANGES a été résolu en conservant les deux contributions.
Le bundle JavaScript régénéré est identique au bundle fourni par Claude.

Les derniers I1/W1 Core sont conservés. Deux sondes historiques Claude ont été
actualisées : W1 n'est plus un échec attendu ; I1 vérifie la fraîcheur calculée
et le refus d'une étiquette imposée par l'appelant. Le test d'arrêt HTTP capture
explicitement la déconnexion attendue, joint son thread et ferme la connexion.
Les tests de registre emploient spawn plutôt que fork dans un processus multithread.

## Historique G229 — Qualification GitHub Actions sur les commits publiés

| Suite | Révision testée | Résultat |
| --- | --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38600958582) | `d74d772` | 2315 tests et 12 sous-tests réussis, 93,51 s |
| Worker expérimental (même exécution) | `d74d772` | 19 scénarios réussis, 1,47 s ; ne clôture pas le contrat réel |
| [Qdrant ciblé](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38600958856) | `d74d772` | 60 tests réussis, 1,52 s |
| [Core complet avec intégration Memory](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38601095316) | `ff0b65e` + Memory `d74d772` | 1763 tests et 1299 sous-tests réussis, 7 ignorés, 8 avertissements, 281,55 s |

Les lots se chevauchent : ne pas additionner leurs comptes. Aucun échec dans ces workflows.
Les six intégrations Memory sont activées et les dépendances de sauvegarde sont présentes.
Les sept tests Core ignorés nécessitent numpy, ONNX ou OpenCV et des modèles d'identité.
Les huit avertissements pytest proviennent du `fork` restant dans
`test_profile_registry_probes.py::RegistryProbes::test_eight_concurrent_imports_publish_exactly_once` ;
ce fichier distinct du registre déjà corrigé devra aussi passer à `spawn`.
Les actions checkout/setup-python émettent en outre des avertissements Node 20/24.
Ces avertissements sont enregistrés, pas supprimés par filtrage.

## Historique des preuves locales

- Memory G229 : 66 tests ciblés réussis, dont trois régressions reproduites avant correction. Rejeu complet final sur le code `556443c` : **2309 réussis, 12 sous-tests, 6 échecs liés aux sockets interdites**, 86,05 s. Ces six scénarios passent désormais dans la CI publiée ; aucun n’a été masqué.
- Core après fusion, première suite locale : **1699 réussis, 51 ignorés, 1 xfail, 21 échecs, 1 avertissement**, 1288 sous-tests, 264,20 s. Vingt échecs sont liés aux sockets AF_UNIX interdites dans l'environnement ; le dernier est un succès inattendu du test W1 encore marqué expectedFailure. Cette suite n'est PAS verte.
- Rejeu après correction des sondes I1/W1 et du test HTTP : **57 réussis, 24 sous-tests, aucun avertissement**, avec `-W error`. Inclut les six intégrations contre le véritable code Memory sur corpus synthétique.
- Autre lot ciblé registre/identité/index documentaire/activation monitoring : **65 réussis, 18 sous-tests**, `-W error`.
- JavaScript connecté : **139 réussis, 26 ignorés**, aucun échec ; les essais Chromium sont ignorés faute de moteur disponible. Ce n'est pas une recette visuelle Windows.
- Les comptes se chevauchent : ne pas les additionner.

La CI Core a lu Memory au commit exact
`d74d772be25fe7d0e266711f58fba44248ba412a` et exécuté les six intégrations
au lieu de les ignorer. Les dépendances age/OpenSSL/FFmpeg restent installées
par la CI ; age est absent localement (45 tests de sauvegarde ignorés).
Les six autres skips locaux sont des moteurs d'identité optionnels absents.

## Publication et recette

Le contrôle automatique avait refusé la première publication faute de confirmation
explicite. Toytoy l'a donnée à **18 h 44 Europe/Paris**. Les deux branches de
développement sont publiées, avec des arbres identiques aux fichiers préparés :

- Memory : `d74d772be25fe7d0e266711f58fba44248ba412a`.
- Core : `ff0b65e0caf700ff99524611495e09106b6f3240`, avec les parents
  `bb3bef6` (Core) et `2b52d8c` (Claude C178).

**J2 reste ouvert**. J3 exige B01–B12 sur VM/PC ; J4 est la décision de bêta.
L'indisponibilité MCP bloque la recette distante, pas l'analyse du dépôt.

## Suite prioritaire

1. Terminer J2 : contrat réel, reprise journal/index, contrôle de dérive à révision égale.
2. Contre-revue indépendante Claude du lot G229 et de l'intégration (fiche dédiée).
3. Restaurer MCP puis exécuter B01–B12 avec sauvegardes et SHAs figés.
4. Entretien CI : mettre à jour les actions Node ; suppression du `fork` résiduel validée en G230.

Les anciens rapports sont conservés comme preuves datées, sans réécriture rétroactive.
