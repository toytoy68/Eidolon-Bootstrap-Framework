# Patchs Claude pour Eidolon Memory Engine (G178)

Claude a reçu l'accord de toytoy pour travailler dans Memory (12/10/2026, vers 14 h 20).
Sa session peut **lire** le dépôt `toytoy68/Eidolon-Memory-Engine`, mais pas y pousser :
l'attache en écriture a été refusée par les permissions de la session. Les commits
sont donc livrés ici sous forme de patchs `git format-patch`, à appliquer par Codex
ou à pousser dès que l'accès en écriture est accordé.

**Base** : `41854309ab212d5d732cbc7e8e551f2b4c11a08a` (ta livraison Qdrant G179, `refactor/architecture-v1`).
Les patchs 0001 à 0003, d'abord faits sur `f7136239`, ont été rebasés sans conflit.

```sh
git checkout -b claude/memory-g178 41854309ab212d5d732cbc7e8e551f2b4c11a08a
git am /chemin/vers/eidolon-core/collaboration/memory-patches/0001-*.patch   # puis les suivants, dans l'ordre
python3 -m pytest -q tests
```

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0001 | A5-02 : politique de passage v3, contexte gauche et marqueurs de négation signalés | 2 024 tests Memory réussis ; sonde d'audit du 05/10 : « Ne pas acheter la V100 cette semaine. » complet |
| 0002 | Corpus synthétique v1 (30 documents, 27 questions, 8 catégories), réponses figées **avant** toute exécution | SHA-256 figé par test |
| 0003 | Banc de rappel lexical : rappel@k, sources, abstention, latence ; comparaison avant/après A5-02 ; lecture des résultats | 2 027 tests Memory réussis ; résultats dans `docs/claude-memory-eval/README.md` (Memory, patch 0003) |
| 0004 | Contre-revue de l'adaptateur Qdrant G179 : sondes hors de tes fichiers, 3 écarts en `xfail` strict (Q2 migration de modèle, Q3 péremption invisible dans les résultats, Q4 empreinte devinable) | 2 054 tests Memory réussis + 3 xfail ; `docs/claude-memory-eval/QDRANT-REVIEW-G179.md` |

## Patch 0005 (G183, base `a9c8740453eaf8c99bcf89d39d11e018d3287244`)

Base différente des patchs 0001–0004, déjà intégrés par Codex en `03157fc`.

```sh
git checkout -b claude/memory-g183 a9c8740453eaf8c99bcf89d39d11e018d3287244
git am /chemin/vers/eidolon-core/collaboration/memory-patches/0005-*.patch
```

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0005 | Contre-vérification A5-02 v3 (12 000 cas aléatoires) et sondes du rappel canonique par index G181/G182 : 6 sondes vertes, 4 écarts en `xfail` strict (P1 à P4) | 2 112 tests Memory réussis + 4 xfail ; chaque xfail vérifié avec `--runxfail` |

## Patch 0006 (G186, base `533ac1d6cfd975dbcebf730d0a3f31b17a1f6e44`)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0006 | Contre-revue aléatoire des correctifs P1–P4 : couverture des morceaux et frontières base + accents (1 200 archives), extrait indexé fidèle, borné et marqueurs recomptés (9 000 références). Observation O1 en `xfail` strict | 2 134 tests Memory réussis avant patch ; sondes : 6 réussies + 1 xfail, vérifié avec `--runxfail` |

## Patch 0007 (G194, base `533ac1d6cfd975dbcebf730d0a3f31b17a1f6e44`)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0007 | Contre-revue G194 des candidats Qdrant dans le rappel canonique, sur Qdrant en mémoire et embedding synthétique. Vérifié : rappel lexical sans index, relecture canonique avec provenance, aucune synchronisation automatique, générations conservées. Écarts en `xfail` strict : Q1 pas d'abstention, Q2 archives exclues en mode index, Q3 génération orpheline après échec | 2 134 tests Memory avant le patch ; sondes : 4 réussies et 3 xfail, raisons vérifiées avec `--runxfail` |

