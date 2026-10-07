# Archive de sources bêta reproductible — C-TASK-G044

Claude, 07/10/2026. Outil : [tools/build_beta_bundle.py](../tools/build_beta_bundle.py),
tests : [tests/test_build_beta_bundle.py](../tests/test_build_beta_bundle.py).
**Archive de développement** : ce n'est ni une qualification de la bêta, ni
une Release, ni une installation. Rien n'est publié par l'outil.

## Construire et vérifier

Depuis n'importe quel dossier du dépôt, avec un commit **explicite et
complet** (40 caractères hexadécimaux ; pas de branche, d'étiquette ni de
SHA court) :

```sh
python3 eidolon-core/tools/build_beta_bundle.py --commit <sha complet> --output <nouveau fichier>.tar.gz
python3 eidolon-core/tools/build_beta_bundle.py --verify <fichier>.tar.gz
sha256sum <fichier>.tar.gz
```

Sortie JSON : `status: OK` et code 0, ou `REFUSED` et code 2. Le fichier de
sortie **ne doit pas exister** : rien n'est jamais écrasé.

## Ce que l'archive contient, et rien d'autre

Tout est lu dans les **objets Git du commit** (`git ls-tree`, `git cat-file`),
jamais dans le dossier de travail. Un fichier non suivi, une modification
locale, un état, un jeton ou un cache ne peuvent donc pas y entrer.

| Inclus (liste autorisée) | Exclu |
| --- | --- |
| `eidolon-core/src/eidolon_core/` | tests, exemples, collaboration, preuves de validation |
| `index.html`, `app.js`, `style.css` et `README.md` du client connecté (`--web-root desktop/connected`) | prototype simulé, sources et tests du client (`app.js` est le bundle déjà généré) |
| `eidolon-core/desktop/connected/launchers/` (lanceur candidat) | scripts Bootstrap `0x-*.sh`, images |
| `pyproject.toml`, `README.md`, `LICENSE` | tout fichier non suivi |
| Documentation de recette : `BETA-ACCEPTANCE`, `BETA-FIXTURE`, `BETA-SERVER-PC`, `HTTP-READ-API`, `HTTP-RECEIPTS`, `HTTP-PREFLIGHT` | — |

Ajouts générés :

- `MANIFEST.json` : commit, arbre, heure du commit, et pour chaque fichier son
  chemin, sa taille, son mode et son SHA-256 ;
- `START-HERE.md` : démarrage et limites.

Dans la liste autorisée, sont **refusés** : un lien symbolique, un
sous-module, un nom interdit (`__pycache__`, `.pyc`, `.sqlite3`, `.db`,
`read-token`, `.env`, `.key`, `.pem`, `.log`…), un fichier attendu absent.

## Reproductibilité

Même commit, mêmes octets :

- entrées triées ;
- propriétaire 0/0 sans nom ;
- date de chaque entrée = heure du commit ;
- en-tête gzip sans date.

Vérifié par deux constructions identiques, dans les tests et sur la branche
(SHA-256 identiques). `--verify` refuse :

- une entrée modifiée ;
- une entrée ajoutée ou manquante ;
- un chemin hors liste ou contenant `..`.

## Utiliser l'archive

1. Copier l'archive et son SHA-256 sur le serveur, puis comparer.
2. Extraire dans un dossier **neuf**.
3. Depuis `eidolon-beta-<sha>/eidolon-core/`, suivre [BETA-FIXTURE.md](BETA-FIXTURE.md),
   puis [BETA-ACCEPTANCE.md](BETA-ACCEPTANCE.md), avec `PYTHONPATH=src`.

Le test `test_current_commit_bundle_runs_fixture_and_preflight` fait ce
parcours : il construit l'archive du commit courant, l'extrait, prépare le
jeu synthétique **depuis l'archive**, puis lance le diagnostic
`http_api --check`, qui doit répondre `PASS`.

## Limites

- Pas essayé sur la VM Debian 13 (Python 3.13) ni sous Windows.
- Pas de signature : l'empreinte SHA-256 doit être transmise par un canal de
  confiance.
- Le contenu dépend de la liste autorisée. Un nouveau fichier nécessaire hors
  liste doit y être ajouté explicitement, sinon il manquera (l'outil ne le
  devine pas).
- Le nom interdit est contrôlé par motif : un secret dans un fichier suivi
  au nom anodin ne serait pas détecté. La protection principale est de ne
  jamais committer de secret.

## Durcissement Codex C-012, 07/10/2026

Le vérificateur contrôle désormais aussi : archive non vide, fichiers requis,
unicité des membres et des chemins du manifeste, schéma/identités, tailles,
modes, propriétaire/date, contenu exact du document START-HERE. Il ne charge
pas plus de 1024 membres, 16 Mio par membre et 64 Mio cumulés. Les noms interdits
sont revérifiés. Il n'extrait aucun fichier pendant cette vérification.

`authenticity_verified=false` explicite qu'une archive entièrement réécrite
avec son manifeste reste possible : comparer une empreinte externe de confiance.
Les documents BETA-LOCAL-CHECK et READ-TOKEN rejoignent la liste incluse.
L'outil de vérification reste celui du checkout de confiance, pas un programme
à exécuter depuis une archive inconnue. Preuves avant/après dans
[le bilan Codex](validation/2026-10-07/codex-g042-g044/README.md).

## Documents optionnels ajoutés le 07/10

QUERY-CLEANUP, RESEARCH-GUARD, INVOCATION-BUDGET, QUERY-HISTORY et
RESEARCH-MISSIONS sont inclus quand ils existent au commit sélectionné.
La coquille Tauri et ses sources restent hors de cette archive serveur/client
Web ; consulter le dépôt complet pour ce prototype. Les liens du README vers
des composants exclus ne rendent pas ces composants présents dans l’archive.
