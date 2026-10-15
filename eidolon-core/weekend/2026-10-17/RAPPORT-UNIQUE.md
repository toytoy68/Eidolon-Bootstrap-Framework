# Eidolon — rapport unique de préparation du week-end

**15 octobre 2026 — Codex/GPT — week-end des 17–18 octobre.**

Le dossier PC/VM est préparé et les principaux raccordements Memory ont été développés hors VM. Il s'agit d'une **candidate de recette**, pas d'une bêta déclarée opérationnelle. Aucun fichier n'a été installé sur ton PC ou tes VM pendant ce travail.

## Livraison

Le ZIP de livraison regroupe les sources Core et Memory à deux commits exacts, les tests, les configurations exemples, les inventaires, les procédures et le formulaire de preuves. `MANIFEST.json` inventorie chaque fichier avec SHA-256 ; le fichier SHA256SUMS livré à côté permet de contrôler l'archive. Le générateur refuse un fichier de sortie existant et ne lit que les objets Git des commits choisis.

- **Sources Core qualifiées :** `35f45a0a5f112183694c371b6a5adbd78cd35778`, branche `feat/eidolon-core-v0.1`. La publication finale du présent rapport ne change pas ce code.
- **Memory :** `c6a77631d75f96a31b3a1c291ad462ee9f94c0ea`, branche `refactor/architecture-v1`. La CI Core épingle exactement ce commit.
- **Claude :** C191 intégré, parent `c8c585bd8c64f056cb69e6a0ed3f61a309a8e204` conservé dans l'historique Core ; patch 0067 appliqué sans modification à Memory, attribution et original conservés.
- **Point d'entrée :** [README.md](README.md), puis [RECETTE.md](RECETTE.md). Les chemins/hôtes/comptes réels sont à renseigner dans [MACHINE-INVENTORY.md](MACHINE-INVENTORY.md).

Le paquet contient des sources, pas les dépendances Python, modèles, données, secrets ou un exécutable Windows. Les journaux historiques sont exclus. Les tests ciblés fournis sont exécutables depuis le paquet ; certains anciens tests documentaires nécessitent le dépôt Git complet. Le caractère reproductible concerne les octets de l'archive, pas encore un environnement VM entièrement verrouillé.

## Développement effectué

| Travail | Résultat vérifié hors VM | Limite à conserver |
| --- | --- | --- |
| Corrections C191 | Inventaire DFS borné en descripteurs, refus explicite en cas de ressources insuffisantes ; 35 sondes d'usage CLI Memory reçues | L'inventaire reste non atomique ; corpus arrêté requis |
| Pont Memory → Qdrant | Option `--index-config`, alias existant, descriptor compatible, relecture canonique ; erreur explicite si l'index choisi est indisponible | Pas de repli lexical silencieux ; défaut lexical inchangé sans option |
| Embeddings locaux | Ollama CPU, modèle/digest et dimensions contrôlés, prétraitement requête/document distinct, identité stable dans l'index | Aucun téléchargement ; pertinence et latence réelles à mesurer |
| Passages d'archives persistants | Adapter Qdrant séparé, positions canoniques, reconstruction en génération distincte et bascule après vérifications ; assertion G201 Q1 devenue verte | Reconstruction complète seulement, un passage retenu par document, budget candidats en passages |
| Mémorisation explicite | CLI avec aperçu, validation de l'empreinte exacte, journal métier existant, rejeu idempotent et conflit si la commande change | Parcours opérateur ; pas encore le bouton « retenir ceci » dans le chat |
| Maintenance hôte | Politique/lecteur de Claude adoptés avec attribution ; collecte charge/boot, check-only et un tick explicite, liste d'identifiants autorisés | Activité humaine jamais déduite de la charge ; pas de producteur de reçus automatiquement raccordé |
| Dossier PC/VM | Inventaires, exemples JSON, brouillons systemd, recette ordonnée, rollback et 26 cas à renseigner | Aucun service/compte activé ; PowerShell et périphériques physiques non exécutés ici |
| Qualification documentaire | Vérificateur des résultats refusant lignes manquantes, statuts inconnus et PASS sans preuve datée | Même complet, le document ne donne aucune autorisation automatique de bêta |

Les fichiers de maintenance ciblent l'index **documentaire**, avec un alias distinct. L'index de **passages** refuse les opérations du worker incrémental. Les générations échouées et anciennes sont conservées pour revue ; aucune suppression automatique n'a été ajoutée.

## Vérifications réellement exécutées

