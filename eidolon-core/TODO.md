# TODO propre à Eidolon Core

Périmètre autorisé le 05/10/2026 : première tranche v0.1 isolée de Bootstrap,
sans déploiement VM ni modification du Memory Engine. Pas de pourcentage global
emprunté au moteur mémoire. Les concepts G-001–006/G-017 guident les frontières,
ils ne constituent pas des fonctionnalités livrées.

## Livré dans cette tranche

- [x] Paquet autonome, CLI, démonstration sans service/GPU, modèle déterministe.
- [x] Missions stables, progression vérifiée, blocage/échec/annulation.
- [x] Persistance SQLite et événements atomiques, exclusion d'exécutions concurrentes.
- [x] Plans structurés, précontrôle intégral, paramètres et permissions hors modèle.
- [x] Outil local pur, résultat contrôlé indépendamment, preuves et sources conservées.
- [x] Délais, interruption de processus, reprise sans relance aveugle.
- [x] Réconciliation explicite et auditée, sans confirmation automatique des sources.
- [x] Adaptateur réel de rappel, tests synthétiques du service mémoire sur copie.
- [x] Documentation des trois défauts mémoire et des validations différées.
- [x] Standard de présentation commun Eidolon, consignes AGENTS.md, en-têtes
  des modules et mode humain de la CLI ; aperçu sans installation.
- [x] Canal d'échanges Core Codex/GPT ↔ Claude Code, protocole, brainstorming
  et consignes de découverte AGENTS.md/CLAUDE.md ; première revue préparée.

## Revue C-REV-001 : corrections livrées

[Bilan, bases et preuves](docs/REVIEW-FIXES-2026-10-05.md) : 47 tests Core et
6 intégrations réelles du moteur sur corpus synthétiques réussis sous Python 3.12.

- [x] F-01 : JSON fini/UTF-8 persistable avant plan, diagnostic terminal propre.
- [x] F-02 : preuves par références, cinq sorties de 600 ko sans blocage final.
- [x] F-03 : abandon terminal conservant l'effet inconnu et l'audit.
- [x] F-04 : verrou d'exécutant et lancement autorisé après journalisation ;
  réconciliation interdite pendant l'exécution locale, test SIGKILL réel.
- [x] F-05 : indisponibilité/délai modèle reprenable, distinct du plan invalide.
- [x] F-06 : reçu tardif conservé et non promu automatiquement en succès.
- [x] Filet INTERNAL_ERROR basé sur l'état durable ; sondage d'annulation allégé.
- [x] Contre-revue Claude C-REV-002 reçue (C-MSG-004, base `2474c7c`).
- [x] Suites C-REV-002 : N-01/N-02, annulation avant autorisation, profondeur
  bornée, connexion interrompue, origine/cohérence des preuves et adoption du reçu.
  [Bilan](docs/COUNTER-REVIEW-FIXES-2026-10-05.md) : 58 tests Core + 6 intégrations.
- [x] N-08 : marge des délais de test relevée, annulation synchronisée ; deux
  tests ciblés verts sur deux CPU avec six concurrents. Recette VM toujours différée.
