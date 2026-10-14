# Revue de code et d'architecture (Claude, après G233)

Auteur : Claude. Date : 14/10/2026, Europe/Paris.
Bases : Core `820ba2a` (branche `feat/eidolon-core-v0.1`), Memory `26976e3`
(branche `refactor/architecture-v1`).
Méthode : lecture ciblée, graphe d'imports calculé (AST), sabotages locaux
non publiés, sondes exécutables. Ce n'est **pas** une lecture exhaustive,
ni un pentest, ni une recette VM.

## 1. Verdict

L'architecture est **saine dans son principe** :

- Markdown canonique ;
- Qdrant dérivé et reconstructible ;
- le modèle propose, Core décide, l'humain approuve ;
- verrou coopératif et publication atomique ;
- pas de suppression automatique.

Les fichiers critiques sont écrits défensivement : lecture par descripteur,
`O_NOFOLLOW`, comparaisons d'identité, reçus « incertains » au lieu de
succès supposés.

Il reste trois risques : la **duplication des chemins de worker**, une
**perte de provenance à la reconstruction Qdrant**, et une **dette de
couches** dans Memory. Aucun ne justifie une refonte. J2 ne doit pas être
promu en production avant Q1 et la consolidation des workers.

Suites, avec mes sondes : Memory **2 529 réussis**, 6 `xfail` documentés ;
Core **1 771 réussis**, 12 ignorés.

## 2. Suivi de l'audit G227 de GPT, sur le code actuel

| ID | État vérifié | Preuve |
| --- | --- | --- |
| A01 verrou optionnel | **corrigé** | `apply_upsert` refuse `canonical_root=None` ; verrou réentrant (`exclusive_write`) |
| A02 provenance des points | **corrigé pour `upsert_verified`**, **pas pour `rebuild`** | voir Q1 |
| A03 TOCTOU du lecteur canonique | **corrigé** | `CanonicalReader` : descripteur du dossier, `O_NOFOLLOW`, `fstat` avant et après, identité du dossier |
| A04 contrat sur un worker expérimental | **partiellement corrigé** | `IndexWorker` est une **copie** du worker de référence ; le vrai worker est `JournalUpsertWorker`. Mon patch 0033 porte le contrat sur ce dernier |
| A05 sentinelle `ABSENT` | corrigé (enum typée, `5698a40`) | — |
| A07 horloge Web | corrigé (`05f3182`) | — |
| A08 lecture du secret du pont | **ouvert** | `BridgeMemory.recall` : `is_symlink`, puis `stat`, puis `read_text`, sans descripteur, sans borne, sans contrôle du parent |
| A09 saturation DNS | atténué, comme prévu | plafond de 8, refus immédiat ; mes tests de charge passent sur le code intégré |
| A10, A11 | ouverts (orchestration et recette réelles) | hors code |

## 3. Nouveaux constats

| ID | Gravité | Constat | Preuve | Remédiation proposée |
| --- | --- | --- | --- | --- |
| **Q1** | **moyen** | `QdrantIndex.rebuild()` écrit les points avec `_point(memory)`, **sans** `canonical_sha256`, `embedding_id` ni `generation`. Après **toute** reconstruction, `evidence_for()` renvoie `None` pour chaque point. | Sonde 0035 (`xfail` strict) ; démonstration : provenance présente après `upsert_verified`, absente après `rebuild`. | Faire passer `rebuild` par le même chemin que `upsert_verified`, avec l'empreinte relue par `CanonicalReader`. |
| W1 | moyen | **Trois** implémentations de worker : `worker.py` (copie de ma référence, en-tête encore « reference_worker.py »), `worker_isolated.py` (ancien `upsert()` sans provenance) et `worker_journal` + `worker_upsert` (le vrai). | Lecture ; graphe d'imports. | Garder `JournalUpsertWorker`. Retirer ou marquer « test » les deux autres. Lancer la recette en CI sur le vrai worker (0033). |
| W2 | faible | Deux contrôles finaux du vrai worker (droits et canon juste avant `INDEXED`, sur le chemin de reprise après accusé perdu) n'étaient couverts par **aucun** test de GPT. | Sabotage local : les deux mutants survivent aux 26 tests GPT, et mes sondes 0033 les tuent. | Intégrer 0033. |
| Q2 | faible | `QdrantIndex.delete()` et `upsert()` sans provenance restent publics. | Sonde 0035 (`xfail` strict). | Les retirer de l'adaptateur de production, ou les réserver à une API de suppression revue. |
| S1 | faible | `INDEX_STALE` signifie seulement « canon incomplet ». Une modification non indexée depuis une semaine reste `INDEX_PENDING`. | Sonde 0034 (`xfail` strict). | Escalade par âge de la plus ancienne intention, avec un seuil calibré (étude G218). |
| L1 | dette | Memory : **36 modules** forment un seul cycle d'imports. `backend.filesystem` (stockage) importe `information.references` (règle métier), qui importe `threads` et `operations`. Autre cycle : `persistence` → `operations.read_phase`. | Graphe AST : 146 modules, 607 imports internes, 2 cycles. | Inverser la dépendance : le backend reçoit une politique de suppression injectée ; `persistence` émet un événement au lieu d'appeler `read_phase`. Sans urgence. |
| L2 | dette | Core : 5 cycles, dont `approvals ↔ runtime ↔ store ↔ diagnostics ↔ objectives ↔ simulation` et le bloc média (7 modules). | Graphe AST : 113 modules, 400 imports. `contracts` a un fan-in de 66, ce qui est sain. | Extraire les interfaces (protocoles) de `store` et `runtime`. |
| M1 | info | `IndexMaintenance.reviews()` (une lecture) efface des lignes de revue devenues sans objet. | Lecture. | Acceptable sous verrou ; à documenter comme lecture avec nettoyage. |
| R1 | info | `CanonicalReader` sans `max_bytes` lit le fichier entier (cas du worker journal). | Lecture. | Passer une borne explicite au worker de production. |

## 4. Points forts confirmés

- **Aucune suppression de données** dans le code J2 : seules des lignes de
  suivi internes (revues, observations, checkpoints) sont effacées.
- Surface HTTP Core :
  - écoute sur `127.0.0.1` seulement ;
  - liste blanche `Host` (protection contre le DNS rebinding) ;
  - jetons comparés par empreinte, jeton de lecture par `compare_digest`.
- Worker journal :
  - cinq vérifications successives avant `INDEXED` : droits, canon,
    relecture du point, canon et droits à nouveau ;
  - un accusé perdu ne devient jamais un succès ;
  - les suppressions sont reportées en revue.
- Journal :
  - création atomique (M13 corrigé) ;
  - plantage à chacune des 6 étapes de la migration sans perte (sondes
    0032).
- I1 et W1 :
  - mes 10 tests I1 et 3 tests W1, dont la charge de 50 appels parallèles,
    passent sur le code intégré par GPT ;
  - ils sont versés dans Core.

## 5. Ordre recommandé

1. Q1, puis rejouer 0035.
2. W1 : un seul worker, avec 0033 en CI.
3. A08 : lecture du secret par descripteur.
4. S1, Q2.
5. Dette L1 et L2, par petites étapes, sans changer le comportement.
6. Recette VM et PC (A10, A11), sauvegarde vérifiée, sans suppression
   Qdrant.
