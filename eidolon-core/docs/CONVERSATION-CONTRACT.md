# Contrat conversation/1 — de la conversation à la mission

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G084.
Code : [conversation.py](../src/eidolon_core/conversation.py).
Tests : [test_conversation.py](../tests/test_conversation.py).
Exemples : [examples/conversation/](examples/conversation/).

Statut : **contrat pur**. Aucun stockage (G085), aucun adaptateur de modèle (G086),
aucune route HTTP (G087), aucune interface (G088). Rien ici ne lance une mission.

## Règle centrale

Un texte produit par le modèle n'est ni une autorisation ni une exécution :

- Core affiche ce texte comme une donnée (`model_text`) ;
- Core décide seul de la nature de la réponse ;
- Core dérive lui-même la requête de mission, à partir d'un catalogue que le
  modèle ne peut pas modifier ;
- seule une **soumission humaine**, qui nomme l'empreinte exacte de la
  proposition figée, peut conduire à une mission.

## Les sept objets

| Objet | Protocole | Qui le produit |
| --- | --- | --- |
| Tour utilisateur | `eidolon-conversation-turn/1` | client, validé par Core |
| Sortie du modèle | version 1 : `kind`, `text`, `proposal` | modèle, **non fiable** |
| Réponse | `eidolon-conversation-reply/1` | Core |
| Proposition de mission | `eidolon-mission-proposal/1` | Core uniquement |
| Soumission | `eidolon-proposal-submission/1` | humain, via un client |
| Lien conversation → mission | `eidolon-conversation-link/1` | Core |
| Mission et résultat | missions existantes (`client-sync/1`) | runtime existant |

### Tour utilisateur

- Champs exacts : `store_id`, `conversation_id` (`c-` + 32 hex), `turn_id`
  (`t-` + 32 hex), `sequence` (à partir de 1), `role` = `user`, `text` (1 à 8 000
  caractères), `client_id`, `client_turn_key`, `previous_turn_sha256`.
- Les tours forment une **chaîne** : chaque tour porte l'empreinte du précédent.
  `check_turn_order` refuse un trou, une bifurcation ou un tour d'une autre
  conversation ou d'une autre base (`TURN_OUT_OF_ORDER`).
- Répétition : même `client_id` et même `client_turn_key` avec le même contenu,
  c'est le même tour. Avec un contenu différent, la demande est refusée
  (`same_request`, `TURN_KEY_REUSED`).

### Sortie du modèle

Format JSON strict :

```json
{"version": 1, "kind": "answer|clarification|proposal|out_of_scope", "text": "…", "proposal": null}
```

Une proposition s'écrit `{"template": …, "parameters": {…}}`.

Sont refusés :

- les clés en double, `NaN`, une profondeur supérieure à 4 et une taille
  supérieure à 16 Kio ;
- une version autre que 1 et tout champ en plus ;
- une proposition présente hors du `kind` `proposal`.

Une sortie illisible ou absente n'est **jamais** devinée ni réparée : la réponse
devient `UNAVAILABLE`, avec `MODEL_OUTPUT_INVALID` ou `MODEL_UNAVAILABLE`.

### Réponse : Core décide de la nature

| La sortie du modèle | Ce que Core vérifie | Réponse |
| --- | --- | --- |
| `answer` / `clarification` | rien à exécuter | `ANSWER` / `CLARIFICATION`, aucune proposition |
| `out_of_scope` | — | `OUT_OF_SCOPE`, avec la liste des capacités (`candidates`) |
| `proposal` avec un modèle de mission inconnu | catalogue `TEMPLATES` | `OUT_OF_SCOPE` `TEMPLATE_UNSUPPORTED` |
| `proposal` avec des paramètres inattendus | paramètres exacts | `CLARIFICATION` `PARAMETERS_INVALID` |
| `proposal`, cible ambiguë | catalogue de cibles | `CLARIFICATION` `TARGET_AMBIGUOUS`, candidats **issus du catalogue** |
| `proposal`, cible inconnue | catalogue de cibles | `CLARIFICATION` `TARGET_ABSENT` |
| `proposal`, capacité absente | catalogue de cibles | `OUT_OF_SCOPE` `CAPABILITY_ABSENT` |
| `proposal` valide | tout ce qui précède | `PROPOSAL`, avec une proposition figée et son empreinte |

