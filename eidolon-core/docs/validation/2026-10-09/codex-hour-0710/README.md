# Agents média — séance du 09/10/2026 commencée à 07 h 10 Europe/Paris

Auteur : Codex/GPT. Demande toytoy : six tâches pour Claude et poursuite du dépôt
pendant une heure. G090–G095 publiées dans `cb21ec568bb72a970848e4a813262980f8ecd0ab` ;
G084–G089 restent la priorité conversation/mission de Claude.

Code livré : [`344bf1f44da90710a495da018ab592e9604d1119`](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/commit/344bf1f44da90710a495da018ab592e9604d1119)
sur `feat/eidolon-core-v0.1`, arbre `43326b2df02ae0f0ee2656ff3f830ffc5e302d12`.
Base avant séance : `1a2a3a2584ce5ad222713606387f4c764326430e`.
La preuve suivante porte sur le code publié ; aucune fusion main ni installation VM.

## Fonctionnalités livrées

- C-049 : artefacts privés à référence opaque, import atomique, quotas et contrôle
  d'intégrité à la lecture ; lots interrompus inspectables, publication revue
  limitée aux lots complets revérifiés.
- C-050 : transfert local ComfyUI facultatif, reçu strict, relecture et empreinte
  avant soumission. Sources déjà déposées également relues. Étapes durables,
  interruption incertaine sans renvoi, lecture du reçu accepté avant coupure.
- C-051 : collecte explicite des sorties enregistrées, workflow historique lié
  au plan, formats/tailles/nombres bornés, provenance et imports partiels conservés.
  Export complet vers un fichier neuf privé, sans écrasement ni lien au magasin.

[Contrat opérateur et frontière G094](../../../MEDIA-AGENTS.md). Une référence
n'est pas une permission. Les octets contrôlés ne prouvent ni qualité visuelle,
ni consigne remplie, ni résultat de mission. Aucun statut `SUCCEEDED` déduit.

## Vérifications réellement exécutées

| Vérification | Résultat et preuve |
| --- | --- |
| Suite Python complète finale | **1 040 réussis**, aucun ignoré ; [python-full.txt](python-full.txt) |
| Tests média ciblés | **69 réussis** (19 existants adaptés + 50 nouveaux) ; [media-tests.txt](media-tests.txt) |
| Dépendance Memory réelle | 6 cas inclus dans la suite, corpus temporaire synthétique, `EIDOLON_MEMORY_INTEGRATION=1` |
| Client, tests unitaires | 60 réussis / 14 Chromium non exécutés ; [node-tests.txt](node-tests.txt) |
| Client, intégration HTTP | 5 réussis / 1 Chromium non exécuté ; [node-integration.txt](node-integration.txt) |
| Client total | **65 réussis / 15 non exécutés**, aucune validation visuelle Chromium revendiquée |
| Assets générés | [assets.txt](assets.txt), `app.js up to date` ; sources UI inchangées |
| Installation isolée | Paquet construit/installé sans dépendances réseau ; [install.txt](install.txt) |
| Recette des six modes | [installed-result.json](installed-result.json), 61 modules installés identiques aux sources |
| Archive distribuable | 102 fichiers vérifiés ; [bundle-build.json](bundle-build.json), [bundle-verify.json](bundle-verify.json) |
| Reproductibilité | Deux constructions du commit publié donnent les mêmes octets ; [bundle-reproducibility.json](bundle-reproducibility.json) |
| Installation depuis archive | [bundle-install.txt](bundle-install.txt), [bundle-installed-result.json](bundle-installed-result.json), six modes et 61 modules identiques |
| Traçabilité du code testé | Empreintes de 61 modules et 4 fichiers de tests média ; [source-hashes.json](source-hashes.json) |

Memory Engine utilisé en lecture seule, commit
`a2a1910d8e93bde2ef6a32280a7abf5324854510` de `refactor/architecture-v1`.
Son checkout reste propre. Aucun corpus personnel ni fichier moteur modifié.

Les 50 nouveaux tests couvrent liens/FIFO/permissions, magasins remplacés,
contenus modifiés, quotas cumulés, concurrence d'écrivains, récupération limitée,
perte d'accusé moteur, relecture source différente, chemins de sortie refusés,
historique incomplet ou workflow étranger, limites de sorties et import partiel.
Des **processus réellement arrêtés** éprouvent les frontières de publication,
récupération et export, ainsi que les étapes upload/source/queue. La coupure
spécifique entre import d'une sortie et mise à jour du reçu de collecte utilise
une exception de test dérivée de `BaseException` : ne pas la présenter comme un
crash système ou une coupure électrique.

La [recette installée](installed_check.py) lance les vraies commandes CLI,
un serveur HTTP loopback simulant ComfyUI/Ollama, et FFmpeg réel sur un clip bleu
synthétique. Elle importe image/vidéo, supprime les originaux, exerce les six modes,
contrôle deux uploads, quatre soumissions, deux analyses, quatre collectes et quatre
exports. Les relances dans le même dossier et exports au même nom sont refusés
sans deuxième appel. **Aucun modèle, GPU ou moteur réel de génération n'a tourné.**

## Reproduction

Depuis `eidolon-core/`, avec un checkout Memory Engine séparé :

```sh
PYTHONPATH=src:.:/chemin/Eidolon-Memory-Engine EIDOLON_MEMORY_INTEGRATION=1 python -m unittest discover -s tests -t . -q
PYTHONPATH=src:. python -m unittest tests.test_media_agents tests.test_media_artifacts tests.test_media_transfer tests.test_media_outputs -q
node --test desktop/connected/tests/*.test.js desktop/connected/tests/integration/*.test.js
node desktop/connected/build.js --check
python -m venv --system-site-packages /chemin/nouveau-venv
/chemin/nouveau-venv/bin/python -m pip install --no-deps --no-build-isolation --no-index .
env -u PYTHONPATH /chemin/nouveau-venv/bin/python docs/validation/2026-10-09/codex-hour-0710/installed_check.py
python tools/build_beta_bundle.py --commit 344bf1f44da90710a495da018ab592e9604d1119 --output /chemin/nouvelle-archive.tar.gz
python tools/build_beta_bundle.py --verify /chemin/nouvelle-archive.tar.gz
```

La construction sans réseau suppose setuptools disponible dans l'environnement.
La recette requiert `/usr/bin/ffmpeg`. Pour l'essai archive, installer le paquet
extrait vérifié dans un **second** venv, puis lancer le même script de recette
avec son Python et sans `PYTHONPATH`. La vérification d'archive contrôle les
empreintes/chemins, pas l'authenticité de son auteur. Les échecs de Chromium ne
sont pas masqués par le total des tests réussis.

## Reste à qualifier

Moteurs, poids et workflows réels ; compatibilité des nœuds vidéo ; VM/V100/Windows ;
commande depuis l'accueil ; upload navigateur authentifié ; rattachement au
catalogue/worker de missions et à l'autorisation conversationnelle ; budgets GPU
communs, rétention et galerie ; validation métier et vidéo longue/son.

Les moteurs restent une frontière de confiance. Le contrôle distant de source
prouve les octets relus avant la soumission, pas leur conservation ultérieure.
La reprise ne supprime ni lots incomplets ni fichiers moteur incertains. Les
fichiers privés et verrous ne protègent pas contre un processus hostile sous le
même compte. Un timeout socket n'est pas une échéance murale globale.

Dernière livraison Claude observée après fetch : `e52561036a9f31052c2a1b05b74e1f7dbf0f2ca8`
(C092/G071). Les six fiches sont publiées ; aucun démarrage de sa session ni
achèvement des tâches suivantes n'est affirmé.
