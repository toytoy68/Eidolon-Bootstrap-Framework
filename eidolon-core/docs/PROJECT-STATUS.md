# Eidolon — État consolidé du dépôt

Mise à jour : 15 octobre 2026, lots G236–G238, Codex/GPT.

**MT1/MT3 et R1 corrigés et qualifiés dans Memory. Dix tâches confiées à Claude ; recette serveur jetable en cours, MCP toujours indisponible.**

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
