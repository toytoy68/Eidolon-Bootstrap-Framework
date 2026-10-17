# G284 — tunnel automatique du lanceur Windows

Demande toytoy du 17 octobre 2026, 08 h 10 Europe/Paris : ne plus lancer le tunnel manuellement.

Base distante a94f851d3ec91d2a4d7e6e7e8cb9ed6dc7a6e017. Lot Codex : module desktop/windows/eidolon-auto-tunnel.ps1, appel depuis eidolon-open.ps1, tests Windows et paquet G284. Lanceur C# et client Tauri conserves.

Avant lecture/transmission de l'appairage au client, le lanceur garantit la presence du tunnel. Il reutilise uniquement un ecouteur 127.0.0.1 dont le proprietaire est le ssh.exe attendu, avec transfert -L et destination concordants. Il refuse un autre programme, port, serveur, utilisateur (sensible a la casse), ou une ecoute large. Les appels concurrents passent par un mutex local.

Un nouvel SSH est tente en mode BatchMode=yes et fenetre cachee pendant 12 s au plus. A defaut, une fenetre d'authentification est ouverte automatiquement pendant 120 s au plus. Les processus crees qui echouent sont arretes ; un processus preexistant n'est jamais arrete. Le tunnel pret est conserve pour les relances.

StrictHostKeyChecking=yes et HostKeyAlgorithms=ssh-ed25519 conserves. Liaison locale uniquement, keepalive et ExitOnForwardFailure actifs. Aucun mot de passe conserve, aucune nouvelle cle ni modification authorized_keys/known_hosts. Le mode silencieux suppose une cle/agent deja configure. L'absence de mot de passe repetitif n'est donc pas garantie par ce lot.

Recette Windows : test d'appairage DPAPI, proprietaire SSH/destination incorrects refuses, vrai port local d'un autre programme refuse ; doublures de processus pour reutilisation, succes silencieux, repli interactif et nettoyage sur echec. Aucune connexion reelle ni donnee personnelle dans ces tests. La connexion au serveur depuis le PC utilisateur reste a valider sur place.
