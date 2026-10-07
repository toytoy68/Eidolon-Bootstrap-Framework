# Examiner une mission bloquée ou interrompue — C-026

Codex/GPT, 07/10/2026. Parcours local Linux/POSIX, depuis `eidolon-core/`,
avec le code correspondant à l’état examiné. Il relie les commandes existantes
sans déclencher une reprise. Conserver l’identifiant de mission et le chemin
d’état exacts ; aucun jeton HTTP n’est nécessaire.

## Lire l’état de travail existant

Choisir une mission dans le client ou dans l’inventaire local :

```sh
PYTHONPATH=src python -m eidolon_core --state /chemin/etat client-missions
PYTHONPATH=src python -m eidolon_core --state /chemin/etat runtime-inspect m-IDENTIFIANT
```

Les chemins et l’identifiant sont des valeurs à remplacer. `client-missions`
est paginé ; sa première page n’est pas nécessairement l’inventaire complet.
Pour un affichage console, placer `--format human` avant `runtime-inspect`.
Les deux consultations n’exécutent ni le modèle ni les outils de la mission.
Un répertoire absent n’est pas créé par ces commandes. Depuis C-027,
l’inventaire CLI utilise aussi le lecteur SQLite sans initialisation ni
migration ; une base de schéma ancien/incomplet est refusée pour revue.

Lire d’abord `mission_id`, `observed_at`, `status`, `phase` et
`changed_during_sampling`. Si ce dernier est true, conserver cette observation
puis demander une nouvelle capture explicitement. Un changement fréquent ne
justifie pas une boucle de relance de la mission.

| Indication | Lecture utile et suite de l’examen |
| --- | --- |
| `LOCAL_LOCK_HELD` | Un verrou était détenu pendant le sondage. Examiner le processus déjà connu du lancement ; le rapport ne donne pas son identité et n’en demande pas l’arrêt. |
| `FREE_AT_SAMPLE` ou `MISSING` | Aucun verrou détenu n’a été établi à cet instant. Ce n’est pas une preuve d’arrêt de tous les descendants ni d’absence d’effet. |
| `RETURNED_RESULT_AWAITS_VERIFICATION` | Un résultat est durable mais pas encore vérifié. Conserver le reçu, le résultat et la garde de recherche ; leur présence ne justifie pas de rejouer l’outil. |
| `EFFECT_UNKNOWN_REVIEW_REQUIRED` | Une tentative peut avoir produit un effet. Examiner les preuves propres à cet outil avant toute décision explicite de réconciliation. |
| `INVOCATION_BUDGET_EXHAUSTED` | Le budget durable est consommé. Relancer avec une autre limite ne remplace pas le contrat enregistré de cette mission. |
| `INVOCATION_BUDGET_INVALID` | Le compteur et son audit ne concordent pas. Conserver les données pour revue, sans réécrire le compteur. |
| `INVOCATION_BUDGET_UNAVAILABLE` | L’audit dépasse une borne du diagnostic. Le budget restant n’est pas établi ; ce code ne démontre pas une corruption. |
| `CANCELLATION_REQUESTED_NOT_PROOF_OF_STOP` | La demande d’annulation est enregistrée. Les effets et la fin des ouvriers restent à examiner séparément. |
| `TERMINAL_STATE_RETAIN_EVIDENCE` | La mission porte un état terminal. Les preuves et les éventuels effets inconnus restent à conserver. |

Un budget `AVAILABLE`, un reçu `PRESENT_UNVERIFIED` ou un marqueur `MARKED`
n’autorisent aucune action. `authorizes_execution=false`,
`receipt_content_verified=false` et `external_effects_known=false` restent
explicites. Le diagnostic ne lit pas la garde de recherche. Les détails et
limites des sondages sont dans [RUNTIME-INSPECTION.md](RUNTIME-INSPECTION.md).

## Examiner une copie de revue déjà préparée

Si la consultation ordinaire répond `RECOVERY_REVIEW_ONLY`, utiliser son
lecteur historique :

```sh
PYTHONPATH=src python -m eidolon_core --state /chemin/copie-revue recovery-inspect
PYTHONPATH=src python -m eidolon_core --state /chemin/copie-revue recovery-inspect --mission-id m-IDENTIFIANT
```

`source_store_id` désigne l’origine, `store_id` la nouvelle identité de revue.
Les champs `status_at_snapshot` et `proposal_status_at_snapshot` décrivent le
passé. Un accord `APPROVED` ou `USED` dans cette copie n’est pas une nouvelle
autorisation. `historical_only=true` et `execution_authority=false` doivent
rester présents. Aucune commande ne réactive actuellement une copie de revue.

Pour préparer volontairement une nouvelle copie, suivre le parcours séparé
[RECOVERY-REVIEW.md](RECOVERY-REVIEW.md) : cette opération écrit dans une
**destination neuve**, conserve la source et ne remplace pas une sauvegarde
complète. Une perte de réponse peut arriver après publication de la copie ;
inspecter la destination existante avant d’envisager une autre préparation.

## Interpréter les sorties et préserver les preuves

| Résultat du diagnostic | Signification |
| --- | --- |
| Code 0 avec rapport | La lecture demandée a abouti. La mission peut être bloquée et son budget invalide. |
| Code 2 | Lecture refusée ou indisponible. Ce code seul ne prouve ni un effet ni son absence. |
| `RECOVERY_INCOMPLETE` | Préparation non publiée. Garder le dossier et ses marqueurs pour examen. |
| `RECOVERY_REPORT_MISMATCH` / `INVALID_RECOVERY_RECORD` / `INVALID_RECOVERY_MISSION` | Métadonnées ou projection historique refusées. Aucun rapport partiel n’est produit. |
| `RECOVERY_INSPECTION_LIMIT` | L’inspection dépasse une borne de volume, nombre ou temps coopératif. La copie reste gardée. |
| `INSPECTION_STORAGE_UNAVAILABLE` / `STORAGE_UNAVAILABLE` | Lecture SQLite indisponible. Examiner la disponibilité du stockage ; ne pas déduire un état de mission absent. |

Noter le commit Core, l’heure, le code de retour et le rapport obtenu. Ne pas
retirer les marqueurs, réinitialiser le budget ou effacer des reçus pour faire
passer le diagnostic. La copie SQLite historique n’inclut pas les reçus des
ouvriers, les baux, la simulation ni Memory Engine ; ces éléments restent des
preuves distinctes. Les annotations acteur/motif de récupération peuvent
contenir du texte personnel : les rapports historiques ne sont pas anonymisés.

## Essai sans données personnelles

La [recette locale](BETA-LOCAL-CHECK.md) vérifie l’observateur HTTP sur un état
jetable. Le [jeu synthétique](BETA-FIXTURE.md) fournit des identifiants connus
pour pratiquer ce parcours, notamment `not_started`, `cancel_requested` et
`text_completed`. Les consulter ne change pas les attentes du manifeste.
Les fixtures de recherche restent locales ; ce parcours ne qualifie ni un
fournisseur Web réel, ni Windows, SSH ou un serveur utilisateur.
