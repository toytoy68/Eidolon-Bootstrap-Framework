# G059 — contre-revue des missions de recherche synthétique (C-021)

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G059](../../../../collaboration/tasks/C-TASK-G059.md).

Cible figée : `6bc15e1`, en copie `git archive`. Les fixtures C-021 sont
fixes : aucun réseau. Sources non modifiées ; la proposition est jointe à
part.

```sh
python3 docs/validation/2026-10-07/claude-g059/probes_g059.py <copie>/eidolon-core/src
```

Une recherche réellement lancée se compte par le **nombre de fiches dans le
journal de la garde** : chaque `coordinator.run` écrit exactement une
intention. Les coupures sont provoquées par le point d'arrêt (`checkpoint`)
du runtime, dans des sous-processus.

Sorties : [cible](probes.txt), [avec la proposition](probes-proposal.txt).

## Résultats

| Thème | Cas | Résultat |
| --- | --- | --- |
| Nominal | lisible / partiel / vide / bloqué, 2 pages requises | `SUCCEEDED` + `ACHIEVED`, puis `BLOCKED` + `PARTIAL` / `NOT_ACHIEVED` ; **1 recherche** chacune, 4 invocations |
| | reprise après la fin | aucune nouvelle recherche |
| | texte gardé par la garde | `notice pont` : courriel et téléphone retirés |
| Contrat hors modèle | plan modifiant la requête, la cible, `operation_id`, ou ajoutant un champ | `PREFLIGHT_REFUSED`, **0 recherche** |
| | mémoire avec un faux `_core_research` | écrasé par le runtime : la recherche porte l'`operation_id` de la mission |
| | création avec 0 ou 3 pages, `True`, requête vide, requête de 1001 caractères | refusée |
| Rapports | rapport authentique | vérifié |
| | rapport de m1 présenté pour m2 ; texte de page modifié ; cible abaissée ; tampon pointant la recherche de m2 | **non vérifiés** |
| Coupures | après `CALL_STARTED`, après `WORKER_SPAWNED` | `REVIEW_REQUIRED / UNKNOWN_EFFECT`, **0 recherche**, aucune relance |
| | après `RESULT_SAVED` | la reprise vérifie seulement : `SUCCEEDED`, toujours 1 recherche |
| Garde | **absente** pendant la vérification | le runtime **recrée un journal vide** ; la mission passe `CONFIGURATION_CHANGED`, appel `RETURNED` conservé ; après restauration, la reprise vérifie et réussit |
| | occupée | le runtime ne se construit pas (`WEB_RESEARCH_IN_FLIGHT`) ; il reprend ensuite normalement |
| | intention incertaine, journal intact | nouvelle mission : `REVIEW_REQUIRED / CALL_ERROR` (la garde refuse) |
| | **intention incertaine, puis journal supprimé** | **nouvelle mission : `SUCCEEDED`**, dans un journal neuf (G059-1) |
| Budget | limite 3 | `INVOCATION_BUDGET_EXHAUSTED`, 0 recherche |
| CLI | `research` (JSON) et `run --format human` | affichent la demande d'origine **avec** courriel et téléphone : document local privé, comme documenté |
| HTTP | santé, liste, détail | **aucune donnée personnelle**, aucun texte de page |

## G059-1 (P2) — le runtime recrée en silence un journal de garde supprimé

`SyntheticResearchBackend.__init__` ouvre la garde avec la valeur par défaut
`create=True`, et recrée aussi la base des pauses. À **chaque** construction
du runtime (CLI `research` ou `run`), un journal supprimé est donc recréé
vide, sans avertissement.

- Les missions existantes sont protégées : leur configuration nomme
  l'ancien `guard_id` → `CONFIGURATION_CHANGED`.
- Mais une **nouvelle** mission recherche normalement, même si l'ancien
  journal contenait une intention **incertaine**. Mesuré : `SUCCEEDED`.

C'est le contournement que la garde documente (« supprimer le journal »),
sauf qu'ici il ne demande aucun geste explicite.

[Proposition](proposal-no-silent-guard.diff), sur `research_runtime.py`
seulement :

- créer la garde et les pauses **uniquement** au premier usage du dossier ;
- ensuite, `create=False` : un journal absent donne
  `RESEARCH_GUARD_NOT_FOUND`, et des pauses absentes
  `RESEARCH_PAUSES_MISSING`.

Mesuré : journal supprimé → runtime refusé, rien n'est recréé ; restauration
→ reprise vérifiée. Les autres sondes sont inchangées. Suite complète :
**773 OK**, 7 ignorés ([sortie](proposal-tests.txt)).

Limite : supprimer **tout** le dossier `research-fixture` ressemble à un
premier usage. Pour l'éviter, il faudrait que le Store signale l'existence
de missions de recherche. À décider par Codex.

## Observations

- La coupure entre `CALL_STARTED` et l'intention de garde laisse
  `UNKNOWN_EFFECT`. Or l'intention est écrite **avant** tout contact : son
  absence pour cet `operation_id` prouve qu'aucun fournisseur n'a été
  appelé. Une reprise sans revue serait donc sûre dans ce cas précis.
  C'est une piste d'ergonomie (P3), pas un défaut.
- Avec une intention incertaine, une nouvelle mission échoue en
  `CALL_ERROR` : le code ne dit pas que la cause est la garde. Message à
  préciser (P3).
- Garde occupée : l'erreur sort de la construction du runtime, avant
  toute mission. Le contrat (« vérification indisponible, résultat
  conservé ») n'est pas atteint par ce chemin, mais rien n'est perdu.

## Limites

- Fixtures fixes, Linux, Python 3.11. Ni fournisseur réel, ni VM, ni
  Windows.
- Les coupures sont placées sur trois points du journal de mission.
- La sortie CLI contient la demande d'origine : c'est le contrat C-021
  (document local), non un défaut.
