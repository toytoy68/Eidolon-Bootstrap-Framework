# L1/L2 : cartographie des cycles d'imports et plus petites extractions (Claude, G236-10)

Auteur : Claude. Date : 15/10/2026, Europe/Paris.
Bases : Core `c661539`, Memory `587d4a9`. Statut : **proposition**.

## 1. Outil reproductible

```sh
python eidolon-core/tools/claude_import_cycles.py eidolon-core/src/eidolon_core
python eidolon-core/tools/claude_import_cycles.py <checkout Memory>/core [--json]
```

- Analyse AST seulement : rien n'est importé ni exécuté.
- Compte aussi les imports **différés**, placés dans des fonctions : c'est
  là que se cachent la plupart des cycles.
- Limites : `importlib`, `__import__`, les branches par plateforme et les
  réexports par attribut d'`__init__` sont approchés ou manqués.

## 2. État observé

| Dépôt | Modules | Imports internes (dont différés) | Cycles |
| --- | --- | --- | --- |
| Core | 115 | 401 (112) | 5 : média (7 modules), `approvals`/`runtime`/`store`/… (6), `http_api`/`media_workspace`/`preflight` (3), `dialogue`/`dialogue_profiles` (2), `query_history`/`research_guard` (2) |
| Memory | 145 | 602 (101) | 2 : un bloc de **36 modules** (57 liens différés à l'intérieur) et `persistence` ↔ `operations.read_phase` |

## 3. Classement par risque

| Rang | Cycle | Risque | Pourquoi |
| --- | --- | --- | --- |
| 1 | Memory, 36 modules | moyen | Le stockage (`backend.filesystem`) dépend de règles métier. Un import réordonné peut casser au démarrage, et les tests isolés deviennent difficiles. |
| 2 | Memory, `persistence` ↔ `read_phase` | moyen | La couche la plus basse dépend d'une couche haute. |
| 3 | Core, `approvals`/`runtime`/`store` | moyen | C'est le cœur des autorisations ; les cycles compliquent la revue de sécurité. |
| 4 | Core, média (7) | faible | Ensemble cohérent, déjà isolé du reste. |
| 5 | Core, paires (`dialogue`, `query_history`, `http_api`) | faible | Imports différés locaux. |

## 4. Plus petites extractions, éprouvées

Les deux expériences ont été menées sur une copie de Memory `587d4a9`,
suite complète comprise. Les deux patchs sont des **propositions**, à
appliquer dans l'ordre.

| Patch | Changement | Effet mesuré | Suite |
| --- | --- | --- | --- |
| [0041](../../collaboration/memory-patches/0041-claude-l1-publication-phase-leaf.patch) | état de la phase de lecture stabilisée déplacé dans un module feuille `operations/publication_phase.py` ; `read_phase` le réexporte | cycles : **2 → 1** | 2 638 réussis, 15 ignorés, 5 xfail (inchangé) |
| [0042](../../collaboration/memory-patches/0042-claude-l1-atomic-write-bytes.patch) | `_atomic_bytes` devient `persistence.atomic_write_bytes` ; `converter` le réexporte sous l'ancien nom | le bloc de **36 → 13 + 12** modules ; **11 modules** sortent de tout cycle | inchangé |

Comment 0042 a été trouvé : pour chacun des 122 liens internes au bloc de
36, j'ai mesuré la taille du plus grand cycle restant une fois ce lien
retiré. Le meilleur candidat est `sources.chatgpt_import` →
`migration.converter`. Ce lien n'importait **qu'un** utilitaire privé
d'écriture atomique.

Prochains candidats, du même calcul :

- `backend.filesystem` → `sources.chatgpt_import` (import différé), qui
  laisserait un plus grand cycle de 16 modules ;
- `operations.readiness` → `routing.execution`, qui en laisserait 28.

## 5. Ce que je ne propose pas

- Pas de refactorisation globale.
- Pas de déplacement de logique métier.
- Pas de changement des fichiers réservés à GPT (`maintenance.py`,
  `worker_journal.py`, `worker_canonical.py`).
- Côté Core, aucune expérience pour l'instant : les cycles y sont plus
  petits, et les fichiers concernés (`runtime.py`, `store.py`) sont à GPT.
