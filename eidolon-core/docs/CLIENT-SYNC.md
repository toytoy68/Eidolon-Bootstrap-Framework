# Synchronisation locale du futur client — C-008a

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Base e25cd2a.
Statut : **implémenté et testé localement**, Python 3.11+/POSIX, bibliothèque
standard. Ce n'est pas une API réseau, un serveur authentifié ou un client Windows.

## Usage exécutable

Depuis eidolon-core/ :

```sh
PYTHONPATH=src:. python -m examples.client_sync_demo --format human
PYTHONPATH=src:. python -m examples.client_sync_demo
PYTHONPATH=src:. python -m unittest tests.test_client_sync -v
```

La démonstration crée un état temporaire, capture une nouvelle mission, exécute
la mission text.stats synthétique existante, reconstruit le lecteur et rattrape
le journal par pages de deux événements. Elle vérifie la livraison répétée,
les références uniques et un seul lancement de l'outil ; un curseur altéré
produit RESET_REQUIRED. La « coupure » consiste à conserver le curseur pendant
que Core avance, sans transport réseau simulé ni serveur lancé.

Pour une mission existante (remplacer m-ID et le répertoire) :

```sh
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo client-snapshot m-ID
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo client-poll m-ID --cursor cursor.json --limit 20
```

cursor.json contient **seulement l'objet cursor** de la réponse précédente,
pas l'enveloppe entière. Fichier borné à 4096 octets. Limite de page 1–100,
50 par défaut. JSON par défaut ; --format human utilise le standard Eidolon.
Code de retour 0 = consultation accomplie, 2 = erreur ou RESET_REQUIRED ; ce
code ne signifie jamais qu'une mission est réussie. Une base absente n'est
pas créée par ces commandes. Aucun Runtime, modèle, mémoire, outil ou monde
simulé n'est construit par la branche CLI de synchronisation.

## Contrat eidolon-client-sync/1

`ClientSync(store).snapshot(id)` et `.poll(id, cursor, limit=50)` sélectionnent
une mission explicite. Pas de liste globale de missions, d'agents ou d'appareils.
L'enveloppe comporte protocol, store_id, mission_id, status, snapshot, events,
cursor, has_more, snapshot_only=true et authorizes_execution=false.

| Élément | Sens |
| --- | --- |
| SNAPSHOT | Capture actuelle ; le curseur démarre au dernier événement de cette mission |
| DELTA | Références d'événements après le curseur, plus une capture actuelle cohérente |
| RESET_REQUIRED | Ancien curseur non continu avec l'état observé ; raison et nouvelle capture fournies explicitement |
| snapshot.as_of_sequence | Dernier événement de la mission visible dans la transaction de lecture |
| snapshot.observed_at | Date de capture du stockage ; aucune preuve de santé actuelle d'un processus ou appareil |
| cursor.sequence | Dernier événement livré au client ; peut être inférieur à as_of_sequence pendant la pagination |
| events | Références sequence/at/kind, sans detail ; aucun correctif d'état à rejouer |
| has_more | D'autres événements existaient dans cette capture après la page rendue |

Une capture initiale n'envoie pas tout le passé. L'historique antérieur reste
accessible par les outils locaux existants (show --events), hors ce protocole.
La mission et le journal sont lus dans une transaction SQLite explicite avec
query_only=ON : une annulation concurrente ne produit pas une mission ancienne
associée à un curseur qui aurait déjà consommé son événement.

## Deux progressions à conserver séparément dans l'interface

1. La projection de mission est remplacée par une capture plus récente du même
   store_id/mission_id, ordonnée par as_of_sequence. Elle ne se reconstruit pas
   depuis les références d'événements ; les pages peuvent décrire un passé
   antérieur à la projection incluse.
2. Le curseur du journal n'avance que jusqu'à la dernière référence reçue.
   Dédupliquer par (store_id, mission_id, sequence). Une réponse répétée peut
   contenir la même page : aucune nouvelle mission, action ou notification en
   double à en déduire. Ne pas remplacer le curseur par as_of_sequence sous
   prétexte que la capture est plus récente.

La révision de mission seule ne suffit pas : request_cancel écrit le drapeau
et l'événement sans incrémenter la révision. Montrer « Annulation demandée »
jusqu'à observation de CANCELLED ; fermer la fenêtre ne demande aucune annulation.
Un statut RUNNING capturé ne prouve pas qu'un processus est encore vivant.

## Projection et autorité

Liste explicite des champs : id, revision, status, phase, cancel_requested,
progress, objective_kind, outcome_status, action_view calculée côté Core.
Pas de requête utilisateur, configuration, contexte mémoire, texte de modèle,
paramètres d'action, sortie d'outil ni détail brut d'événement.
La vue d'accord conserve décision/applicabilité/effet séparés ; une proposition
reste PENDING sans expiration. Un accord USED n'est jamais présenté comme une
preuve d'exécution à lui seul. L'action_view est celle du module déjà testé.