| Campagne | Résultat | Preuve |
| --- | --- | --- |
| Memory complet, Python 3.13 CI | **3146 réussis, 25 ignorés, 3 xfail, 12 sous-tests** | [Run 38771217927](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38771217927) |
| Worker journal réel sur données isolées | **52 réussis** | Même run, étape dédiée |
| Qdrant ciblé, en mémoire | **550 réussis, 1 xfail** | [Run 38771217742](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38771217742) |
| Serveur Qdrant jetable 1.15.4 | **18 réussis** | [Run 38771217799](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38771217799) |
| Chromium, client inchangé par la correction finale du générateur | **205 réussis, aucun ignoré** | [Run 38772321671](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38772321671), source Core 4e219fa |
| Core complet, Python 3.13 CI | **2192 réussis, 8 ignorés, 1328 sous-tests** ; propriétaires root **5 réussis** | [Run final 38772571847](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38772571847), source Core 35f45a0 |
| Tests ciblés depuis le ZIP extrait | **37 Memory + 12 Core réussis** | Exécution locale sur le contenu du candidat, `-W error` |
| Contrôles CLI du dossier | `CONFIG_VALID`, `PREVIEW`, `CHECK_ONLY/NOT_EXECUTED`, `LAST_ACTIVITY_UNKNOWN` | Exécutés localement ; aucun service externe interrogé |
| Formulaire de recette initial | **26 NOT_RUN, INCOMPLETE**, code 1 | Résultat attendu ; aucune preuve PC/VM inventée |

La CI Core ignore six essais de dépendances/modèles biométriques absents et deux essais nécessitant root, ces deux derniers étant couverts par l’étape propriétaires séparée. Les tests Node de son job standard donnent 161 réussis et 38 ignorés faute de navigateur ; la campagne Chromium distincte couvre le navigateur avec 205 réussites sans exclusion.

Les comptages se recouvrent : ne pas les additionner en un nombre de tests uniques. Dans la CI Memory complète, 18 cas de serveur sont couverts par le job serveur distinct ; les sept essais de montage privé restent ignorés faute de capacités. Les trois xfail restants concernent des contrats historiques distincts (rétention des générations, ancienne surface administrative, retard d'index historique) ; ils ne sont pas présentés comme résolus.

La campagne locale complète avait cinq échecs Memory liés aux sockets Unix interdites et un stub de serveur à adapter à sa fermeture désormais explicite. Le stub a été corrigé et les tests ciblés repassés ; la CI complète est verte. Les 22 échecs Core locaux relevés dans cette campagne relevaient des restrictions sockets Unix/changement de propriétaire ; la CI sur UID ordinaire et l'étape root contrôlent ces cas. Aucun contournement ni suppression de test n'a été utilisé pour masquer ces limites.

## Ce qu'il reste à faire, par priorité

| Priorité | Travail restant | Dépendance |
| --- | --- | --- |
| **P0 — samedi, avant adoption** | Relever installations/ports/comptes, sauvegarder et restaurer une copie, contrôler modèles/caches/digests, exécuter check-storage sous le compte réel | Accès VM et inventaire effectif |
| **P0 — samedi** | Qualifier montage readonly, exception du verrou stable pour la maintenance, autorisations et compte de service C187 | Décision de compte + essais UID/montage réels |
| **P0 — samedi** | Reconstruire un alias de passages de recette, raccorder Core, tester citations/paraphrases/hors sujet, indisponibilités et délais | Modèle, Qdrant et copie du corpus réel |
| **P0 — développement restant** | Raccorder « retenir ceci » au chat avec identité/autorisation et reçu de bout en bout ; produire les reçus d'activité Core authentiques | Travail logiciel encore ouvert, pas simplement bloqué par les VM |
| **P0 — dimanche** | Micro/casque/webcam, permissions, tunnel, mise à l'échelle, reprise après coupure et mesures de ressources | PC Windows et périphériques physiques |
| **P0 — dimanche** | Reprise de maintenance, restauration, endurance, redémarrage et rollback ; décision go/no-go sur preuves | VM/PC et durée d'observation réelle |
| **P1** | Incrémental des passages ; branchement complet du Web autorisé, profils actifs et isolation mémoire ; fichiers Windows/NAS et application résidente | Développement et choix d'intégration, puis recette sur les environnements réels |
| **P2** | Moteurs média/GPU avancés, biométrie complète, rétention automatisée, DARME avancé, mobile/robot/Eidolon OS | Hors de ce lot de préparation ; ne pas les confondre avec des tâches terminées |

Ce lot ne clôt donc **pas tout le backlog hors VM**. Il livre les raccordements prioritaires ci-dessus sous forme testée et transférable, et distingue les développements encore ouverts des validations impossibles sans machines réelles. La CLI opérateur n'est pas présentée comme un parcours conversationnel complet ; le collecteur n'est pas présenté comme une maintenance automatique installée.

## Ordre conseillé sur place

1. Contrôler le ZIP, l'inventaire et la sauvegarde restaurée.
2. Qualifier le stockage et le rappel sur copie, puis la mémorisation synthétique.
3. Qualifier un tick documentaire et sa reprise, en conservant les checkpoints et les preuves.
4. Faire la recette Windows réelle et l'endurance.
5. Examiner les 26 résultats, les réserves et le rollback avant toute adoption des candidats.

Les exemples de seuils/ports sont des propositions à revoir. Aucun accès VM, transfert sur machine, création du compte C187, activation de service, migration, suppression, fusion main ou relance du benchmark G182 n'a été effectué. [ROLLBACK.md](ROLLBACK.md) décrit la marche arrière sans écrasement des données courantes.
