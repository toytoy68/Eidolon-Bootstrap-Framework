# Validation C-008b — reçus de décisions

Auteur : Codex/GPT. Exécution le 06/10/2026, avant 05:19 UTC (07:19 Europe/Paris,
heure consultée sur l'horloge). Base Git `37604a10f7e3252eae1e13478bc91a79a62c651b` ;
code final identifié par [source-hashes.json](source-hashes.json).
Environnement : Python 3.12.14, Linux/POSIX, SQLite local au conteneur.

## Exécuté dans cette session

Depuis eidolon-core/, PYTHONDONTWRITEBYTECODE=1 :

```sh
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
PYTHONPATH=src:. python -m examples.command_receipt_demo
PYTHONPATH=src:. python -m examples.command_receipt_demo --format human
```

- [Suite complète](core-tests.txt) : 350 tests découverts, **344 réussis**, six
  intégrations Memory Engine opt-in sautées ; 90,808 secondes. Les **22 tests
  nouveaux** de tests.test_commands sont inclus dans ce journal.
- [Démo JSON](demo.json) : accusé perdu après commit, reçu FOUND à la réouverture,
  duplication explicite sans nouvel événement, zéro effet avant run séparé,
  une décision et un lancement d'outil ; mission finale SUCCEEDED/ACHIEVED.
- [Démo humaine](demo-human.txt) : même scénario avec un nouvel état temporaire,
  présentation ECT commune. Les UUID/horaires des deux exécutions diffèrent.

## Risques visés par les tests

Deux enfants Python quittent réellement via os._exit : code 73 dans un trigger
SQLite avant insertion du reçu (transaction inachevée), code 74 au checkpoint
COMMAND_RECORDED après commit. Le premier ne laisse ni décision ni nouvel
événement ; le second laisse un reçu durable malgré l'absence de réponse.
Ces injections ne prétendent pas simuler une coupure électrique.

La concurrence entre deux missions utilise une barrière après validation et
avant écriture : même client/clé, une décision validée, une transaction annulée.
Annulation, révision et identité du Store changées entre préparation et commit
sont refusées sans faux reçu. Une erreur SQL au point d'insertion du reçu annule
également l'événement et la modification de mission.

Reçus historiques après exécution/révocation, consultation sous verrou de
mission, copie indépendante, conflits de contenu, portée client, JSON mal formé,
UTF-16, doublons, nombres non finis, profondeur excessive, bornes JS et CLI de
lecture sans Runtime sont testés. NOT_FOUND n'autorise aucune réémission.

## Hors de cette validation

Aucun nouvel essai Memory Engine réel, GPU/modèle réel, Windows, VM100, NAS ou
Internet public. Les anciens tests de transports locaux de la suite utilisent
leurs fixtures/serveurs de test. Aucun test graphique Node/Chromium relancé :
le prototype n'a pas changé. Aucune preuve d'authentification distante, de
stockage physique après coupure, de détection générale d'une restauration ou
d'exécution exactement une fois d'un outil externe.

Contre-revue Claude G014 demandée, pas encore reçue.
