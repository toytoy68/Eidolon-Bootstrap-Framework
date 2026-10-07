# G053 — premier lot Tauri 2 en consultation

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G053](../../../../collaboration/tasks/C-TASK-G053.md).
Base : `48a33fc`, après C072. Livrable :
[`desktop/tauri/`](../../../desktop/tauri/README.md), qui contient le contrat
de sécurité et les décisions ouvertes. Le client existant n'est pas modifié.

## Sources lues

Le site `v2.tauri.app` est **refusé par le proxy** de cette session. J'ai
donc lu le code source officiel publié sur crates.io :

| Crate | Version | SHA-256 de l'archive |
| --- | --- | --- |
| `tauri` | 2.12.1 (01/10/2026) | `ed99ee96…f2ace9` |
| `tauri-utils` | 2.10.1 | `2ff55a61…18621ee` |

Points relevés dans ces sources :

- `WebviewWindowBuilder::on_navigation` : renvoyer `false` annule la
  navigation.
- `on_new_window` avec `NewWindowResponse::Deny` refuse l'ouverture.
- `devtools(bool)`.
- `CapabilityRemote.urls` : une origine distante n'obtient une permission
  que par une capacité qui la nomme.
- `security.capabilities` vide : toutes les capacités du dossier
  `./capabilities/` sont incluses. Ce dossier n'existe pas ici.
- `freezePrototype` s'applique à toutes les webviews.

Versions des registres le même jour : `tauri` 2.12.1, `tauri-build` 2.7.1,
`@tauri-apps/cli` 2.12.1. C'est la même version que l'étude G010.

## Qualification, séparée comme demandé

| Niveau | Résultat |
| --- | --- |
| **Compilation Linux** | OK : Ubuntu 24.04, rustc et cargo 1.97.0, WebKitGTK 2.52.6 installé dans le conteneur. Debug, puis release en 2 min 18 ; binaire release 6,2 Mo |
| **Tests unitaires** | 2/2 : bornes du port ; origine exacte (15 URL refusées, dont `localhost`, `[::1]`, `127.0.0.2`, `https`, identifiants, `file:`, `data:`, `javascript:`, `tauri:`) ([sortie](cargo-test.txt)) |
| **Lancement Linux** (Xvfb) | OK en debug et en release ([sortie release](live-release.txt)) |
| **Windows réel** | **non fait** : ni compilation MSVC, ni WebView2, ni poste |

## Lancement Linux : ce qui a été observé

Harnais : [live_g053.py](live_g053.py). Il tourne sous Xvfb et ne lance que
ses propres processus.

| Cas | Résultat |
| --- | --- |
| L0 `--port 80`, `--port abc`, `--url …` | code 2 avant toute fenêtre |
| L1 vrai serveur Core (jeu bêta synthétique) | la fenêtre charge `/`, `app.js`, `style.css` |
| L1 saisie du jeton (xdotool), puis clic sur une mission | `/v1/health`, `/v1/missions`, puis le détail ; « Connecté en lecture seule » ; Host toujours `127.0.0.1:<port>` ; Origin absent ou identique ; jeton absent des URL ([capture](l1-core-client.png)) |
| L2 page sonde : globaux | `__TAURI_INTERNALS__` **présent**, `__TAURI__` absent |
| L2 `invoke("plugin:app\|version")` | **refusé** par l'ACL |
| L2 `location.href` et `<iframe>` vers une autre origine en boucle locale | **refusés** : 0 requête reçue par l'autre serveur ; la page reste sur son origine |
| L2 `window.open` | `null`, 0 requête |
| L2 `fetch` vers l'autre origine | **parti** : la coquille ne filtre pas les requêtes. Dans le vrai client, la CSP de Core (`connect-src 'self'`) l'interdit |
| D données de la webview | 18 entrées dans `~/.local/share/local.eidolon.consultation` ; jeton absent |

Au premier essai, le jeton tapé par `xdotool` a été déformé par le clavier
nu de Xvfb (majuscules, `_`, `-`) : `TOKEN_FORMAT`. Le harnais utilise donc
un jeton synthétique en minuscules et chiffres, que le serveur accepte. Ce
n'est pas un défaut de l'application.

## Limites

- Linux seulement, sous Xvfb sans accélération (avertissements libEGL sans
  effet observé).
- Windows est entièrement à qualifier sur le poste de recette. WebView2 et
  WebKitGTK n'exposent pas toujours les mêmes événements de navigation.
- Aucun tunnel SSH réel : le serveur Core est lancé directement sur
  `127.0.0.1`, ce qui équivaut au point d'entrée local du tunnel.
- L'icône est un disque généré pour la compilation, pas une identité
  visuelle.
- Ni la CLI Tauri, ni un bundle, ni une signature n'ont été utilisés.
