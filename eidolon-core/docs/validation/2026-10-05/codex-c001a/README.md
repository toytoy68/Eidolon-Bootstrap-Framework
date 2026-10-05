# Validation C-001a — Codex/GPT

Exécution locale du 05/10/2026, Linux conteneur, Python 3.12.14.
Base code `3cb1ae551fcbeb16badbf6e2110901928ea0a618`, parent documentaire
`9620c478da5aa22ff5530628c10c5fba01404512`. Code vérifié : commit introduisant
ce dossier (documents/résultats ajoutés après exécution). Aucun avis Claude reçu.

| Vérification exécutée ici | Résultat | Preuve |
| --- | --- | --- |
| Suite Core, dont 11 nouveaux cas de contrat | 69 tests, OK, 49,076 s | [core-tests.txt](core-tests.txt) |
| API réelle Memory Engine sur corpus synthétique isolé | 6 tests, OK, 1,139 s | [memory-integration.txt](memory-integration.txt) |
| Démo couverture, refus, clarification, annulation partielle | 4 issues attendues, OK | [objective-demo.json](objective-demo.json) |
| CLI JSON/humain et sortie bloquée | Succès code 0, clarification code 2 | [cli-demo.json](cli-demo.json), [cli-human.txt](cli-human.txt), [cli-clarification.json](cli-clarification.json) |

Depuis `eidolon-core/` :

```sh
PYTHONPATH=src:. python -m unittest tests.test_core tests.test_review_regressions tests.test_counter_review tests.test_objectives -v
PYTHONPATH=src:. python -m examples.objective_demo
EIDOLON_MEMORY_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="src:.:$EIDOLON_MEMORY_SOURCE" python -m unittest tests.test_memory_engine -v
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-c001a demo
PYTHONPATH=src python -m eidolon_core --format human --state /tmp/eidolon-c001a show m-ID
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-c001a create 'Vérifier le service du NAS.'
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-c001a run m-ID-HORS-CATALOGUE
```

Remplacer les IDs par ceux renvoyés ; chaque démo crée une mission distincte.
Pour les captures CLI jointes, même séquence dans un répertoire temporaire,
JSON parsé et assertions sur statut/issue/sources/codes de retour ; état supprimé
après sauvegarde des captures. La démo objective_demo vérifie elle-même ses issues.

`EIDOLON_MEMORY_SOURCE` désigne ici une copie isolée au commit
`7d99ded07b7e10aa8029655ce4a939af6e0a6c44`, état Git propre avant/après.
Les tests utilisent ses services coordonnés et leur rappel sur des données
synthétiques temporaires ; aucune modification de son code ni écriture canonique
manuelle. Ce n'est pas une qualification des trois défauts d'import/rappel sur
la dernière branche distante : voir la TODO pour leur suivi séparé.

Les tests historiques à deux/cinq étapes utilisent maintenant deux/cinq références
distinctes. La régression de volume garde cinq reçus de 600 ko et son vérificateur
synthétique de confiance ; elle mesure la persistance, pas la sémantique text.stats.
Les doublons sont désormais un cas rouge explicite, plus un succès attendu.

Cas T-1/T-3/T-4/A-2 de Claude couverts dans le périmètre restreint C-001a :
demande incompatible, couverture incomplète, répétition et mémoire vide. Pour T-3,
le plan incomplet est refusé avant exécution, donc NON_ATTEINT ; PARTIEL est réservé
aux résultats déjà vérifiés. Les scénarios produit A–D complets restent ouverts.

Non exécuté : VM100 `192.168.1.135`, Debian/Python 3.13, NAS, session Windows,
Internet réel, Ollama/GPU/modèle réel, charge générale, coupure électrique.
Aucun déploiement ou fusion main. Les résultats de Claude restent attribués dans
leurs rapports antérieurs ; les chiffres ci-dessus sont ceux exécutés par Codex.