## Patch 0008 (G201, base `533ac1d`, indépendant de 0007)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0008 | Jeu de **calibration** de 24 questions (8 directes, 8 paraphrases, 8 hors sujet), figé par SHA et **disjoint** du corpus de test v1. Cas d'acceptation en `xfail` strict pour les décisions G201 : signal `INDEX_STALE`/`INDEX_PENDING`, passages d'archive vérifiés depuis l'index de production, rétention sans génération orpheline | sondes Claude : 24 réussies et 6 xfail (avec 0007) ; raisons vérifiées avec `--runxfail` |

## Patch 0009 (G202, base `533ac1d`, **après 0008**)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0009 | Deux cas d'acceptation G202 : changement d'`embedding_id` refusé explicitement (vérifié), panne de Qdrant attendue comme état explicite `INDEX_UNAVAILABLE` (`xfail` strict : aujourd'hui `ConnectionError` sort du rappel) | `test_g201_contract_probes.py` : 2 réussis et 4 xfail ; raison vérifiée avec `--runxfail` |

## Patch 0010 (G204, base `8a3db5c`)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0010 | Contre-revue du journal d'intentions `change_journal.py` (fichier GPT non modifié). Vérifié : 4 processus concurrents, aucune intention perdue. Noté : lien symbolique suivi (J3), pas d'état final pour une intention abandonnée (J4), révisions non monotones acceptées (J5). `xfail` strict : J1 retour d'INDEXED à PUBLISHED par une écriture tardive ; J2 fichier créé selon l'umask (0644) | 2 154 tests Memory à `8a3db5c` ; sondes : 4 réussies et 2 xfail, raisons vérifiées avec `--runxfail` |

## Patchs 0011 et 0012 (G205, base `a631532`)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0011 | **Remplace 0010** sur `a631532` : il crée le fichier de sondes du journal dans sa version mise à jour. J1 à J3 deviennent des tests de non-régression : l'écrivain tardif est bloqué par `BEGIN IMMEDIATE`, et cette sonde **échoue sur l'ancien `8a3db5c`** ; fichier 0600 quel que soit l'umask ; lien symbolique et dossier partagé refusés ; fichier public existant refusé sans `chmod`. Nouveau : 6 processus créent le même journal en même temps sans rien perdre | 8 sondes réussies, 3 répétitions |
| 0012 | **Proposition G205-B**, en fonctions pures et sans E/S : `reconcile_plan` (SUPERSEDED, reprise PUBLISHED après un arrêt, ABANDONED seulement après un délai de grâce, alerte d'intégrité, rattrapage par manifeste), `compaction_plan` et `retirement_plan` | 8 tests ; suite Memory : 2 174 réussis et **1 échec qui vient de GPT** (`test_public_parent_is_rejected`, voir C170) |

## Patchs 0013 et 0014 (G206, base `bb48cfb`)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0013 | **Correctif de ma proposition intégrée** (`reconcile_plan.py`). Une absence doit être **prouvée** (`ABSENT`) ; un identifiant non lu est **inconnu** et ne fait qu'attendre (`WAIT`), sans jamais publier une suppression ni retirer de l'index ; valeurs canoniques validées avant toute décision ; nombre de lecteurs inconnu = génération gardée | 10 tests ; démonstration du défaut sur `bb48cfb` (un `DELETE` non lu passait en `MARK_PUBLISHED`) |
| 0014 | Sondes d'acceptation G206-B pour la migration du journal (contrat proposé : `created`/`updated`/`reason`, `close(seq, état, raison)` idempotent, refus depuis `INDEXED`, migration sans perte d'un journal au schéma actuel, clôtures concurrentes) | 5 `xfail` strict, tous pour la raison attendue (interface absente) |

## Patchs 0015 et 0016 (G209 à G211, base `fa03e09`, **dans l'ordre**)

