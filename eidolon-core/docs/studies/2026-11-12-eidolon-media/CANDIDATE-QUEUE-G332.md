# File des modèles à tester — G332

Demande toytoy du 12/11/2026 : inclure tous les candidats repérés, y compris ceux
qui nécessitent les deux V100 SXM2 16 Go. Catalogue de recherche évolutif, pas
inventaire exhaustif de tous les checkpoints publiés. Aucun modèle de cette liste
n'est installé automatiquement et une ligne ne vaut ni licence acceptée ni test.

## Règles communes et ordre d'exécution

1. Vérifier poids exacts, licence complète et restrictions de la variante ; figer
   révision, taille et SHA256. Code, poids, encodeurs et LoRA peuvent avoir des
   licences différentes. Accès gratuit et poids ouverts ne signifient pas open source.
2. Vérifier Volta sm_70, pilote et runtime isolé ; aucun remplacement du pilote,
   CUDA ou ComfyUI fonctionnel. Aucun téléchargement pendant l'inférence.
3. Vérifier l'absence d'Eva et de tout autre client GPU ; libérer seulement les
   caches média. Tester petit puis augmenter : 512², 768×432, puis 1024×576 ou
   1024² selon entraînement du modèle. Les petites images ne valident pas la
   qualité à résolution native. Le cadrage 4:3 peut être posé sur un canevas 16:9
   avec bandes latérales, sans étirer le contenu.
4. Sur chaque candidat techniquement viable : main ouverte, katana/fourreau,
   comptage/couleurs, duo devant château ; au moins deux seeds, répétition d'une
   seed, comparaison à résolution et recette documentées. Ne pas comparer des
   paramètres incompatibles comme s'ils étaient identiques. Première passe
   matérielle limitée distincte d'une campagne qualité complète.
5. Mesurer chargement, encodage, génération, VRAM **par GPU**, puissance/limites,
   GPU/HBM, CPU et erreurs. Évaluer visuellement tous les résultats, pas seulement
   la validité PNG. Les échecs sont conservés. Pas d'apprentissage automatique
   sur une image simplement produite ; G329-02 reste rejetée et ancien LoRA invalidé.

Priorité immédiate : véritable répartition FLUX.1 Schnell (demande deux GPU),
puis RealVisXL/Juggernaut pour comparer les défauts du SDXL de base. Les autres
candidats restent dans la file, avec les blocages explicités ci-dessous.

## Images : tous les candidats de la recherche et variantes pertinentes

L'estimation « 2 × paramètres » donne seulement les octets des poids en 16 bits,
pas la VRAM totale : encodeurs, VAE, activations, contexte CUDA s'ajoutent.
Les colonnes matérielles décrivent un **chemin d'essai**, pas une compatibilité acquise.

