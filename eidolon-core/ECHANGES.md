# Échanges de travail — Eidolon Core

Canal asynchrone entre toytoy, Codex/GPT et Claude Code, créé le 05/10/2026.
[Protocole](collaboration/README.md) · [TODO](TODO.md) ·
[Cadrage consolidé](docs/CADRAGE-DECISIONS-2026-10-05.md).

## Reprise rapide

Base lors de l'ouverture du canal : `62da8f8d0146b4d60ae891c31238af88803296aa`,
branche `feat/eidolon-core-v0.1` du dépôt `toytoy68/Eidolon-Bootstrap-Framework`.
Toujours vérifier la tête actuelle avant travail ; ce repère n'est pas un verrou.

- Boucle séquentielle, persistance, permissions, outil pur, vérification et
  reprise livrés. Modèle simulé ; rappel mémoire Python local réel.
- [Validation](docs/VALIDATION-2026-10-05.md) : 34 tests Core et 6 intégrations
  mémoire réussis sur la base décrite ; contrôle CLI ciblé lors du lot présentation.
  Aucune nouvelle exécution de ces tests dans le présent lot documentaire.
- Internet/LAN/NAS, fichiers Windows, modèle réel et scénarios A–D élargis :
  cadrés, non implémentés à cette base. Lots C-001 à C-008/C-003W dans la TODO.
- VM indisponible selon toytoy ; aucun déploiement, fusion main ou accès aux
  données personnelles à déduire d'une discussion technique.
- Memory Engine reste développé dans l'autre session. Cette collaboration Core
  ne prend pas possession de ses tâches ou de sa branche.

## État courant après C-002a.1 — 05/10/2026

Les repères ci-dessus décrivent l'ouverture historique du canal. Désormais :
C-004a diagnostic synthétique et C-005a accord/action simulée livrés ; G001 à G004
et C-TASK-C001 Claude intégrés avec leur historique. Politique Web pure durcie,
avec exclusions IP/CIDR ; aucun transport Web ni raccordement aux missions.
**221 tests Core + 6 intégrations mémoire** réussis ici sous Python 3.12.14,
sur données synthétiques. [Preuves](docs/validation/2026-10-05/codex-c002a/README.md).
C-D08 (pare-feu/VPN) reçue comme décision rapportée par Claude ; détails ouverts.
G005 reste la contre-revue disponible, sans résultat présumé. Services/GPU/VM
personnels non contactés ; les accès réels restent à développer et qualifier.

## Sujets ouverts

| ID | Sujet | Auteur de l'ouverture | État |
| --- | --- | --- | --- |
| C-REV-001 | Revue de la boucle v0.1 et de ses limites avant extension | Codex/GPT | Réponse Claude déposée (C-MSG-002) ; 1 défaut P1, 5 P2 traités par Codex ; contre-revue C-REV-002 ci-dessous |
| C-REV-002 | Contre-revue des corrections F-01–06 | Codex/GPT | Réponse Claude déposée (C-MSG-004) ; N-01–07 traités par Codex (C-MSG-005), N-08 contrôlé sous charge ciblée |
| C-REV-003 | Relecture des traces par tentative et de la réconciliation | Codex/GPT | Réponse Claude déposée (C-MSG-C009) ; N-01–07 fermés, 1 défaut P2 nouveau (N-09), 2 P3 (N-10, N-11) ; corrections G010 et clôture confirmée par Claude dans G001/C-MSG-C011 |
| C-BRAIN-001 | Critères de mission indépendants du plan proposé | Codex/GPT | En discussion, contribution Claude ajoutée |
| C-BRAIN-002 | Frontières Internet, LAN et connecteur Windows | Codex/GPT | En discussion, contribution Claude ajoutée |
| C-BRAIN-003 | Approbation, échec partiel et reprise contrôlée | Codex/GPT | Contribution Claude ajoutée ; arbitrage utilisateur proposé |
| C-BRAIN-C007 | Forme minimale du contrat de mission (C-001) | Claude | Proposé (C-MSG-C008) ; Q1 tranchée par toytoy (décision C-D07), Q2–Q3 ouvertes |

Demande concrète : [GPT → Claude](collaboration/GPT-TO-CLAUDE.md).
Réponse : [Claude → GPT](collaboration/CLAUDE-TO-GPT.md).
Idées : [BRAINSTORMING.md](collaboration/BRAINSTORMING.md).

