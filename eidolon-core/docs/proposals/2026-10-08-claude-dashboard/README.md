# Étude G076 — Dashboard inspiré de Jarvis et thème Eidolon

Auteur : Claude. Date : 08/10/2026, Europe/Paris. Statut : **ÉTUDE — choix toytoy ouvert**.
Base : branche Core au commit de livraison (G075 inclus). Fiche : C-TASK-G076.
Complète [les propositions Codex](../2026-10-08-dashboard-context.md) (P9–P12) sans les remplacer.

Cette étude ne remplace ni `desktop/connected`, ni Tauri, ni le prototype. La
maquette est isolée, avec des **données simulées**, et ne déclare aucune
fonctionnalité.

- [mockup.html](mockup.html) : fichier autonome, sans réseau. Les deux
  compositions et trois états se choisissent par l'ancre `#a-connected`,
  `#b-stale`, etc.
- [shoot.js](shoot.js) : captures, ordre du clavier, contraste, débordement.
- [checks.json](checks.json) : résultats de ces contrôles.

## Identité visuelle conservée

- Le **E bleu** sur carré arrondi bleu nuit, en SVG dans la maquette. Il est à
  remplacer par l'icône Windows définitive, que le dépôt ne contient pas encore :
  `desktop/tauri/icons/icon.png` n'est qu'un disque provisoire.
- Fond très sombre, halos bleus en dégradé (inspiration du wallpaper, que je n'ai
  pas vu) et panneaux translucides.
- Mention « Eidolon Core Technologies (ECT) ».
- Une **présence** (orbe bleue) réduite : elle pulse seulement quand la connexion
  est fraîche, devient grise et immobile si la capture est périmée, et
  s'immobilise avec `prefers-reduced-motion`.

## Les deux compositions à 1366×768

| | A · Conversation au centre | B · Missions au centre |
| --- | --- | --- |
| Capture | [connecté](captures/a-connected-1366x768.png), [hors connexion](captures/a-offline-1366x768.png), [sources](captures/a-connected-1366x768-sources.png) | [connecté](captures/b-connected-1366x768.png), [capture figée + sources](captures/b-stale-1366x768-sources.png), [1920×1080 mouvement réduit](captures/b-connected-1920x1080-reduced.png) |
| Ce qui se voit sans faire défiler | conversation, 3 compteurs d'attention, 4 missions compactes (libellé + état) | 3 compteurs, 4 missions complètes (progression, type, date de capture), état, archives |
| Ce qui manque | progression, date de capture et archives, repliées dans « État, archives et outils » | la conversation : 2 lignes visibles à 768 px de haut |
| Constat | une mission bloquée reste visible pendant la conversation grâce aux compteurs | la supervision est claire, mais le panneau de conversation empilé est trop petit à 768 px |

Premier essai mesuré : la première version de A n'affichait **qu'une mission et
demie** dans la colonne de droite (état et missions empilés). Il a fallu replier
l'état pour qu'A reste honnête. À 1366×768, la colonne latérale ne peut porter
**qu'un** bloc riche sur trois : état, missions ou conversation.

## États représentés

| État | Traitement |
| --- | --- |
| Connecté, frais | point vert, orbe animée, envoi possible (futur) |
| Hors connexion | bandeau « dernier état reçu (heure), périmé », cartes sur fond « périmé », orbe grise, saisie désactivée avec la raison |
| Capture figée (reset) | bandeau `STATE_CHANGED` + « recharger explicitement », même traitement, saisie « recharger avant d'écrire » |
| Mission bloquée / décision attendue | badge « Décision attendue » et compteur. La conversation **montre la preuve** mais ne porte pas l'accord |
| Effet inconnu | badge « Effet à vérifier » rouge. Le texte dit « je ne relance rien » ; pas de bouton Réessayer |
| Données absentes | « — » plus l'étiquette « futur » (GPU), jamais 0 ni une jauge décorative |
| Archives | liste et rappel « cohérence vérifiée ; authenticité non établie » (repris de G066) |

Aucune mission n'est animée : une capture n'est pas un processus vivant (règle
P9 de Codex, appliquée).

## Chaque indicateur relié à sa source

Le bouton « Sources des données » affiche une étiquette sur chaque indicateur :
**vert = API actuelle**, **ambre = futur/simulé**.

