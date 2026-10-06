# Séance Codex/GPT du 06/10/2026 — intégration et préparation bêta

Tranche demandée par toytoy : 19 h 36–20 h 36 Europe/Paris, puis publication
sur `feat/eidolon-core-v0.1` et reprise demain. Base distante initiale
`6ae125cfd26564acebf97f6ee697ceaddf676435`. Environnement des preuves Codex :
Linux, Python 3.12.14, Node 24.19.0. Aucun installateur, service système,
serveur utilisateur, NAS, GPU ou déploiement exécuté.

## Intégration Claude

G032/C046 et G033/C047 intégrés depuis `6f8b695`, puis G034/C048 et G035/C049
depuis `c73f788`. Les messages et preuves signés Claude restent conservés.

- **HTML** : 24 tests reproduits, [journal](html-tests.txt). Corrections de
  l’extracteur seul ; raccordement au WebReader toujours différé.
- **APT** : 23 cas reproduits, [journal](apt-boundaries.txt), syntaxe des trois
  scripts Bootstrap vérifiée. Seule la fonction extraite travaille sur des
  fichiers fictifs ; aucun installateur exécuté ou sourcé.
- **API figée G034** : constat D-G034-1 utilisé pour C-009e, puis 81 réponses
  brutes examinées avec le correctif : [sondes rejouées](g034-probes-after.txt).
  M1/M2 obtiennent health immédiatement ; contrôles de fuite négatifs. Les
  mutations constatées dans J2 comprennent les commandes CLI du banc ; l’API
  seule ne modifie pas l’état.
- **Recette G035** : procédure intégrée ; ajouts Codex signés, dossiers uniques,
  création du jeton par CLI et correction des limites de disponibilité.
  Les anciennes preuves Claude ne sont pas présentées comme une exécution
  des retouches Codex. Windows, SSH et serveur de toytoy restent à tester.

## Lots Codex

| Lot | Résultat | Preuves |
| --- | --- | --- |
| C-009d | Jeton privé créé complet, sans remplacement ; échec après publication distingué d’un fichier absent | [52 tests ciblés](token-tests.txt), puis [15 tests jeton](token-final-tests.txt) après correction de fermeture de descripteur |
| C-009e | Quatre connexions actives au maximum, 3 s d’inactivité, 5 s de lecture totale ; arrêt des lectures et jonction des workers | [Défaut reproduit](preconnect-before.txt), [65 tests](http-availability-tests.txt), sondes G034 |
| C-009f | Identité JSON liée à la ligne SQL, champs exportés typés/bornés, doublons refusés | [Deux échecs avant correction](projection-before.txt), [91 tests après](projection-tests.txt) |
| C-009g | Six missions synthétiques et trois requêtes de reçu, création exclusive, garde des états incomplets | [8 tests dédiés](beta-fixture-tests.txt), [73 tests API/recette](fixture-http-tests.txt), [contrat](../../../BETA-FIXTURE.md) |

Les journaux avant correction sont des preuves de défauts résolus, pas le
résultat final. Les nombres des groupes ciblés se recoupent : ne pas les sommer.
Les lots n’ajoutent aucune commande distante à l’API.

## Vérification globale et parcours réel local

Sur le code local `8163a3e8cb99af413361c81e56f933141fef9845` :

```sh
PYTHONPATH=src:. python -m unittest discover -s tests -v
```

**614 tests : 608 réussis, 6 intégrations Memory Engine non exécutées**,
115,679 s. [Journal final](final-python-tests.txt). Le
[premier passage](full-python-tests.txt), avant C-009g, contenait 606 tests,
600 réussis et les mêmes six non exécutés.

Le [script de recette](recipe-smoke.py), exécuté depuis `eidolon-core/`,
utilise exclusivement ses dossiers temporaires et ses propres processus :

```sh
PYTHONPATH=src python docs/validation/2026-10-06/codex-evening/recipe-smoke.py
```

**24 contrôles réussis**, [journal](recipe-smoke.txt) : préparation, diagnostic,
assets, refus sans jeton, six missions, trois reçus, bases inchangées pendant
la lecture, création/annulation locale visibles, redémarrage conservant
identité et curseur. Le serveur lancé garde son jeton initial ; après arrêt et
redémarrage explicite avec le nouveau fichier, seul le nouveau jeton est accepté.
Le code CLI 4 d’une annulation terminée est attendu, pas transformé en succès 0.
Les processus sont arrêtés par leur PID, les fichiers temporaires nettoyés.

## Client et limite navigateur

Le [passage Node global](full-node-tests.txt) sur C-009f contient 112 tests :
**86 réussis, 24 échecs au lancement de Chromium absent, 2 ignorés pour cette
même absence**. Aucune de ces 26 épreuves navigateur n’a validé l’interface.
Les échecs ne sont ni masqués ni présentés comme des tests fonctionnels verts.

Le bundle connecté est conforme (`node desktop/connected/build.js --check`).
Le client connecté est revérifié après C-009g dans
[final-connected-tests.txt](final-connected-tests.txt) : **18 réussis, 2 essais
Chromium ignorés**, dont quatre tests avec serveur réel. Les essais réels locaux
ne constituent pas une recette Windows, un tunnel SSH ni un test navigateur.

## Reprise

Priorité Claude : G036 (reçus), G037 (accessibilité), G038 (navigateur/API),
G039 (mesures), G040 (PowerShell/SSH), G041 (contrat seulement). G042–G044
restent dans la file, sans démarrage implicite d’une session. Codex reprendra
les écarts serveur reproductibles et l’intégration des livraisons, après lecture
du message reçu et contrôle du commit distant.

Les contrats [READ-TOKEN](../../../READ-TOKEN.md),
[HTTP-READ-API](../../../HTTP-READ-API.md),
[HTTP-PREFLIGHT](../../../HTTP-PREFLIGHT.md) et
[BETA-ACCEPTANCE](../../../BETA-ACCEPTANCE.md) décrivent les limites opératoires.
Cette livraison prépare une bêta de consultation ; elle ne qualifie pas encore
le parcours complet PC–serveur ni l’exécution distante.

## Correspondance des commits de livraison

Les commits sont transférés par le connecteur GitHub ; leurs SHA diffèrent des
commits locaux utilisés pour les preuves. **Chaque arbre transféré a été
comparé à son arbre local et est identique.** Les deux fusions conservent le
parent Claude, sans écrasement de son historique. La référence de branche est
mise à jour une seule fois à la clôture, après le commit de bilan, avec contrôle
de son ancienne valeur `6ae125c` ; aucun push forcé.

| Lot | Commit local testé/intégré | Commit GitHub correspondant |
| --- | --- | --- |
| Fusion G032/G033 | `4a909b6` | `434c34aa0df117eadd0e006b742691d2db1150bd` |
| C-009d | `4c1465f` | `219868568b536ff91a911e4f483b8d8cc40ea5ac` |
| Fusion G034/G035 | `931e268` | `8be404ce6865e3724461737e3a8f019b3c3afb62` |
| C-009e | `97cc1e6` | `0dcf932de41c02abde2e70491d3fa062d3aebecb` |
| C-009f | `2a2fa97` | `ff3b3a6c364bf3016e1c77041b361b586727063c` |
| C-009g / code final | `8163a3e` | `57b3823b0636cd9ca626ef049fb79dca7e50c5cf` |

Le commit suivant porte ce bilan, les journaux finaux, le script de recette
et G052. Il ne modifie pas le code de production testé. Les sources locales
avec leurs commits d’origine sont conservées sur une branche de sauvegarde
du checkout, distincte de la branche de travail alignée sur GitHub.
