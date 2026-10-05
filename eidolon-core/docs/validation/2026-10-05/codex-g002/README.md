# Intégration du validateur G002 — Codex/GPT

Base Claude : `bc6d153`, intégrée via `a273f3c`. Python 3.12.14, Linux, 05/10/2026.
Lecture du module, des 16 tests et du contrat ; tests Claude reproduits.
Les cinq sondes d'entrée ont produit les [résultats avant correction](before.txt).
Correctifs : UTF-8 strict/fini sur tout le document, type de métrique, nombres
représentables, domaines physiques, corpus vide incomplet. Quatre tests nouveaux
avec sous-cas. [20 tests réussis](tests.txt), sans GPU ni télémétrie réelle.

```bash
PYTHONPATH=src:. python -m unittest tests.test_qualification tests.test_qualification_boundaries -v
```

Aucun seuil matériel adopté ; un rapport cohérent ne prouve pas son authenticité.
La publication de critères dans le rapport ne prouve pas leur antériorité réelle.
La contre-revue G001 a été lue ; ses sondes restent attribuées à Claude, la suite
Core complète sera rejouée avec C-005a. O-1/O-2 ne sont pas des garanties nouvelles.
