# Reprise bêta — Codex, 07/10/2026

Base : Core 0890820, Claude 310d94b. Fusion locale 1325d09 ; arbre
`a82b89e07944b97aa9dd1eb0d1b5e57b12ce3703` publié à l'identique sur bfd78a8,
avec les deux parents Core/Claude conservés. Environnement Linux, Python
3.12.14, Node 24.19.0. Aucune VM, Windows, SSH ou installation système.

## C-010a — intégration G036–G041

Six lots Claude lus et intégrés sans conflit, messages/archives intacts.
37 tests connectés reproduits et 12 Chromium non exécutés :
[avant correctifs](connected-integration.txt). Les 49 PASS annoncés par Claude
sur son environnement ne sont pas attribués au présent environnement.
G041 reste une étude, aucun endpoint d'écriture activé.

## Corrections C-010b–e

- F-G039-1 : capacité occupée → réponse 503 BUSY fixe, pré-authentification,
  sans consultation SQLite ni nouveau worker ; écriture bornée à 50 ms.
  Refus explicite et récupération du service éprouvés sur sockets réelles.
  Connexion déjà morte/non inscriptible : livraison du refus non garantie.
- Budget SQLite coopératif 2 s par connexion, callback toutes les 1000
  instructions. Requête récursive coûteuse interrompue ; lecture suivante
  possible et base inchangée. Pas de délai dur sur E/S disque ou calcul Python.
- Banc Node : erreur de spawn prise en charge, stderr drainé, démarrage en
  délai → arrêt attendu, TERM puis KILL si nécessaire sur le seul enfant.
  [Tests lifecycle et intégration](lifecycle-tests.txt) : 8 réussis, 1 Chromium ignoré.
- Lanceur candidat : après `cd`, les chemins relatifs restent ancrés au home
  distant ; les absolus restent absolus. Sept [contrôles statiques](launcher-static.txt),
  **aucune exécution PowerShell ou Windows**. La correction ne vaut pas recette SSH.

49 [tests API ciblés](http-targeted.txt) réussis. Pas d'augmentation des quatre
connexions, ni relecture automatique ajoutée au client.

## C-010f/g — recette et paquet

`python -m eidolon_core.beta_check --web-root desktop/connected` remplace la
nécessité de lancer une preuve historique depuis son dossier exact : 24
contrôles, JSON pur par défaut, pas de dépendance Git/cwd, assets explicites.
[Rapport source](recipe-source.json) et [trois tests du contrat/nettoyage](recipe-tests.txt).
Les tests couvrent également un démarrage serveur refusé et l'absence de fuite
de chemin/diagnostic brut dans le rapport.

[package-smoke.py](package-smoke.py) construit un wheel hors réseau dans une
copie temporaire, installe dans un venv neuf et vérifie 38 modules octet pour
octet, le point d'entrée CLI et les mêmes 24 contrôles. [Rapport](package-smoke.json).
Le wheel ne contient pas les assets Web ; ils proviennent explicitement du
checkout testé. Ce n'est pas une archive/release bêta publiée (G044).

## C-010h/i — documentation et validation finale

Parcours, contrats HTTP et TODO actualisés ; répartition des 12 tâches dans
[le plan](../../../PLAN-2026-10-07.md).

- `PYTHONPATH=src:. python -m unittest discover -s tests -v` : **621 tests,
  615 réussis, 6 intégrations Memory Engine non exécutées**, 114,641 s.
  [Journal](final-python.txt).
- `node --test desktop/connected/tests/*.test.js desktop/connected/tests/integration/*.test.js` :
  **41 réussis, 12 tests Chromium non exécutés**, zéro échec. [Journal](final-connected.txt).
- `node desktop/connected/build.js --check` : bundle conforme, sources produit
  client inchangées par Codex (réservées à G043).

Les groupes ciblés se recoupent avec les suites, ne pas additionner les totaux.
Le prototype autonome non modifié n'a pas été revalidé ; les anciens échecs de
lancement Chromium ne deviennent pas des validations navigateur par ce lot.
Serveur utilisateur, Debian 13/Python 3.13, Windows, SSH, modèle et intégrations
mémoire réelles restent à vérifier. Aucun succès de mission/effet réel déduit.
