# Plan de recette bêta priorisé (Claude, G258-10)

Auteur : Claude. Date : 15/10/2026, Europe/Paris. Statut : **proposition**.
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
| 1 | Suites Core et Memory sur la VM, SHA exacts | `pytest -q` | compte différent de la CI publiée, sans explication |
| 2 | M1 : sauvegarde, puis restauration sur copie isolée | `VM-OPERATIONS-ACCEPTANCE.md` (Memory) | sauvegarde non vérifiée, ou octets différents après restauration |
| 3 | M3 : Qdrant jetable, reconstruction, puis arrêt de Qdrant | `G222-QUALIFICATION-RUNBOOK` (Memory) | `INDEX_UNAVAILABLE` absent quand Qdrant est arrêté (B04) |
| 4 | M2 : pont seul, un rappel, puis pont arrêté | B02, B03 | souvenir présenté sans référence, ou succès annoncé quand le pont est arrêté |
| 5 | M4 : worker J2 sur instance isolée | `J2-WORKER-QUALIFICATION` (Memory) | **toute** suppression, ou tout `INDEXED` sans preuve |
| 6 | C1 : PC → Core → Memory, texte | B01, B10 | note de contexte absente alors que la mémoire est incomplète |
| 7 | C2 : missions | B05 à B07 | effet répété, ou action sans approbation |
| 8 | C3 : politique hôte, vérification sans effet | [runbook G256-10](2026-10-15-host-acceptance-runbook.md) | `engine_calls` différent de 1, ou une écriture constatée |
| 9 | Restauration complète et redémarrages | B08, B11 | référence perdue après redémarrage |

## 4. Décisions à prendre par toytoy avant l'étape 0

1. La VM, le PC et la fenêtre d'essai.
2. Le dossier de données et l'espace minimal.
3. Le compte de service Memory et ses permissions.
4. La politique hôte : source, âges, unité et limite de charge.
5. Le maintien d'Internet sur OFF pour le premier parcours.

## 5. Ce que ce plan exclut

- Toute fusion vers `main`, tout déploiement automatique, toute suppression
  dans Qdrant ou dans le canon.
- Le benchmark G182 et le corpus privé.
- La voix, la caméra, les agents média, le robot, EidolonOS.
