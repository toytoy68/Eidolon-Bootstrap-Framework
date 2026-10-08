# Reprise Core du 08 octobre 2026 à 04 h 35 Paris

Base fdf1123b00e13bc1fed7fc88bca12f49d726b242, Python 3.12.14/Linux,
Node 24.19.0. Checkout séparé ; Memory Engine b33c3a0 en référence seulement.

- baseline-python.log : 840 tests découverts, 834 réussis, six intégrations mémoire ignorées.
- ollama-before.log : dix nouveaux tests, 28 sous-cas en échec et six erreurs
  avant correctif ; canaries entièrement synthétiques.
- ollama-after.log : 68 tests associés réussis après C-034, dont dix nouveaux.

Commandes depuis eidolon-core :

```sh
PYTHONPATH=src:. python -m unittest discover -s tests -t . -q
PYTHONPATH=src:. python -m unittest tests.test_ollama_boundaries tests.test_ollama_model tests.test_model_config tests.test_integration_review tests.test_openai_chat_model tests.test_openai_chat_boundaries -v
```

Aucun fournisseur, modèle, GPU, serveur utilisateur, VM ni client Windows réel
contacté ou qualifié. Les sources et journaux du prototype Claude sont préservés.
C-BRAIN-G012 reste une proposition, sans choix anticipé.

## C-035 — rapports de qualification

qualification-cli.log : 32 tests réussis (20 existants et 12 nouveaux). La
commande qualification-check n'initialise ni Store, ni runtime, ni modèle.
Fichiers modifiés/remplacés, FIFO, liens, dépassements, erreurs privées et
fermeture déterministe vérifiés. Une origine hardware_reported reste déclarative.

## C-036 — candidat llama-server en CLI

llama-cli.log : 32 tests réussis, dont 11 nouveaux. Les sous-processus CLI
contactent seulement un faux serveur HTTP loopback : succès, reprise sans
réémission, configuration changée, clé absente/invalide et erreurs sans reflet.
Aucun choix de moteur ni activation par défaut. Nom de variable de clé seulement.

## C-037 — cadrage et erreurs de lecture HTTP

model-http-before.log : sept tests, 36 sous-cas en échec et sept erreurs avant
correctif. Un EOF pouvait être accepté malgré un Content-Length plus grand,
et la lecture d'un corps HTTPError échappait au diagnostic normalisé.
model-http-after.log : 62 tests réussis, dont huit du nouveau module HTTP ;
en-têtes ambigus refusés, corps incomplet refusé, erreurs 500 normalisées et
reprise de missions /2 refusée sous manifestes /3. HTTP synthétique uniquement.

## Vérification de l'ensemble et du paquet — 05 h 05 Paris

python-full.log : étape intermédiaire C-034/C-035, 862 découverts,
856 réussis et six ignorés. Ce n'est pas la preuve du dernier état C-036/C-037.

python-final-with-memory.log : **881 tests réussis, aucun ignoré** en 161,319 s.
La référence Memory Engine b33c3a0 est injectée explicitement par PYTHONPATH,
avec EIDOLON_MEMORY_INTEGRATION=1 ; seuls des corpus temporaires synthétiques
sont utilisés. Les six tests mémoire avaient aussi été exécutés séparément
(memory-integration.log). Ce n'est pas un essai sur le corpus privé de toytoy.

installed-check.py/json : build de wheel sans réseau, installation dans un venv
neuf, 49 modules identiques aux sources. Trois verdicts CLI avec codes 0/2/3,
état absent préservé et empreinte exacte. Ollama et llama-server factices : un
appel chacun, reprise inchangée sans réémission, clé synthétique absente de
l'état. Recettes installées : missions 24/24, recherches/archives 25/25.
Environnement temporaire supprimé. Les sources client n'ont pas été modifiées ;
les tests Node/Chromium n'ont pas été rejoués dans ce lot.

```sh
PYTHONPATH=src:. python -m unittest tests.test_qualification_cli tests.test_qualification tests.test_qualification_boundaries -v
PYTHONPATH=src:. python -m unittest tests.test_llama_model_config tests.test_model_config tests.test_qualification_cli -v
PYTHONPATH=src:. python -m unittest tests.test_model_http tests.test_ollama_model tests.test_openai_chat_model tests.test_llama_model_config tests.test_model_config -v
PYTHONPATH=src:.:/chemin/vers/memory-engine EIDOLON_MEMORY_INTEGRATION=1 python -m unittest discover -s tests -t . -q
python docs/validation/2026-10-08/codex-hour-0435/installed-check.py
```
