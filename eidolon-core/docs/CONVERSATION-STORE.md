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
- Le schéma est versionné (`eidolon-conversation-store/4`, `user_version` 4 ; v1 à v3 seulement par migration explicite).
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
  fois (v1 → v2 → v3 → v4), **une transaction par étape**, sur le même Store, et ne
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

**Retour arrière** : arrêter le serveur, puis remettre le fichier de
sauvegarde à la place de `<état>/conversations/conversations.sqlite3` (droits
0600). Les conversations écrites **après** la sauvegarde sont perdues. Il n'y
a pas de migration descendante : un ancien code refuse une base plus récente.

**Limites** : arrêter le serveur avant de migrer (un serveur ancien encore
ouvert est détecté seulement s'il écrit après la sauvegarde) ; la sauvegarde
n'est ni chiffrée ni signée, son empreinte prouve l'intégrité, pas
l'authenticité ; aucun test sur un vrai disque plein.

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
