# Validation C-008a — Codex/GPT — 06/10/2026

Base : e25cd2a8856c9a80513100ed1b30bcd013e6c931. Python 3.12.14/Linux.
Code du commit introduisant ce rapport ; [empreintes](source-hashes.json).

- core-tests.txt : **328 tests découverts, 322 réussis, 6 intégrations mémoire
  opt-in sautées**, 81,715 s. Aucun accès moteur mémoire dans ce lot.
- targeted-tests.txt : **19 tests réussis**, dont le cas de
  concurrence : une seconde connexion SQLite/WAL écrit l'annulation exactement
  entre lecture de la mission et lecture du journal. Cette intercalation est aussi
  couverte par la suite complète finale ; nombres hors précision JS refusés.
- demo.json : trace JSON complète d'une mission synthétique, capture avant
  exécution, cinq pages de deux événements, répétition d'une page et reset.
- demo-human.txt : seconde exécution indépendante du même scénario, affichage
  standard Eidolon ; les UUID et heures diffèrent normalement entre exécutions.

Couvert : aucune mutation par lecture, pagination/duplicats, reprise avec une
nouvelle instance Store, annulation sans changement de révision, événements
d'autres missions intercalés, champs privés exclus, curseurs invalides/étrangers,
base changée, ancre modifiée, retour en arrière, préfixe supprimé, migration
additive d'une base sans métadonnées, CLI sans Runtime et proposition PENDING
préservée sans redémarrage du service simulé.

Commandes depuis eidolon-core/ :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m unittest tests.test_client_sync -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m examples.client_sync_demo --format human
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m examples.client_sync_demo
```

Ce sont des fichiers SQLite temporaires et des missions/outils synthétiques.
Aucun réseau dans la démo C-008a ; la suite générale inclut les anciens tests
HTTP/TLS loopback. Ni authentification ni serveur Desktop, poste Windows,
modèle/GPU, NAS ou VM qualifié. Le simulateur de coupure conserve simplement
le curseur pendant que Core progresse. Les droits réseau futurs restent absents.
[Contrat et limites](../../../CLIENT-SYNC.md).
