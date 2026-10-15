# Recette VM/PC hors ligne : procédure et préflight (Claude, G236-9)

Auteur : Claude. Date : 15/10/2026, Europe/Paris. Statut : **proposition**.
Rien n'est lancé par ce document : ni service, ni installation, ni
benchmark sémantique, ni accès au corpus privé, ni réseau.

## 1. Principe

1. **Arrêt sur inconnu** : une vérification `UNKNOWN` arrête la recette
   comme un `FAIL`. Personne ne suppose un état non observé.
2. **Lecture seule d'abord** : le préflight ne fait que lire
   (`git rev-parse`, `git status`, `find_spec`, `disk_usage`, `lstat`).
   Le secret du pont n'est **jamais ouvert**.
3. **Références figées** : les mesures existantes servent de base de
   comparaison. Elles ne sont **pas relancées** par cette procédure.

## 2. Prérequis à réunir avant de commencer

| Élément | Source | Si absent |
| --- | --- | --- |
| SHA Core et Memory à recetter | dernier message GPT, `docs/PROJECT-STATUS.md` | arrêt |
| Python ≥ 3.11, `qdrant_client` | `pyproject.toml` Core et Memory | arrêt |
| Dossier de données et espace minimal | décision toytoy (aucune valeur inventée ici) | arrêt |
| Secret du pont, dans un dossier 0700 sous un chemin **sans lien symbolique** | G235 (A08) | arrêt |
| Sauvegarde vérifiée du canon Markdown | `docs/VM-OPERATIONS-ACCEPTANCE.md` (Memory) | arrêt |
| VM/MCP joignable | état actuel : **non qualifié** | arrêt |

## 3. Préflight (sans effet)

```sh
python eidolon-core/tools/claude_offline_preflight.py --confirm-read-only \
  --core <checkout Core> --expect-core <SHA Core> \
  --memory <checkout Memory> --expect-memory <SHA Memory> \
  --data-dir <dossier de données> --min-free-bytes <octets décidés> \
  --credential <chemin du secret du pont>
```

- Sortie : un rapport JSON.
- Code de sortie : 0 si tout est `PASS`, 1 si une vérification est `FAIL`,
  2 si une vérification est `UNKNOWN`.
- Sans `--confirm-read-only`, rien ne s'exécute.
- Tests : `eidolon-core/tests/test_claude_offline_preflight.py` (5 tests,
  dont « n'écrit rien dans les dépôts » et « ne lit jamais le secret »).

## 4. Étapes de recette, à faire seulement après un préflight `PASS`

| Étape | Commande ou document existant | Preuve attendue | Arrêt si |
| --- | --- | --- | --- |
| 1. Suites hors réseau | `pytest -q` Core et Memory aux SHA recettés | mêmes comptes que la CI publiée | un échec ou un compte différent non expliqué |
| 2. Qualification Qdrant locale | `docs/G222-QUALIFICATION-RUNBOOK-2026-10-14.md` (Memory) | journal de commandes et SHA | serveur non local ou non jetable |
| 3. Worker J2 | `docs/J2-WORKER-QUALIFICATION-2026-10-14.md` (Memory) | aucune suppression, reprise après arrêt | toute suppression, tout `INDEXED` sans preuve |
| 4. Recette VM | `docs/VM-ACCEPTANCE-2026-10-03.md`, `docs/VM-OPERATIONS-ACCEPTANCE.md` (Memory) | sauvegarde puis restauration vérifiées | sauvegarde non vérifiée |
| 5. Bêta PC et serveur | `docs/BETA-SERVER-PC.md`, `docs/G221-INTEGRATED-BETA-ACCEPTANCE.md` (Core) | grille de G221 | un critère non observé |

## 5. Références de performance (à comparer, pas à relancer)

Fichiers JSON sous `docs/benchmarks/` dans Memory :

- `information-writes-2026-10-01.json` ;
- `information-batches-2026-10-02.json` ;
- `journal-scans-before-2026-10-01.json` et `journal-scans-after-2026-10-01.json` ;
- `maintenance-*-2026-10-02.json`.

Le point de référence sémantique est
`docs/G182-SEMANTIC-CHECKPOINT-2026-10-12.md` (Memory).

Une nouvelle mesure se fait sur le **même** matériel, et seulement sur
décision explicite de toytoy.

## 6. Limites

- Le préflight ne prouve ni la santé d'un service, ni l'accès réseau, ni
  les permissions effectives d'un compte de service.
- `numpy` absent donne `UNKNOWN` (dépendance d'identité optionnelle) et
  arrête donc la recette tant que toytoy n'a pas décidé de son périmètre.
