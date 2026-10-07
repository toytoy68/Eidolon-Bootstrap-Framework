# G061 — contre-revue des diagnostics de reprise, des copies de revue et des consultations CLI

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G061](../../../../collaboration/tasks/C-TASK-G061.md),
avec son complément C-027.

Cible figée : `7b46ab0`, en copie `git archive`. Elle contient C-022, C-025,
C-026 et C-027. Sources non modifiées.

```sh
python3 docs/validation/2026-10-07/claude-g061/probes_g061.py <copie>/eidolon-core/src
```

Méthode :

- états synthétiques créés par le Core figé ;
- **tous** les diagnostics passent par la CLI (codes de sortie, JSON et
  humain) ;
- chaque dossier d'état reçoit une **empreinte** avant et après (chemin,
  taille, SHA-256, `mtime`) pour détecter toute création ou mutation.

Tout ce qui suit a été **exécuté**, sauf mention « par lecture ». Sortie :
[probes.txt](probes.txt).

## runtime-inspect (C-022)

| Cas | Résultat |
| --- | --- |
| état absent | code 2 `INSPECTION_STATE_UNAVAILABLE` ; **dossier non créé** |
| mission terminée (JSON et humain) | code 0, `TERMINAL_STATE_RETAIN_EVIDENCE` ; **fichiers identiques** ; texte de la demande absent des deux sorties |
| mission inconnue, identifiant mal formé | code 2 |
| arrêt après `WORKER_SPAWNED` | `RUNNING/EXECUTING`, appel `STARTED`, reçu `MISSING`, indice `EFFECT_UNKNOWN_REVIEW_REQUIRED` ; fichiers identiques |
| arrêt après `RESULT_SAVED` | appel `RETURNED`, reçu `PRESENT_UNVERIFIED`, indice `RETURNED_RESULT_AWAITS_VERIFICATION` ; fichiers identiques |
| verrou de mission tenu par **un autre processus**, puis relâché | `HELD_AT_SAMPLE`, puis `FREE_AT_SAMPLE` |
| 15 inspections sous écrivain concurrent intensif | 1 `SNAPSHOT_CHANGED_RESAMPLE` ; quelques refus code 2 `INSPECTION_STORAGE_UNAVAILABLE` (budget de 2 s) ; aucune capture présentée comme stable à tort |

### Budget

| Cas | Résultat |
| --- | --- |
| ancienne mission sans limite | `LEGACY_UNBOUNDED`, `audit_checked=false` |
| compteur altéré | `INVALID`, `remaining=null`, indice `INVOCATION_BUDGET_INVALID` |
| événement de réservation de 20 Kio | `UNAVAILABLE` (`RESERVATION_SIZE_LIMIT`), pas une corruption présumée |
| **limite 3, mission bloquée par le budget** | **`AVAILABLE`, `remaining=1`, indice `BLOCKED_REVIEW_MISSION`** (G061-1) |

Dans tous les cas : fichiers identiques, aucune donnée privée. La reprise
reste décidée par `run`, qui répond `INVOCATION_BUDGET_EXHAUSTED`.

### G061-1 (P3) — budget « disponible » alors que la mission est bloquée pour budget

Le diagnostic ne déclare `EXHAUSTED` que si `used == limit`. Or le runtime
exige **2 places** avant un outil : l'outil et sa première vérification.
Avec 2 réservations sur 3, la mission est `BLOCKED /
INVOCATION_BUDGET_EXHAUSTED`, mais le diagnostic affiche `AVAILABLE`,
`remaining=1`, sans l'indice « budget épuisé ». L'opérateur reçoit donc
un signal trompeur, sans aucun risque d'exécution.

Proposition (Codex, `runtime_inspect.py`), au choix :

- reprendre le code d'erreur enregistré dans la mission ;
- ou signaler `INSUFFICIENT_FOR_TOOL_AND_VERIFICATION` quand il reste
  moins de 2 places avant un outil.

## recovery-prepare / recovery-inspect (C-025)

| Cas | Résultat |
| --- | --- |
| préparation, puis inspection globale et par mission | code 0, `historical_only=true` ; projection de mission sans demande ; **fichiers identiques** |
| `runtime-inspect`, `client-missions`, `client-snapshot`, `run` sur la copie | tous code 2 `RECOVERY_REVIEW_ONLY` ; la copie **reste** en revue |
| ancien rapport sans `capture_semantics` | accepté, comme documenté |
| `source_store_id = store_id`, `execution_authority=true`, `capture_semantics` inconnue, `store_id` de base différent | `RECOVERY_REPORT_MISMATCH` |
| JSON malformé, clé dupliquée, `NaN` | `INVALID_RECOVERY_RECORD` |
| rapport de 40 000 octets, 10 001 missions | `RECOVERY_INSPECTION_LIMIT` |
| rapport absent | `RECOVERY_REPORT_MISSING` |
| mission absente de la copie | code 2, mais erreur brute `KeyError` (cosmétique, P3) |

Chaque refus laisse les fichiers identiques. Aucun rapport partiel n'est
présenté comme une inspection complète : tout refus donne le code 2, sans
rapport.

Le motif (`reason`) de la préparation est restitué **tel quel**, y compris
un courriel synthétique qui y avait été placé. C'est conforme au contrat
(annotation locale, pas un export anonymisé), mais l'opérateur doit le
savoir.

## Consultations CLI client (C-027)

| Cas | Résultat |
| --- | --- |
| `client-missions`, `client-snapshot`, `client-poll` sur un état normal | code 0 ; **fichiers identiques** ; demande absente |
| état absent | code 2 ; **non créé** |
| table `command_receipts` absente, `user_version` 0, `sync_metadata` absente | code 2 `UNSUPPORTED_READ_SCHEMA` ; **aucune migration**, fichiers identiques |
| copie de revue | code 2 `RECOVERY_REVIEW_ONLY` |
| 10 captures sous écrivain concurrent intensif | réussies ou refusées `STORAGE_UNAVAILABLE` ; séquences croissantes, jamais d'état partiel |

## Limites

- L'écrivain concurrent est volontairement extrême (insertion en boucle
  serrée). Les refus `STORAGE_UNAVAILABLE` mesurent le budget de 2 s, pas
  un usage réaliste.
- Ces diagnostics ne prouvent ni l'absence d'effet externe, ni l'absence
  de réécriture SQL cohérente. Ils ne le prétendent pas : vérifié par
  lecture des sorties (`external_effects_known=false`,
  `authorizes_execution=false`).
- Linux, système de fichiers local, Python 3.11.
