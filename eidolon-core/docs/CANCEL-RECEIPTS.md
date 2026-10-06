# Demande d'annulation avec reçu — C-008c

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Base `476acc1`.
Statut : livré en Python standard/POSIX, SQLite local. Cette interface de
contrôle de confiance prépare le futur client ; elle n'est pas une API réseau.
Les validations de ce lot emploient exclusivement des missions synthétiques.

## Exécution

Depuis eidolon-core/ :

```sh
PYTHONPATH=src:. python -m examples.cancel_receipt_demo --format human
PYTHONPATH=src:. python -m examples.cancel_receipt_demo
PYTHONPATH=src:. python -m unittest tests.test_cancel_commands -v
```

Deux scénarios : avant exécution, demande enregistrée puis mission annulée par
un run explicite ; après interruption au marqueur CALL_STARTED, demande
également enregistrée mais mission maintenue en REVIEW_REQUIRED. La démo jette
la réponse initiale, reconstruit Store, retrouve le reçu et vérifie qu'une
répétition n'ajoute pas d'événement. Ce n'est pas une simulation de transport.
Son appel interrompu est arrêté **avant lancement de l'enfant** ; le runtime
reste conservateur devant son marqueur durable. Un test distinct annule un
vrai enfant après un effet local commis et vérifie que cet effet est conservé.

Pour un état existant :

```sh
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-demo command-cancel --request cancel.json
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-demo command-receipt --store-id s-ID --client-id desktop-test --command-key cancel-001
```

Les identifiants doivent provenir de client-snapshot. Le fichier cancel.json
suit le contrat ci-dessous ; la démo JSON produit deux exemples dans
scenarios[].command, dont les bases temporaires sont supprimées en fin de démo.
Une base absente est refusée, sans création. command-cancel ne construit aucun
Runtime, modèle, moteur mémoire ou monde simulé ; pas besoin de --profile.
La nouvelle commande ne lance, ne reprend et ne réconcilie aucune mission.
L'ancienne CLI cancel garde son comportement existant : demande puis tentative
de traitement par Runtime.cancel. Elle ne produit pas de reçu rétroactif.

Code 0 = traitement de la commande enregistré, **pas arrêt confirmé**. Un
ALREADY_TERMINAL donne aussi 0, avec son issue explicite. Code 2 = erreur ou
conflit ; une erreur système n'est pas une preuve d'absence de commit. Consulter
le reçu. JSON par défaut ; --format human utilise la bannière ECT et INFO.

## Contrat eidolon-cancel-command/1

CancelCommands(store).submit(command) accepte exactement les champs suivants :

| Champ | Valeur / borne |
| --- | --- |
| protocol | eidolon-cancel-command/1 |
| store_id | s-UUID observé via client-snapshot |
| client_id | Espace local de clés, mêmes règles que les décisions C-008b |
| command_key | Clé conservée avant émission, mêmes règles que C-008b |
| mission_id | Identifiant m-UUID existant |
| actor | Libellé explicite, 1–200 caractères non vide après trim |
| reason | Motif explicite, 1–4 000 caractères non vide après trim |

UTF-8, fichier ≤32 768 octets ; doublons JSON, données non finies, substituts
isolés, champs supplémentaires et mauvaise version refusés. Les clés/client_id
font 1–80 caractères ASCII alphanumériques, point, tiret, soulignement ; premier
caractère alphanumérique. Le même client_id/command_key partage l'espace des
clés approve/reject/revoke. Une clé de décision ne peut devenir une annulation.

**Pas de révision attendue ni d'empreinte de proposition.** Annuler demande
l'arrêt de la mission entière nommée, y compris si elle progresse depuis la
capture. Cela ne modifie ni son objectif ni sa cible. Exiger une révision ici
empêcherait une demande d'arrêt utile chaque fois que le runtime avance.
L'identité exacte du Store et de la mission reste obligatoire ; aucun alias de
cible n'est accepté. L'annulation de toutes les missions n'est pas implémentée.

## Traitement atomique

Store.record_cancellation reçoit la requête validée et ouvre BEGIN IMMEDIATE.
L'identité du Store et l'éventuel reçu précédent sont vérifiés dans cette même
transaction. Même clé/contenu retourne exactement le reçu historique ; autre
contenu donne COMMAND_KEY_REUSED sans effet sur la mission.

| État observé dans la transaction | cancel_outcome | Modification |
| --- | --- | --- |
| Non terminal, demande absente | REQUESTED | Flag cancel_requested=true et événement CANCEL_REQUESTED |
| Non terminal, demande déjà présente | ALREADY_REQUESTED | Flag inchangé, événement CANCEL_COMMAND_RECORDED |
| SUCCEEDED / FAILED / CANCELLED / ABANDONED | ALREADY_TERMINAL | Mission intacte, événement CANCEL_COMMAND_RECORDED |

