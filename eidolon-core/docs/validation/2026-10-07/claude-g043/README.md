# G043 — fraîcheur du client face aux réponses refusées

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G043](../../../../collaboration/tasks/C-TASK-G043.md).
Base : `310d94b` (C055). Fichiers modifiés : `desktop/connected/` seulement
(`src/session.js`, `src/view.js`, `app.js` régénéré, `tests/session.test.js`).

- [5 nouveaux tests sur le client d'avant : 3 échecs](session-tests-before-310d94b.txt)
- [suite complète après : 54/54, 0 sauté](node-tests.txt) (Node, vrai serveur, Chromium)

## Écarts reproduits, puis corrigés

| # | Avant | Après |
| --- | --- | --- |
| F1 | Une page de liste en HTTP 200 mais **refusée** par le protocole (ici `authorizes_execution: true`) faisait avancer « Dernière réponse reçue », sans aucun problème affiché | la date ne bouge pas ; `problem` = code de refus, portée `list` ; la lecture s'arrête |
| F2 | Pour une mission, une réponse **refusée** (autre Store) ou **plus ancienne** que la capture affichée faisait aussi avancer la date | seule une réponse acceptée la fait avancer ; un refus est affiché (portée `selection`) |
| F3 | Avec un `RESET_REQUIRED` en attente, rien ne disait dans le détail que la capture n'était plus l'état actuel (seul le bandeau le signalait) | `viewIsCurrent()` ; le détail affiche « Capture figée » ou « Capture non actualisée : la dernière réponse a été refusée » |
| F4 | Un test G031 (« jamais plus de trois pages ») passait **par accident** : ses données étaient invalides (`INVALID_GENERATION`), chaque page était refusée, et l'ancienne boucle redemandait quand même | données de test valides ; le test vérifie maintenant 3 pages **acceptées**, 6 missions, 0 refus |

Le libellé devient « Dernière lecture acceptée ». Une réponse est « acceptée »
quand les consommateurs n'ont compté ni refus, ni réponse obsolète, gelée ou
plus ancienne (compteurs existants de `mission-list-state.js` et
`sync-state.js`, qui ne sont pas modifiés).

## Vérifié sans écart

- Réponse d'une **ancienne époque de liste** pendant une nouvelle lecture :
  ignorée.
- **Deux connexions simultanées** : seule la dernière s'applique. La réponse
  de la première est comptée comme obsolète, renvoie `false` et ne change
  rien.
- `RESET_REQUIRED` reste une réponse de protocole **acceptée** : elle est
  datée, mais la vue gelée n'est pas présentée comme actuelle.

## Limites

- Les tests sont sur transport scripté. Le vrai serveur ne produit pas ces
  réponses invalides ; les bancs réels G031 à G038 restent verts.
- Un refus arrête la lecture de la liste en cours. Une nouvelle lecture se
  fait par « Relire la liste », sans relance automatique.

## Complément après C-MSG-G056 (même jour)

G056 précise deux attentes de G043 et annonce une réponse `503 BUSY` côté
serveur (C-010b, pas encore livrée).

| # | Attente | Réalisé |
| --- | --- | --- |
| F5 | Une consultation de **reçu** ne rafraîchit pas la capture actuelle | un reçu FOUND ou NOT_FOUND garde sa propre date (`receipt.receivedAt`) ; `lastSuccessAt` et la capture ne bougent pas (avant : `lastSuccessAt` avançait) |
| F6 | `503 BUSY` distinct d'une panne, sans relecture automatique, sans présenter de donnée périmée comme actuelle | nouvelle phase `busy` : reste en ligne ; message « Serveur occupé » ; liste « non actualisée (serveur occupé) » ; détail « Capture non actualisée » ; `viewIsCurrent` faux ; **aucune relance automatique** ; « Actualiser » et « Relire la liste » restent possibles, et le premier succès rend la phase `connected` |
| F7 | Une relecture de liste qui échoue (BUSY, refus) ne doit pas être masquée | `relist` ne relit plus la mission sélectionnée si la liste n'a pas été lue : un détail frais ne cache plus l'échec de la liste |

[Suite complète : 56/56, 0 sauté](node-tests-complement.txt), dont 2 tests
nouveaux (BUSY, reçu sans rafraîchissement).

Limite : le serveur ne produit pas encore `BUSY`. Le client est testé sur
transport scripté avec le corps d'erreur C-009a (`error: "BUSY"`). Si C-010b
choisit un autre code ou un autre statut HTTP, il faudra adapter une ligne
de `session.js`. Une fermeture sans réponse (F-G039-1, comportement actuel)
reste lue comme une panne réseau.
