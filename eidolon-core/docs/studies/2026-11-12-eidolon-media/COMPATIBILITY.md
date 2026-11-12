# Modèles, licences et compatibilité Volta

Vérification des sources primaires le 12/11/2026. Tailles décimales de fichiers,
VRAM en Mio/Gio selon libellé. Une estimation n'est jamais une mesure V100.
Poids ouverts/gratuits ne signifient pas code et données intégralement open source.

| Solution | Licence des poids / restrictions | Poids sélectionnés ou repérés | V100 16 Go / 32 Go | FP16 et usages |
| --- | --- | --- | --- | --- |
| SD 1.5 | CreativeML OpenRAIL-M : licence avec restrictions d'usage et obligations de redistribution | Checkpoint safetensors 4,265 Go | **Testé 16 Go**, environ 4,0–4,3 Gio observés ; 32 Go non testée | Texte/image, img2img et masque réels ; base standard, pas checkpoint spécialisé inpainting |
| SDXL base 1.0 | CreativeML Open RAIL++-M, restrictions d'usage | 6,938 Go, sans refiner | **Testé 16 Go en G327**, 8880 Mio au pic ; 32 Go non testée | FP16 + VAE FP32 réels, 1024×576, 17,94–18,65 s ; carré1024² non testé. Voir SDXL.md |
| Wan 2.1 T2V 1.3B | Apache-2.0 pour le dépôt de poids retenu ; notices à conserver | Diffusion FP16 2,838 Go + UMT5 FP16 11,366 Go + VAE 0,254 Go | **Testé 16 Go**, pic observé 13 200–13 264 Mio ; 32 Go non testée | T2V réel ; ce checkpoint T2V n'est pas un modèle I2V |
| Stable Video Diffusion, 14 images | Stability AI Community License du 05/07/2024 ; usage personnel/évaluation gratuit. Usage commercial : conditions dont enregistrement et seuil de revenu, pas licence permissive inconditionnelle | `svd.safetensors` 9,560 Go | **Testé 16 Go**, 5 008–11 888 Mio selon ordre/cache ; 32 Go non testée | I2V réel ; pas de commande textuelle détaillée de l'animation |
| AnimateDiff SD1.5 | Module Apache-2.0 ; licence du modèle de base également applicable | Module v1.5/v2 environ 1,67/1,82 Go, en plus du checkpoint | Candidat 16 Go, budget exploratoire 8–14 Gio ; **non testé** | FP16 envisageable ; 256/512², 16 images à commencer. Extension Comfy dédiée à auditer |
| FLUX.1-schnell | Apache-2.0 pour les poids publiés ; différent de FLUX.1-dev | Diffusion 23,783 Go + AE 0,335 Go, encodeurs en plus | 16 Go : offload/quantification indispensables ; 32 Go : placement encore à étudier | Alternative image plus récente ; conversion FP16/numérique et coût PCIe à qualifier, aucun test réel |

## Mesures et plafonds prudents

| Profil livré | Recette réellement exercée | Temps API observé | Résolution maximale validée / suite |
| --- | --- | --- | --- |
| SD1.5 texte | 512², 20 étapes, seed 42 | environ 4,4 s ; premier chargement direct moteur 5,76 s | 512² qualifié ; calcul 768² interrompu volontairement pour le test d'annulation, pas qualifié en sortie |
| SD1.5 édition/masque | 512², 20 étapes | 4,5–5 s | Fidélité au prompt limitée ; conservation hors masque vérifiée |
| Wan 1.3B | 320×256, 9 puis 17 images ; 10 puis 20 étapes | 15–24 s | 320×256/17 images validé techniquement ; 480p et clips longs non mesurés |
| SVD | 320×256, 14 images, 15 étapes | 18–25 s | 320×256/14 images validé techniquement ; 1024×576 natif non essayé |

Ces temps comprennent la file locale, le chargement/caches OS, l'inférence,
la collecte et l'export ; ce ne sont pas des temps de calcul isolés. Les caches
Comfy ont été remis à zéro entre répétitions, sans vider le cache disque Linux.
Le temps de chargement séparé n'a pas été instrumenté de manière comparable
sur tous les modèles : ne pas le déduire des seules durées globales. Qualité
vidéo encore exploratoire, faible résolution et peu d'étapes.

## Runtime retenu et limites matérielles

ComfyUI **0.3.26**, commit `9aac21f894a122ddb8d825c57ad61c0db5e630db` ;
PyTorch **2.6.0+cu124**, torchvision 0.21.0+cu124, torchaudio 2.6.0+cu124,
Transformers 4.49.0, PyAV 14.2.0. Choix conservateur correspondant au pilote
550 et au support `sm_70` réellement constaté, pas une affirmation sur la
« dernière version compatible ». L'ancienne affirmation torch 2.14/cu126 de
la branche vidéo n'est pas utilisée comme preuve de compatibilité.

- FP16 pour diffusion/encodeurs ; VAE en FP32. UMT5 FP16 réellement chargé sur V100.
- BF16 et FP8 natifs non disponibles sur Volta ; aucun chemin nécessitant ces
  calculs retenu. Un fichier BF16/FP8 et un calcul compatible sont deux questions
  distinctes ; le profil téléchargé Wan est explicitement FP16.
- Attention divisée ComfyUI, xFormers désactivé, aucun FlashAttention/SageAttention.
- Triton 3.2.0 est une dépendance installée de torch ; aucun kernel Triton
  personnalisé ni compilation JIT ajoutée pour ces recettes.
- Toutes les extensions custom sont désactivées. Aucun Manager, GGUF ou plugin
  multi-GPU installé. Le nœud natif SaveWEBM est suivi d'un export H.264 CPU PyAV.

## Sources et traçabilité

- [SD1.5, carte du modèle](https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5)
  révision `451f4fe16113bff5a5d2269ed5ad43b0592e9a14` ; miroir du modèle historique,
  fichier safetensors vérifié par SHA256 LFS. Restrictions OpenRAIL conservées.
- [SDXL, licence](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md),
  métadonnées à `462165984030d82259a11f4367a4eed129e94a7b`.
- [Wan officiel](https://github.com/Wan-Video/Wan2.1) et
  [conditionnement Comfy-Org](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged),
  révision de téléchargement `123acf1cc74bccbb9bfff8ac1ee72edc08c2341d`.
  Les 8,19 Go annoncés en amont ne sont pas repris comme mesure de notre workflow.
- [SVD, licence de la révision téléchargée](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid/blob/9cf024d5bfa8f56622af86c884f26a52f6676f2e/LICENSE.md).
  Powered by Stability AI. This Stability AI Model is licensed under the Stability
  AI Community License, Copyright © Stability AI Ltd. All Rights Reserved.
- [AnimateDiff officiel](https://github.com/guoyww/AnimateDiff),
  [poids](https://huggingface.co/guoyww/animatediff), révision `fdfe36afa161e51b3e9c24022b0e368d59e7345e`.
- [FLUX.1-schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell),
  métadonnées à `741f7c3ce8b383c54771c7003378a50191e9efe9`.
- [ComfyUI, code retenu](https://github.com/Comfy-Org/ComfyUI/tree/9aac21f894a122ddb8d825c57ad61c0db5e630db), GPL-3.0.

Les cinq fichiers réellement téléchargés, leurs tailles, révisions et SHA256
complets sont figés dans `download_models.py`. Aucun poids n'est redistribué
dans ce dépôt. Pour chaque futur checkpoint/LoRA, vérifier sa propre licence,
son modèle de base et ses éventuelles restrictions avant de l'inscrire au catalogue.
