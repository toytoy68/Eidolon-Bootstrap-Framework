# C-TASK-G021 — cohérence du total de missions dans le prototype

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G021](../../../../collaboration/tasks/C-TASK-G021.md).
Défaut trouvé par Codex sur G018 (`bfa75d2`),
[sonde `probe-list.js`](../codex-recovery-followup/probe-list.js).
Périmètre : `desktop/prototype/` seulement ; ni `src/`, ni `tests/` Python.

Environnement : Linux, Node 22.22.0, Playwright 1.56.1, Chromium local.

## Défaut, reproduit puis corrigé

Une page qui annonce `mission_count=3`, n'apporte qu'une mission et se dit
dernière (`has_more=false`) était acceptée. Résultat : `complete=true` et
« Capture entièrement lue (1) ». La sonde de Codex a été rejouée avant
correction (même sortie que la sienne), puis après :

```json
{"case":"terminal-page-shorter-than-announced","announced":3,"received":0,"complete":false,
 "summary":"Liste incomplète : réponse incohérente (LIST_ENDED_EARLY), 0 reçues sur 3 annoncées ; nouvelle lecture explicite nécessaire"}
```

[Sortie après correction](codex-probe-list-after.txt).

## Règle ajoutée (`mission-list-state.js`, SHA-256 `58add172…`)

Avant de prendre une page, on calcule « reçues jusqu'ici + items de la page »
et on le compare au total `generation.mission_count` :

| Cas | Code | Effet |
| --- | --- | --- |
| cumul > total | `COUNT_EXCEEDED` | page refusée |
| `has_more=false` et cumul < total | `LIST_ENDED_EARLY` | page refusée |
| `has_more=true` et cumul ≥ total | `HAS_MORE_INCONSISTENT` | page refusée |

Dans les trois cas :

- **rien** n'est pris de la page ;
- la lecture **s'arrête** (`halted`) et les réponses tardives sont gelées ;
- le statut devient « Liste incomplète : réponse incohérente (…), N reçues sur
  M annoncées », avec un bandeau « Relire la liste » ;
- aucune mission n'est inventée, et la liste n'est jamais déclarée complète.

Le compteur `received` compte aussi les missions au-delà du plafond
d'affichage.

**Protocole et affichage** : le contrôle du total est une règle de cohérence
du protocole. Le plafond de 200 reste une **borne d'affichage** :
« 200 affichées sur 250 annoncées », jamais complète. La déduplication, les
curseurs, le reset, la sélection et la provenance sont inchangés.

## Preuves

`tests/g021.test.js` (6 tests, SHA-256 `e3ace344…`) :

| Version de `mission-list-state.js` | Résultat | Sortie |
| --- | --- | --- |
| `bfa75d2` (G018) | **1 réussi, 5 échoués** | [g021-before-bfa75d2.txt](g021-before-bfa75d2.txt) |
| après correction | **6 réussis** | [g021-after.txt](g021-after.txt) |

Le test qui passe déjà sur `bfa75d2` est le garde-fou « traces valides
inchangées » : 3 pages observées complètes, base vide, 250 → 200 tronquée.

Cas couverts :

- première page qui finit trop tôt (le cas de Codex) ;
- page suivante qui finit trop tôt ;
- total zéro avec un item ;
- dépassement sur deux pages ;
- `has_more` incohérent ;
- traces valides ;
- gel puis relecture complète.

Suite complète du prototype : **92/92** ([sortie](tests-output.txt)).

- **Nouveau dans G021** : 6 tests de logique et 1 parcours Chromium
  (`liste-incoherente`). Capture
  [19 — fin incohérente](captures/19-g021-fin-incoherente.png).
- **Déjà rapporté avant G021** : les 85 tests précédents passent toujours.
  Contraste le plus faible : 4,70:1, sur 9 vues de liste désormais.

Fixtures dérivées ajoutées, étiquetées :

- `ended_early` : `fresh_pages[1]` présentée comme dernière page ;
- `has_more_inconsistent` : `varied_page` avec `has_more=true`.

La trace observée C-008e est inchangée (SHA-256 vérifié).

## Limites

- Le total annoncé n'est contrôlé que par cohérence interne des réponses. Il
  ne peut pas révéler un serveur qui mentirait de façon cohérente.
- Après un arrêt, seule une relecture explicite repart. Il n'y a pas de
  nouvelle tentative automatique.
