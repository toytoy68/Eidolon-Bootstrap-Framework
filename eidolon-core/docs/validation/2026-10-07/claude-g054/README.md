# G054 — diagnostics et arguments de la coquille Tauri

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G054](../../../../collaboration/tasks/C-TASK-G054.md).

Base : `621d71b` (intégration Codex de G050–G053). Seuls
`desktop/tauri/src/origin.rs` et `src/main.rs` sont modifiés. Restent
inchangés :

- la fenêtre unique ;
- l'ACL vide : aucune commande, aucun plugin, aucune capacité ;
- l'absence de tunnel et d'appairage ;
- le client connecté.

## Changements

| Avant (G053) | Après |
| --- | --- |
| `argument inconnu : <valeur>` réaffichait l'argument (un jeton passé par erreur, par exemple) | codes constants (`InputError`), sans aucune valeur |
| `navigation refusée vers <origine>` et `nouvelle fenêtre refusée vers <origine>` | `navigation refusée : autre origine que le client Core` et `nouvelle fenêtre refusée` |
| `--port` répété : la dernière valeur gagnait | refusé : `--port donné plusieurs fois` |
| argument non UTF-8 : **panique** Rust (code 101, valeur affichée) | refusé, code 2 (`args_os`) |
| variable `EIDOLON_CORE_PORT` non UTF-8 : **ignorée en silence** (port par défaut) | refusée (`var_os`) |
| variable invalide + `--port` valide : la variable était ignorée | refusée : une valeur présente mais invalide n'est jamais écartée en silence |

## Vérifications exécutées

```sh
cd eidolon-core/desktop/tauri
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo build --locked
python3 ../../docs/validation/2026-10-07/claude-g054/check_g054.py <target>/debug/eidolon-consultation
PYTHONPATH=src xvfb-run -a python3 docs/validation/2026-10-07/claude-g053/live_g053.py <binaire> <dossier>   # depuis eidolon-core/
```

| Contrôle | Résultat |
| --- | --- |
| rustfmt, clippy `-D warnings` | propres |
| Tests unitaires | **5/5** : bornes et sources du port, formes d'arguments, non-UTF-8 (Unix), absence d'écho pour 5 secrets synthétiques (jeton, adresse IP de documentation, chemin, échappement terminal, CRLF + en-tête) dans toutes les positions, origine exacte (17 URL refusées) |
| Binaire, 13 entrées invalides | **13/13** : code 2, une seule ligne constante, aucune valeur réaffichée ([après](check-debug.txt)) |
| Même banc sur le binaire G053 | **7/13** : 2 échos du secret, 1 panique non-UTF-8, 3 entrées acceptées ([avant](check-before-g053-release.txt)) |
| Banc de lancement G053 rejoué | client Core chargé et connecté ; `invoke` refusé ; navigation refusée avec le **message constant** ([sortie](live-after.txt)) |

Les 3 entrées acceptées par G053 (`--port` répété, variable non UTF-8,
variable invalide avec `--port`) ont ensuite échoué faute d'écran (le banc
retire `DISPLAY`). Une panique GTK, et non un refus, en est la preuve.

## Limites

- Linux seulement. Windows : non compilé, non lancé. Sous Windows,
  `args_os` donne de l'UTF-16 ; non testé.
- Les messages de Tauri, de WebKitGTK ou de GTK eux-mêmes ne sont pas sous
  le contrôle de la coquille. Ils peuvent contenir des chemins système.
- Le test « non UTF-8 » unitaire n'existe que sous Unix.
