# Architecture Core v0.1

Ce document décrit la tranche implémentée. La cible élargie d'assistant résident,
d'accès Internet/LAN et de clients distants est consignée dans le
[cadrage consolidé](CADRAGE-DECISIONS-2026-10-05.md). L'absence d'outil réseau dans
la démo actuelle n'est pas une exigence de fonctionnement hors ligne du produit.

## Responsabilités

| Module | Contrat |
| --- | --- |
| `contracts` | JSON borné, références et réserves mémoire, plan strict v1 |
| `objectives` | Catalogue restreint hors modèle, liaison au rappel et couverture des preuves |
| `targets` / `diagnostics` | Catalogue, permissions par cible et observation synthétique C-004a |
| `model` | `Model.propose(request, context) -> str`, simulateur déterministe |
| `memory` | `MemoryReader.recall(query) -> dict`, fixture ou délégation au vrai moteur |
| `tools` | Registre de code de confiance, validateurs, politique fixe, vérificateurs |
| `simulation` / `actions` / `approvals` | Service fictif transactionnel, préconditions, décisions locales liées à une tentative |
| `store` | SQLite : snapshot et événement dans une transaction, contrôle de révision |
| `worker` | Appels en processus spawn, délais, interruption, reçu JSON borné |
| `runtime` | Mission, plan, précontrôle intégral, exécution séquentielle, reprise |
| `cli` | Création, exécution/reprise, inspection, annulation et réconciliation |

## Mission et progression

Identifiant UUID stable `m-…`, requête d'origine conservée, configuration figée.
Statuts : NEW, RUNNING, BLOCKED, REVIEW_REQUIRED, SUCCEEDED, FAILED, CANCELLED,
ABANDONED (clôture avec effet inconnu conservé).
Phases distinctes : RECALL, PLAN, READY, EXECUTING, VERIFY, DONE.
La progression compte les étapes **vérifiées**, pas celles promises ou démarrées.
Les appels portent `mission_id/step_id`, numéro de tentative, versions de l'outil
et du vérificateur, empreintes du contexte et du résultat.

Le modèle propose uniquement `{"version":1,"steps":[...]}` ; 1 à 5 étapes,
identités uniques, paramètres objets, clés inattendues/dupliquées et nombres non
finis refusés. La profondeur JSON du plan est bornée à 32 conteneurs avant
parsing, indépendamment de la limite de récursion Python. Aucun champ modèle
« success », « permission » ou instruction
mémoire ne constitue une autorisation. La sortie brute est conservée avant
validation pour diagnostic, dans les limites de taille.

Le précontrôle autorise **toutes** les étapes et valide leurs paramètres avant
le premier outil, puis recommence lors d'une reprise. La politique autorise
uniquement les noms configurés **et** les outils déclarés sans effet. Le modèle
ne peut pas modifier le registre ni cette politique. Les paramètres de
`text.stats` contiennent uniquement une référence à l'extrait persisté.

L'objectif est établi hors modèle dès la création : seul le texte exact de la
mission synthétique est reconnu dans C-001a. Après rappel, le code fige toutes
les références et l'empreinte du contexte. Le précontrôle exige exactement un
appel text.stats par référence. L'[évaluateur de mission](MISSION-CONTRACT-C001A.md)
recalcule `outcome` à chaque enregistrement à partir des preuves d'étapes ; le
passage SUCCEEDED exige aussi ACHIEVED. L'objectif ne vient jamais du plan.
Pour cette mission de statistiques, une mémoire vide bloque avant le modèle et peut être rappelée lors d'un `run`
explicite. Ce catalogue n'est pas encore une compréhension générale de la demande.

C-004a ajoute une intention explicite `create_diagnostic(cible)` : résolution
hors modèle, catalogue figé, permission cible/capacité, observation synthétique
datée et vérifiée. La santé DOWN est un résultat possible d'une mission réussie.
Un rappel vide est ici un contexte valide, jamais une preuve de santé.
[Contrat détaillé et limites](SYNTHETIC-DIAGNOSTIC-C004A.md).

C-005a ajoute `ActionRuntime` et une politique séparée pour le seul outil de
mutation `service.restart.simulated`. L'effet et son reçu sont transactionnels
dans une base synthétique ; aucune capacité d'administration réelle n'est exposée.
La proposition persiste sans TTL, l'accord consommé est enregistré avec le
lancement. Une comparaison état/révision dans la transaction couvre la course
entre contrôle préalable et modification. Le reçu et l'accord sont nécessaires
au succès. [Contrat C-005a](SIMULATED-ACTIONS-C005A.md).

## Persistance et reprise