| ID / modèle | Essai sur 16 Go | Essai sur 2×16 Go | Licence / porte à franchir | Statut initial |
| --- | --- | --- | --- | --- |
| I01 — SD 1.5 base | Témoin FP16 | Deux tâches indépendantes, contrôle du débit | CreativeML OpenRAIL-M | Déjà testé ; qualité limitée |
| I02 — SDXL base 1.0 | Témoin FP16, VAE FP32 | Composants répartis comme contrôle ; pas nécessaire à sa taille | CreativeML Open RAIL++-M | Déjà testé ; 12 rejets visuels G331 |
| I03 — SDXL inpainting dédié | Masques et préservation hors masque | Faible priorité multi-GPU | Licence de la variante exacte à vérifier | À qualifier ; ne pas confondre avec masque sur base |
| I04 — RealVisXL V5.0 FP16 | Checkpoint 6,94 Go ; 1024² FP16,30/50étapes réellement exécutées | Deux jobs pour débit restent non testés ; aucun besoin de fusion mémoire ici | OpenRAIL++ déclaré, carte et licence du SDXL de base archivées G333 | **Testé G333** :13PNG dont1répétition ;1/6proposée par condition30/50,1doute et4rejets ; [rapport](CHECKPOINTS-G333.md) |
| I05 — Juggernaut XL v9 | DPM++ 2M Karras30,CFG5,1024² FP16 exécuté | Idem I04 | OpenRAIL-M déclaré + restriction services API payants ; textes archivés G333 | **Testé G333** :7PNG dont1répétition ;2/6proposées,4rejets ; aucune promotion ; [rapport](CHECKPOINTS-G333.md) |
| I06 — Juggernaut XL variantes plus récentes | Sélection exacte après audit auteur | Idem I04 | Auditer chaque version ; ne pas hériter automatiquement de v9 | À identifier/figer avant téléchargement |
| I07 — FLUX.1 Schnell complet | Une carte FP16 seule non testée ; poids seuls 23,78 Go | Générateur FP16 réparti, encodeurs CPU ; tuilage VAE G339 | Apache-2.0 ; poids Comfy vérifiés, provenance G332 | **Testé G332 puis G339** :12 PNG G339,4/8 proposées,2 réserves,2 rejets ;6,451 s médianes 1024² à4étapes ; [comparatif dev](FLUX-COMPARISON-G339.md). Aucune promotion |
| I08 — FLUX.1 Schnell GGUF Q8 | Quantification + encodeurs CPU | Comparer à I07 pour qualité, vitesse et mémoire | Apache-2.0 + provenance conversion/runtime | À tester ; déquantification compatible Volta à prouver |
| I09 — FLUX.1 Schnell GGUF Q4 | Même protocole, perte possible de détails | Comparaison d'efficacité, pas nécessité mémoire | Idem I08 | À tester |
| I10 — FLUX.1 dev | Offload/quantification sur une carte non testé | Générateur complet FP16 réparti, encodeurs CPU, VAE en tuiles | FLUX.1 dev Non-Commercial v1.1.1 archivée ; poids publics Comfy de SHA identique BFL | **Testé G338** :12 PNG, répétition exacte ;4/8 propositions,2 réserves,2 rejets ; aucune promotion. [Rapport](FLUX-DEV-G338.md) |
| I11 — FLUX.2 klein 4B | **FP16 sur une V100 testé**, Qwen3 CPU FP32 et VAE GPU FP32 ; pic9 728Mio | GPU1 au repos ; répartition non nécessaire dans cette recette | Apache-2.0 ; révision et SHA auteur vérifiés | **Testé G340** :12PNG,5/8 proposées,3 rejets (main01 à six doigts et deux katanas) ;3,396s médianes GPU/décodage1024², encodage CPU57,175s/4textes ; [rapport](KLEIN-G340.md). Aucune promotion |
| I12 — FLUX.2 klein base 4B | FP16 GPU0, 50 étapes, CFG4 | GPU1 au repos | Apache-2.0, SHA vérifiés | **Testé G341** :12 images,5/8 proposées,3 rejets,63,26s médianes ; [rapport](KLEIN-BASE-G341.md). Aucune promotion |
| I13 — FLUX.2 klein 9B | Offload/quantification | ~18 Go de générateur seul : candidat répartition réelle | FLUX Non-Commercial License et obligations associées | Différé G342 : dépôt auteur soumis à acceptation HF ; aucun poids9B téléchargé. Licence/FP16/encodeurs restent à qualifier |
| I14 — FLUX.2 klein base 9B | Idem I13, plus d'étapes | Répartition explicite | Idem I13 | Non testé |
| I15 — FLUX.2 klein 9B-KV | Chemin mémoire spécifique | Répartition + budget cache à mesurer | Idem I13 | Non testé ; pas de supposition sur le cache |
| I16 — FLUX.2 dev 32B | Quantification/offload seulement | ~64 Go de poids 16 bits : **ne tient pas directement dans 2×16** | Licence exacte et runtime à auditer | Étude quantification/CPU, pas candidat FP16 intégral |
| I17 — Z-Image Turbo 6B | FP16 non testé ; Qwen3 CPU FP32 | Générateur FP32 réparti sur deux V100, VAE GPU0 FP32 ; pics14 068/14 490Mio | Apache-2.0 déclaré, carte et licence code auteur archivées | **Testé G342** :12PNG,4/8 proposées,2 réserves katana,2 rejets pour visiteurs ajoutés ;45,481s médianes1024² ; [rapport](ZIMAGE-G342.md). Aucune promotion |
| I18 — Z-Image base 6B | Idem, davantage d'étapes | Idem I17 | Licence exacte du checkpoint à archiver | Non testé ; pas d'édition annoncée mais indisponible |
| I19 — Qwen-Image 2.1 | Encodeur 8B séparé du générateur 7B, budget complet impératif | Répartition ou encodage CPU séquentiel | **Qwen Research License**, recherche/évaluation ; usage privé créatif non déduit | Essai recherche possible après audit ; intégration pas autorisée par cette étiquette seule |
| I20 — Qwen-Image 2.1 Turbo | Variante 8 étapes | Idem I19 | Idem I19 | Non testé ; support FP16/Volta non acquis |
| I21 — Qwen-Image / Edit antérieurs 20B | Quantification/offload | ~40 Go de générateur 16 bits : **pas intégralement dans 2×16** | Vérifier licence/version exactes, pas celle de 2.1 par analogie | Piste quantification/mixed precision, pas validation V10016 |
| I22 — FLUX.3 Image Klein 5,6B | Générateur + encodeur VL4B, budget à mesurer | Répartition possible à étudier ; prompt upsampler uniquement local | **FLUX Kommunity License**, distincte de la licence du code | Très expérimental ; pile amont récente, FP16 Volta non prouvé |
| I23 — FLUX.3 Image Klein Base | Idem, davantage d'étapes | Idem I22 | Idem I22 | Non testé |
| I24 — Stable Diffusion 3.5 Medium 2,5B | Générateur modeste mais encodeurs lourds | Encodeurs et/ou blocs séparés | Stability Community License, conditions/revenu à vérifier | Non testé, stabilité FP16 à vérifier |
| I25 — Stable Diffusion 3.5 Large / Large Turbo 8B | Générateur proche de 16 Go, offload nécessaire | Blocs répartis, encodeurs CPU | Idem I24, variante exacte à figer | Candidats deux GPU, non testés |
| I26 — Sana 0,6B / 1,6B FP16 | **600M G334 et 1600M G335 testés** : générateur FP16, encodeur CPU FP32, DC-AE GPU FP32 ; pics 7 878 / 9 832 Mio | Encodeur séparé / débit non testés ; GPU1 au repos | Sana/DC-AE Apache-2.0 ; Gemma2 garde ses conditions et restrictions | 12 générations par variante ; 600M : 2/8 proposées, 2 doutes, 4 rejets ; 1600M : 1/8 proposée, 2 doutes, 5 rejets. [G334](SANA-G334.md), [G335](SANA-G335.md). Aucune promotion |
| I27 — Sana Sprint 0,6B / 1,6B | Recette distillée distincte | Selon budget encodeur | Licence et FP16 à auditer séparément | Non testé ; annonce mémoire ≠ mesure V100 |