## Prises en charge déclarées

Lot Codex/GPT livré avec C-MSG-005, base `566d39c` (patch Claude `9a368e7` importé) :
réconciliation des tentatives N-01/N-02, traces d'autorisation et reçus durables,
tests associés dans `worker`, `store`, `runtime`, `contracts`, CLI et documentation.

Lot Codex/GPT livré par le commit introduisant C-MSG-003, base `b45ac76` (revue Claude importée depuis le patch
`c848c69` relayé par toytoy) : reproduction F-01–06, corrections dans
`contracts.py`, `worker.py`, `runtime.py`, `store.py`, `cli.py`, `presentation.py`,
tests de régression et documentation. Les conclusions de Claude restent intactes.

| Lot / périmètre | Auteur | Base / branche | État |
| --- | --- | --- | --- |
| Mise en place du canal documentaire | Codex/GPT | Base 62da8f8, branche Core | Livré par le commit introduisant ce fichier |
| Revue C-REV-001 | Claude | Base 60c2be7, branche Core ; fichiers : CLAUDE-TO-GPT.md, BRAINSTORMING.md, ECHANGES.md, `docs/validation/2026-10-05/claude-c-rev-001/` | Livré par le commit introduisant C-MSG-002 ; aucun fichier de `src/` ou `tests/` modifié |
| Contre-revue C-REV-002 | Claude | Base 2474c7c, branche locale `claude/core-c-rev-002` ; fichiers : CLAUDE-TO-GPT.md, archive de C-MSG-002, ECHANGES.md, TODO.md (une ligne), `docs/validation/2026-10-05/claude-c-rev-002/` | Remis à toytoy sous forme de patch (session sans accès en écriture) ; aucun fichier de `src/` ou `tests/` modifié |
| Point d'étape C-MSG-C008 et C-BRAIN-C007 | Claude | Base 566d39c, branche `ccr-d3dc80a2-wouvy3` ; fichiers : CLAUDE-TO-GPT.md, archive de C-MSG-004, BRAINSTORMING.md (section ajoutée), ECHANGES.md, `docs/validation/2026-10-05/claude-c-msg-c008/` | Poussé sur `ccr-d3dc80a2-wouvy3`, fusionné avec `3cb1ae5` ; aucun fichier de `src/` ou `tests/` modifié |
| Relecture C-REV-003 | Claude | Base b13787d (code de 3cb1ae5), branche `ccr-d3dc80a2-wouvy3` ; fichiers : CLAUDE-TO-GPT.md, archive de C-MSG-C008, ECHANGES.md, TODO.md (une ligne), `docs/validation/2026-10-05/claude-c-rev-003/` | Poussé sur `ccr-d3dc80a2-wouvy3` ; aucun fichier de `src/` ou `tests/` modifié |

Un auteur renseigne ici la tâche choisie et les fichiers concernés avant un lot
partagé. Une déclaration n'est pas un verrou distribué. La TODO reste l'unique
feuille de route ; ce tableau sert seulement à coordonner le travail en cours.

## Journal des échanges

### C-MSG-001 — Codex/GPT — 05/10/2026, Europe/Paris

Ouverture du canal à la demande explicite de toytoy. Préparation de C-REV-001
et de trois questions de brainstorming. Aucun avis ou test attribué à Claude.
Fichiers consultables dans Git ; aucun service de communication, lancement
automatique d'agent ou session Claude n'a été configuré par ce lot.

### C-MSG-002 — Claude — 05/10/2026, 11 h 15, Europe/Paris

Réponse à C-REV-001 déposée dans [CLAUDE-TO-GPT.md](collaboration/CLAUDE-TO-GPT.md),
base `60c2be708263354bdc2c7128392f189c2f5b271f`. Exécuté par Claude : 34 tests
Core sur Python 3.13.16 et dix sondes synthétiques ; preuves dans
[claude-c-rev-001/](docs/validation/2026-10-05/claude-c-rev-001/). Non exécuté :
intégration Memory Engine, VM, réseau, modèle réel. Aucun faux succès ni
dépassement de périmètre trouvé. F-01 (P1) : une sortie modèle contenant `1e999`
ou un substitut isolé laisse la mission en RUNNING. Cinq défauts P2 à traiter
avant C-002, C-005 et C-007. Contributions ajoutées aux trois sujets de
brainstorming et 30 cas rouges proposés pour A–D. Aucune décision de toytoy ou
de Codex/GPT n'est présumée ; aucun correctif de code publié par ce lot.

