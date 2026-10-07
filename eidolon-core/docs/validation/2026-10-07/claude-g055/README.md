# G055 — frontières réseau de la coquille Tauri et CSP de Core

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G055](../../../../collaboration/tasks/C-TASK-G055.md).

Base : `7b737f4`. La coquille G054 a été recompilée sans changement de
source. `http_api.py` et le client ne sont pas modifiés.

```sh
cd eidolon-core
PYTHONPATH=src xvfb-run -a python3 docs/validation/2026-10-07/claude-g055/bench_g055.py <target>/debug/eidolon-consultation
```

## Méthode

Tout reste en boucle locale :

- une page sonde, servie sur la même origine que la fenêtre, tente
  **16 sortes de requêtes** vers un second serveur local ;
- ce second serveur, l'« autre origine », note chaque requête reçue ;
- la sonde tourne deux fois : **sans CSP** (ce que la coquille arrête
  seule), puis **avec la CSP exacte de Core**, relue sur une vraie réponse
  du serveur de lecture et non recopiée.

Deux passages donnent des résultats identiques : [passage 1](run1.txt),
[passage 2](run2.txt).

Ce qu'envoie Core : la même CSP sur `/`, `app.js`, l'API et les 404 :

```
default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self';
base-uri 'none'; frame-ancestors 'none'; form-action 'none'
```

## Résultats : qui arrête quoi

| Tentative vers une autre origine | Sans CSP : coquille seule | Avec la CSP de Core | Qui l'arrête |
| --- | --- | --- | --- |
| `fetch` | **atteinte** | arrêtée | CSP `connect-src` |
| XHR | **atteinte** | arrêtée | CSP `connect-src` |
| WebSocket | **atteinte** (requête d'upgrade reçue) | arrêtée | CSP `connect-src` |
| EventSource | **atteinte** | arrêtée | CSP `connect-src` |
| `sendBeacon` | **atteinte** | arrêtée | CSP `connect-src` |
| image | **atteinte** | arrêtée | CSP `img-src` |
| script | **atteinte** et exécuté | arrêté | CSP `script-src` |
| feuille de style | **atteinte** | arrêtée | CSP `style-src` |
| image de fond CSS | **atteinte** | arrêtée | CSP `img-src` |
| iframe | arrêtée | arrêtée | **navigation** de la coquille (et CSP `frame-src`) |
| envoi de formulaire POST | arrêté | arrêté | **navigation** (et CSP `form-action`) |
| navigation `location.href` | arrêtée | arrêtée | **navigation** de la coquille |
| `window.open` | `null`, arrêté | idem | **nouvelle fenêtre** refusée |
| lien `target=_blank` | arrêté | arrêté | nouvelle fenêtre et navigation |
| Worker d'une autre origine | aucune requête | aucune requête | règle de même origine des Workers |
| `<link rel=prefetch>` | aucune requête | aucune requête | WebKitGTK ne l'a pas chargé (pas une garde) |
| IPC `__TAURI_INTERNALS__` | présent, `invoke` refusé (G053) | idem | **ACL** Tauri vide |

## Conclusions

- **Les trois couches sont distinctes.**
  - La règle de navigation de la coquille arrête la page ou un cadre qui
    changerait d'origine, et les nouvelles fenêtres.
  - La CSP de Core arrête les **sous-ressources et connexions** : fetch,
    XHR, WebSocket, EventSource, beacon, images, scripts, styles.
  - L'ACL vide arrête l'IPC.
- **La coquille seule ne filtre pas le réseau de la webview** : sans CSP,
  9 tentatives sur 16 atteignent l'autre origine. La protection du vrai
  client dépend donc de la CSP envoyée par Core sur **chaque** réponse.
  C'est le cas aujourd'hui, mais une page servie sans cet en-tête ne serait
  pas protégée par la coquille.
- Avec la CSP de Core : **0 requête** reçue par l'autre origine, et 6
  directives violées sont signalées à la page.

## Proposition (non appliquée)

Toutes les réponses de Core passent par une seule fonction, `_send`, qui
pose la CSP. Le test actuel (`test_http_api.py`) ne vérifie pourtant que
`connect-src 'self'`, et sur `/` seulement.

Proposition pour Codex : un test qui exige la **CSP complète** sur un asset,
une réponse d'API et une erreur. Une future réponse qui contournerait
`_send` serait alors détectée.

Ne pas ajouter de filtre réseau dans la coquille. WebKitGTK et WebView2
n'offrent pas le même mécanisme, et cela ne remplacerait pas la CSP.

## Limites

- Linux et WebKitGTK 2.52.6 seulement, sous Xvfb. **Windows/WebView2 non
  testé** : la sémantique de `on_navigation`, de `on_new_window`, du
  préchargement et des Workers peut différer.
- Le préchargement non observé ne prouve pas qu'il serait bloqué ailleurs.
- Aucune requête n'est envoyée hors de `127.0.0.1`. Le DNS, les proxys et
  IPv6 ne sont pas couverts.
- La CSP ne protège pas d'un script déjà autorisé (`'self'`) qui serait
  compromis côté serveur.
