# G044 — archive de sources bêta reproductible : preuves

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G044](../../../../collaboration/tasks/C-TASK-G044.md).
Livrables : `tools/build_beta_bundle.py`, `tests/test_build_beta_bundle.py`,
[BETA-BUNDLE.md](../../../BETA-BUNDLE.md). Aucun fichier existant n'est
modifié. Aucune publication, aucun binaire, aucune installation.

- [9 tests de l'outil : OK](tests.txt)
- [Suite Python complète : 623 tests, OK, 6 sautés (intégrations mémoire habituelles)](full-suite.txt)
- [Constructions sur la branche](branch-builds.txt), commit `15ec7f8` :
  - deux constructions donnent le **même SHA-256** (`a16ac9f4…`) et des
    octets identiques (`cmp`) ;
  - `--verify` passe ;
  - une destination existante est refusée ;
  - un SHA court est refusé.

## Ce que prouvent les tests

| Test | Vérifié |
| --- | --- |
| Deux constructions | octets identiques, `--verify` OK |
| Contenu | rien que des fichiers **suivis** et **autorisés** du commit. Un fichier non suivi, un `read-token` local, une modification locale de `app.js` et un script Bootstrap suivi contiennent tous un secret sentinelle : **absent** de l'archive |
| Métadonnées | propriétaire 0/0 sans nom, une seule date (celle du commit), en-tête gzip sans date, mode exécutable conservé |
| Manifeste | chaque SHA-256 correspond au contenu |
| Commit | `HEAD`, nom de branche, SHA court, vide et SHA inexistant : refusés, rien d'écrit |
| Destination existante | refusée, contenu d'origine intact |
| Lien symbolique, `state.sqlite3`, fichier autorisé manquant | refusés |
| Archive modifiée ou avec un fichier ajouté | `--verify` échoue |
| CLI | codes 0 et 2, JSON `OK` et `REFUSED` |
| **Archive du commit courant** | extraite, puis `beta_fixture` et `http_api --check` lancés **depuis l'archive** : `PASS` |

## Limites

- Linux et Python 3.11 seulement ; ni Debian 13 ni Windows.
- Pas de signature : le SHA-256 doit passer par un canal de confiance.
- La liste autorisée est explicite ; tout nouveau fichier nécessaire doit y
  être ajouté.
- Les noms interdits sont repérés par motif, pas par analyse du contenu.
