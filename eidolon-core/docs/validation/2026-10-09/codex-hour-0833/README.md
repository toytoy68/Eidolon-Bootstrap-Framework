# Agents média et intégration — séance du 09/10/2026, 08 h 33 Europe/Paris

Auteur : Codex/GPT. Demande toytoy : six nouvelles tâches pour Claude et une
heure de poursuite du dépôt. Branche : `feat/eidolon-core-v0.1`.

## Coordination et livraisons reçues

Les six fiches **G096–G101** sont publiées dans
`1b44ab0c872eb0fe1cb781068e26f183a7c6eccb` : sources citées, isolation des pièces
jointes, changement de modèle, formats historiques, annulation ciblée et résultats
média. G084–G089 restent prioritaires. La publication des fiches ne lance pas une
session Claude.

La référence locale Claude était périmée : seul le refspec de la branche Core
était suivi. Lecture distante et fetch explicite ont retrouvé C103 / `ccf9a9e`,
puis C104 / `8e21108e83809463bb0c99d5cd48ca6e18959485` pendant la séance. Le suivi
de sa branche est corrigé. Les bilans antérieurs restent des traces datées ; leur
mention de G071 comme dernière livraison était incomplète.

Historique G072–G079 intégré. **G084 reçu et intégré sans modification** : contrat
pur de conversation, propositions versionnées, soumission humaine et lien vérifié
à une mission synthétique. Aucun stockage, contrôleur de dialogue, API ou interface
de chat livré par ce contrat. G085 est annoncé comme suite par Claude C104, sans
session en cours présumée ici. L'icône simplifiée à 32 px choisie par toytoy dans
son échange avec Claude est intégrée ; les huit autres entrées ICO sont inchangées.

## Travail Codex

- **C-052** : `eidolon-media preflight`, hors ligne par défaut ; validation des
  entrées et de la source. Sondes explicites de métadonnées ComfyUI/Ollama, sans
  prompt, octet source, upload ni inférence. Un diagnostic n'autorise pas un travail
  et son plan n'est pas réutilisable. [Guide opérateur](../../../MEDIA-AGENTS.md).
- **C-053** : paire logo client/serveur G078 intégrée ; asset facultatif inclus
  dans les archives nouvelles. Les boutons « Exécution indisponible » signalés
  par C103 sont remplacés par du texte. Les tests d'absence de commandes sont
  conservés, avec une régression sur le HTML réel.
- **C-054** : remplacement de la lecture SQL `substr(CAST(TEXT AS BLOB))` par
  l'accès incrémental SQLite en lecture seule. Longueur des corps/détails contrôlée
  avant leur matérialisation, dans la transaction qui sélectionne la ligne.
- **C-055** : écart G073-1 corrigé : des critères fixés exactement au début de
  l'essai sont refusés, même si les fuseaux diffèrent. Guide CLI précisé sur le
  délai socket et le budget total du worker.

## Vérifications exécutées

| Vérification | Résultat et preuve |
| --- | --- |
| Suite Python après C-052–C-054 | 1 060 réussis, aucun ignoré ; [journal](python-before-c055.txt) |
| Suite complète après C-055, avant réception G084 | **1 061 réussis**, aucun ignoré ; [journal](python-full.txt) |
| Contrat G084 après intégration | **23 réussis**, dont mission Store/runtime réelle synthétique ; [journal](conversation-g084-tests.txt) |
| Dépendance Memory | 6 tests inclus dans les suites complètes, checkout réel séparé, corpus synthétique |
| Précontrôle et agents média | 86 réussis ; [journal](media-tests.txt) |
| Lecture SQLite / HTTP / précontrôle serveur | 86 réussis ; [journal](storage-http-tests.txt) |
| Qualification et CLI | 33 réussis ; [journal](qualification-tests.txt) |
| Client Node + HTTP | **66 réussis, 15 non exécutés**, zéro échec ; [journal](client-tests.txt) |
| Assets | `app.js up to date` ; [preuve](assets.txt) |
| Logo serveur | 7 cas : présent, absent, lien, lien cassé, dossier, trop grand, sans web-root ; [sonde G078 rejouée](logo-server-probe.txt) |
| Icône sélectionnée | 9 entrées cohérentes, seul 32 px change, assemblage identique ; [inspection](icon-selected-inspection.json), [reproduction](icon-reproducibility.json) |
| G072 / G073 / G074 | Bancs Claude rejoués sans échec ; [G072](claude-g072-replayed.txt), [G073 avant correction](claude-g073-replayed.txt), [G073 après correction](claude-g073-after-fix.txt), [G074](claude-g074-replayed.txt) |
| Sources testées | Empreintes de 63 modules et des tests concernés ; [manifest](source-hashes.json) |
| Installation finale, après G084/C-055 | 63 modules identiques et six modes réussis ; [installation](install-final.txt), [recette](installed-final-result.json) |

