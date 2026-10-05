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
- [x] Contre-revue C-REV-003 reçue (C-MSG-008, base `3cb1ae5`).
- [ ] Suites de C-REV-003 signalées par Claude, non traitées : N-09 (P2),
  N-10 et N-11 (P3). Voir [CLAUDE-TO-GPT.md](collaboration/CLAUDE-TO-GPT.md).
- [ ] Budget global des tentatives et rétention/nettoyage coordonnés des reçus,
  historiques et verrous ; aucun effacement automatique d'un état actif.
- [ ] Externaliser les gros documents/médias avec budgets et rétention avant
  leur prise en charge ; sorties actuelles bornées et toujours inline dans SQLite.
- [ ] C-001 : appliquer [C-D07](docs/CADRAGE-DECISIONS-2026-10-05.md) : `SUCCEEDED`
  réservé à une mission atteinte, état terminal distinct pour les autres issues
  (nom et code CLI à fixer). Proposition de contrat : C-BRAIN-007.
- [ ] P3 : mémoire vide distincte de MODEL_INVALID ; clarification du blocage
  de précontrôle avec configuration figée, à intégrer dans C-001.
- [ ] C-008 : propriétaire/battement de mission pour distinguer vivant/orphelin.
- [ ] C-005 : identité humaine authentifiée ; `actor` actuel est une trace libre.

## Prochaine tranche proposée : critères de mission et contrôleur simulé enrichi

Le [cadrage consolidé du 05/10](docs/CADRAGE-DECISIONS-2026-10-05.md) intègre le
brainstorming reçu et l'exigence explicite **Internet + machines du LAN, dont
Memory Engine et NAS**, ainsi que les **documents, images, vidéos et audio de
la session Windows**. Ces capacités deviennent un besoin du socle, pas une
option liée au futur Desktop. Le code v0.1 n'en dispose pas encore.

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
| C-007 | Adaptateur Ollama configurable et mission A sourcée | Réponses structurées, manque de contexte explicite, critères indépendants et protocole de qualification ; aucun modèle préqualifié |
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
