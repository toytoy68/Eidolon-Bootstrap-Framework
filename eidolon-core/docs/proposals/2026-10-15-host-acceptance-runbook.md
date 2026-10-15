# Recette hôte reproductible du tick de maintenance (Claude, G256-10)

Auteur : Claude. Date : 15/10/2026, Europe/Paris. Statut : **proposition**.
Ce document **n'exécute rien et n'installe rien**. Il complète la
[recette hors ligne](2026-10-15-claude-offline-acceptance-runbook.md) (G236-9).
Aucune étape ci-dessous ne lance de service, de minuteur ni de tick réel sur
Memory.

## 1. Préconditions (arrêt si une seule manque)

| # | Précondition | Comment la constater | Si absente |
| --- | --- | --- | --- |
| P1 | Préflight hors ligne `PASS` aux SHA recettés | `tools/claude_offline_preflight.py`, code 0 | arrêt |
| P2 | Python ≥ 3.11 ; checkout Core au SHA recetté | `python3 --version`, `git rev-parse HEAD` | arrêt |
| P3 | Politique écrite et relue par toytoy | fichier JSON, voir § 2 | arrêt |
| P4 | L'hôte sait produire l'instantané par **renommage atomique** | revue du script de capture de l'hôte (hors de ce dépôt) | arrêt |
| P5 | Dossier de l'instantané : sans lien symbolique, non modifiable par d'autres comptes | `ls -ld` sur chaque dossier du chemin | arrêt |
| P6 | Horloge de l'hôte synchronisée | `timedatectl` ou équivalent, relevé noté | arrêt |

## 2. Valeurs à fournir (aucune n'est inventée ici)

| Valeur | Qui la fournit | Où |
| --- | --- | --- |
| `expected_source` | toytoy | politique |
| `max_observation_age_seconds`, `max_load_age_seconds` | toytoy | politique |
| `load_unit` (nom de la mesure) et `load_limit` | toytoy | politique |
| Chemins absolus de la politique et de l'instantané | toytoy | ligne de commande |
| Heure d'exécution | relevée au moment de la commande | `--now` |

## 3. Commande (vérification seule, sans effet)

```sh
cd <checkout>/eidolon-core
PYTHONPATH=src python3 tools/claude_host_policy.py --check-only \
  --policy <chemin absolu de la politique> \
  --snapshot <chemin absolu de l'instantané> \
  --now "$(date --iso-8601=seconds)"
```

- Pas de Memory, pas de contrôleur : un moteur factice compte les appels.
- Sortie : une ligne JSON. Code de sortie :
  - **0** : `WOULD_TICK` ;
  - **1** : observation refusée ;
  - **2** : politique ou lecture refusée.

## 4. Cas à jouer et sorties attendues

Chaque cas est couvert par un test de `tests/test_claude_host_policy_g256.py`.

| Cas | Préparation | Sortie attendue |
| --- | --- | --- |
| Nominal | instantané frais, charge sous la limite | code 0, `engine_calls: 1`, `load_ok: true`, `notes: []` |
| Observation périmée | `--now` au-delà de `max_observation_age_seconds` | code 1, `stage: observation` |
| Capture dans le futur | `at` postérieur à `--now` | code 1 |
| Charge inconnue | pas de `load` | code 0, `load_ok: false`, `LOAD_UNKNOWN` : le contrôleur différera |
| Démarrage inconnu | pas de `boot_at` | code 0, `BOOT_AT_UNKNOWN`, `boot_at` = `at` : différé |
| Autre unité de charge | `unit` différent de la politique | code 1 |
| Instantané modifiable par d'autres | `chmod 666` | code 2, `SNAPSHOT_WRITABLE_BY_OTHERS` |
| Permission refusée | `chmod 000` (compte non root) | code 2, `SNAPSHOT_UNAVAILABLE` |
| Politique incomplète | un champ retiré | code 2, `stage: policy` |
| Mauvaise source | `source` différente | code 1 |

**Appel unique** : `engine_calls` vaut exactement 1 quand la décision est
`WOULD_TICK`. Dans les cas refusés, le champ est absent : la fabrique n'est
jamais appelée (prouvé par les tests de `run_with_policy`).

## 5. Arrêt et vérification des effets

- **Arrêt** au premier résultat différent de la colonne « attendue ». On
  note la sortie JSON complète, sans la corriger ni relancer en boucle.
- **Effets** : la commande ne doit rien écrire. On le vérifie avant et
  après la recette :
  - `git status --porcelain` identique dans Core ;
  - même liste et mêmes dates (`ls -l --time-style=full-iso`) pour les
    dossiers de la politique et de l'instantané ;
  - aucun nouveau processus résident (`ps` avant/après).

## 6. Ce qui reste hors de cette recette

- Le **tick réel** sur `IndexMaintenance` : il demande le compte de
  service, les permissions Memory et une fenêtre décidée par toytoy. Aucune
  commande n'est proposée tant que ces décisions ne sont pas prises.
- L'installation d'un service ou d'un minuteur.
- La production de l'instantané par l'hôte (script de capture).
