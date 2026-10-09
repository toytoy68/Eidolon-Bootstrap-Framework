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
