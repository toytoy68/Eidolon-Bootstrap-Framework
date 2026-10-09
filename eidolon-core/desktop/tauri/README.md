# Coquille Tauri 2 de consultation — prototype G053

Claude, 07/10/2026. Fiche [C-TASK-G053](../../collaboration/tasks/C-TASK-G053.md),
décision [C-D14](../../docs/CADRAGE-DECISIONS-2026-10-05.md) (Tauri).
**Prototype de consultation.** Rien n'est installé, signé ni distribué ; le
[client connecté](../connected/README.md) reste le client de référence.

## Ce que fait la coquille, et rien d'autre

Une seule fenêtre, ouverte sur `http://127.0.0.1:<port>/`. C'est l'adresse
locale où le tunnel SSH expose le client **servi par Core**. La page parle à
Core par `fetch`, en même origine, exactement comme dans un navigateur. Le
contrat de Core (Host, Origin, CSP) reste inchangé et n'est pas contourné.

| Garde | Moyen |
| --- | --- |
| Pas d'IPC pour la page distante | aucune commande Rust, aucun plugin, aucun dossier `capabilities/` : l'ACL Tauri refuse tout appel (mesuré) |
| Une seule origine | `on_navigation` : schéma `http`, hôte exactement `127.0.0.1`, port exact, sans identifiants. `localhost`, `[::1]`, une autre adresse ou un autre port sont refusés |
| Pas de nouvelle fenêtre | `on_new_window` → `Deny` (`window.open` et `target=_blank`) |
| Pas d'outils de développement | `.devtools(false)`, y compris en mode debug |
| Pas de paramètre libre | seul `--port N`, **une fois** (ou `EIDOLON_CORE_PORT`), est accepté, de 1024 à 65535 ; défaut 8765. Tout autre argument, une valeur non UTF-8, ou une variable présente mais invalide (même avec `--port`) → code 2 |
| Diagnostics sans écho (G054) | messages **constants** : aucun argument, aucune valeur de variable ni aucune URL refusée n'est réaffiché (un jeton ou une adresse privée pourrait s'y trouver) |
| Pas d'installation | `bundle.active=false` ; aucun démarrage automatique, aucun raccourci, aucune écriture système |

La coquille **ne lance pas** le tunnel, ne lit ni ne stocke le jeton, et ne
fait aucun appairage. Le jeton est saisi dans la page et gardé en mémoire de
la page, comme dans le navigateur.

## Construire et lancer (développement)

Prérequis Linux (Ubuntu 24.04) : Rust stable, `libwebkit2gtk-4.1-dev`,
`build-essential`.

```sh
cd eidolon-core/desktop/tauri
cargo test                      # règles d'origine et de port
cargo build                     # binaire : target/debug/eidolon-consultation
# tunnel SSH ouvert vers Core sur 127.0.0.1:8765 (lanceur existant), puis :
./target/debug/eidolon-consultation --port 8765
```

Versions exactes : `tauri =2.12.1`, `tauri-build =2.7.1`, `Cargo.lock`
versionné. Aucune CLI Tauri ni Node n'est nécessaire.

## Icône « e » du logo programme (validé par toytoy le 08/10/2026)

L'icône combine deux pièces validées, sans les modifier :

- le **cadre** de [l'icône de référence](../../assets/branding/eidolon-icon-reference.png) :
  carré arrondi, liseré et halo bleus, coins rendus transparents ;
- le **« e » manuscrit** du [logo programme](../../assets/branding/eidolon-logo.png).
  Ce sont ses propres pixels, découpés avant « IDOLON » avec le début de l'orbite,
  bords estompés et composés en mode *screen* sur l'intérieur repeint.

Fichiers :

- générateur :
  [docs/proposals/2026-10-08-claude-icon-variants/logo_e.js](../../docs/proposals/2026-10-08-claude-icon-variants/logo_e.js) ;
- assembleur :
  [build_ico.py](../../docs/proposals/2026-10-08-claude-icon-variants/build_ico.py)
  (copie octet pour octet des rendus) ;
- `icon.png` (512 px, RGBA), 128 et 256 px : version complète ;
- `icon.ico` (9 images) et `32x32.png` : de 16 à **32 px**, le « e » seul,
  agrandi et éclairci sur carré plat ; de 40 à 256 px, la version complète.
  Le 32 px simplifié est un choix de toytoy du 09/10/2026 (indice e/fond 10,4
  contre 5,5, [G079](../../docs/validation/2026-10-08/claude-g079/README.md)).

Les fichiers sont déclarés dans `bundle.icon`. L'empaquetage reste désactivé et
le rendu Windows n'a pas été vu.
[Planche de lisibilité](../../docs/proposals/2026-10-08-claude-icon-variants/logo-e-lisibilite.png) :
le trait du logo est fin, mais le « e » reste reconnaissable à 16 px.

## Limites connues

- **`window.__TAURI_INTERNALS__` est injecté** dans la page distante, comme
  sur toute webview Tauri. La protection repose sur l'ACL : la page ne
  détient **aucune** permission. Toute future capacité devra exclure cette
  fenêtre, ou n'accorder `remote.urls` qu'en connaissance de cause.
- `on_navigation` filtre les navigations, pas les requêtes. Une requête
  `fetch` vers une autre origine part si la page le décide. Le client servi
  par Core l'interdit par sa CSP (`connect-src 'self'`), pas la coquille.
- La webview garde un dossier de données
  (`~/.local/share/local.eidolon.consultation` sous Linux). Le jeton n'y a
  pas été trouvé.
- Windows : **ni compilé ni lancé**. WebView2, le mode d'exécution sans
  console (`windows_subsystem`) et la sémantique de navigation restent à
  vérifier sur le poste.

## Décisions ouvertes (non prises ici)

| ID | Question |
| --- | --- |
| DT1 | Comment l'application connaît-elle le port : argument (actuel), fichier écrit par le lanceur, ou saisie dans une page locale ? |
| DT2 | L'application lance-t-elle elle-même le tunnel SSH, ou reste-t-elle séparée du lanceur PowerShell (actuel) ? |
| DT3 | Appairage durable (C-D12) : où et comment garder la clé de l'appareil sous Windows. Non conçu ici ; aucune commande distante. |
| DT4 | Distribution Windows : installateur ou exécutable seul, mode WebView2 (programme d'amorçage ou version fixe), signature. |
| DT5 | Effacer les données de la webview à la fermeture, ou les garder ? |