0013 n'est plus à appliquer : `0e83573`/`30fb6ef` portent la même logique.

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0015 | Deux tests GPT corrigés (aucun code modifié). `test_stale_intent_may_be_closed_after_grace` abandonnait une intention dont le canonique n'était **pas lu** (`{}`) : il passe maintenant `ABSENT`. `test_rejects_unknown_schema_without_mutation` échouait avec l'umask 022 (refus sur permissions avant le contrôle de schéma) : fichier mis en 0600 d'abord | à `fa03e09` : ces 2 tests échouent (umask 022) ; avec 0015 : 11/11 |
| 0016 | Contre-revue G207-G209 (fichiers Claude). Tests fixés : migration sans perte et idempotente, clôture idempotente, 4 clôtures concurrentes, journal public ou lien refusé, M8 (canonique non lu jamais pris pour supprimé). `xfail` strict : M2 séquence réutilisée après compactage puis migration ; M4 nouveau journal encore en v1 ; M7 aperçu refusé à exactement `limit` ; M9 `CLOSE_ABANDONED` sans revue | suite Memory à `fa03e09` + 0015 + 0016 : **2 188 réussis**, 4 xfail, 0 échec |

## Patchs 0017 et 0018 (G212, base `facf2e1`, **dans l'ordre** ; remplacent 0015 et 0016)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0017 | Réparation de tests GPT (aucun code). `tests/test_reconcile_preview.py` ne s'importait plus depuis `f44f84d` : deux lignes contiennent un `\n` littéral (erreur de syntaxe), donc **tout le fichier était ignoré**. Une fois importable, `test_reject_truncated_journal` utilisait une intention pour `limit=1`, ce qui est désormais (à raison) une limite exacte : deux intentions. Test de schéma de migration rendu indépendant de l'umask | à `facf2e1` : fichier en erreur de collecte, plus l'échec umask ; avec 0017 : 14/14 |
| 0018 | Sondes G212 : M2, M7 et M9 deviennent des tests de non-régression (ils passaient en `XPASS` strict) ; M2 aussi après compactage complet ; journal v1 : cycle complet utilisable, `close_terminal` refusé sans modification. `xfail` strict : M4 (journal neuf en v1) et **M10** : `preview(limit=1000)`, valeur acceptée par l'aperçu, lève toujours `invalid limit` car `pending()` plafonne à 1000 | suite Memory à `facf2e1` + 0017 + 0018 : **2 196 réussis**, 2 xfail, 0 échec |

## Patchs 0019 à 0021 (G214, base `9a77710` ; 0019 remplace 0016/0018, 0017 devenu inutile)

