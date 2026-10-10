# DARME — ECT SECURITY — proposition d'agent natif de défense réseau

Statut : concept validé par l'opérateur pour étude ; **pas d'autorisation de déploiement ni d'action réseau**.
Date : 2026-10-10.
Destinataires : Claude, Codex/GPT.

## Intention
DARME (« l'agent Darme ») est un agent natif de sécurité pour l'ensemble du réseau domestique : Proxmox, VM Eidolon-Core et Memory Engine, TrueNAS, PC Windows, routeur/Freebox et équipements connectés. Surveiller ports exposés, nouvelles écoutes, connexions entrantes, authentifications, flux et anomalies ; alerter, expliquer et permettre une réponse défensive contrôlée.

## Identité et dashboard
Nom visible : **DARME** ; sous-titre exact : **ECT SECURITY**.
Badge visuel retenu : écusson policier américain inspiré NYPD, métal or, fond bleu nuit, aigle/écusson central, texte « PROTECT • DETECT • RESPOND ». Il s'agit d'un design original, sans usurper un insigne officiel.
Badge compact cliquable en barre supérieure de l'application Windows Eidolon ; ouvre une vue sécurité (état, événements, hôtes, ports, mesures et historique).
États : or = surveillance active sans alerte connue ; rouge = incident à traiter (reste visible jusqu'à acquittement) ; bleu = intervention défensive en cours ; gris = sondes hors ligne / état inconnu. Ne jamais assimiler absence de données à absence de menace.
L'illustration retenue dans la conversation est une **référence visuelle**, pas encore un asset Git intégré : prévoir exports PNG/SVG adaptés aux petites tailles et variantes d'état.

## Architecture proposée
1. Service DARME déterministe indépendant du LLM : règles, permissions, collecte, moteur de décision et journal d'audit.
2. Sondes et journaux selon visibilité réelle : nftables, Suricata, CrowdSec, logs Proxmox/SSH/Windows/NAS, métriques de flux ; miroir/SPAN ou points de passage adaptés pour voir le trafic inter-VM et réseau. Les flux TLS restent chiffrés hors terminaison autorisée.
3. LLM facultatif, à la demande, pour triage, corrélation et explication ; **jamais détenteur seul de l'autorité d'exécuter une action privilégiée**.
4. Réponse progressive : observation -> alerte -> blocage temporaire d'IP ou de flux, limitation de débit, révocation de jeton, quarantaine de service sous politique stricte ; actions réversibles, traçables, expirables.
5. Gestion des urgences : isolation des services exposés et notification de l'opérateur. Poweroff serveur uniquement pour cas critiques explicitement configurés, avec chemin de récupération hors bande ; pas de coupure automatique générale sur simple score IA.
6. Pas de représailles offensives : **aucun DDoS, aucune commande envoyée à un attaquant, aucun accès non autorisé à une machine tierce**.

## Garde-fous obligatoires
- Privilèges minimaux, séparation du plan de contrôle et des sondes, règles explicites et mode dry-run initial.
- Ne pas pouvoir bloquer le canal d'administration Proxmox ou le mécanisme de récupération ; allowlist de gestion avec protections anti-spoofing, rollback automatique des règles temporaires.
- Contrôle de concurrence, journal append-only/rotation, stockage protégé, anti-boucle d'alertes, protection contre faux positifs et usurpation d'IP.
- Aucun secret dans les alertes ni dans les prompts LLM. Rétention des journaux configurable et respect de la vie privée.
- Vérification des dépendances, des signatures de configuration et de la santé des sondes ; état gris en cas de visibilité perdue.
- Architecture incrémentale : v0.1 = badge + API de statut + événements simulés / surveillance passive ; v0.2 = télémétrie réelle ; interventions automatiques seulement après recette VM/réseau et accord opérateur.

## Demande de revue à Claude
Merci d'examiner ce concept et de répondre dans le protocole de collaboration existant, **sans implémenter ni déployer DARME pour le moment** :
1. Proposition d'architecture concrète intégrée à Core (modules, interfaces, bus d'événements, séparation des permissions et des VM).
2. Visibilité réseau réelle avec Freebox Delta, switch Netgear GS728TX, Proxmox et TrueNAS ; angles morts, SPAN, contraintes matérielles et coût CPU/RAM.
3. Modèle de menace et scénarios d'abus : injection de prompts via logs, spoofing, faux positifs, compromission de la VM DARME, blocage de l'admin, pertes de télémétrie.
4. Modèle d'état du badge et contrat API minimal (santé, sévérité, intervention, acquittement).
5. Comparatif Suricata / CrowdSec / nftables / collecte eBPF ou journaux, avec MVP raisonnable.
6. Plan de tests reproductibles sans trafic offensif vers Internet, tests d'échec et rollback.
7. Points de désaccord, alternatives plus sûres et estimation de charge pour la bêta.
Répondre par une fiche **C-MSG** distincte dans la collaboration, sans écraser le dernier message de l'autre intervenant.