SQLite `synchronous=FULL`, schéma versionné 1, transaction unique par transition
et événement. Un verrou POSIX non bloquant par mission exclut deux exécutants
coopératifs. Une demande d'annulation est une transaction séparée, possible
pendant l'appel ; elle ne peut pas être effacée par un snapshot périmé. Le
dernier passage SUCCEEDED vérifie cette demande dans la transaction.

| Frontière persistée | Reprise |
| --- | --- |
| Rappel/plan sans appel démarré | Relire/replanifier si nécessaire, sinon utiliser le snapshot sauvegardé |
| STARTED, pas de reçu | REVIEW_REQUIRED ; aucune répétition automatique |
| RETURNED, reçu durable | Refaire la vérification, aucun appel outil |
| VERIFIED | Conserver les preuves et passer à l'étape suivante |
| SUCCEEDED / FAILED / CANCELLED / ABANDONED | Retourner l'état terminal sans nouvelle exécution |

Le journal distingue l'intention d'appel, le reçu retourné et la validation.
Une intention persistée peut précéder un appel qui n'a jamais démarré. Le choix
conservateur est de demander une revue dans cette fenêtre aussi. Après un arrêt
brutal du parent, un exécutant enfant peut subsister. Il prend un verrou propre
à l'appel/tentative avant son signal « prêt ». Le parent persiste
`WORKER_SPAWNED` (PID, horodatage), puis donne le signal d'exécution. Sans ce
signal, la fermeture du tube empêche l'appel. `no-effect` et `observed-result`
prennent le même verrou, sans attente, jusqu'à l'enregistrement de la décision ;
un enfant vivant qui détient ce verrou empêche donc la reprise. PID et horodatage
servent au diagnostic, pas à une autorisation susceptible de réutilisation de PID.
Les appels sans protocole de verrou ne peuvent pas activer de reprise ;
`abandon` permet leur clôture honnête. Aucune promesse exactly-once.

Après un délai/annulation pendant l'outil, Core arrête son processus enfant et
conserve REVIEW_REQUIRED ; un arrêt local ne démontre pas l'absence d'effet chez
un futur service distant. Le runtime ne fournit aucun outil externe dans v0.1.
L'annulation n'est ni un rollback ni une suppression des preuves déjà obtenues.

Avec `lease-v2`, l'enfant écrit et synchronise `authorized` dans le fichier
verrouillé avant d'entrer dans le fournisseur. Il publie le reçu borné par
écriture complète, synchronisation et renommage à côté du verrou, dans le
dossier d'état de la mission. Le chemin dépend de l'identifiant d'appel et du
numéro de tentative. Ces reçus restent présents après la mort du parent ; la
réconciliation les lit sous le verrou et les rattache à SQLite. L'absence d'un
marqueur pour `lease-v1` reste inconnue, pas assimilée à « jamais autorisé ».
Pas de qualification de résistance à une coupure électrique ; sauvegarder le
dossier d'état complet sans déplacer ni effacer un état actif.

Le parent lit le reçu aussi après arrêt/jonction sur délai ou annulation :
`late_receipt` est conservé sans valoir résultat vérifié. Une erreur normale est
`error_receipt` et une récupération après interruption `recovered_receipt`.
Un reçu positif interdit `no-effect`. `use-receipt` sélectionne sa valeur exacte,
la marque `worker_receipt_reconciliation`, puis exige toujours le vérificateur.
Une sortie humaine contradictoire est refusée avant adoption ; une sortie
humaine concordante garde l'origine `human_reconciliation`.

Une erreur d'outil ne prouve pas l'absence d'effet. Un appel autorisé ou inconnu
exige une attestation distincte `confirm_no_effect` après investigation, y compris
avec un reçu d'erreur. Un reçu positif interdit toujours la relance.
L'ancienne tentative et ses reçus sont archivés dans `attempt_history` avant
incrémentation, sans relance automatique. Le seul verrou libre ne donne plus
accès à une nouvelle tentative quand un reçu positif existe localement.

Si le parent sait n'avoir envoyé aucune permission et a arrêté/joint l'enfant,
une annulation devient CANCELLED, un défaut de lancement BLOCKED ; l'appel
est préparé pour une tentative ultérieure explicite. Une mort brutale du parent
reste conservativement en revue. Rappel/modèle/vérification utilisent encore
des reçus temporaires ; leurs dossiers orphelins n'ont pas de nettoyage automatique.

