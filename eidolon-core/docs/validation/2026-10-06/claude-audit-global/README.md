# Vérification globale du code livré — 06/10/2026

Auteur : Claude, à la demande de toytoy (« vérifier tout le code déjà livré »).
Base : `3ac96e6` (fusion de `origin/feat/eidolon-core-v0.1`, C-MSG-G035).
Nature : vérification transversale, **pas une certification**.

Ce lot ne modifie aucun code. Les installateurs n'ont été **ni exécutés ni
sourcés** (AGENTS.md) : seulement lus, et contrôlés sur des copies.

Environnement : Python 3.11.15, Node 22.22.0, Chromium via Playwright 1.56.1,
ruff, shellcheck 0.11. Linux, sans réseau sortant vers les sites testés.

## Ce qui a été exécuté

| Contrôle | Résultat | Preuve |
| --- | --- | --- |
| Suite Python Core complète | **455 tests, OK** (6 intégrations Memory Engine sautées) | [core-tests.txt](core-tests.txt) |
| Suite du prototype bureau (logique + Chromium) | **92/92** | [prototype-tests.txt](prototype-tests.txt) |
| Analyse statique Python (ruff : erreurs, bugs probables, sécurité) | aucune erreur de syntaxe ni nom indéfini dans `src/` ; 5 remarques mineures | [ruff.txt](ruff.txt) |
| Syntaxe JS du prototype (`node --check`) | tous les fichiers OK | — |
| Filtre de destinations Web (`egress.decide`) | 32 adresses spéciales et 16 URL piégées : toutes refusées sauf les 2 publiques témoins | [egress_probe.py](egress_probe.py) · [sortie](egress_probe-output.txt) |
| Installateurs Bootstrap 01/02/03 | **ne passent pas `bash -n` tels que versionnés** (voir I1) | [installers-check.txt](installers-check.txt) |
| Recherche de fuites dans Git (IP publiques, ports, secrets) | aucune IP publique personnelle ni secret | voir ci-dessous |

## Constats

### I1 — Installateurs en fins de ligne Windows (CRLF) : BLOQUANT pour un clone neuf

`git ls-files --eol` donne `i/crlf` pour `01-system.sh`, `02-nvidia.sh` et
`03-docker.sh`, versionnés ainsi depuis `b1b74b8` (« Add files via upload »).

- La ligne de lancement devient `#!/usr/bin/env bash\r`. Un `./01-system.sh`
  échoue avant de commencer.
- `bash 01-system.sh` échoue en erreur de syntaxe (`'{\r'`, ligne 142).

Converties en LF sur une copie, les trois passent `bash -n`. **shellcheck** ne
relève alors que des variables inutilisées (SC2034), aucun défaut de logique.

**Correctif proposé**, non appliqué car l'installateur est hors du périmètre
Core et n'a pas été exécuté :

- convertir les trois fichiers en LF ;
- ajouter un `.gitattributes` avec `*.sh text eol=lf`.

À faire valider par toytoy, qui a pu convertir ses copies localement lors de
son installation.

### I2 — `02-nvidia.sh` : modification des dépôts Debian non idempotente (P3)

Simulation de la commande `sed` **sur un fichier d'exemple**, jamais sur le
système :

- **Format une ligne** (`sources.list`), cas courant `main non-free-firmware` :
  - après un passage : `main contrib non-free non-free-firmware non-free-firmware` ;
  - après un second passage : les composants sont encore dupliqués.
- **Format deb822** (`debian.sources`) : l'expression n'accepte que la ligne
  exacte `Components: main`. Une ligne `Components: main non-free-firmware`
  n'est **pas** complétée : `non-free` manquerait pour `nvidia-driver`. Je n'ai
  pas vérifié le contenu exact qu'écrit l'installeur Debian 13 ; c'est une
  hypothèse à confirmer sur la machine.

**Proposition** : n'ajouter que les composants absents, sur les deux formats.

### C1 — Core : statique, minime

- **B904** : trois `raise` sans `from` dans `egress.py`. Diagnostic seulement.
- **S310** : `urlopen` dans les adaptateurs Ollama et OpenAI. **Vérifié** : le
  schéma est limité à http(s), boucle locale par défaut, sans proxy ni
  redirection, et https obligatoire pour une clé hors boucle locale.
- **Tests** : 5 imports inutilisés.

Aucun défaut de comportement.

### C2 — Prototype : aucun HTML construit depuis les données

Recherche de concaténations brutes et d'`eval` : aucune donnée de serveur
n'est insérée autrement que par `textContent` ou `esc()`. Les tests de texte
hostile passent, et la CSP interdit le script en ligne et toute connexion.

### C3 — Fuites

Les seules IPv4 publiques versionnées sont :

- les résolveurs publics des installateurs et des tests (1.1.1.1, 8.8.8.8,
  9.9.9.9) ;
- `example.com` (93.184.x, dans mes sondes) ;
- 224.0.0.1 (cas de test).

Aucun port de service personnel, aucune clé (`sk-`, `ghp_`, `AKIA`, motifs
`api_key=`/`token=`). Les adresses du réseau local de toytoy, dans
`01-system.sh`, sont privées et viennent de son propre envoi.

## Ce qui n'est pas couvert

- **Moteur mémoire réel** (intégrations sautées), **modèles réels**,
  **Windows**, **V100** et **réseau réel**.
- **`worker.py` et adaptateurs mémoire** : pas relus ligne à ligne ; ils sont
  couverts par la suite existante et les revues G008/G011/G015/G020.
- Les correctifs `3f16d7d` (restauration) et `cd80be2` (pauses Web) sont
  **testés par la suite** ci-dessus. Leur contre-revue indépendante est l'objet
  de G022 et G024.
