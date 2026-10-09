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
- Le schéma est versionné (`eidolon-conversation-store/1`, `user_version` 1).
  Une autre version est refusée.
- Le dépôt est **lié au Store des missions** par son `store_id`. Copié à côté
  d'un autre Store, il est refusé (`STORE_CHANGED`).

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
