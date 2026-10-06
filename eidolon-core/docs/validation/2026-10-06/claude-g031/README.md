# G031 — client de consultation connecté : preuves

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G031](../../../../collaboration/tasks/C-TASK-G031.md).
Base : `4d0f606` (API publiée `21c0f729`, `http_api.py` inchangé).
Livrable : [desktop/connected/](../../../../desktop/connected/README.md). Ni
`src/`, ni `tests/` Python, ni `desktop/prototype/` modifiés.

Environnement : Linux, Python 3.11.15, Node 22.22.0, Playwright 1.56.1 avec
Chromium headless. Aucun réseau hors `127.0.0.1` ; états Core synthétiques
créés par la CLI dans des dossiers temporaires. Jetons aléatoires créés par
les tests, en fichier 0600, jamais écrits dans les sorties.

## Résultats

- [node-tests.txt](node-tests.txt) : **20/20** tests du client.
  - 14 sur **transport scripté** (fixtures) : format du jeton, pagination et
    arrêt à 3 pages, reset de liste, 401, 403, 503, 400, panne réseau,
    reconnexion même base ou **autre base**, liste d'une autre base,
    sélection obsolète, déconnexion, `poll` avec `has_more` puis
    `RESET_REQUIRED`, réponse qui revendique une autorité, identifiant
    malformé.
  - 6 sur le **vrai serveur** `http_api` :
    - les assets servis sont identiques aux fichiers, et `app.js` est à jour ;
    - liste de 4 missions réelles, capture, puis annulation écrite par un
      **autre processus** (CLI Core) et vue par `poll` puis par la liste ;
    - mauvais jeton → 401 ; serveur arrêté → hors ligne, données gardées ;
      serveur relancé → reprise sans effacement ;
    - autre état derrière la même adresse → affichage effacé ;
    - Chromium : parcours complet, puis serveur arrêté ;
    - Chromium par un autre `Host` → 403.
- Prototype inchangé : 92/92 tests (`desktop/prototype/tests`).
- [mutations-output.txt](mutations-output.txt) : quatre garde-fous retirés un à
  un ([mutations.py](mutations.py)). Chacun fait échouer au moins un test.

Le parcours Chromium a aussi vérifié :

- le champ jeton est vidé ;
- `localStorage`, `sessionStorage` et les cookies sont vides ;
- le jeton est absent du DOM ;
- aucun bouton de commande n'existe ;
- toutes les requêtes restent sur la même origine ;
- il n'y a pas de défilement horizontal à 390 px ;
- il n'y a aucune erreur console, hors pannes réseau voulues.

## Captures (serveur réel, données synthétiques)

- [bureau, mission en attente de décision](g031-connected-desktop.png)
- [mobile 390 px, annulation vue après « Actualiser »](g031-connected-mobile.png)
- [mobile, serveur arrêté : état gardé et marqué périmé](g031-connected-offline.png)

## Limites

- Pas de tunnel SSH, de Windows ni de navigateur autre que Chromium headless.
- La liste n'est relue que sur demande : son libellé peut retarder sur le
  détail (visible sur la capture mobile).
- Pas d'audit automatique du contraste ni du parcours clavier, contrairement
  au prototype. Seules les captures ont été relues à l'œil.
- Le serveur reste mono-requête : la relecture toutes les 10 s n'a pas été
  mesurée sous charge.
