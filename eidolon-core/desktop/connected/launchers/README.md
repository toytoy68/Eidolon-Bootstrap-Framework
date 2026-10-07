# Lanceur candidat du tunnel SSH (PC Windows) — C-TASK-G040

Auteur : Claude, 06/10/2026. **Candidat de recette**, pas l'application
Windows d'Eidolon. Le choix du cadre de cette application (Tauri, Electron…)
reste ouvert. Ce lanceur complète la [recette bêta](../../../docs/BETA-ACCEPTANCE.md)
(étapes W1 à W10) sans la remplacer.

`eidolon-tunnel.ps1` ouvre ou arrête **un** tunnel SSH local :
`127.0.0.1:<Port>` sur le PC vers `127.0.0.1:<Port>` sur le serveur.

## Ce qu'il fait et ne fait pas

| Fait | Ne fait jamais |
| --- | --- |
| Vérifie la présence de `ssh.exe` et que le port local est libre | installer quoi que ce soit, ni OpenSSH ni module |
| Mode **aperçu par défaut** : affiche les commandes prévues, sans connexion | créer une clé, lire ou afficher un jeton ou un mot de passe |
| `-Connect` : diagnostic distant facultatif (`http_api --check`), puis tunnel dans une **nouvelle fenêtre** pour répondre à SSH | désactiver la vérification de la clé d'hôte SSH, ni toucher à `known_hosts` |
| Attend que le port local écoute (au plus 120 s) puis affiche l'URL | ouvrir le port sur le réseau : écoute sur `127.0.0.1` seulement |
| `-Stop` : arrête **seulement** le `ssh` qu'il a lancé (même PID, même date de démarrage) | arrêter le serveur Core ou un autre processus ; modifier pare-feu, VPN ou services |

Le serveur Core doit déjà tourner (recette, étape S4). Le lanceur ne le
démarre pas.

## Utilisation (PowerShell, dans ce dossier)

```powershell
# 1. Aperçu : rien n'est connecté
.\eidolon-tunnel.ps1 -Server <serveur> -User <utilisateur> -Port 8765

# 2. Connexion, avec le diagnostic C-009c sur le serveur (chemins relatifs au dossier personnel distant)
.\eidolon-tunnel.ps1 -Server <serveur> -User <utilisateur> -Port 8765 -Connect -OpenBrowser `
  -RemoteCore eidolon-recette/eidolon-core -RemoteState eidolon-beta/state -RemoteTokenFile eidolon-beta/read-token

# 3. Arrêt du seul tunnel lancé par ce script pour ce port
.\eidolon-tunnel.ps1 -Stop -Port 8765
```

- Le **port** est obligatoire, entre 1024 et 65535. Il doit être **le même
  que `--port` sur le serveur**, car le serveur vérifie
  `Host: 127.0.0.1:<port>`.
- Le nom du serveur, l'utilisateur et les chemins distants sont filtrés
  strictement. Une valeur commençant par `-` ou contenant `;`, une espace ou
  des guillemets est refusée **avant** tout appel à `ssh`.
- Le jeton se lit sur le serveur, puis se colle dans la page. Le script ne
  le lit jamais.
- L'enregistrement du tunnel (PID, port, date de démarrage) est écrit dans
  `%LOCALAPPDATA%\Eidolon\beta-tunnel\tunnel-<port>.json`. C'est le seul
  fichier créé, et `-Stop` le retire.
- Si Windows refuse de lancer un script non signé, l'exécuter pour cette
  seule session avec `powershell -ExecutionPolicy Bypass -File
  .\eidolon-tunnel.ps1 …`. Le script ne modifie pas la politique
  d'exécution.

## Vérifications

- [Contrôles statiques](../tests/launcher.test.js) : 6 tests Node sur le texte
  du script (liaison 127.0.0.1, `--` avant la destination, aucune option qui
  affaiblit SSH, arrêt limité à son processus, aucun jeton lu).
- Exécution réelle avec **PowerShell 7.4.6 sous Linux** et un `ssh.exe`
  **simulé** :
  [preuves](../../../docs/validation/2026-10-06/claude-g040/README.md).
- **Non exécuté** : Windows, Windows PowerShell 5.1, vrai `ssh.exe`, vraie
  connexion, invite d'empreinte ou de mot de passe, navigateur Windows.

## Correctif Codex C-010e — 07/10/2026

Les chemins relatifs et `~/...` du diagnostic sont ancrés dans le dossier
personnel distant, y compris après le `cd` vers RemoteCore. Les chemins
absolus sont conservés ; `~autre-utilisateur` est refusé. Auparavant retirer
`~/` faisait chercher état/jeton dans le dossier Core. Contrôles statiques ici ;
PowerShell/Windows et SSH réels restent à exécuter.
