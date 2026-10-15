# Politique hôte et instantané : durcissement G258 (Claude, tâches 4 à 7 et 9)

Auteur : Claude. Date : 15/10/2026, Europe/Paris. Statut : **expérimental**.
Ce document complète [G256-6/7](2026-10-15-host-policy-and-snapshot.md).

- Fichiers : `tools/claude_host_policy.py`, `tools/claude_observation_snapshot.py`,
  `tools/claude_offline_preflight.py`.
- Tests : `tests/test_claude_host_policy_g258.py`.
- **41 sondes rouges avant correctif** : 40 dans les deux modules, plus le
  préflight sous Windows.

## G258-4 — Politique construite sans validateur

| Défaut avant correctif | Correctif |
| --- | --- |
| `HostPolicy("", timedelta(0), …, load_limit=-1)` se construisait. Le refus arrivait plus tard, comme refus d'**observation**, ou pas du tout (unité vide). | `__post_init__` valide **toute** construction, avec `PolicyRefused`. |
| Une politique gelée modifiée par `object.__setattr__` passait. | `run_with_policy` revalide **avant** la fabrique. |
| `1e-7` seconde donnait `timedelta(0)`, donc une politique « valide » à durée nulle. | Refus « rounds to zero ». La plus petite durée acceptée est 1 µs, conservée exactement. |

## G258-5 — Nombres et chaînes extrêmes

| Entrée | Avant | Après |
| --- | --- | --- |
| `1e999` | `inf` accepté : il ne passe pas par `parse_constant` | `SNAPSHOT_INVALID_JSON` |
| entier de 5 000 chiffres | `ValueError` brute, **sans code stable** | `SNAPSHOT_INVALID_JSON` |
| entier de plus de 18 chiffres | accepté | refusé. Une mesure d'hôte n'en a pas besoin. |
| `"\ud800"` (surrogate isolé), en valeur ou en clé | accepté : plantage plus tard à l'encodage | `SNAPSHOT_ENCODING` |
| `"source"` en double de `"source"` | déjà refusé | inchangé (`SNAPSHOT_DUPLICATE_KEY`) |
| `1e-400`, `-0.0` | 0,0 | inchangé : nombres finis |

La profondeur exacte est vérifiée : 4 niveaux sont acceptés, 5 sont refusés.

## G258-6 — Identité du fichier et identité du chemin

- **Identité du fichier** : `(st_dev, st_ino, taille, mtime, ctime)` de la
  feuille, identique avant et après la lecture, par descripteur **et** par
  nom (G256).
- **Identité du chemin** (nouveau) : après la lecture, le chemin est
  reparcouru depuis `/`, sans suivre de lien. Le dossier obtenu doit être
  le **même** (`st_dev`, `st_ino`) que celui qui a servi à lire.
- Avant le correctif, un ancêtre renommé pendant la lecture passait : les
  octets étaient lus, mais ne venaient plus du chemin de confiance. Ancêtre
  renommé, remplacé ou transformé en lien : `SNAPSHOT_PATH_CHANGED`.
- Un ancêtre déjà en lien, ou inaccessible (`EACCES` simulé, sans `chmod`
  système), donne `SNAPSHOT_PATH`. Un fichier disparu donne
  `SNAPSHOT_CHANGED`.
- Limite : entre le second parcours et le retour de la fonction, un
  renommage reste possible. L'hôte doit donc garder le dossier non
  modifiable par d'autres comptes (déjà exigé).

## G258-7 — Portabilité

| Primitive | Usage | Linux serveur | Windows PC |
| --- | --- | --- | --- |
| `O_NOFOLLOW`, `O_DIRECTORY`, `O_NONBLOCK`, `O_CLOEXEC` | lecteur | présentes | absentes |
| `dir_fd` pour `open` et `stat`, `follow_symlinks=False` | lecteur | présents | absents |
| `geteuid`, propriétaire et mode POSIX | préflight (secret du pont) | présents | absents |
| `lstat`, `disk_usage`, `git` | préflight | présents | présents |

- `missing_primitives()` liste ce qui manque. Le lecteur refuse alors
  (`SNAPSHOT_PLATFORM_UNSUPPORTED`) **avant** tout `open`.
- **Défaut de mon préflight** : sans `os.geteuid`, il plantait
  (`AttributeError`). Il répond maintenant `UNKNOWN`, ce qui arrête la
  recette.
- Conclusion : l'instantané et la politique sont **produits et lus sur le
  serveur Linux**. Le PC Windows n'est qu'un client navigateur.

## G258-9 — Budgets de la projection de passages (Memory, patch 0054)

Mesures synthétiques, en mémoire, sur ce conteneur. Trois révisions de
chaque archive ; chaque archive compte trois messages.

| Archives | Caractères par message | Points après r1 / r2 / r3 | Servis | Dépassés après r3 | Projection d'une révision | Requête |
| --- | --- | --- | --- | --- | --- | --- |
| 50 | ~2 700 | 350 / 780 / 1 210 | 430 | 780 | 0,02 s | 0,6 ms |
| 200 | ~2 700 | 1 600 / 3 380 / 5 160 | 1 780 | 3 380 | 0,1 s | 2,5 ms |
| 200 | ~10 800 | 5 180 / 10 760 / 16 340 | 5 580 | 10 760 | 0,3 s | 8,5 ms |

Les points dépassés croissent **linéairement** avec les révisions : après 3
révisions, les deux tiers des points stockés ne sont plus servis.

Proposition :

- deux budgets **fournis par l'opérateur** : `max_passages_per_archive` et
  `max_points` (ce dernier compte les points dépassés) ;
- un refus ne change rien, et la projection précédente reste servie ;
- `stats()` donne les points servis et dépassés ;
- un compactage éventuel reste une **opération d'administration séparée et
  revue** (Q2), jamais automatique.
