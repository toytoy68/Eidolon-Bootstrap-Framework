# G042 — contre-revue de la consultation des reçus C-009b (`37dc199`)

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G042](../../../../collaboration/tasks/C-TASK-G042.md).
Cible figée : `37dc199ec5da7da49655c4be1bc27e90d5b62d7d`, copie `git archive`
(`receipt_lookup.py` `70534696…`, `http_api.py` `4d0e5f6a…`). Ni ces sources
ni les tests de Codex ne sont modifiés. `receipt_lookup.py` est **identique**
sur la branche intégrée : les mêmes sondes y donnent les mêmes résultats,
aux horodatages près.

```sh
PYTHONPATH=$FROZEN/eidolon-core/src python3 docs/validation/2026-10-07/claude-g042/probes_g042.py
```

- [Sondes](probes-37dc199.txt), états synthétiques : 3 reçus d'annulation
  (REQUESTED, ALREADY_REQUESTED, ALREADY_TERMINAL) et 2 de décision
  (approve, revoke).
- Chaque altération est faite sur une **copie** de l'état, avec `sqlite3`.
- [Tests de Codex sur la copie figée : 45 OK](codex-tests-on-frozen.txt)
  (`test_receipt_lookup`, `test_http_api`).

## Verdict

| Point | Résultat |
| --- | --- |
| Les 5 reçus authentiques | FOUND, protocole et statut corrects |
| `actor` et `reason` (texte privé de l'événement) | absents de toutes les réponses |
| Décision altérée seule : statut, décision, date, révision | **503**, refus correct (empreinte de la commande et lien à l'événement) |
| Événement altéré (acteur, type) ou supprimé | **503** |
| Corps > 32 Ko, clé JSON en double, corps d'un autre reçu | **503** |
| `store_id` de la base changé | **409 STORE_CHANGED** |
| Commande enregistrée **après** une première consultation | NOT_FOUND puis FOUND, sans renvoi : l'absence reste ambiguë, comme documenté |
| Verrou d'écriture 0,5 s / 3 s | 200 FOUND en 545 ms / **503** après 2,0 s |
| Champ en plus, autre mission, autre Store, clé invalide (HTTP) | 400 / 409 / 409 / 400, sans donnée du reçu dans l'erreur |

## G042-1 — reçu d'annulation altéré seul, exporté comme valide (P3)

Pour les **reçus d'annulation**, quatre champs ne sont liés ni à
l'empreinte de la commande, ni à l'événement :

- `mission_status_at_recording` ;
- `mission_revision` ;
- `cancel_requested_at_recording` ;
- `recorded_at`, vérifié seulement par égalité avec l'événement.

Une modification de **la seule ligne du reçu** passe donc :

| Altération d'une seule ligne | Résultat |
| --- | --- |
| C5 : `NEW` → `RUNNING` | FOUND, exporte RUNNING |
| C6 : révision 0 → 5 | FOUND, exporte 5 |
| C7 : ALREADY_TERMINAL, drapeau inversé | FOUND |
| C8 : ALREADY_TERMINAL, `CANCELLED` → `SUCCEEDED` | FOUND : le reçu affirme que la mission était **réussie** à l'enregistrement |

C-009b l'annonce en partie : « Les états historiques du reçu ne constituent
pas un audit complet […] notamment la révision et le statut historiques
d'annulation ». Le cas C8 montre que l'état terminal lui-même peut être
changé. Les décisions, elles, sont bien protégées, car `expected_revision`
entre dans l'empreinte.

**Proposition** (Codex décide) : écrire dans le détail de l'événement
`CANCEL_*` l'empreinte du reçu entier (`receipt_sha256`), puis la comparer à
la lecture. Toute altération isolée de la ligne du reçu serait alors
refusée. Cela s'appliquerait aux nouveaux reçus seulement : les anciens
resteraient lisibles avec la limite actuelle, signalée.

## Hors périmètre, confirmé

**C16, modification cohérente** : changer `recorded_at` dans le reçu **et**
dans l'événement donne FOUND avec une fausse date. C'est la limite annoncée :
sans signature, une réécriture cohérente de la base n'est pas détectée.

## Limites

États synthétiques. Concurrence simulée par un verrou `BEGIN EXCLUSIVE`, pas
par plusieurs écrivains réels. La sonde D1 montre l'ambiguïté de NOT_FOUND
sur une commande enregistrée juste après ; elle ne fige pas une commande en
vol au milieu de sa transaction.
