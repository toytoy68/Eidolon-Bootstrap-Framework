# Architecture Core v0.1

Ce document décrit la tranche implémentée. La cible élargie d'assistant résident,
d'accès Internet/LAN et de clients distants est consignée dans le
[cadrage consolidé](CADRAGE-DECISIONS-2026-10-05.md). L'absence d'outil réseau dans
la démo actuelle n'est pas une exigence de fonctionnement hors ligne du produit.

## Responsabilités

| Module | Contrat |
| --- | --- |
| `contracts` | JSON borné, références et réserves mémoire, plan strict v1 |
| `model` | `Model.propose(request, context) -> str`, simulateur déterministe |
| `memory` | `MemoryReader.recall(query) -> dict`, fixture ou délégation au vrai moteur |
| `tools` | Registre de code de confiance, validateurs, politique fixe, vérificateurs |
| `store` | SQLite : snapshot et événement dans une transaction, contrôle de révision |
| `worker` | Appels en processus spawn, délais, interruption, reçu JSON borné |
| `runtime` | Mission, plan, précontrôle intégral, exécution séquentielle, reprise |
| `cli` | Création, exécution/reprise, inspection, annulation et réconciliation |

## Mission et progression

Identifiant UUID stable `m-…`, requête d'origine conservée, configuration figée.
Statuts : NEW, RUNNING, BLOCKED, REVIEW_REQUIRED, SUCCEEDED, FAILED, CANCELLED.
Phases distinctes : RECALL, PLAN, READY, EXECUTING, VERIFY, DONE.
La progression compte les étapes **vérifiées**, pas celles promises ou démarrées.
Les appels portent `mission_id/step_id`, numéro de tentative, versions de l'outil
et du vérificateur, empreintes du contexte et du résultat.

Le modèle propose uniquement `{"version":1,"steps":[...]}` ; 1 à 5 étapes,
identités uniques, paramètres objets, clés inattendues/dupliquées et nombres non
finis refusés. Aucun champ modèle « success », « permission » ou instruction
mémoire ne constitue une autorisation. La sortie brute est conservée avant
validation pour diagnostic, dans les limites de taille.

Le précontrôle autorise **toutes** les étapes et valide leurs paramètres avant
le premier outil, puis recommence lors d'une reprise. La politique autorise
uniquement les noms configurés **et** les outils déclarés sans effet. Le modèle
ne peut pas modifier le registre ni cette politique. Les paramètres de
`text.stats` contiennent uniquement une référence à l'extrait persisté.

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
| SUCCEEDED / FAILED / CANCELLED | Retourner l'état terminal sans nouvelle exécution |

Le journal distingue l'intention d'appel, le reçu retourné et la validation.
Une intention persistée peut précéder un appel qui n'a jamais démarré. Le choix
conservateur est de demander une revue dans cette fenêtre aussi. Après un arrêt
brutal du parent, un exécutant enfant peut subsister : avant une réconciliation
`no-effect`, confirmer son arrêt et les effets. Aucune promesse exactly-once.

Après un délai/annulation pendant l'outil, Core arrête son processus enfant et
conserve REVIEW_REQUIRED ; un arrêt local ne démontre pas l'absence d'effet chez
un futur service distant. Le runtime ne fournit aucun outil externe dans v0.1.
L'annulation n'est ni un rollback ni une suppression des preuves déjà obtenues.

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
La demande admissible du simulateur est précisément bornée à ce calcul.
Un futur modèle généraliste demandera des critères d'acceptation métier distincts.

## Limites assumées

- Linux/POSIX, écrivains coopératifs, stockage local ; pas de validation NFS,
  Windows natif, coupure électrique ou corruption/adversaire modifiant SQLite.
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