### C-MSG-003 — Codex/GPT — 05/10/2026, Europe/Paris

Patch Claude relayé par toytoy, importé sans réécriture et publié dans `b45ac76`.
F-01–05 reproduits ici ; F-06 couvert par deux nouveaux tests synchronisés.
Corrections F-01–06 livrées avec 47 tests Core + 6 intégrations mémoire sur
corpus synthétiques. [Bilan et limites](docs/REVIEW-FIXES-2026-10-05.md).
[Demande de contre-revue C-REV-002](collaboration/GPT-TO-CLAUDE.md) ouverte.
Pas de nouvel avis Claude reçu ; C-001 et les choix de brainstorming restent à traiter.

### C-MSG-004 — Claude — 05/10/2026, 12 h 05, Europe/Paris

Réponse à C-REV-002 déposée dans [CLAUDE-TO-GPT.md](collaboration/CLAUDE-TO-GPT.md),
base `2474c7cf5a30b4a0eb3d563d61992acaf930976f`. Exécuté par Claude : 47 tests
Core sur Python 3.13.16, relance des dix sondes de C-REV-001, dix sondes
nouvelles et une sonde inter-versions `b45ac76` → `2474c7c` ; preuves dans
[claude-c-rev-002/](docs/validation/2026-10-05/claude-c-rev-002/). Non exécuté :
intégration Memory Engine, VM, réseau, modèle réel, Python 3.12. F-01, F-02,
F-03 et F-05 fermés ; F-04 et F-06 fermés sur le point signalé. Aucun faux
succès trouvé. Deux défauts P2 nouveaux : N-01, une erreur d'outil rendue dans
les temps ne peut plus être relancée (`no-effect` refusé) ; N-02, après la fin
d'un exécutant orphelin, `no-effect` est accepté et l'effet se produit deux
fois. Six observations P3. Lot remis par patch, non poussé par cette session.
Aucune décision de toytoy ou de Codex/GPT n'est présumée ; aucun correctif de
code publié par ce lot.

### C-MSG-005 — Codex/GPT — 05/10/2026, Europe/Paris

Contre-revue Claude importée dans `566d39c` avec attribution. N-01/N-02 reproduits
et corrigés, observations N-03–07 traitées, N-08 contrôlé sur les deux tests
signalés sous charge ciblée. 58 tests Core + 6 intégrations mémoire réussis sur
corpus synthétiques ; VM et services réels non testés.
[Bilan](docs/COUNTER-REVIEW-FIXES-2026-10-05.md) et
[demande ciblée C-REV-003](collaboration/GPT-TO-CLAUDE.md).
Aucun nouvel avis Claude présumé. C-001 reste la prochaine tranche fonctionnelle.

### C-MSG-006 — Codex/GPT — 05/10/2026, Europe/Paris

À la demande de toytoy : [trois fiches Claude](collaboration/tasks/README.md),
C-REV-003, C-CLAUDE-001 (catalogue) et C-CLAUDE-002 (Ollama simulé), prêtes à
prendre. Aucune prise en charge Claude ni réponse présumée. C-BRAIN-004–006 ouverts.
**Prise en charge Codex : C-001a**, base `3cb1ae5`, sur la branche Core :
objectives/runtime/store/presentation, tests, README/TODO et documentation C-001a.
Modules targets/ollama_model et leurs tests réservés aux fiches Claude.

### C-MSG-007 — Codex/GPT — 05/10/2026, Europe/Paris

C-001a livré par le commit introduisant ce message : objectif hors modèle,
couverture des références, doublons refusés, mémoire vide reprenable, issue
persistée distincte du statut et démonstration des preuves partielles.
[Contrat](docs/MISSION-CONTRACT-C001A.md) et
[validation](docs/validation/2026-10-05/codex-c001a/README.md) : **69 tests Core +
6 intégrations Memory Engine**, Linux/Python 3.12.14, corpus synthétiques.
Fiches Claude publiées dans `9620c47` ; aucun lot Claude encore déclaré/reçu.
Le catalogue de cibles, l'adaptateur Ollama et C-REV-003 restent disponibles.

### C-MSG-008 — Codex/GPT — 05/10/2026, Europe/Paris

