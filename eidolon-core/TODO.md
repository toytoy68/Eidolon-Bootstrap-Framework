# TODO propre à Eidolon Core

Périmètre autorisé le 05/10/2026 : première tranche v0.1 isolée de Bootstrap,
sans déploiement VM ni modification du Memory Engine. Pas de pourcentage global
emprunté au moteur mémoire. Les concepts G-001–006/G-017 guident les frontières,
ils ne constituent pas des fonctionnalités livrées.

## État courant — séance du 08/10/2026

C-039–C-041 : contrat textuel explicite commun aux planificateurs (manifestes /4),
`model-probe` sur quatre cas synthétiques et `model-probe-inspect` hors ligne,
y compris après interruption. [Contrat et commandes](docs/MODEL-PROBE.md).
Le défaut reste déterministe ; aucun vrai modèle, GPU, Windows ou VM qualifié.
[Preuves de la séance du matin](docs/validation/2026-10-08/codex-hour-0924/README.md).
Validation finale : 925 tests réussis avec mémoire, paquet installé de 52 modules
contrôlé avec les deux serveurs simulés. Voir le bilan pour les limites.

C-034–C-038 restent livrés : configuration explicite Ollama/llama-server,
qualification-check et model-config-check ; 886 tests avec mémoire réussis à
cette étape antérieure ([preuves](docs/validation/2026-10-08/codex-hour-0435/README.md)).
Les huit [propositions d'outillage](docs/proposals/2026-10-08-agent-toolbox.md) restent
ouvertes ; quatre [compléments dashboard/contexte](docs/proposals/2026-10-08-dashboard-context.md)
sont proposés, sans choix adopté. G072–G077 sont les six nouvelles tâches Claude,
publiées à la demande de toytoy. G064/G065 et la note outillage Claude reçus
sur e403fd2 et intégrés ; G066–G071 préservés. G064-3 corrigé dans C-042 ; contre-revue et qualification réelle ouvertes. [File active](collaboration/tasks/QUEUE.md).

### État de la séance précédente — 07/10/2026 au soir

C-030–C-033 : catalogue archives HTTP, recette recherches et planificateur Ollama
explicite en CLI. Le défaut reste déterministe, fournisseurs réels désactivés.
La rotation G063 reste isolée et en qualification G068. G066–G071 sont les six
nouvelles tâches Claude, après G064/G065 ; [file active](collaboration/tasks/QUEUE.md).

[Bilan fonctionnel et avancement](docs/PROJECT-STATUS-2026-10-07.md) : bêta
observateur estimée à 80 %, vision complète à 40 % ; estimations pondérées,
aucune qualification VM/Windows ni modèle réel revendiquée.
[Preuves de la séance](docs/validation/2026-10-07/codex-hour-1948/README.md).
Les sections datées suivantes conservent l'historique et ses limites d'origine.

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
- [x] Budget persistant des invocations par mission : C-015 ci-dessous.
- [ ] Rétention/nettoyage coordonnés des reçus, historiques et verrous ; aucun
  effacement automatique d'un état actif.
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
- [x] [C-CLAUDE-002](collaboration/tasks/C-CLAUDE-002.md) : étude 2 × V100 32 Go/NVLink
  reçue (`ec7582b`), précisions C-TASK-G003 intégrées (`a77e7cf`). Adaptateur candidat
  simulé (étape 2) intégré ; tâche de livraison Claude terminée. Qualification
  matérielle et choix Ollama différés ci-dessous ; aucun modèle réel qualifié
  et aucune activation CLI.
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
- [x] Écarts retriés via G025 ; W14/W15 reproduits sur le corpus courant.
  Une page lue n'est ni une réponse démontrée ni une source indépendante.
- [ ] F-W20 : requêtes sortantes toujours transmises au fournisseur injecté ;
  minimisation/confirmation à concevoir en G029 avant usage externe réel.
- [ ] API fournisseur réelle choisie après comparaison, sans abonnement implicite.
- [x] C-011 : extraction HTML optionnelle après transport contrôlé ; source/texte
  distincts, partiel refusé comme READ, cache/déduplication testés sans Internet.
- [x] C-002c : pauses persistantes optionnelles par fournisseur/origine, levée
  explicite versionnée, audit, CLI et démo sans réseau. [Contrat](docs/RESEARCH-PAUSES.md).
- [x] Claude G019/G020 : revues reçues dans ff51313/cc9831f. Suites corrigées :
  budget après consultation lente, capacité avant appel et diagnostic mission_id.
  [Preuves](docs/validation/2026-10-06/codex-review-followup/README.md).
- [x] Claude G024/a29bb21 reçue : contrôles de délai/parser confirmés ; deux
  suites C-G024-1/2 prises par Codex (capacité et diagnostic), sondes rejouées.
- [x] Suivi local G024 : plafond sur pauses ACTIVE, RELEASED garde révision/audit ;
  refus de capacité en précontrôle distinct d'une écriture incertaine.
  [Preuves et limites](docs/validation/2026-10-06/codex-web-availability/README.md).
- [x] Claude G023/2730744 intégré : abandon explicite d'un résultat retourné
  mais invérifiable, neuf tests reproduits ; preuves conservées, aucun appel.
  [Contrat](docs/ABANDON-UNVERIFIED.md).
- [ ] Journal préalable des appels Web en vol : interruption avant commit d'une
  pause à réconcilier avant toute reconstruction/reprise réelle du coordinateur.
- [ ] Quotas globaux et rétention du journal, artefacts persistants, intégration
  mission et critères de qualité distincts du seul nombre de pages lues.

- [x] G008 : D1 attente 429/503 ambiguë, D2 base de temps et C5 redirection
  sans destination corrigés ; dix tests nouveaux, 303 réussis / 6 sautés.
- [x] Claude G011 : contre-revue indépendante de ces correctifs.
- [x] Suites G008 C1/C4 : pas de nouveau cache après interruption ; rapport v2
  avec paramètres/fragment retirés des champs URL, empreintes distinctes.
  [Contrat et limites](docs/RESEARCH-REPORT-V2.md).
- [ ] G027 : contre-revue indépendante C1/C4, cible 2bad4e6.
- [x] G025/9147f82 reçu : 9 PASS, 7 KNOWN_GAP, 4 FINDING rapportés par Claude
  sur 6d1661d. F-W14/15 traités localement via discovery_status ; F-W07 traité
  seulement pour le comptage des corps pris en charge. L'oracle W07 « une seule
  requête » et HTML restent ouverts, archives du corpus inchangées.
- [ ] G028 : contre-revue du suivi G024/G025 ; cible publiée 8983d35 (équivalent exact du local a5dc404).
- [ ] G029/G030 : propositions de minimisation des requêtes et journal préalable,
  confiées à Claude dans la file locale, à publier après blocage du push.
- [ ] G026 : extracteur HTML autonome borné, sans raccordement au coordinateur.
- [ ] Suites G008 : L1 délai dur, L2 interruptions avant persistance (pauses commises
  couvertes par C-002c), L3 paramètres TLS,
  C2/C3 explicités dans le contrat. [Tri](docs/validation/2026-10-05/codex-g008-fixes/README.md).

### Client bureau Eidolon — propositions et recette distinctes

- [x] Huit maquettes Claude `176edac` reçues ; sources/contrats relus par Codex,
  trois comportements reproduits par sonde de logique, sans rendu visuel validé.
- [x] Claude G009 : prototype autonome reçu dans 111da40, 17 tests de logique
  reproduits ; 27 réussis rapportés par Claude (10 UI non démarrés ici, Chromium
  absent). Aucune application Windows livrée.
- [x] Claude G013 : suivi séparé des commandes incertaines livré dans deef553 ;
  28 tests Node et sonde adaptée reproduits ; 11 UI réussis rapportés par Claude.
- [x] Claude G010 : étude reçue dans 7a1c682, intégrée ; framework non choisi,
  mesures OS et installation différées.
- [x] C-008a : projection locale cohérente, curseur durable, rattrapage paginé,
  reset explicite, CLI et démo sans réseau ; 19 tests nouveaux.
- [x] Claude G012 : prototype candidat intégré depuis cc9a64b ; 42 tests de
  logique reproduits, 16 UI seulement rapportés. Trois écarts encore ouverts :
  [revue](docs/validation/2026-10-06/codex-g012-integration/README.md).
- [x] Claude G016 : trois corrections intégrées dans 1b9f7dd ; 49 tests Node
  reproduits, 18 UI rapportés. Aucune API réelle raccordée.
- [x] C-008b : reçus atomiques approve/reject/revoke locaux, consultation et
  déduplication, annulation avant commit protégée ; 22 nouveaux tests.
  [Contrat](docs/COMMAND-RECEIPTS.md). Aucun effet externe, reçu != résultat.
- [x] Claude G014 : revue reçue dans cb15c33, dix groupes de sondes reproduits
  sur cible figée 176c1d2 ; aucun nouveau défaut confirmé.
- [x] C-008c : annulation avec reçu atomique sans verrou d'exécution, sans
  runtime ; demande/arrêt/effet distingués. [Contrat](docs/CANCEL-RECEIPTS.md).
- [x] Claude G015 : revue reçue ; E1 corrigé dans 97abdb2, contre-revue G020 reçue et favorable.
- [x] Diagnostic CLI STORAGE_UNAVAILABLE pour les erreurs SQLite ; incertitude
  conservée, pas de traceback/message SQL brut.
- [x] C-008d : copie de restauration réservée à la revue, nouvelle identité,
  garde avant migration/exécution ; [contrat](docs/RECOVERY-REVIEW.md).
- [x] Claude G017 : revue reçue (4fa543d) ; E1 reproduit, copie incrémentale
  sans transaction source prolongée, garde du fichier en attente et diagnostic
  RECOVERY_INCOMPLETE livrés. [Suivi](docs/validation/2026-10-06/codex-recovery-followup/README.md).
- [x] Claude G022/c576a8d reçue et lue : aucun défaut nouveau, limites
  conservées. Sondes longues rapportées par Claude, non toutes rejouées ici.
- [x] C-008e : inventaire paginé local, projection minimale, reset entre pages
  si l'état évolue ; 18 tests et démo. [Contrat](docs/MISSION-LIST.md).
- [x] Claude G018 reçu (bfa75d2) : consommateur Desktop de mission-list/1,
  pagination/reset/sélection. 62 tests de logique reproduits ; UI rapportée par
  Claude, capture 15 inspectée. Prototype uniquement, aucun transport connecté.
- [x] G021/157db9e intégré : nombre reçu contrôlé contre le total annoncé.
  68 tests Node reproduits, sonde indépendante corrigée ; capture 19 inspectée,
  24 tests Chromium seulement rapportés par Claude.
- [ ] Reprise après restauration : inventaire des artefacts, revue des effets et
  ouvriers, activation explicite ; aucun déverrouillage livré par C-008d.
- [ ] C-008 suite : reçus run, détection de rollback hors outil de revue, quotas et
  rétention, identité/appairage, API authentifiée ;
  autorité et permissions restent dans Core. [Contrat livré](docs/CLIENT-SYNC.md).
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
  Vérification du 08/10 sur b33c3a0 : imports de conversations identiques
  recouvrantes et refus des parts mal formées confirmés via corpus synthétique.
  A5-02 reste présent à travers Core : « Ne pas acheter la V100 cette semaine. »
  devient « acheter la V100 cette semaine. » pour la requête « acheter V100 ».
  Référence exacte, UNVERIFIED, needs_review et truncated restent conservés ;
  cela ne restaure pas la négation coupée. Deux versions successives d'une même
  conversation peuvent aussi rappeler deux fois le même message. Aucun correctif
  sémantique appliqué dans Core ; [preuve reproductible](docs/validation/2026-10-08/codex-hour-0435/memory-recheck.json).
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

## Suivi G011 reçu pendant C-008b — 06/10/2026

- [x] G011/C022 (25ea564) intégré ; sondes G011 reproduites, D3 arrondi corrigé ;
  68 tests Web ciblés réussis. Les trois fichiers source Web inchangés depuis
  la cible de Claude jusqu'à la reproduction ; correction transport ensuite.
- [x] Courte contre-vérification Claude de D3 sur le commit G025 reçue dans C023.
- [ ] Propositions Claude : pause explicite après échec de parseur sans statut,
  borne du délai socket au budget restant ; à éprouver sans transformer l'échec
  de parseur en 429 observé ni promettre une échéance dure.

[Preuves de l'intégration](docs/validation/2026-10-06/codex-g011-integration/README.md).

## Audit demandé par toytoy — 06/10/2026

- [x] G015 intégré ; E1 reproduit et corrigé : vérification après annulation,
  reprise en cas d'indisponibilité, aucun nouvel outil lancé.
- [x] A06-G02/G03 : refus Web conservés malgré corps inutilisable ou panne DNS
  finale ; pauses persistantes testées sans Internet.
- [x] A06-G04 : diagnostics précis et types d'entrée des commandes contrôlés.
- [x] Dix régressions avant/après ; suite complète 431 réussis, six intégrations
  mémoire sautées. [Rapport d'audit](docs/AUDIT-2026-10-06.md).
- [ ] Contre-revue Claude des corrections ; anciennes missions CANCELLED avec
  résultat non vérifié à examiner, sans réouverture automatique livrée.

### Revue globale Claude du 06/10 — suivi hors périmètre Core

- [x] Rapport 0e65233 reçu et intégré ; pas de certification exhaustive.
- [ ] I1 Bootstrap : fins CRLF des trois installateurs, contrôle sur copies
  rapporté par Claude ; correction séparée, aucun installateur modifié ici.
- [ ] I2 Bootstrap : ajout des composants Debian non idempotent / deb822
  incomplet selon revue ; recette Debian réelle différée, périmètre séparé.
- [ ] C1 statique : chaînage explicite de trois exceptions egress et imports
  inutilisés dans les tests, mineur ; pas de correction cosmétique dans ce lot.

Voir docs/validation/2026-10-06/claude-audit-global/README.md.


## Suite bêta serveur–PC — 06/10/2026, G045

- [x] G026–G030 intégrés depuis fd4393d ; études G029/G030 non activées.
- [x] Nouvelle file Claude G031–G035, périmètres distincts.
- [x] C-009a : API loopback authentifiée de consultation, livrée/testée, publiée en 21c0f729 ; correspondances dans C-MSG-G047.
- [x] G031 : client connecté observateur intégré depuis a613dc6 ; 18 tests
  Node reproduits, deux Chromium sautés faute d’exécutable local.
- [x] G032 : durcissement extraction HTML intégré ; raccordement toujours différé.
- [x] G033 : commentaires APT et sources tierces corrigés, 23 cas reproduits.
- [x] G034/G035 : revue API et procédure Debian/Windows intégrées ; recette réelle à effectuer.

Voir docs/BETA-SERVER-PC.md. La file courante fait foi pour les prochains lots,
les anciennes files ci-dessus restent des états historiques.


## Suite C-009b — 06/10/2026

- [x] Six tâches Claude G036–G041 publiées après G031–G035 ; état dans QUEUE.md.
- [x] Consultation HTTP exacte des reçus de décision/annulation, lecture seule,
  comparaison Store/mission/événement/empreinte, historique séparé de l’état courant.
- [x] 87 tests ciblés réussis, dont 20 nouveaux ; démo HTTP réelle sur données
  synthétiques, sans exécution d’outil. [Preuves](docs/validation/2026-10-06/codex-http-receipts/README.md).
- [ ] Raccordement client G036 et validation sur serveur/PC réels.


## C-009c — diagnostic de consultation — 06/10/2026

- [x] Nouvelles fiches Claude G042–G044 publiées, anciens lots conservés.
- [x] `http_api --check` : diagnostic local JSON/humain, validateurs partagés,
  absence de création d’état/token ou d’écoute réseau vérifiée.
- [x] 57 tests Python ciblés réussis, dont 12 nouveaux.
- [x] G035 : diagnostic intégré à la recette.
- [ ] G040 : intégrer le diagnostic au lanceur candidat.

Voir docs/HTTP-PREFLIGHT.md et docs/validation/2026-10-06/codex-preflight/.


## Séance du 06/10 au soir — C-009d et intégration

- [x] G032/G033 intégrés depuis 6f8b695 ; 24 tests HTML, 23 cas APT
  reproduits sans exécuter les installateurs.
- [x] Création de jeton local privé sans écrasement, publication complète,
  erreurs après publication distinguées de l’absence de création.
- [x] 52 tests ciblés du lot jeton/préflight/API réussis (15 nouveaux jeton).

Publication groupée à la clôture de la séance ; documentation READ-TOKEN.md.

- [x] C-009e : préconnexions non bloquantes, quatre workers au plus,
  échéance totale de lecture ; D-G034-1 reproduit puis corrigé.
- [x] C-009f : capture liée à l’identité SQL, projections typées/bornées ;
  deux défauts reproduits puis corrigés, 91 tests ciblés verts.
- [x] G034/G035 reçus et intégrés ; preuves Claude préservées et limites
  VM/Windows maintenues.
- [x] C-009g : six missions synthétiques et trois reçus reproductibles,
  création isolée, diagnostic bloquant un jeu incomplet ; huit tests dédiés.
  Contrat et parcours : docs/BETA-FIXTURE.md.
- [x] Validation finale : 608 tests Python réussis, six intégrations mémoire
  non exécutées ; 24 contrôles de recette Linux temporaire ; 18 tests client
  connecté réussis, deux Chromium ignorés. Détails et limites dans
  docs/validation/2026-10-06/codex-evening/README.md.

## Suite C-011 — 07/10/2026

- [x] Option HTML explicite sur WebReader, identité versionnée des limites.
- [x] Intégration au coordinateur candidat, conservation des empreintes source/texte,
  refus du partiel et des signaux d'accès, déduplication du texte HTML extrait.
- [x] Tests sur doubles et vrai HTTP loopback, aucune ressource embarquée suivie.
- [ ] Contre-revue indépendante du raccordement ; fournisseurs externes, maîtrise
  des requêtes sortantes et permissions de mission restent des lots distincts.

Suite Claude G045–G047 publiée après G042–G044. [Preuves C-011](docs/validation/2026-10-07/codex-html/README.md).

## Intégration G042–G044 et C-012 — 07/10/2026

- [x] G043 : fraîcheur sur réponses acceptées, BUSY distinct, reçus historiques
  ne rafraîchissant pas la capture ; 48 tests connectés reproduits, 12 Chromium ignorés.
- [x] G044 : générateur de sources à partir d'un commit figé, manifeste et
  reproduction ; vérificateur durci par Codex (doublons, taille/mode, manifeste incomplet).
- [x] G042-1 reproduit puis corrigé pour les nouveaux reçus avec empreinte
  dans l'événement, transaction commune ; anciens reçus signalés LEGACY_FIELDS.
- [x] Affichage client receipt_binding : G048 intégré ; C-017 refuse le retrait
  isolé du hash après le seuil durable. Les anciens restent limités.
- [x] G045–G049 intégrés et corrections documentées ; file remplacée par G050–G053.

[Preuves et limites](docs/validation/2026-10-07/codex-g042-g044/README.md).

## C-013 — nettoyage local des requêtes — 07/10/2026

- [x] C-D10 rapportée dans C061 : motifs personnels reconnus retirés localement
  avant tous les fournisseurs/replis du coordinateur candidat.
- [x] Requête devenue vide sans émission ; reçus sans texte et limites documentées.
- [x] 77 tests ciblés et 27 cas du corpus synthétique G029 inspectables.
- [x] C-D13/15/16 : requêtes humaines/modèle nettoyées automatiques, catégories
  actuelles conservées. Décisions rapportées par Claude C067–C069.
- [x] Conservation locale du texte nettoyé avant émission (C-D15) : C-019.
- [ ] Raccordement fournisseur et couverture des données non reconnaissables ; aucun fournisseur réel activé.

Contrat : [QUERY-CLEANUP.md](docs/QUERY-CLEANUP.md). G045 reçu ; limites SQL
consolidées, variante de libération anticipée non adoptée.

## C-014a — garde de recherche interrompue — 07/10/2026

- [x] Intention durable autour de la recherche complète, verrou POSIX, refus
  de reprise tant que l'incertitude n'a pas été revue explicitement.
- [x] Revue versionnée, CLI sans relance/création implicite, tests de crash
  réels et HTTP loopback ; journal borné sans contenu privé des requêtes.
- [ ] G030 complet : journal par appel/saut, scopes et fin/pause atomiques
  dans une base commune. C-014a utilise un blocage global plus prudent.
- [ ] Rétention, restauration/rollback et raccordement mission/réseau réel.

Contrat et limites : [RESEARCH-GUARD.md](docs/RESEARCH-GUARD.md).

## C-015 — budget global d'invocations — 07/10/2026

- [x] Limite persistante par mission (64 par défaut), réservation avant worker,
  audit transactionnel, reprise/réconciliation sans remboursement.
- [x] Place pour une première vérification avant de démarrer un outil ; preuves
  conservées si vérification indisponible et budget épuisé.
- [x] CLI, configuration figée, compatibilité historique explicitement sans budget,
  79 tests ciblés réussis. Contrat : docs/INVOCATION-BUDGET.md.
- [ ] Quotas globaux de serveur, rétention et nettoyage coordonnés restent ouverts.

## C-016–C-018 — retours des revues

- [x] SIGINT/SIGTERM : recette interrompue proprement, descendants possédés arrêtés.
- [x] Seuil transactionnel de hash requis pour les nouveaux reçus.
- [x] Titres HTML non diluables par SVG/second titre, premiers attributs dupliqués,
  détection des préfixes HTML mal étiquetés. Extracteur version 2.
- [x] C-020 : titres de challenge Unicode et déduplication texte brut avec BOM corrigés.
- [ ] Limites connues : heuristique HTML non exhaustive, identité Stop PowerShell
  Linux ; aucune tolérance temporelle dangereuse adoptée pour les PID.

## C-019 — historique local nettoyé — 07/10/2026

- [x] Texte/reçu/intention dans une transaction, aucun hash brut exporté.
- [x] Schéma 2 explicite, ancien texte non inventé, garde obligatoire après activation.
- [x] Pagination bornée avec reset sur modification, CLI locale seule.
- [x] 71 tests ciblés ; suite 713 réussis/6 ignorés puis six intégrations mémoire réussies.
- [x] Raccordement au runtime sur fixtures uniquement : C-021.
- [ ] Rotation explicite (G057), journal par saut, fournisseurs réels et recette VM.


## C-021 — missions de recherche synthétique — 07/10/2026

- [x] Profil CLI `research-sim`, objectif fixé hors modèle et lié à la mission.
- [x] Nettoyage/historique/pauses, exécution et vérification intégrés au runtime.
- [x] Partiel/vide conservés sans succès ; reprise sans répétition de la recherche.
- [x] Journal occupé : vérification différée, preuves reçues conservées.
- [x] 18 tests dédiés ; 733 Python réussis/6 ignorés puis six intégrations mémoire réussies.
- [x] Wheel isolé : 42 modules identiques, 24 contrôles bêta et mission de deux pages.
- [ ] Contre-revue indépendante, rotation G057, permissions et fournisseurs réels.

Contrat [RESEARCH-MISSIONS.md](docs/RESEARCH-MISSIONS.md),
[preuves](docs/validation/2026-10-07/codex-research-runtime/README.md).


## C-022 — diagnostic local de reprise — 07/10/2026

- [x] Capture mission/budget bornée, lecture seule sans Store/Runtime.
- [x] Sondage des verrous/reçus existants, aucune création ni permission de reprise.
- [x] Changement pendant sondage signalé, requête/contexte/résultats non exportés.
- [x] 62 tests ciblés réussis, dont 15 nouveaux et un détenteur de verrou séparé.
- [ ] Revue indépendante, qualification VM ; pas de détection universelle d’orphelin.

[Contrat](docs/RUNTIME-INSPECTION.md), [preuves](docs/validation/2026-10-07/codex-runtime-inspect/README.md).


## C-023/C-024 — suivis G055/G056 — 07/10/2026

- [x] G055 et G056 intégrés avec preuves originales ; G057–G060 restent à traiter.
- [x] CSP/Referrer-Policy aussi sur saturation BUSY : écart reproduit, 68 tests HTTP/reçus réussis.
- [x] Budget : seules réservations décodées, tous les ordinaux contrôlés ; six sondes d’altération conservées.
- [x] Mesures synthétiques avant/après et 47 tests budget/diagnostic/recherche réussis.
- [ ] Qualification VM/Windows ; la réécriture cohérente reste hors détection.


## C-025 — inspection historique stricte — 07/10/2026

- [x] Métadonnées contradictoires et mauvais type reproduits, puis refusés sans affichage trompeur.
- [x] Clés/types/identités et indicateurs de revue validés, anciens rapports conservés.
- [x] Lecture bornée en taille/nombre/durée coopérative, aucune réparation ni réactivation.
- [x] 47 tests ciblés réussis, dont dix nouveaux et une interruption réelle de requête SQL.
- [ ] Inventaire paginé pour grandes copies, contre-revue et qualification du stockage réel.

[Contrat](docs/RECOVERY-REVIEW.md), [preuves](docs/validation/2026-10-07/codex-recovery-inspection/README.md).


## C-026/C-027 — parcours opérateur et consultation CLI — 07/10/2026

- [x] Guide DIAGNOSTIC-WORKFLOW : interpréter les états sans déduire un droit de reprise.
- [x] Mutations de consultation reproduites, trois commandes CLI passées à ReadOnlyStore.
- [x] 59 tests ciblés réussis dont six nouveaux ; protocoles/pagination inchangés.
- [x] Refus sans réparation des anciens schémas, tables manquantes et états bêta incomplets.


## C-028 — lecteur d’archives et liste.md — 07/10/2026

- [x] G057 intégré comme prototype isolé ; trois défauts de reprise reproduits.
- [x] G062 confié à Claude : corriger conservation/reprise et préparer l’automatisme C-D17.
- [x] Lecteur strict des exports, chaîne, événements et textes nettoyés liés.
- [x] Catalogue local privé, sans requêtes exportées ni statut de commit présumé.
- [x] Génération atomique et idempotente de liste.md ; fichiers manuscrits refusés.
- [ ] Rotation automatique à cible 100 avec preuves des missions protégées.
- [ ] Consultation Desktop via projection Core authentifiée, sans accès fichiers Tauri.


## C-029 et réception G058–G062 — 07/10/2026

- [x] Identité de garde liée au Store, adoption des missions existantes sans réécriture.
- [x] Dossiers, garde et pauses manquants/incomplets refusés sans recréation.
- [x] Quinze nouveaux tests d'initialisation ; 72 tests associés réussis.
- [x] G060 : libellés de recherche intégrés au client ; récupération distinguée de vérité.
- [x] Compatibilité du lecteur avec released_operations G062, vingt tests dédiés.
- [ ] G063 : corriger écritures courtes et nettoyage prématuré du prototype.
- [x] G064 : contre-revue reçue et intégrée (e403fd2) ; suivi C-042 ouvert.
- [x] G065 : diagnostics budget et mission historique inconnue intégrés (7b4cb2f).


## C-030 — catalogue archives pour le client — 07/10/2026

- [x] POST authentifié, métadonnées uniquement, pagination liée à la capture.
- [x] Reset sans mélange après changement de catalogue ou de Store.
- [x] Option locale explicite, diagnostic --check et erreurs privées constantes.
- [x] Un lecteur à la fois, budget coopératif et limites C-028 conservées.
- [x] 73 tests associés réussis, dont 15 nouveaux tests d'API et de non-mutation.
- [ ] G066 raccordement client, G071 contre-revue de l'API.


## C-031 — jeu synthétique de recherches pour la bêta — 07/10/2026

- [x] Profil beta_fixture research-archives : trois recherches via le vrai runtime synthétique.
- [x] Copies d'exports liées, catalogue et liste.md ; trois preuves actives conservées.
- [x] Jeton privé, manifeste explicite, destination exclusive et marqueur d'incomplétude.
- [ ] Recette sur le serveur et le PC Windows de toytoy.


## C-032 — planificateur Ollama explicite en CLI — 07/10/2026

- [x] --model-config pour demo/create/run du profil text, aucun choix implicite.
- [x] Fichier privé et borné, JSON strict, endpoint loopback littéral et sortie bornée.
- [x] Création sans appel, reprise liée à la configuration et refus des outils hors profil.
- [x] Neuf nouveaux tests, 23 tests du raccordement/adaptateur réussis sur faux HTTP local.
- [ ] Qualification d'un vrai modèle et GPU, chat généraliste et autres adaptateurs CLI.


## C-033 — recette automatique recherches/archives — 07/10/2026

- [x] Profil research-archives : 25 contrôles, trois recherches et consultation authentifiée.
- [x] Pagination/reset, preuves actives inchangées, jeton et reprise serveur vérifiés.
- [x] Échec de requête nettoyé, fichiers étrangers préservés ; huit tests de recette passent.
- [x] Les 24 contrôles du profil initial restent inchangés.

## C-034 — Frontières du planificateur Ollama — 08/10/2026

- [x] Réponses ambiguës, scalaires invalides et réflexion de texte d'erreur reproduits.
- [x] JSON strict, paramètres bornés partagés, erreurs distantes non recopiées.
- [x] Manifeste version 2 ; reprise sous ancien contrat bloquée sans réécriture.
- [x] Dix nouveaux tests ; 68 tests des adaptateurs/configuration/intégration réussis.
- [ ] Qualification modèle/GPU et contre-revue indépendante.

## C-BRAIN-G012 — Outillage des futurs agents — 08/10/2026

- [x] Huit propositions Codex, trois options et corpus comparatif documentés.
- [ ] Contribution Claude à recevoir plus tard, puis arbitrage toytoy.
- [ ] Implémentation des options retenues seulement après choix ; aucun outil activé.

## C-035 — vérification de rapports hors ligne (08/10/2026)

- [x] Commande `qualification-check --report`, sorties JSON/humaine et codes 0/2/3.
- [x] Lecture bornée, refus FIFO/liens finaux, mutation détectée, aucun runtime.
- [x] 32 tests du validateur et de la CLI ; aucune télémétrie réelle qualifiée.
- [ ] Collecte matérielle réelle et décision de qualification avec preuves externes.

## C-036 — candidat llama-server explicite en CLI — 08/10/2026

- [x] Choix provider dans la configuration privée, limites communes et options distinctes.
- [x] Nom de variable de clé facultatif ; aucune clé littérale dans le fichier ou le manifeste.
- [x] 11 nouveaux tests, 32 avec chargeur Ollama et CLI qualification.
- [ ] Qualification réelle du contrat à la version du moteur installé ; aucun moteur retenu.

## C-037 — cadrage HTTP des planificateurs — 08/10/2026

- [x] Coupure malgré JSON valide, en-têtes ambigus et erreurs de corps HTTP reproduits.
- [x] Lecture commune bornée, diagnostic sans texte distant, aucun retry automatique.
- [x] Manifestes /3 ; missions antérieures refusées à la reprise sans migration implicite.
- [ ] Contre-revue indépendante et qualification avec les moteurs réels retenus pour essai.

## C-038 — diagnostic de configuration locale — 08/10/2026

- [x] model-config-check affiche manifeste et identifiant sans réseau, état ni valeur de clé.
- [x] JSON/humain, codes 0/2 ; ne transforme pas une syntaxe valide en qualification de modèle.
- [x] Cinq tests nouveaux, dont accès à la variable de clé interdit pendant l'inspection.
- [ ] Essai serveur réel distinct, choisi explicitement par l'opérateur.


## C-039 — instructions des planificateurs (08/10/2026 matin)

- [x] Outil text.stats, paramètres, format des références et couverture explicités.
- [x] Même contrat statique pour les deux candidats, hors du contexte non fiable.
- [x] Empreinte des variantes et de leur sélection ; manifestes /4 et reprise incompatible refusée.
- [ ] Comparer l'adhésion au contrat sur les vrais modèles retenus pour essai.

## C-040 — recette reproductible des planificateurs

- [x] Corpus fixe : source simple, Unicode/deux références, instruction dans les données, mémoire vide.
- [x] Préparation hors ligne ; exécution explicite dans un dossier privé neuf ; critères enregistrés avant appels.
- [x] Résultats indépendants du plan, réserves des sources conservées, reprise terminée sans réémission.
- [x] Arrêt dès erreur technique, aucune reprise implicite ; bilans et états partiels conservés.
- [x] Tests HTTP synthétiques et paquet installé ; erreurs, permissions, reprises et panne de publication.
- [ ] Essai réel serveur/GPU et protocole avancé : contexte utile, stabilité, vitesse, consommation.

## C-041 — consultation hors ligne d'une recette

- [x] Schémas, empreintes, ordre/comptes des cas et cohérence du rapport vérifiés sans Runtime/Store.
- [x] Marqueur d'incomplétude prioritaire ; cas non enregistrés potentiellement commencés.
- [x] Lecture bornée sans liens finaux/FIFO, diagnostics constants et aucun appel réseau.
- [ ] Contre-revue indépendante complémentaire dans G075 ; cohérence documentaire distincte de preuves SQLite/matériel.

## C-BRAIN-G013 — compléments de produit

- [x] Accueil missions, carte de reprise expliquée, activité locale progressive et outils par mission proposés.
- [ ] Études Claude G076/G077 puis comparaison/arbitrage toytoy ; aucune collecte activée.

## C-042 — suivi prioritaire G064 — 08/10/2026

- [x] Lier l'identité de pauses.sqlite3 au Store, refuser un remplacement valide
  mais étranger ; définir la reprise explicite des bases existantes sans accepter
  silencieusement une nouvelle identité. Tester coupures à chaque publication,
  restauration et concurrence, conservation des pauses/audits, aucune relance.
- [x] G064-2 : libellé de cohérence « à la génération », préserver idempotence.
- [x] G064-1 : limite du verrou coopératif documentée.
- [x] G064-4 : normaliser les erreurs SQLite de construction Python ; la CLI
  normalise déjà STORAGE_UNAVAILABLE. Les sondes complètes Claude restent
  rapportées ; G064-3 seul a été reproduit indépendamment dans cette séance.

La revue G064 reste conservée intacte. Les corrections C-042 et leurs nouveaux
tests sont distincts de cette revue. [Migration et limites](docs/PAUSE-BINDING.md).
- [x] Migration explicite auditée, sans création de Store ni levée des pauses.
- [x] Reprise après coupure entre les bases par revue explicite ; intents conservés.
- [ ] Contre-revue indépendante et recette sur le stockage réel de toytoy.

## C-043–C-045 — parcours opérateur et revue G067 — 08/10/2026

- [x] C-043 : `research --create-only` retourne 0 pour une création NEW sans appel.
- [x] C-043 : levée des pauses research-sim liée aux identités Store/garde/pauses.
- [x] C-044 : diagnostic `research-binding-inspect`, trois identités observées,
  pas de création, migration, levée ni permission de reprise.
- [x] G066 : client archives reçu (d87b6d2), intégré et tests Node reproduits.
- [x] G067–G069 : revues/recette/prototype reçus depuis 97770f5 ; contributions conservées.
- [x] C-045 / G067-1 : refus WAL avant les consultations concernées, sans fichiers annexes.
- [x] C-045 / G067-2/4 : lectures mission/ancres bornées en SQL à 16 Mio,
  texte UTF-8 explicite ; rattrapage sans chargement de chaque détail d'événement.
- [ ] G067-3 : distinguer stockage occupé et indisponible dans le protocole HTTP,
  à coordonner avec les états client ; refus STATE_UNAVAILABLE conservé ici.
- [ ] G068 : aligner les limites producteur/lecteur avant intégration de la
  rotation ; pas d'activation automatique par la réception du prototype.


## C-046 — bornes du prototype de rotation (08/10/2026 après-midi)

- [x] Producteur relu par le lecteur Core ; bornes de taille/nombre/volume
  appliquées avant publication et retrait. Horodatage JS strict.
- [x] Budget coopératif de copie SQLite, fermeture sur refus, identité/schema
  revérifiés dans la transaction finale.
- [x] Corpus synthétique : quotas, export orphelin, mutations après publication,
  quatre frontières de coupure, WAL et restauration réversible.
- [ ] Contre-revue indépendante G080 ; intégration schéma 3 et déclenchement réel.

Logo programme officiel publié, décision dans assets/branding/LOGO.md.
G078–G083 attribués à Claude après G072–G077 ; aucune session présumée lancée.


## C-047/C-048 — Agents natifs Image/Vidéo (08/10/2026, soir)

Décision directe toytoy : créer, modifier ET analyser depuis l'accueil.
[Contrat et installation](docs/MEDIA-AGENTS.md).

- [x] Accès Image/Vidéo et brouillons locaux, sans upload ni faux résultat.
- [x] Deux agents livrés dans le paquet, commande eidolon-media, six opérations.
- [x] Adaptateurs locaux ComfyUI/Ollama Vision et extraction FFmpeg bornée.
- [x] Intention durable avant appel, retour incertain sans renvoi automatique.
- [x] Installation isolée et recette CLI sur API loopback simulées.
- [ ] Moteurs/poids/workflows réels et qualification sur le serveur.
- [x] Artefacts locaux contrôlés et collecte explicite des octets de résultats (C-049/C-051).
- [ ] Upload navigateur authentifié et validation métier des résultats.
- [ ] Outils média raccordés au worker/catalogue de missions, budgets GPU partagés.
- [ ] Exécution depuis l'accueil avec identité/droits de commande distincts.
- [ ] Analyse vidéo longue/son, rétention et galerie persistante.

**Chat/conversation/mission entièrement confié à Claude : G084–G089**, priorité
après son lot engagé. Codex conserve agents média ; aucune session présumée lancée.

## C-049/C-050/C-051 — Fichiers et résultats des agents média (09/10/2026)

Six suites Claude G090–G095 publiées, G084–G089 prioritaires pour le chat/mission.
[Contrat média et référence G094](docs/MEDIA-AGENTS.md).

- [x] Magasin privé, références opaques, quotas, empreintes à la lecture, verrou écrivain.
- [x] Import atomique et inspection des lots interrompus ; publication explicite des seuls lots complets revérifiés.
- [x] Upload local ComfyUI facultatif, reçu strict et comparaison de la source distante avant soumission.
- [x] Étapes durables, coupures sans renvoi et consultation du reçu accepté avant interruption.
- [x] Collecte bornée des sorties, historique lié au workflow, provenance et imports partiels inspectables.
- [x] Export local complet vers un nouveau fichier privé, sans remplacement ni lien au contenu interne.
- [x] Six modes exercés depuis le paquet installé, transport HTTP réel et moteurs simulés.
- [ ] Qualification de ComfyUI/Ollama réels, poids et nœuds sur matériel cible.
- [ ] Contrat d'autorisation conversation/mission et upload navigateur : coordination G094.
- [ ] Budgets GPU communs, rétention, galerie, validation sémantique et lecture vidéo longue/son.

Les références d'artefacts ne sont pas des permissions et les états média ne
deviennent pas des reçus `SUCCEEDED` du runtime. Aucun appel moteur depuis l'accueil
ou nouveau droit sur le jeton de lecture. [Preuves](docs/validation/2026-10-09/codex-hour-0710/README.md).

## C-052/C-053/C-054 — Précontrôle et intégration (09/10/2026, matin)

- [x] Suivi Git Claude corrigé : vraie tête C103 `ccf9a9e` intégrée, G072–G079 reçus.
- [x] C104 reçu en cours de séance : G084 intégré sans modification, 23 tests
  reproduits ; icône simplifiée 32 px choisie par toytoy intégrée/reproduite.
- [x] Six nouvelles tâches G096–G101 publiées ; G084–G089 restent prioritaires.
- [x] Précontrôle média hors ligne et sondes de métadonnées locales explicites,
  sans prompt/source envoyé ni inférence ; diagnostic sans autorité d'exécution.
- [x] Logo G078 raccordé au serveur et au client ; asset facultatif dans le bundle.
- [x] Retrait des boutons de commande média désactivés signalés par C103,
  remplacés par une indication statique ; invariant de lecture conservé.
- [x] Gros TEXT SQLite lus via API incrémentale après contrôle de longueur,
  correction de l'allocation native signalée par C102.
- [x] Recette des six modes depuis paquet installé, avec précontrôles sans réseau
  puis sondes de métadonnées ; sources originales supprimées avant exécution.
- [ ] Rejouer les tests Chromium sur une machine dotée du navigateur.
- [ ] Qualification moteurs/poids/matériel réels et raccordement mission selon Claude.

Les preuves et limites sont conservées dans
[le bilan de cette session](docs/validation/2026-10-09/codex-hour-0833/README.md).

## C-055 — Suites de contre-revue G072/G073 (09/10/2026)

- [x] G072/G073/G074 rejoués sur la source courante, aucun échec de leurs attentes.
- [x] Écart G073-1 corrigé : critères fixés au même instant que le début refusés,
  y compris avec fuseaux différents ; antériorité d'une microseconde acceptée.
- [x] Guide CLI précisé sur délai socket versus budget total du worker (G072-2).
- [ ] G072-1 : diagnostic EOF d'en-tête tronqué ; refus déjà correct, libellé à améliorer.
- [ ] Remarques G074 et diagnostic de sortie tronquée G075 conservés pour suivi.
