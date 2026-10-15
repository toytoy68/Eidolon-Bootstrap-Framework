# Plan de recette bêta priorisé (Claude, G258-10)

Auteur : Claude. Date : 15/10/2026, Europe/Paris. Statut : **proposition, actualisée en G262-10**
(sections 6 à 9 ; le critère d'arrêt de l'étape 1 est remplacé par le § 7).
Il n'exécute rien et ne remplace pas la grille
[G221](../G221-INTEGRATED-BETA-ACCEPTANCE.md) (B01 à B12) ni les jalons
[G225](../G225-BETA-MILESTONES.md) (J1 à J4). Il les **ordonne** à partir de ce
qui est prouvé aujourd'hui.

Bases :

- Memory `a0cc112` (G259) ;
- Core `216647d` ;
- bilan GPT [PROJECT-STATUS](../PROJECT-STATUS.md).

## 1. Trois niveaux de preuve, à ne jamais confondre

| Niveau | Ce qu'il prouve | Ce qu'il ne prouve pas |
| --- | --- | --- |
| **Expérience** (`tests/claude_memory_eval`, `tools/claude_*`) | une idée tient sur données synthétiques | rien pour la production : non branché |
| **CI** (workflows verts sur SHA figés) | le code fait ce que ses tests disent, en loopback, sur un runner | réseau réel, permissions du service, GPU, VM, PC Windows, durée |
| **Production** (VM/PC, recette datée) | le parcours réel, avec preuves datées et SHA | — |

À ce jour, **aucun** parcours n'a atteint le niveau production : G221 est
« définie, non exécutée ».

## 2. Parcours par état de préparation

| Parcours | Code prêt (CI) | Prérequis VM/PC manquants | Preuve manquante |
| --- | --- | --- | --- |
| **M1** Memory canonique : écrire, lire, sauvegarder, restaurer | oui | VM Memory, dossier de données, sauvegarde vérifiée | restauration sur copie isolée (B11) |
| **M2** Pont Memory authentifié (rappel borné, délais G257, verrou G259) | oui | secret 0600 dans un dossier 0700, loopback ou tunnel | rappel réel depuis Core (B02), pont arrêté (B03), redémarrage (B08) |
| **M3** Qdrant local reconstructible + fraîcheur `STALE`/`UNVERIFIED` | oui (serveur Qdrant qualifié séparément) | Qdrant jetable sur la VM | Qdrant indisponible (B04) ; reconstruction sur VM |
| **M4** Worker J2 (indexation prouvée, aucune suppression) | oui | compte de service, permissions Memory | 19 scénarios worker sur instance réelle isolée (G225) |
| **C1** Core ↔ PC : conversation texte, note de contexte (0006) | oui (+ Chromium) | VM Core, tunnel SSH, PC appairé | B01, B10 |
| **C2** Missions, approbation, reçus | oui | idem C1 | B05, B06, B07 |
| **C3** Tick de maintenance hôte (G254) | oui pour l'appel | politique écrite par toytoy, script de capture de l'hôte | vérification sans effet (`--check-only`), puis tick réel décidé à part |
| **C4** Web/SearXNG | oui | hors du premier parcours (Internet OFF) | B12 seulement |
| Rétention des générations, reçu de bascule, passages d'archives, lecteur d'instantané | **expérience** | — | **hors bêta** : aucune décision de production |

## 3. Ordre court des essais (Memory d'abord)

Chaque étape exige la précédente. Au **premier** critère d'arrêt, on
s'arrête : on note la sortie complète, on ne relance pas en boucle et on ne
corrige pas sur la VM.

| # | Essai | Commande ou document | Critère d'arrêt |
| --- | --- | --- | --- |
| 0 | Préflight hors ligne aux SHA recettés | [runbook G236-9](2026-10-15-claude-offline-acceptance-runbook.md) | tout `FAIL` ou `UNKNOWN` |
| 1 | Suites Core et Memory sur la VM, SHA exacts | `pytest -q` | une différence avec la CI **non classée** selon le § 7 |
| 2 | M1 : sauvegarde, puis restauration sur copie isolée | `VM-OPERATIONS-ACCEPTANCE.md` (Memory) | sauvegarde non vérifiée, ou octets différents après restauration |
| 3 | M3 : Qdrant jetable, reconstruction, puis arrêt de Qdrant | `G222-QUALIFICATION-RUNBOOK` (Memory) | `INDEX_UNAVAILABLE` absent quand Qdrant est arrêté (B04) |
| 4 | M2 : pont seul, un rappel, puis pont arrêté | B02, B03 | souvenir présenté sans référence, ou succès annoncé quand le pont est arrêté |
| 5 | M4 : worker J2 sur instance isolée | `J2-WORKER-QUALIFICATION` (Memory) | **toute** suppression, ou tout `INDEXED` sans preuve |
| 6 | C1 : PC → Core → Memory, texte | B01, B10 | note de contexte absente alors que la mémoire est incomplète |
| 7 | C2 : missions | B05 à B07 | effet répété, ou action sans approbation |
| 8 | C3 : politique hôte, vérification sans effet | [runbook G256-10](2026-10-15-host-acceptance-runbook.md) | `engine_calls` différent de 1, ou une écriture constatée |
| 9 | Restauration complète et redémarrages | B08, B11 | référence perdue après redémarrage |

## 4. Décisions à prendre par toytoy avant l'étape 0

