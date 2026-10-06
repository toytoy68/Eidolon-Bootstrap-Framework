# Preuves de l'audit Codex du 06/10/2026

[Rapport et périmètre](../../../AUDIT-2026-10-06.md).

Depuis eidolon-core/ :

```sh
PYTHONPATH=src python -m unittest tests.test_audit_regressions -v
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src:. python -m examples.cancel_receipt_demo --format human
PYTHONPATH=src:. python -m examples.research_pauses_demo
```

- before.txt : mêmes dix régressions avec sources extraites du commit
  32f1c8d243bbeb3d4ece7da0e0b9b633dc85332e dans un répertoire temporaire.
  Dix méthodes, 18 échecs de sous-cas, six erreurs ; échec attendu.
- after.txt : dix régressions réussies sur les sources corrigées.
- full-tests.txt : 437 tests, 431 réussis, six intégrations mémoire sautées.
- cancel-demo.txt / pauses-demo.json : démonstrations exécutées après correction.
- source-hashes.json : SHA-256 des sources de la revue et des régressions.

Les tests sont dans tests/test_audit_regressions.py. Pour reproduire avant
correction, extraire src/ depuis le SHA initial dans une copie isolée et utiliser
son chemin src dans PYTHONPATH, tout en exécutant les nouveaux tests depuis
la racine Core courante. Aucune installation système ni ressource utilisateur.
