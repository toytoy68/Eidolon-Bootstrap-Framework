# Validation C-004a / C-001b — Codex/GPT

Exécutée le 05/10/2026 dans le conteneur Linux, Python 3.12.14.
Base Core : `7800b10588a84d46410437ba7795b3ababbb6b67` ; résultats pour le lot
contenant ce rapport, avant publication. Aucune mesure sur VM ou GPU.

| Périmètre | Résultat | Preuve |
| --- | --- | --- |
| Core : 102 tests existants + 19 nouveaux tests diagnostic | 121 réussis, aucun ignoré | [Journal](core-tests.txt) |
| API Memory Engine réelle, copie isolée, données synthétiques | 6 réussis | [Journal](memory-tests.txt) |
| Démonstration de cinq missions, assertions exécutées | UP, DOWN, UNREACHABLE vérifiés ; ambiguïté et permission refusées | [Sortie JSONL](demo.jsonl) |

Commande Core depuis `eidolon-core/` :

```bash
PYTHONPATH=src:. python -m unittest tests.test_core tests.test_review_regressions tests.test_counter_review tests.test_objectives tests.test_targets tests.test_ollama_model tests.test_integration_review tests.test_diagnostics -v
PYTHONPATH=src:. python -m examples.service_diagnostic_demo
```

Commande d'intégration : `EIDOLON_MEMORY_INTEGRATION=1`,
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src:.:/chemin/memory-reference`,
`python -m unittest tests.test_memory_engine -v`.
Dépendance observée : `7d99ded07b7e10aa8029655ce4a939af6e0a6c44`, copie propre
avant et après. Ces six tests exercent l'adaptateur de rappel et la mission de
statistiques sur les vrais services mémoire locaux, sans corpus utilisateur ;
ils ne qualifient pas un accès mémoire distant ni le nouveau diagnostic avec
une mémoire distante. Aucun fichier canonique existant modifié.

Les tests diagnostic sont simulés. La péremption à la reprise utilise une
horloge injectée dans le vérificateur ; aucun reçu n'est falsifié pour cet essai.
Les cas de reprise diagnostic injectent une interruption aux frontières durables.
La suite historique conserve ses essais réels de processus/SIGKILL et ses faux
transports Ollama, dont loopback local. Aucun modèle réel n'est exécuté.

Non exécuté : GPU/V100/NVLink, Ollama réel, VM100, NAS, Windows, réseau personnel,
Internet applicatif, reboot et coupure physique. Aucune installation Bootstrap,
aucun déploiement et aucune fusion dans main.
