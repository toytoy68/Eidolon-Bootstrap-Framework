# Recette bêta « observateur » — serveur Debian et PC Windows

Claude, 06/10/2026. Fiche [C-TASK-G035](../collaboration/tasks/C-TASK-G035.md).
Basée sur le code publié : API `http_api` (C-009a, diagnostic C-009c
`a8ae8fa`) et client [desktop/connected](../desktop/connected/README.md)
(G031). Références : [HTTP-READ-API.md](HTTP-READ-API.md),
[HTTP-PREFLIGHT.md](HTTP-PREFLIGHT.md), [BETA-SERVER-PC.md](BETA-SERVER-PC.md).

## Ce que cette recette teste, et ce qu'elle ne teste pas

**Testé** : depuis le navigateur du PC, par un tunnel SSH, **consulter** les
missions d'un état Core **synthétique** du serveur ; voir une modification
faite sur le serveur ; survivre à une coupure du tunnel ou à un redémarrage du
serveur sans mélange ni action.

**Pas testé ici** : le chat et le modèle réel, les commandes à distance
(approuver, lancer, annuler), la mémoire, le Web, le NAS, les fichiers
Windows, le GPU, et les scripts Bootstrap. La page n'a **aucun bouton
d'action**.

Les instructions ne modifient **ni pare-feu, ni VPN, ni configuration SSH,
ni service systemd, ni GPU**. Le serveur écoute sur `127.0.0.1` seulement.
Le port 8765 n'est jamais ouvert sur le réseau : seul le tunnel y mène.

## Prérequis

| Où | Prérequis | Vérifier |
| --- | --- | --- |
| Serveur | accès SSH **déjà** fonctionnel depuis le PC | `ssh <utilisateur>@<serveur>` ouvre une session |
| Serveur | Python 3.11 ou plus récent (Debian 13 : 3.13) | `python3 --version` |
| Serveur | `git` et accès en lecture au dépôt | `git --version` |
| Serveur | port 8765 libre en local | `ss -ltn \| grep 8765` ne renvoie rien |
| Serveur (facultatif) | Node.js, seulement pour `build.js --check` | `node --version` |
| PC | Windows 10/11 avec le client OpenSSH | PowerShell : `ssh -V` |
| PC | Edge ou Chrome à jour | — |
| PC | port 8765 libre | PowerShell : `Get-NetTCPConnection -LocalPort 8765 -State Listen` ne renvoie rien |

Si 8765 est pris d'un côté, choisir un autre port, **le même aux deux
extrémités** : le serveur vérifie `Host: 127.0.0.1:<port>`.

## Étapes serveur (session SSH 1)

**S1 — Récupérer le code.** Dossier séparé ; rien n'est installé.

```sh
git clone --branch feat/eidolon-core-v0.1 https://github.com/toytoy68/Eidolon-Bootstrap-Framework.git ~/eidolon-recette
cd ~/eidolon-recette/eidolon-core
git log -1 --format=%H        # noter ce commit dans la checklist
```

**S2 — État synthétique et jeton privé.** Le jeton n'est jamais affiché par
ces commandes.

```sh
export PYTHONPATH=src
BETA="$HOME/eidolon-beta"
mkdir -p "$BETA"
python3 -m eidolon_core --state "$BETA/state" demo > "$BETA/demo.json"
python3 -c 'import os,secrets,sys; fd=os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.write(fd,(secrets.token_urlsafe(32)+"\n").encode()); os.close(fd)' "$BETA/read-token"
```

**S3 — Diagnostic sans démarrer.** Attendu : quatre `[OK]`, code 0. Un PASS
ne qualifie pas la bêta.

```sh
python3 -m eidolon_core.http_api --state "$BETA/state" --token-file "$BETA/read-token" \
  --web-root desktop/connected --port 8765 --check --format human
node desktop/connected/build.js --check     # facultatif : "app.js up to date"
```

