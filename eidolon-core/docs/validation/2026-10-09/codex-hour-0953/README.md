# Session Codex — 09/10/2026, à partir de 09 h 53 Europe/Paris

Périmètre : agents Image/Vidéo et installation ; conversation/mission appartient
à Claude. Base reçue : `e512bd3` (C105/G085), intégrée puis publiée dans `bcdaa32`.
Memory Engine lu comme dépendance de test à `a2a1910d8e93bde2ef6a32280a7abf5324854510`,
sans modification. Linux, Python 3.12.14, SQLite 3.53.1, FFmpeg 6.1.1.

## C-056 — Diagnostic de configuration

`eidolon-media config-check --config moteurs.json [--require image.analyze]
[--format human]` contrôle la structure des six opérations et retourne les
réglages à compléter, sans requête ni source nécessaire. JSON par défaut ;
`CONFIGURED_SCOPE` sortie 0, `INCOMPLETE`/`INVALID` sortie 2 sur stdout ; erreurs
empêchant le rapport sur stderr. La sélection de périmètre accepte les opérations
absentes non demandées, mais ne masque pas une configuration invalide.

Validation des workflows partagée avec l'exécution ; marqueur privé du magasin
seulement ; métadonnées FFmpeg seulement ; aucun moteur, source, sous-processus,
travail, téléchargement ou permission. Les classes vides/non imprimables/trop
longues sont maintenant refusées avant une éventuelle sonde moteur.

## Vérifications avant intégration C106

| Preuve | Résultat réellement exécuté par Codex |
| --- | --- |
| `conversation-tests.txt` | 45 tests G084/G085 initiaux réussis |
| `g085-storage-findings.json`, `probe_g085_storage.py` | quatre défauts reproduits sur copies synthétiques, transmis dans G107 |
| `media-tests.txt` | 103 tests média réussis, dont 17 nouveaux |
| `python-full.txt` | 1 123 tests réussis, 0 ignoré ; Memory integration activée |
| `install.txt`, `installed-result.json` | paquet installé hors source : 66 modules identiques, six parcours média, trois diagnostics |

`media-existing-tests.txt` conserve la première passe (86 tests, une attente de
code d'erreur devenue obsolète pour une classe contenant une nouvelle ligne).
Le test attend désormais le refus structurel commun `INVALID_WORKFLOW_NODE` ;
la passe média finale et la suite complète ci-dessus sont vertes.

`installed_check.py` compare tous les modules installés aux sources, exerce la
CLI en sous-processus, des API HTTP loopback simulées et FFmpeg réel. Les sources
originales sont supprimées avant les exécutions via références d'artefacts.
Les diagnostics de configuration et précontrôles hors ligne n'émettent aucun
appel moteur ; les sondes explicites ne transmettent que les métadonnées prévues.
Aucun vrai modèle, poids, GPU, VM ou PC Windows qualifié.

## Résultats reçus et limites

C105 rapporte 81/81 tests Node/Chromium sur `55be01f` ; preuve Claude conservée
sous `../claude-c103-recheck/`. Chromium n'est pas installé ici ; ces résultats
ne sont pas présentés comme reproduits par Codex.

C106 (`3ad4aa8`) est intégré sans modification des sources Claude. Les sept
contrôles indépendants de `recheck_g085_storage.py` passent (`g085-fixed-result.json`).
La sonde initiale conserve les défauts anciens ; elle n'est pas applicable à la
nouvelle API de création explicite.

La contre-revue G086 reproduit une référence de mémoire encore citée après
retrait total de cette mémoire du corps envoyé au modèle pour respecter le
budget. `probe_g086_sources.py` et `g086-source-finding.json` emploient le vrai
adaptateur avec un transport injecté synthétique, sans modèle ni réseau.
Constat transmis à Claude dans G108 ; son module n'est pas édité par Codex.

Les moteurs/workflows de production restent à configurer par l'opérateur.
L'accueil ne lance toujours pas d'opération média ; l'API/permission et le
raccordement au catalogue runtime restent dans les lots coordonnés avec Claude.

## Intégration C106

`python-integrated.txt` : **1 141 tests réussis en 192,680 s, aucun ignoré**,
avec `PYTHONPATH=src:.:/workspace/scratch/16ec975b83e7/memory-reference` et
`EIDOLON_MEMORY_INTEGRATION=1 python -m unittest discover -s tests -t . -q`.
Le constructeur de bundle inclut désormais aussi les guides stockage/dialogue.
L'empreinte des sources validées figure dans `source-manifest.json`.

## Archive publiée C-056/G086 — b5f08508

Archive de développement depuis `b5f08508b557e42da6947b4dc724966733323c8e` :
**112 fichiers, 413 328 octets** ; SHA-256
`322ec23c091fe7fb29e5e5afa30cd3c20b78e49faa1710353f062f2bfbf67da7`.
Deux constructions identiques (`bundle-build*.json`, `bundle-reproducibility.json`),
contrôle du manifeste (`bundle-verify.json`), extraction puis installation depuis
cette extraction en venv distinct (`bundle-install.txt`). Le vérificateur confirme
la cohérence du manifeste, pas l'authenticité d'une archive quelconque.

`bundle-installed-result.json` : **67 modules installés identiques**, six modes,
six précontrôles hors ligne, six sondes de métadonnées et trois contrôles de
configuration. FFmpeg réel ; moteurs et médias synthétiques, aucun vrai modèle.

Depuis `/tmp`, sans PYTHONPATH, `eidolon_core.beta_check` sur les assets extraits :
**24/24 contrôles missions et 25/25 contrôles archives de recherche**
(`bundle-beta-missions.json`, `bundle-beta-research-archives.json`). Serveur HTTP
réel sur loopback et données temporaires synthétiques ; navigateur, SSH, VM et
Windows non essayés. Le logo est empreinté, mais les trois requêtes d'assets de
cette recette concernent HTML/JS/CSS. Pas d'extension implicite de cette preuve.

## C-058 — Inspection humaine d'un travail

`inspect --format human` donne les étapes durables et les indications opérateur
sans exposer les textes non fiables au terminal, ni modifier le JSON par défaut.
`media-status-tests.txt` : huit tests réussis. Le test de coupure utilise réellement
`execute` et une interruption synthétique après `QUEUE_ACKNOWLEDGED`, puis vérifie
le rendu humain, les octets et mtime du journal inchangés, et l'absence de socket,
sous-processus ou lecture source. Le reçu permet de suggérer la consultation ;
il ne prouve aucune réussite. Aucun renvoi ou nettoyage automatique.

L'archive b5f08508 précède C-058 ; elle n'est pas présentée comme preuve de ce
nouveau rendu. La publication suivante conservera cette distinction.

`media-final-tests.txt` : **111 tests média réussis en 6,350 s** après C-058.
