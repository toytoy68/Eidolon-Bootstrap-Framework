# Prototype de recherche — Codex/GPT — 05/10/2026

## Bases et périmètre

Base de code `c8cd94abd251d11d9cbcd038f47b8f54ef72667a` ; répartition et
brainstorming publiés dans `f0e4a273c11da64656f872769a619a18868596f5`.
Le commit introduisant ce rapport livre le prototype `research.py`.
Python 3.12.14, Linux/POSIX, bibliothèque standard ; données synthétiques.

## Résultats exécutés ici

- `research-tests.txt` : **23 tests réussis**, repli, erreurs et quotas,
  validations d'enveloppes, défi/login HTTP 200, limites, déduplication,
  politique/DNS simulé, cache et copies, suspension de domaine, annulation,
  délai et conservation du reçu. Un test interdit explicitement les API réseau.
- `core-tests.txt` : **264 tests découverts, 258 réussis, 6 sautés**.
  Les six tests sautés sont les intégrations Memory Engine opt-in.
- `demo.jsonl` et `demo-human.txt` : trois scénarios avec assertions : repli
  après quota, lecture réutilisée depuis le cache, résultat partiel lorsqu'un
  défi HTTP 200 ne permet pas d'atteindre deux pages lues.

Depuis `eidolon-core/` :

```sh
PYTHONPATH=src:. python -m unittest tests.test_research -v
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
PYTHONPATH=src:. python -m examples.research_demo
PYTHONPATH=src:. python -m examples.research_demo --format human
```

## Ce que ces résultats ne valident pas

Aucun fournisseur Internet, HTTP/DNS externe, modèle réel, GPU ou machine
personnelle contacté par ce prototype. Les autres tests Core peuvent utiliser
leurs serveurs HTTP loopback simulés habituels. Le module ne fait pas partie
du runtime de mission ; `READ_TARGET_MET` ne signifie pas `SUCCEEDED`.
Pas d'extracteur HTML général ; détection de défi partielle, délai coopératif.
[Contrat complet](../../../WEB-RESEARCH-PROTOTYPE.md).

Memory Engine n'est pas relancé pour ce lot : les six dernières intégrations
réussies contre sa copie `7d99ded07b7e10aa8029655ce4a939af6e0a6c44`
restent consignées dans [codex-g005](../codex-g005/README.md).
La livraison G006 de Claude (`6a972ff`) a été repérée, mais ses tests ne sont
pas reproduits ici et son transport n'est pas intégré par cette tranche.
Sa contribution G007 reste attendue ; aucun avis indépendant n'est présumé.
