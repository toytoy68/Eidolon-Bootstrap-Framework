# G048 — intégrité des reçus (C-012) et affichage de `receipt_binding`

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G048](../../../../collaboration/tasks/C-TASK-G048.md).

Cibles figées par `git archive` :

- `0fdf18e` (C-012) ;
- `b5f0093` (son parent, avant C-012), pour fabriquer un ancien état.

`receipt_lookup.py` et `store.py` n'ont pas changé depuis `0fdf18e` jusqu'à
la branche courante. Sources serveur non modifiées.

```sh
python3 docs/validation/2026-10-07/claude-g048/probes_g048.py <copie 0fdf18e>/eidolon-core/src <copie b5f0093>/eidolon-core/src
```

États synthétiques en dossiers temporaires. Chaque altération porte sur une
**copie**, faite avec `sqlite3`. HTTP en boucle locale seulement, avec un
jeton synthétique. Sortie : [probes.txt](probes.txt).

## Partie 1 — contre-revue serveur

| # | Cas | Résultat |
| --- | --- | --- |
| A | 5 reçus authentiques (2 décisions, 3 annulations) | FOUND `EVENT_HASH` ; ni acteur, ni motif, ni hash de l'événement exportés |
| B | Altération isolée du reçu, hash présent (G042 C1, C4, C5–C8) | **toutes refusées** `503 RECEIPT_UNAVAILABLE` : G042-1 corrigé |
| C | Hash présent mais invalide : majuscules, 63 caractères, non hexadécimal, hash d'un autre reçu, nombre, `null`, chaîne vide, objet, espace final, clé dupliquée (dans les deux ordres) | **tous refusés** |
| D | Hash retiré seul | FOUND `LEGACY_FIELDS` (attendu) |
| D | **Hash retiré + altération C5–C8 (annulation)** | **FOUND `LEGACY_FIELDS`, valeurs altérées exportées** (G048-1) |
| D | Hash retiré + altération C1/C4 (décision) | refusé : `request_sha256` couvre déjà décision et révision |
| E | Reçu altéré + hash recalculé | FOUND `EVENT_HASH` : hors détection, comme le documente C-012 |
| F | Ancien état (`b5f0093`) lu par `0fdf18e` | 5 × FOUND `LEGACY_FIELDS` ; base identique après lecture ; **aucune migration** |
| F | Nouvelle commande écrite dans l'ancien état | seul le nouvel événement porte un hash (`EVENT_HASH`) ; les anciens restent `LEGACY_FIELDS` |
| G | Processus tué entre le hash et l'insertion du reçu | base identique, NOT_FOUND ; même clé renvoyée ensuite : FOUND `EVENT_HASH` |
| G | Processus tué après l'insertion du reçu, avant le commit | idem |
| G | Refus SQL à l'insertion du reçu | `IntegrityError`, base identique ; renvoi ensuite : FOUND `EVENT_HASH` |
| H | Même clé, même contenu | reçu historique, base identique |
| H | Même clé, autre contenu | `COMMAND_KEY_REUSED`, base identique |
| H | 4 processus, même clé en parallèle | 1 reçu, 1 événement, réponses identiques (voir limite) |
| I | HTTP, état neuf / ancien | 200 FOUND, `receipt_binding` = `EVENT_HASH` / `LEGACY_FIELDS` |

La panne est provoquée par un déclencheur SQLite, posé dans la copie, qui
appelle une fonction `os._exit(9)` enregistrée dans le sous-processus. Le
déclencheur est retiré avant la lecture.

### G048-1 — rétrogradation : retirer l'empreinte suffit (P3)

`LEGACY_FIELDS` est accordé à **tout** événement sans `receipt_sha256`, y
compris un événement écrit après C-012. Il suffit donc de **retirer la clé**
de l'événement pour que les altérations C5–C8 d'un reçu d'annulation soient
de nouveau exportées. Ces altérations couvrent le statut de mission, la
révision et l'indicateur, et même CANCELLED remplacé par SUCCEEDED.

Portée réelle : il faut écrire dans la base, comme pour E (réécriture
cohérente). Ce n'est donc pas une nouvelle classe d'attaquant. Mais pour une
**corruption** ou une modification maladroite, retirer une clé est plus
simple que recalculer une empreinte, et le résultat se présente comme un
« ancien format » légitime.

**Proposition** (Codex décide ; sources réservées) :

- noter dans `sync_metadata`, à la première écriture C-012, la séquence à
  partir de laquelle chaque reçu porte une empreinte ;
- refuser un événement sans empreinte au-delà de cette séquence ;
- les anciens reçus restent `LEGACY_FIELDS`, sans réécriture.

Non prototypé ici.

### Séparer intégrité et authenticité

- `EVENT_HASH` : le reçu et son événement concordent à cette lecture.
- Une réécriture cohérente (E) reste invisible.
- Ce n'est ni une signature ni une identité, et ce n'est jamais une preuve
  qu'une action a été exécutée ou arrêtée.

## Partie 2 — affichage client (`desktop/connected`)

| Réponse Core | Session | Affichage « Contrôle d'intégrité » |
| --- | --- | --- |
| FOUND + `EVENT_HASH` | gardé | liaison au journal vérifiée par Core à cette lecture ; ni signature, ni preuve d'exécution |
| FOUND + `LEGACY_FIELDS` | gardé | contrôle limité (ancien format) ; pour une annulation, statut, révision et indicateur non couverts |
| FOUND **sans** le champ | `binding: null` | « non précisé par ce serveur » — **jamais `EVENT_HASH` par défaut** |
| FOUND + autre valeur (`SIGNED`, `null`, minuscules) | refusé `INVALID_BINDING` | reçu non affiché |
| NOT_FOUND + champ présent | refusé `INVALID_RECEIPT` | — |

La capture, sa fraîcheur et la phase de connexion restent inchangées. Une
seule requête est envoyée par consultation explicite.

Fichiers :

- `src/session.js`, `src/view.js` ;
- `app.js`, régénéré par `build.js` (`--check` OK) ;
- `README.md` ;
- tests : `tests/session.test.js` (+1 test : 8 réponses scriptées, libellés)
  et `tests/receipts.test.js` (vrai serveur : `EVENT_HASH` ; Chromium : texte
  affiché).

Résultats :

- Node : **61/61** ([sortie](node-tests.txt)), dont les tests Chromium ;
- Python : **677 OK**, 6 ignorés.

## Limites

- Linux, Python 3.11, Chromium Playwright local. Ni VM, ni Windows, ni SSH.
- H parallèle : lors du **premier** passage, les réponses des 4 processus
  n'étaient pas toutes identiques, et la sortie n'en gardait pas le détail.
  Ce n'est pas reproduit ensuite : 3 passages complets, plus 150 envois
  (25 × 6 processus), tous identiques. Le dossier comptait toujours 1 reçu
  et 1 événement. Cause probable : un verrou SQLite dépassé (5 s) sous
  charge, mais ce n'est **pas établi**.
- Le lecteur CLI local ne fait pas ce contrôle (documenté par C-012) : non
  testé ici.
