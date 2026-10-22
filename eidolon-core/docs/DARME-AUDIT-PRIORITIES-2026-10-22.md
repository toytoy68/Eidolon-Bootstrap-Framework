# Audit DARME — couverture et priorités — 2026-10-22

Statut : **constats de lecture seule sur VM100**. Pas de déploiement, d'intrusion simulée, d'acquittement ni de modification de configuration. Les observations ponctuelles ne constituent pas une recette de sécurité complète.

## État observé

- `eidolon-darme.service`, `eidolon-darme-ssh.service` et `eidolon-monitor.service` : actifs au contrôle. Service DARME ~17 Mio RAM, SSH ~32 Mio (valeurs ponctuelles).
- DARME interroge six unités systemd locales, le disque du journal et un flux SSH signé ; configuration d'échantillonnage à 10 s.
- Socket Unix privé `/run/eidolon-darme/status.sock`, protocole de lecture seule. Comptes dédiés et restrictions systemd (pas de capacités, NoNewPrivileges, ProtectSystem).
- Réponse de statut vers 2026-10-22 10:37 UTC : `badge=red`, `visibility=partial`, `unacknowledged_alerts=1`, `ingestion_paused=false`, `ssh_feed_healthy=true`.
- Les six unités surveillées, `journal-disk` et `ssh-auth` sont indiqués sains ; `security-telemetry=false`, `security_telemetry_installed=false`. L'alerte non acquittée n'a pas été identifiée par cette lecture.
- Mesures machine CPU/RAM/swap/disque disponibles ; `gpu=null`.
- Collecteur SSH : événements d'échec d'authentification, enveloppe signée Ed25519, contrôle de séquence/anti-rejeu, pas de nom d'utilisateur ou d'adresse transmis dans le flux normalisé.
- Le code déployé n'expose pas de capture de paquets, d'exécution de commandes, de modification de pare-feu ou de remédiation ; `enforcement_enabled=false`. Le statut indique `advisor=fixed`, donc pas de conseil LLM opérationnel démontré.
- Recherche ciblée dans les modules DARME déployés : aucun collecteur CVE/NVD/KEV ni inventaire logiciel identifié. `crowdsec` et `fail2ban` inactifs sur VM100 (absence d'activation, pas preuve de nécessité).
- La couverture d'autres VM, de Proxmox, des ports exposés et du réseau n'a pas été démontrée.

## Priorités proposées (sans activation)

| Rang | Sujet | Critère de sortie | Moment |
| --- | --- | --- | --- |
| P0 — qualification bêta | Identifier l'unique alerte ouverte ; déterminer si `security-telemetry` est volontairement absente ou indispensable à la recette ; contrôler la cohérence badge/visibilité | Cause documentée, état explicite et recette de statut reproductible | Avant clôture bêta si bloquant |
| P1 | Inventaire versionné des logiciels, services et surfaces exposées | Collecte authentifiée, périmètre et fraîcheur affichés, aucune supposition de version | Après bêta |
| P1 | Corrélation inventaire / avis de sécurité officiels (Debian, CISA KEV, CVE) | Appariement produit/version corrigée, provenance, réduction des faux positifs, alertes exploitables | Après bêta |
| P2 | Étudier un collecteur IDS / CrowdSec ou équivalent | Besoin et couverture démontrés, droits minimaux, coût/charge mesurés | Après bêta |
| P2 | Procédure de réaction graduée et rollback | Politique déterministe, validation humaine pour coupure/blocage, canal admin protégé, audit et retour arrière testé | Après bêta |
| P3 | Conseiller IA ponctuel de Core | Conseil sans pouvoir d'exécution, bornes de temps/contexte, repli fixe et tests de refus | Après bêta |

## Architecture conservée

DARME = service déterministe permanent, léger et indépendant de Core/Memory/GPU pour la détection et les alertes. Core = conseiller facultatif, **jamais** autorité de blocage, acquittement ou changement de sévérité. Une remédiation future nécessite un contrôleur séparé et une décision explicite.

## Précautions et suite

1. Auditer l'alerte restante avec un accès autorisé aux journaux sans l'acquitter automatiquement.
2. Documenter le statut voulu de la source `security-telemetry` et le critère d'acceptation bêta.
3. Après bêta, spécifier les collecteurs d'inventaire/CVE en lecture seule ; ne pas ouvrir de chantier maintenant.
4. Tester ensuite panne/reprise, fausses alertes, pertes de source, saturation, permissions et restauration sur environnement de recette.

Source de veille motivant l'étude : https://www.youtube.com/watch?v=og_OLja5sL8 . Les CVE et incidents racontés dans la vidéo ne sont **pas vérifiés** par cet audit ; ne pas les traiter comme des faits de sécurité confirmés.

**Règle opérateur : la bêta Core/Memory reste prioritaire.** Ce document est un compte rendu et un parking de priorités, pas une autorisation d'exécuter les tâches.
