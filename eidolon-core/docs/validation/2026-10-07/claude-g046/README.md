# G046 — contre-revue du lanceur SSH candidat après C-010e (`d9265fa`)

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G046](../../../../collaboration/tasks/C-TASK-G046.md).
Cible figée : `d9265fa`, `desktop/connected/launchers/eidolon-tunnel.ps1`.
Le script de Codex n'est pas modifié. Une **proposition** est jointe à part
([proposal-eidolon-tunnel.ps1](proposal-eidolon-tunnel.ps1) : 2 changements,
diff en tête de [run-proposal.txt](run-proposal.txt)).

## Méthode

- PowerShell 7.4.6 **sous Linux**, binaire officiel au SHA-256 vérifié, hors
  dépôt.
- Mode d'arguments `Standard` (PowerShell 7) et `Legacy`. `Legacy` reproduit
  la façon dont **Windows PowerShell 5.1** transmet les arguments à un
  programme natif.
- [Faux ssh](fake-ssh.py) :
  - il porte le nom de processus `ssh`, comme `ssh.exe` sous Windows (copie
    de python nommée `ssh`) ;
  - il écoute sur le port comme un tunnel ;
  - pour le diagnostic distant, il joint les arguments par des espaces et
    les exécute avec `bash -c`, comme un vrai serveur SSH ;
  - le dossier personnel distant **contient une espace**, et la copie figée
    de Core y est installée : le `--check` distant tourne vraiment.
- [Harnais](run-g046.sh) et [wrapper](wrapper.ps1). Processus et dossiers
  temporaires possédés, nettoyés à la fin. Aucun serveur réel, aucune
  configuration SSH.

Sorties : [cible `d9265fa`](run-d9265fa.txt), [proposition](run-proposal.txt).

## Résultats

| Cas | `d9265fa` | Proposition |
| --- | --- | --- |
| Chemins relatifs, mode Standard (PowerShell 7) | diagnostic réussi | réussi |
| Chemins `~/…`, mode Standard | réussi | réussi |
| Chemins relatifs ou `~/…`, mode **Legacy (≈ 5.1)**, dossier personnel avec une espace | **échec : `cd: too many arguments`** | réussi |
| Chemin absolu contenant une espace | refusé avant ssh (filtre) | refusé (inchangé) |
| `~autre/x`, `~root`, espace, `$HOME/x`, apostrophe, `-x` | refusés avant ssh | refusés |
| Relance pendant le tunnel | « port déjà utilisé » (code 2) | « tunnel déjà actif » (code 0) |
| `-Stop` sur le tunnel lancé (processus `ssh`) | **refuse, tunnel laissé vivant** | **arrêté** |
| `-Stop` quand le PID enregistré est un autre processus `ssh` (PID réutilisé) | refuse, processus intact | refuse, intact |

## G046-1 — guillemets doubles perdus sous Windows PowerShell 5.1 (P2 pour le PC)

C-010e entoure les chemins de guillemets doubles (`"$HOME/…"`). Sous
Windows PowerShell 5.1 (shell par défaut de Windows 10/11), un guillemet
double à l'intérieur d'un argument passé à `ssh.exe` n'est pas échappé : il
disparaît. Le serveur reçoit `cd $HOME/eidolon-recette/eidolon-core`, sans
guillemets. Cela marche tant que le dossier personnel distant n'a pas
d'espace, et casse sinon. Reproduit avec le mode `Legacy` de PowerShell 7 ;
**non vérifié sur un vrai Windows**.

**Proposition** : `~/'chemin'` au lieu de `"$HOME/chemin"`. Le tilde est
développé par le shell distant sans découpage en mots, et le reste est entre
guillemets simples, qui traversent 5.1 intacts. Les filtres d'entrée sont
inchangés : pas d'apostrophe, de `$` ni d'espace dans le chemin donné.

## G046-2 — `-Stop` refuse d'arrêter son propre tunnel sous Linux (P3)

Le contrôle d'identité compare **exactement** les dates de démarrage, en
ticks. Sous Linux, .NET recalcule cette date à chaque lecture (heure de
démarrage + jiffies) ; mesuré : 0,84 ms d'écart pour le même processus. Le
tunnel est alors jugé « réutilisé » : l'enregistrement est retiré et le
tunnel **reste vivant**. Sous Windows, la date vient du noyau et devrait être
exacte ; **non vérifié**.

**Proposition** : une tolérance de 2 s (`[math]::Abs(...) -gt 20000000`). Une
réutilisation de PID par un autre processus `ssh` dans ces 2 s est
improbable, et le contrôle du nom reste. Mesuré : le tunnel est arrêté, et un
processus `ssh` étranger reste intact.

## Limites

Rien n'a tourné sous Windows ni avec un vrai `ssh.exe`, ni avec une invite
d'empreinte ou de mot de passe. Le mode `Legacy` est une reproduction, pas
Windows PowerShell 5.1 lui-même.
