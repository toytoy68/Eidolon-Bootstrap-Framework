# Budget durable des invocations — C-015

07/10/2026. Les nouvelles missions reçoivent par défaut **64 invocations**.
La limite est une configuration de Core, jamais un paramètre décidé par le
modèle. `Limits(max_invocations=N)` et la CLI `--max-invocations N` acceptent
1 à 4096. La limite et le compteur sont persistés dans la mission.

Une invocation est un passage par le lanceur de processus contrôlé du runtime :
rappel mémoire, proposition du modèle, exécution d'outil, vérification et
observations préalables de l'action simulée. Lectures CLI, décisions humaines,
parseurs locaux, consultation HTTP et appels de recherche candidate ne sont
pas dans ce compteur. La recherche a ses propres limites et sa garde.

## Invariants

- Compteur et événement `INVOCATION_RESERVED` écrits dans la même transaction,
  **avant le démarrage du worker**. La réservation est conservée même si le
  processus s'arrête avant de démarrer le worker : comptage prudent.
- Erreur, délai, mémoire vide, reprise et réconciliation « sans effet » ne
  remboursent pas les réservations. Un même état persistant garde son budget.
- Le compteur est comparé aux ordinaux et limites du journal. Modifier seulement
  le compteur ou perdre un événement donne `INVOCATION_BUDGET_INVALID`.
- Avant un nouvel outil, il doit rester de quoi lancer l'outil **et une première
  vérification**. Les contrôles d'autorisation pouvant eux-mêmes appeler des
  observateurs, la disponibilité est revérifiée après eux et avant le commit
  `CALL_STARTED`. Une approbation n'est pas consommée si cette vérification échoue.
- À épuisement : `BLOCKED / INVOCATION_BUDGET_EXHAUSTED`, sans nouveau worker.
  Un résultat déjà retourné reste `RETURNED`, conservé avec son empreinte ;
  aucune promotion en succès ou annulation propre d'un effet non vérifié.
- Les voies de réconciliation/abandon existantes restent disponibles. Une
  réconciliation ne remet pas le compteur à zéro et n'augmente pas la limite.

Une vérification défaillante peut épuiser le budget : avoir réservé une place
ne garantit pas qu'elle réussira. Le résultat non vérifié peut être abandonné
explicitement avec ses preuves conservées. Aucune relance automatique n'est
introduite. Modifier la limite au redémarrage, même pour l'augmenter, donne
`CONFIGURATION_CHANGED` pour la mission existante.

## Commandes et compatibilité

```sh
python -m eidolon_core --state /chemin/etat --max-invocations 64 demo
python -m eidolon_core --state /chemin/etat --max-invocations 64 run m_ID
```

Reprendre avec la **même configuration** que lors de la création. Une ancienne
mission dont la configuration ne contient pas `max_invocations` n'est pas
migrée silencieusement : le nombre de ses anciennes invocations n'était pas
journalisé complètement. Le mode explicite `--max-invocations 0` (API :
`Limits(max_invocations=None)`) restaure la configuration historique sans
budget, sous réserve que tous les autres paramètres correspondent. Ce mode
peut aussi créer une mission sans budget : il n'est pas présenté comme borné.
Il ne désactive pas le budget d'une mission déjà créée avec une limite.

Le mode humain affiche les invocations réservées et la limite. Le JSON expose
`invocation_budget: {limit, used}` ; aucune nouvelle permission n'en découle.

## Portée et limites

Ce compteur borne les invocations, **pas** le nombre de commandes `run`, la
taille de l'historique, les appels internes d'un adaptateur de confiance, les
octets stockés ou le temps total de vie d'une mission. La rétention reste
séparée. Le délai existant par appel reste inchangé. Une restauration cohérente
de la base, le SQL direct ou une nouvelle mission échappent à ce compteur ;
il ne constitue ni une signature ni un quota global de serveur.

[Preuves](validation/2026-10-07/codex-invocation-budget/README.md) : reprises,
crash avant worker, défaut d'audit, résultat non vérifié, conditions d'action,
configuration figée et compatibilité explicite, sur données synthétiques.
