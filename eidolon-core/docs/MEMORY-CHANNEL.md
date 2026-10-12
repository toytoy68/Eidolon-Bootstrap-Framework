# Canal de lecture Memory → dashboard Core (G166)

Auteur : Claude. Date : 12/10/2026, Europe/Paris.

**Statut** : conçu, codé et testé en conteneur. **Non provisionné** : Codex
l'installe après revue. Tant que la recette réelle n'est pas faite, Memory
reste dans `not_covered` et la page affiche « Non surveillé ».

## 1. But et limites

Montrer dans le dashboard le statut DARME de Memory : badge, sources,
fraîcheur et mesures `eidolon-machine/1`. C'est le même contenu que pour
Core.

Interdits :
- toute clé d'administration côté Core ou côté page ;
- toute commande choisie par le navigateur ;
- tout accès en écriture à Memory.

## 2. Schéma

```
navigateur ──(clé de conversation)──► Core 8767 ──relais──► eidolon-monitor 8768 (compte toytoy)
                                                                 │ ssh, arguments FIXES
                                                                 ▼
                                    Memory sshd ── compte eidolon-monitor-feed ── ForceCommand
                                                                 │ STATUS\n
                                                                 ▼
                                                 /run/eidolon-darme/status.sock (eidolon-darme)
```

## 3. Garanties

| Risque | Parade |
| --- | --- |
| Le navigateur influence la commande | Aucune entrée : la route GET `/v1/monitor/status` n'accepte ni paramètre ni corps. Hôte, utilisateur, port, clé et `known_hosts` viennent du fichier privé `monitor.json` (0600), validés au démarrage. |
| La clé de Core sert à autre chose | Côté Memory : `ForceCommand` et `restrict` dans `authorized_keys`, plus `from="<IP_CORE>"`. Ni terminal, ni transfert, ni agent, ni X11, ni tunnel. Toute commande envoyée par le client est **refusée** (code 2). |
| Usurpation de Memory | `StrictHostKeyChecking=yes` sur un `known_hosts` **dédié**, sans fichier global, sans configuration (`-F /dev/null`) |
| Ce que ssh pourrait lire de la machine | `IdentitiesOnly`, `IdentityAgent=none`, `ControlPath=none`, `PermitLocalCommand=no`, `HOME=/nonexistent`, environnement vidé |
| Faux serveur DARME sur Memory | La commande forcée vérifie le compte du socket (`SO_PEERCRED` = `eidolon-darme`) |
| Réponse énorme ou lente | 64 Kio et 6 s au plus côté Core (le groupe de processus est tué) ; 64 Kio et 2 s côté Memory |
| Charge sur Memory | Au plus **une** connexion SSH par 10 s, quel que soit le nombre d'onglets |
| Fuite d'information | Erreurs génériques seulement (`UNAVAILABLE`, `TIMEOUT`…), jamais le texte d'erreur de ssh. La liste blanche de `summarize` s'applique comme pour Core. |
| Données périmées | Même règle que Core : `generated_at` et `sampled_at` contrôlés ; au-delà, « Statut périmé » ou « Mesures PÉRIMÉES » |

**Pourquoi pas un transfert de socket par le tunnel existant** : un
`StreamLocalForward` rendrait le socket DARME de Memory joignable par tout
processus de Core qui accède au fichier relayé. La commande forcée ne permet
qu'**une** lecture, d'**un** seul format, par **une** seule clé.

## 4. Fichiers prêts

