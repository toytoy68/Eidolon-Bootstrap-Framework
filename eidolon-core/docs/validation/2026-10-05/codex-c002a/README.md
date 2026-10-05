# C-002a.1 — validation Codex/GPT — 05/10/2026

## Bases examinées

Core précédent : `b028957d225c0475b3e856e971f88cbbcb3ad008`.
Branche Claude intégrée : `4283db98e4c51743042e911ad3bd9eb1033a70b6` ; politique
Web livrée par `b869eef`. Prise en charge publiée : `7eafc78`.
Python 3.12.14, Linux/POSIX, bibliothèque standard. Les adresses globales des
fixtures servent uniquement à la classification ; elles ne sont pas contactées
et ne constituent pas la configuration réseau de toytoy.

## Exécuté

| Fichier | Résultat |
| --- | --- |
| `claude-tests-reproduced.txt` | 12 tests initiaux reproduits avant correctif |
| `before.txt` | Neuf sondes : exceptions URL, contrôles retirés, port 0, Unicode, DNS implicite/avec zone, politique mutable, NAT64 local, consommation DNS non bornée |
| `policy-tests.txt` | 30 tests réussis : 12 initiaux et 18 nouveaux tests de frontière |
| `core-tests.txt` | 227 tests découverts, **221 réussis**, 6 intégrations opt-in sautées |
| `memory-tests.txt` | Ces **6 intégrations** exécutées séparément, toutes réussies |
| `demo.jsonl` / `demo-human.txt` | Huit décisions attendues vérifiées, JSON pur et présentation Eidolon |

Deux attentes historiques ont été adaptées au contrat `/2` : le préfixe NAT64
local /48 est refusé intégralement ; le budget de redirections est fixé dès
la décision initiale. Les sondes avant correctif restent conservées.

Depuis `eidolon-core/` :

```sh
PYTHONPATH=src:. python -m unittest tests.test_egress tests.test_egress_boundaries -v
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
PYTHONPATH=src:. python -m examples.web_policy_demo
PYTHONPATH=src:. python -m examples.web_policy_demo --format human
```

Mémoire réelle sur copie isolée `7d99ded07b7e10aa8029655ce4a939af6e0a6c44`,
dépôt inchangé, corpus temporaires synthétiques préparés via services coordonnés :

```sh
EIDOLON_MEMORY_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="src:.:$EIDOLON_MEMORY_SOURCE" \
  python -m unittest tests.test_memory_engine -v
```

EIDOLON_MEMORY_SOURCE est le chemin de la copie isolée, dépendances du moteur
installées comme dans le README. Aucun corpus utilisateur.

## Garantie mesurée et limites

Exclusions configurées contrôlées sur IP littérale, DNS, réponse mixte,
redirection, IPv4 encapsulée et préfixe IPv6 extérieur. Configuration et manifeste
indépendants des listes mutables d'origine. Générateur DNS infini arrêté après
33 adresses pour refuser une réponse de plus de 32. Aucun socket du parcours
politique : tests avec `socket` et résolution système interdits.

Cette borne ne tue pas un résolveur qui bloque avant de rendre un élément.
Aucun DNS réel, HTTP, TLS, firewall, VPN, modèle, GPU ou VM testé. La politique
reste non raccordée au runtime et ne prouve aucune exécution d'outil. Une IP
publique du foyer non inventoriée, une traduction ou une route particulière ne
sont pas reconnues automatiquement. Le futur transport devra respecter la
sélection d'IP et les permissions, et la recette réseau appliquer C-D08.

[Contrat et sources officielles consultées](../../../EGRESS-POLICY.md).
