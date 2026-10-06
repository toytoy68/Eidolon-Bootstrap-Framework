# Client de consultation connecté — C-TASK-G031

Auteur : Claude, 06/10/2026. Contrat : [HTTP-READ-API.md](../../docs/HTTP-READ-API.md)
(`eidolon-http-read/1`). Ce client est **réellement connecté** au serveur
`http_api` ; il ne contient aucun scénario simulé. Le prototype
`desktop/prototype/` reste séparé et inchangé.

## Ce qu'il fait

- Il demande un jeton de lecture, le garde **en mémoire seulement** (le champ
  est vidé dès l'envoi), et l'oublie à la déconnexion, au rechargement ou
  après un 401.
- Il lit `/v1/health`, puis la liste (`mission-list/1`, pages de 100, au plus
  3 pages, donc 200 missions affichées au maximum).
- Sélectionner une mission demande une capture (`client-sync/1`). « Actualiser »
  fait un `poll` avec le curseur exact. La case « Relire toutes les 10 s »
  répète cette relecture ; elle est décochée par défaut.
- `RESET_REQUIRED` n'est jamais appliqué en silence : un bandeau demande de
  recharger la capture, et la liste périmée reste affichée jusqu'à « Relire la
  liste ».
- En cas de panne, il garde le dernier état reçu, daté et marqué périmé.

- **Reçu historique (G036)** : pour la mission sélectionnée, saisir un
  identifiant client et une clé de commande, puis « Consulter le reçu »
  (`POST /v1/command-receipt`). `FOUND` est un **enregistrement daté**, affiché
  à côté de la capture actuelle, jamais fusionné avec elle. `NOT_FOUND` garde
  l'incertitude : ce n'est pas une permission de renvoi. `STORE_CHANGED`
  bloque toute autre consultation jusqu'à une reconnexion explicite.

Il n'y a **aucune commande** : ni accord, ni lancement, ni annulation.

## Garde-fous contre les mélanges

| Risque | Protection |
| --- | --- |
| réponse arrivée après déconnexion, 401 ou nouveau jeton | `connEpoch` : la réponse est ignorée |
| réponse d'une ancienne sélection | jeton de sélection (`mission-list-state.js`) |
| page d'une ancienne liste | époque de liste et curseur exact |
| reconnexion à une **autre base** (`store_id` différent) | tout l'affichage précédent est effacé, avec un message |
| liste servie pour une autre base que `/v1/health` | refus, rien n'est affiché |
| identifiant de mission mal formé | jamais transformé en chemin de requête |

Les valeurs de Core sont écrites avec `textContent`. Le code n'utilise pas
`innerHTML`, `localStorage`, `sessionStorage` ni de cookie. Les requêtes
partent vers `/v1/...` sur la même origine, sans cookie ni redirection suivie,
avec un délai de 10 s.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `index.html`, `style.css` | page et mise en page (une colonne sous 760 px) |
| `src/session.js` | session : transport injecté, erreurs, époques |
| `src/view.js` | rendu DOM |
| `src/main.js` | démarrage navigateur, `fetch` |
| `app.js` | **fichier généré** par `build.js` : `sync-state.js` et `mission-list-state.js` du prototype, puis les trois sources |
| `tests/session.test.js` | 20 tests sur transport scripté (fixtures), dont 6 reçus |
| `tests/server.test.js` | 6 tests sur le **vrai serveur** Python et dans Chromium |
| `tests/receipts.test.js` | 3 tests reçus sur le vrai serveur et le jeu bêta C-009g (dont 1 Chromium) |
| `tests/helpers.js` | outils partagés des bancs réels (CLI, jeu bêta, serveur, nettoyage) |

Le serveur ne sert que trois fichiers (`/`, `/app.js`, `/style.css`) : d'où le
fichier unique `app.js`. Après toute modification d'une source :

```sh
cd eidolon-core
node desktop/connected/build.js          # régénère app.js
node desktop/connected/build.js --check  # échoue si app.js est en retard
NODE_PATH=<dossier contenant playwright> node --test "desktop/connected/tests/*.test.js"
```

Sans Python 3.11, sans Playwright ou sans exécutable Chromium, les tests concernés sont marqués
« skipped », jamais réussis.

## Lancer

Suivre [HTTP-READ-API.md](../../docs/HTTP-READ-API.md), en ajoutant
`--web-root desktop/connected` à la commande du serveur, puis ouvrir
`http://127.0.0.1:8765` (directement ou par le tunnel SSH). Saisir le contenu
du fichier jeton. Ne pas ouvrir `index.html` en `file://` : la page doit être
servie par Core.

## Limites

- Essais faits sur Linux, Chromium headless, serveur local sur `127.0.0.1`.
  Pas d'essai de tunnel SSH ni de navigateur Windows.
- La liste n'est pas relue automatiquement : son libellé peut retarder sur le
  détail (par exemple « Nouvelle » dans la liste, « Annulée » dans le détail)
  jusqu'à « Relire la liste ».
- Les événements affichés sont ceux reçus **depuis la sélection** ; le passé
  antérieur à la capture n'est pas récupéré (contrat `client-sync/1`).
- Le jeton est une clé de lecture, pas une identité humaine.
