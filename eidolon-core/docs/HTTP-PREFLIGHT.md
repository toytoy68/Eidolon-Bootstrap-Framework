# Diagnostic local avant démarrage — C-009c

Codex/GPT, 06/10/2026. Le diagnostic réutilise les validateurs du serveur de
consultation. Il inspecte des fichiers existants, sans créer de base ou de jeton,
ni démarrer un serveur. Compatible avec Python 3.11+ sur le serveur Linux.

Depuis eidolon-core/, avec les mêmes paramètres que le lancement HTTP :

```sh
PYTHONPATH=src python -m eidolon_core.http_api \
  --state /chemin/etat-existant --token-file /chemin/jeton-prive \
  --web-root desktop/connected --port 8765 --check --format human
```

Pour un rapport JSON exploitable par G035/G040, omettre --format ou choisir
--format json. Sans --check, le lancement existant reste inchangé ; --format
est réservé au diagnostic. Aucun token ne doit être passé sur la ligne de
commande : seul le chemin du fichier est demandé.

## Contrat

`protocol: eidolon-http-preflight/1`, `status: PASS|FAIL`, liste `checks` avec
`name`, `status: PASS|FAIL|SKIP` et `code`. Code de sortie 0 si tous les contrôles
demandés passent, 2 si au moins un échoue. Le client non demandé est SKIP ; un
PASS sans web-root signifie que le serveur pourra proposer l’API seule sous
réserve des autres conditions de démarrage, pas une interface disponible.

Les indicateurs `server_started`, `port_availability_checked`,
`client_browser_tested`, `full_database_audit`, `authorizes_execution` restent
false. Aucun chemin, contenu de mission, identité Store, token ni empreinte de
token n’est exporté. Les erreurs ne bloquent pas les autres contrôles.

| Contrôle | Vérification | Principaux codes d’échec |
| --- | --- | --- |
| token | Fichier régulier privé appartenant à l’utilisateur, pas de lien final, format borné | TOKEN_UNAVAILABLE, TOKEN_FILE_NOT_PRIVATE, INVALID_TOKEN |
| state | Base existante SQLite ro, version/tables/identité reconnues, pas de garde récupération | STATE_NOT_FOUND, STATE_UNAVAILABLE, UNSUPPORTED_READ_SCHEMA, INVALID_STORE_ID, RECOVERY_REVIEW_ONLY |
| client | Trois assets fixes lisibles, pas de lien final, taille bornée | INVALID_WEB_ROOT, ASSET_TOO_LARGE |
| port | Entier de 0 à 65535 | INVALID_PORT |

`NO_WEB_ROOT` explicite l’absence volontaire du client. Le mode humain précise
les erreurs et réutilise la présentation ECT. Une erreur de syntaxe des arguments
reste une erreur argparse sur stderr, avant tout rapport de diagnostic.

## Limites et suite

Le diagnostic ne réserve pas les fichiers : ils peuvent changer ensuite. Le
serveur refait ses contrôles au démarrage. Aucun port occupé n’est détecté ;
0 reste le port éphémère destiné aux tests. Pour le tunnel PC, employer un port
fixe identique aux deux extrémités comme décrit dans HTTP-READ-API.md.

Le contrôle des assets ne vérifie ni leur fonctionnement dans le navigateur
ni la cohérence du bundle généré : `node desktop/connected/build.js --check`
reste distinct. Le contrôle SQLite n’examine pas toutes les missions ni tous
les reçus ; ce n’est pas une vérification intégrale du schéma ou de l’intégrité.
Les éventuels fichiers auxiliaires SQLite WAL/SHM dépendent du mode du producteur.
Aucune migration, écriture métier, réparation, génération de token ou exécution
d’outil n’est réalisée. Rien ne valide ici Debian/Windows, SSH ou les modèles.

Après résolution locale des erreurs, retirer --check/--format pour démarrer
le serveur, puis appliquer la recette bêta. Un PASS n’est pas une autorisation
de commande ni une qualification de la bêta.

[Preuves](validation/2026-10-06/codex-preflight/README.md).
