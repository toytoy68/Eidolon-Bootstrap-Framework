# G047 — vérification indépendante : recette locale, paquet et vérificateur d'archive

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G047](../../../../collaboration/tasks/C-TASK-G047.md).
Cibles figées :

- `d9265fa` (C-010f/g : `beta_check`, paquet), en copie `git archive` ;
- `0fdf18e` (C-012 : vérificateur durci de l'archive G044), pour P8
  seulement, preuves séparées.

Aucune source modifiée.

```sh
python3 docs/validation/2026-10-07/claude-g047/probes_g047.py <copie d9265fa/eidolon-core> <copie 0fdf18e> <dépôt>
python3 docs/validation/2026-10-07/claude-g047/p5_sigterm.py <copie d9265fa/eidolon-core>
```

Linux, Python 3.11.15, setuptools 68.1.2 (Debian), pip 24.0. `TMPDIR` est
redirigé vers un dossier vide pour observer ce qui reste. Sorties :
[sondes](probes.txt), [SIGTERM en détail](p5-sigterm-detail.txt).

## Résultats

| # | Cas | Résultat |
| --- | --- | --- |
| P1 | Recette depuis la copie source, JSON et texte | **PASS**, 24 contrôles, 2,7 s ; aucune chaîne de type jeton dans les sorties ; rien ne reste |
| P2 | Dossier courant ailleurs, `PYTHONPATH` et `--web-root` absolus | PASS |
| P2 | `--web-root` relatif depuis un autre dossier | FAIL `LOCAL_RECIPE_FAILED` (attendu, mais sans cause lisible) |
| P3 | Processus enfant tué pendant la phase de préparation | FAIL propre : rien ne reste |
| P4 | Ctrl+C (SIGINT) | FAIL `INTERRUPTED` propre : rien ne reste |
| P5 | **SIGTERM** (`kill`, `timeout`, arrêt de service) | **pas de rapport ; dossier temporaire laissé** (avec `read-token` 0600 synthétique) ; **serveur de recette orphelin, encore à l'écoute** si le signal arrive pendant qu'il tourne |
| P6 | `--web-root` incomplet | FAIL en 0,1 s, rien de créé |
| P7 | Wheel avec setuptools du système | **échec Debian** `install_layout` ; réussit avec `SETUPTOOLS_USE_DISTUTILS=stdlib` |
| P7 | Contenu du wheel | 43 entrées : modules seulement, **ni client Web, ni tests, ni outil d'archive** |
| P7 | Installation sans réseau en venv, puis recette depuis `/`, sans `PYTHONPATH` | modules **identiques octet pour octet** ; **PASS** (version 0.1.0) ; sans client Web : FAIL, comme documenté |
| P8 | Vérificateur durci, archive authentique | OK, `authenticity_verified=false` |
| P8 | Membre en double, contenu modifié, membre ajouté ou retiré, mode 0777, START-HERE modifié, lien symbolique, `../`, 1100 membres, membre de 17 Mio, gzip de 200 Mio de zéros | **tous refusés**, en 40 à 80 ms, **sans extraction** |

## G047-1 — SIGTERM : serveur orphelin et dossier avec jeton laissés (P2 pour la recette)

`beta_check` traite Ctrl+C (`KeyboardInterrupt`), mais pas SIGTERM. Python
s'arrête alors sans exécuter les `finally` : le serveur enfant n'est pas
arrêté, et `TemporaryDirectory` n'est pas nettoyé. SIGTERM est justement le
signal de `kill`, de `timeout`, d'une CI qui annule ou d'un arrêt de service.
Les données sont synthétiques, et le jeton ne sert qu'à ce serveur, mais
celui-ci reste à l'écoute sur `127.0.0.1` avec ce jeton.

**Proposition** (Codex décide) :

- convertir SIGTERM en `SystemExit` au début de `main`, ce qui fait jouer les
  `finally` existants ;
- lancer les enfants dans leur propre groupe de processus et arrêter le
  groupe.

## G047-2 — construction du wheel avec setuptools Debian (P3, VM Debian)

Sur Debian, `pip wheel --no-build-isolation` avec le setuptools du système
échoue sur `install_layout`. La même construction réussit avec
`SETUPTOOLS_USE_DISTUTILS=stdlib`. Debian 13 est la cible de la VM : à
prévoir dans la recette du paquet, ou construire le wheel ailleurs. La cause
exacte côté Debian n'est pas analysée ici.

## Fichier source, wheel et archive G044 : ne pas les confondre

| | Contient | Sert à |
| --- | --- | --- |
| Copie source (checkout) | tout le dépôt | développement, tests |
| **Wheel** (C-010g) | modules `eidolon_core` seulement | installer Core ; le client Web doit venir d'ailleurs (`--web-root` absolu) |
| **Archive G044** | modules, client Web, lanceur, docs de recette, manifeste | copier une version complète sur le serveur |

## Limites

- Linux seulement, sans navigateur. Ni VM, ni Windows, ni SSH.
- Un PASS local ne qualifie pas la bêta.
- P3 et P4 ont frappé la phase de préparation ; le cas « serveur en cours »
  n'est mesuré que pour SIGTERM (P5 détaillé).
