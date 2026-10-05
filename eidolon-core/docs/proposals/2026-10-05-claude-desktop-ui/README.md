# Proposition d'interface — client Eidolon sur Windows 11

Auteur : Claude, 05/10/2026. Statut : **proposition de maquettes**, rien n'est
décidé, aucun framework Desktop choisi (cadrage §7 : « sans choisir
prématurément un framework Desktop »). Aucun code de runtime touché.

Demande de toytoy : « tu peux te pencher sur l'interface de l'appli qui serait
déployée sur mon PC principal Windows 11 ? ». Consignes reçues de lui pendant le
travail, appliquées ici :

- l'application s'appelle seulement **« Eidolon »** : c'est l'interface qui
  représente son système Eidolon ;
- s'inspirer de **vraies interfaces graphiques**, pas de la sortie console des
  scripts Bootstrap ;
- une **présence** d'Eidolon : un œil robot/caméra dans un coin, qui varie selon
  l'activité du système ;
- des **endroits pour afficher les agents déployés** et les appareils.

Les maquettes vivent sur un canevas de design privé de toytoy. Les sources sont
copiées dans [`maquettes/`](maquettes/) pour relecture : ce sont des fichiers de
maquette (`.dc.html`) qui ne s'ouvrent pas seuls dans un navigateur, car ils
attendent le moteur du canevas (`support.js` absent).

## Écrans

| Fichier | Écran | Points du cadrage couverts |
| --- | --- | --- |
| `Main.dc.html` | Conversation : accueil contextuel, carte d'accord, réponse sourcée, micro, œil de présence | §7 accueil type ; C-005a (approbation simulée affichée comme telle) ; hors-ligne et rattrapage |
| `Missions.dc.html` | Liste par état, détail : objectif, demande d'accord, preuves, déroulé | états Core (`AWAITING_DECISION`, `RUNNING`, `REVIEW_REQUIRED`, `SUCCEEDED`, `BLOCKED`) traduits en libellés humains |
| `Systeme.dc.html` | Agents (Eidolon, Exécuteur, Recherche web, Mémoire, Vision) et appareils (serveur, ce PC, WALL-E, NAS), panneau de détail | §9 : connexion, dernier contact, capacités autorisées, télémétrie avec fraîcheur, contexte, travail ; un appareil hors ligne n'est jamais présenté comme prêt ; §10 sécurité robot locale |
| `Lecture.dc.html` | Lecture assistée d'une page bloquée | piste G010 ; provenance « fournie par toi » ; pas de contournement ; minimisation avant envoi |
| `Settings.dc.html` | Connexion par VPN, démarrage, notifications, silence, dossiers autorisés, micro, webcam | C-D06 (connecteur fichiers, rien par défaut) ; C-D08 (VPN) ; §7 démarrage automatique et silence |
| `Tray.dc.html` | Menu de la zone de notification | §7 menu rapide : voix, missions, état, silence, paramètres ; quitter ne coupe pas les missions |
| `Toasts.dc.html` | Notifications Windows | §11 ; pas d'accord donné depuis une notification |
| `Presence.dc.html` | Les six états de l'œil | veille, écoute, travail, attente d'accord, silence, injoignable |

## Choix proposés (à discuter)

1. **Aucun accord depuis une notification** : seulement « Ouvrir pour décider »,
   pour éviter un clic distrait sur une action réelle.
2. **Le silence n'accepte rien** : les demandes attendent dans Missions.
3. **L'œil reflète un état réel**, jamais une animation décorative. Priorité :
   injoignable > écoute > attente d'accord > travail > veille. Animations
   coupées si Windows demande de réduire les animations.
4. **Les états Core restent la source** ; l'interface les traduit en libellés
   courts, sans fusionner deux états distincts.
5. **Aucune adresse réseau** dans l'interface ni dans ces fichiers : l'adresse du
   serveur est un emplacement `[ADRESSE DU SERVEUR DANS LE VPN]`.

## Ce que l'interface demande au contrat client distant

Ces besoins sont des hypothèses à confronter au contrat, pas des exigences :

- un **flux d'événements** avec curseur de reprise, pour le rattrapage après
  coupure (« 3 événements rattrapés ») ;
- un **état de présence agrégé** calculé par Core (l'œil ne doit pas déduire
  l'état lui-même) ;
- par agent et par endpoint : état, `last_seen`, capacités autorisées,
  télémétrie avec horodatage d'origine, mission liée ;
- une **décision d'accord** liée à une demande précise, idempotente,
  enregistrée avec l'appareil d'origine ;
- un **appairage par appareil**, révocable, distinct de l'identité de toytoy.

## Limites

Valeurs d'exemple (batterie 64 %, 33 °C, nombre de workers, heures) : illustratives,
pas des mesures. Seule la carte graphique RTX 2060 12 Go vient d'une capture
d'installation fournie par toytoy. Les agents listés sont ceux existants ou
prévus dans Core ; Mémoire et Vision sont présentés désactivés ou prévus.
Contraste et cibles de 44 px visés, non mesurés par un outil.
