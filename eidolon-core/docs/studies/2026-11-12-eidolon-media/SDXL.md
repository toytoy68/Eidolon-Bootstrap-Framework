# SDXL base 1.0 — validation V100, G327

Eidolon Core Technologies (ECT), 12 novembre 2026. Accord direct toytoy après
les limites qualitatives observées sur SD1.5. Aucun entraînement effectué.

## Implémentation isolée

Profil opt-in `sdxl-text` ; le profil SD1.5 par défaut reste inchangé.
Checkpoint officiel `sd_xl_base_1.0.safetensors`, révision
`462165984030d82259a11f4367a4eed129e94a7b`, 6 938 078 334 octets,
SHA256 `31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b`.
Téléchargement explicite via download_models.py --profile sdxl, taille/hash
vérifiés et reçu conservé sur X399. Pas de refiner, LoRA ou custom node ajouté.

Licence [CreativeML Open RAIL++-M](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/462165984030d82259a11f4367a4eed129e94a7b/LICENSE.md),
avec restrictions d'usage ; gratuit ne signifie pas licence sans conditions.
Copie locale : LAB/SDXL-LICENSE.md. Le modèle de base peut fonctionner seul selon
la [carte officielle](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/462165984030d82259a11f4367a4eed129e94a7b/README.md).

Runtime inchangé : ComfyUI0.3.26, torch2.6.0+cu124, FP16, VAE FP32,
attention divisée, sans xFormers. Nœuds natifs CLIPTextEncodeSDXL, deux entrées
textuelles et conditionnement des dimensions ; DPM++2M, Karras, CFG6.
La sélection du catalogue SD1.5 et de ses LoRA reste refusée pour ce profil.

## Mesures réelles

Même prompt et seed72420 que l'essai SD1.5 précédent, 30étapes. Modèle,
résolution, sampler et CFG changent : comparaison de configurations d'usage,
pas benchmark isolant le seul coût de l'architecture.

| Mesure | SD1.5 précédent | SDXL essai1 | SDXL répétition |
| --- | ---: | ---: | ---: |
| Résolution native | 768×432 | 1024×576 | 1024×576 |
| Temps API total | 7,36s | 17,94s | 18,65s |
| Pic VRAM relevé | 5008Mio | 8880Mio | 8880Mio |
| Charge GPU max | 99% | 100% | 100% |
| GPU max | 37°C | 37°C | 36°C |
| HBM max | 39°C | 40°C | 40°C |
| Puissance GPU max relevée | 213,77W | 227,86W | 222,76W |
| CPU Tdie max | non mesuré | 35,875°C | 36°C |
| Relevés | 32 | 76 | 79 |

GPU1 V10016Go seule ; GPU0 et GTX1060 à0% et respectivement1/2Mio. Consigne
GPU1 200W, lectures transitoires supérieures conservées. Ces watts ne mesurent
pas la consommation secteur. Échantillonnage demandé0,2s, plus durée des
lectures ; aucun maximum continu garanti. Durées comprenant file, chargement,
inférence et collecte, pas chargement isolé.

Deux recalculs avec caches Comfy libérés, sans purge du cache disque Linux.
PNG identiques SHA256 `459f8424fb2bdda107e7a434349b72a8ae14552f7e996f3bf30de366c8afedfd`.
Preuves privées : LAB/sdxl-probe-20261112-123358 (PNG, métadonnées, sondes).
[Mesures agrégées](sdxl-validation.json), [recette](sdxl_probe.py). Les images
et prompts utilisateur ne sont pas publiés dans Git.

## Qualité et limites

Inspection du PNG réel : deux personnages mieux différenciés, kimono rouge,
composition plus lisible et détails améliorés. Le bâtiment ressemble encore
à un pavillon plutôt qu'à un grand château ; armure, coiffure, mains et visages
restent imparfaits. Un cas ne démontre ni qualité photographique générale ni
amélioration universelle. Aucune note esthétique automatique.

Compatibilité 1024×576/30étapes validée sur cette V10016Go. Carré1024² et
preset4:3 (768×576) bornés/testés logiciellement, mais non générés dans cette
campagne. Aucun test SDXL édition/inpainting, LoRA ou refiner. Deux répétitions
ne remplacent pas une campagne longue de stabilité.

## Utilisation et vérifications

```json
{"profile":"sdxl-text","format":"16:9","output_size":"native",
 "prompt":"A mountain lake at sunrise","steps":30,"seed":42}
```

Via LocalGenerationClient ou POST/v1/jobs authentifié avec clé d'idempotence.
SDXL :1024×576 en16:9,768×576 en4:3 avec cadre1024×576 ;720p/1080p restent
des exports CPU. Sans format, SDXL prend1024². Aucun sélecteur HUD ajouté.

Unité API actuelle : `eidolon-media-api-sdxl-20261112.service`, remplaçant
uniquement l'ancienne unité média transitoire après file vide. Arguments
identiques plus `--enable sdxl-text`. Moteur dédié inchangé. API et moteur
conservent le réseau limité à localhost ; test de la nouvelle API : connexion
locale réussie,1.1.1.1:443 en timeout depuis son cgroup. Générations locales.
Services Core/comm/monitor/memory-tunnel/Ollama/Darme observés actifs après les
tests. Pas de modification pilote, Eva, Core ou Memory de production. Caches
GPU libérés à file vide après les recettes. Pas d'activation au démarrage.

Tests média :218 découverts,214pass/4skip en développement (PyAV absent),
213pass/5skip sur X399 (ffmpeg CLI absent). Tests SDXL :géométrie, conditionnement,
refus des modèles d'une autre famille et maintien des comportements SD1.5.
