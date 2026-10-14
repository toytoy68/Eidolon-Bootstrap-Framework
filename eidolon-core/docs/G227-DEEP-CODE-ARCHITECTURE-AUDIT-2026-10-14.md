# G227 — Audit transversal approfondi du code et de l'architecture

Date : 14 octobre 2026. Branche Core `feat/eidolon-core-v0.1` (base `215d7f8`), Memory `refactor/architecture-v1` (base `490e4b2`), EidolonOS `main` (`cab53d2`). Audit statique de fichiers représentatifs et de la structure des trois dépôts, complété par les résultats GitHub Actions. **Ce n'est ni une lecture exhaustive des 2 927 fichiers, ni un pentest, ni une recette VM.** Aucun code de production modifié.

## Inventaire de portée

- Memory : 646 fichiers, 354 Python, 169 fichiers Python de tests. Modules inspectés : journal, migration, plan, preview, worker expérimental et worker_upsert, gate, canonical reader, Qdrant, verrouillage.
- Core : 2 275 fichiers, 429 Python, 138 fichiers Python de tests. Modules inspectés : worker, approvals, recovery, HTTP, conversation API, bridge, dialogue, modèle, SOUL, Web, DARME, communications et média.
- EidolonOS : 6 fichiers, aucun module Python ; documentation d'identité/continuité essentiellement conceptuelle.
- CI Memory run `38565669688` : 2300 PASS, 19 PASS contrat expérimental ; Qdrant run `38565669677` : 46 PASS. Core run `38531549417` : 1660 PASS, 6 SKIP, 5 warnings. Ces résultats ne prouvent pas la conformité de la production.

## Constatations, preuves et priorité

| ID | Priorité | Constat | Preuve / conséquence | Remédiation |
|---|---|---|---|---|
| A01 | P0 | `worker_upsert.apply_upsert` autorise `canonical_root=None`. | Appel sans verrou possible, alors que l'upsert n'est pas atomique avec les écrivains. | Séparer API production (verrou obligatoire) et API de test, puis essais de concurrence interprocessus. |
| A02 | P0 | `QdrantIndex._point` ne stocke que `information_id` et `revision` ; `revision_for` ne valide pas le digest des bytes canoniques. | Une révision correcte peut correspondre à un contenu/vector incorrect. | Payload `canonical_sha256`, identité d'embedding et génération ; read-back typé complet. |
| A03 | P0 | `CanonicalReader` effectue `is_file`, `read_bytes` et contrôle de symlink séparément. | TOCTOU possible en présence d'un écrivain non coopératif. | Ouvrir avec `O_NOFOLLOW`, `fstat` et vérification de racine/parent ; tests de substitution. |
| A04 | P0 | Les 19 tests contractuels portent sur `IndexWorker` expérimental ; `worker_upsert` est un chemin distinct. | Les 19 PASS ne prouvent pas la sûreté du worker Qdrant réel. | Adapter le contrat au même chemin d'exécution et aux mêmes erreurs/reçus. |
| A05 | P1 | `reconcile_plan.ABSENT = "ABSENT"` puis `is ABSENT`. | Comparaison d'identité non fiable pour des chaînes équivalentes construites séparément ; peut fausser le plan. **Défaut de code directement confirmé.** | Sentinelle typée unique + validation des snapshots, test avec chaîne non internée. |
| A06 | P1 | `reconcile_plan` compare surtout les révisions indexées. | Dérive à révision égale non détectée par le plan. | Comparer révision, digest et génération, traiter inconnu sans suppression. |
| A07 | P1 | `WebBudget.finish` écrit `float(self.clock())` sans test `isfinite`, contrairement à `reserve`. | NaN/Inf ou temps négatif peuvent entrer dans l'état de clôture ou produire un échec inattendu. **Asymétrie directement confirmée.** | Fonction horloge commune, validation avant transaction, tests de refus. |
| A08 | P1 | `BridgeMemory` fait `is_symlink/is_file/stat/read_text` en opérations distinctes. | Course sur le chemin du secret si le répertoire est modifiable par un autre acteur. | Ouverture via descripteur `O_NOFOLLOW`, `fstat`, lecture bornée, contrôles parents. |
| A09 | P1 | Le résolveur Web est borné à 8 threads mais les threads DNS bloqués ne sont pas annulables. | Saturation durable : les nouvelles résolutions échouent jusqu'à retour des threads. | Santé DNS, métriques, stratégie d'isolation/annulation ; tests de saturation prolongée. |
| A10 | P1 | `QdrantIndex.rebuild` exige un instantané canonique arrêté et un écrivain d'alias coordonné extérieurement. | Les contrôles de manifeste ne remplacent pas une transaction avec les écrivains. | Verrou/génération/alias et protocole de reprise explicitement orchestrés. |
| A11 | P1 | Bridge réel Core↔Memory et parcours VM/PC restent non qualifiés (6 skips Core). | Contrats unitaires verts sans preuve de disponibilité, de latence, de reconnexion et de permissions de production. | Recette B01–B12, panne de tunnel, sauvegarde/restauration et test de modèle local. |
| A12 | P2 | EidolonOS reste documentaire (6 fichiers, 0 Python). | Aucune fonctionnalité d'OS livrée à considérer dans la bêta. | Maintenir hors périmètre J2/J3. |
| A13 | P2 | Les diagnostics INDEX_* et DARME ont une couverture partielle ; 5 warnings Core subsistent. | Observabilité de production et comportement sous panne encore à qualifier. | Mesures de fraîcheur, supervision, inventaire des warnings, tests d'exploitation. |

## Architecture : points sains observés

- Séparation Core (autorisations/mission), Memory (canonique) et Qdrant (index reconstructible).
- Les propositions du LLM ne sont pas une autorisation : `approvals.action_binding` lie action, tentative, configuration et contexte à un digest.
- SOUL est limité au style, pas aux permissions ; le modèle est configuré sur loopback.
- Les écritures canoniques disposent d'un verrou coopératif et d'une publication atomique.
- Les workers média et Core enregistrent l'intention ou la tentative avant effet ; l'incertitude n'est pas automatiquement convertie en succès.
- Le Web impose une politique explicite et un plafonnement des résolutions.

## Ce qui reste non vérifié

Sécurité de chaque route HTTP et média, code des centaines de tests, déploiement Proxmox, permissions effectives des services, MCP/Cloudflare, certificats, journalisation des secrets, matériel GPU, Qdrant réel et restauration complète. Ne pas affirmer l'absence de défauts dans ces domaines.

## Plan d'action et portes de validation

1. P0 A01–A04 : verrou obligatoire, read-back avec digest, lecteur sans TOCTOU, contrat unique de worker.
2. P1 A05–A08 : sentinelle typée, dérive digest, horloge Web, lecture de secret sécurisée.
3. P1 A09–A11 : saturation DNS, génération Qdrant, intégration Core/Memory/PC.
4. P2 A12–A13 : OS différé et monitoring.
5. CI complète sur SHA figé, scénarios de crash et concurrence, puis recette VM isolée. Aucune suppression Qdrant automatique et aucune fusion `main` avant validation humaine.

## Verdict

Architecture modulaire cohérente ; **défauts aux frontières et invariants de cohérence**, plutôt qu'une refonte à prévoir. J2 ne doit pas être promu en production. Le nombre de tests verts ne démontre ni l'atomicité interservices ni la sécurité contre un écrivain non coopératif.
