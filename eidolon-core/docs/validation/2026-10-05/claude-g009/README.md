# Preuves C-TASK-G009 — prototype bureau autonome

Auteur : Claude, 06/10/2026. Prototype : [`desktop/prototype/`](../../../../desktop/prototype/README.md).
Base : `e25cd2a` (contient `534099d` et les correctifs G008 de Codex).
Les maquettes d'origine (`docs/proposals/2026-10-05-claude-desktop-ui/`) sont intactes.
`src/`, `tests/` Core, runtime, store et approvals ne sont pas modifiés.

## Commande et environnement

```sh
cd eidolon-core
CAPTURES=$PWD/docs/validation/2026-10-05/claude-g009/captures \
NODE_PATH=/opt/node22/lib/node_modules node --test --test-reporter=spec "desktop/prototype/tests/*.test.js"
```

Node 22.22.0, Playwright 1.56.1, Chromium sans interface, Linux.
[Sortie complète](tests-output.txt) : **27 tests, 27 réussis**.

## Ce qui est mesuré (rendu réel dans Chromium)

| Vérification | Méthode | Résultat |
| --- | --- | --- |
| Aucune requête hors fichiers locaux, aucune erreur | Écoute des requêtes et des erreurs de page, 3 scénarios | 0 requête externe, 0 erreur |
| Clavier seul | Tab jusqu'à « Autoriser », Entrée, puis parcours complet | Atteint ; « envoi en cours », puis enregistré ≠ exécuté |
| Cibles ≥ 44 × 44 px | Boîtes de tous les boutons, listes, zones de texte et cases étiquetées visibles | 0 contrôle trop petit, 35 vues (7 scénarios × compacte + 4 onglets) |
| Contraste du texte (WCAG AA) | Couleur calculée de chaque texte visible contre le premier fond opaque | Pire cas 4,70:1 pour 4,5 requis |
| Défilement horizontal | `scrollWidth` à 1360 px (35 vues) et à 680 px (équivalent zoom 200 %, 4 vues) | Aucun |
| Animations réduites | `prefers-reduced-motion: reduce` émulé | Animation de l'œil `none` (sinon `eid-breathe`) |
| Parcours | Hors ligne, accusé perdu, session verrouillée, micro hors ligne, lecture assistée | Conformes (voir les tests UI) |

Transitions sans rendu (17 tests du modèle) : un seul envoi par décision ;
accord ≠ exécution ≠ résultat ; un refus ne lance rien ; hors ligne, rien n'est
envoyé ni mis en file plus tard ; un accusé perdu impose de consulter le reçu
(un événement de mission partagé ne vaut pas reçu du client) ; un doublon de
rejeu est ignoré ; un trou de séquence demande un nouvel état complet ; un accord
consommé ne se révoque pas ; révocation et annulation sont des demandes
distinctes, sans effet local avant la réponse du serveur ; une revue requise
n'est jamais relancée ; une décision sur une proposition changée est rapportée
« non enregistrée » ; fermer, le silence ou une notification ne décident rien ;
la lecture assistée envoie exactement le texte relu ; les fonctions ne
modifient pas l'état reçu.

## Captures

| Fichier | Scénario |
| --- | --- |
| [01](captures/01-resultat-verifie.png) | Effet vérifié, preuves datées |
| [02](captures/02-hors-ligne-decision-bloquee.png) | Hors ligne, décision désactivée et raison affichée |
| [03](captures/03-accuse-perdu.png) | Accusé perdu : « enregistrement à vérifier » |
| [04](captures/04-session-verrouillee.png) | Notification générique, fenêtre non ouverte |
| [05](captures/05-micro-hors-ligne.png) | Indicateur micro visible malgré la coupure |
| [06](captures/06-zoom-200-parametres.png) | 680 px de large, Paramètres |
| [07](captures/07-lecture-assistee.png) | Aperçu exact avant envoi |

## Défaut trouvé et corrigé pendant le lot

Un premier passage a donné 26 réussis sur 27. Après avoir coché la case de
relecture, le dialogue était redessiné et le curseur de la zone de texte
revenait au début : la suite tapée s'insérait devant le texte. Corrigé, le
curseur est remis en fin de texte, et le test tape explicitement en fin.

## Non vérifié

Windows, Edge/WebView2, mise à l'échelle Windows, lecteur d'écran réel (NVDA,
Narrateur), vraie zone de notification, vraies notifications, démarrage
automatique, verrouillage réel de session, secrets du système. Le contraste des
états de survol et du texte d'invite des champs vides n'est pas mesuré. Les
captures sont prises sous Linux et ne valent pas rendu Windows.