Les variantes d'une même ligne restent des essais séparés et auront leur propre
SHA/résultat. Les checkpoints spécialisés et LoRA sont ajoutés uniquement avec
leur référence exacte, leur licence et leur modèle de base ; aucun catalogue
tiers ni téléchargement automatique n'est activé.

## Vidéo : conserver les pistes et ouvrir la répartition

| ID / modèle | Chemin d'essai | Porte à franchir / statut |
| --- | --- | --- |
| V01 — Wan 2.1 T2V 1.3B | Reprendre témoin 320×256, 9/17 images ; monter progressivement | Déjà généré sur une V100, qualité encore expérimentale |
| V02 — SVD 14 images | I2V, témoin local puis résolution native progressive | Déjà généré ; licence Stability à conserver |
| V03 — SVD-XT 25 images | I2V, besoin mémoire supérieur au SVD testé | Poids/licence exacts à auditer ; non testé |
| V04 — AnimateDiff SD1.5 | G336 retrouvé, G337 : 6 clips, 2 contrôles SD1.5 | **Non validé** : textures sans scène ; SD1.5 seul fonctionne. Diagnostic de la chaîne vidéo à poursuivre. [Rapport G337](ANIMATEDIFF-G337.md) |
| V05 — Wan 2.1 T2V 14B | ~28 Go de générateur : blocs sur deux V100, T5 CPU | Activations vidéo peuvent dépasser le budget ; FP16 à tester |
| V06 — Wan 2.1 I2V 14B 480p | Même partage, encodeur image en plus | Pas de 480p d'emblée ; compatibilité bas format à vérifier |
| V07 — Wan 2.1 I2V 14B 720p | Après V06 seulement | Modèle distinct ; 720p cible amont, pas capacité validée |
| V08 — Wan 2.1 FLF2V 14B | Première/dernière image, partage explicite | Non testé, licence/conditionnement exacts à figer |
| V09 — Wan 2.1 VACE 1.3B | Contrôle/édition vidéo, une carte en premier | Licence et workflow propres, non testé |
| V10 — Wan 2.1 VACE 14B | Deux cartes + budget des modules de contrôle | Non testé, risque mémoire plus élevé que T2V seul |

