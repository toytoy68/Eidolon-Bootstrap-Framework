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
- **Contrôle d'intégrité du reçu (G048)** : `receipt_binding` est affiché.
  - `EVENT_HASH` : liaison au journal vérifiée par Core.
  - `LEGACY_FIELDS` : contrôle limité (ancien format).
  - Champ absent (serveur plus ancien) : « non précisé », jamais `EVENT_HASH`.
  - Toute autre valeur : réponse refusée.

  Aucun de ces cas n'est une signature ni une preuve d'exécution.

- **Missions de recherche synthétique (G060)** : l'objectif
  `research_retrieval.synthetic` s'affiche « Recherche synthétique (pages
  fixes) ». Une note distingue :
  - récupération **complète** (pages fixes lues et vérifiées, pas une
    information confirmée) ;
  - **partielle** (moins de pages que demandé, objectif non atteint) ;
  - **sans preuve** (aucune page vérifiée).

  La requête et le texte des pages ne sont **pas** dans la projection Core,
  et ne s'affichent donc jamais. Un objectif ou une issue inconnus restent
  affichés tels que reçus.

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
| `src/archives.js` | état pur du catalogue paginé des archives : validation C-030, générations, pages figées (G066) |
| `src/session.js` | session : transport injecté, erreurs, époques |
| `src/view.js` | rendu DOM |
| `src/main.js` | démarrage navigateur, `fetch` |
| `app.js` | **fichier généré** par `build.js` : `sync-state.js` et `mission-list-state.js` du prototype, puis les quatre sources |
| `tests/session.test.js` | tests sur transport scripté (fixtures), dont 7 reçus (G036, G048) |
| `tests/server.test.js` | 6 tests sur le **vrai serveur** Python et dans Chromium |
| `tests/receipts.test.js` | 3 tests reçus sur le vrai serveur et le jeu bêta C-009g (dont 1 Chromium) |
| `tests/research.test.js` | 3 tests missions de recherche C-021 sur projections Core réelles (dont 1 Chromium) |
| `tests/a11y.test.js` | 8 tests Chromium : clavier, focus, zoom 200 %, 320×640, contraste, mouvement réduit (G037) |
| `tests/integration/e2e.test.js` | 6 tests de bout en bout : pagination réelle, troncature à 200, reset entre deux pages, absence de réémission, nettoyage sur échec, 150 missions dans Chromium (G038) |
| `tests/archives.test.js` | 9 tests archives (G066) : 6 sur réponses scriptées, 2 sur le vrai serveur C-030, 1 Chromium clavier et 360 px |
| `tests/helpers.js` | outils partagés des bancs réels (CLI, jeu bêta, serveur, nettoyage) |

Le serveur sert trois fichiers obligatoires (`/`, `/app.js`, `/style.css`) et le
logo facultatif `/eidolon-logo.png`. Les scripts restent réunis dans `app.js`.
Le logo G078 est affiché après décodage ; le titre textuel reste disponible en
cas d'absence ou d'échec. Aucun répertoire de fichiers arbitraires n'est exposé.
Après toute modification d'une source :

```sh
cd eidolon-core
node desktop/connected/build.js          # régénère app.js
node desktop/connected/build.js --check  # échoue si app.js est en retard
NODE_PATH=<dossier contenant playwright> node --test "desktop/connected/tests/**/*.test.js"
```

Sans Python 3.11, sans Playwright ou sans exécutable Chromium, les tests concernés sont marqués
« skipped », jamais réussis.

## Archives de recherche (G066)

Panneau « Archives de recherche » sous les missions, contrat
[HTTP-RESEARCH-ARCHIVES.md](../../docs/HTTP-RESEARCH-ARCHIVES.md) :

- lecture **sur demande seulement** (« Charger les archives », puis « Archives
  suivantes » par pages de 50) ; rien n'est lu à la connexion ni relancé seul ;
- métadonnées seulement : nom, date enregistrée, nombres de recherches. Ni lien,
  ni téléchargement, ni texte de recherche, ni identifiant de mission ou de garde ;
- chaque page est contrôlée : drapeaux de garantie exacts, même base que la
  connexion, même catalogue (`catalog_sha256`, tête de chaîne, totaux) que la
  première page, numéros contigus. Sinon elle est ignorée ;
- `RESET_REQUIRED`, un refus ou une coupure **figent** la liste affichée
  (« Liste figée ») jusqu'à un rechargement explicite, qui remplace tout :
  deux catalogues ne sont jamais concaténés. Une nouvelle connexion repart vide ;
- les refus propres aux archives (`ARCHIVES_NOT_CONFIGURED`, `ARCHIVES_BUSY`,
  `ARCHIVES_UNAVAILABLE`, curseur refusé) restent dans ce panneau et ne
  déclarent pas la connexion perdue ;
- « Cohérence vérifiée par Core » n'est ni une authenticité ni une preuve que
  l'export a été pris en compte dans le journal actif.

Le serveur doit être lancé avec `--research-archives DOSSIER`.

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
- Archives : essayées sur le jeu bêta `research-archives` (3 archives) seulement.
  Plus de 1 000 archives ne sont jamais conservées côté client.


## C-047 — Espaces Image et Vidéo

Deux cartes à l'accueil ouvrent des formulaires créer/modifier/analyser.
Brouillons limités à la mémoire de page, conservés entre les deux espaces,
effacés au rechargement, pagehide ou clic Déconnexion. Aucun upload, lecture
de contenu, stockage navigateur ou appel média. Un texte annonce l'exécution
indisponible ; aucun bouton de commande, même désactivé, n'est présenté.
Seules les métadonnées du fichier choisi sont utilisées ; validation serveur
indispensable lors du futur raccordement. [Contrat](../../docs/MEDIA-AGENTS.md).

Source : src/media-agents.js, ajoutée à build.js. G088 peut modifier l'accueil
en conservant ce module et son montage. L'en-tête/logo G078 est intégré (C-053).
