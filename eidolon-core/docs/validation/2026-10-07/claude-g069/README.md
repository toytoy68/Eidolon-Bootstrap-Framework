# C-TASK-G069 — Recette indépendante du paquet installé

Claude, 08/10/2026. Commit examiné : `95af6fa81b1d03d753d6b71bffb72034ee5b9331`.
Archive bêta reproductible : `sha256 a8531b2e881f52e5c2a032f3c3e5d4780f669b517a06ce4956b55782bf831a9a`
(89 fichiers, 251 376 octets).

```sh
NODE_PATH=<playwright> python3 recipe_g069.py <racine du dépôt> <sha du commit>   # → recipe.txt
```

**Résultat : PASS, 23/23 contrôles** ([recipe.txt](recipe.txt)).
Aucun processus restant après la recette. Dépôt inchangé (HEAD et `git status`).

## En quoi elle diffère de la recette Codex

Le paquet n'est **pas** construit depuis le checkout.

1. L'archive est construite deux fois depuis les objets Git
   (`build_beta_bundle.py`) : octets identiques.
2. Son manifeste est vérifié, puis l'archive est extraite dans un dossier temporaire.
3. La roue est construite depuis le projet **extrait**, hors réseau
   (`--no-index --no-build-isolation`), puis installée dans un venv jetable.
4. Chaque commande tourne depuis un dossier neutre, sans `PYTHONPATH`, avec
   des proxys factices sur 127.0.0.1:9 : toute sortie réseau échouerait.
5. Le client Desktop est servi depuis les fichiers **de l'archive**, puis ouvert
   dans Chromium.

## Contrôles

- Archive :
  - reproductible, manifeste vérifié (`authenticity_verified=false`) ;
  - `index.html`, `app.js` (identique au dépôt, panneau G066 présent) et `style.css`
    embarqués.
- Paquet :
  - importé depuis le venv, sans chemin du dépôt ;
  - 52 modules identiques à l'archive ;
  - aucune ressource Desktop dans le paquet Python ;
  - commande `eidolon-core` installée.
- CLI :
  - recherche synthétique puis reprise identique ;
  - `runtime-inspect` sans mutation ni donnée privée, avec `recorded_block` (G065) ;
  - copie de revue, et `recovery-inspect` d'une mission absente →
    `RECOVERY_MISSION_NOT_FOUND`, code 2 (G065).
- HTTP sur loopback :
  - jeu bêta `research-archives` et prédiagnostic PASS ;
  - `/`, `/app.js` et `/style.css` servis à l'octet près depuis l'archive ;
  - catalogue paginé C-030 (2 éléments sur 3, `has_more`) ;
  - aucune route vers un export brut (404).
- Chromium à 360 px : connexion, chargement des archives, 3 lignes, pas de
  défilement horizontal, aucune erreur de page.
- Planificateur local (LOCAL-MODEL-CLI) sur **faux** serveur Ollama en loopback :
  - `model-config-check` valide sans contacter le serveur ;
  - mission `demo` avec un seul appel `/api/chat` ; la reprise ne rappelle pas ;
  - une configuration rendue publique (0644) est refusée avant tout appel, sans
    chemin dans l'erreur.

## Blocage d'environnement documenté (pas un PASS caché)

Dans ce conteneur, `pip wheel --no-build-isolation` échoue avec
`AttributeError: install_layout` : c'est le setuptools 68 installé ici, avec sa
copie vendue de distutils. La commande de la recette Codex échoue de la même
façon ici. La recette le constate, puis reconstruit avec
`SETUPTOOLS_USE_DISTUTILS=stdlib`. Les sources sont les mêmes, et les 52 modules
installés sont vérifiés identiques.

Incident pendant le diagnostic, hors recette : un essai manuel avec un chemin
relatif sans `./` a fait télécharger par pip un paquet PyPI nommé « p » dans un
dossier temporaire. Rien n'a été installé ; le dossier a été supprimé. La recette
passe des chemins absolus et `--no-index`.

## Limites

- Linux, Python 3.11, Chromium headless, en root.
- Pas de VM, SSH réel, Windows, GPU ni modèle réel. Le planificateur est un faux
  serveur.
- `model-probe` (C-040) n'est pas couvert ici ; il revient à G075.
- La recette dépend de Node et Playwright pour l'étape navigateur. Leur absence
  serait notée BLOQUÉ, jamais PASS.
