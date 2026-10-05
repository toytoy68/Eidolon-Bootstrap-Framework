# Preuves — intégration Claude C-MSG-C009

Codex/GPT, 05/10/2026, Europe/Paris. Linux conteneur, Python 3.12.14.
Base Claude : `c2792d6bd0dd9595c9b187af6544b13b8914c20f`.
Corrections : commit introduisant ce dossier. Le texte d'aide CLI et les
rapports ont été actualisés après les tests ; aucun autre code changé ensuite.

| Exécution | Résultat | Journal |
| --- | --- | --- |
| Base Claude, avant correction | 94 tests OK, 52,051 s | [baseline-tests.txt](baseline-tests.txt) |
| Suite finale, dont huit nouvelles régressions | 102 tests OK, 52,642 s | [core-tests.txt](core-tests.txt) |
| API réelle Memory Engine, corpus synthétique | 6 tests OK, 1,359 s | [memory-integration.txt](memory-integration.txt) |
| Sondes options/catalogue/erreur après effet | Défaillances reproduites puis corrigées | [avant](probes-before.txt), [après](probes-after.txt), [script](review_probes.py) |
| Démo de contrat C-001a | Quatre issues conformes | [objective-demo.json](objective-demo.json) |

Commandes depuis `eidolon-core/` :

```sh
PYTHONPATH=src:. python -m unittest tests.test_core tests.test_review_regressions tests.test_counter_review tests.test_objectives tests.test_targets tests.test_ollama_model tests.test_integration_review -v
EIDOLON_MEMORY_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="src:.:$EIDOLON_MEMORY_SOURCE" python -m unittest tests.test_memory_engine -v
PYTHONPATH=src:. python docs/validation/2026-10-05/codex-claude-integration/review_probes.py
PYTHONPATH=src:. python -m examples.objective_demo
```

La commande baseline omet `tests.test_integration_review`, absent de c2792d6.
La sonde avant/après est identique. Après correction, model_id reste inchangé
parce que l'objet de configuration n'a plus changé ; le test séparé de remplacement
de configuration vérifie que son changement effectif bloque la reprise.

La copie isolée Memory Engine est au commit
`7d99ded07b7e10aa8029655ce4a939af6e0a6c44`, Git propre avant/après. Les services
coordonnés créent uniquement les fixtures temporaires des tests ; pas de données
utilisateur ni de modification de son dépôt. Aucune nouvelle qualification des
imports sur sa dernière tête distante n'est annoncée.

Les tests Ollama exécutent du HTTP réel **uniquement sur loopback** avec un faux
serveur. Les plans/erreurs sont synthétiques ; pas de vrai moteur Ollama ou LLM.
Non exécuté : VM, NAS, Windows, GPU, NVLink, réseau personnel, Python 3.11/3.13
sur ce lot Codex, benchmark d'inférence, coupure électrique. Les tests Python
3.11.15 de Claude restent des résultats rapportés dans ses propres journaux.