**S4 — Lancement au premier plan.** Laisser cette session ouverte.

```sh
python3 -m eidolon_core.http_api --state "$BETA/state" --token-file "$BETA/read-token" \
  --web-root desktop/connected --port 8765
```

**S5 — Contrôle sur le serveur** (session SSH 2, même dossier, mêmes
`PYTHONPATH` et `BETA`). Attendu : `page : 200`, `health :
eidolon-http-read/1 read_only authorizes_execution = False`,
`sans jeton : 401`, puis une seule ligne `127.0.0.1:8765`.

```sh
python3 - "$BETA/read-token" <<'PY'
import json, sys, urllib.error, urllib.request
base = "http://127.0.0.1:8765"
print("page :", urllib.request.urlopen(base + "/").status)
token = open(sys.argv[1]).read().strip()
health = json.load(urllib.request.urlopen(urllib.request.Request(base + "/v1/health", headers={"Authorization": "Bearer " + token})))
print("health :", health["protocol"], health["mode"], "authorizes_execution =", health["authorizes_execution"])
try:
    urllib.request.urlopen(base + "/v1/health")
except urllib.error.HTTPError as exc:
    print("sans jeton :", exc.code)
PY
ss -ltn | grep 8765
```

**S6 — Modifier l'état pendant la consultation** (session 2, pendant W5).

```sh
python3 -m eidolon_core --state "$BETA/state" create "mission de recette synthétique"
# noter l'identifiant m-… affiché, puis :
python3 -m eidolon_core --state "$BETA/state" cancel m-IDENTIFIANT
```

**S7 — Redémarrage du serveur** (pendant W7) : Ctrl+C dans la session 1,
puis relancer la commande S4.

**S8 — Arrêt.** Ctrl+C dans la session 1. Si le serveur a été lancé en
arrière-plan (`&`, script), Ctrl+C et `kill -INT` **n'ont aucun effet** :
utiliser `kill <PID>`.

**S9 — Retrait.** Rien d'autre n'a été créé ; aucun service à retirer.

```sh
rm -rf "$HOME/eidolon-beta"
rm -rf "$HOME/eidolon-recette"     # si le code n'est plus utile
```

## Étapes PC Windows (PowerShell)

**W1 — Tunnel.** Laisser la fenêtre ouverte. À la première connexion, SSH
demande de confirmer l'empreinte du serveur : la comparer, ne pas l'accepter
à l'aveugle.

```text
ssh -N -L 127.0.0.1:8765:127.0.0.1:8765 <utilisateur>@<serveur>
```

**W2 — Ouvrir** `http://127.0.0.1:8765` dans Edge ou Chrome. Préférer
`127.0.0.1` à `localhost`. Attendu : « Eidolon Core — Consultation seule »,
« Non connecté. »

**W3 — Jeton.** Dans la session SSH 2 : `cat "$BETA/read-token"`. Copier la
valeur, la coller dans « Jeton de lecture », puis « Se connecter ». Attendu :
« Connecté en lecture seule », liste « Capture entièrement lue (1) », champ
vidé. Ne coller le jeton nulle part ailleurs.

**W4 — Détail.** Cliquer la mission. Attendu : « Réussie — résultat daté »,
statut SUCCEEDED / DONE, date de capture.

**W5 — Modification vue.** Après S6 (création), cliquer « Relire la liste » :
2 missions. Sélectionner la nouvelle, faire l'annulation de S6, puis
« Actualiser ». Attendu : « Annulée », événements `CANCEL_REQUESTED` et
`CANCELLED`.

**W6 — Coupure du tunnel.** Ctrl+C dans la fenêtre du tunnel, puis
« Actualiser ». Attendu : « Serveur injoignable », missions toujours
affichées et marquées périmées. Relancer W1, puis cliquer « Se connecter »
avec le même jeton (à recoller si la page a été rechargée). Attendu :
reconnexion sans message « Autre base ».

