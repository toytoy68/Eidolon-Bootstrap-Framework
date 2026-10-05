# Vue des accords et des effets — suites de G005

Auteur : Codex/GPT. Date : 05/10/2026. Base Core `02af040`, contre-revue Claude
`0e601e7`, intégrée avec son historique. Les huit sondes de Claude ont été
reproduites sous Python 3.12.14 ; leur sortie est identique après la ligne de
version Python. [Preuves](validation/2026-10-05/codex-g005/README.md).

## Trois informations distinctes

La CLI ajoute `action_view` au JSON des missions avec proposition. Le mode humain
présente les mêmes informations dans le cadre Eidolon. Cette vue est recalculée
à partir du snapshot, sans sauvegarde, lecture réseau, observation du service ou
appel modèle. `proposal.status`, les décisions et les événements ne changent pas.
Les API d'orchestration et leurs empreintes de configuration ne sont pas modifiées.

| Champ | Sens |
| --- | --- |
| `decision.status` | Décision durable : PENDING, APPROVED, REJECTED, REVOKED ou USED |
| `applicability.code` | Blocage connu ou contrôle restant à faire, selon le snapshot |
| `effect.code` | Nature de la preuve conservée pour la tentative de cette proposition |
| `call_id`, `attempt`, `proposal_sha256` | Liaison à la proposition et à sa tentative exacte |
| `snapshot_only: true` | Vue de l'état conservé, aucune observation actuelle |
| `authorizes_execution: false` | Métadonnée explicite : cette vue n'accorde jamais une permission |

Une vue fournie dans une entrée est ignorée : le rendu humain et la sortie JSON
la recalculent. Le runtime ne lit pas `action_view` pour décider. Il conserve
permissions, contrôles de condition, consommation atomique et vérification.

## Applicabilité et reprise

- `AWAITING_DECISION` : PENDING, sans expiration automatique.
- `RECHECK_REQUIRED` : APPROVED, mais les contrôles de `run` restent obligatoires.
  Cet affichage ne signifie jamais « exécutable maintenant ».
- `STALE_CONDITION` : la dernière observation conservée diffère de la condition
  liée à l'accord, ou le runtime a signalé ACTION_PRECONDITION_CHANGED. Dans
  C-005a, créer une nouvelle mission après revue ; la décision passée reste
  conservée. Révoquer ensuite l'accord ne fait pas oublier l'observation.
- `CONFIGURATION_MISMATCH` : la dernière reprise a utilisé une configuration
  différente. **Ce n'est pas forcément définitif** : restaurer la configuration
  d'origine peut permettre une reprise après les contrôles normaux. Cette nuance
  complète O-G5-2 ; ne pas convertir tout ce cas en « expiré ».
- `BINDING_INVALID` : empreinte de proposition incohérente ou liaison refusée.
- `CONSUMED` : USED, accord consommé au lancement ; il ne peut pas être rejoué.
- `REJECTED`, `REVOKED`, `CANCEL_REQUESTED`, `MISSION_CLOSED` indiquent leur
  obstacle propre. La fermeture et l'annulation ont priorité dans l'affichage.

Aucun âge ne rend un accord périmé. Seuls les faits conservés dans le snapshot
sont décrits ; un état changé depuis la dernière lecture reste inconnu ici.

## Preuve d'effet

| Code | Ce qui est effectivement connu |
| --- | --- |
| `NOT_STARTED` | Cette proposition correspond à une tentative PREPARED, sans lancement enregistré |
| `NOT_AUTHORIZED` | L'historique indique que cette tentative n'a pas reçu l'autorisation d'appeler l'outil |
| `NO_EFFECT_REPORTED` | Réconciliation humaine avec confirmation d'absence d'effet ; cette vue ne la prouve pas |
| `UNKNOWN` | Accord consommé sans preuve permettant de conclure, ou tentative introuvable |
| `RESULT_UNVERIFIED` | Résultat ou reçu positif conservé, vérification encore nécessaire |
| `VERIFIED_PAST_EFFECT` | Résultat de cette tentative marqué VERIFIED, lié à l'accord et empreinte cohérente ; preuve historique |
| `INCONSISTENT_EVIDENCE` | Empreinte ou liaison incohérente ; aucun effet confirmé par la vue |

Une tentative remise à PREPARED possède un nouveau numéro. Si la proposition
courante concerne encore la précédente, la vue cherche **cette ancienne tentative**
dans `attempt_history`. Dès qu'une nouvelle proposition est créée, elle décrit
la nouvelle tentative, sans lui attribuer les reçus de l'ancienne.

`USED` peut donc coexister avec `NOT_AUTHORIZED` (annulation avant l'appel),
`UNKNOWN` (interruption), `NO_EFFECT_REPORTED` ou `VERIFIED_PAST_EFFECT`.
Un reçu positif, même tardif, reste non vérifié tant que le vérificateur n'a pas
réussi. Une erreur d'outil ne prouve pas l'absence d'effet.

## Décision concernant O-G5-3

La réconciliation conserve son comportement prudent. Même si la transaction du
simulateur a rejeté une action avant écriture, cette tranche n'ajoute aucun chemin
automatique « sans effet ». Le protocole général ne déduit rien d'un message
d'erreur. Aucun mécanisme de relance ou permission n'a changé pour améliorer
l'affichage.

## Démonstration

Depuis `eidolon-core/` :

```sh
PYTHONPATH=src:. python -m examples.action_view_demo
PYTHONPATH=src:. python -m examples.action_view_demo --format human
```

Six missions synthétiques : attente, accord, condition changée, accord consommé
puis annulation avant autorisation, configuration différente, effet vérifié puis
service repassé DOWN. Chaque scénario contrôle les états attendus et le compteur
d'effets fictifs. Toutes les bases sont temporaires ; aucun service réel.

Pour inspecter une mission existante, `show ID` expose `action_view` en JSON ;
`--format human show ID` utilise le rendu commun. Conserver le même `--state`.
La vue ne crée ni décision ni événement et ne confirme aucune source mémoire.
Les propositions historiques restent lisibles sans migration.

## Limites

Code/fichiers locaux de confiance ; les empreintes vérifient la cohérence, pas
l'authenticité face à un acteur réécrivant toutes les preuves. Le rendu ne relance
pas le vérificateur ni ne prouve une santé actuelle. Aucun client distant,
authentification humaine, pare-feu/VPN, VM ou réseau réel ajouté par ce lot.