| Fichier | Rôle |
| --- | --- |
| [monitor_remote.py](../src/eidolon_core/monitor_remote.py) | Lecteur côté Core : validation de la configuration, ligne de commande fixe, bornes |
| [monitor_service.py](../src/eidolon_core/monitor_service.py) | Une machine accepte `"ssh": {...}` à la place de `"socket"` ; une lecture par 10 s au plus |
| [darme_status_feed.py](../deployment/memory-feed/darme_status_feed.py) | Commande forcée sur Memory |
| [sshd-eidolon-monitor-feed.conf](../deployment/memory-feed/sshd-eidolon-monitor-feed.conf) | Bloc `Match User` de sshd |
| [authorized_keys.template](../deployment/memory-feed/authorized_keys.template) | Une ligne `restrict,from=…,command=…` |
| [test_monitor_remote.py](../tests/test_monitor_remote.py) | 6 tests : arguments fixes, bornes, refus, cache 10 s, commande forcée |

## 5. Provisionnement (Codex, après revue)

Les adresses IP et les clés restent **sur les VM**, jamais dans Git.

**Sur Memory** (root) :
1. Créer le compte, verrouillé, sans dossier personnel :
   ```sh
   useradd --system --shell /bin/sh --home-dir /nonexistent --no-create-home eidolon-monitor-feed
   usermod -aG eidolon-darme eidolon-monitor-feed
   ```
   L'interpréteur `/bin/sh` est nécessaire à sshd pour lancer la
   `ForceCommand` ; `nologin` l'empêcherait.
2. Installer la commande forcée, root, 0755 :
   ```sh
   install -m 0755 deployment/memory-feed/darme_status_feed.py /usr/local/lib/eidolon/darme-status-feed
   ```
3. Installer le bloc sshd dans `/etc/ssh/sshd_config.d/`, puis lancer
   `sshd -t` **avant** `systemctl reload ssh`.
4. Remplir `/etc/ssh/eidolon-monitor-feed/authorized_keys` à partir du
   modèle (root:root 0644) : IP de Core et clé publique de l'étape Core 1.

**Sur Core** (compte toytoy) :
1. Générer la clé dédiée :
   ```sh
   ssh-keygen -t ed25519 -N '' -C eidolon-monitor@core -f ~/eidolon-monitor/memory_feed_ed25519
   ```
   La clé privée doit être en 0600.
2. Épingler l'hôte : obtenir l'empreinte de Memory par un canal déjà sûr
   (console de la VM), puis écrire `~/eidolon-monitor/memory_known_hosts`
   (0644). **Pas** de `ssh-keyscan` aveugle.
3. Ajouter Memory dans `monitor.json` :
   ```json
   {"id": "memory", "label": "Memory", "ssh": {"host": "<IP_MEMORY>", "user": "eidolon-monitor-feed",
    "key": "/home/toytoy/eidolon-monitor/memory_feed_ed25519",
    "known_hosts": "/home/toytoy/eidolon-monitor/memory_known_hosts"}}
   ```
   Retirer « Memory » de `not_covered`.
4. Ouvrir le réseau de l'unité vers Memory seulement, par un drop-in local
   `/etc/systemd/system/eidolon-monitor.service.d/memory.conf` :
   ```ini
   [Service]
   IPAddressAllow=<IP_MEMORY>
   ```
   Puis lancer `daemon-reload` et `restart eidolon-monitor`.

**Recette réelle à publier** :
1. `--check` montre `memory: ok`.
2. La page affiche Memory avec badge, fraîcheur et mesures.
3. `ssh … eidolon-monitor-feed@memory id` répond
   `FEED_TAKES_NO_COMMAND`.
4. Une demande de terminal (`-t`) ou de transfert (`-L`) est refusée.
5. Une clé ou une empreinte d'hôte modifiée donne `UNAVAILABLE`.
6. Si DARME est arrêté sur Memory, la page affiche « Indisponible ».

**Retour arrière** :
1. Retirer la ligne de `authorized_keys`, puis recharger sshd.
2. Remettre Memory dans `not_covered`.
3. Supprimer le drop-in réseau.

## 6. Non fait

- Aucun provisionnement ni essai sur les vraies VM.
- La rotation de la clé suit la règle générale : jamais implicite.
- Le GPU de VM101 n'est pas couvert par ce canal (G169).