- [x] Contre-revue C-REV-003 reçue (C-MSG-C009, base `3cb1ae5`).
- [x] Suites C-REV-003 : N-09 confirmation après erreur ; N-10 verrou absent
  après spawn bloquant ; N-11 import de reçu avant refus documenté.
  [Bilan de l'intégration](docs/CLAUDE-INTEGRATION-2026-10-05.md).
- [ ] Budget global des tentatives et rétention/nettoyage coordonnés des reçus,
  historiques et verrous ; aucun effacement automatique d'un état actif.
- [ ] Externaliser les gros documents/médias avec budgets et rétention avant
  leur prise en charge ; sorties actuelles bornées et toujours inline dans SQLite.
- [x] C-001a : mémoire vide distincte de MODEL_INVALID et rappel reprenable,
  critères de couverture hors modèle, issue distincte du statut et preuves partielles.
  [Contrat et limites](docs/MISSION-CONTRACT-C001A.md).
- [ ] Révision explicite d'un plan refusé : configuration et proposition restent
  figées ; créer une nouvelle mission pour les corriger dans cette tranche.
- [x] C-D07 appliquée par C-001a : `SUCCEEDED` exige l'issue ACHIEVED ; les
  autres issues restent hors de `SUCCEEDED`. Proposition d'origine : C-BRAIN-C007.
- [ ] C-008 : propriétaire/battement de mission pour distinguer vivant/orphelin.
- [ ] C-005 : identité humaine authentifiée (C-005a simule les décisions) ; `actor` actuel est une trace libre.

## Prochaine tranche proposée : critères de mission et contrôleur simulé enrichi

Le [cadrage consolidé du 05/10](docs/CADRAGE-DECISIONS-2026-10-05.md) intègre le
brainstorming reçu et l'exigence explicite **Internet + machines du LAN, dont
Memory Engine et NAS**, ainsi que les **documents, images, vidéos et audio de
la session Windows**. Ces capacités deviennent un besoin du socle, pas une
option liée au futur Desktop. Le code v0.1 n'en dispose pas encore.

### C-001a et tâches parallèles

- [x] Premier contrat restreint : demande synthétique reconnue par le code,
  toutes les références rappelées couvertes, doublons refusés avant tout outil.
- [x] `outcome` persistant : atteint, non atteint, partiel, clarification, sans
  preuve ; aucun succès final sans objectif atteint et résultats vérifiés.
- [x] Démonstration `examples.objective_demo`, sans réseau ni VM.
- [x] [C-REV-003](collaboration/tasks/C-REV-003.md) : avis Claude intégré et suites traitées.
- [x] [C-CLAUDE-001](collaboration/tasks/C-CLAUDE-001.md) : catalogue pur de cibles
  et capacités intégré avec tests ; raccordement runtime/permissions livré en C-004a.
- [ ] [C-CLAUDE-002](collaboration/tasks/C-CLAUDE-002.md) : étude 2 × V100 32 Go/NVLink
  reçue (`ec7582b`), précisions C-TASK-G003 intégrées (`a77e7cf`). Adaptateur candidat
  simulé (étape 2) intégré ; Ollama à réévaluer,
  aucun modèle réel qualifié et aucune activation CLI.
- [x] C-004a/C-001b : [diagnostic synthétique](docs/SYNTHETIC-DIAGNOSTIC-C004A.md),
  cible résolue hors modèle, permission par capacité, observation datée vérifiée,
  CLI et reprise ; état DOWN distinct de l'échec de mission.
- [x] Claude : G003/G002/G001 reçus (`a273f3c`), code et preuves lus, validateur
  intégré ; 20 tests qualification après durcissement de cinq frontières d'entrée.
- [x] Claude : [C-TASK-G004](collaboration/tasks/C-TASK-G004.md), adaptateur candidat
  API chat llama.cpp intégré (`da145db`), puis durci ; 27 tests sur transports
  simulés et HTTP loopback, aucune activation CLI ni qualification de modèle réel.
  [Bilan intégré : 191 tests Core + 6 mémoire](docs/validation/2026-10-05/codex-g004/README.md).
- [x] Claude : [C-TASK-G005](collaboration/tasks/C-TASK-G005.md), contre-revue
  de C-005a sur base figée `5c169cb` reçue (`0e601e7`) ; huit sondes reproduites.
  O-G5-1/O-G5-2 traités par une vue dérivée, O-G5-3 conservateur.
- [x] Claude : [C-TASK-G006](collaboration/tasks/C-TASK-G006.md), transport HTTP
  candidat intégré avec G007 dans `534f4f4` ; 15 tests reproduits, puis frontières
  renforcées et [lecteur raccordé](docs/WEB-READER.md), hors runtime.
- [x] C-005a : [approbation et action simulée](docs/SIMULATED-ACTIONS-C005A.md),
  accord lié aux paramètres/tentative, refus/révocation, état/version revérifiés,
  effet/reçu transactionnels sur fixture ; 23 tests et démo de six scénarios.
- [ ] C-005 réel : identité authentifiée, protocole de service, autorisation
  distante et recette ; actor actuel reste une trace libre, pas une identité.
- [ ] Étendre le contrat aux scénarios A–D ; le lot C-001 complet reste ouvert.

### Accès Web — C-002a reçu et durci

- [x] Politique pure de destinations Claude (`b869eef`) intégrée : DNS injecté,
  adresses contrôlées et sélectionnées, redirections revérifiées ; hors runtime.
- [x] C-002a.1 : exclusions IP/CIDR explicites, configuration figée, validation
  URL/DNS renforcée, NAT64 local refusé ; 30 tests et démo de huit décisions.
- [x] C-002b candidat : transport HTTP de lecture avec adresse épinglée,
  TLS/Host/SNI corrects, pas de proxy, bornes et délais, redirections contrôlées ;
  tests sur transport simulé et HTTP/TLS loopback ; accès externe non qualifié.
- [ ] Raccordement `web.read` au catalogue, permissions et critères de mission,
  provenance/version du contenu et minimisation des données sortantes.
- [ ] C-D08 rapportée par Claude : pare-feu sortant et VPN avant accès réels ;
  choix des outils, inventaire local hors Git, adresse publique/préfixes propres
  au foyer et traductions/routes particulières à qualifier sur le matériel.

### Recherche Web — C-D09 et C-BRAIN-G010

- [x] Premier coordinateur `research.py` sur doubles : fournisseurs, replis
  bornés, cache RAM, blocages et reçus ; hors runtime et sans service réel.
- [x] Claude G007 : avis contradictoire et corpus de 20 cas intégrés ; cohérence
  du corpus vérifiée ici, pas encore conformité du coordinateur à ses attentes.
- [x] WebReader : raccordement HTTP au coordinateur, statut/Retry-After/provenance,
  reçus tardifs et suspensions entre sauts ; démonstration sur serveur local.
- [x] Banc G007 exécuté par Claude sur `99641df` : 9 PASS, 7 KNOWN_GAP,
  4 FINDING rapportés dans C018 ; non reproduit par Codex dans le lot Desktop.
- [ ] Reproduire et trier ces écarts sur base actuelle ; ne pas assimiler une
  page lue à une réponse démontrée ou à une source indépendante.
- [ ] API fournisseur réelle choisie après comparaison, sans abonnement implicite.
- [ ] Extraction HTML après transport contrôlé ; texte simple seulement à ce stade.
- [ ] Attente/quotas durables par fournisseur, artefacts persistants, intégration
  mission et critères de qualité distincts du seul nombre de pages lues.

- [ ] Traiter la contre-revue G008 reçue dans `e55dc5d` : D1 attente perdue
  sur en-têtes ambigus, D2 horloges incompatibles ; trier L1–L3/C1–C5.

### Client bureau Eidolon — propositions et recette distinctes

- [x] Huit maquettes Claude `176edac` reçues ; sources/contrats relus par Codex,
  trois comportements reproduits par sonde de logique, sans rendu visuel validé.
- [ ] Claude G009 : prototype autonome hors ligne avec accords, refus, perte
  d'accusé, reconnexion et états de preuve ; aucune application Windows livrée.
- [ ] Claude G010 : comparaison Tauri/PySide/Electron et recette Windows ;
  framework non choisi, mesures OS et installation différées.
- [ ] Codex C-008 : contrat distant versionné, projection, reçus de commandes
  et rattrapage des événements ; autorité et permissions restent dans Core.
- [ ] C-003W : connecteur documents/médias Windows et permissions locales,
  séparé de la présence graphique. Voir [revue](docs/proposals/2026-10-05-codex-desktop-review/README.md).

### Lots concrets suivant le brainstorming

| Lot | Livrable | Critère de sortie |
| --- | --- | --- |
| C-001 | Contrats de mission/cible/capacité et critères de réussite A–D | Refus des cibles ambiguës et des plans sans rapport avec l'objectif ; fixtures indépendantes du modèle |
| C-002 | Connecteurs de lecture Internet et LAN, politiques distinctes | Destinations, redirections, egress, authentification, délais/volume et provenance contrôlés ; tests sans infrastructure personnelle |
| C-003 | Rappel Memory Engine distant et accès aux fichiers NAS autorisés | API/protocole réellement vérifiés, références/statuts préservés, périmètres de fichiers bornés, aucune écriture canonique directe |
| C-003W | Connecteur Windows de fichiers, indépendant du Desktop complet | Dossiers autorisés, droits de session, recherche/lecture et preuves de version ; PC hors ligne, liens hors périmètre et changements concurrents traités |
| C-004 | Mission B de diagnostic d'un service | Résultat observé daté, authentifié selon le transport et vérifié ; cible hors ligne ou réponse périmée explicite |
| C-005 | Mission C avec proposition d'action, approbation liée aux paramètres, refus/annulation | Démonstration de redémarrage simulée ; aucun vrai redémarrage sans cible et autorisation concrètes |
| C-006 | Mission D : reprise explicite après échec partiel | X vérifié reste acquis ; Y seul réessayé si admissible ; appel à effet inconnu toujours en revue |
| C-007 | Moteur réévalué pour 2 × V100 32 Go/NVLink, adaptateur interchangeable et mission A sourcée | Réponses structurées, manque de contexte explicite, critères indépendants et protocole de qualification ; aucun modèle préqualifié |
| C-008 | Contrats de client distant et événements de reconnexion | Fermeture du client distincte de l'annulation ; événements récupérables sans recréer les missions |

Les connecteurs commencent avec doubles de test ou services locaux synthétiques.
Leur activation vers Internet, le NAS et les services personnels constitue une
recette distincte. Les choix API/transport, cibles et authentification seront
explicités avant activation ; les accès réels ne sont pas supposés disponibles.

### Exigences transversales

1. Définir un petit catalogue de missions et leurs critères d'acceptation
   déterministes indépendants du plan ; résultat partiel, clarification et absence
   de preuve doivent avoir des sorties explicites. Garder un lot de cas réservé.
2. Étendre les contrats modèle (capacités/hors domaine, version/configuration,
   budget entrée/sortie/temps), puis ajouter un adaptateur de modèle local optionnel.
   Aucun modèle n'est qualifié par la réussite du simulateur.
3. Ajouter budget global durable, nouvelles tentatives contrôlées des lectures,
   révision explicite d'une proposition et traitement clair des plans devenus caducs.
   Ne pas ajouter d'expiration automatique des propositions.
4. Renforcer la frontière des exécutants avant tout outil à effets : sandbox,
   permissions par cible, autorisation humaine authentifiée, reçus observables,
   protocole de réconciliation propre à chaque outil et tests après perte réseau.
5. Préparer le noyau du protocole AI Lab G-017 : corpus attendu, erreurs
   éliminatoires, artefacts de mesure ; benchmark réel séparé des tests unitaires.

## Coordination avec Memory Engine

- [ ] Revalider l'adaptateur après les corrections A5-01 (exports recouvrants),
  A5-02 (contexte/négation) et A5-03 (content.parts). Suivre ces corrections dans
  l'autre session, ne pas les implémenter ici.
  Actualisation du 05/10 : correctif A5-03 publié dans `d34a365`, diff lu ici,
  tests non réexécutés dans ce lot. A5-01/A5-02 restent ouverts sur cette tête.
- [ ] Contrat de fraîcheur/révision à la frontière d'une action réelle.
- [ ] Si une mutation est autorisée ultérieurement : adaptateur des services
  coordonnés, identité stable, idempotence métier et reprise par le moteur.
- [ ] File durable de propositions/revue métier interopérable, décisions et
  statuts épistémiques séparés ; rien ne s'accepte ou ne s'abandonne par silence.

## Validations différées à la disponibilité de la VM

- [ ] Recette Python 3.13/Debian 13, installation isolée du paquet.
- [ ] Arrêt/reboot du runtime et diagnostic des éventuels enfants survivants.
- [ ] Persistance/permissions/stockage physique et essai contrôlé de coupure.
- [ ] Matériel prévu : 2 × V100 32 Go + NVLink selon toytoy. Vérifier références
  exactes des modules SXM2 et de leur carte adaptatrice PCIe (NVLink sur PCB
  selon toytoy), topologie et visibilité hôte/VM ; comparer un GPU, partage
  sur deux et rôles séparés. [Note](docs/INFERENCE-2XV100-2026-10-05.md).
- [ ] Modèle/GPU réel, latence, consommation, contexte utile et qualification.
- [ ] Corpus utilisateur seulement après choix/autorisation et copie isolée.
- [ ] Internet réel, service Memory Engine distant et NAS : valider séparément
  connectivité, identité, permissions, limites de débit/volume et comportement
  en cas de perte réseau ; commencer par les lectures autorisées.
- [ ] Session Windows réelle : fichiers/dossiers choisis, chemins déplacés,
  droits effectifs, liens/jonctions, fichiers indisponibles et verrouillage de
  session. Valider les lectures avant toute capacité de modification.

## Vision produit conservée pour les tranches ultérieures

- [ ] Traitement multimédia des ressources Windows/NAS : extraction documentaire,
  OCR/Vision, segments vidéo et transcription audio ; capacités et budgets explicites.

- [ ] Client Windows résident : E bleu, chat, zone de notification, autostart
  configurable, silence et état du serveur.
- [ ] Presence/Identity : événements locaux, identité probable séparée de
  l'authentification, contexte invité et protection des informations personnelles.
- [ ] Voix : transcription, synthèse et identité du locuteur traitées séparément.
- [ ] Catalogue des équipements, fraîcheur de la télémétrie et missions liées.
- [ ] Scheduler différé/récurrent/conditionnel et notifications dédupliquées.
- [ ] Robot/Vision/domotique : contrôle et sécurité locaux indépendants du LLM.

Ni Hermes, ni Qdrant, ni multi-agents, ni service permanent n'est requis pour
terminer ou reproduire la tranche actuelle. Main reste inchangée.