Wan propose FSDP/xDiT en amont. Cela ne prouve ni un fonctionnement sur deux
V10016Go ni la compatibilité des kernels associés : auditer avant toute installation.
Les 14B ne sont pas déclarés « compatibles » sur la seule somme 32 Go.

## Ce que signifie utiliser les deux cartes

- **A — Indépendant** : deux jobs, chacun sur sa carte. Augmente potentiellement le
  débit mais pas la taille maximale d'un modèle.
- **B — Composants** : encodeur sur une carte, générateur sur l'autre. Ne résout
  pas un générateur qui dépasse lui-même 16 Go.
- **C — Blocs répartis** : un même générateur possède des couches sur les deux
  cartes. Vérifier chaque paramètre, exécuter et surveiller les activations.
- **D — Quantification/offload CPU** : solution supplémentaire, jamais présentée
  comme équivalente à un modèle FP16 intégral en VRAM.

L'essai G332 cible C pour FLUX Schnell, avec encodeurs CPU FP32 explicitement
séparés. Le plan initial donne 22,15 Gio de paramètres FP16 du générateur, avec
plafond de placement 12 Gio par carte. Ce plafond n'inclut pas les activations.
Mesurer les pics réels, le placement et les compteurs NVLink ; un compteur nul
ou non disponible ne permet pas d'affirmer un trafic NVLink observé. La présence
NV6 et l'accès CUDA peer-to-peer sont seulement des préconditions.

Avec 2×32 Go, réexécuter cette matrice : ne pas annoncer 64 Go unifiés. Les modèles
qui dépassent 32 Go par composant peuvent toujours nécessiter un partage explicite.

## Sources primaires et pistes de code examinées

- [RealVisXL V5](https://huggingface.co/SG161222/RealVisXL_V5.0),
  [Juggernaut v9](https://huggingface.co/RunDiffusion/Juggernaut-XL-v9).
- [FLUX.1](https://github.com/black-forest-labs/flux),
  [Schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell),
  [republication Comfy](https://huggingface.co/Comfy-Org/flux1-schnell),
  [encodeurs Comfy](https://huggingface.co/comfyanonymous/flux_text_encoders).
- [FLUX.2](https://github.com/black-forest-labs/flux2),
  [4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B),
  [9B](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B).
- [Z-Image](https://github.com/Tongyi-MAI/Z-Image),
  [débordement FP16](https://github.com/Tongyi-MAI/Z-Image/issues/15),
  [correctif proposé](https://github.com/Comfy-Org/ComfyUI/pull/11187).
- [Qwen 2.1 et sa licence](https://github.com/QwenLM/Qwen-Image-2.1),
  [proposition FP16](https://github.com/Comfy-Org/ComfyUI/pull/17686),
  [ancienne proposition mixed precision](https://github.com/Comfy-Org/ComfyUI/pull/12522).
- [Expériences communautaires Qwen V100](https://github.com/lotus0000/ComfyUI-Qwen-V100-MixedPrecision) :
  résultats rapportés sur V10032, ni validation de nos cartes16 ni autorisation
  d'exécuter l'extension sans audit. Le chiffre 28,63 Go concerne Qwen Rapid,
  pas une mesure démontrée du Qwen2.1 de notre essai.
- [FLUX.3](https://github.com/black-forest-labs/flux-3-image-klein) : code et poids
  ont des licences distinctes ; ses exemples CUDA récents ne remplacent pas notre pile.
- [SD3.5 Medium](https://huggingface.co/stabilityai/stable-diffusion-3.5-medium),
  [Large](https://huggingface.co/stabilityai/stable-diffusion-3.5-large).
- [Sana](https://github.com/NVlabs/Sana),
  [table des précisions](https://github.com/NVlabs/Sana/blob/main/docs/model_zoo.md).
- [Wan2.1, modèles et multi-GPU](https://github.com/Wan-Video/Wan2.1),
  [AnimateDiff](https://github.com/guoyww/AnimateDiff),
  [SVD-XT](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt).
- [Diffusers 0.32.2, grands modèles](https://huggingface.co/docs/diffusers/v0.32.2/en/tutorials/inference_with_big_models),
  [stable-diffusion.cpp / FLUX](https://github.com/leejet/stable-diffusion.cpp/blob/master/docs/flux.md).

Les PR de compatibilité sont des pistes, pas des correctifs considérés intégrés.
Leur état est à revérifier lors de l'essai de chaque candidat.
