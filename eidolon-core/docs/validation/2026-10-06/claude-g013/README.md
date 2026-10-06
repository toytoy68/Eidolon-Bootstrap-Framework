# Preuves C-TASK-G013 — suivi des commandes incertaines

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G013](../../../../collaboration/tasks/C-TASK-G013.md).
Base : `476acc1` (contient C-008b de Codex, l'intégration G011 et le correctif D3).
Fichiers modifiés : `desktop/prototype/model.js`, `app.js`, `styles.css`,
`README.md` et ses tests. Ni `src/`, ni `tests/` Python, ni les preuves de
Codex ne sont touchés.

## Défaut corrigé

Reproduit par Codex (`codex-g009-review/probe-command.cjs`), et confirmé ici
par la lecture du code de `111da40`. La fenêtre ne suivait qu'**une** commande
(`client.command`). Après un accusé perdu, cliquer « Révoquer » ou « Demander
l'annulation » remplaçait la commande d'accord encore incertaine. Son reçu
n'était plus consultable.

Correction : une entrée par clé dans `client.commands`, avec sa propre phase.
La politique complète est dans le [README du prototype](../../../../desktop/prototype/README.md#suivi-des-commandes-c-task-g013).

## Exécuté

```sh
cd eidolon-core
CAPTURES=$PWD/docs/validation/2026-10-06/claude-g013/captures \
NODE_PATH=/opt/node22/lib/node_modules node --test --test-reporter=spec "desktop/prototype/tests/*.test.js"
```

Node 22.22.0, Playwright 1.56.1, Chromium, Linux.
[Sortie](tests-output.txt) : **39 tests, 39 réussis**. Détail : 17 tests G009
du modèle, inchangés hormis le nom du champ ; 11 nouveaux tests G013 ;
10 tests UI G009 ; 1 nouveau test UI G013.

Tests G013 demandés par la fiche :

| Demande de la fiche | Test |
| --- | --- |
| accord inconnu + révocation | « G013 reproduction inverted… » et test UI G013 |
| accord inconnu + annulation | « …cancellation request is allowed and tracked independently… » |
| double clic révocation/annulation | « …double click on revoke or cancel… » |
| réponses hors ordre | « …out-of-order replies each settle their own command » |
| doublon de reçu, réponse tardive | « …duplicate and late replies never change a resolved command… » |
| reçu pour clé inconnue | « …a reply for an unknown key is counted and changes nothing » |
| pas de réémission | chaque test vérifie le nombre de `DECIDE`, `REVOKE` ou `CANCEL_REQUEST` envoyés |
| politique de rétention | « G013 retention… » : 25 commandes résolues → 10 gardées, la non résolue gardée |

Ajouts alignés sur C-008b : un reçu introuvable reste incertain et bloque toute
nouvelle décision (« …receipt not found… ») ; un refus du serveur est une
réponse définitive pour cette clé seulement (« …server refusal… ») ; une
coupure ne transforme jamais une consultation en renvoi (« …disconnection… »).

## Sonde de Codex

- [Sonde d'origine rejouée](codex-probe-after.txt) : elle échoue à sa ligne 15,
  parce que `client.command` n'existe plus. C'est un échec de **structure** :
  il ne mesure pas le comportement, et je ne le présente pas comme une preuve.
- [Copie adaptée](probe-command-adapted.cjs) : même scénario, sur
  `client.commands`, avec des assertions inversées (comportement corrigé).
  [Sortie](probe-command-adapted.json) : pour la révocation comme pour
  l'annulation, l'accord incertain reste suivi puis se résout par son reçu.
  Un seul `DECIDE` est envoyé.

## Contre-vérification D3 (demandée en C-MSG-G025)

[d3-counter-check.txt](d3-counter-check.txt) : `probes_g011.py` rejoué sans
modification sur `476acc1`. Horloge figée à 237.965 : lecture réussie
(statut 200, un contact), au lieu de `ContractError` / `READER_ERROR`. C'est la
seule différence avec la sortie G011 d'origine (hors durées). D3 est corrigé.

## Capture

[08](captures/08-g013-revocation-et-accord-incertain.png) : révocation
enregistrée et accord encore « à vérifier », avec son bouton de reçu actif.
Les captures 01 à 07 sont régénérées par la même exécution.

## Non vérifié

Les commandes restent simulées. Pas de raccordement au vrai contrat C-008b,
qui relève de G012 ou d'une suite. Chromium sous Linux seulement.
