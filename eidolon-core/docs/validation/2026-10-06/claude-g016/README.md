# C-TASK-G016 — correction des écarts G012-01/02/03

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G016](../../../../collaboration/tasks/C-TASK-G016.md).
Cible corrigée : `cc9a64bda4d9fd619cf25cf8607230d31ae3d7da` (consommateur G012).
Revue d'origine : [codex-g012-integration](../codex-g012-integration/README.md).
Périmètre : `desktop/prototype/` seulement. Ni `src/`, ni `tests/` Python, ni
la sonde de Codex modifiés.

Environnement : Linux, Node 22.22.0, Playwright 1.56.1, Chromium local
(`/opt/pw-browsers`). Aucun Windows, VM, GPU, réseau externe ni modèle réel.

## Preuve « échoue avant, passe après »

Les 7 tests de [`tests/g016.test.js`](../../../../desktop/prototype/tests/g016.test.js)
ont été joués deux fois :

| Version de `sync-state.js` | Résultat | Sortie |
| --- | --- | --- |
| `cc9a64b` (SHA-256 `2f6e696e…6ad43f`, `git show cc9a64b:…`) | **2 réussis, 5 échoués** | [g016-before-cc9a64b.txt](g016-before-cc9a64b.txt) |
| après correction (SHA-256 `4606f28f…def88e5`) | **7 réussis** | [g016-after.txt](g016-after.txt) |

```sh
cd eidolon-core
git show cc9a64b:eidolon-core/desktop/prototype/sync-state.js > /tmp/old.js
G016_SYNC_STATE=/tmp/old.js node --test desktop/prototype/tests/g016.test.js   # 2/7
node --test desktop/prototype/tests/g016.test.js                                # 7/7
```

Les deux tests déjà verts sur `cc9a64b` sont des **garde-fous**, pas des
régressions : « les autres validations ne sont pas relâchées » (5, `true`, `{}`,
81 caractères restent refusés) et « un second reset remplace le premier »
(déjà le cas, désormais explicite et compté).

Suite complète du prototype : **67 tests, 67 réussis** ([sortie](tests-output.txt)),
dont 18 tests d'interface réellement exécutés dans Chromium. Contraste le plus
faible : 4,70:1 sur les 35 vues G009 et sur les 9 vues de synchronisation.

## Ce qui change

**G012-01 — `objective_kind=null`.** Accepté s'il vaut `null` ou une chaîne de
80 caractères au plus ; tout autre type reste `INVALID_MISSION`. La vue affiche
« Aucun objectif reconnu (hors catalogue) ». Une mission `BLOCKED` avec
`outcome_status=CLARIFICATION` s'affiche « Bloquée — précision demandée ». La capture
Core **observée** (`core-unsupported.json` de Codex) est recopiée sans
changement dans le groupe `observed` des fixtures, avec son chemin source et
son SHA-256 ; elle alimente le scénario `sync-objectif-null`.

**G012-02 — reset en attente.** Dès qu'un `RESET_REQUIRED` est reçu, toute
réponse SNAPSHOT ou DELTA est ignorée et comptée (`frozenAnswers`), quelle que
soit son époque : vue, curseur et références restent identiques, et
`nextRequest` rend `null` (zéro émission). Définitions demandées par la fiche :

- un **second reset** remplace le premier (`supersededResets`) ; l'acceptation
  applique le plus récent ;
- après acceptation, une **réponse de l'ancienne époque** reste ignorée ;
- un nouveau reset dans la nouvelle époque redevient « en attente », jamais
  appliqué seul.

Aucun renvoi de commande, aucune reconstruction depuis les événements.

**G012-03 — revue et annulation.** `REVIEW_REQUIRED` est testé en premier :
« Revue requise — effet à vérifier », même avec `cancel_requested=true`. La
demande d'annulation a sa propre ligne (`cancelNote`) : « Annulation demandée :
enregistrée, issue non garantie », ou, sur un état final, « Annulation demandée
avant la fin ; issue capturée : X ». L'effet `UNKNOWN` et les preuves restent
affichés ; aucun texte ne promet `CANCELLED`. Sur une mission en cours, le
libellé devient « Annulation demandée — issue non confirmée ». Le cas UI
`sync-revue-annulation` (dérivé `review_with_cancel`) vérifie qu'aucun bouton
n'est rendu dans la fenêtre.

## Sonde historique de Codex

[`probe.cjs`](../codex-g012-integration/probe.cjs) affirme les **anciens
défauts** (rejet `INVALID_MISSION`, vue déplacée de 1 à 11, ancien libellé).
Je ne l'ai pas réécrite. Rejouée après correction, elle échoue dès sa première
assertion, comme prévu par sa propre documentation :
[codex-probe-after.txt](codex-probe-after.txt) (`null` reçu au lieu de
`INVALID_MISSION`).

| Sonde Codex | Mes tests |
| --- | --- |
| attend le rejet de la capture réelle | attendent son acceptation, et le refus des autres types |
| attend la vue déplacée (1 → 11) | rejouent la même séquence et attendent 1, puis gèlent aussi SNAPSHOT, une capture plus récente, et vérifient `nextRequest = null` |
| attend « pas encore confirmée » sur une revue | attendent « Revue requise », une note d'annulation séparée et l'absence de « CANCELLED » |
| — | second reset, ancienne époque après acceptation, mission en cours annulée |

## Captures

[13 — revue et annulation](captures/13-g016-revue-et-annulation.png) ·
[14 — objectif nul observé](captures/14-g016-objectif-nul.png) ·
[10 — reset avec réponse tardive gelée](captures/10-sync-reset.png).
Les autres captures (01 à 12) sont régénérées par la même exécution.

## Limites

- Prototype de démonstration : enveloppes enregistrées, aucune connexion à Core.
- Le gel s'applique à toute réponse pendant l'attente : une capture réellement
  plus récente est aussi ignorée jusqu'à l'acceptation. C'est voulu (la fiche
  demande zéro changement avant acceptation), au prix d'une vue plus ancienne.
- Les compteurs `frozenAnswers` et `supersededResets` ne sont pas bornés en
  nombre d'éléments : ce sont deux entiers.
- Les libellés sont ceux du prototype, pas un vocabulaire du contrat Core.
