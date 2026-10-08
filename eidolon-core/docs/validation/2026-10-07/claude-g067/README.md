# C-TASK-G067 — Contre-revue des lectures SQLite bornées

Claude, 08/10/2026. Base : `1e9d8b8` (branche Core `fadc3bc` fusionnée).
Le dossier `src` a été figé par `git archive`.
Modules examinés : `ReadOnlyStore` (http_api), `MissionList`, `ClientSync`.
Données synthétiques, dossiers temporaires, aucune source Core modifiée.

```sh
python3 probes_g067.py <src figé>      # → probes.txt (≈ 2 min, pic ≈ 1,6 Gio)
```

Chaque cas part d'une copie fraîche d'un état de référence (4 missions réelles).
L'empreinte compare noms, tailles, modes, mtime et contenus de tous les fichiers
avant et après la lecture.

## Confirmé

- **Aucune page partielle** : une seule mission invalide sur quatre fait refuser
  toute la page et la capture. Exemples : JSON invalide, clé dupliquée, identité
  différente, révision 1,5 ou 2^53, `cancel_requested=2`, statut trop long,
  imbrication 100 000, événements manquants.
  En HTTP : 503 `STATE_UNAVAILABLE`, 91 octets, sans liste.
- **Schéma** : `store_id` absent, `user_version=2`, table manquante et mode revue
  sont refusés avec un code constant.
- **Aucun fichier créé ni modifié** par une lecture ou un refus, en journal
  `DELETE` (le mode par défaut du Store).
- **Concurrence** :
  - une création normale entre deux pages → `RESET_REQUIRED STATE_CHANGED` ;
  - 3 s de lectures pendant des créations continues → 18 pages cohérentes,
    aucun refus.
- **Événements** : 1 000 000 d'événements sur une mission → liste en 0,03 s,
  capture en 0,09 s, rattrapage en 0,13 s. Les requêtes sont indexées.

## Défauts minimaux

- **G067-1 (moyen) — une lecture crée des fichiers en mode WAL.**
  - Si la base est passée en WAL (par un outil SQLite ; Core ne le fait pas),
    la première lecture « seule » crée `missions.sqlite3-wal` et `-shm`.
  - Sur un dossier non inscriptible, elle échouerait.
  - Correctif minimal proposé : avant `connect`, lire l'en-tête (octets 18–19 = 2
    signifie WAL) et refuser avec un code constant, ou le documenter comme
    prérequis.
- **G067-2 (moyen) — aucune borne d'octets sur le corps des missions** dans
  `MissionList` et `ClientSync`. `runtime_inspect` borne déjà à 16 Mio.

  | Corps d'une mission | Liste | Pic mémoire |
  | ---: | ---: | ---: |
  | 16 Mio | 0,08 s | 124 Mio |
  | 64 Mio | 0,32 s | 428 Mio |
  | 256 Mio | 1,45 s | 1,58 Gio |

  - Le budget SQL de 2 s ne couvre pas le décodage Python.
  - Correctif minimal proposé : lire `substr(CAST(body AS BLOB),1,MAX+1)` comme
    `runtime_inspect`, puis refuser au-delà, par exemple `MISSION_SIZE_LIMIT`.
- **G067-3 (faible) — délai SQL et verrou de stockage sont confondus.**
  - En journal `DELETE`, un écrivain qui tient une transaction exclusive donne
    `OperationalError database is locked` après 2,0 s.
  - Un budget épuisé donnerait `interrupted`.
  - Les deux deviennent le même HTTP 503 `STATE_UNAVAILABLE` : le client ne peut
    pas distinguer « réessayer » de « base illisible ».
  - Proposition : `STATE_BUSY` pour le verrou.
- **G067-4 (faible) — des valeurs hors type sont acceptées sans contrôle.**
  - Un corps stocké en BLOB UTF-16 est accepté (`json.loads` détecte l'encodage).
  - Un détail d'événement en BLOB donne `ContractError` avec un message libre en
    API (503 en HTTP).
  - Proposition : exiger `type(body) is str`.

## Mesures sans défaut

- **Budget SQL** : il ne s'est jamais déclenché, même réglé à 0 s, sur 300 000
  événements. Toutes les requêtes restent sous 1 000 opérations SQLite (index,
  `count` optimisé). Il reste un filet, pas une borne de durée totale.
- **Page de 100 missions de 2 Mio** : 0,59 s, 30 857 octets JSON servis.
  La projection reste petite.
- **Réécriture SQL directe d'un corps sans événement** entre deux pages : servie
  sans reset (statut lu `FAILED`). C'est hors garantie et documenté
  (« écritures Core normales »).
- **Révision `'3'`** : convertie en entier par l'affinité INTEGER de SQLite. Ce
  n'est pas un défaut.

## Limites

- Les essais tournent en root : les refus liés aux droits de dossier ne sont pas
  observables ici.
- Pas de NFS, Windows ni coupure électrique.
- Le pic mémoire du processus principal (1,56 Gio) vient de la préparation du cas
  256 Mio par la sonde elle-même.
- Les durées sont des mesures uniques sur ce conteneur, pas des garanties.
