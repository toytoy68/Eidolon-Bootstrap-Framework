# Protocole expérimental V100 Volta — performances, compatibilité et optimisation

**Statut : PROPOSITION POUR REVUE (Claude) — aucune modification de production autorisée par ce document.**  
Date : 2026-11-22 · Cible : Eidolon-OS / banc GPU · Version : 0.1

## 1. Objectif et hypothèses

Déterminer, sur les **deux Tesla V100 SXM2 16 Go** d'Eidolon-OS, les optimisations **réelles, reproductibles et économiquement pertinentes** pour l'inférence LLM et la génération d'images. Distinguer :

- **H0** : le logiciel actuel exploite déjà les V100 au mieux pour la charge choisie ;
- **H1** : une mise à jour ou un kernel Volta spécialisé améliore le débit / la latence / l'énergie ;
- **H2** : une différence apparente vient de la version logicielle, du cache, du contexte, du power cap ou de la température ;
- **H3** : une couche de compatibilité améliore la prise en charge de modèles récents, mais pas nécessairement leur vitesse.

**Important :** le projet [Zagitta/gpu-unlock](https://github.com/Zagitta/gpu-unlock) ne prend pas en charge Volta/GV100. Ne **pas** installer, forcer, patcher ou flasher ce module sur les V100. Il n'existe à ce stade **aucune preuve validée ici** d'une limitation firmware équivalente à celle de la RTX 3080 Ti.

## 2. Matériel de référence et périmètre

| Élément | Configuration connue / à revérifier au début |
| --- | --- |
| Hôte | X399 / Threadripper 1950X / 128 Go RAM / Debian 13 |
| GPU 0 | Tesla V100-SXM2-16GB, PCI 0000:0a:00.0, CUDA CC 7.0 |
| GPU 1 | Tesla V100-SXM2-16GB, PCI 0000:0c:00.0, CUDA CC 7.0 |
| Pilote observé | NVIDIA 550.163.01 |
| Alimentation / refroidissement | MSI 1000 W, watercooling V100 ; vérifier débit, pompe, températures |
| Limites de puissance | 150 à 300 W par V100, paliers 150 / 200 / 250 / 300 W |
| Ollama observé | 0.32.15 ; Flash Attention désactivé dans le service existant |
| Archivage | /srv/eidolon/work/v100-optimization/ (à créer) |

**Isolation :** ne jamais charger les deux GPU pour les tests *single-GPU* ; mesurer et enregistrer l'activité et la consommation de la carte non testée. Vérifier qu'aucune autre charge (Ollama, ComfyUI, VM passthrough) ne perturbe la mesure. Ne pas arrêter les services de production sans fenêtre de maintenance explicite. Éviter d'utiliser la même instance Ollama que les usages domestiques.

## 3. Sources à examiner — à valider avant toute adoption

- [llama.cpp](https://github.com/ggml-org/llama.cpp) : kernels CUDA, quantification, Flash Attention, issues Volta.
- [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) : chemin CUDA, FP16/FP32, performances V100, qualité numérique.
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) : workflows déterministes, mémoire GPU, précision et attention.
- [PyTorch](https://github.com/pytorch/pytorch) : support sm_70, compatibilité CUDA et kernels.
- [Zagitta/gpu-unlock](https://github.com/Zagitta/gpu-unlock) : **contre-exemple**, non compatible Volta.
- Projets communautaires mentionnés précédemment (« volta-forever », « Strata-V100 », « ninfer-v100 ») : **ne pas présumer leur existence, leur maturité ni leurs gains** ; vérifier URL, commits, licences, mainteneurs, compatibilité sm_70 et tests indépendants avant inclusion. Les annonces de gains « ×3 » concernent potentiellement un cas particulier et ne sont pas transposables à SDXL.

Consigner pour chaque candidat : URL canonique, commit SHA, licence, dépendances, modèle/format pris en charge, issue de référence, preuve indépendante, mécanisme exact et risque de régression.

## 4. Mesures communes et critères de validité

Avant **chaque série** : horodatage, version Debian/noyau/pilote/CUDA, SHA du binaire, SHA du modèle, GPU UUID, PCIe, horloges, power cap, température initiale, ECC (avant/après), consommation de base, GPU mémoire, configuration du refroidissement.

- Même modèle **exact** (hash), mêmes paramètres, même prompt et même workflow pour A et B.
- Première passe de chauffe **exclue** des statistiques ; au moins **5 répétitions mesurées** par point, idéalement 10.
- **A/B/A** ou ordre randomisé des variantes, pour éviter de confondre optimisation et dérive thermique.
- Métriques : médiane, dispersion (p10/p90 ou écart-type), temps total, latence première sortie, débit, pics et moyenne GPU W, températures, fréquence, VRAM, erreurs ECC.
- Shelly mesure **la plateforme entière** : relever puissance à vide et Wh de **lots continus ≥ 2 minutes**. Calculer Wh/1 000 tokens ou Wh/image en indiquant si la mesure inclut le repos, les warmups et les temps d'attente. Éviter les extrapolations depuis un lot de 15 s.
- Contrôler que la charge **s'exécute réellement** : logs d'exécution, GPU utilisé, sortie créée, checksum/qualité. Pour ComfyUI, changer les seeds de manière déterministe entre images, mais **utiliser la même liste de seeds dans chaque variante**. Une sortie cache en < 1 s n'est pas une génération.
- En cas de crash, d'erreur CUDA, d'image noire, de NaN ou de dégradation visible : **rejeter** la variante, même si elle est rapide.
- Interrompre immédiatement à **85 °C GPU**, erreurs ECC nouvelles non corrigées, Xid, pertes de communication, pompe/ventilation anormale ou instabilité. Respecter les limites matérielles et électriques du banc.
- Un gain n'est « confirmé » que si **≥ 5 %**, reproductible sur A/B/A, avec intervalles non ambigus, qualité conservée et sans coût énergétique excessif. Sinon « neutre/incertain ».

## 5. Phase 0 — audit et baseline, lecture seule d'abord

1. Inventorier GPU, pilote, CUDA, versions Ollama/llama.cpp/ComfyUI, modèles, versions Python/PyTorch, compilation sm_70 et ECC.
2. Contrôler disponibilité de 16 Go VRAM, PCIe, éventuelle interconnexion NVLink, température et puissance au repos.
3. Sauvegarder configs, scripts, logs, hashes et plan de retour arrière.
4. Définir un environnement **isolé** (venv/conteneur/VM adaptée) sans remplacer le pilote système ni le service Ollama principal.
5. Enregistrer la baseline à **150, 200, 250, 300 W** sur **GPU 0 puis GPU 1**.

**Sortie :** manifeste matériel, journal baseline, liste des limitations et état de sécurité.

## 6. Phase 1 — microbenchmarks CUDA et précision

- GEMM cuBLAS : FP32 SIMT, FP16 Tensor Core avec accumulation FP32, tailles 1024/2048/4096/8192 selon VRAM.
- Attention : longueurs de séquence 512/2048/8192 (si supportées), batch 1/4, comparaison kernels standard vs optimisés sm_70.
- Mesurer latence GPU par CUDA events après warmup, synchronisation correcte, puissance/thermique et exactitude par rapport à une référence.
- FP16, BF16, FP8 : **ne pas supposer de support matériel natif BF16/FP8 sur V100**. Toute émulation doit être explicitement signalée et testée pour précision et coût.
- Vérifier que les résultats ne viennent pas d'une simple différence de précision ou d'une baisse de qualité.

**Sortie :** tableau TFLOPS/latence/erreur numérique/W par kernel et palier.

## 7. Phase 2 — LLM : inférence réelle

Modèle fixe : **qwen2.5-coder:7b-instruct-q4_K_M**, hash exact, `num_ctx=8192`, `num_predict=384`, `temperature=0`, `seed=42`, une requête à la fois. Prompt :

> Écris un script Python autonome pour analyser un fichier CSV de mesures électriques avec les colonnes timestamp et watts. Calcule le minimum, le maximum et la moyenne par heure. Ajoute la gestion des lignes invalides, une interface en ligne de commande et trois exemples d’utilisation.

Comparer à environnement **et version moteur identiques** :
- A : backend Ollama/llama.cpp actuel, sans Flash Attention.
- B : Flash Attention si **réellement disponible et compatible**.
- C : backend/kernels CUDA optimisés sm_70, uniquement après revue du code.
- D : versions alternatives de llama.cpp / optimisations d'attention dans environnement séparé.

Relever `eval_count / eval_duration`, latence première génération, `prompt_eval_duration`, GPU offload complet, tokens exacts, erreurs, température et Wh/1 000 tokens. Ajouter un **long prompt / long contexte** : le décodage Q4 7B batch 1 peut être limité par la bande passante et masquer les gains de calcul.

**Référence historique, non contrôlée :** sur Eidolon-OS Ollama 0.32.15, V100 0 ≈ 112,66 tok/s à 250 W ; V100 1 ≈ 112,08 tok/s à 250 W. Ne pas présenter ces nombres comme comparaison A/B si la pile logicielle change.

## 8. Phase 3 — images SDXL et kernels Volta

Reprendre le workflow validé sur la RTX 3080 Ti : **SDXL Base 1.0**, checkpoint SHA vérifié, **1024×1024, 25 steps, Euler, CFG 7**, prompt et négatif constants, seeds déterministes partagées, un rendu par exécution.

Comparer :
- A : ComfyUI / PyTorch standard compatible sm_70, FP16 si stable ;
- B : variantes d'attention et de mémoire (xformers uniquement si compatible, PyTorch SDPA, slicing selon versions) ;
- C : stable-diffusion.cpp et kernels FP16/FP32 spécialisés, **si** même checkpoint et sorties qualitativement comparables ;
- D : moteurs plus récents via compatibilité uniquement si testés et sans modifications globales.

À chaque palier : warmup, ≥ 5 images distinctes, puis lot ≥ 2 min, qualité inspectée (artefacts, NaN, images noires, anatomie), métriques temps médian, images/min, Wh/image, VRAM max et GPU temp.

**Référence RTX uniquement indicative** : 3080 Ti avec gpu-unlock ≈ 5,22 s/image à 300 W ; sans ≈ 7,22 s. Le gain RTX ne prédit pas un gain V100.

## 9. Phase 4 — deux GPU, NVLink et scalabilité

Une fois les deux cartes **individuellement validées** :
- 1 job/GPU en parallèle : débit total, équité, Wh/image, Wh/1 000 tokens.
- Modèle réparti sur deux GPU : vérifier placements de couches, transferts et overhead. **NVLink n'agrège pas automatiquement la VRAM**.
- Charge mixte (LLM + SDXL) : isoler les modèles, surveiller mémoire, concurrence CPU/PCIe et consommation.
- Tester 150/200/250 W par carte d'abord ; 300 W uniquement si alimentation et refroidissement restent dans les marges sûres.

## 10. Critères d'adoption / rejet

**Adopter** si : gain médian ≥ 5 % confirmé par A/B/A, sorties valides, ECC inchangé, stabilité sur ≥ 30 min, efficacité énergétique égale ou meilleure, maintenance maîtrisée, rollback testé.

**Conserver comme expérimental** si : gain ponctuel, dépendances fragiles, versions figées, précision légèrement modifiée, gain limité à un modèle ou surcoût énergétique.

**Rejeter** si : GPU non supporté, modification firmware/BIOS risquée, instabilité, pertes ECC, NaN, baisse de qualité, gains non reproductibles ou incompatibilité avec les services Eidolon.

Aucune optimisation ne doit être déployée sur la pile principale sans **revue Claude + approbation utilisateur**.

## 11. Format des résultats et livraison

Arborescence proposée :

```text
/srv/eidolon/work/v100-optimization/
  manifest.json
  baseline/{gpu0,gpu1}/
  candidates/<candidate-id>/
  logs/
  images/
  comparisons/
  rollback/
  REPORT.md
```

Chaque résultat JSONL : `timestamp, host, gpu_uuid, gpu_index, candidate, commit_sha, model_sha, driver, cuda, power_limit_w, gpu_power_mean_w, gpu_temp_max_c, shelly_wh, elapsed_s, output_count, quality_status, errors, notes`.

Rapport final : classement **débit**, **Wh/unité**, **fiabilité**, **complexité de maintenance**, verdict par candidat (**VALIDÉ / À REVOIR / REJETÉ**), preuves et procédure de rollback.

## 12. Questions de revue à Claude

1. Le protocole isole-t-il correctement les variables entre moteurs et architectures ?
2. Quelles bibliothèques/kernels sm_70 sont réellement maintenus et compatibles avec Debian 13, NVIDIA 550, CUDA 12.4 ?
3. Comment garantir un benchmark SDXL non caché, et une comparaison visuelle/numérique honnête entre moteurs ?
4. Les mesures Shelly sur X399 peuvent-elles être normalisées malgré la consommation CPU/RAM de base ?
5. Quels tests ECC/Xid, watchdog thermique et mécanismes de rollback manquent ?
6. Quels projets communautaires méritent validation, avec **références vérifiables** plutôt que promesses de performance ?
7. Quelles modifications proposer sous forme de PR distinctes (instrumentation, baseline, candidats) ?

**Attendu de Claude :** critique technique argumentée, corrections proposées et matrice de risques. **Ne pas fusionner ni exécuter automatiquement.**