| Indicateur | Source | État |
| --- | --- | --- |
| Connexion, base | `GET /v1/health` (`store_id`) | API |
| Libellé, statut/phase, progression, type | `eidolon-mission-list/1`, `client-sync` (`status`, `phase`, `progress`, `objective_kind`) | API |
| « Capture reçue à », périmée | `receivedAt` local du client (G043) | API (client) |
| Décisions attendues | `action_view.decision` | API |
| Effets à vérifier / résultats vérifiés | `status` `REVIEW_REQUIRED` / `SUCCEEDED` | API |
| Archives | `POST /v1/research-archives` (C-030) | API |
| Sources mémoire | références de la capture (pas le texte) | API (partiel) |
| Conversation | aucune API de chat | **futur** |
| Outils disponibles | registre Python, pas d'API catalogue (C-BRAIN-G012) | **futur** |
| GPU, VRAM | aucune télémétrie | **futur** |
| Orbe de présence | dérivée de la fraîcheur de connexion | API (dérivée) |

## Clavier, contraste, mouvement

- **Ordre du clavier**, vérifié par `shoot.js` : choix de composition → Sources →
  missions (une carte = un arrêt, avec `aria-label` libellé + état) →
  conversation. Le focus est jaune (`#ffd866`, 13,6:1 sur le fond).
- **Contraste** (WCAG AA ≥ 4,5:1 pour le texte normal) :
  - texte 13,8 ;
  - secondaire 8,2 ;
  - accent 6,4 ;
  - alerte sur fond « périmé » 7,6 ;
  - OK 8,7 ;
  - bouton primaire **5,9**. Il était à 4,0 dans la première version, ce qui
    échouait ; le bleu a été assombri.
- **Mouvement** : l'orbe ne pulse qu'avec une connexion fraîche et jamais avec
  `prefers-reduced-motion` (contrôlé). Pas d'autre animation.
- **Débordement horizontal** : 0 px sur les 6 captures. **Requêtes externes** : 0.

## Analyse et proposition

1. **Pour la bêta de consultation, je rejoins Codex : B au premier plan.** Le chat
   n'existe pas encore, et une conversation simulée au centre ferait croire à
   une fonction absente.
2. **Ce que je propose de challenger** : plutôt que deux vues séparées, une seule
   page avec une **bande d'attention permanente** (les 3 compteurs, plus la
   fraîcheur) et un **centre commutable** Conversation ↔ Missions (`Ctrl+1` /
   `Ctrl+2`).
   - Raison mesurée : à 1366×768, la colonne latérale ne tient qu'un bloc riche.
     Empiler la conversation sous l'état (B) ou l'état sous les missions (A
     première version) la rend illisible.
   - L'état et les archives deviennent un tiroir repliable, ouvert d'office
     quand la connexion est perdue.
3. **Règle d'interface** : la conversation peut **citer** une mission et ouvrir sa
   preuve. Elle ne porte jamais un accord ni une reprise : l'accord reste dans la
   fiche de la mission. C'est la séparation conversation / mission / effet de C-D01.

Compromis :

- le centre commutable demande un geste de plus pour passer du chat à la
  supervision ;
- la bande d'attention prend environ 90 px de hauteur ;
- l'orbe est une présence d'agrément ; elle peut être masquée dans les réglages.

## Essai utilisateur proposé (toytoy, données synthétiques)

Même jeu de 4 missions, chaque tâche faite dans A, B et la variante
« centre commutable », dans un ordre tiré au sort :

1. Dire en moins de 10 s s'il y a quelque chose à faire, et quoi.
2. Depuis une conversation de 30 échanges, ouvrir la preuve de la mission
   « Effet à vérifier ».
3. Couper le serveur : dire si ce qui est affiché est actuel.
4. Trouver la date de la dernière archive.
5. Retrouver la même information au clavier seul.

Mesures : temps, erreurs (surtout « croire actuel ce qui est périmé »), nombre
d'actions, préférence déclarée. Les seuils sont à fixer avant l'essai par toytoy.

## Limites

- Maquette statique en Chromium Linux. Rien ne prouve le rendu de la WebView
  Windows (Tauri) ni l'échelle d'affichage à 125 %/150 %, fréquente sur un
  portable 1366×768.
- Le wallpaper et l'icône définitive ne sont pas dans le dépôt : les couleurs
  sont une interprétation de « sombre / bleu ».
- Aucune donnée réelle, aucune fonctionnalité ajoutée au client.
