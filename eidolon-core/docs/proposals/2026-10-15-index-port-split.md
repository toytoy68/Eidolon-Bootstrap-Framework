# Q2 : séparer le port « worker » du port « administration » de l'index (Claude, G236-7)

Auteur : Claude. Date : 15/10/2026, Europe/Paris. Base Memory : `587d4a9`.
Statut : **proposition**. `IndexPort` et `QdrantIndex` restent inchangés.
Expérience : [patch Memory 0040](../../collaboration/memory-patches/0040-claude-g236-index-port-split.patch).

## 1. Qui appelle quoi (code applicatif `core/`, hors adaptateurs et tests)

| Membre | Appelants | Rôle |
| --- | --- | --- |
| `embedding_id`, `alias` | maintenance, orphan_scan, reconcile_scan, worker_journal, worker_upsert | identité |
| `active_generation` | maintenance, orphan_scan, reconcile_scan, worker_journal | génération |
| `evidence_for` | orphan_scan, reconcile_scan, worker_journal, worker_upsert | preuve |
| `upsert_verified` | worker_journal, worker_upsert | écriture prouvée |
| `inventory_page` | orphan_scan | inventaire |
| `query` | retrieval.contextual, retrieval.indexed | lecture |
| `status` | aucun dans `core/` | diagnostic |
| `rebuild` | **aucun** dans `core/` | administration |
| `delete` | **aucun** | administration |
| `upsert` (sans preuve) | **aucun** (ancien worker isolé, sous `tests/`) | ancien |
| `revision_for` | aucun | ancien |

Méthode : recherche des appels réels. Les chaînes `"index.upsert"` et
`"index.delete"` sont des noms de permission, pas des appels.

## 2. Proposition

Trois protocoles, définis par rôle, sans casser `IndexPort` :

```python
class WorkerIndexPort(Protocol):           # worker, scans, maintenance
    embedding_id: str
    alias: str
    def active_generation(self) -> str: ...
    def evidence_for(self, information_id: str) -> IndexEvidence | None: ...
    def upsert_verified(self, memory, *, canonical_sha256: str) -> IndexEvidence: ...
    def inventory_page(self, *, generation: str, offset, limit: int) -> IndexInventoryPage: ...

class RetrievalIndexPort(Protocol):        # recherche
    def query(self, text: str, *, limit: int = 5) -> list[IndexHit]: ...
    def status(self) -> IndexStatus: ...

class AdminIndexPort(Protocol):            # opérateur, après revue
    def rebuild(self, persistent_root) -> None: ...
    def delete(self, information_id: str) -> None: ...
```

Étapes, chacune petite et réversible :

1. Ajouter les trois `Protocol` dans `port.py`, sans rien retirer.
2. Annoter les constructeurs de `JournalUpsertWorker`, `ReconciliationScan`,
   `OrphanScan` et `IndexMaintenance` avec `WorkerIndexPort`.
3. Faire passer l'hôte par une **vue étroite**, comme la
   `WorkerIndexView` de l'expérience, pour que `delete` et `rebuild`
   soient **inaccessibles** depuis le cycle, et pas seulement inutilisés.
4. Plus tard, et seulement si l'on veut : retirer `upsert` sans preuve et
   `revision_for`, après vérification des appelants externes (outils,
   CLI).

## 3. Preuve de faisabilité (0040)

À travers une vue qui n'expose que les six membres « worker » :

- le cycle de maintenance **complet** tourne : worker, scan canonique, scan
  des orphelins, revue ;
- un document retiré hors procédure est signalé (`REVIEW_REQUIRED`) et son
  point **reste en place** ;
- `rebuild`, `delete`, `upsert` et `revision_for` lèvent
  `AttributeError` ;
- la vue refuse toute affectation.

## 4. Limites

La vue est une barrière de conception, pas une sécurité contre du code
malveillant dans le même processus (accès possible à `_index`). La
protection réelle reste la revue humaine et les droits `index.delete`.
