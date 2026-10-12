# DARME : état et travaux nécessaires — audit du 12 octobre 2026

Base examinée : Core e88a0c4, Memory f713623. DARME est un prototype de noyau passif et de journal local, pas un service de défense permanent installé. Aucun endpoint DARME trouvé dans l'API active, aucun collecteur authentifié ni processus permanent DARME sur Core/Memory. Les unités de recette transitoires ne constituent pas un déploiement de protection.

## Constats et correction

- Projection bornée à 10 000 événements avec validation du type de sévérité, fuseaux horaires, caractères de contrôle, sources connues et collision d'identifiant.
- Priorité de l'alerte rouge conservée devant la perte de santé d'une sonde.
- Journal SQLite, événements et acquittements idempotents, refus des collisions ; fichier propriétaire privé, acquittement avec acteur et motif.
- Défaut reproduit : ingestion saturée pouvait laisser visibilité complète et badge or. Corrigé : état ingestion_paused, visibilité partielle, gris sans alerte connue, rouge si une alerte subsiste. La pause reste verrouillée même si health(true) est rappelé ; reprise nécessite un mécanisme explicite à développer.
- Défaut de chemin : un répertoire ancêtre symbolique pouvait contourner le contrôle du seul fichier. Corrigé et testé. Cela ne supprime pas toutes les courses entre vérification et ouverture SQLite dans un répertoire contrôlé par un attaquant.
- 17 tests existants puis 27 ciblés réellement exécutés. Dix tests nouveaux couvrent saturation, persistance, acquittements, alias de répertoire, collisions et limites de texte. Suite complète : 1 470 tests, six ignorés, sans échec. Un test historique d'arrêt serveur journalise RemoteDisconnected attendu ; il n'est pas un échec de la suite.
- Aucun blocage, scan actif, capture réelle, extinction ni commande déclenchée par modèle.

## Travaux avant une surveillance permanente

| Priorité | Élément | État observé | Travail et recette |
|---|---|---|---|
| P0 | Processus/compte DARME isolé | Absent | Service distinct du HTTP Core ; compte sans sudo ; stockage dédié ; limites CPU/RAM ; restauration et reprise |
| P0 | Santé avec fraîcheur | Booléen manuel | Heartbeats horodatés, TTL et horloge monotone ; redémarrage/perte/rejeu ; gris sur sonde périmée |
| P0 | Authenticité des sources | Nom en allowlist seulement | Clé par collecteur, signature Ed25519 ou HMAC selon modèle de confiance, séquence anti-rejeu, rotation/révocation |
| P0 | Admission et backpressure | Capacité mémoire bornée, journal non borné | File bornée, quotas disque, rétention/archive, purge explicitement auditée, disque plein et reprise après saturation |
| P0 | Règles et normalisation | Sévérité fournie par appelant | Parseurs par source, données typées, seuils/baselines, anti-boucle ; provenance de la sévérité et refus des logs forgés |
| P0 | Journal de sécurité | SQLite local | Accès concurrents, chaîne d'intégrité ou scellement hors machine, date des acquittements, sauvegarde/restauration ; SQLite privé n'est pas inviolable |
| P0 | API de statut | Absente | Lecture authentifiée, generated_at, freshness, coverage et santé ; acquittement authentifié indépendant du LLM |
| P1 | Collecteurs passifs | Absents | journald SSH, systemd, ports locaux ; curseurs persistants, permission minimale, normalisation et retrait de secrets |
| P1 | Conseil LLM | Recette seulement | Worker CPU à la demande, timeout, cache, file bornée, refus des sorties invalides ; ne peut modifier sévérité ou badge |
| P1 | Interface | Concept | Badge et vue sécurité avec rouge/bleu/gris/or, sources manquantes, dates ; test Windows et mobile à effectuer |
| P1 | Ollama/infrastructure | Core loopback ; VM101 configurée LAN auparavant | Cartographier clients puis limiter accès ; rester local, préserver tunnel ; ne pas donner API de gestion modèle à DARME |
| P1 | Droits d'installation | sudo temporaire opérateur | Le futur compte DARME ne doit pas hériter de NOPASSWD global ; retirer droits temporaires après chantier et conserver récupération |
| P2 | IDS réseau | Non installé | Suricata IDS avec interface de capture réellement visible ; évaluer SPAN et trafic inter-VM ; TLS reste chiffré |
| P2 | CrowdSec | Pas de service vérifié actif | Détection seule d'abord ; examiner partage externe ; bouncer séparé plus tard |
| P3 | Remédiation | Aucune | Agent distinct, actions limitées et expirables, canal admin protégé, rollback et pont isolé avant activation |

La liste fixe des sources DARME ne prouve ni identité cryptographique ni couverture de Proxmox, NAS, Freebox et Windows. Aucun accès Proxmox hôte ou SPAN n'a été testé. Installer un IDS dans une VM sans recopie de trafic ne donne pas une visibilité générale.

## Architecture retenue pour la suite

Les règles déterministes et le journal fonctionnent sans LLM et sans GPU. DARME permanent ne signifie pas lancer un LLM sur chaque paquet ni chaque ligne. Agréger et dédupliquer les événements, maintenir les badges sans modèle, et demander une explication au worker CPU uniquement sur changements et incidents. Limiter la simultanéité à un, l'entrée à des événements normalisés et des fiches compactes, et le temps mural. Escalade vers Core facultative, sans lui déléguer les permissions.

Recette CPU sur VM101 car AVX2 y est exposé. La VM Core CPU présente QEMU 2.5 sans AVX/AVX2 ; ne pas extrapoler la vitesse mesurée à cette VM. Memory expose AVX2 mais dispose de 8 Go partagés avec son moteur : une future isolation CPU doit réserver sa RAM et son temps de rappel. Aucun service permanent n'est installé par cette recette.

## Ressources vérifiées

- [NCSC — risque résiduel d'injection](https://www.ncsc.gov.uk/blog-post/prompt-injection-is-not-sql-injection) : séparation de privilèges et contrôles déterministes.
- [OWASP — prévention d'injection](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) : défense en profondeur, outils restreints, sorties contrôlées.
- [OWASP — journalisation](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) : dates, provenance, absence de secrets, limites et accès.
- [systemd Debian 13](https://manpages.debian.org/trixie/systemd/systemd.exec.5.en.html) : environnement, isolation et permissions ; directives à tester réellement.
- [Suricata EVE](https://docs.suricata.io/en/latest/output/eve/eve-json-output.html) et [capture](https://docs.suricata.io/en/latest/capture-hardware/) : format des événements et visibilité des sondes.
- [CrowdSec](https://docs.crowdsec.net/docs/intro/) : traitement, API et bouncers séparés.
- [Python hmac](https://docs.python.org/3/library/hmac.html) : primitive d'authentification, pas anti-rejeu complet.
- [Ollama API](https://docs.ollama.com/api/chat) : compteurs de tokens et durées ; versions/digests réellement mesurés conservés.

Huit fiches de synthèse datées ont été créées dans Memory par le journal canonique, statut UNVERIFIED / PENDING_REVIEW, dont une politique interne DARME explicitement identifiée. Corpus servi à Core : 189 informations après import. Les douze cas avec mémoire utilisent le rappel réel, avec deux extraits maximum ; les extraits résultants sont figés pour comparer tous les modèles avec les mêmes données. Les deux autres cas simulent explicitement Memory indisponible.
