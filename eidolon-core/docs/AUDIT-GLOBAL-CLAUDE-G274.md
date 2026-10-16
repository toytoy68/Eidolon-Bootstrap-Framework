# Audit global indépendant d'Eidolon — G274

Auteur : Claude (Claude Code), 16 octobre 2026, Europe/Paris (+0200).
Mandat : [G274-AUDIT-GLOBAL](../collaboration/G274-AUDIT-GLOBAL.md), relayé par Codex/GPT
à la demande de toytoy (07 h 42). Réponse : C-MSG-C192 dans
[CLAUDE-TO-GPT](../collaboration/CLAUDE-TO-GPT.md).

## 1. Verdict

**Aucun P0 trouvé.** Je n'ai reproduit ni perte de données, ni fuite entre profils, ni
contournement d'autorisation. Les protections déjà revues (écritures canoniques, liaison de
profil, jetons distincts, aperçu/confirmation, reçus) tiennent sur les scénarios rejoués.

**Deux P1 confirmés bloquent un parcours de la bêta :**

| ID | Gravité | Défaut | Effet |
| --- | --- | --- | --- |
| [F001](#g274-f001--le-texte-brut-du-tour-sert-de-requête-de-rappel) | **P1** | Le tour est envoyé tel quel comme requête de rappel | Mémoire « indisponible » pour tout message multi-ligne, avec tabulation ou de plus de 500 caractères |
| [F002](#g274-f002--un-seul-document-non-extractible-bloque-toute-la-racine) | **P1** | Un seul document non extractible annule toute la synchronisation | Une note vide, un PDF scanné ou un PDF de plus de 4 Mio bloque la racine indéfiniment |
| [F003](#g274-f003--une-admission-gpu-en-échec-laisse-une-tête-de-file-orpheline) | **P2** | Une admission GPU interrompue par une erreur laisse sa demande en attente | Tous les tours suivants expirent (`GPU_ADMISSION_TIMEOUT`) jusqu'à `cancel-waiting` |
| [F004](#g274-f004--le-seuil-candidat-choisi-est-le-plus-permissif) | **P2** | Le seuil d'identité candidat est le plus permissif parmi les seuils équivalents | FAR consommé jusqu'à la cible alors qu'un seuil séparant existait |

Plus huit constats P3 (documentation, nommage, CI), quatre hypothèses non reproduites et
des observations de conception. Chaque défaut confirmé a une sonde rouge sur le code audité
et un correctif séparé, appliqué en essai puis retiré.

## 2. Bases réellement auditées

| Dépôt | Branche | SHA | Remarque |
| --- | --- | --- | --- |
| Bootstrap/Core | `feat/eidolon-core-v0.1` | `04805515b219d985e0d0d4ae35d37ae9d9511f71` | Tête au début de l'audit (07 h 45). Delta depuis `940616c` et `00fe9cb` : **documentaire seulement** (0 fichier `src/`, `tests/`, `desktop/`) |
| Memory | `refactor/architecture-v1` | `76d664013d4e018212682c5aa56305bea0c41db6` | Identique à la référence G274 ; tête distante inchangée en fin d'audit |

Aucun nouveau commit n'est arrivé pendant l'audit sur ces deux branches (contrôle `git fetch`
en fin de travail). Mon travail est sur la branche `claude/g274-audit`, issue de `0480551`.

Environnement : conteneur Linux jetable, Python 3.13.16, Node 22, `age`, `openssl`, `ffmpeg`,
`pdftotext` présents ; exécution en **root** (les sondes qui exigent un UID ordinaire sont
ignorées, comme indiqué par pytest). Ni VM, ni PC, ni Windows, ni GPU, ni Qdrant/Ollama serveur.

## 3. Méthode

1. Inventaire des sous-systèmes et points d'entrée (section 4).
2. Suites existantes rejouées comme base, **pas comme garantie** : Core
   [résultat §11](#11-commandes-et-résultats), Memory 3 154 réussis, Node 210 réussis.
3. Analyse statique ciblée : `ruff` (F821, F811, B023, B006, PLE) sur le code produit des
   deux dépôts, `shellcheck` sur les installateurs, liens Markdown, et un contrôle
   **documentation ↔ CLI** : 85 modules `python -m …` cités dans `weekend/`, `docs/` et
   `Memory/docs/`, chaque option comparée à `--help` (y compris sous-commandes).
4. Lecture des chemins à risque, en priorité les parcours qui écrivent, croisent des
   profils ou reprennent après panne, puis les livraisons récentes (G269/G270 Memory, G270–G273 Core).
5. Pour chaque suspicion : scénario minimal sur données synthétiques, vrai pont Memory sur
   boucle locale quand le contrat est en jeu, sonde qui échoue, correctif minimal séparé,
   sabotage du correctif pour vérifier que la sonde discrimine.

Les modes de vérification suivent le mandat : **TESTÉ** (exécuté ici), **LU** (lecture de
code seulement), **NON VÉRIFIÉ** (non examiné en profondeur), **BLOQUÉ** (impossible ici).

## 4. Inventaire

| Sous-système | Dépôt | Points d'entrée principaux |
| --- | --- | --- |
| Installateurs Bootstrap | Bootstrap | `01-system.sh`, `02-nvidia.sh`, `03-docker.sh` |
| Missions Core (runtime, worker, store, reprise) | Core | `python -m eidolon_core` (29 sous-commandes) |
| API locale, conversations, relais | Core | `eidolon_core.http_api` ; `/v1/conversations/*` (27 routes), `/v1/comm/*`, `/v1/monitor/*` |
| Services de profil bêta | Core | `beta_runtime` (profils, aperçu/confirmation, reçus, Web, fichiers, documents, mémorisation) |
| Dialogue et file GPU | Core | `dialogue`, `gpu_queue` (CLI `status/enqueue/acquire/cancel-waiting/release`) |
| Bibliothèque, conservation | Core | `library_sync` (`--sync --watch`), `retention_preview` |
| Identité | Core | `identity_runtime`, `identity_measure`, `identity_evaluation`, runners ONNX/OpenCV |
| Médias, voix, vision | Core | `media_*`, `comm_*`, `eidolon-media`, `eidolon-media-worker` |
| Surveillance DARME | Core | `darme_*`, `monitor_*`, `deployment/darme-*.py` |
| Maintenance d'index | Core → Memory | `maintenance_host` (`--check-only/--execute`) |
| Client bureau | Core | `desktop/connected` (navigateur), `desktop/tauri` (Rust), `desktop/windows/*.ps1` |
| Moteur canonique | Memory | `core/backend`, `core/information`, `core/persistence`, journaux et reprise |
| Rappel et index | Memory | `core/retrieval`, `core/indexing` (`runtime check-config/status/rebuild/sync`) |
| Pont Memory | Memory | `services.memory_bridge` (`/v1/recall`, `/v1/remember`), `services.profile_binding` |
| Échange de collaboration | Memory | `services/collaboration` (MCP, JWT RS256) |
| CI | les deux | `core-tests`, `core-windows`, `core-desktop-browser`, `memory-tests`, `memory-qdrant-*` |

## 5. Matrice de couverture

| Composant | Mode | Justification |
| --- | --- | --- |
| Pont Memory `/v1/recall`, `/v1/remember`, liaison de profil | **TESTÉ** | vrais serveurs sur boucle locale, deux profils, mémorisation puis rappel (F001) |
| Services de profil `beta_runtime` (mémorisation, reprise UNKNOWN, isolation) | **TESTÉ** | via `ConversationAPI` réelle et deux ponts réels ; reprise de la même commande observée |
| Dialogue → rappel (`Dialogue._recall`, `BridgeMemory`, `recall_for`) | **TESTÉ** | F001 sur les deux chemins |
| Bibliothèque `library_sync` | **TESTÉ** | F002 : fichier vide, blanc, > 4 Mio, PDF sans texte ; témoin lisible |
| File GPU `gpu_queue` / `ScheduledModel` | **TESTÉ** | F003 avec vrai verrou SQLite concurrent ; témoin de reprise opérateur |
| Calibration `identity_evaluation` | **TESTÉ** | F004, jeu synthétique minimal |
| Contrôle doc ↔ CLI (85 modules) | **TESTÉ** | aucune option documentée absente de `--help` |
| Liens Markdown actifs | **TESTÉ** | un seul lien cassé hors archives (F010) ; les archives conservent volontairement leurs liens d'origine |
| Client navigateur `desktop/connected` | **TESTÉ** (suite existante) | `build.js --check` à jour, 210 tests Node réussis ; aucun rendu Windows |
| `identity_measure`, `retention_preview`, `access_token`, `client_credentials` (rotation, révocation) | **LU** | aucune anomalie hors F004 ; restauration d'une ancienne base de clés déjà documentée (ROLLBACK) |
| `maintenance_host` (tranche passages), index Memory (`qdrant_passages`, `qdrant_index`, `runtime`) | **LU** | descripteur par génération correct ; H2 pour le verrou |
| Écritures canoniques Memory (`writes`, `remember`, `persistence`) | **LU** | idempotence par identifiant stable, verrous exclusifs ; suites Memory vertes |
| `http_api` (routage, hôtes/origines, relais), `conversation_api` (27 routes) | **LU** | appartenance vérifiée sur les routes à identifiant ; F009 pour l'arrêt |
| Scripts Windows `eidolon-resident.ps1`, `eidolon-startup.ps1` | **LU** | F011 ; aucune exécution Windows |
| Installateurs Bootstrap | **LU** + `shellcheck` | aucun avertissement hors variables inutilisées ; non exécutés (effets système) |
| `deployment/darme-*.py`, `vm-profile/*.service`, brouillons `.service.in` | **LU** | H1 sur le brouillon bibliothèque |
| Échange MCP Memory (`services/collaboration`) | **LU** partiel | vérification JWT RS256, audience, émetteur, portées ; outils VM non examinés en profondeur |
| Runtime de missions, worker, reprise (C-001…C-021) | **NON VÉRIFIÉ** en profondeur | suites vertes ; revues antérieures nombreuses, rien de neuf examiné |
| Médias, voix (STT/TTS), vision, ComfyUI | **NON VÉRIFIÉ** en profondeur | suites vertes ; pas de moteur réel |
| Tauri (`origin.rs`) | **BLOQUÉ** | pas de toolchain Windows ; couvert par le workflow `core-windows` |
| Moteurs d'identité réels (ONNX, OpenCV), Qdrant serveur, Ollama, VRAM | **BLOQUÉ** | absents ici ; voir aussi F012 (CI) |
| Comptes réels, montages NAS/SMB, tunnels SSH, matériel, 50 preuves PC/VM | **BLOQUÉ** | restent **NOT_RUN** |

## 6. Défauts confirmés

Sondes : [`tests/test_claude_audit_g274.py`](../tests/test_claude_audit_g274.py). Sur le code
audité, chaque cas défaillant est marqué `xfail(strict=True)` : il doit échouer, et un passage
inattendu fait échouer la suite. Chaque patch retire ses propres marques.

### G274-F001 — le texte brut du tour sert de requête de rappel

- **Dépôt/SHA** : Core `0480551` (code identique à `00fe9cb`) ; contrat Memory `76d6640`.
- **Fichiers et symboles** : `src/eidolon_core/dialogue.py` `Dialogue._recall` ;
  `beta_runtime.BetaRuntime.recall_for` ; `memory.BridgeMemory.recall` →
  `memory_bridge_client.recall` ; côté Memory `services/memory_bridge.py` `validate_request`.
- **Attendu** : un pont sain qui contient la réponse est utilisé pour un message ordinaire.
- **Observé** : la requête du pont est limitée à 500 caractères sans caractère de contrôle,
  alors qu'un tour peut faire 8 000 caractères et contenir des sauts de ligne. Le texte brut
  est transmis. Résultat : 400 côté pont (profils bêta) ou `ValueError` côté client
  (`BridgeMemory`), puis `memory: "unavailable"` et réponse **sans sources**.
- **Déclenchement** : tout tour avec `\n`, `\t` ou plus de 500 caractères, c'est-à-dire une
  grande partie des vrais messages. Aucun prérequis de configuration.
- **Impact** : le parcours chat → rappel est silencieusement dégradé ; l'écran annonce une
  mémoire indisponible alors que le pont fonctionne. Ce n'est pas documenté (DIALOGUE.md
  ne mentionne pas cette limite). **P1**, confiance élevée.
- **Reproduction** : `pytest tests/test_claude_audit_g274.py -k f001 --runxfail` ; deux
  profils, vrais ponts, mémorisation confirmée de « La V100 est en cave. », puis tour
  « Bonjour,\nque sais-tu de la V100 ? ». Résultat réel : `{'memory': 'unavailable',
  'memory_items': 0}` ; la même question sur une ligne donne `sent` (témoin vert).
- **Cause** : aucune préparation de requête entre le tour et le contrat de rappel.
- **Correction minimale** ([0007](../collaboration/core-patches/0007-claude-g274-f001-recall-query.patch)) :
  `recall_query(text)` dans `dialogue.py` — contrôles remplacés par des espaces, espaces
  regroupés, coupe au dernier espace avant 500 caractères (coupe franche pour un mot plus
  long). Le texte du tour, l'historique et le modèle sont inchangés. Le choix « début du
  message » est une décision produit possible ; la fin du message pourrait porter la question.

### G274-F002 — un seul document non extractible bloque toute la racine

- **Dépôt/SHA** : Core `0480551`.
- **Fichiers et symboles** : `src/eidolon_core/library_sync.py` `Library._scan` ;
  `documents.extract`, `profile_files.read_bytes`.
- **Attendu** : la note lisible est synchronisée ; le fichier problématique est listé comme
  présent sans extrait.
- **Observé** : `documents.extract` lève `DocumentError` (`DOCUMENT_SIZE_INVALID` pour un
  fichier vide, `DOCUMENT_NO_TEXT` pour un fichier blanc ou un PDF sans couche texte) et
  `read_bytes` lève `ValueError` au-delà de 4 Mio. Rien n'est attrapé : **toute la génération
  est refusée**. En `--watch`, chaque passage échoue de nouveau tant que le fichier existe.
- **Déclenchement** : un seul fichier de ce type dans la racine. C'est l'état ordinaire d'un
  dossier de documents réel (scans, gros PDF, notes vides).
- **Impact** : le suivi de bibliothèque (P1 du backlog G273) ne produit jamais de génération
  sur un dossier réel. La sortie ne dit que `SCAN_REFUSED_OLD_GENERATION_PRESERVED` et le nom
  de classe de l'exception, sans le fichier en cause. La doc dit qu'« une erreur » conserve la
  génération précédente, sans dire qu'un fichier ordinaire suffit. **P1**, confiance élevée.
- **Reproduction** : `pytest tests/test_claude_audit_g274.py -k f002 --runxfail` ; résultats
  réels : `DOCUMENT_SIZE_INVALID`, `DOCUMENT_NO_TEXT` (×2), `bounded regular file required`.
- **Correction minimale** ([0008](../collaboration/core-patches/0008-claude-g274-f002-library-unextractable.patch)) :
  au-delà de 4 Mio, le fichier est inventorié sans hachage ni extrait (taille revérifiée au
  second passage) ; une `DocumentError` d'extraction n'est plus fatale : fichier inventorié
  avec son hachage, **aucune version** mise en cache, nouvel essai au passage suivant. Le
  rapport ajoute `not_extracted` par code. Liens, liens physiques, modifications, budgets et
  interruptions restent fatals, comme avant.

### G274-F003 — une admission GPU en échec laisse une tête de file orpheline

- **Dépôt/SHA** : Core `0480551`.
- **Fichiers et symboles** : `src/eidolon_core/gpu_queue.py` `Queue.wait`, `Queue.acquire`,
  `ScheduledModel.reply`.
- **Attendu** : une tentative qui sort sans bail retire sa demande.
- **Observé** : `wait` n'annule la demande que sur arrêt explicite ou délai. Une exception de
  `acquire` (SQLite occupé plus de 2 s, erreur d'E/S) sort de la boucle et laisse la ligne
  `WAITING`. Une demande de dialogue a la priorité 100 et vieillit : elle reste **en tête
  pour toujours**. `acquire` n'admet que la tête : chaque tour suivant attend puis échoue en
  `GPU_ADMISSION_TIMEOUT`, alors que toute la capacité est libre.
- **Déclenchement** : un verrou concurrent de plus de 2 s sur `gpu-queue.sqlite3` au mauvais
  moment (CLI opérateur, inspection, sauvegarde), ou une erreur d'E/S.
- **Impact** : dialogue bloqué jusqu'à `cancel-waiting` manuel. La procédure G273 documente la
  reprise opérateur pour un processus tué ; elle ne couvre pas une erreur transitoire dans un
  processus vivant. **P2** (contournement documenté), confiance élevée.
- **Reproduction** : `pytest tests/test_claude_audit_g274.py -k f003 --runxfail` : vrai
  `BEGIN EXCLUSIVE` tenu 2,5 s juste après l'insertion ; résultat réel : `OperationalError`,
  puis `['WAITING']` dans `inspect()`. Le témoin confirme que `cancel-waiting` rétablit l'admission.
- **Correction minimale** ([0009](../collaboration/core-patches/0009-claude-g274-f003-gpu-withdraw.patch)) :
  toute sortie de `wait` sans bail appelle `_withdraw`, qui annule seulement une ligne encore
  `WAITING` (trois essais espacés de 0,5 s). Une ligne `ACTIVE` n'est jamais libérée par ce
  chemin : la règle de conservation des réservations incertaines est inchangée.

### G274-F004 — le seuil candidat choisi est le plus permissif

- **Dépôt/SHA** : Core `0480551`. **Fichier** : `src/eidolon_core/identity_evaluation.py` `evaluate`.
- **Attendu** : à taux de faux rejets égal, le seuil qui accepte le moins d'imposteurs.
- **Observé** : `min(candidates)` départage les égalités de FRR par le **plus petit** seuil.
  Jeu synthétique : authentiques 0,9/0,9, imposteurs 0,3/0,5 en calibration.
  - Cible FAR 0,5 : seuil 0,3 + ε choisi (FAR calibration 0,5), alors que 0,9 sépare
    parfaitement (FAR 0, FRR 0).
  - Cible FAR 0 : seuil 0,5 + ε, au ras de l'imposteur le plus haut. Un imposteur de
    validation à 0,55 passe (FAR validation 1,0).
- **Impact** : le seuil proposé consomme la marge de sécurité. Aucun seuil n'est activé, et
  `validation_meets_empirical_target` signale l'écart ; d'où **P2**, confiance élevée sur le
  comportement.
- **Reproduction** : `pytest tests/test_claude_audit_g274.py -k f004 --runxfail`.
- **Correction minimale** ([0010](../collaboration/core-patches/0010-claude-g274-f004-threshold-tiebreak.patch)) :
  départage par le seuil le plus **haut** à FRR égal. Le choix d'une marge (milieu entre classes)
  reste une décision de calibration à prendre avec de vraies captures.

### Constats P3

| ID | Dépôt | Constat | Proposition |
| --- | --- | --- | --- |
| F005 | Memory | La docstring de `core/indexing/qdrant_passages.py` dit « reconstruction complète seulement » ; `docs/G269-OFFLINE-RUNTIME.md` dit « pas encore de mises à jour incrémentales ». G270 a ajouté `sync`. Côté Core, `RECETTE.md` l. 85 (« pas encore un bouton de conversation ») et l. 107 (« archive_passages refusé par ce worker ») contredisent `beta_runtime` (action `remember`) et `maintenance_host.PassageTick` | Mettre à jour ces trois textes |
| F006 | Memory | Sur `/v1/remember`, un refus de validation (commande invalide, empreinte différente) répond 503 `RECALL_UNAVAILABLE`, nom de rappel et code d'indisponibilité | Code d'erreur propre à l'écriture ; Core peut rester prudent (UNKNOWN) |
| F007 | Memory | `services/memory-controller/memory_controller.py` utilise `Any` sans l'importer (19 occurrences). Sans effet à l'exécution grâce à `from __future__ import annotations` ; `typing.get_type_hints` échouerait | Importer `Any` ou marquer le module comme hérité |
| F008 | Bootstrap | `README.md` : bannière `docs/images/banner.jpg` absente ; feuille de route « Planned » pour 02/03 alors que les scripts existent. `01-system.sh` déclare IP/passerelle/DNS jamais utilisés ; il valide `age`/`openssl` pour Core mais n'installe pas `poppler-utils` ni `ffmpeg`, requis par les documents et médias Core (documenté à part dans DOCUMENTS-G272) | Corriger le README ; retirer ou utiliser la configuration réseau ; décider où vivent les dépendances Core |
| F009 | Core | `http_api` n'installe pas de gestionnaire SIGTERM. `systemctl stop/restart` tue le processus sans `server_close()`, alors que DIALOGUE.md décrit l'arrêt par `server_close` (vrai pour Ctrl+C seulement). Aucun enregistrement après l'arrêt dans les deux cas ; l'écart touche surtout la fermeture des services et la file GPU (voir §8) | Gestionnaire SIGTERM → `shutdown()`, ou doc précisée |
| F010 | Bootstrap | Seul lien actif cassé : la bannière du README (les archives gardent volontairement leurs liens d'origine) | Voir F008 |
| F011 | Core | `eidolon-startup.ps1` vérifie l'empreinte du script résident à l'inscription, pas à chaque ouverture de session ; un changement ultérieur du script par le même compte s'exécute | Faire vérifier l'empreinte par une amorce, ou le documenter |
| F012 | CI | `core-tests.yml` n'installe ni numpy, ni onnxruntime, ni OpenCV : les tests de runners d'identité sont **toujours** ignorés en CI ; la mesure G273 n'y voit jamais un vrai moteur | Job optionnel avec l'extra `identity` et des modèles de test |

## 7. Hypothèses à vérifier (non reproduites)

- **H1 — Bibliothèque et brouillon systemd.** `library-sync.service.in` fixe `CPUQuota=10%`.
  Chaque extraction lance un interpréteur Python, et le passage a un budget mural de 30 s.
  Mesuré ici sans quota : environ 50 ms par extraction d'une petite note (20 essais).
  À 10 % de CPU, cela ferait environ 0,5 s par fichier, soit une soixantaine de nouvelles
  notes par passage au plus, moins pour des PDF. Comme le passage est tout ou rien, un premier
  passage sur un dossier moyen pourrait ne jamais aboutir. Calcul, pas mesure sous quota :
  à vérifier sur la machine cible avant de fixer `CPUQuota`.
- **H2 — Rappel pendant une synchronisation de passages.** `QdrantPassageIndex._publish` tient
  le verrou canonique exclusif pendant toute la synchronisation, embeddings compris. Un rappel
  attend ce verrou ; le client Core abandonne après 10 s. Le premier tour après une période
  d'inactivité pourrait donc être sans mémoire, le temps que la reprise d'activité arrête la
  synchronisation. En mode `--snapshot`, rien n'arrête la synchronisation.
- **H3 — Arrêt pendant une attente d'admission.** L'annulation d'une attente se fait dans le
  fil du tour, qui est un fil démon. Si le processus se termine avant, la ligne `WAITING`
  reste. F003 n'y change rien. À observer avec un vrai arrêt de service.
- **H4 — Marge de calibration.** Au-delà de F004, aucun écart entre seuil et classes n'est
  imposé. À traiter avec de vraies captures, pas sur données synthétiques.

## 8. Observations de conception et limites connues

- **Réservations GPU durables.** `ACTIVE` et `UNKNOWN` ne sont jamais libérées
  automatiquement. Toute erreur d'adaptateur (y compris une connexion refusée avant tout
  calcul) et tout redémarrage pendant une réponse consomment `dialogue_mib` jusqu'à une
  libération revue. Avec l'exemple 16 000/2 000/6 000 Mio, deux événements suffisent à
  bloquer le dialogue. C'est conforme au parti pris documenté ; je recommande un inventaire au
  démarrage qui signale les réservations héritées.
- **Bibliothèque tout ou rien.** Même avec 0008, un lien, un lien physique ou un dépassement
  de budget refusent la racine entière, comme documenté.
- **Surveillance.** `/v1/monitor/*` est visible par tout client appairé, quel que soit le
  profil ; à arbitrer si les profils familiaux ne doivent pas voir l'état des machines.
- **Rotation.** `ClientCredentials.rotate` réactive un client révoqué. C'est documenté
  (SERVICES-HORS-VM-G273) et cohérent avec la liaison client → profil.
- **Documentées, non contredites par le code** : absence de purge, agent Windows natif,
  connexion biométrique multipersonne, moteurs hors file, restauration d'une ancienne base
  de clés.

## 9. Revues G273 absorbées

| N° | Sujet | Couverture | Résultat |
| --- | --- | --- | --- |
| 1 | Synchronisation | TESTÉ | **F002** ; protections lien/modification conservées par 0008 |
| 2 | Versions et reprise | LU + suites | cache par profil et format correct ; pas d'écart |
| 3 | Bibliothèque API/UI | LU | portée client → profil ; pagination et réponses tardives côté UI correctes |
| 4 | Conservation | LU | versions courantes protégées même absentes ; aucune écriture |
| 5 | Clés opérateur | LU | rotation atomique, inventaire sans hachage ; restauration documentée |
| 6 | Session utilisateur | LU | retrait de sa seule clé, double confirmation |
| 7 | Mesure d'identité | LU | consentement, doublons, sessions ; voir F012 |
| 8 | Calibration | TESTÉ | **F004** ; NaN, booléens et fuites refusés |
| 9 | Admission GPU | TESTÉ | **F003** ; §8 pour les réservations durables |
| 10 | Raccordement dialogue/média | LU + suites | échec moteur conservé UNKNOWN ; aucune préemption revendiquée ; H3 |

## 10. Ordre de correction proposé pour la bêta

1. **F001** (0007) : chaque conversation réelle en dépend.
2. **F002** (0008) : sans lui, la bibliothèque ne synchronise aucun dossier réel.
3. **F003** (0009) et l'inventaire des réservations héritées (§8).
4. **F004** (0010), avant toute calibration sur captures réelles.
5. P3 de documentation (F005, F008, F010), puis F006, F009, F011, F012.
6. Mesurer H1/H2/H3 lors de la recette du week-end.

## 11. Commandes et résultats

Depuis `eidolon-core/`, Memory cloné à côté :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:../../eidolon-memory-engine EIDOLON_MEMORY_INTEGRATION=1 \
  python -m pytest -q -rxs -p no:cacheprovider tests/test_claude_audit_g274.py   # sondes
... --runxfail                                                                   # voir les défauts
git apply collaboration/core-patches/0007-…patch 0008-…patch 0009-…patch 0010-…patch
```

| Exécution | Résultat réel |
| --- | --- |
| Core, code audité, sans les sondes G274 (base) | **2 273 réussis**, 9 ignorés (UID root, moteurs d'identité absents), 1 328 sous-tests |
| Core, code audité + sondes G274 | 2 278 réussis, 9 ignorés, **13 xfail** (les défauts), 1 328 sous-tests |
| Core + patches 0007–0010 | **2 292 réussis**, 9 ignorés, 0 xfail, 0 échec, 1 328 sous-tests |
| Core + patches 0007–0009 (avant F004) | 2 289 réussis, 9 ignorés |
| Memory `76d6640` | **3 154 réussis**, 23 ignorés, 3 xfail historiques, 12 sous-tests |
| Client navigateur | `build.js --check` à jour ; **210** tests Node réussis |
| Sondes `--runxfail` | 13 rouges, chacune sur l'assertion du défaut (mémoire `unavailable`, `ValueError` client, `DOCUMENT_SIZE_INVALID`, `DOCUMENT_NO_TEXT` ×2, `bounded regular file required`, `['WAITING']`, seuil 0,5 + ε au lieu de 0,9) |

Sabotages des corrections, chacun appliqué puis restauré (vérifié par `cmp` et `git status`) :

| Sabotage | Sondes rouges |
| --- | --- |
| F001 : requête = texte brut | 6 |
| F001 : sans la coupe à 500 caractères | 3 (cas « long ») |
| F002 : erreur d'extraction de nouveau fatale | 3 |
| F002 : sans contrôle de taille | 1 (> 4 Mio) |
| F003 : sans `_withdraw` | 2 |
| F004 : ancien départage `min(candidates)` | 2 |

Les fichiers de Codex/GPT (`dialogue.py`, `library_sync.py`, `gpu_queue.py`,
`identity_evaluation.py`) sont identiques à `0480551` sur ma branche : les corrections ne
vivent que dans les patches. Commits de la branche `claude/g274-audit` : sondes, puis
rapport, patches et réponse.
