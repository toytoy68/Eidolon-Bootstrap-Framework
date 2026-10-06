# Validation C-008c — annulation avec reçu

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Python 3.12.14/Linux.
Base `476acc1cc2d9358f921c2ffc9387ec0c190576d3` ; code testé identifié par
[source-hashes.json](source-hashes.json). Aucun fichier Memory Engine modifié.

Exécuté depuis eidolon-core/, avec PYTHONDONTWRITEBYTECODE=1 :

```sh
PYTHONPATH=src:. python -m unittest tests.test_cancel_commands -v
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
PYTHONPATH=src:. python -m examples.cancel_receipt_demo
PYTHONPATH=src:. python -m examples.cancel_receipt_demo --format human
```

[20 tests ciblés](targeted-tests.txt), puis [suite complète](core-tests.txt) :
370 tests découverts, **364 réussis et six intégrations mémoire opt-in sautées**,
94,981 secondes. [Démo JSON](demo.json) et [présentation humaine](demo-human.txt)
exécutées avec des états temporaires indépendants ; les UUID/horaires diffèrent.

## Vérifications décisives

- Demande enregistrée sous verrou de mission sans Runtime ; flag observable
  à révision constante via ClientSync, reçu historique conservé après annulation.
- Rejeu exact sans événement supplémentaire ; concurrence sur la même clé
  (même mission ou missions distinctes), conflit avec une clé d'approbation.
- Annulation commise pendant préparation d'un accord : accord refusé, reçu
  d'annulation conservé. Demande commise après RESULT_VERIFIED et avant le commit
  final : pas de succès, résultats d'appel conservés, résultat final absent.
- Succès déjà commis : intact, reçu ALREADY_TERMINAL. Idem pour FAILED,
  CANCELLED et ABANDONED synthétiques ; annulation déjà demandée distinguée.
- Enfant effectuant un redémarrage **dans la base de simulation locale** puis
  attendant : annulation reçue pendant son exécution, REVIEW_REQUIRED,
  preuve du redémarrage conservée, aucune deuxième exécution. Ce test emploie
  l'injection FaultAction existante ; ce n'est pas un arrêt d'un service réel.
- Appel interrompu au marqueur de lancement : annulation ne supprime pas
  UNKNOWN_EFFECT. Coupures de processus os._exit avant et après commit :
  aucune transaction partielle, ou reçu retrouvé malgré l'accusé perdu.
- Erreur SQL et dépassement des entiers sûrs JSON : rollback du flag, événement
  et reçu. Entrées/JSON invalides, Store changé, mission absente refusés.
- CLI humaine INFO, jamais OK pour le seul reçu ; aucune base créée si absente.

## Limites

Aucun essai de coupure électrique, disque physique, NAS, VM100, Windows ou modèle
réel. Les tests Web existants utilisent leurs doubles/serveurs locaux. Memory
Engine non revalidé par ce lot. Aucun appairage ni identité distante, aucune
preuve d'arrêt externe ou d'absence d'effet déduite d'un reçu d'annulation.
Les exceptions SQLite restent celles du Store interne (une panne SQLite peut
remonter en traceback dans la CLI) ; après erreur, consulter l'état/le reçu,
ne pas en déduire que le commit n'a pas eu lieu. Diagnostic CLI plus homogène
à traiter avec la frontière de transport. Rétention/génération après restauration
restent ouvertes. [Contrat](../../../CANCEL-RECEIPTS.md).
