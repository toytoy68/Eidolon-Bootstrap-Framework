# DARME passif — déploiement du 12 octobre 2026

Service eidolon-darme.service installé et activé au démarrage sur **Core (192.168.1.101) et Memory (192.168.1.110)**. VM101 GPU /192.168.1.135 n'est pas couverte par une sonde locale. Code identique sur les deux machines : darme_service.py SHA256 cbdc26327fe12130096d48797d1cb644d8b9f0c43ac788fd13478992d921b857.

## Périmètre réellement actif

- Core : état systemd de core-api, gpu-tunnel, memory-tunnel.
- Memory : état systemd de memory-bridge et collaboration.
- Disque du journal local : alerte si libre <256 Mio ou <5 %.
- Sondage toutes les 10 secondes, fraîcheur 60 secondes, journal durable et projection bornée.
- Une panne devient une alerte persistante ; le retour à active ne vaut pas acquittement. Une panne déjà non acquittée n'est pas dupliquée au redémarrage.
- Aucun trafic capturé, aucune signature de malware, aucune vérification fonctionnelle HTTP des applications : active signifie seulement unité systemd active.
- Pas de conseiller LLM câblé ; advisor=fixed annonce le mode, sans endpoint de génération de conseil. Aucun appel GPU, remédiation ou acquittement distant.

Le badge actuel **gris / visibilité partielle** est volontaire : security-telemetry=false reste une source manquante. Le service ne certifie jamais que la machine est protégée. Tous les services surveillés et le disque répondent actuellement ; aucune alerte non acquittée. Un acquittement opérateur authentifié reste à construire ; aucune purge automatique.

## Isolation et interface

Compte système eidolon-darme, shell nologin, aucun groupe supplémentaire ni droit sudo ajouté. Code root non modifiable par le service sous /opt/eidolon-darme ; configuration root /etc/eidolon-darme/config.json. Journal /var/lib/eidolon-darme/journal.sqlite 0600. Répertoire d'état 0700 ; socket /run/eidolon-darme/status.sock 0660 dans répertoire 0750.

Protocole AF_UNIX privé : envoyer les octets STATUS\n, recevoir une ligne JSON. Aucun endpoint TCP/HTTP ni entrée d'événement externe. La confiance des sondes est locale : appels systemctl avec arguments fixes dans le processus dédié. Ed25519 et séquences anti-rejeu seront nécessaires si des collecteurs distants sont introduits.

Lecture administrateur :
```sh
sudo -u eidolon-darme python3 -c 'import socket;s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect("/run/eidolon-darme/status.sock");s.sendall(b"STATUS\n");print(s.recv(16384).decode())'
```

Les consommateurs futurs doivent recevoir explicitement l'accès au groupe du socket, ou utiliser un relais limité. Ne pas exposer le socket au monde ni donner sudo à l'UI. Claude conserve ses fichiers API/dialogue/UI ; le branchement de l'affichage est à coordonner, pas livré ici.

Systemd : NoNewPrivileges, capacités vides, ProtectSystem=strict, ProtectHome, PrivateDevices/PrivateTmp, AF_UNIX seulement, 128 Mio maximum, CPUQuota=10 %, TasksMax=16. Env Python ignoré par -I ; le lanceur ajoute seulement le chemin du paquet root installé.

## Recette réellement exécutée

59 tests unitaires DARME réussis, dont huit tests du nouveau service : perte/reprise de sonde, disque faible, quota/retry, confidentialité du statut, persistance et déduplication après reprise, validation de configuration. Une assertion de test initialement incorrecte a été corrigée : au quota, la dernière santé valide reste conservée mais la visibilité est dégradée et l'admission réessayée.

Recette systemd isolée sur **les deux VM** : compte non root, refus de socket IP, refus d'écriture /etc, alerte sur unité connue inactive, requête de mutation refusée, accès nobody au socket refusé, alerte conservée sans doublon après restart. Les unités de recette et leurs journaux temporaires ont été retirés. Aucun service métier arrêté.

Contrôles finaux : active + enabled, NRestarts=0, environ 9,9 Mo consommés sur chaque VM, journal/socket permissions vérifiées et hash identique. La suite Core 1 494 / Memory 2 018 du lot précédent n'a pas été relancée pour ce changement isolé ; les tests ciblés et la recette réelle couvrent ce déploiement.

## Installation et retour arrière

Fichiers reproductibles : deployment/eidolon-darme.service, deployment/darme-launch.py, deployment/darme-install.py, tools/check_darme_service.py. L'installateur attend un dossier contenant darme.py, darme_store.py, darme_service.py, launch.py et eidolon-darme.service, et une liste JSON des unités autorisées. Il crée le compte si absent, sauvegarde les chemins existants dans /var/backups/eidolon/darme-preinstall-*.tar.gz puis installe et active. Il nécessite root ; ce droit n'est pas accordé au service. Les scripts d'installation et de recette sont destinés aux VM Linux, pas au client Windows.

Retour arrière immédiat : sudo systemctl disable --now eidolon-darme.service. Conserver le journal ; restaurer les fichiers de la sauvegarde si une version précédente existait, puis daemon-reload. Aucun autre service ne dépend de DARME actuellement.

Limites restantes : journal SQLite limité à 64 Mio /100 000 événements, mais pas de quota filesystem couvrant tout le répertoire ; aucun effacement d'alertes automatique. La projection est reconstruite à chaque sondage : une grande histoire doit être mesurée avant extension. Statut sur demande, pas de notifications utilisateur, aucune collecte IDS, signatures distantes, empreinte hors VM ou administration des acquittements. Une corruption du journal fait échouer le démarrage plutôt que présenter un état sain.
