# Dépôt des conversations — persistance et reprise

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G085.
Code : [conversation_store.py](../src/eidolon_core/conversation_store.py).
Tests : [test_conversation_store.py](../tests/test_conversation_store.py).
Contrat des objets : [CONVERSATION-CONTRACT.md](CONVERSATION-CONTRACT.md) (G084).

## Où et pourquoi séparé

- Le dépôt est `<état>/conversations/conversations.sqlite3`. Le dossier est en
  0700, le fichier en 0600, comme pour `research-fixture/`.
- C'est une **base séparée** : `missions.sqlite3` n'est jamais migré ni écrit par
  ce module. Un test vérifie que son empreinte reste identique après des tours,
  des réponses et des lectures.
- Le schéma est versionné (`eidolon-conversation-store/5`, `user_version` 5 ; v1 à v4 seulement par migration explicite).
  Une autre version est refusée.
- Le dépôt est **lié au Store des missions** par son `store_id`. Copié à côté
  d'un autre Store, il est refusé (`STORE_CHANGED`).

## Ouverture : création explicite, fichier vérifié à chaque accès

Correctifs des constats G085-R1 à R4 de Codex (C-MSG-G107) :

- **Création séparée de la reprise** : `ConversationStore(store, create=True)`
  crée un dépôt absent. Sans `create`, un dépôt absent est refusé
  (`CONVERSATION_STORE_MISSING`) et **rien n'est créé**.
- **Avant chaque connexion** :
  - le dossier doit être un vrai dossier privé (0700, même propriétaire) ;
  - la base doit être un fichier régulier privé (0600), **jamais un lien** ;
  - elle doit rester **le même fichier** (périphérique et inode) qu'à
    l'ouverture.

  Un lien donne `CONVERSATION_STORE_UNAVAILABLE`, sans toucher sa cible (R1).
  Un fichier remplacé donne `STORE_CHANGED` (R2).
- **Connexions sans création** : SQLite est ouvert en `mode=rw`. Une lecture
  d'un fichier supprimé est refusée et ne recrée pas de fichier vide (R3).
- **Identité et schéma relus dans la transaction**, à chaque accès : une base
  d'un autre Store donne `STORE_CHANGED` (R2).
- **Jamais de tables ajoutées à une base existante** : le schéma n'est créé que
  sur une base vide, avec `create=True`. Une base SQLite étrangère reste
  identique octet pour octet.
- **Identité écrite avec le schéma, dans la même transaction**, seulement sur
  une base vide (G085-R5). Une base étrangère qui a déjà une table `meta` vide
  et `user_version=1` est refusée sans être modifiée. L'ouverture ne complète
  ni ne répare jamais une base existante.
- **Bornes du contexte** : `max_turns` de 1 à 200 et `max_chars` de 1 à
  200 000, en entiers stricts (R4).

Ces protections visent les erreurs et les substitutions de fichiers. Elles ne
défendent pas contre un processus hostile qui tourne sous le même utilisateur.

## Schéma v2 : une seule tentative de réponse par tour (G090-R1)

- La table `attempts` enregistre, **avant** l'appel au modèle, une tentative
  par tour, avec son échéance. `claim_attempt` rend l'un de quatre états :

  | État | Signification |
  | --- | --- |
  | `answered` | une réponse existe déjà |
  | `claimed` | cet appelant appelle le modèle, une seule fois |
  | `busy` | une autre tentative est dans son délai : réponse « en préparation » |
  | `expired` | tentative commencée sans réponse enregistrée |

- Une tentative `expired` (coupure, plantage, délai dépassé) n'autorise
  **jamais** un second appel au modèle. Le tour est clos en `UNAVAILABLE`,
  avec `MODEL_ATTEMPT_INTERRUPTED`, et l'utilisateur renvoie un nouveau
  message s'il le souhaite.
