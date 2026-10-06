# Première bêta serveur–PC : périmètre et étapes

Codex/GPT, 06/10/2026. Objectif demandé par toytoy : pouvoir essayer Eidolon
sur son serveur et son PC le week-end du 10–11 octobre. C'est une cible de
travail, pas une qualification ni une livraison promise à date certaine.

## Parcours minimal visé

1. Core sur Linux, avec un dossier d'état de test distinct.
2. Une mission synthétique créée/exécutée par la CLI du serveur.
3. Un client dans le navigateur du PC, connecté par tunnel SSH, affiche les
   vraies missions, leur progression et leur dernier état connu.
4. Une coupure du tunnel ne change aucune mission. Au retour : reconnexion,
   inventaire neuf et rattrapage sans état mélangé ni nouvelle exécution.

Ce premier jalon est un **observateur connecté**, pas encore le chatbot
généraliste, l'application Windows installable ou une autorisation d'actions.
La consultation HTTP des reçus locaux est livrée (C-009b), son affichage attend
G036. Une deuxième tranche ajoutera l’envoi de commandes authentifiées,
puis le modèle réel et le rappel mémoire revalidé. L'accès externe Web,
NAS/fichiers Windows, voix/caméra et robot restent des recettes séparées.

## Répartition active

- Codex : API HTTP de consultation, token local, lecture SQLite sans création
  ni migration, tests réels sur boucle locale, documentation de lancement.
- Claude G031 : client connecté indépendant du prototype simulé, selon
  [HTTP-READ-API.md](HTTP-READ-API.md).
- Claude G032/G033 : robustesse HTML et corrections du parseur APT.
- Claude G034 : contre-revue de l'API sur le commit livré par Codex.
- Claude G035 : recette serveur/PC et préparation Windows, sans installation.

## Conditions avant de parler de bêta utilisable

- [ ] API et client intégrés, tests HTTP et UI de bout en bout réussis.
- [ ] Parcours authentification, panne et reconnexion testé avec le vrai client.
- [ ] Procédure testée sur Debian et Windows, états synthétiques uniquement.
- [ ] Installation/démarrage/arrêt/retrait documentés sans exécuter Bootstrap.
- [ ] Limites visibles : lecture seule, modèle simulé, aucune action distante.

Les scripts Bootstrap restent hors du parcours sur serveur déjà installé.
Le correctif APT reçu avec C040 a deux écarts reproduits : ajouts après un
commentaire `#` (donc inactifs), et modification d'une source tierce contenant
`main`. G033 les traite avant toute qualification d'installation Debian.

## État intégré au 06/10, lot G049

API C-009b et client G031 réunis ; 87 tests Python ciblés réussis pour les reçus
et commandes/API, puis 18 tests Node reproduits dont quatre avec serveur réel.
Les deux essais Chromium sont rapportés réussis par Claude sur sa livraison,
mais sautés ici faute d’exécutable. Aucun test serveur/PC utilisateur ou tunnel
SSH réel effectué ; les conditions ci-dessus restent à valider avant qualification.
