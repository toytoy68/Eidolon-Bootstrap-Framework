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
