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
