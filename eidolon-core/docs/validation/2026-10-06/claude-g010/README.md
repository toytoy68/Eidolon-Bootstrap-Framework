# Preuves C-TASK-G010 — faisabilité du client Windows

Auteur : Claude, 06/10/2026. Étude : [WINDOWS-CLIENT-FEASIBILITY.md](../../../desktop/WINDOWS-CLIENT-FEASIBILITY.md).
Base : `e9526de` (fusion de `1f2a76d`). Aucun essai sous Windows.

## Collecte des sources (exécutée ici, Linux)

```sh
git clone --depth 1 --filter=blob:none --sparse https://github.com/tauri-apps/tauri-docs   # 712e12a755d3
git clone --depth 1 --filter=blob:none --sparse https://github.com/electron/electron       # 6b48d9813bd7
git ls-remote https://github.com/tauri-apps/tauri refs/tags/tauri-v2.12.1                  # 30da1fd6e17d
git ls-remote https://github.com/electron/electron refs/tags/v44.5.1                       # b4404a4d56d0
curl https://registry.npmjs.org/electron/latest          # 44.5.1, MIT
curl https://pypi.org/pypi/PySide6/json                  # 6.11.2 ; roues win_amd64 Essentials/Addons
curl -I https://github.com/electron/electron/releases/download/v44.5.1/electron-v44.5.1-win32-x64.zip  # 157 998 329 octets
curl https://raw.githubusercontent.com/qt/qtbase/6.11/src/widgets/util/qsystemtrayicon.cpp
curl https://raw.githubusercontent.com/qtproject/pyside-pyside-setup/6.11/sources/pyside6/doc/deployment/deployment-pyside6-deploy.rst
```

Les sites v2.tauri.app, electronjs.org et doc.qt.io ne répondent pas depuis
cette session ; leurs sources dans les dépôts ont été lues à la place.
[Extraits exacts cités par l'étude](source-excerpts.md).

## Essai (spike) unique

Question précise : le prototype dépend-il de `file://` ? Tauri sert ses pages
depuis un protocole propre, Electron souvent depuis une origine locale.

[spike-origin-http.js](spike-origin-http.js) sert `desktop/prototype/` en
`http://127.0.0.1:8765` (serveur Python local), puis joue le parcours G009
(accord, exécution simulée, résultat) et le rattrapage client-sync/1.
[Résultat](spike-origin-http.json) : état « Réussie — résultat daté »,
10 références, une seule origine de requêtes (`127.0.0.1:8765`), 0 erreur.
La CSP de la page est conservée.

Limite : Chromium sous Linux, pas WebView2 ; aucune conclusion sur Windows.
Aucun squelette Tauri ou Electron n'a été construit : un binaire Linux ne
lèverait aucune des deux inconnues bloquantes.
