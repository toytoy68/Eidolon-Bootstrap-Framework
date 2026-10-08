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

## C-038 et fin de validation de code

model-config-check.log : 37 tests ciblés, dont cinq nouveaux. Inspection privée
sans Store/runtime/réseau, sans accès à la variable contenant la clé (accès
explicitement interdit par le test), état existant préservé. VALID_CONFIG
n'établit pas la disponibilité d'un modèle. Guide et README raccordés.

python-c038-final.log : **886 tests réussis, aucun ignoré**, 160,606 s,
intégration Memory Engine comprise. installed-c038-check.json : 49 modules
installés identiques, contrôles hors ligne des deux configurations puis un seul
appel HTTP factice par fournisseur, reprise sans réémission ; recettes 24+25.
Le rapport installé initial reste conservé comme preuve de C-034–C-037.

## Archive de la première publication

d281745be18709e675c3d59b97c784274b19af61 contient C-034–C-037 et les propositions.
L'arbre Git distant d262d98e7df809b0f77663c66d68dbc554d1ba8d est identique à celui
testé localement. Publication via connecteur GitHub après refus d'authentification
du push HTTPS ; aucune modification de main. Les deux commits locaux antérieurs
restent conservés sur une branche locale de sauvegarde.

archive-check.json : archive de ce commit, 85 fichiers et 49 modules, trois
fixtures synthétiques qualification incluses. Empreintes vérifiées ; les trois
verdicts fonctionnent après extraction, sans création d'état. SHA-256 :
31fcb51d208073d6ac8534e86b9399e12aca9ee0ef94ccc84694cec3b191cccd.
Cette archive précède C-038 ; elle n'est pas annoncée comme le dernier paquet.

## Liaison Memory Engine : A5-01/02/03

memory-recheck.py/json utilise uniquement un corpus temporaire synthétique,
le code réel Memory Engine b33c3a0 et EngineMemory de Core. Aucune source du
dépôt mémoire modifiée, aucun corpus personnel ouvert.

- Conversations identiques dans deux exports recouvrants : une occurrence
  rejouée, une ajoutée, trois éléments distincts au rappel ; octets canoniques
  existants préservés. Réimporter le second fichier ne change aucun octet.
- Cinq types de content.parts mal formés sont refusés avant mutation du corpus.
- **A5-02 toujours présent** : le rappel « acheter V100 » coupe « Ne pas » dans
  une phrase synthétique. L'extrait reste une tranche exacte du texte, avec
  needs_review, truncated et UNVERIFIED ; cela ne protège pas son sens à lui seul.
- **Versions successives** : importer une conversation poursuivie conserve deux
  archives et peut rappeler deux fois le même message. Distinct du replay
  d'une conversation identique corrigé dans A5-01.

Toutes les lectures Core ont conservé les octets du corpus (hors verrou technique
documenté). Les limites observées sont consignées pour la session mémoire ;
elles ne sont ni corrigées dans Core ni masquées par les 886 tests de régression.

```sh
PYTHONPATH=src:/chemin/vers/memory-engine python docs/validation/2026-10-08/codex-hour-0435/memory-recheck.py
```

## Publication finale du code et archive C-038

Code publié : 2a6488a6956051ea4df817aed07e7ef538043b3f ; arbre
58d40a6b3e2a3f9cd8a5d6291c5c43f23a9629ad identique au local testé. Les
publications suivantes ne complètent que documentation, coordination et preuves.

archive-check.py / archive-c038-check.json comparent les **85 fichiers aux objets
Git du commit**, avant exécution depuis l'extraction. Les trois verdicts et les
deux contrôles de configuration passent sans état créé. Sources extraites et
temporaires retirés. SHA-256 de l'archive du code final :
161a6b8acc71fb053357867d92c6bb83069c7fc45affd31838510ddaf7a0022b.

```sh
# Après construction de l'archive de ce commit avec tools/build_beta_bundle.py :
python docs/validation/2026-10-08/codex-hour-0435/archive-check.py --archive /chemin/eidolon-beta-2a6488a.tar.gz --commit 2a6488a6956051ea4df817aed07e7ef538043b3f
```

82 liens locaux des guides, propositions, README et message actif ont été
contrôlés sans cible manquante avant le dernier ajout du compte rendu concis.
La page des pistes mémoire/outillage reprend les propositions et les deux
limites mémoire, en maintenant l'avis Claude et la décision toytoy ouverts.
