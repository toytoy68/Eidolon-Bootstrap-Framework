# C-TASK-G018 — inventaire paginé mission-list/1 dans le prototype

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G018](../../../../collaboration/tasks/C-TASK-G018.md).
Contrat : [MISSION-LIST.md](../../../MISSION-LIST.md), cible `d330615` (C-008e).
Périmètre : `desktop/prototype/` seulement. Ni `src/`, ni `tests/` Python modifiés.
Aucune requête réseau, aucun accès SQLite, aucune commande.

Environnement : Linux, Node 22.22.0, Playwright 1.56.1, Chromium local.
Pas de Windows, de VM ni de framework choisi.

```sh
cd eidolon-core
node desktop/prototype/fixtures/build-list-fixtures.js     # régénère les fixtures
NODE_PATH=<dossier contenant playwright> node --test "desktop/prototype/tests/*.test.js"
# ouvrir desktop/prototype/index.html#liste-pagination (ou un autre scénario « Liste »)
```

**85 tests, 85 réussis** ([sortie](tests-output.txt)) :

- 13 nouveaux tests de logique (`tests/list.test.js`) ;
- 5 nouveaux tests d'interface réellement joués dans Chromium.

Plus faible contraste : 4,70:1, sur les 8 vues de liste comme sur les autres
vues ; aucune cible de moins de 44 px, aucun débordement horizontal.

## Fichiers

| Fichier | SHA-256 | Rôle |
| --- | --- | --- |
| `mission-list-state.js` | `3040e14c…3ae55` | consommateur pur |
| `list-view.js` | `a5b17f9f…9f69` | scénarios du banc et rendu |
| `fixtures/build-list-fixtures.js` | — | générateur |
| `fixtures/mission-list-fixtures.js` | `982b0d63…802b` | fixtures générées |

Fichiers aussi modifiés :

- `sync-state.js` : `validateMission`, partagée par les deux protocoles, qui
  ont la même projection Core ;
- `sync-view.js` : badge de provenance ;
- `app.js`, `index.html`, `styles.css` ;
- le README du prototype.

## Provenance (remarque de Codex sur G016)

- **observé** : la trace C-008e (`codex-mission-list/demo.json`) est recopiée
  **sans changement** ; son SHA-256 (`71cc35c1…41cb`) est vérifié par un test.
- **dérivé : nom** : 9 cas, chacun avec ce qui a été construit ou changé (champ
  `why`) :
  - base vide ;
  - page variée ;
  - 250 missions ;
  - autorité prétendue ;
  - entier 2^53 ;
  - génération mélangée ;
  - texte HTML ;
  - captures de sélection ;
  - autre store.
- Chaque ligne de la liste et la carte de sélection affichent leur provenance.
  La carte client-sync existante affiche maintenant « observé : trace Core
  C-008a » ou « dérivé : … », selon la capture affichée, au lieu de
  « TRACE C-008a ».
- **Captures de sélection** : les traces Core ne contiennent aucune capture
  client-sync des missions listées. Les enveloppes de sélection sont donc
  **dérivées** des projections de la liste (même store, id, statut ; ancre et
  heure construites), et étiquetées ainsi. Ce n'est pas une mesure Core.

## Ce que garantit le consommateur (testé)

| Règle | Test |
| --- | --- |
| Pages d'une seule génération et d'un seul store ; autre génération : `GENERATION_MIXED`, jamais fusionnée | logique + UI rejets |
| Curseur renvoyé tel quel ; ni perte ni doublon sur la trace observée | logique + UI pagination |
| Page répétée ou tardive : sans effet, comptée | logique + UI pagination |
| Hors ligne : page ignorée ; au retour, même curseur redemandé | logique |
| `RESET_REQUIRED` : ancien inventaire gardé et marqué **PÉRIMÉE**, aucune requête, réponse tardive gelée ; « Relire la liste » explicite ; ancienne époque ignorée ensuite | logique + UI reset |
| Plafond : 250 annoncées → « Liste tronquée : 200 affichées sur 250 annoncées », jamais complète | logique + UI |
| Validation : protocole, autorité, entiers sûrs, ordre des id, forme du curseur et du reset ; une enveloppe client-sync n'est pas une page | logique |
| Sélection : seulement un SNAPSHOT client-sync de cet id ; aucun `after_id` dans la requête ; le curseur de liste injecté comme curseur d'événements est rejeté par `sync-state.js` | logique |
| Réponse pour une sélection antérieure : ignorée, la mission affichée reste la dernière choisie | logique + UI sélection en vol |
| Capture d'un autre `store_id` ou d'un autre id : refusée | logique |
| Liste vide, objectif null, revue + annulation, annulation en cours : libellés distincts, effet `UNKNOWN` visible, aucun bouton d'exécution | logique + UI statuts |
| Aucun `fetch`, minuteur ni stockage dans le consommateur | logique |

## Captures

- [15 — pagination et sélection](captures/15-g018-pagination-et-selection.png)
- [16 — reset entre pages](captures/16-g018-reset-entre-pages.png)
- [17 — sélection en vol](captures/17-g018-selection-en-vol.png)
- [18 — statuts variés](captures/18-g018-statuts-varies.png)

Les captures 01 à 14 sont régénérées par la même exécution.

## Limites

- Le **rafraîchissement automatique** n'est pas fait. La liste est lue sur
  demande (pages du banc) ; on ne relit pas à intervalle, et aucune relecture
  automatique ne suit un reset (c'est voulu par le contrat).
- **Activité continue** : si le serveur change à chaque page, la lecture peut
  ne jamais finir (limite C-008e). Le client le montre (« périmée ») mais ne
  propose pas de stratégie.
- **Plafond de 200** : choisi pour la mémoire de rendu, pas mesuré sur un vrai
  poste.
- **Sélection** : une capture unique ; pas de suivi des pages client-sync
  ensuite.
- **Ordre réseau** et incarnation distante restent à traiter avec un vrai
  transport (remarque de Codex sur G016).
- **Hors périmètre** : aucune identité, aucune autorisation ; transport non
  construit.