Remplacé par le § 8 : plusieurs paramètres sont déjà connus et ne sont pas redemandés.

## 5. Ce que ce plan exclut

- Toute fusion vers `main`, tout déploiement automatique, toute suppression
  dans Qdrant ou dans le canon.
- Le benchmark G182 et le corpus privé.
- La voix, la caméra, les agents média, le robot, EidolonOS.

## 6. Manifeste des preuves (à remplir pendant la recette)

Une ligne par essai du § 3. Chaque case est **observée** et non recopiée d'une recette précédente.
Une case vide reste vide : elle n'est jamais complétée par une supposition.

| # | SHA Core | SHA Memory | Environnement | Commande exacte | Résultat observé | Limites | Date et heure |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | | | machine, OS, Python, **compte** qui exécute | | sortie JSON du préflight | | |
| 1 | | | idem, avec dépendances optionnelles présentes ou absentes | | comptes et liste des différences classées (§ 7) | | |
| 2 | | | | | empreintes avant et après restauration | | |
| 3 | | | version Qdrant | | `INDEX_UNAVAILABLE` visible | | |
| 4 | | | compte du pont | | référence document/révision | | |
| 5 | | | compte du worker | | aucune suppression ; preuves `INDEXED` | | |
| 6 | | | PC : navigateur, tunnel | | note de contexte affichée | | |
| 7 | | | | | reçus, refus | | |
| 8 | | | | | `engine_calls`, `git status` avant et après | | |
| 9 | | | | | références après redémarrage | | |

La colonne « Environnement » nomme toujours le **compte** utilisé. Un test lancé en root et le même test
lancé sous un compte ordinaire ne sont pas la même preuve. Exemple : la sonde « fichier illisible »
(mode 000) ne se déclenche que sous un compte ordinaire (correctif GPT G260).

## 7. Comparer aux résultats de CI : classer, ne pas exiger l'égalité des comptes

Les comptes dépendent de la plateforme et des dépendances. Par exemple, la qualification GPT G261 a vu
20 échecs `AF_UNIX` et 2 échecs de `chown`, tous liés au runtime. Chaque différence avec la CI publiée
est classée **avant** de continuer :

| Classe | Exemple | Effet |
| --- | --- | --- |
| A. Exclusion documentée | dépendance optionnelle absente (`numpy`, torch), test réservé à root, Chromium absent | noter le test et la raison, continuer |
| B. Limite d'environnement | sockets `AF_UNIX` interdites, `unshare` refusé, système de fichiers sans `chown` | reproduire une fois **hors** de cette limite, ou arrêter si c'est impossible |
| C. Différence inexpliquée | un échec qui n'entre ni en A ni en B | **arrêt** : sortie complète notée, aucune correction sur la VM |

Un test **ignoré** n'est jamais compté comme réussi. Une classe A ou B est une dette de qualification,
et non un succès (G225).

## 8. Paramètres déjà connus : candidats à vérifier, pas à redemander

Je les reprends des documents existants. Chacun est **vérifié** à l'étape 0, et non supposé. Aucune
adresse ni aucun port n'est recopié ici : on les lit dans les documents d'origine.

| Paramètre | Valeur connue | Source | Vérification à l'étape 0 |
| --- | --- | --- | --- |
| Machine Core | VM100 (deux V100 SXM2 32 Go en NVLink) ; VM101 retirée après migration | `docs/GPU-DISPLAY.md`, `docs/NETWORK-VM-MAPPING-2026-10-10.md` | `nvidia-smi`, nom d'hôte |
| Machine Memory | VM110, « source de vérité » de Memory Engine | `docs/NETWORK-VM-MAPPING-2026-10-10.md` | SHA Memory et état du dépôt |
| Profil du pont validé le 12/10 | unité `deployment/vm-profile/eidolon-memory-bridge.service` (Memory), compte `toytoy` | dépôt Memory | `systemctl cat`, `ps -o user=` |
| Accès PC | navigateur Windows via tunnel SSH | `docs/BETA-SERVER-PC.md`, G221 | tunnel ouvert, appairage |
| Internet | OFF pour le premier parcours | G221 | aucune route sortante pendant B01–B11 |

**Restent à décider par toytoy** :

- la fenêtre d'essai ;
- le dossier de données et l'espace minimal ;
- les seuils de la politique hôte : source, âges, unité et limite de charge ;
- les **trois** décisions du § 9.

## 9. Compte de service Memory : trois décisions séparées

| Décision | Préalable | Ce qu'elle autorise | Ce qu'elle n'autorise pas |
| --- | --- | --- | --- |
| **1. Adopter** le compte `eidolon-memory` | relecture GPT (G261 : favorable) | préparer : créer le compte, copier les données (vérifiées par `claude_copy_inventory.py`), préflight `--service-account` | arrêter l'ancien service ; activer la nouvelle unité |
| **2. Adapter le verrou** | choix entre la version intermédiaire (2 verrous montés en écriture) et la version cible (verrou ouvert en lecture seule, changement de code GPT) | écrire et tester l'unité correspondante | activer en production |
| **3. Activer** | décisions 1 et 2 prises, préflight entièrement `PASS`, sauvegarde relue | basculer le pont, avec retour arrière prêt | supprimer l'ancien corpus (décision ultérieure, séparée) |

Les preuves de chaque décision vont dans le manifeste du § 6. Détails techniques :
[compte de service, § 6](2026-10-15-memory-service-account.md).
