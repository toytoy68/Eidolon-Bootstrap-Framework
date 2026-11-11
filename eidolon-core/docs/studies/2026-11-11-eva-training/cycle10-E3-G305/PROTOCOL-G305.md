# Eva cycle10 — E3 répétition, protocole G305

Auteur : Codex/GPT. 11/11/2026, Europe/Paris.
Base : a24c6c68c321f720ce9384cc9c391324b12eaa40, feat/eidolon-core-v0.1.
Autorisation toytoy : « ok on reprend l'entrainement en utilisant les 2 V100 ! ».
Lot pris en charge : protocole, préparation isolée, qualification, essai borné, preuves et rapport. Aucun changement Core en production.

## État à la publication

Le X399 a été réveillé pour cette demande. Nouveau boot qualifié : copies RAM2x sans défaut, memtester4GiB avec mlock complet, doubles SHA source et adaptateur conformes. Les8DIMM sont déclarés2400MT/s@1,2V par SMBIOS. Cette qualification porte sur4GiB, pas sur toute la RAM ni sur une réparation définitivement démontrée.

L'orchestrateur est actif ; le smoke DDP4 mises à jour est en cours. Le vrai essai et ses résultats ne sont pas encore validés à cette publication. Il ne démarrera que si le smoke et les contrôles passent. Pas de nouveau cycle automatique.

## Hypothèse et changement borné

Les sondes G304 montrent un potentiel en few-shot, mais des comparaisons de reste erronées et une reconversion minutes→heure fragile. Elles ne démontrent pas que le seul défaut est une dose trop faible.

Après accord de toytoy sur davantage de répétitions, E3 teste trois passages du jeu E2 **strictement inchangé côté entraînement** :878 exemples,408 packs512 par passage,102updates par passage,306au total. Parentcycle5 ; E2 n'est pas adopté comme parent. Les169 réponses horaires (101replay+68cibles) sont chacune revues3fois.

LR maximal3e-6 conservé. Le calendrier de102pas E2 (warmup5 puis décroissance) est répété à chaque passage ; l'état optimiseur est conservé. Le nombre de passages et le matériel changent : ceci ne démontre pas un effet de dose isolé de toutes les différences numériques DDP. Aucun changement de méthode time_steps ou de texte cible supplémentaire.

V100×2 à200W chacune, FP16/NF4doublequant, LoRAr8alpha16, un adaptateur commun via DDP/NCCL ; global4packs/update,2/rank. TestCPU de gradient pondéré équivalent au calcul monoprocessus, couverture exacte des408packs à chaque passage. Le GPU1060 n'est pas utilisé.

Tokens supervisés par passage :47334rappel+12775cibles ; cible21,253%. Total3passages :180327tokens supervisés. Ne pas annoncer75/25.

## Mesure

- Sélection192 E2 réutilisée, évaluée avant puis102/204/306 ; seuils existants net+6cibles, test apparié exact exploratoirep≤0,05, perte acquis≤1, perte par strate≤1. Trois regards exploratoires, sans validation confirmatoire ni promotion.
- Rapport final :320 nouvelles questions horaires,10strates×32, seed111103, plus32acquis réutilisés. Exclusion des paires connues des anciens jeux et sondes ; le test final réservé n'est pas lu ni exploité.
- Deux générations neuves du parent sur352questions+8canaris avant optimizer, attribution desIDs aux mêmesGPU ; identité requise. Même processus et un chargement par GPU : aucune affirmation de deux chargements indépendants.
- Rapport après = candidat entraîné final306, même si la sélection conserve le parent.
- Mesures de format initial, structure heuristique, fausses comparaisons et troncatures ; une structure plausible n'est pas un oracle de chaîne mathématique.
- Temps, températuresGPU/HBM/CPU, puissances parGPU, énergieGPU intégrée, puissance secteur Shelly et étapes conservés.

## Exécution et conservation

Dossier serveur : /srv/eidolon/work/eva-learning-cycle10-repetition-20261111-4c1f2095.
Services : eidolon-eva-c10-preflight-4c1f2095 et eidolon-eva-c10-dual-4c1f2095.
L'orchestrateur attend le préflight, fait qualification-dual, puis run et finish_result.py.
Verrous globaux et manifestes figés ; aucun doublon ni source active modifiée.
Gardes : GPU/HBM83°C,CPU Tdie70°C, ECC/Xid/noyau, progression et télémétrie secteur.
Avant chaque chargement : nouvelles copiesRAM2x et doublesSHA ; aucun retest en boucle après défaut matériel.
Checkpoint complet tous20pas et aux fins de passage102/204/306. Pas de reprise automatique d'un run partiel.
Tous les poids, données, réponses, checkpoints et journaux sont conservés ; aucun modèle promu, aucun arrêt machine prévu.

Les fichiers *.py.txt sont des copies d'étude du code réel, expurgées des UUIDGPU/adressesLAN et non exécutables telles quelles. source-index.json distingue SHA original et SHA public. Les preuves de résultats seront ajoutées après exécution ; ces sources ne constituent pas une réussite d'entraînement.