GPT a intégré lui-même les réparations de 0017 (`99eea30`, `41b3828`).

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0019 | Sondes journal v2 : M2, M7, M9 et M10 en non-régression (999 lignes acceptées, 1000 refusée d'emblée) ; ouverture d'une base v1 ou v2 **sans mutation** (schéma, `user_version`, lignes, `sqlite_sequence`) ; migrations répétées sans effet, lignes terminales et raisons conservées ; migration refusée sans changement pendant qu'un écrivain tient le verrou. `xfail` strict : **M4** (journal neuf en v1) et **M11** (fausse `INTEGRITY_ALERT` si une écriture arrive entre l'instantané canonique et la lecture du journal) | voir ligne suivante |
| 0020 | **Recette isolée du worker** : worker de **référence** (fichier de test, pas de production) et 12 scénarios : nominal et rejeu, canon illisible, absence prouvée (suppression seulement **proposée**), document réapparu, crash avant renommage, avant `published()`, entre `upsert` et `indexed()`, Qdrant indisponible puis rétabli, canon modifié après le plan, révisions rapides, profil sans droits, verrou occupé. Chaque garde vérifiée par sabotage (relecture, droits, suppression, relecture d'index retirés : les tests correspondants échouent) | 0019 + 0020 : suite Memory **2 213 réussis**, 2 xfail |
| 0021 | Sondes du découpage en passages (`passages.py`, non modifié). `xfail` strict **P1** : `verify_passage` ne compare que le texte ; un passage d'un autre document, d'une autre révision ou avec un faux `passage_id` est accepté | 0019 à 0021 + 0007 à 0009 : **2 224 réussis**, 10 xfail, 0 échec |

## Patchs 0022 et 0023 (G214 suite, base `36c8b8d` ; remplacent 0019 et 0020, avec 0021 inchangé)

Depuis `a04ea1c`, un journal neuf est créé directement en v2 : mes sondes construisent désormais un journal
v1 avec leur propre schéma d'origine, indépendamment de la fixture de GPT.

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0022 | Sondes journal : M4 devient non-régression ; un journal v2 natif et un journal v1 migré ont la **même forme** (colonnes, types, contraintes, index, états acceptés, état inconnu refusé). `xfail` strict : M11 (ordre de lecture de l'aperçu) et **M12** (`user_version` reste 0 pour un v2 natif, 2 pour un v2 migré) | voir ligne suivante |
| 0023 | Recette du worker étendue à la liste bloquante de `docs/G214-INDEX-WORKER-ACCEPTANCE.md` : accusé Qdrant perdu (jamais annoncé comme succès, rejoué une fois), canon modifié pendant le calcul des embeddings (pas marqué indexé), droits retirés entre plan et action, changement de modèle ou de découpeur (`INDEX_INCOMPATIBLE`, aucune écriture), journal tronqué, horloge reculée, deux workers concurrents. **19 scénarios** ; chaque nouvelle garde vérifiée par sabotage | 0021 + 0022 + 0023 sur `36c8b8d` : suite Memory **2 227 réussis**, 3 xfail (M11, M12, P1), 0 échec |

## Patch 0024 (P1 corrigé par GPT, base `e61f3d1` ; remplace 0021, avec 0022 et 0023 inchangés)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0024 | Sondes des passages sur `c8fdc21` : P1 devient non-régression (autre document, révision ou `passage_id` refusés) ; une contrefaçon qui **recalcule** l'identité est refusée quand `document_id` et `revision` de confiance sont fournis. `xfail` strict **P3** (faible) : ces deux arguments restent facultatifs ; l'identité est un hachage sans clé, donc une contrefaçon cohérente pour un autre propriétaire passe si l'appelant les omet | 0022 + 0023 + 0024 sur `e61f3d1` : suite Memory **2 230 réussis**, 3 xfail (M11, M12, P3), 0 échec |

## Patchs 0025 à 0027 (G217, base `c551d08`)

Ordre : **0025, 0023, 0026**, puis 0027 si tu retiens la proposition M11. 0025 remplace 0022 ; 0026
remplace 0024 ; 0023 (recette du worker, 19 scénarios) est inchangé.

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0025 | Sondes journal : M12 en non-régression (version 2 à la création seulement ; une base v1 existante garde 0, puis passe à 2 par migration) ; 6 processus créent le même journal neuf : schéma v2, version 2, 6 lignes. M11 : limite de la forme « dictionnaire » fixée, correctif par lecteur en `xfail` strict | voir 0027 |
| 0026 | Sondes passages : P3 en non-régression (`document_id` et `revision` obligatoires, nommés seulement) ; tous mes appels passent les métadonnées de confiance | — |
| 0027 | **Proposition M11** pour `reconcile_preview.py` (fichier GPT) : `canonical` peut être un **lecteur** `f(ids)` appelé **après** la lecture du journal. Une écriture qui arrive pendant l'aperçu donne `INDEX_UPSERT` ou `ENQUEUE_UPSERT`, jamais une fausse alerte. Forme dictionnaire inchangée ; aucune action, aucune suppression. Retire l'`xfail` M11 de 0025 | 0025 + 0023 + 0026 : **2 236 réussis**, 1 xfail (M11) ; + 0027 : **2 237 réussis, 0 xfail** |

## Patch 0028 (G218, base `372b093`)

GPT a intégré M11 (`372b093`, même logique que 0027) : 0027 n'est plus à appliquer.

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0028 | Partie test de 0027 seulement : la sonde « lecteur canonique après journal » devient non-régression. Ordre : 0025, 0023, 0026, 0028 | suite Memory à `372b093` : **2 237 réussis, 0 xfail, 0 échec** |

## Patchs 0029 à 0031 (G218, base `64c6ed1`)

Ordre complet sur `64c6ed1` : **0025, 0023, 0026, 0028, 0029, 0030, 0031**.

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0029 | Audit des plantages et des verrous : un processus enfant meurt (`os._exit`) à une instruction SQL précise. Plantage à chacune des 6 étapes de la migration : journal v1 intact (schéma, lignes, intégrité), puis migrable. Plantage pendant la création : fichier privé, réouvrable. 4 migrations concurrentes : une seule migre, aucune corruption. `xfail` strict **M13** : plantage entre `CREATE TABLE` et `user_version` = version 0 définitive | 10 réussis, 1 xfail |
| 0030 | Contrat du worker réutilisable : `EIDOLON_WORKER_FACTORY` choisit le worker testé ; le worker de référence passe par `worker_preflight` de GPT (`CLOSE_SUPERSEDED` en revue) ; notice `WORKER-CONTRACT.md`. Sabotages revérifiés | 19 réussis |
| 0031 | Sondes de caractérisation pour des passages dans Qdrant (voir l'étude Core `docs/proposals/2026-10-13-passages-qdrant-calibration.md`) | 4 réussis ; suite Memory complète **2 257 réussis, 1 xfail (M13), 0 échec** |

## Patchs 0032 à 0035 (G220, base `26976e3`)

Ordre sur `26976e3` : **0008, 0032, 0033, 0034, 0035**. GPT a déjà intégré la recette du worker (0023/0030) ;
0025 à 0031 sont regroupés dans 0032 pour cette base.

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0032 | Sondes journal, plantages et passages rafraîchies ; **M13 corrigé** (`975ca6c`) : sa sonde devient non-régression | — |
| 0033 | Contrat contre le **vrai** worker `JournalUpsertWorker` (Markdown réel, Qdrant en mémoire) : révisions rapides, écriture jamais renommée, droits retirés et canon modifié sur le chemin de reprise, aucune suppression ; séparation attente/revue/refus. **Tue deux mutants** qui survivent aux 26 tests GPT | 9 réussis |
| 0034 | Jeu `dev-calibration-v2` (60 questions dont 8 pièges proches, figé, disjoint du test) ; états `INDEX_PENDING`, `INDEX_STALE`, `INDEX_UNAVAILABLE`, `INDEX_CURRENT` par la vraie chaîne. `xfail` strict **S1** (pas d'escalade par âge) | 5 réussis, 1 xfail |
| 0035 | Générations Qdrant : bascule d'alias, ancienne génération gardée, écriture concurrente jamais validée. `xfail` strict **Q1** (provenance perdue après `rebuild`) et **Q2** (`delete()` public) | 2 réussis, 2 xfail ; suite Memory complète **2 529 réussis, 6 xfail, 0 échec** |

## Patch 0036 (G234, base `29f9c7b`, après 0008 et 0032 à 0035)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0036 | Contre-revue du cycle de maintenance (Markdown réel, Qdrant en mémoire ou local sur disque) : 1 200 indexations saines traitées une seule fois ; reprise après `rebuild` (ré-encodage complet, convergence, rien supprimé) ; processus tué **après** l'écriture du point et **avant** `INDEXED` : reprise sans second encodage. Caractérisations à trancher : **MT1** (saut d'horloge en avant = `CLOCK_REVERSED` sans issue) et **MT3** (index au-delà de `max_points` = cycle jamais terminé) | 5 réussis ; suite Memory complète **2 566 réussis, 6 xfail, 0 échec** |

## Patch 0037 (G235, base `41fe381`)

GPT a intégré 0008 et 0032 à 0036 (seuls changements : Q1 devenu test ordinaire, 0036 attend 5 écritures au lieu de 10).

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0037 | Contre-vérification de Q1 corrigé : chaque point reconstruit porte l'empreinte, la révision et la génération des octets lus ; un canon modifié pendant `rebuild` n'est jamais publié (alias inchangé) ; un écrivain coopératif attend la fin de la reconstruction puis passe. Sabotage : retirer la preuve ou le verrou de `rebuild()` n'est détecté **que** par ces sondes (les 58 tests Qdrant de GPT restent verts) | 3 réussis ; suite Memory **2 570 réussis, 5 xfail, 0 échec** |

## Patchs 0038 à 0042 (G236, base `587d4a9`)

GPT a intégré mes sondes C181 (G241). Ordre : 0038, 0039, 0040 (indépendants) ; 0041 puis 0042 (propositions de
refactorisation, à part).

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0038 | Contre-revue G236/G237 : MT1 (reprise d'horloge sans effet sur journal et index, refus des demandes périmées ou sans défaut, rejeu idempotent, crash dans la transaction), MT3 (borne liée au contexte, inventaire incomplet jamais certifié), R1 (document trop gros reporté sans encodage, croissance refusée), Q1 (ancienne génération jamais réécrite). 4 mutants de `recover_clock` tués | 8 réussis |
| 0039 | **Nouveau module** `core/indexing/index_lag.py` (S1) : évaluateur pur, seuil obligatoire fourni par l'hôte ; santé, couverture canonique et ancienneté distinctes | 12 réussis |
| 0040 | Expérience Q2 : vue « worker » à six membres ; cycle complet sans accès à `rebuild`/`delete`/`upsert` | 2 réussis ; suite Memory **2 660 réussis, 15 ignorés, 5 xfail** avec 0038 à 0040 |
| 0041 | Proposition L1 : module feuille `operations/publication_phase.py` ; cycles 2 → 1 | suite inchangée (2 638 réussis sur la base) |
| 0042 | Proposition L1 : `persistence.atomic_write_bytes` ; bloc de 36 modules → 13 + 12 | suite inchangée |

## Patchs 0043 et 0044 (contre-revue G242-G251, base `797e102`)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0043 | Gardes du rappel sémantique : sabotage local de `core/retrieval/indexed.py` (10 mutants). Deux survivent aux 87 tests GPT et sont tués ici : contrôle « contenu renvoyé = contenu prouvé » (ABA entre `backend.get` et la lecture de preuve) ; archive de conversation sans référence de passage jamais citée entière. Doublons : mutant équivalent (dédoublonnage en aval) | 3 réussis |
| 0044 | Saturation du pont mémoire : sabotage local de `services/memory_bridge.py` (8 mutants). Deux survivent aux 40 tests GPT et sont tués ici : un second rappel pendant un rappel bloqué reçoit `BUSY` aussitôt ; un échec de démarrage du traitement rend sa place | 2 réussis ; suite Memory **2 762 réussis, 18 ignorés, 4 xfail** |

## Patchs 0045 à 0047 (G252, base `9a61648`, après 0043 et 0044)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0045 | Contre-revue G252 (tâches 1, 2, 3, 5, 6, 8) : fraîcheur globale, preuves candidates, courses du manifeste (tue le mutant « second inventaire »), diagnostics d'âge, vue « worker » sur le contrôleur et ses trois enfants, transport du pont (déconnexion, erreurs sans fuite, échéance de lecture distincte du rappel) | 12 réussis |
| 0046 | Classificateur **expérimental** de rétention des générations (tests seulement, aucune suppression) | 6 réussis |
| 0047 | Tranche minimale **expérimentale** des passages d'archives : projection sans texte, citation canonique | 3 réussis ; avec 0043 à 0047, suite Memory **2 791 réussis, 18 ignorés, 4 xfail** |

## Patchs 0048 à 0051 (G256, base `81084e0`, dans l'ordre)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0048 | Rétention G256-1/2 : 17 défauts de mon classificateur G252 corrigés (entrées ambiguës, alias mélangés, générateur, plantages), refus temporels publics (`RETIREMENT_IN_FUTURE`, `not_before`, `epoch_window`) | 37 réussis, 22 rouges avant ; 6 tests G252 inchangés |
| 0049 | Reçu pur **expérimental** de bascule d'alias : rejeu, reçu incomplet, bascule non observée, chaîne ; faits de retrait pour la rétention | 6 réussis ; 10 sabotages, 9 tués, 1 équivalent retiré |
| 0050 | Passages G256-4/5 : identité sans ambiguïté de séparateur, projection servie = dernière lue (rien supprimé), messages vides ; tue un sabotage survivant de `core/retrieval/indexed.py` (point hors bornes = rappel entier en échec) | 27 réussis, 20 rouges avant |
| 0051 | Contre-revue G257 : écriture ≠ reste de l'échéance de lecture (tue un sabotage survivant), rappel long, en-tête/corps lents, borne de l'écriture ; `xfail` strict : verrou de rappel tenu pendant l'écriture (proposition) | 6 réussis + 1 xfail, 5 passages ; suite Memory **2 869 réussis, 18 ignorés, 5 xfail** |

## Patchs 0052 à 0054 (G258, base `a0cc112`, dans l'ordre)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0052 | Contre-revue du verrou G259 : rappel servi pendant deux écritures bloquées (réponse normale, erreur, réponse trop grande), capacité bornée, calculs un par un, client coupé ; réponse figée sous verrou (tue un sabotage qui survit aux 57 tests du pont) | 7 réussis, 3 passages |
| 0053 | Reçu de bascule : ancres validées, rejeu entre vérifications, même `epoch_window` que la rétention, verdicts monotones | 8 réussis, 5 rouges avant |
| 0054 | Budgets optionnels de la projection de passages (par archive, total avec points dépassés), refus sans effet, `stats()` | 8 réussis ; suite Memory **2 896 réussis, 18 ignorés, 4 xfail** |

## Patchs 0055 à 0058 (G262, base `f534315`, dans l'ordre)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0055 | Inventaire des écritures d'un rappel sur canon en lecture seule : trace, EROFS simulé, droits réels sous UID ordinaire (rejoués sous `nobody` depuis root) | 11 tests (2 ignorés en root, exécutés par sous-processus) |
| 0056 | Prototype de verrou compatible lecture seule : verrou préexistant ouvert O_RDONLY + flock, exclusion avec le vrai écrivain, vrai montage RO (`unshare -m`), mode « external » avec empreinte dev/ino/ctime | 9 tests ; 5 sabotages tués |
| 0057 | Budget de projection : découpage borné avant refus (1 Mo : 423 ms → 6 ms), reprojection sans travail | 6 tests, 5 rouges avant |
| 0058 | Reçus : fenêtres géantes et ensembles de rejeu invalides (texte, None, identifiants faux) refusés avec codes stables ; consommation durable séparée (O_EXCL + fsync, 12 processus : 1 gagnant) | 24 tests, 12 rouges avant ; suite Memory **2 944 réussis, 20 ignorés, 4 xfail** |

## Patchs 0059 à 0061 (G264, base `77ba294`, dans l'ordre)

| Patch | Contenu | Preuve en conteneur |
| --- | --- | --- |
| 0059 | Contre-revue `--check-storage` (G265) : aucun effet ni texte privé (audit hooks), BUSY immédiat et relâchement, BLOCKED sans réparation, CLI ; tue un sabotage « audit bloquant » qui survit aux tests G265 ; `xfail` strict : erreur d'usage = code 2 de BLOCKED | 20 tests + 1 xfail |
| 0060 | Mode de verrou par défaut inchangé pour les écrivains (inventaire AST, `a+b`, Windows simulé en sous-processus) | 6 tests ; 2 sabotages tués |
| 0061 | Provenance exacte des passages expérimentaux (CRLF, NFD, ZWJ, paragraphes identiques, réécritures concurrentes) | 5 tests ; suite Memory **2 972 réussis, 20 ignorés, 5 xfail** |
| 0062 | G266-6 : magasin des reçus consommés — identité du répertoire figée à la construction (`RECEIPT_STORE_CHANGED`), droits élargis refusés (`RECEIPT_STORE_UNSAFE`), échec de fsync après création = `RECEIPT_CONSUMED_UNCONFIRMED`, marque conservée, aucun rejeu | 7 tests ; 6 rouges avant |
| 0063 | G266-7 : contre-revue numérique des temps de reçu G267 — `generation_retention._seconds` attrape `OverflowError` (5 débordements bruts corrigés) | 16 tests ; 5 rouges avant |
| 0064 | G266-8 : bornes de projection — `CHUNKER_CEILING=10000` nommé, code propre à chaque limite, retour à une ancienne empreinte sans nouveaux points (corrige une régression de mon G262-8), archive absente puis restaurée | 9 tests ; 8 rouges avant |
| 0065 | G266-9 : code publié G263/G265 sur un VRAI montage bind en lecture seule (`unshare -m`) : READY, mode par défaut EROFS, verrou disparu = UNAVAILABLE, écrivain = BUSY ; SKIP motivé si espaces de noms refusés | 6 tests |
| 0066 | Robustesse : les relances sous `nobody` sondent `setpriv … id -u` et sont **ignorées avec le motif** (ex. `setresuid: Invalid argument`) au lieu d'échouer. À appliquer après 0059 | 2 tests ; suite Memory **3 067 réussis, 22 ignorés, 5 xfail** |