Toute réponse porte `model_text_is_evidence: false` et `authorizes_execution: false`.

Depuis G091, une réponse porte aussi `context` : ce que le modèle a reçu
(tours entiers transmis ou exclus, état de la mémoire, extraits tronqués), avec
`partial`. Il vaut `null` quand le modèle n'a rien produit d'utilisable.
Voir [DIALOGUE.md](DIALOGUE.md).

Les `sources` contiennent au plus 5 références mémoire (`information_id@revision`),
triées et sans doublon. Le contenu rappelé n'est pas une instruction.

### Proposition figée et versionnée

- Elle reprend la conversation, le tour source et son empreinte, le modèle de
  mission, la cible demandée **et la cible résolue** (`target_id`), ainsi que
  l'empreinte du catalogue.
- Elle contient la requête **dérivée par Core**, par exemple « Diagnostiquer le
  service synthétique : nas ».
- Elle porte `requires_human_submission: true` et `authorizes_execution: false`.
- Une nouvelle proposition dans la même conversation garde le même
  `proposal_id`, prend `version + 1` et porte `supersedes_sha256`, l'empreinte de
  la version précédente.
- `validate_proposal` refuse une proposition retouchée : autre requête,
  autorisation ajoutée, modèle de mission non pris en charge, ou chaîne de
  versions incohérente.

### Soumission (demande d'action humaine)

- Champs exacts : `store_id`, `client_id`, `command_key`, `conversation_id`,
  `proposal_id`, `proposal_version`, `proposal_sha256`, `actor` et `reason`
  (obligatoires et bornés).
- `check_submission` n'accepte que la **dernière** version, inchangée, de cette
  conversation et de cette base :
  - version dépassée : `PROPOSAL_STALE` ;
  - empreinte différente : `PROPOSAL_CHANGED` ;
  - autre proposition, autre conversation ou aucune proposition :
    `PROPOSAL_UNKNOWN`.
- La répétition suit la règle des commandes existantes : même clé et même
  contenu, c'est la même soumission ; même clé avec un autre contenu, c'est
  `COMMAND_KEY_REUSED`.
- Le jeton de lecture actuel n'autorise **aucune** soumission. Le droit
  d'écriture sera défini par G087.

### Lien vers la mission et son résultat

- `mission_arguments(proposal)` renvoie la requête et l'intention explicite
  transmises à `Store.create`. C'est le seul chemin, et le texte du modèle n'y
  entre jamais.
- `make_link` puis `check_link` vérifient que la mission **est** la proposition
  soumise, et pas seulement qu'elle porte son identifiant : même requête, même
  type, même `request_sha256` et même `target_id` résolu. Toute incohérence
  donne `LINK_INVALID`.
- Le résultat se lit sur la mission par les projections existantes. La
  conversation ne recopie ni ne résume ce résultat.

## Périmètre MVP

- Une conversation, une proposition explicite à la fois.
- Une seule mission proposable : `service_diagnostic.synthetic`, en lecture
  seule, sur le catalogue de cibles configuré.
- Le redémarrage simulé, la recherche et les agents média ne sont **pas**
  proposables par la conversation. Ils sont expliqués comme hors capacités.

## Preuves

`python3 -m unittest tests.test_conversation` : 23 tests, dont :

- tours falsifiés, désordonnés ou rejoués ;
- 12 sorties de modèle malformées ;
- injection dans le texte du modèle ;
- propositions retouchées, périmées ou changées ;
- 7 liens falsifiés ;
- un parcours réel : Store, mission créée depuis la proposition, diagnostic
  synthétique `SUCCEEDED`, lien vérifié sur la mission terminée ;
- les exemples publiés revalidés, la réponse de proposition reproduite à
  l'identique.

## Limites

- Aucun horodatage dans ces objets : Core les ajoutera au stockage (G085).
- L'idempotence est définie (`same_request`) mais pas encore persistée (G085,
  G087).
- Le catalogue de modèles de mission est figé dans le code (une seule entrée).
  L'étendre demande une revue.
