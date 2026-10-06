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
| `sync-state.js` | Consommateur pur du protocole `eidolon-client-sync/1` (C-TASK-G012) : aucune requête, aucune commande |
| `sync-view.js` | Scénarios de synchronisation du banc et leur rendu (texte posé par `textContent`) |
| `mission-list-state.js` | Consommateur pur du protocole `eidolon-mission-list/1` (C-TASK-G018) : pages d'une seule génération, reset, sélection |
| `list-view.js` | Scénarios d'inventaire du banc et leur rendu (texte posé par `textContent`) |
| `fixtures/build-list-fixtures.js` | Génère `mission-list-fixtures.js` : trace Core C-008e inchangée (« observé ») et cas dérivés étiquetés |
| `fixtures/build-sync-fixtures.js` | Génère `client-sync-fixtures.js` depuis la trace réelle de Codex, inchangée, plus des cas dérivés étiquetés |
| `tests/model.test.js` | 17 tests de transitions et d'absence d'envoi indu |
| `tests/commands.test.js` | 12 tests du suivi des commandes par clé (G013) et de l'œil « Reçu à vérifier » (G012) |
| `tests/sync.test.js` | 13 tests du consommateur sur la trace réelle et les cas dérivés |
| `tests/list.test.js` | 13 tests du consommateur mission-list/1 (G018) |
| `tests/g021.test.js` | 6 tests de régression G021 (total annoncé, nombre reçu, `has_more`) ; ils échouent sur `bfa75d2` |
| `tests/ui.test.js` | 24 tests dans Chromium : réseau, clavier, parcours, cibles, contraste, zoom, animations, lecture assistée, G013, synchronisation, G016, inventaire G018 |
| `tests/g016.test.js` | 7 tests de régression des écarts G012-01/02/03 (C-TASK-G016) ; ils échouent sur `cc9a64b` |

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

## Synchronisation client-sync/1 (C-TASK-G012)

Le banc propose un second groupe de scénarios, « Synchronisation client-sync/1 ».
Le bouton « Réponse suivante » livre des enveloppes enregistrées : la trace
réelle de Codex (C-008a, `docs/validation/2026-10-06/codex-client-sync/demo.json`,
recopiée sans changement) et des cas **dérivés**, chacun étiqueté avec ce qui a
été modifié. Aucun n'est présenté comme une sortie réellement observée.

`sync-state.js` garde séparément :

- **la vue** : la dernière capture de mission, ordonnée par `as_of_sequence`.
  Une capture plus ancienne ou égale ne la remplace jamais ;
- **le curseur** : la dernière référence d'événement reçue, qui peut être en
  retard sur la vue (« rattrapage en cours ») ;
- **les références d'événements** : de l'historique, jamais des changements
  appliqués à la vue. Elles sont dédupliquées par séquence ;
- **la connectivité locale**, et l'**époque** des requêtes : un rechargement
  explicite rend périmées les réponses à des requêtes plus anciennes.

Règles :

- Une page dont le premier événement ne suit pas le curseur (contrôle par
  `event_count`, pas par +1 sur les séquences) ne fait ni avancer le curseur ni
  ajouter de références. Sa capture reste prise si elle est plus récente.
- `RESET_REQUIRED` n'est jamais appliqué seul : la vue reste l'ancienne,
  l'interrogation s'arrête, et la raison est expliquée. Seul « Recharger
  explicitement la vue » la remplace. Cela ne relance rien et ne décide rien.
- **Gel pendant un reset en attente** (G016) : toute réponse SNAPSHOT ou DELTA
  qui arrive ensuite, même de la même époque, est ignorée et comptée
  (`frozenAnswers`) ; ni la vue, ni le curseur, ni les références ne bougent,
  et aucune requête n'est émise. Un second `RESET_REQUIRED` remplace le premier
  (`supersededResets`) : l'acceptation applique le plus récent. Après
  acceptation, les réponses de l'ancienne époque restent ignorées.
- `objective_kind` vaut une chaîne bornée (80) ou `null` : Core renvoie `null`
  pour un objectif hors catalogue. L'interface affiche « Aucun objectif reconnu
  (hors catalogue) » et n'invente rien.
- Rejetés sans effet : version de protocole inconnue, prétention d'autorité,
  curseur d'une autre mission ou d'une autre base sans `RESET`, entier hors de
  `Number.isSafeInteger`, enveloppe mal formée. Une erreur signalée par Core est
  listée ; aucune capture n'en est déduite.
- Hors ligne : rien n'est appliqué ni demandé. Au retour, seule une lecture est
  demandée, jamais une file d'actions.
