# G284 — tunnel automatique du lanceur Windows

Demande toytoy du 17 octobre 2026, 08 h 10 Europe/Paris : ne plus lancer le tunnel manuellement.

Base distante a94f851d3ec91d2a4d7e6e7e8cb9ed6dc7a6e017. Lot Codex : module desktop/windows/eidolon-auto-tunnel.ps1, appel depuis eidolon-open.ps1, tests Windows et paquet G284. Lanceur C# et client Tauri conserves.

Avant lecture/transmission de l'appairage au client, le lanceur garantit la presence du tunnel. Il reutilise uniquement un ecouteur 127.0.0.1 dont le proprietaire est le ssh.exe attendu, avec transfert -L et destination concordants. Il refuse un autre programme, port, serveur, utilisateur (sensible a la casse), ou une ecoute large. Les appels concurrents passent par un mutex local.

Un nouvel SSH est tente en mode BatchMode=yes et fenetre cachee pendant 12 s au plus. A defaut, une fenetre d'authentification est ouverte automatiquement pendant 120 s au plus. Les processus crees qui echouent sont arretes ; un processus preexistant n'est jamais arrete. Le tunnel pret est conserve pour les relances.

StrictHostKeyChecking=yes et HostKeyAlgorithms=ssh-ed25519 conserves. Liaison locale uniquement, keepalive et ExitOnForwardFailure actifs. Aucun mot de passe conserve, aucune nouvelle cle ni modification authorized_keys/known_hosts. Le mode silencieux suppose une cle/agent deja configure. L'absence de mot de passe repetitif n'est donc pas garantie par ce lot.

Recette Windows : test d'appairage DPAPI, proprietaire SSH/destination incorrects refuses, vrai port local d'un autre programme refuse ; doublures de processus pour reutilisation, succes silencieux, repli interactif et nettoyage sur echec. Aucune connexion reelle ni donnee personnelle dans ces tests. La connexion au serveur depuis le PC utilisateur reste a valider sur place.

## Livraison et preuves

Les nouvelles sondes Windows et les tests DPAPI/JavaScript ont reussi a l'etape 4 du workflow `39009211651`, job `117327888602`, commit `2002bb34c6192b70c1d05a0ce55591d9d3e545e6`. Le premier essai avait echoue dans la doublure Start-Process, corrigee avec les memes types string/string[] que la commande Windows. La recompilation globale du client est encore en cours au moment de cette livraison.

Le ZIP livre reutilise les deux binaires G283 inchanges (sources natives non modifiees), deja compiles et testes par le workflow `39007775750`. Eidolon.exe SHA-256 `706abf320735f44e78c1ebfda8e1eb027bd1d6bec1820c6610b72ab87af343d6` ; client Tauri `b7b98400d21dafa4ecfbe1ce9812d794b64ccd55803e30160dee4ab7f59097b5`. Les deux scripts runtime et le guide proviennent du lot G284 publie ; integrite ZIP et empreintes du manifeste controlees.

ZIP utilisateur livre `eidolon-pc-g284.zip`, 2 737 177 octets, SHA-256 `6fbc6b32f5d409d6eaa87392ff1ed3d675f99e12270c8bc8c3be6e9ca481e842`. Un ZIP produit par la recompilation CI pourra avoir une autre empreinte ; ne pas le confondre avec celui-ci. Aucun vrai SSH ni test du PC de toytoy n'est presume.
