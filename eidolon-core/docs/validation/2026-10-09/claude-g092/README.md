# G092 — Reconnexion et accessibilité du chat

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G092.

## Livré

- **Reprise après un rechargement ou une reconnexion** :
  - nouvelle route `recent` : conversations non vides **de ce client**, la
    plus récente d'abord, en lecture seule ;
  - une fois la clé acceptée, la page propose « Reprendre (n échanges,
    dernier le …) » ;
  - `resume` relit la conversation (`page`), restaure les échanges et la
    dernière proposition, et place le focus sur le message ;
  - un tour resté **sans réponse** devient « Réponse en préparation… —
    Vérifier la réponse » : la vérification réutilise **sa** clé, Core
    rejoue, il n'y a jamais de doublon ;
  - l'état d'une validation n'est **pas** supposé après une reprise. Revalider
    une proposition déjà validée donne un refus expliqué : « déjà validée
    (peut-être avant une reprise) : voir les missions ».
- **Aucune commande rejouée automatiquement** : la reprise ne fait que lire
  (vérifié : aucune requête `turn`, `submit`, `cancel` ni `resolve`).
- Messages de refus de validation en clair : `PROPOSAL_ALREADY_SUBMITTED`,
  `PROPOSAL_STALE`, `PROPOSAL_CHANGED`, `DIGEST_MISMATCH`.

## Preuves : deux familles distinctes

**Tests de logique** (Node, transport scripté, sans navigateur) :
`tests/conversation.test.js`, **10 tests**, dont la reprise (lecture seule,
tours sans réponse marqués `pending`, proposition restaurée, validation non
supposée).

**Essais Chromium réels** : `tests/conversation-ui.test.js`, **7 tests**, avec
le serveur réel lancé avec `--conversations simulated`. L'interception réseau ne
sert qu'à injecter ce qu'on ne peut pas produire à la demande : une réponse
tardive, un reçu incertain, des sources longues.

| Essai | Résultat |
| --- | --- |
| Clavier seul : ouverture, envoi, focus revenu sur le message ; indicateur de focus ≥ 2 px sur les 5 contrôles ; fermeture → focus sur la clé, badge « Consultation seule » | PASS |
| 320×640 : 5 sources de 300 caractères et un texte de 400 caractères sans espace | 0 px de débordement, clé absente du DOM |
| Zoom 200 % (640×360, facteur 2) : même contenu | 0 px de débordement |
| Réponse arrivée **après** la fermeture | ignorée : journal vide, conversation fermée |
| Mission incertaine (`MISSION_CREATION_UNCERTAIN`) | « Création incertaine… », pas de bouton de suivi, **1 seule** soumission |
| Rechargement puis reprise | 2 échanges et la proposition reviennent, focus sur le message, **0** requête d'écriture |
| Brouillon Image (C-047) | conservé après ouverture et fermeture d'une conversation |

Captures : [sources à 320 px](captures/g092-sources-320.png),
[zoom 200 %](captures/g092-sources-640.png),
[reprise](captures/g092-reprise-1280.png).

Suites :

- client **98/98** dans Chromium réel ;
- Python **1 214 OK** (6 ignorés), dont `recent` (cloisonnement, ordre, borne,
  jeton de lecture refusé).

## Limites

- Chaque ouverture crée une conversation vide. `recent` ne liste que les
  conversations non vides, mais les vides s'accumulent. L'effacement est à
  prévoir avec l'export (G093).
- Les références de sources sont affichées en entier, donc longues sur
  mobile. Elles ne sont jamais tronquées.
- Lecteur d'écran réel non testé : seuls la structure et les rôles ARIA sont
  vérifiés.
- WebView Windows non vue.