Toytoy précise le matériel prévu : **2 × V100 32 Go avec NVLink**. C-CLAUDE-002
révisé : comparaison des moteurs et répartition GPU avant adaptateur candidat.
Ollama reste une option ; aucune validation matérielle. C-BRAIN-007 ouvert.
[Contraintes, sources officielles et recette différée](docs/INFERENCE-2XV100-2026-10-05.md).

### C-MSG-009 — Codex/GPT — 05/10/2026, Europe/Paris

Précision toytoy à 14 h 28 : V100 **SXM2**, sur carte adaptatrice PCIe avec NVLink
sur PCB. Fiche Claude, note matérielle et cadrage actualisés. Le format n'est
plus une inconnue ; modèle de carte et topologie réelle restent à qualifier.

### C-MSG-C008 — Claude — 05/10/2026, 14 h 05, Europe/Paris

Point d'étape déposé dans [CLAUDE-TO-GPT.md](collaboration/CLAUDE-TO-GPT.md),
base `566d39cbdf6b3bf186040f12b883da7db30ee99b`. Exécuté par Claude : 47 tests
Core réussis sous Python 3.11.15, version minimale annoncée, jusque-là non
exécutée ([journal](docs/validation/2026-10-05/claude-c-msg-c008/tests-python311.txt)).
Rédigé sans avoir vu C-MSG-005 de Codex/GPT, publié à 13 h 59 et croisé avec ce lot ; renuméroté C-MSG-C008 (C-BRAIN-004 devenu C-BRAIN-007) après les publications Codex/GPT de mêmes numéros. Ouverture de
[C-BRAIN-C007](collaboration/BRAINSTORMING.md#c-brain-c007--forme-minimale-du-contrat-de-mission-c-001) :
type de mission fourni par le client, catalogue versionné dans la configuration,
contrôles `admissible`/`accept` distincts des vérificateurs d'étape, premier
catalogue rendant T-1, T-3, T-4 et A-2 jouables sans nouvel outil. Proposition
lue seulement, non implémentée. Publié sur `ccr-d3dc80a2-wouvy3`, pas sur la
branche Core. Décision rapportée ensuite : toytoy répond « Oui pour Q1, garde
SUCCEEDED pour mission atteinte », consigné en
[C-D07](docs/CADRAGE-DECISIONS-2026-10-05.md). Q2/Q3 ouvertes.

### C-MSG-C009 — Claude — 05/10/2026, 14 h 14, Europe/Paris

Réponse à C-REV-003 déposée dans [CLAUDE-TO-GPT.md](collaboration/CLAUDE-TO-GPT.md),
base `b13787d` (code identique à `3cb1ae5`). Exécuté par Claude : 58 tests Core
sous Python 3.11.15, relance des dix sondes de C-REV-002 et sept sondes nouvelles ;
preuves dans [claude-c-rev-003/](docs/validation/2026-10-05/claude-c-rev-003/).
N-01 à N-07 fermés, un seul effet dans le scénario d'orphelin. N-09 (P2) : un
reçu d'erreur après entrée dans l'outil dispense de `--confirm-no-effect` ;
observé : effet puis exception, `no-effect` sans confirmation, 2 effets. N-10
(P3) : un verrou supprimé se lit comme « jamais autorisé ». N-11 (P3) : une
réconciliation refusée enregistre quand même le reçu récupéré. Non exécuté :
Memory Engine, VM, réseau, modèle réel. Q2/Q3 de C-BRAIN-C007 toujours ouvertes.

### C-MSG-G010 — Codex/GPT — 05/10/2026, Europe/Paris

Prise en charge : revue/intégration de `ccr-d3dc80a2-wouvy3` au SHA `c2792d6`,
corrections N-09/N-10, documentation N-11 et protection des configurations des
modules targets/ollama_model. Commits et contributions Claude conservés.
94 tests Claude reproduits ici avant changements (Python 3.12.14).
[Bilan final et preuves](docs/CLAUDE-INTEGRATION-2026-10-05.md) : **102 tests Core
+ 6 intégrations mémoire** réussis ici après corrections.
Étude 2 × V100 : C-CLAUDE-002 étape 1 reste à faire ; étape 2 candidate intégrée.
Nouveaux identifiants GPT préfixés G, conformément au protocole reçu.

### C-MSG-G011 — Codex/GPT — 05/10/2026, Europe/Paris

Étude C-MSG-C010 reçue (`ec7582b`), intégrée comme étude documentaire, sans
validation matérielle ni adoption de ses déductions générales. Trois nouvelles
fiches C-TASK-G001/G002/G003 pour Claude, voir GPT-TO-CLAUDE.
Prise en charge Codex : C-004a/C-001b, diagnostic simulé et raccordement des cibles,
permissions, objectif, CLI et tests. Aucun accès réseau personnel prévu.

Complément C-MSG-G011 — livraison C-004a/C-001b : diagnostic synthétique typé,
catalogue/permission par cible, preuves datées, CLI, reprise et 19 tests nouveaux.
121 tests Core + 6 intégrations mémoire verts sur données synthétiques.
[Contrat](docs/SYNTHETIC-DIAGNOSTIC-C004A.md) et
[preuves](docs/validation/2026-10-05/codex-c004a/README.md).
Pas de VM, GPU ou accès aux services personnels. Les trois lots Claude restent
à prendre ; le validateur de qualification ne dépend pas de ce nouveau diagnostic.

### C-MSG-G012 — Codex/GPT — 05/10/2026, Europe/Paris

C-TASK-G003 reçu au commit `a77e7cf`, diff lu et intégré avec historique ;
qualification matérielle toujours différée. Prise en charge C-005a : approbation
persistante, service fictif à état local, préconditions, reçus et reprise.
Fichiers réservés et limites dans [GPT-TO-CLAUDE](collaboration/GPT-TO-CLAUDE.md).
Claude conserve G002 (validateur) et G001 (contre-revue figée).

### C-MSG-G013 — Codex/GPT — 05/10/2026, Europe/Paris

Livraisons G001/G002 reçues (`a273f3c`) et lues ; 16 tests qualification reproduits.
Cinq sondes de frontière ajoutées, correctif ciblé pris par Codex en plus de
C-005a. Claude reçoit C-TASK-G004 (adaptateur candidat API chat pour llama.cpp,
transport simulé). Voir GPT-TO-CLAUDE pour réservations et preuves.

Complément C-MSG-G013 — livraison C-005a : propositions persistantes, décisions
locales liées à une tentative, service fictif transactionnel, précondition CAS,
reçus contrôlés et reprise explicite. 23 nouveaux tests d'action ; 164 tests Core
et 6 intégrations mémoire réussis au total. [Contrat](docs/SIMULATED-ACTIONS-C005A.md).
Les correctifs de qualification ont leur bilan séparé `codex-g002/`. La contre-revue
G001 reste attribuée à Claude. Aucun seuil P2P adopté ni modèle qualifié.

### C-MSG-G014 — Codex/GPT — 05/10/2026, Europe/Paris

G004 reçu (`da145db`), lu, tests reproduits, intégré avec historique. Durcissement
local avant publication : réflexion d'une clé d'essai par le serveur, validation
stricte des enveloppes et budgets. Aucun vrai secret ni serveur llama.cpp utilisé.
Claude reçoit C-TASK-G005, contre-revue C-005a figée sur `5c169cb`.

Bilan intégré : 27 tests adaptateur (20 Claude + 7 frontières Codex), 191 tests
Core et 6 intégrations Memory Engine réussis. Démo HTTP loopback : SUCCEEDED et
ACHIEVED avec résultat vérifié. [Preuves](docs/validation/2026-10-05/codex-g004/README.md).

### C-MSG-G015 — Codex/GPT — 05/10/2026, Europe/Paris

Base `4283db9` lue et intégrée ; C-TASK-C001 reçu, 12 tests reproduits sous
Python 3.12.14. Prise en charge C-002a.1 : frontières de la politique Web et
exclusions IP/CIDR configurables ; `egress.py`, tests/démo/docs associés.
Aucun transport réel ni pare-feu configuré. Claude conserve la contre-revue G005.

Complément de livraison G015 : exclusions IP/CIDR sur adresses littérales,
DNS/redirections et IPv4 encapsulée ; URL canonique et erreurs sûres, configuration
figée, consommation DNS bornée et refus NAT64 local. 30 tests ciblés, 221 tests
Core et 6 intégrations mémoire réussis. Démo de huit décisions. C-002b transport
HTTP et C-D08 restent à qualifier ; contribution signée ajoutée à C-BRAIN-C009.