Une exception inattendue recharge l'état durable, journalise `INTERNAL_ERROR`
et bloque ; si la phase persistée est EXECUTING, elle exige une revue. Si le
stockage lui-même reste indisponible, cette journalisation ne peut être garantie
et l'erreur remonte. KeyboardInterrupt/SIGKILL ne sont pas convertis en succès.
Une panne/délai du fournisseur modèle reste reprenable ; une sortie invalide
est un échec terminal distinct. `abandon` clôt l'orchestration sans nier l'effet
inconnu et sans promettre d'arrêter un exécutant survivant.

Les preuves finales référencent les appels et leurs empreintes, sans copier les
sorties, et portent l'origine du reçu. Les empreintes des sorties sont recalculées
avant succès ; c'est un contrôle de cohérence, pas une signature protégeant contre
un acteur qui modifierait à la fois le résultat et son empreinte. La limite de
1 Mo porte sur chaque reçu, pas sur leur liste cumulée.
Les cinq sorties restent dans le snapshot de mission SQLite (au plus environ
5 Mo hors contexte/métadonnées) ; externaliser les médias en objets adressés par
empreinte reste un chantier ultérieur, pas une fonctionnalité livrée.

Après WORKER_SPAWNED, la réconciliation exige le fichier verrou existant ; son
absence bloque au lieu de recréer un inode vide. L'abandon reste disponible.
La récupération d'un reçu peut être persistée avant le refus d'une décision :
le journal conserve alors cette observation sans activer de nouvelle tentative.

## Mémoire et vérité

Core conserve le bundle complet, sans filtrer provenance, temporalité, relations,
statuts, confiance, troncature, références ou avertissements. Une source reste
une donnée non fiable, distincte de l'instruction utilisateur. Une mémoire vide
n'est pas une preuve d'absence ; la mission de démonstration ne peut réussir
sans au moins un résultat vérifié. Une mémoire indisponible bloque avant le plan.

L'adaptateur appelle l'API Python `ContextualRecall` sur une racine explicite ;
il ne reproduit ni stockage ni classement ni readiness. Pas d'API HTTP imaginée.
La future écriture devra passer par `FilesystemInformationWrites` ou les parcours
qualifiés `RoutingExecutor`, avec commandes/IDs stables et leurs propres reprises.
Aucun accès direct aux fichiers canoniques en écriture n'est fourni ici.

Les copies de contexte et les reçus dans SQLite sont des traces Core, pas de
nouvelles Informations confirmées. La réconciliation humaine arbitre la reprise
d'un appel ; elle ne change jamais les statuts épistémiques. Aucun mécanisme
d'expiration des propositions ni de conversion du silence en décision.

## Portée des preuves

Le vérificateur recalcule les statistiques des octets/du texte conservés ; une
fausse sortie ne passe pas. L'empreinte lie la preuve à ce snapshot. Elle ne
prouve ni l'actualité future de la source, ni la justesse de son interprétation,
ni que la mission naturelle quelconque serait satisfaite par le plan choisi.
La demande admissible est bornée par le code à ce calcul indépendamment du
modèle. La couverture vérifiée concerne toutes les références du rappel conservé.
Un futur modèle généraliste demandera d'autres types et critères d'acceptation ;
C-001a ne qualifie pas les scénarios A–D complets.

## Limites assumées

- Linux/POSIX, écrivains coopératifs, stockage local ; pas de validation NFS,
  Windows natif, coupure électrique ou corruption/adversaire modifiant SQLite.
  Ne pas déplacer/copier l'état actif ni supprimer ses fichiers de verrou pendant
  une exécution : l'exclusion repose sur les mêmes fichiers locaux. Un verrou
  libéré n'atteste pas l'absence d'effet distant ou d'un processus descendant.
- Fournisseurs Python de confiance ; isolation de processus sans sandbox OS,
  quota mémoire/CPU ou cloisonnement réseau. Les bornes limitent les réponses
  JSON et les durées, pas tous les coûts internes d'un fournisseur malveillant.
  Les implémentations doivent être importables et sérialisables avec `spawn`
  (pas de lambda/closure, reconstruire les connexions dans le processus enfant).
  Un échec de démarrage après l'intention persistée reste conservativement en revue.
- IDs/versions déclarés par les implémentations ; pas encore d'attestation des
  binaires, d'authentification humaine ou de preuve externe signée.
- Budget par appel, pas de budget total ; pas de file distribuée, ordonnanceur,
  moteur de notifications, multi-agents, interface graphique ou modèle réel.
- Snapshots locaux en clair ; pas de chiffrement ni rétention automatique.
  Démonstration exclusivement synthétique. Aucun historique utilisateur ingéré.
- Mémoire figée pendant la mission. Un futur outil réel devra revalider la
  fraîcheur/applicabilité et les autorisations juste avant son effet.
