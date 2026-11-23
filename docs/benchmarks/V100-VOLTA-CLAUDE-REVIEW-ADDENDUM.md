# Addendum de revue Claude — garde-fous obligatoires avant campagne V100

Date : 2026-11-22. Statut : corrections proposées sur PR #21, **non déployées**.

Cet addendum complète et, en cas de conflit, **prime** sur le protocole v0.1. Les affirmations de versions et les gains communautaires restent à vérifier sur sources officielles avant installation.

## Blocages avant tout benchmark

1. **Cache LLM** : séparer le microbenchmark **llama-bench** (pp/tg fixes, -r répétitions, politique de cache documentée) du benchmark **Ollama bout-en-bout** (préfixe unique par requête ou rechargement du modèle). Journaliser prompt_eval_count, prompt_eval_duration, eval_count, eval_duration, EOS/arrêt anticipé et réponse complète. Temperature=0 ne garantit pas une longueur identique entre variantes.
2. **Power cap et production** : nvidia-smi -pl modifie la carte entière. Exiger une fenêtre de maintenance autorisée ou la réservation effective d'un GPU sans processus de production ; vérifier avec nvidia-smi et les services. Sauvegarder les limites initiales **par UUID**, les restaurer dans un trap/finally même après interruption et confirmer la restauration. **Pas de changement de cap pendant l'audit lecture seule.**
3. **Identité GPU** : CUDA_DEVICE_ORDER=PCI_BUS_ID, sélection par **UUID**, enregistrer la correspondance UUID ↔ PCI ↔ CUDA/NVML ; ne jamais présumer que GPU 0 = 0a:00.0.
4. **Compatibilité SDXL** : environnement isolé, version PyTorch et wheel CUDA avec sm_70 effectivement présent (candidat torch <=2.14 + cu126 **à confirmer**), vérifier torch.cuda.get_arch_list(), is_available(), device réel, et absence de repli CPU. Ne pas installer CUDA 13 ou remplacer le pilote système. Fixer VAE FP32 **ou** sdxl-vae-fp16-fix (hash), même choix pour A et B ; rejeter NaN/images noires.
5. **Watchdog** : seuil GPU 85 °C, température HBM si exposée (sinon déclarer indisponible), ECC avant/après, pages retirées (nvidia-smi -q -d PAGE_RETIREMENT), Xid journalctl -k, températures ambiantes, horloges SM/mémoire et raisons de throttling ; arrêt du job si anomalie. Ne pas supposer que toutes les métriques existent sur le pilote.
6. **Énergie** : lire le **compteur Wh Shelly** avant/après chaque lot >=2 min. Mesurer le repos dans la même session avec modèle chargé ; publier Wh bruts, Wh nets (brut − repos × durée), puissance GPU NVML et résidu plateforme. Répéter A/B/A.
7. **NUMA et topologie** : relever nvidia-smi topo -m et numactl --hardware avant de décider de l'affinité ; vérifier NVLink et P2P via nvidia-smi nvlink -s. Ne pas répartir un 7B Q4 sur deux V100 pour prétendre démontrer l'intérêt du multi-GPU ; utiliser un modèle qui ne tient pas dans 16 Go.
8. **Limite théorique** : 900 Go/s ÷ 4,7 Go ≈190 tok/s est un ordre de grandeur mémoire pour un 7B Q4, pas une limite stricte : KV, cache, calcul, bande passante effective et overhead modifient le résultat.
9. **Versions de moteurs** : identifier le llama.cpp réellement embarqué dans Ollama avant toute comparaison. Évaluer ensuite les kernels Volta Flash Attention/MMVQ sur commit figé dans une instance séparée ; ne pas confondre version moteur et kernel.
10. **Candidats communautaires** : vérifier les URL, mainteneurs, licences, commits et résultats de geoffwatts/ninfer-v100, Leonccaa/ReVolta et flash-attention-legacy. Les noms « volta-forever » et « Strata-V100 » ne sont pas validés. Aucun fork non audité sur la production.

## Ordre de livraison proposé

- **PR instrumentation** : inventaire lecture seule, schéma JSONL, cap rollback, compteur Shelly, watchdog, Xid/ECC.
- **PR baseline** : llama-bench + Ollama anti-cache, GPU par UUID, 150/200/250/300 W seulement après autorisation de fenêtre.
- **PR llama.cpp** : kernels Volta et version récente dans un environnement séparé.
- **PR SDXL** : torch sm_70 confirmé, VAE fixé, mêmes seeds, sorties contrôlées.
- **PR multi-GPU** : NVLink/P2P et modèle >16 Go.

## Schéma de mesure additionnel

Ajouter au JSONL : gpu_uuid, gpu_pci_bus_id, cuda_device_order, numa_node, sm_clock_mhz, memory_clock_mhz, throttle_reasons, hbm_temp_c_or_null, ambient_temp_c_or_null, ecc_before_after, retired_pages_before_after, xid_events, shelly_wh_raw, shelly_wh_net, idle_w_model_loaded, cache_policy, prompt_eval_count, eval_count, eos_reason, vae_precision, torch_arch_list, rollback_verified.

**Critère d'entrée** : aucune modification des pilotes, du firmware, des services IA ou du plafond de puissance sans contrôle explicite des préconditions. **Critère de sortie** : A/B/A reproductible, qualité inchangée, absence de Xid/ECC nouveau, température sûre, rollback validé, revue Claude et accord utilisateur avant production.
