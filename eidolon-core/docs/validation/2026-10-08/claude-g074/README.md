# C-TASK-G074 — Configurations locales des planificateurs et leur identité (C-036/C-038)

Claude, 08/10/2026. Base : `5812a5e` (src figé). Cible : `model_config.py`,
`model-config-check` et les identités des deux adaptateurs, sans modification.

```sh
python3 probes_g074.py <src figé>     # code 1 si une attente échoue → probes.txt (≈ 15 s)
```

Méthode :

- La CLI tourne dans un sous-processus avec un *audit hook* : socket
  `connect`/`bind`, `sqlite3.connect`, ouverture en écriture, `mkdir`.
- `os.environ` y est remplacé par un espion qui note toute lecture de la variable
  de clé.
- Aucun service n'écoute sur les ports configurés ; aucun n'est contacté.

**Résultat : 57/57 attentes, 0 échec, 7 remarques (aucune n'est un défaut bloquant).**

## Confirmé

- **Inspection pure** : sur tous les cas, aucun socket, aucune ouverture SQLite
  (donc ni Store ni Runtime), aucune écriture, `--state` jamais créé, **valeur de
  clé jamais lue**. Ni clé ni chemin dans stderr. `server_contacted`,
  `secret_value_read` et `authorizes_execution` restent `false`.
- **Adresses** :
  - acceptées : `127.0.0.1`, `[::1]`, https, sans port, barre finale ;
  - refusées : `localhost`, 127.0.0.2, `127.1`, `0x7f.0.0.1`, `::ffff:127.0.0.1`,
    point final, chiffres pleine chasse, ports 0 et 65536, chemin, requête,
    `user@`, ftp, espace insécable, espace de largeur nulle, DEL.
- **Types et fournisseurs** : booléens à la place d'entiers, bornes, flottant
  pour un entier, option de l'autre fournisseur, `api_key_env` sur Ollama, clé
  inconnue, `allow_non_loopback`, clé écrite en clair dans le fichier → refusés.
- **Fichiers** : 0644, 0640, lien final, FIFO (sans blocage), 17 Kio, clé
  dupliquée → refusés. Une réécriture de même taille pendant la lecture →
  `MODEL_CONFIG_CHANGED_OR_TOO_LARGE`.
- **Identités** :
  - chaque option testée change l'identité : `num_predict`, `temperature`,
    `timeout`, `max_output_bytes`, port, `max_tokens`, `context_tokens`, nom de
    la variable de clé ;
  - changer la **valeur** de la clé sans renommer la variable garde l'identité
    (limite documentée) ;
  - la barre finale est normalisée.

## Remarques

- **Caractères invisibles dans le nom du modèle** : U+200B (largeur nulle) et
  U+202E (inversion bidi) sont acceptés. L'adaptateur ne refuse que les espaces
  au sens `isspace()`.
  - Deux configurations peuvent sembler identiques à l'écran et avoir des
    identités différentes ; le nom envoyé au serveur contient ces caractères.
  - Les sorties JSON et humaine les affichent échappés (`‮`), ce qui limite
    la tromperie.
  - Proposition : refuser les caractères non imprimables (`isprintable()`) dans
    `model`.
- **`api_key_env` accepte tout nom valide** (`HOME`, `AWS_…`). Sa valeur sera
  envoyée en `Bearer` au point configuré à l'exécution. C'est en loopback
  seulement et c'est un choix de l'opérateur, mais à dire dans la documentation :
  un fichier de configuration reçu d'ailleurs peut ainsi viser une autre variable.
- **Port `011434`** : même destination que 11434, mais identité différente (le
  texte brut entre dans le manifeste). C'est sans danger : l'identité est
  seulement plus stricte que la destination.
- **API Python ≠ politique CLI** (différences voulues, documentées) : les
  adaptateurs acceptent `localhost`, l'absence de `num_predict`, et une adresse
  hors loopback avec `allow_non_loopback=True`. La CLI refuse les trois.

## Limites

- Aucun serveur réel. On ne vérifie ni la disponibilité ni la qualité d'un
  modèle.
- L'espion ne voit que les accès Python à `os.environ`, pas un accès C direct.
- Essais en root (refus de propriétaire non observable).
