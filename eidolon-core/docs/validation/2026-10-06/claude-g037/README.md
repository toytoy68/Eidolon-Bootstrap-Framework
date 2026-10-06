# G037 — accessibilité et petits écrans du client connecté

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G037](../../../../collaboration/tasks/C-TASK-G037.md).
Base : `8617a95` (client G036). Fichiers modifiés : `desktop/connected/`
seulement ; le prototype simulé n'est pas touché et aucune dépendance n'est
ajoutée.

Banc : [tests/a11y.test.js](../../../../desktop/connected/tests/a11y.test.js),
8 tests dans un **vrai Chromium** (headless, Linux), sur le **vrai serveur**
avec le jeu synthétique C-009g. Les mêmes tests ont été lancés sur le client
d'avant (`CONNECTED_WEB_ROOT` vers une copie de `8617a95`) et d'après.

- [avant : 3 échecs sur 8](a11y-before-8617a95.txt)
- [après : 8/8](a11y-after.txt)
- [suite complète du client : 37/37](node-tests.txt)

## Défauts trouvés et corrigés

| # | Défaut (avant) | Correction |
| --- | --- | --- |
| A1 | Au clavier, sélectionner une mission **renvoyait le focus en haut de la page** : la liste est reconstruite à chaque rendu. Prouvé en retirant seulement la correction : focus sur `body` | le rendu replace le focus sur le bouton de la même mission |
| A2 | Après la connexion, le focus restait sur le champ jeton vidé | le focus va à la liste des missions (`#missions`) ; après un refus, il reste sur le champ jeton |
| A3 | Une clé longue dans le résultat de reçu élargissait la page : **+12 px à 640 px** (zoom 200 %) et **+332 px à 320 px** | `overflow-wrap: anywhere` sur les panneaux |

## Vérifié sans défaut

- Indicateur de focus visible (contour ≥ 2 px) sur les 20 premiers arrêts de
  tabulation.
- Contraste du texte ≥ 4,5:1 en thème clair et sombre (texte désactivé
  exclu, comme le permet WCAG).
- Commandes d'au moins 24 px (44 px en pratique) aux trois tailles.
- Aucune animation ni transition avec `prefers-reduced-motion`.
- Statuts annoncés par des zones `aria-live` existantes.

## Captures (données synthétiques)

[1280×720](g037-1280x720.png), [clavier 1280×720](g037-keyboard-1280x720.png),
[zoom 200 %](g037-zoom.png), [320×640](g037-320x640.png),
[thème sombre](g037-dark.png).

## Non exécuté

- Lecteur d'écran réel (NVDA, Narrator) : non disponible ici.
- Windows, Edge, mise à l'échelle Windows.
- Zoom navigateur réel : simulé par une fenêtre de 640×360 CSS avec un
  facteur de pixel 2.
- Le bandeau `RESET_REQUIRED` est annoncé (`role="alert"`) sans déplacer le
  focus ; ce choix n'a pas été testé avec un utilisateur.