**W7 — Redémarrage du serveur** (S7), puis « Se connecter ». Attendu : mêmes
missions, aucun message « Autre base ».

**W8 — Mauvais jeton.** « Se déconnecter », coller une valeur fausse de même
longueur, « Se connecter ». Attendu : « Jeton refusé ».

**W9 — Rechargement (F5).** Attendu : « Non connecté » ; le jeton n'est plus
connu de la page.

**W10 — Fin.** « Se déconnecter », Ctrl+C dans le tunnel, puis S8 et S9.

## Checklist d'acceptation (toytoy)

| # | Point | Conteneur Claude, 06/10 | VM / Windows |
| --- | --- | --- | --- |
| 1 | S2–S3 : état, jeton 0600, diagnostic 4 × OK | PASS (Python 3.11) | À EXÉCUTER SUR VM |
| 2 | S4–S5 : page 200, health, 401 sans jeton, écoute 127.0.0.1 seulement | PASS | À EXÉCUTER SUR VM |
| 3 | S8–S9 : arrêt, jeton absent du journal, retrait complet | PASS (arrêt par `kill`) | À EXÉCUTER SUR VM |
| 4 | W1 : tunnel établi | non testable (pas de SSH) | À EXÉCUTER SUR WINDOWS |
| 5 | W2–W4 : page, connexion, liste, détail | PASS en Chromium Linux, sans tunnel (G031) | À EXÉCUTER SUR WINDOWS |
| 6 | W5 : création et annulation vues après relecture | PASS en Chromium Linux (G031) | À EXÉCUTER SUR WINDOWS |
| 7 | W6 : coupure puis reprise sans mélange | PASS, serveur arrêté au lieu du tunnel (G031) | À EXÉCUTER SUR WINDOWS |
| 8 | W7 : redémarrage serveur, même base | PASS en Node (G031) | À EXÉCUTER SUR VM + WINDOWS |
| 9 | W8–W9 : mauvais jeton, oubli au rechargement | mauvais jeton : PASS en Node (G031) ; rechargement : non testé | À EXÉCUTER SUR WINDOWS |
| 10 | Aucune action possible, aucune donnée hors de l'état synthétique | PASS (G031, G034) | à constater |

La bêta n'est **pas** qualifiée tant que les colonnes VM et Windows ne sont pas
remplies par toytoy. Le commit testé est noté à S1.

## Blocages et risques connus

1. **Lenteur ou blocage (D-G034-1)**. Le serveur traite une requête à la
   fois, avec un délai de 3 s par lecture.
   - Une connexion restée ouverte (préconnexion du navigateur, tunnel) peut
     retarder une réponse d'environ 3 s.
   - Un client local lent peut bloquer la consultation.
   - Si la page affiche « injoignable » alors que le tunnel tourne, attendre
     puis « Actualiser ».
2. **Arrêt** : un serveur lancé en arrière-plan ignore Ctrl+C et
   `kill -INT` ; utiliser `kill <PID>`. Vérifié dans le conteneur.
3. **Accès au dépôt** : si le dépôt est privé, `git clone` demande une
   authentification GitHub sur le serveur. Ne pas mettre de jeton GitHub dans
   l'URL ni dans un fichier du dépôt.
4. **Python 3.13** (Debian 13) : non essayé ici, seulement 3.11.
5. **Branche** : les correctifs G032–G035 sont publiés sur la branche Claude
   tant que Codex ne les a pas intégrés à `feat/eidolon-core-v0.1`. Le
   client et l'API utilisés par cette recette y sont déjà.
6. **Pas de TLS** : le tunnel SSH protège le trajet. Ne jamais exposer 8765 sur
   le réseau ni ouvrir de port dans le pare-feu pour cette recette.

[Preuves de la séquence serveur exécutée dans le conteneur](validation/2026-10-06/claude-g035/README.md).
