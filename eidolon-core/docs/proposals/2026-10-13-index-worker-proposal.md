# Worker d'indexation Memory : proposition en trois étages (G208, G209)

Auteur : Claude. Date : 13/10/2026, Europe/Paris.
Statut : **proposition**. Aucun code actif, aucune VM. S'appuie sur le
journal v2 de GPT (`420184f`), `reconcile_plan` (avec le correctif 0013/0015)
et `reconcile_preview` (absence prouvée, `fa03e09`).

## 1. Trois étages séparés

| Étage | Rôle | Droits | Ne fait jamais |
| --- | --- | --- | --- |
| **1. Planifier** | `preview_reconciliation` sur un instantané **complet et daté** : journal, canonique (`Canonical` ou `ABSENT` **prouvé**) et index | lecture seule | écrire quoi que ce soit |
| **2. Vérifier** | Pour chaque action, **relire** le Markdown juste avant : révision, empreinte et droits (profil, G173) ; passage (document, révision, position, empreinte) ; `embedding_id` et version du découpeur | lecture seule | se fier à l'instantané de l'étage 1 |
| **3. Agir** | Exécuter **seulement** les actions revérifiées : `upsert` ou `delete` de passages Qdrant, puis `indexed()` ; `published()` ; `close_terminal()` | écriture index et journal | toucher au Markdown ; supprimer une collection ; agir sans vérification |

Règles communes :
- **Aucune suppression automatique** de données canoniques, de collections
  ou de lignes de journal. `retirement_plan` et `compaction_plan` ne
  produisent que des **propositions**, appliquées après une revue humaine.
- `CLOSE_ABANDONED` et `INTEGRITY_ALERT` exigent une **revue** (M9) ; le
  worker les liste sans les appliquer seul.
- `WAIT` : rien n'est fait, réessai au tour suivant.
- Une seule instance active, avec un verrou exclusif non bloquant (comme le
  registre G184). Une seconde instance répond « occupé » et ne fait rien.

## 2. Ordre de l'étage 3 et idempotence

1. `upsert` ou `delete` dans Qdrant (`wait=True`), avec l'identifiant de
   point dérivé de (document, révision, découpeur, plage). Rejouer donne le
   même point, sans doublon.
2. Relecture de l'index : le point existe, ou n'existe plus, avec la bonne
   révision.
3. `indexed(seq)`, qui est idempotent.

Un arrêt entre 1 et 3 laisse l'intention `PUBLISHED`. Au tour suivant, le
plan refait l'étape 1 (sans effet en double) puis 3.

## 3. Tests d'interruption à écrire avec le worker

Chaque test tue le processus (`os._exit`) à un point précis, relance le
worker, et vérifie l'état final et l'absence de double effet.

| Arrêt entre | Attendu après relance |
| --- | --- |
| `begin()` et le renommage canonique | intention `INTENT`, écriture invisible : `WAIT`, puis `CLOSE_ABANDONED` proposé après le délai de grâce **et une revue** |
| renommage et `published()` | `MARK_PUBLISHED` (reprise), puis indexation une seule fois |
| `published()` et l'`upsert` Qdrant | `INDEX_UPSERT` rejoué, un seul point |
| `upsert` Qdrant et `indexed()` | `upsert` rejoué sans doublon, puis `indexed()` |
| deux révisions rapides du même document | la plus ancienne devient `SUPERSEDED`, seule la révision canonique courante est indexée |
| suppression canonique, puis plantage avant l'index | `INDEX_DELETE` appliqué, sur absence **prouvée** |
| canonique illisible (permission, disque) | `WAIT` partout : aucune publication, suppression ni clôture (M8) |
| Qdrant indisponible | état `INDEX_UNAVAILABLE`, rien de marqué `indexed()` |
| changement d'`embedding_id` ou de découpeur | refus, reconstruction complète dans une nouvelle génération |

## 4. Écarts relevés en contre-revue G209 (patch 0016)

M2 (réutilisation de séquence), M4 (nouveau journal en v1), M7 (refus à
exactement `limit`), M8 (canonique non lu pris pour supprimé : corrigé par
GPT en `0e83573`/`30fb6ef`) et M9 (abandon sans revue). À régler avant le worker.