- `action_view` peut valoir `null`. Sinon, décision, applicabilité et effet
  restent trois lignes distinctes, et aucun bouton d'accord n'est rendu.
- Annulation demandée : « Annulation demandée — issue non confirmée » tant que
  la capture ne dit pas `CANCELLED`, même à révision inchangée.
- **`REVIEW_REQUIRED` reste l'état principal** (G016), même avec
  `cancel_requested=true` : « Revue requise — effet à vérifier ». La demande
  d'annulation est montrée sur une ligne à part (« Annulation demandée :
  enregistrée, issue non garantie »), l'effet inconnu et les preuves restent
  affichés, aucun texte n'annonce une capture `CANCELLED` à venir et aucun
  bouton n'est rendu.

Scénarios du banc ajoutés par G016 : `sync-objectif-null` (capture Core
**observée**, recopiée telle quelle avec son empreinte) et
`sync-revue-annulation` (cas **dérivé** `review_with_cancel`). Le scénario
`sync-reset` livre en plus une réponse tardive pendant l'attente, puis un
second reset.
- **Rétention** : 200 références au plus (les plus anciennes partent d'abord,
  et sont comptées), 20 rejets et 20 erreurs Core au plus.

Le passage du prototype G009 (événements internes comme `MISSION_RUNNING`) au
protocole réel n'est pas fait dans la fenêtre principale. Les deux mondes
coexistent dans le banc, sans inventer d'événements G009 à partir de
client-sync/1.

## Œil : « Reçu à vérifier »

Quand une demande reste incertaine (`unknown` ou `not-found`), l'œil passe en
attention avec ce libellé. Priorité : injoignable > écoute (capture locale) >
silence > reçu à vérifier > décision ou revue en attente > au travail > veille.
Cela change l'attention visuelle seulement : aucun état métier, aucun son,
aucun renvoi. Silence et fermeture de fenêtre gardent leurs règles.

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

## Inventaire mission-list/1 (C-TASK-G018)

Troisième groupe du banc : « Inventaire mission-list/1 ». Chaque ligne et chaque
capture porte sa provenance : **observé** (trace Core C-008e de Codex, recopiée
avec son SHA-256) ou **dérivé : nom du cas** (construit et étiqueté). Le badge
de la carte client-sync dit maintenant la même chose, au lieu de « TRACE C-008a ».

Règles de `mission-list-state.js` :

- **Une génération** : les pages assemblées ont le même `store_id` et la même
  `generation`. Une page d'une autre génération est refusée (`GENERATION_MIXED`),
  jamais fusionnée.
- **Pagination** : seule la réponse à la requête attendue (curseur renvoyé tel
  quel) est prise. Page répétée ou tardive : comptée, sans effet. Hors ligne :
  ignorée ; au retour, la même page est redemandée avec le même curseur.
- **Reset** : `RESET_REQUIRED` garde l'ancien inventaire, marqué **périmé**, et
  arrête les requêtes. Seul « Relire la liste » commence une nouvelle lecture
  (nouvelle époque) ; l'ancien inventaire reste affiché comme périmé jusqu'à la
  fin de la nouvelle lecture.
- **Total annoncé** (G021) : `generation.mission_count` lie toute la lecture.
  Avant de prendre une page, le client vérifie le nombre cumulé reçu : plus que
  le total (`COUNT_EXCEEDED`), fin avant le total (`LIST_ENDED_EARLY`) ou
  `has_more=true` alors que tout est reçu (`HAS_MORE_INCONSISTENT`) sont
  refusés. La page n'est pas prise, la lecture s'arrête (« Liste incomplète »),
  rien n'est déclaré complet ni inventé ; seule « Relire la liste » repart.
  Ce contrôle relève du protocole ; le plafond de 200 n'est qu'une borne
  d'affichage.
- **Plafond visible** : 200 missions. Au-delà, « Liste tronquée : 200 affichées
  sur N annoncées », jamais « entièrement lue ».
- **Sélection** : « Voir la mission » demande seulement une capture client-sync/1
  de cet identifiant (`sync-state.js`). Le `next_cursor` de la liste n'est
  jamais un curseur d'événements. Une réponse pour une sélection antérieure
  est ignorée et comptée ; une capture d'un autre `store_id` est refusée.
- Aucun bouton d'exécution : les seuls boutons lisent (« Voir la mission »,
  « Relire la liste »).

Les traces Core ne contiennent aucune capture client-sync pour les missions de
la liste : les captures de sélection sont **dérivées** des projections de la
liste, et étiquetées comme telles.
