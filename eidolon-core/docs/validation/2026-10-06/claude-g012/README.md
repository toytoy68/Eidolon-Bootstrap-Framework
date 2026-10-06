# Preuves C-TASK-G012 — consommateur client-sync/1 dans le prototype

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G012](../../../../collaboration/tasks/C-TASK-G012.md).
Base : `1489898` (contient C-008a `37604a1`, C-008b, C-008c et l'intégration de G013).
Contrat : [CLIENT-SYNC.md](../../../CLIENT-SYNC.md), version `eidolon-client-sync/1`.
Empreintes vérifiées : `client_sync.py` `6584fa2a…a4ea`, identique à
[source-hashes.json](../codex-client-sync/source-hashes.json) ; trace
[demo.json](../codex-client-sync/demo.json) `f95801f6…f9a`, inchangée.

Fichiers ajoutés ou modifiés : `desktop/prototype/` uniquement (`sync-state.js`,
`sync-view.js`, `fixtures/`, `app.js`, `index.html`, `model.js` pour l'œil,
README et tests). Ni `src/`, ni `tests/` Python, ni contrats ou preuves de Codex.

## Exécuté

```sh
cd eidolon-core
node desktop/prototype/fixtures/build-sync-fixtures.js
CAPTURES=$PWD/docs/validation/2026-10-06/claude-g012/captures \
NODE_PATH=/opt/node22/lib/node_modules node --test --test-reporter=spec "desktop/prototype/tests/*.test.js"
```

Node 22.22.0, Playwright 1.56.1, Chromium, Linux. [Sortie](tests-output.txt) :
**58 tests, 58 réussis**. Détail : 13 tests du consommateur, 1 test de l'œil,
5 tests UI de synchronisation, et les 39 tests G009/G013 toujours verts.

## Scénarios de la fiche → tests

| # | Demande | Test (`sync.test.js`, sauf mention) | Fixture |
| --- | --- | --- | --- |
| 1 | Reconnexion après progression, pages bornées, doublons | « 1. reconnection… » ; UI « catch-up… » | réelle (page 2 livrée deux fois) |
| 2 | Capture en avance sur la page | « 2. capture ahead… » | réelle (`as_of` 11, curseur 3) |
| 3 | Réponses hors ordre | « 3. out-of-order… » | dérivée `late_older_answer` |
| 4 | Annulation à révision inchangée | « 4. cancellation… » ; UI | dérivées `cancel_before`, `cancel_requested_same_revision` |
| 5 | RESET_REQUIRED, rechargement explicite ; curseur ou version rejetés | « 5a », « 5b » ; UI « RESET_REQUIRED… » | réelle `reset_example` ; dérivées `reset_store_changed`, `wrong_mission_cursor`, `unknown_protocol`, `unsafe_integer` |
| 6 | Déconnexion | « 6. disconnection… » ; UI | réelle |
| 7 | Axes d'accord séparés, rien d'autorisé | « 7. approval axes… » ; UI | dérivées `action_pending`, `action_review` ; réelle `action_view=null` |
| 8 | Texte comme donnée | « 8. hostile text… » ; UI « hostile text rendered as text only » | dérivée `hostile_text` |

Plus : rétention bornée (« retention… »), pureté des fonctions, et le cas
ci-dessous (« a page that does not start right after our cursor… »).
Les 10 cas dérivés sont générés par `build-sync-fixtures.js`. Chacun porte
`derived: true` et une phrase `why` qui dit ce qui a été changé.

## Point de conception trouvé pendant le lot

L'enveloppe `DELTA` ne rappelle pas le curseur de la requête, et les séquences
peuvent sauter à cause d'autres missions. Une page qui ne commence pas juste
après le curseur du client (réponse à une autre requête) aurait pu faire
avancer ce curseur en laissant un trou. Ma première version avait ce défaut,
trouvé en construisant le scénario « texte hostile », avant tout commit.

Correction côté client : `cursor.event_count − events.length` doit égaler le
`event_count` du curseur du client. Sinon, la page est écartée : ni
références, ni curseur, mais sa capture reste prise si elle est plus récente.

**Suggestion pour le contrat (pas un défaut)** : faire figurer dans `DELTA`
le point de départ de la page (par exemple `from_sequence` et
`from_event_count`, repris du curseur reçu). Le client pourrait alors vérifier
la continuité sans déduction.

## Œil « Reçu à vérifier »

Demandé par Codex en C-MSG-G026. Test « G012 eye… » (`commands.test.js`) :
attention et libellé quand une demande est incertaine ; hors ligne, écoute et
silence restent prioritaires ; aucun envoi supplémentaire ; le libellé
disparaît une fois le reçu consulté.

## Captures (Chromium, Linux)

| Fichier | Contenu |
| --- | --- |
| [09](captures/09-sync-rattrapage.png) | Rattrapage terminé : 10 références, 2 doublons ignorés |
| [10](captures/10-sync-reset.png) | RESET_REQUIRED (ANCHOR_CHANGED) en attente du rechargement |
| [11](captures/11-sync-annulation.png) | « Annulation demandée — pas encore confirmée » |
| [12](captures/12-sync-rejets-texte-hostile.png) | Réponses refusées et texte HTML affiché comme texte |

Les captures 01 à 08 (G009/G013) sont régénérées par la même exécution.

## Non vérifié

Pas de transport : les enveloppes sont livrées par le banc, pas lues depuis
Core. Pas de raccordement des commandes C-008b/C-008c (hors fiche). La fenêtre
principale G009 garde son serveur simulé. Rendu Windows, zone de notification
et notifications non qualifiés. Lecteur d'écran réel non essayé.
