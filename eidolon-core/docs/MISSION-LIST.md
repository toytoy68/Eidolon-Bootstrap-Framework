# C-008e — Inventaire local des missions

Codex/GPT, 06/10/2026. Protocole **eidolon-mission-list/1**.
Paquet standard Python, sans dépendance nouvelle. Serveur POSIX comme le Core
actuel ; pas de transport, d'authentification, de surveillance en arrière-plan
ou de branchement de l'interface graphique dans ce lot.

## Besoin et contrat

Le futur écran Missions doit découvrir les identifiants avant de sélectionner
une mission avec client-sync/1. `MissionList(store).page(cursor=None, limit=50)`
retourne de 0 à 100 projections, triées par identifiant stable (ordre lexical,
**pas** date de création ni priorité). La lecture ne démarre ni Runtime, ni
modèle, ni mémoire, ni outil et ne produit aucun événement.

| Champ | Sens |
| --- | --- |
| protocol | eidolon-mission-list/1, distinct de client-sync/1 |
| snapshot_only / authorizes_execution | toujours true / false |
| store_id | identité locale, ni authentification ni secret |
| status | PAGE ou RESET_REQUIRED |
| observed_at | horodatage UTC de cette lecture, pas une preuve de disponibilité actuelle |
| generation | sequence globale, event_count, mission_count, anchor_sha256 du dernier événement |
| items | objets as_of_sequence + mission projetée ; aucune demande ni sortie brute |
| has_more / next_cursor | suite disponible / curseur à transmettre sans modification ; null en fin de liste |
| reason | seulement pour RESET_REQUIRED : STORE_CHANGED ou STATE_CHANGED |

La projection réutilise celle de client-sync/1 : identifiant, révision, statut,
phase, demande d'annulation, progression, type d'objectif (éventuellement null),
issue et vue d'accord/effet. Une demande hors catalogue reste visible sous
BLOCKED/CLARIFICATION. PENDING n'expire pas. APPROVED n'est pas une autorisation
d'exécution et cancel_requested=true ne signifie pas CANCELLED. Aucun corps de
requête, configuration, contexte mémoire, résultat brut ou détail d'événement.
Une projection d'accord peut encore nécessiter la lecture et le hachage des
preuves stockées : cette tranche ne remplace pas leur stockage inline.

## Cohérence et reprise

Chaque page lit identité, génération et projections dans **une transaction de
lecture SQLite**. Un écrivain WAL peut progresser pendant cette lecture : toute
la page représente la capture antérieure, jamais un mélange avant/après.
Les pages sont bornées ; les identifiants sont lus avant les corps pour éviter
de charger simultanément 101 gros corps bruts en mémoire.

Le curseur transporte version=1, store_id, generation et after_id. Si une
écriture Core normale change le journal entre deux pages, la continuation renvoie
RESET_REQUIRED avec **aucun item et aucun curseur suivant**. Une annulation
invalide ainsi la liste même si la révision de mission ne change pas. La création
d'une mission et sa progression sont aussi détectées. Un autre store_id impose
également un reset. Un curseur mal formé est une erreur, pas un nouveau départ.

Le client doit assembler une génération unique. Après reset, garder son ancien
ensemble comme périmé, signaler le besoin de relecture et commencer explicitement
une nouvelle liste sans curseur. Ne pas remplacer silencieusement quelques
lignes. `has_more=false` prouve seulement que cette capture est entièrement lue,
jamais que le système restera inchangé. La sélection d'une mission appelle
ensuite client-snapshot pour une vue fraîche, sans accorder de permission.

Rejouer une requête de page sur un état inchangé rend les mêmes items/curseur ;
observed_at peut changer. Le curseur survit à la reconstruction du lecteur mais
n'a ni signature, ni autorité, ni expiration temporelle. Il n'est pas une capacité
d'accès : un appelant local peut choisir d'autres identifiants existants.

## Commandes

Depuis eidolon-core/ ; utiliser un état déjà créé :

```sh
PYTHONPATH=src python -m eidolon_core --state /chemin/etat client-missions --limit 20
PYTHONPATH=src python -m eidolon_core --state /chemin/etat client-missions --cursor curseur.json --limit 20
PYTHONPATH=src:. python -m examples.mission_list_demo --format human
```

`curseur.json` contient seulement l'objet next_cursor précédent. Maximum 4096
octets, UTF-8 strict, clés uniques et entiers JS exacts ; aucun float/bool accepté
comme compteur. Limit vaut 1 à 100. `--format human` reprend l'affichage ECT ;
JSON demeure la sortie par défaut. Code 0 = page lue, **pas mission réussie** ;
code 2 = reset ou erreur, distingués par le JSON et stdout/stderr. Les erreurs
SQLite gardent STORAGE_UNAVAILABLE. Un dossier absent n'est pas créé par la
commande ; les copies recovery-prepare sont bloquées par la garde Store.

L'API de lecture ne modifie pas la base. Comme les autres CLI de lecture, la
commande ouvre un Store existant et utilise son initialisation/migration courante ;
ce n'est pas un lecteur forensic pour une base arbitraire. recovery-inspect reste
le lecteur des copies historiques.

## Limites et prochaine tranche

- Une activité continue peut forcer plusieurs relectures et empêcher de terminer
  une liste paginée. Pas de capture longue persistante ni de garantie de progression.
  Mesurer avant de choisir entre captures matérialisées ou inventaire « vivant »
  explicitement non atomique. Aucune nouvelle tentative automatique ici.
- COUNT parcourt le journal/la table selon SQLite. Le coût des gros historiques
  et des corps de missions n'est pas qualifié ; limites de pages et mémoire du
  rendu ne constituent pas un budget global de durée ou de stockage.
- La génération détecte les écritures normales Core et certaines altérations du
  journal. Une modification SQL ancienne conservant tête et compteurs peut passer
  inaperçue. Un clone manuel peut conserver store_id. Pas d'anti-rollback universel.
- L'inventaire expose toutes les missions du Store local choisi. Avant toute API
  distante : identité, autorisation et filtrage par périmètre, isolation des
  curseurs entre utilisateurs, transport authentifié et budgets restent à construire.
- Le client Desktop ne consomme pas encore ce nouveau contrat. Pagination,
  reset, sélection et annulation/revue devront y être testés sur fixtures.
- Memory Engine, Windows, VM100, NAS, GPU et modèles réels ne sont pas testés ici.

[Validation et démonstration](validation/2026-10-06/codex-mission-list/README.md).


## C-027 — CLI strictement en lecture seule, 07/10/2026

Les branches client-missions, client-snapshot et client-poll utilisent désormais
le même ReadOnlyStore que l’API HTTP : mode SQLite ro/query_only, budget SQL
coopératif de deux secondes, refus des états bêta incomplets et des copies de
revue. Elles ne construisent plus Store et ne migrent plus le schéma. Une base
ancienne ou incomplète est refusée par UNSUPPORTED_READ_SCHEMA ; aucune table
ou identité manquante n’est recréée pendant une consultation. Les protocoles,
curseurs et projections restent inchangés.

[Reproduction et vérification](validation/2026-10-07/codex-cli-readonly/README.md).
