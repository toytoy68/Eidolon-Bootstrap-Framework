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
La consultation HTTP des reçus locaux et son affichage G036 sont intégrés. Une deuxième tranche ajoutera l’envoi de commandes authentifiées,
puis le modèle réel et le rappel mémoire revalidé. L'accès externe Web,
NAS/fichiers Windows, voix/caméra et robot restent des recettes séparées.

## Répartition active au 07/10

La [tranche initiale](PLAN-2026-10-07.md) est conservée comme historique.
G042–G054 sont intégrés ; Claude poursuit G055–G057 dans la
[file active](../collaboration/tasks/QUEUE.md). Codex a livré C-019–C-021 :
historique nettoyé, extraction HTML durcie et missions de recherche synthétique.

## Conditions avant de parler de bêta utilisable

- [ ] API et client intégrés, tests HTTP et UI de bout en bout réussis.
- [ ] Parcours authentification, panne et reconnexion testé avec le vrai client.
- [ ] Procédure testée sur Debian et Windows, états synthétiques uniquement.
- [x] Installation/démarrage/arrêt/retrait documentés sans exécuter Bootstrap.
- [x] Limites documentées : lecture seule, modèle simulé, aucune action distante.

Les scripts Bootstrap restent hors du parcours sur serveur déjà installé.
Les deux écarts APT reçus avec C040 (ajouts après commentaire et modification
d’une source tierce contenant `main`) sont corrigés par G033, intégré et vérifié
sur fichiers fictifs. Cela ne qualifie pas une installation Debian.

## État intégré au 06/10, lot G049

API C-009b et client G031 réunis ; 87 tests Python ciblés réussis pour les reçus
et commandes/API, puis 18 tests Node reproduits dont quatre avec serveur réel.
Les deux essais Chromium sont rapportés réussis par Claude sur sa livraison,
mais sautés ici faute d’exécutable. Aucun test serveur/PC utilisateur ou tunnel
SSH réel effectué ; les conditions ci-dessus restent à valider avant qualification.

## Séance du soir — G052

G032–G035 intégrés. La [recette serveur/PC](BETA-ACCEPTANCE.md) et le
[jeu de six missions](BETA-FIXTURE.md) sont disponibles. C-009d/e/f/g apportent
création privée du jeton, disponibilité HTTP bornée, validation des projections
et préparation synthétique isolée. 608 tests Python réussis, six intégrations
mémoire non exécutées ; 24 contrôles de recette locale avec processus réels.
[Bilan détaillé](validation/2026-10-06/codex-evening/README.md).

La prochaine file Claude est G036–G041 : reçus, accessibilité, navigateur/API,
mesures, lanceur candidat et contrat des commandes. Les trois premières
conditions de qualification ci-dessus restent ouvertes : elles exigent encore
un navigateur et le parcours sur les machines de toytoy.

## Recette autonome et paquet — 07/10

La [commande beta_check](BETA-LOCAL-CHECK.md) exécute 24 contrôles avec de
vrais processus sur données temporaires. Le même parcours est vérifié depuis
un wheel installé dans un venv isolé, sans téléchargement. Les assets du client
sont fournis séparément par `--web-root`, ils ne sont pas contenus dans le wheel.
[Preuves](validation/2026-10-07/codex-beta/README.md).

La validation locale ne remplace pas les essais sur Debian 13, Windows ou SSH.
Le lanceur PowerShell reste candidat ; ses chemins relatifs de diagnostic
sont corrigés, mais ce n'est pas une exécution Windows.


## Actualisation du 07/10, C-021

Le profil local `research-sim` exécute la boucle de mission sur pages fixes,
avec objectif, garde, historique nettoyé et vérification liés à la mission.
Il ne contacte aucun fournisseur réel. Voir [le parcours](RESEARCH-MISSIONS.md).
Le paquet installé passe 24 contrôles bêta, puis la création, la reprise et
la lecture d’historique d’une mission de deux pages ; 733 tests Python et
six intégrations mémoire sur corpus temporaire passent. 49 tests du client
passent ; les 12 cas Chromium restent ignorés dans cet environnement.
[Preuves actuelles](validation/2026-10-07/codex-research-runtime/README.md).
La qualification Debian/Windows/SSH sur les machines utilisateur reste ouverte.

## Actualisation du 09/10, G082 (Claude)

Recette opérateur synthétique rejouée depuis le **paquet installé** (commit
`aa245e1`) : **28/28** dans le conteneur. Elle couvre :

- démarrage et diagnostic ;
- tunnel (relais local à la place de SSH) ;
- conversation avec un profil simulé choisi explicitement ;
- rappel mémoire simulé ;
- coupure et retour ;
- reçus anciens après redémarrage ;
- arrêt.

[Rapport et commandes VM100/Windows préparées](validation/2026-10-09/claude-g082/README.md).

Consigne nouvelle : le tunnel SSH doit garder **le même port** des deux côtés
(`-L 127.0.0.1:8765:127.0.0.1:8765`). Sinon, la conversation est refusée
(`HOST_REFUSED`), alors que la lecture fonctionne.

Restent à faire sur les machines de toytoy : le vrai `ssh -L`, le navigateur
ou la WebView Windows, la coupure réseau réelle, le vrai modèle et le vrai
Memory Engine.