- **Migration explicite** :
  `python -m eidolon_core.conversation_api --state <état> migrate --backup <nouveau fichier>`
  (sauvegarde vérifiée d'abord, voir G099 ci-dessous), ou, dans le code,
  `ConversationStore(store, migrate=True)`. Elle avance d'une version à la
  fois (v1 → v2 → v3 → v4 → v5), **une transaction par étape**, sur le même Store, et ne
  réécrit rien d'autre. Une migration interrompue laisse une version
  intermédiaire valide, que la même commande reprend. Sans migration, un
  dépôt ancien est refusé (`CONVERSATION_STORE_MIGRATION_REQUIRED`) **sans être
  modifié** ; une version future est refusée (`CONVERSATION_STORE_UNAVAILABLE`).

## Évolution du stockage : inspection, sauvegarde, migration, retour arrière (G099)

Code : [conversation_storage.py](../src/eidolon_core/conversation_storage.py).
Tests : [test_conversation_storage.py](../tests/test_conversation_storage.py) (10).

| Commande (`python -m eidolon_core.conversation_api --state <état> …`) | Effet |
| --- | --- |
| `inspect-store` | rapport hors ligne en **lecture seule** (SQLite `mode=ro`) : version, état, intégrité, nombre de lignes, empreinte logique. Ne migre jamais ; code 3 si la base n'est pas à jour |
| `backup --output <fichier>` | copie cohérente (sauvegarde en ligne SQLite) vers un **nouveau** fichier 0600, jamais écrasé, puis vérifiée : intégrité, même version, même dépôt, même empreinte logique |
| `migrate --backup <fichier>` | sauvegarde vérifiée, **puis** migration par étapes ; la sauvegarde est obligatoire |

États rapportés : `CURRENT`, `MIGRATION_REQUIRED` (v1 ou v2), `FUTURE_VERSION`
(refusée partout, rien n'est écrit), `UNKNOWN`.

Garanties testées :

- lire n'est jamais migrer : l'inspection et l'ouverture sans `migrate`
  laissent le fichier identique octet pour octet ;
- identifiants, ordre et références conservés : les lignes des tables
  `conversations`, `turns`, `replies`, `proposals` et `submissions` sont
  identiques avant et après ;
- aucune mission rejouée : la base des missions est identique octet pour
  octet ;
- la migration ne commence que si la base contient **encore** exactement le
  contenu sauvegardé, vérifié sous le verrou d'écriture
  (`BACKUP_STALE` sinon) ;
- coupure entre deux étapes : version intermédiaire valide, reprise par la
  même commande ;
- erreur disque pendant une étape : l'étape est annulée ;
- échec de la sauvegarde (disque plein simulé, dossier absent, fichier déjà
  présent) : rien n'est migré, aucun fichier partiel ne reste ;
- sauvegarde endommagée : détectée par `verify_backup`.

**Sauvegarde chiffrée (age)** : demande de toytoy du 10/10/2026. Outil
choisi par toytoy : [age](https://age-encryption.org). La préparation de la
VM ([01-system.sh](../../01-system.sh)) l'installe, avec `age-keygen`, et
vérifie leur présence. Ailleurs : `apt install age`.
Core n'écrit aucun code de chiffrement : il confie les octets à `age` et
contrôle ce qui revient.

| Commande | Effet |
| --- | --- |
| `backup --output <fichier.age> --encrypt-to <destinataires>` | copie et vérification **en mémoire**, puis seule la forme chiffrée est écrite (nouveau fichier 0600) : aucune sauvegarde en clair sur le disque |
| `migrate --backup <fichier.age> --encrypt-to <destinataires>` | même chose avant une migration |
| `decrypt-backup --input <fichier.age> --identity <clé privée> --signer <clé publique de signature> --output <fichier>` | vérifie la signature (**obligatoire**), déchiffre vers un **nouveau** fichier 0600, puis le vérifie ; pour examiner une sauvegarde, la restauration passe par `restore-backup` |

- **Destinataires** : clés **publiques** `age1…`, une par ligne, de 1 à 20,
  sans doublon ; les commentaires `#` sont permis. Le fichier appartient au
  compte du serveur et n'est modifiable que par lui. Pour chiffrer, le serveur
  n'a besoin que de ces clés publiques.
- **Clé privée** : créée avec `age-keygen -o toytoy.key`. La clé publique
  s'obtient avec `age-keygen -y toytoy.key`. Il faut la garder **hors du
  serveur**, ou au moins hors du dossier des sauvegardes, en 0600. Elle ne
  sert qu'au déchiffrement. Deux destinataires (par exemple une clé de
  secours) permettent chacun de déchiffrer.
- **Contrôles** :
  - les clés publiques validées sont passées à `age` sur la ligne de
    commande ;
  - la clé privée est ouverte une seule fois par Core (sans lien symbolique,
    propriétaire, 0600) ;
  - `age` tourne sans variable d'environnement et avec un délai maximal ; ses
    messages ne sont pas relayés.
- **Fichier modifié, tronqué ou mauvaise clé** :
  `BACKUP_DECRYPTION_FAILED`, et aucun fichier partiel ne reste. `age`
  authentifie le contenu.
- `verify_backup` refuse un fichier chiffré (`BACKUP_ENCRYPTED`) : il faut le
  déchiffrer d'abord.
- **Refus avant toute écriture** :
  - `age` absent ou mal installé : `AGE_UNAVAILABLE` ;
  - destinataires invalides : `AGE_RECIPIENTS_REFUSED`.
- La sauvegarde **en clair** reste possible sans `--encrypt-to`.

Tests : [test_backup_encryption.py](../tests/test_backup_encryption.py) (13,
ignorés si `age` n'est pas installé).

**Sauvegarde signée (Ed25519)** : demande de toytoy du 10/10/2026. La
signature passe par l'outil `openssl` (Ed25519), que la préparation de la VM
([01-system.sh](../../01-system.sh)) installe et vérifie. Elle
répond à la limite du chiffrement seul : avec la clé publique age, n'importe
qui peut fabriquer un fichier chiffré, mais pas le signer.

| Commande | Effet |
| --- | --- |
| `backup …` (avec ou sans `--encrypt-to`) | **toujours signée** : écrit aussi `<sauvegarde>.sig` (0600), avec la clé du serveur, ou avec `--sign-with <clé privée>`. En cas d'échec, ni sauvegarde ni signature ne restent |
| `migrate …` | même chose avant une migration |
| `backup-key` | affiche la clé publique du serveur (PEM) et son empreinte, à copier **hors** du serveur |
| `verify-backup --input <sauvegarde> --signer <clé publique>` | vérifie la signature, puis, pour une sauvegarde en clair, son contenu |
| `decrypt-backup … --signer <clé publique>` | `--signer` est **obligatoire** : la signature est vérifiée **avant** de déchiffrer (rien n'est écrit sinon), puis le contenu déchiffré est comparé au manifeste signé |
| `restore-backup --input <sauvegarde> --signer <clé publique> [--identity <clé age>]` | **restauration**, signature obligatoire (voir « Retour arrière ») |

- **Signature obligatoire** (demande de toytoy du 10/10/2026) : aucune
  sauvegarde n'est écrite sans signature. Sans `openssl`, aucune sauvegarde
  n'est possible.
- **Clé du serveur** :
  - Core la crée **une fois**, à la première sauvegarde réussie, à côté de la
    base : `backup-signing.pem` (0600) et `backup-signing.pub.pem` (0644).
  - Le résultat de la sauvegarde l'indique : `signing_key: CREATED`, puis
    `EXISTING`.
  - Copier la clé publique hors du serveur (`backup-key`) : c'est elle qu'on
    passe à `--signer`.
  - Si la clé privée disparaît alors que la clé publique est encore là :
    `SIGNING_KEY_LOST`, et rien n'est recréé en silence. L'opérateur restaure
    la clé, ou supprime explicitement la clé publique pour en créer une
    nouvelle.
- **Autre clé** (facultatif, `--sign-with`) : `openssl genpkey -algorithm
  ed25519 -out signature.pem`, puis `chmod 600 signature.pem` ; la clé
  publique s'obtient avec `openssl pkey -in signature.pem -pubout -out
  signature.pub.pem`.
- **Ce qui est signé** : un manifeste JSON canonique qui contient :
  - l'objet (`eidolon-conversation-backup`) ;
  - l'empreinte et la taille du fichier écrit ;
  - chiffré ou non ;
  - le dépôt, la version et l'empreinte logique ;
  - l'empreinte du clair ;
  - la date.
- **La vérification exige tout**, sans rien deviner :
  - la clé attendue (`BACKUP_SIGNATURE_WRONG_SIGNER`) ;
  - une signature valide ;
  - le même fichier (`BACKUP_SIGNATURE_INVALID`) ;
  - une signature présente (`BACKUP_SIGNATURE_MISSING`).
- **Clés refusées** :
  - clé privée non privée ou non Ed25519 : `SIGNING_KEY_REFUSED`, avant
    toute écriture ;
  - clé publique non Ed25519 ou modifiable par d'autres :
    `SIGNER_KEY_REFUSED`.
- **Limite** : la signature prouve que la sauvegarde vient d'un détenteur de
  la clé du serveur. Si le serveur est compromis, sa clé l'est aussi.

Tests : [test_backup_signature.py](../tests/test_backup_signature.py) (18,
ignorés sans `openssl` ou `age`).

**Réponses à la revue préliminaire de GPT (G140)**

*Clé de signature : export, continuité, incident.*

- **Export, juste après la première sauvegarde** : `backup-key` affiche la
  clé publique (PEM) et son empreinte `ed25519:…`. La copier **hors du
  serveur**, sur le PC et sur un support de secours, avec la date : c'est
  elle, et non le serveur, qui fait foi à la restauration.
- **Continuité** : tant que `backup-signing.pem` est là, toutes les
  sauvegardes portent la même empreinte. Le résultat de chaque `backup`
  l'affiche (`signer`), ce qui permet de la comparer à la copie gardée.
- **Clé privée perdue** (disque, réinstallation) :
  - Core refuse de sauvegarder (`SIGNING_KEY_LOST`) au lieu de recréer une
    clé en silence ;
  - pour repartir, supprimer **explicitement** `backup-signing.pub.pem` : la
    sauvegarde suivante crée une nouvelle clé (`CREATED`) ;
  - exporter aussitôt la nouvelle clé publique, et garder l'ancienne pour
    vérifier les anciennes sauvegardes.
- **Clé privée compromise** (serveur piraté) :
  - la signature ne protège plus rien de ce qui est signé après la
    compromission ;
  - créer une nouvelle clé comme ci-dessus ;
  - ne restaurer que des sauvegardes **antérieures** à l'incident, vérifiées
    avec l'ancienne clé publique gardée hors du serveur ;
  - Core ne gère ni liste de révocation ni horodatage de confiance : c'est
    une limite.

*Concurrence pendant la restauration.*
- `restore-backup` prend un verrou SQLite **exclusif** sur la base.
- Une fois le verrou obtenu, la base doit être **le même fichier**
  (périphérique, inode) que celui verrouillé. Sinon, une autre restauration
  l'a remplacée entre-temps : `RESTORE_REFUSED: … concurrent restore`, et
  rien n'est changé. Ce contrôle a été ajouté pendant cette revue. Son test
  échoue sans lui et passe avec.
- Une base absente est remise par lien (`link`), jamais par-dessus une base
  apparue entre-temps.
- Un serveur resté ouvert obtient `STORE_CHANGED` et n'écrit pas dans
  l'ancien fichier.

*Résistance aux échecs (processus réellement tué, `os._exit`) :*

| Coupure | Base | Reste |
| --- | --- | --- |
| après la préparation de la copie | ancienne, intacte | un fichier `.restore-*.sqlite3` (0600) à côté de la base : c'est la sauvegarde vérifiée, déchiffrée si elle l'était, à supprimer à la main |
| sous le verrou, avant le lien | ancienne, intacte | idem |
| après le lien de garde, avant le remplacement | ancienne, intacte | idem, plus `conversations.sqlite3.before-restore-…` (lien vers l'ancienne) |
| après le remplacement | restaurée | la copie gardée de l'ancienne |

Dans tous les cas, la base reste lisible et `CURRENT`, et relancer la
commande réussit. Le fichier `.restore-*` n'est jamais supprimé
automatiquement : une autre restauration pourrait l'utiliser. Comme la base
elle-même, il est en clair, en 0600.

*Mémoire de la sauvegarde chiffrée* (mesurée sur des bases de 50 et 200 Mo,
processus neuf) :
- en clair : environ 5 Mo de plus, quelle que soit la taille ;
- chiffrée : environ **3,1 fois la taille de la base**, à cause de la copie
  en mémoire puis de sa sérialisation par Python ;
- au-delà de **512 Mio**, une sauvegarde chiffrée est refusée
  (`BACKUP_TOO_LARGE_FOR_MEMORY`) avant toute écriture ;
- la vérification se fait désormais sur la copie en mémoire elle-même, sans
  en faire une seconde.

Une piste écartée : un fichier anonyme en mémoire (`memfd`) ouvert par
SQLite via `/proc/self/fd`. Lors de l'essai, SQLite a résolu le lien et
**écrit la base en clair sur le disque**, sous un autre nom.

**Personnalité du dialogue (C-070)** : la dernière version valide gardée par
Core est une ligne `meta` (`personality_last_valid`) de cette base.

- Elle fait donc partie de la sauvegarde, et elle **compte dans l'empreinte
  logique**. Sans copie, l'empreinte ne change pas par rapport aux versions
  précédentes.
- `inspect-store` et `backup` indiquent :
  - sa version et son empreinte dans `personality`, jamais son texte ;
  - `null` si aucune copie n'existe ;
  - `INVALID` si la copie est altérée.
- Une restauration la ramène. Testé dans
  [test_personality.py](../tests/test_personality.py) (`BackupTests`).

**Retour arrière** (demande de toytoy du 10/10/2026 : vérification de
signature **obligatoire**) : arrêter le serveur, puis lancer `restore-backup
--input <sauvegarde> --signer <clé publique> [--identity <clé privée age>]`.
Une sauvegarde **non signée ne se restaure pas** par Core ; Core n'en
produit d'ailleurs plus.

La commande vérifie dans l'ordre :

1. la signature : clé attendue et fichier exact (`BACKUP_SIGNATURE_*`,
   `BACKUP_SIGNER_REQUIRED` sans clé) ;
2. le même Store (`RESTORE_REFUSED` sinon) ;
3. le contenu, déchiffré si besoin, dans un fichier privé **à côté** de la
   base, vérifié et comparé au manifeste signé.

Ensuite seulement, elle remplace la base sous un verrou exclusif. La base
remplacée est gardée sous `conversations.sqlite3.before-restore-<date>`
(0600).

- Si une autre connexion tient la base : `CONVERSATION_STORE_BUSY`.
- Un serveur resté ouvert ne peut pas écrire dans l'ancien fichier : il
  obtient `STORE_CHANGED`.
- En cas de refus, la base est intacte et aucun fichier temporaire ne reste.

Les conversations écrites **après** la sauvegarde ne sont plus dans la base
restaurée ; elles restent dans la copie gardée. Il n'y a pas de migration
descendante : un ancien code refuse une base plus récente.

Tests : [test_backup_restore.py](../tests/test_backup_restore.py) (10).

**Limites** : arrêter le serveur avant de migrer (un serveur ancien encore
ouvert est détecté seulement s'il écrit après la sauvegarde) ; une sauvegarde
**en clair** n'est pas chiffrée. Chaque sauvegarde est désormais **signée**, et la
restauration exige `--signer` : un fichier chiffré fabriqué avec la seule
clé publique age est refusé. Remettre un fichier à la main contourne
Core : cette voie n'est plus documentée, mais rien ne peut l'empêcher. Aucun
test sur un vrai disque plein.

## Schéma v5 : identité exacte du travail média (C-068)

`media_links.job_id` conserve l'identifiant du travail constaté au moment du
rattachement. Une requête identique ne suffit pas à accepter un autre travail.
La migration v4 → v5 est explicite, avec sauvegarde vérifiée, et laisse NULL
pour les anciennes liaisons dont l'identité n'avait pas été enregistrée :
elles deviennent `LEGACY_UNVERIFIABLE`, sans adoption du dossier courant.
`media-link` refuse de réécrire ces liens (`MEDIA_LINK_CONFLICT`).
Les chemins, propositions et dates historiques sont conservés.

`media_links` participe désormais au digest logique et au comptage des
sauvegardes, tant en v4 qu'en v5. Une modification entre sauvegarde et migration
rend cette sauvegarde périmée (`BACKUP_STALE`).

Validation C-068 : tests Python ajoutés mais non exécutés, environnement
indisponible. Les résultats historiques ci-dessous qualifient leurs bases
respectives. [Périmètre et vérifications](validation/2026-10-09/codex-takeover-c068/README.md).

## Schéma v4 : liens proposition média → travail

La table `media_links` relie une proposition média soumise au travail (et à
la collecte) qui la sert. Elle conserve des chemins privés qui ne sont jamais
rendus à un client. Voir [CONVERSATION-MEDIA.md](CONVERSATION-MEDIA.md).

## Schéma v3 : pièces jointes liées à leur conversation (G097)

- La table `attachments` lie une référence d'artefact opaque
  (`media-artifact-ref/1`) à **un propriétaire et une conversation**.
- `attach` n'enregistre rien tant que `verify(référence)` n'a pas prouvé que
  l'artefact existe, inchangé, dans le magasin de Codex. La conversation doit
  appartenir à ce propriétaire (`CONVERSATION_UNKNOWN`). Le même artefact
  rattaché autrement donne `ATTACHMENT_CONFLICT`.
- `attachments` ne rend que les rattachements de ce propriétaire **et** de
  cette conversation. Voir [CONVERSATION-MEDIA.md](CONVERSATION-MEDIA.md).

## Ce qui est garanti

| Situation | Comportement |
| --- | --- |
| Même tour renvoyé (même `client_id` et même `client_turn_key`) | même tour et même réponse rendus (`replayed: true`) ; aucun doublon |
| Même clé avec un autre texte | `TURN_KEY_REUSED` |
| 8 processus ajoutent des tours en même temps | séquences 1 à 8 contiguës, chaîne d'empreintes intacte |
| Réponse enregistrée deux fois | la seconde fois ne fait rien ; une réponse **différente** pour le même tour est refusée (`REPLY_ALREADY_RECORDED`) |
| Réponse falsifiée (tour, empreinte, base, proposition) | `REPLY_INVALID` |
| Proposition qui ne succède pas à la dernière version | `PROPOSAL_STALE` |
| Plus de 1 000 tours | `CONVERSATION_FULL` |
| Base verrouillée par un autre écrivain | `CONVERSATION_STORE_BUSY` après 2 s, sans écriture partielle |
| Fichier corrompu ou illisible | `CONVERSATION_STORE_UNAVAILABLE` |

## Soumission : jamais deux missions

Les deux bases ne partagent pas de transaction. La soumission est donc
**réservée avant** que la mission soit créée, sous un verrou de fichier qui
sérialise les soumissions :

1. Réservation (`RESERVED`), après `check_submission` sur la dernière version.
2. Création de la mission par la fonction fournie (`create(request, intent)`),
   avec la requête dérivée par Core.
3. Enregistrement de la mission et du lien vérifié (`MISSION_CREATED`).

Si une réservation est retrouvée sans mission (tentative coupée) :

| Constat | Statut | Mission créée ? |
| --- | --- | --- |
| aucune mission candidate (même requête, créée après la réservation) et la proposition est toujours la dernière | création, puis `MISSION_CREATED` | oui, une seule |
| aucune candidate, mais une version plus récente existe | `SUPERSEDED_NOT_CREATED` | **non** |
| au moins une candidate | `MISSION_CREATION_UNCERTAIN`, avec les candidates | **non** : un humain décide |

`resolve_uncertain` exige un acteur et un motif :

- **adopter** une candidate : le lien est vérifié avec `check_link` ;
- ou déclarer qu'**aucune** n'est la bonne : `NO_MISSION_CONFIRMED`. Une
  nouvelle soumission, avec une nouvelle clé, devient alors possible.

Autres règles :

- Une seconde clé pour une proposition déjà soumise est refusée
  (`PROPOSAL_ALREADY_SUBMITTED`).
- Même clé, autre contenu : `COMMAND_KEY_REUSED`.
- `receipt()` retrouve un reçu après une réponse perdue. Un reçu porte toujours
  `execution_evidence: false`.

Tests de coupure :

- exception au point `SUBMISSION_RESERVED`, puis au point `MISSION_CREATED` ;
- **processus tué** (`os._exit`) après la création : une seule mission, et la
  reprise donne `UNCERTAIN` ;
- 6 processus soumettent la même demande en même temps : une seule mission.

## Lecture et reprise

- `page(conversation_id, after, limit ≤ 50)` renvoie les tours avec leur
  réponse, dans l'ordre. `next_after` permet de reprendre après une
  reconnexion, y compris depuis un autre processus.
- `context(conversation_id, max_turns, max_chars)` renvoie les tours les plus
  récents qui tiennent dans le budget, du plus ancien au plus récent, avec un
  indicateur `truncated`. C'est l'entrée du dialogue (G086, budgets G091).

## Séparations conservées

- Les réponses ne gardent que des **références** de sources
  (`information_id@revision`). Rien n'est écrit dans Memory Engine, et une
  réponse ne devient jamais un fait vérifié.
- Il n'existe **aucune** fonction d'import : aucune conversation privée n'est
  importée automatiquement.

## Limites

- Recherche des candidates : une requête sur le corps JSON des missions, limitée
  à 10 résultats, non indexée. Elle ne s'exécute qu'après une coupure.
- Une mission créée par la CLI avec exactement la même requête, dans la fenêtre
  d'une soumission coupée, rend la soumission `UNCERTAIN`. Ce cas est
  volontairement prudent.
- Verrou `flock` local : pas de NFS, et pas de Windows sans adaptation.
- Pas d'effacement ni d'export des conversations ici (G093).