Le reçu est inséré dans la transaction du flag et de l'événement. Une erreur
avant commit annule les trois. Une réponse perdue après commit se retrouve avec
command-receipt. Deux commandes identiques simultanées retournent le même reçu,
sans deuxième événement ; deux clés différentes gardent leurs propres reçus
mais ne produisent qu'une transition CANCEL_REQUESTED.

La commande n'acquiert **pas le verrou d'exécution** de la mission. SQLite
sérialise brièvement les écritures avec le délai existant de cinq secondes :
ce n'est ni un arrêt temps réel ni une garantie de disponibilité sous charge.
Le flag est lu dans sa colonne dédiée ; la révision et le corps de la mission
ne sont pas réécrits. ClientSync détecte le changement via la séquence du journal,
même à révision constante. Les données actor/reason restent dans l'événement
interne, jamais dans les références d'événements exposées par ClientSync.

Le runtime conserve ses règles : s'il constate un effet inconnu, il reste en
revue ; si un appel n'a pas été autorisé, il peut confirmer l'annulation sans
l'exécuter. Une demande commise avant la transaction de succès empêche le
succès final. Un succès déjà commis reste un succès, avec reçu ALREADY_TERMINAL.
Une demande tardive ne rembobine pas la mission et ne supprime aucune preuve.

## Reçu eidolon-cancel-receipt/1

Champs : protocol, status=RECORDED, store_id, client_id, command_key, mission_id,
request_sha256, cancel_outcome, mission_status_at_recording, mission_revision,
cancel_requested_at_recording, event_sequence, recorded_at,
execution_evidence=false et effect_absence_evidence=false.
Révision et séquence restent des entiers sûrs JSON/JavaScript.

Ce reçu est **historique**. REQUESTED avec mission_status_at_recording=RUNNING
ne signifie ni arrêt de l'enfant ni effet absent ; CANCELLED observé plus tard
ne signifie pas non plus qu'aucun effet n'a jamais eu lieu. Le client doit garder
séparés reçu de commande, capture actuelle et résultats/preuves de la mission.
La consultation commune eidolon-command-lookup/1 retourne désormais un reçu
de décision **ou** d'annulation : identifier explicitement receipt.protocol.
Un type inconnu ne doit pas être interprété comme un accord ou une annulation.

NOT_FOUND, échec de consultation ou changement de Store conservent les règles
C-008b : aucune réémission automatique autorisée, aucune absence d'effet déduite.
La consultation elle-même ne provoque aucun traitement de la demande en attente.

## Limites et suite

Pas d'identité authentifiée : actor/client_id sont des libellés locaux, pas des
permissions distantes. Pas de serveur, lancement distant, arrêt externe forcé,
garantie exactement une fois ni effacement de l'incertitude. Un effet déjà
commis peut persister après annulation ; réconciliation ou abandon explicite
reste nécessaire selon la mission.

C-008d fournit une [copie historique gardée](RECOVERY-REVIEW.md), sans réactivation.
Hors de cet outil, mêmes limites que C-008b : identité copiée avec sauvegarde/clone,
reçus récents perdus lors d'une restauration ancienne, rétention sans purge ni
quota. Coupure électrique, NAS, Windows et VM non qualifiés. Les autres appels
Store restent des interfaces internes de confiance ; un opérateur pouvant
modifier directement la base n'est pas limité par ce protocole.

Prochaine tranche : contre-revue de ces courses, stratégie de génération après
restauration, appairage/authentification puis API distante. Les commandes run
restent séparées et ne disposent pas encore de ce protocole de reçu.
[Preuves](validation/2026-10-06/codex-cancel-receipts/README.md).

## Correction E1 — audit du 06/10/2026

Une annulation arrête les nouveaux appels d'outil, mais n'empêche plus le
vérificateur de contrôler une sortie déjà reçue et persistée. Le vérificateur
est un callback de confiance **sans mutation** : il ne doit jamais réexécuter
l'action. Son délai par appel reste appliqué. Si son appel échoue ou dépasse
le délai, la mission reste BLOCKED en phase VERIFY, même avec cancel_requested ;
un run explicite reprend cette vérification, pas l'outil.

Une sortie invalide donne FAILED/VERIFICATION_FAILED. Une sortie valide suivie
d'une annulation donne CANCELLED, avec preuves VERIFIED et issue ACHIEVED ou
PARTIAL selon la couverture ; result reste nul. Aucun outil suivant ne démarre.
Un effet encore inconnu conserve REVIEW_REQUIRED et la réconciliation explicite.
Les anciennes missions déjà terminales ne sont pas rouvertes automatiquement :
leurs preuves peuvent être inspectées, aucune migration de leur statut livrée.

[Audit, reproductions et limites](AUDIT-2026-10-06.md).
