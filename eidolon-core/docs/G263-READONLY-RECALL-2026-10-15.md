# G263 — Préparer le rappel pour le compte dédié

Auteur : Codex/GPT, 15 octobre 2026. Reprise demandée par toytoy après G262.

Memory publié : `86950c87fbff54169010042fa1e8887c9bf7465e`, parent `795784a`. [Contrat complet, tests et limites](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/86950c87fbff54169010042fa1e8887c9bf7465e/docs/G263-READONLY-STORAGE-2026-10-15.md). Core modifie uniquement le pin CI et la coordination/documentation dans ce lot.

Le mode explicite `--read-only-storage` permet le rappel sans ouvrir le verrou en écriture ni créer les répertoires. Les verrous existants sont toujours exclusifs et partagés avec les écrivains. Rien n'est déplacé. Les sources Linux locales sont couvertes ; le montage systemd cible, les UID réels du service et le cache reranker restent à qualifier. Les valeurs par défaut restent inchangées.

25 nouveaux tests réussis, 1 ignoré (runtime root) ; 117 tests ciblés et 5 sous-tests réussis au total. Scénarios : rappel simple/projet avec EROFS injecté, HTTP réel, pertes de verrou, fichiers spéciaux/liens, remplacement à l'acquisition, préflight avant écoute, réentrance, exclusivité interprocessus et reprise. Pas de véritable montage readonly exécuté dans ce runtime. Le test chmod sous UID ordinaire doit être exécuté en CI.

Les dix G262 restent attribuées à Claude ; aucun retour après C187 observé sur sa branche 70fc0c6 au début de ce lot. G263 rend leur contre-revue de production possible sans annuler les expériences demandées. [Coordination](../collaboration/GPT-TO-CLAUDE.md).

Publication déjà autorisée dans la session sur les branches de développement. Aucun compte créé, aucune migration, aucun déploiement/main/benchmark G182. Résultats complets CI à ajouter après exécution sur les SHA publiés.

## Résultats Memory confirmés

Source `86950c87fbff54169010042fa1e8887c9bf7465e` ; bilan final publié en `a25a41da815cac2fea908d5336633a205ac7946f` (documentation seulement).

| Validation | Résultat | Preuve |
| --- | --- | --- |
| Memory complet | 2922 réussis, 18 ignorés, 4 xfail, 12 sous-tests ; 181,32 s | [38736188196](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38736188196), job 116425965057 |
| Worker | 52 réussis ; 2,90 s | même workflow |
| Qdrant isolé | 550 réussis, 1 xfail ; 32,50 s | [38736188211](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38736188211), job 116425965248 |
| Qdrant 1.15.4 réel jetable | 18 réussis ; 59,96 s | [38736188225](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38736188225), job 116425965226 |

Les 26 nouveaux cas G263 réussissent en CI, y compris les permissions chmod sous UID ordinaire. Les 18 exclusions de la suite générale sont les scénarios serveur, tous verts dans leur workflow dédié. Quatre xfail historiques maintenus, comptes chevauchants. Cela ne qualifie pas un montage readonly systemd de production.

## Qualification Core finale

Source **`aacf51f29ffda4e1d0a2d3453861b74e79496949`**, pin Memory `86950c87fbff54169010042fa1e8887c9bf7465e`. [Workflow 38736453469](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38736453469), job 116426862253 : **succès**.

- Suite complète : **1991 réussis, 8 ignorés, 1328 sous-tests**, 349,95 s.
- Propriétaires de jetons sous vrais changements d'UID : **5 réussis**, 0,08 s.
- Bundle et tests Node : **160 réussis**, 36 cas navigateur ignorés dans ce job sans Chromium, aucun échec/todo. Le code client n'a pas changé dans G263 ; pas de nouvelle exécution Chromium revendiquée. La preuve G262 reste 202 réussis sans exclusion sur 70fc0c6.

Les huit exclusions Python restent celles de la source précédente : dépendances/modèles optionnels (six) et scénarios propriétaires (deux, couverts par l'étape root). Quatre workflows G263 déclenchés et verts, les comptes se chevauchent. Aucun échec accepté comme succès. Les limites de montage réel, cache et compte dédié restent inchangées.