La projection n'est pas suffisante pour approuver une action concrète : les
paramètres liés et le futur contrat de commande restent à fournir. Ne pas
rendre un bouton d'exécution réel actif à partir de ce protocole. Les champs
omis réduisent l'exposition ; les métadonnées restent privées, pas anonymisées.
Un SHA n'est ni une signature, ni une authentification, ni une confirmation
humaine. Aucun accès distant ne doit être ouvert avant authentification et
filtrage par utilisateur/appareil et mission autorisée.

## Curseur, migration et restauration

Le curseur version 1 contient store_id, mission_id, sequence, event_count et
anchor_sha256. Séquences, comptes et révisions exportés sont bornés à
2^53−1 pour garder une représentation exacte en JavaScript ; aucune conversion
avec arrondi. Au-delà : UNSUPPORTED_INTEGER_RANGE. L'ancre inclut tous les champs persistés du dernier événement
livré, y compris son détail, mais n'en publie que l'empreinte. Le nombre des
événements antérieurs de cette mission détecte une suppression du préfixe.
Les séquences globales peuvent sauter à cause d'autres missions : pas de fausse
perte déduite de ces trous, ni de fuite de leurs événements.

Au démarrage de Store, migration additive : table sync_metadata, identifiant
`s-<UUID>` créé une fois, index events_mission_sequence. Les missions, révisions,
événements et user_version=1 sont conservés ; une ancienne base est compatible.
Cette initialisation écrit des métadonnées une fois. Ensuite, les opérations
ClientSync ne modifient ni base, ni mission, ni accord. L'identifiant survit au
redémarrage du processus ; ce n'est pas une identité de machine authentifiée.

RESET_REQUIRED distingue STORE_CHANGED, CURSOR_AHEAD, ANCHOR_CHANGED et
HISTORY_CHANGED. Remplacer explicitement la vue/cursor après signalement du
rattrapage impossible ; aucune relance d'outil ou décision implicite.
Mission absente, historique vide, curseur mal formé ou pour une autre mission :
erreur, aucune capture prétendument valide. Les curseurs n'expirent pas au temps.

Limites : ce protocole suppose l'écriture coordonnée par Store, sans suppression
ou modification manuelle de SQLite. Il ne scelle pas toute l'histoire : une
modification ancienne conservant le compte et l'ancre n'est pas détectée.
Une copie/restauration identique de la base conserve store_id ; une branche
clonée ayant le même préfixe n'est pas identifiée comme une nouvelle machine.
Avant réplication/restauration exploitée en réseau, ajouter une génération de
service et une procédure de changement d'identité. Le journal n'est pas compacté.
Les count(*) parcourent le préfixe de mission indexé ; performances à grande
échelle non qualifiées. La taille du journal complet n'est pas chargée en RAM.

## Prochaine tranche

G012 côté Claude : consommateur pur JS et scénarios du prototype sur les
fixtures produites ici. G009 est reçu dans 111da40 ; G013 corrige le suivi des commandes incertaines.
G009 reste la base graphique, G010 l'étude Windows,
G011 la contre-revue Web sur base figée e25cd2a.
Côté Codex : commandes avec révision attendue et reçu durable de requête,
identité/appairage/révocation avant transport. Déduplication d'une requête ne
signifie pas exécution externe exactement une fois. API, notifications OS,
Windows et validation VM restent distincts de cette tranche.

[Preuves](validation/2026-10-06/codex-client-sync/README.md).

## Durcissement de lecture C-009f — Codex, séance du 06/10 au soir

Le corps JSON de mission doit porter l’identité de la ligne sélectionnée.
Snapshot et inventaire utilisent le même décodage : clés JSON dupliquées
refusées, drapeau SQLite d’annulation limité à 0/1, révision entière sûre.
La projection vérifie les types et les longueurs des métadonnées, les compteurs
de progression et de tentative dans la plage entière exacte JavaScript ;
aucune conversion d’une chaîne ou d’un objet en statut affichable.
Les références d’événement ont une séquence sûre et des libellés/date bornés.

Une structure non exportable donne une erreur de lecture (HTTP 503
STATE_UNAVAILABLE), sans renvoyer le contenu divergent. Les accords sans
preuve d’effet restent ainsi ; aucune réparation, migration ou nouvelle
exécution. Objectif hors catalogue = null, toujours admis. Une preuve
d’action incohérente mais structurellement valide conserve son diagnostic
d’incohérence ; une structure arbitraire n’est pas rendue au client.

Ce contrôle est celui des données exportées ; il ne certifie pas tout le
contenu privé de la mission ni une base modifiée cohérentement à la main.
[Preuves avant/après](validation/2026-10-06/codex-evening/README.md).


## C-027 — CLI strictement en lecture seule, 07/10/2026

Les branches client-missions, client-snapshot et client-poll utilisent désormais
le même ReadOnlyStore que l’API HTTP : mode SQLite ro/query_only, budget SQL
coopératif de deux secondes, refus des états bêta incomplets et des copies de
revue. Elles ne construisent plus Store et ne migrent plus le schéma. Une base
ancienne ou incomplète est refusée par UNSUPPORTED_READ_SCHEMA ; aucune table
ou identité manquante n’est recréée pendant une consultation. Les protocoles,
curseurs et projections restent inchangés.

[Reproduction et vérification](validation/2026-10-07/codex-cli-readonly/README.md).
