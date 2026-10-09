# Export et inspection des conversations

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G093.
Code : [conversation_export.py](../src/eidolon_core/conversation_export.py).
Tests : [test_conversation_export.py](../tests/test_conversation_export.py).

## Un export est un historique, jamais une commande

- **Pas d'import**, nulle part : ni fonction, ni route, ni CLI. Un export ne
  peut ni réactiver une mission, ni ramener un accord, ni piloter un serveur.
- Il porte `historical: true`, `authorizes_execution: false` et
  `import_supported: false`. L'inspection signale toute autre valeur.
- Les soumissions n'y figurent qu'en **résumé** : clé, statut, proposition,
  empreinte, mission et lien vérifié. Le corps renvoyable n'y est pas, ni le
  motif.
- **Aucun secret** : ni clé `ecc_…`, ni son empreinte, ni jeton de lecture.
  Le magasin d'appairage n'est pas lu.

## Commandes (côté serveur, par l'opérateur)

```text
python -m eidolon_core.conversation_export export --state <état> --client-id <client> \
    --conversation-id <c-…> --output <nouveau fichier>.json
python -m eidolon_core.conversation_export inspect <fichier>.json      # hors ligne, sans état
```

- `export` refuse un dossier d'état absent (rien n'est créé) et la
  conversation d'un autre client. Il écrit un **nouveau** fichier 0600 :
  jamais d'écrasement, jamais à travers un lien. Il est limité à 16 Mio et ne
  modifie aucune base (empreintes vérifiées).
- `inspect` relit un fichier régulier borné, refuse les clés JSON en double,
  puis recalcule :
  - la chaîne des tours (`previous_turn_sha256`, séquences) ;
  - le lien de chaque réponse à son tour (`turn_sha256`, `in_reply_to`) ;
  - l'empreinte des propositions et leur chaîne de versions ;
  - le lien de chaque soumission à sa proposition et à sa mission.

  Il ne contacte aucun serveur.

## Schéma `eidolon-conversation-export/1`

Les champs sont exacts ; tout champ en plus, par exemple un chemin de pièce
jointe, rend l'export incohérent :

| Champ | Contenu |
| --- | --- |
| `schema`, `exported_at` | version et date de l'export |
| `store_id`, `conversation_id`, `client_id` | identités |
| `turns` | liste de `{turn, received_at, reply}` |
| `proposals` | propositions, dans l'ordre des versions |
| `submissions` | résumés des soumissions |
| `historical`, `authorizes_execution`, `import_supported` | drapeaux décrits plus haut |

Il n'y a pas de pièces jointes aujourd'hui. Les références média opaques
viendront avec G094 ; elles ne deviendront jamais des chemins.

## Ce que l'inspection prouve, et ce qu'elle ne prouve pas

- `CONSISTENT` : les empreintes et les liens concordent. L'export n'a pas été
  corrompu accidentellement, et il ne prétend aucun droit.
- `authenticity: NOT_ESTABLISHED` : aucune signature. Le texte des réponses
  est lié à son tour, mais pas chaîné ; une modification accompagnée du
  recalcul des empreintes n'est pas détectable.
- Testés comme détectés : texte d'un tour modifié, réponse détachée,
  autorisation ajoutée, proposition modifiée, lien vers une autre mission, tour
  retiré, champ en plus, import déclaré possible.

## Limites

- L'export est une commande d'opérateur ; aucune route ne permet au client de
  télécharger ses conversations.
- Pas d'effacement des conversations (vides ou non) dans ce lot.
