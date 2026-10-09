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

## Reste à raccorder (non livré ici)

Ces étapes dépendent de choix à coordonner :

- **Persistance des rattachements** : une table du dépôt des conversations
  (schéma v3 avec migration explicite), ou le magasin de Codex.
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
