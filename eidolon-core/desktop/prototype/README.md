# Prototype bureau Eidolon (C-TASK-G009)

Auteur : Claude, 06/10/2026. Statut : **prototype autonome de démonstration**.
Ce n'est pas le client Windows : aucun framework n'est choisi (C-TASK-G010),
aucun serveur n'est contacté, aucune capacité du système n'est utilisée.

## Lancer

Ouvrir `index.html` dans un navigateur récent, directement depuis le disque
(`file://`). Aucun serveur, aucune installation, aucune ressource distante.
La page porte une politique de sécurité qui interdit toute connexion
(`connect-src 'none'`) et n'autorise que ses propres fichiers.

Un scénario peut être choisi dans l'adresse : `index.html#accuse-perdu`.

## Ce qu'on voit

- **Banc de simulation** (en haut, bordure pointillée) : il ne fait pas partie
  de l'application. Il choisit le scénario, avance le serveur simulé d'une
  étape (l'étape suivante est décrite en clair), coupe ou rétablit la
  connexion, active le micro simulé et verrouille la session.
- **Fenêtre Eidolon** : vue compacte (conversation) ou vue étendue
  (Conversation, Missions, Système, Paramètres). Les deux vues lisent le même
  état. L'œil de présence et ses indicateurs sont dans l'en-tête.
- **Intégration Windows simulée** (à droite) : menu de la zone de notification
  et notifications, dessinés dans la page, **non qualifiés sous Windows**.

## Scénarios (déterministes)

| Clé | Parcours |
| --- | --- |
| `accord-succes` | Accord → envoi → accusé « enregistré » → exécution simulée → effet vérifié et preuves datées |
| `refus` | Refus enregistré ; aucune exécution, l'œil ne passe jamais « Au travail » |
| `accuse-perdu` | L'accord part, la connexion tombe avant l'accusé : décision inconnue ; au retour, rejeu avec doublon ignoré, puis consultation du reçu ; aucune nouvelle émission |
| `revue-requise` | Tentative commencée, effet inconnu : aucune relance proposée |
| `hors-ligne` | Serveur injoignable : dernier état connu daté, configuré ≠ disponible |
| `session-verrouillee` | Notification générique ; elle ouvre la décision seulement après déverrouillage |
| `micro-hors-ligne` | Micro simulé actif et serveur injoignable : l'indicateur micro reste visible |

Toutes les heures sont **synthétiques** et marquées comme telles ; aucune
télémétrie n'est présentée comme une observation en direct.

## Règles tenues (UI-01 à UI-10 de la revue Codex)

| ID | Comportement du prototype |
| --- | --- |
| UI-01 | L'œil passe « Au travail » seulement quand le serveur rapporte `RUNNING` ; un accord enregistré ou un refus n'y suffisent pas |
| UI-02 | Hors ligne, les boutons d'envoi sont désactivés avec la raison affichée ; un clic donne « envoi en cours » ; un accusé perdu donne « enregistrement à vérifier », sans renvoi automatique |
| UI-03 | « Révoquer l'accord », « Demander l'annulation de la mission » et « Fermer » sont trois opérations distinctes ; un accord consommé ne se révoque pas ; aucun retour arrière local |
| UI-04 | Bandeau : « Cette déconnexion n'annule pas les missions ; leur état actuel est inconnu », avec la date du dernier état connu |
| UI-05 | L'œil combine l'état du serveur et l'état local ; les indicateurs (connexion, micro, caméra, silence, session) restent visibles quel que soit l'œil |
| UI-06 | Système sépare Agents, Services et capacités, Appareils, avec nature, déploiement, capacités configurées et disponibilité |
| UI-07 | Preuves : libellé, origine, date, empreinte calculée par le serveur, et rappel qu'une empreinte ne prouve pas la vérité |
| UI-08 | Lecture assistée : aperçu exact de ce qui part, aucune promesse d'anonymisation, case de relecture remise à zéro à chaque modification |
| UI-09 | Paramètres : réseau local selon configuration, VPN pour l'extérieur (C-D08) ; identité du serveur et appairage indiqués comme non implémentés |
| UI-10 | Aucune ressource distante ; cibles, contraste, zoom, clavier et animations réduites testés (ci-dessous) |

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `model.js` | États et transitions, purs et déterministes. `state.client` (ce que sait la fenêtre) et `state.sim` (serveur simulé) sont séparés : la fenêtre ne change sa vue d'une mission qu'en appliquant des événements numérotés |
| `app.js` | Rendu et interactions ; uniquement des contrôles natifs (`button`, `select`, `input`, `textarea`) |
| `styles.css` | Thème sombre, polices système, cibles de 44 px, animations coupées si le système le demande |
| `tests/model.test.js` | 17 tests de transitions et d'absence d'envoi indu |
| `tests/commands.test.js` | 11 tests du suivi des commandes par clé (C-TASK-G013) |
| `tests/ui.test.js` | 11 tests dans Chromium : réseau, clavier, parcours, cibles, contraste, zoom, animations, lecture assistée, G013 |

## Suivi des commandes (C-TASK-G013)

Chaque demande envoyée (accord, refus, révocation, demande d'annulation) a sa
propre entrée dans `client.commands`, identifiée par sa clé. Une nouvelle
demande n'efface jamais l'incertitude d'une précédente.

| Phase | Sens | Résolue ? |
| --- | --- | --- |
| `sending` | envoyée, pas encore d'accusé | non |
| `unknown` | accusé perdu (coupure) : enregistrement à vérifier | non |
| `checking` | consultation du reçu en cours | non |
| `not-found` | reçu introuvable : **pas** la preuve que rien n'a eu lieu | non |
| `acknowledged` | accusé ou reçu trouvé pour cette clé | oui |
| `refused` | le serveur a répondu non à cette requête (proposition changée) | oui |

- Une réponse (accusé ou reçu) ne touche que la commande de même clé. Une
  réponse pour une clé inconnue ou déjà purgée est comptée (`strayReplies`) ;
  un doublon ou une réponse tardive sur une commande résolue est compté
  (`duplicateReplies`). Dans les deux cas, rien ne change et rien n'est émis.
- Un événement de mission partagé ne vaut jamais réponse à une commande.
- Aucun nouvel accord ni refus tant qu'une décision précédente n'est pas
  résolue, même si la mission affiche déjà « accord enregistré ». Une
  révocation ou une demande d'annulation reste possible : elle est suivie à part.
  Un double clic n'envoie qu'une révocation et qu'une annulation.
- Une coupure fait passer `sending` et `checking` à `unknown`, jamais à un renvoi.
- **Rétention** : les commandes non résolues ne sont jamais purgées ; on garde
  au plus 10 commandes résolues (les plus anciennes partent d'abord) et 50
  entrées d'historique de décisions. La liste d'envoi (`outbox`) reste
  complète : c'est la trace que vérifient les tests, pas un état d'interface.

Ces règles suivent le contrat de reçus C-008b de Codex (`docs/COMMAND-RECEIPTS.md`) :
un reçu introuvable n'autorise pas à réémettre. Les noms d'états et de messages
restent ceux du prototype, pas ceux du contrat.

## Tests

Depuis `eidolon-core/` :

```sh
node --test "desktop/prototype/tests/*.test.js"
# rendu réel : Playwright doit être résolvable, sinon les tests UI sont sautés
NODE_PATH=/chemin/vers/node_modules node --test "desktop/prototype/tests/*.test.js"
```

Résultats obtenus et ce qui est mesuré : voir
[preuves G009](../../docs/validation/2026-10-05/claude-g009/README.md).

## Limites

- Chromium sous Linux seulement. Ni Windows, ni Edge/WebView2, ni lecteur
  d'écran réel. La zone de notification et les notifications sont dessinées,
  pas réelles.
- Le zoom à 200 % est approché par une fenêtre de 680 px de large, pas par le
  réglage d'échelle de Windows.
- Le contraste est calculé sur les couleurs déclarées. Les états de survol et
  le texte des champs de saisie vides ne sont pas mesurés.
- Le serveur simulé n'est pas le contrat client à venir (réservé à Codex). Les
  noms d'événements sont ceux du prototype, pas une API.
- Aucune réponse de conversation n'est générée : un message envoyé est
  seulement enregistré dans la liste d'envoi.