Les 15 tests Chromium sont **non exécutés** : bibliothèque Playwright disponible,
exécutable Chromium absent. Le contrôle statique des boutons ne remplace pas leur
recette navigateur. Aucune capture nouvelle ni validation visuelle de cette séance.

Memory Engine : `a2a1910d8e93bde2ef6a32280a7abf5324854510`, checkout propre, aucun
fichier moteur ni corpus personnel modifié. Les 1 061 tests et les 23 tests G084
sont deux exécutions distinctes ; aucune suite globale de 1 084 n'est revendiquée.

## Borne mémoire SQLite

[Banc reproductible](probe_storage_memory.py), [mesures](storage-memory.json).
Pour chaque champ mission/event, la base synthétique contient un TEXT de **256 Mio**.
La création de la base et chaque lecture ont lieu dans des processus distincts.
Linux, Python 3.12, SQLite 3.53.1 :

| Lecture | Pic RSS mission | Pic RSS événement |
| --- | --- | --- |
| Ancien `substr(CAST(...))` | 300,6 Mio | 300,6 Mio |
| API incrémentale, refus avant lecture | 12,5 Mio | 12,5 Mio |

Les codes `MISSION_SIZE_LIMIT` / `EVENT_SIZE_LIMIT` sont conservés. TEXT strict,
UTF-8 strict, plafond inchangé de 16 Mio ; pas de fallback non borné si `blobopen`
manque. Le contrôle ne borne pas toutes les allocations possibles de schéma,
d'index, de métadonnées ou du processus. Pas d'essai Windows.
Sources : [SQLite incremental I/O](https://www.sqlite.org/c3ref/blob_open.html),
[Python sqlite3](https://docs.python.org/3/library/sqlite3.html).

## Installation et reproduction

La [recette installée](installed_check.py) utilise les vraies commandes CLI,
des API HTTP loopback simulées et FFmpeg réel sur un clip synthétique. Les six
modes sont précédés d'un précontrôle sans réseau puis d'une sonde de métadonnées.
Les sources sont importées et les originaux supprimés avant les traitements.
Deux uploads, quatre générations simulées, deux analyses simulées, quatre
collectes/exports ; mêmes dossiers ou destinations refusés sans deuxième appel.

Depuis `eidolon-core/` :

```sh
PYTHONPATH=src:.:/chemin/Eidolon-Memory-Engine EIDOLON_MEMORY_INTEGRATION=1 python -m unittest discover -s tests -t . -q
PYTHONPATH=src python docs/validation/2026-10-09/codex-hour-0833/probe_storage_memory.py
node --test desktop/connected/tests/*.test.js desktop/connected/tests/integration/*.test.js
node desktop/connected/build.js --check
python -m venv --system-site-packages /chemin/nouveau-venv
/chemin/nouveau-venv/bin/python -m pip install --no-deps --no-build-isolation --no-index .
env -u PYTHONPATH /chemin/nouveau-venv/bin/python docs/validation/2026-10-09/codex-hour-0833/installed_check.py
```

Setuptools déjà présent et `/usr/bin/ffmpeg` nécessaires à cette recette. Aucun
téléchargement de moteur/poids. Une réexécution de la suite complète après G084
inclura ses 23 tests supplémentaires ; les chiffres ci-dessus décrivent les
exécutions effectivement conservées.

## Limites et suites

Moteurs, poids, workflows et nœuds vidéo réels, VM/V100/Windows restent à qualifier.
L'exécution depuis l'accueil, l'upload authentifié et le rattachement au catalogue
de missions attendent la frontière conversation/permission de Claude. Les
références d'artefacts ne sont pas des droits. Budgets GPU communs, rétention,
galerie, validation métier et vidéo longue/son restent ouverts.

G072-1 (diagnostic d'en-tête tronqué), remarques G074 et diagnostic de sortie
tronquée G075 restent suivis. Les effets réseau des extensions et modèles locaux
ne sont pas isolés par les précontrôles. Aucun main, déploiement ou service système
modifié dans cette séance.
