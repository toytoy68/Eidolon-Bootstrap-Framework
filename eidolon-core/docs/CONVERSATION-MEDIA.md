# Conversation ↔ agents Image/Vidéo : frontière et contrat

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G094.
Code : [conversation_media.py](../src/eidolon_core/conversation_media.py).
Tests contractuels : [test_conversation_media.py](../tests/test_conversation_media.py).
Côté Codex : [MEDIA-AGENTS.md](MEDIA-AGENTS.md) (`media_*.py`, magasin d'artefacts,
moteurs).

## Qui possède quoi

| Domaine | Propriétaire | Ce qui traverse la frontière |
| --- | --- | --- |
| Demande média, validation (`prepare`), moteurs, magasin d'artefacts, références `media-artifact-ref/1`, états des travaux | Codex (`media_*.py`) | une **demande** validée par `prepare`, une **référence opaque** |
| Conversation, proposition figée, rattachement d'un artefact à un propriétaire et à une conversation, soumission humaine, droits | Claude (`conversation*.py`, API) | la proposition `eidolon-media-proposal/1` et sa soumission |

## Parcours visé

1. **Artefact.** Aujourd'hui, l'opérateur l'importe
   (`eidolon-media artifact-import`) ; demain, ce sera un upload authentifié.
   Aucune route d'upload n'est improvisée ici.
2. **Rattachement par Core** (`attachment`) : la référence opaque est liée à
   un `owner_client_id` et à une `conversation_id`. Ce n'est **jamais** le
   navigateur qui fournit la référence, ni un chemin, ni une provenance.
3. **Suggestion du modèle**, par exemple
   `{"template": "media.image.edit", "parameters": {"prompt", "artifact_id", "format"}}`.
   Le modèle ne peut citer qu'un `artifact_id` ; c'est Core qui prend la
   référence complète dans **ses** rattachements.
4. **Proposition figée** (`freeze`) :
   - agent, opération, texte normalisé par `prepare` de Codex, artefact,
     format et durée ;
   - `executor: eidolon-media`, `requires_human_submission: true`,
     `authorizes_execution: false` et
     `success_claim: NEVER_FROM_ENGINE_OR_QUEUE_STATE` ;
   - versions avec `supersedes_sha256`, comme les missions.
5. **Soumission humaine** (`check_submission`) : même contrat que G084, et
   **seul le propriétaire** peut soumettre (`CLIENT_MISMATCH`). Une version
   périmée donne `PROPOSAL_STALE`, une empreinte changée `PROPOSAL_CHANGED`.
6. **Demande remise aux agents** (`media_request`) : agent, opération, texte,
   artefact, format et durée, **revalidés par `prepare` de Codex**. Elle ne
   contient jamais `source` (chemin).
7. **Suivi** (`stage`) : les états média deviennent des étapes de conversation,
   et **aucun** n'est un succès.

   | États média | Étape de conversation |
   | --- | --- |
   | `QUEUED` | en cours |
   | `*_UNVERIFIED` | résultat **non vérifié** |
   | `REVIEW_REQUIRED`, `COLLECTION_INCOMPLETE` | effet inconnu |

## Refus et clarifications

| Situation | Réponse |
| --- | --- |
| Modèle de mission média inconnu (audio, suppression, shell) | `OUT_OF_SCOPE` `MEDIA_TEMPLATE_UNSUPPORTED` |
| Artefact absent, d'un autre propriétaire, d'une autre conversation, référence complète fournie par le modèle, chemin | `CLARIFICATION` `MEDIA_ARTIFACT_NOT_ATTACHED` |
| `source`, format ou durée invalides, durée pour une image, artefact pour une création, texte absent | `CLARIFICATION` `MEDIA_PARAMETERS_INVALID` (validation `prepare` de Codex) |
| Proposition retouchée : autorisation, succès revendiqué, exécutant, artefact, texte non normalisé | refus `INVALID_MEDIA` |

## Liaison côté serveur, revérifiée (G097)

Un identifiant opaque n'est **pas** une autorisation. Depuis G097 :

- **Rattachement enregistré** dans le dépôt des conversations (schéma v3),
  par l'opérateur :

  ```
  python -m eidolon_core.conversation_api --state <état> attach \
    --client-id <client> --conversation-id <c-…> \
    --artifact-root <magasin d'artefacts> --reference ref.json
  ```

  L'artefact est relu par `ArtifactStore.read` de Codex avant tout
  enregistrement.
- **À la proposition** (`propose`) : les rattachements sont relus **à chaque
  fois** pour ce propriétaire et cette conversation. Une référence copiée
  dans une autre conversation, ou utilisée par un autre client, donne
  `MEDIA_ARTIFACT_NOT_ATTACHED` ou `CONVERSATION_UNKNOWN`.
