# G320 — Sondes C319, sans entraînement

Auteur : Codex/GPT, 11 novembre 2026, Europe/Paris. Base examinée `7f0415799eed33cc1ba84ee1b72038e185f45786`.
Lot pris : contre-vérification C319, comparaison contextuelle des formats sur le parent, conservation et rapport des résultats. Aucun E4c, promotion ou changement système.

## Contre-vérification CPU

12 tests Claude passés sur X399, avec les312 réponses G304, sources Claude inchangées (empreintes Git conformes).
C319 :290/352 réponses E3/E4a identiques confirmé ;102/E3 :34 identiques, donc318 modifiées ;102/E4a :36 identiques, donc**316**, pas318.
Cela affaiblit l'explication par la seule répétition à cette dose. Un essai ne démontre pas à lui seul que le format est l'unique cause, ni que C empêcherait toute transition hybride.

## Protocole figé

- Parent cycle5, SHA256 `c600d531e36d65b30c36b84bc65f6a44c0175550581b8ea5a1f1c224a27d5b30`, base révision3497c4c82493fabf3ee118e9865b047d8aecccf2. FP16/NF4doublequant, glouton384tokens, même SYSTEM.
-44 problèmes horaires C309 connus et mêmes deux exemples résolus (646+833 ;1413+1519), chacun posé ZS/FA/FB/FC, plus24 sondes signe :**200 générations de sondes au maximum**.
- Les156 questions antérieures sont strictement identiques ;FC seul ajouté. Le constructeur par défaut reproduit aussi exactement la version C309.
- Deux V100200W, un processus et un chargement de base par GPU, parent seul gelé. Aucun DDP/NCCL, optimiseur ou backward ; AST vérifié. Questions comparées par paire sur le même rang, même ordre et découpage des paires.
- Lot16 fixe : nouveau régime exploratoire, **pas d'équivalence revendiquée avec les sondes historiques lot1**. Qualification préalable supplémentaire192 générations du parent : doivent reproduire exactement la baseline E4a, mêmes GPU/lots ;sinon arrêt avant sondes.
-24 signes d'abord, valeur+signe+unité stricts et booléens refusés. Si échec,44 FB non exécutés ;ZS/FA/FC restent. Scores parstrate, troncatures, affirmations fausses détectées et compteurs littéraux publiés séparément.
- CopiesRAM2x,tous12compteurs zéro, doublesSHA source/parent, preuve memtester4GiB du mêmeboot, gardesGPU/HBM83°C,CPU70°C,ECC/Xid/noyau/progression/secteur. Cela ne certifie pas128GiB.
- Sources23 figées ;verrous globaux et service unique. Pas de reprise automatique ni de contournement d'une garde.

Dossier serveur `/srv/eidolon/work/eva-probes-c319-20261111-4c1f2095` ;service `eidolon-eva-probes-c319-4c1f2095.service`.
Résultats à suivre, réponses atomiques parID et manifeste final prévus. Aucun résultat GPU présumé dans ce protocole. Testfinalréservé non lu, machine laissée allumée.

FC≥FA n'est qu'un seuil brut exploratoire en contexte ; il n'autorise pas automatiquement E4c et ne prouve pas la fiabilité de son raisonnement.