- **Avant l'exécution** (`verify_for_execution`) : le rattachement doit
  toujours exister (`ATTACHMENT_MISSING`), et l'artefact être relu inchangé :

  | Cas | Code |
  | --- | --- |
  | artefact supprimé, magasin remplacé ou illisible | `ARTIFACT_UNAVAILABLE` |
  | contenu ou manifeste modifié | `ARTIFACT_MODIFIED` |
  | magasin occupé | `ARTIFACT_BUSY` |

- Les messages ne contiennent **ni chemin ni contenu** ; les tests le
  vérifient sur les exceptions et sur la sortie de la commande.

Tests : [test_conversation_media_binding.py](../tests/test_conversation_media_binding.py)
(15 tests, avec un vrai magasin d'artefacts de Codex en dossier temporaire).

## Présentation des résultats dans la conversation (G101)

Code : [conversation_media_results.py](../src/eidolon_core/conversation_media_results.py)
et `mediaResultLines` dans [conversation.js](../desktop/connected/src/conversation.js).
Tests : [test_conversation_media_results.py](../tests/test_conversation_media_results.py) (7)
et `conversation.test.js`.

`result_view` construit `eidolon-media-result-view/1` à partir des seuls
enregistrements du serveur : le travail `media-job/1`, la collecte
`media-collection/1` et le magasin d'artefacts. Il n'utilise jamais un chemin
ou une référence écrits par le modèle ou envoyés par le navigateur.

| Contrôle | Effet |
| --- | --- |
| seul le propriétaire de la conversation lit le résultat | sinon `MEDIA_RESULT_UNKNOWN`, même réponse qu'une absence |
| le travail porte l'identifiant figé dans la liaison v5 et la requête préparée **identique** à la proposition soumise | sinon `WRONG_JOB` : rien n'est listé |
| la collecte porte ce travail ; chaque sortie a la provenance de ce travail et de cette collecte | sinon exclue et comptée (`excluded_outputs`) : une référence copiée n'est jamais affichée |
| chaque fichier est relu par le magasin | `hash_verified`, `modified`, `unavailable` ou `busy` ; le contenu reste **non vérifié** |
| collecte interrompue | « collecte partielle : n sur m », fichiers déjà importés conservés |
| texte d'analyse | « observation du modèle, non vérifiée », affiché comme texte |
| historique ancien sans requête structurée | état seulement (`LEGACY_UNVERIFIABLE`), aucun fichier |

Aucun état n'est un succès (`success_claim: false`). L'ouverture d'un fichier
depuis la page est **non disponible** et dite comme telle : il n'y a aucun
bouton. L'opérateur passe par `eidolon-media artifact-export`.

### Raccordement à la page

- **Lien proposition → travail** : dépôt des conversations, schéma v5, table
  `media_links`. L'identifiant exact est figé avec les chemins privés.
  Une liaison v4 migrée n'adopte aucun identifiant : `LEGACY_UNVERIFIABLE`,
  sans observation ni fichier affiché. Voir la migration dans
  [CONVERSATION-STORE.md](CONVERSATION-STORE.md).
  - Commande opérateur, en attendant le worker de Codex :

    ```
    python -m eidolon_core.conversation_api --state <état> media-link --client-id <client> \
      --conversation-id <c-…> --proposal proposition.json --job <dossier du travail> \
      [--collection <dossier de collecte>] --artifact-root <magasin d'artefacts>
    ```

  - Le lien est refusé si le travail ne sert pas exactement cette proposition
    (`MEDIA_JOB_MISMATCH`), s'il est illisible (`MEDIA_JOB_UNAVAILABLE`) ou
    déjà lié à un autre travail (`MEDIA_LINK_CONFLICT`).
- **Route** `media_results`. Les enregistrements sont relus à chaque appel :
  - un fichier modifié depuis apparaît « modifié » ;
  - un travail disparu apparaît « illisible » ;
  - un autre identifiant au même endroit, même avec la même requête, donne
    `WRONG_JOB`, sans exposer son état, son texte ou sa collecte.
- **Page** : bloc « Résultats image et vidéo », bouton « Afficher les
  résultats ». Le contenu est en texte seulement, sans bouton d'ouverture.
- **Tests** :
  - `test_conversation_media_results.py` (10, dont la route et la commande) ;
  - `conversation.test.js` ;
  - Chromium sur le vrai serveur : aucun résultat, puis un vrai travail lié
    par `media_fixture.py`, puis une vue hostile qui reste du texte.

## Reste à raccorder (non livré ici)

Ces étapes dépendent de choix à coordonner :

- **Le dialogue** : ajouter les gabarits média au catalogue de confiance du
  prompt et à `decide_reply`.
- **Lancer** la demande après soumission : par le worker partagé de Codex, ou
  par l'opérateur avec `eidolon-media run`. Le reçu ne doit jamais devenir
  `SUCCEEDED`.
- **Upload authentifié** depuis la page, avec les espaces C-047 :
  `media-agents.js` est à Codex.

## Limites

- Contrat et tests seulement : aucun moteur, aucun fichier lu, aucun travail
  lancé.
- Les quotas et la réservation GPU (C-061) restent du côté de Codex.
