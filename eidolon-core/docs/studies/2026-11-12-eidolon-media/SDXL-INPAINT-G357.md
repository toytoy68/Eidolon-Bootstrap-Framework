# SDXL Inpainting - G357, 14 novembre 2026

Eidolon Core Technologies (ECT).

## Résultat

21 générations locales : 8 retouches natives par passe, deux répétitions et trois contrôles. Chaque passe obtient 0/8 propositions, 1 réserve et 7 rejets. La formulation ciblée n’améliore aucun verdict. Une main retrouve cinq doigts mais reste à revoir ; l’autre garde quatre doigts, le comptage des récipients reste faux, le fourreau manque et la tenue demeure noire.

Effet du prompt : première passe 0/8 proposées, 1 réserve ; passe ciblée 0/8 proposées, 1 réserve. Même source, masque, seed et recette dans chaque paire.

Préservation : la sortie brute modifie aussi des pixels hors masque. Le collage binaire avec la source assure leur conservation exacte, mais peut rendre les raccords visibles. Ce résultat vient du traitement, pas du modèle seul.

Décision : Chaîne techniquement viable, correction automatique non retenue avec ces masques et réglages. Le prompt ciblé ne change aucun verdict ; la main conserve une amélioration partielle.

Avis GPT sur une petite grille de retouches ; ce score ne se compare pas directement aux campagnes texte-vers-image.

## Méthode

Modèle : diffusers/stable-diffusion-xl-1.0-inpainting-0.1, révision 115134f3. Pipeline complet FP16 auteur, UNet dédié à neuf canaux. Licence CreativeML Open RAIL++-M et carte auteur archivées ; recherche privée locale, aucun poids redistribué.

Sources : quatre PNG G356 (01 main, 03 objets, 06 sabre, 07 duo), empreintes vérifiées. Quatre masques polygonaux binaires figés avant tout essai ; mêmes masques dans les deux passes, aucun ajustement après résultat.

Plan : 21 générations : contrôle 512² ; huit retouches natives 1024² avec prompts d’origine ; répétition et masques vide/plein ; huit retouches avec prompts ciblés et une seconde répétition. Deux seeds : 20261113 et 20261114. Aucune sélection de seed.

Recette : Euler auteur, CFG 8, 20 étapes demandées, force 0,99. Diffusers exécute 19 étapes et 19 appels UNet, mesurés. Négatif vide, pas de LoRA, refiner, super-résolution ou adoucissement du masque.

Précision : une V100 GPU0, UNet/CLIP FP16 ; VAE avec force_upcast FP32 dans la pipeline, tuilage. PyTorch 2.6.0+cu124 / Diffusers 0.32.2. Encodage VAE, latents et décodage finis contrôlés ; runtime inchangé.

Mesures : encodage texte/image + débruitage + décodage et contrôles numériques inclus ; chargement, sauvegarde et collage exclus. Écart hors masque calculé sur les PNG RGB, moyenne absolue par canal sur 255. Contrôle séparé de la sortie brute et du composite.

Limites : seconde passe choisie après observation de la première ; revue GPT non aveugle sur aperçus réduits. Masques manuels grossiers, seulement deux graines, force et guidage non balayés. Échec de cette recette ne prouve pas une incapacité générale du modèle.

Exploitation : inférence sans réseau, plafond 300 W et garde GPU/HBM 65/70 °C. Deux répétitions exactes, 84 PNG vérifiés (21 sources, masques, sorties brutes et composites). Aucun entraînement ni promotion ; services actifs, GPU libres, machine allumée.

## Provenance et chaîne

Modèle exact : `diffusers/stable-diffusion-xl-1.0-inpainting-0.1`, révision `115134f363124c53c7d878647567d04daf26e41e`. Tous les fichiers de la variante FP16 proviennent de ce dépôt public auteur, sans exécution de code distant. Fichiers LFS contrôlés par taille/SHA256, petits fichiers par blob Git, puis tous revérifiés par SHA avant chaque chargement. Modèle dédié UNet 9 canaux ; ce n’est pas un simple masque appliqué au SDXL texte-vers-image.

[Carte auteur figée](https://huggingface.co/diffusers/stable-diffusion-xl-1.0-inpainting-0.1/tree/115134f363124c53c7d878647567d04daf26e41e) ; [licence indiquée par l’auteur](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md). Attribution Diffusers team / Stability AI ; CreativeML Open RAIL++-M du 26 juillet 2023 conservée. Étude privée, non-intégration, aucun poids redistribué. Images sources G356 : RunDiffusion / KandooAI ; provenance et conditions du modèle source conservées dans G356.

Les champs EMA historiques du fichier de configuration UNet sont ignorés par Diffusers et restent visibles dans les journaux. Aucun patch du modèle, du scheduler ou du runtime. Le VAE est chargé FP16 et la pipeline utilise son option `force_upcast` pour l’encodage/décodage FP32 ; les valeurs finies sont contrôlées. SDPA MATH, quatre threads, fraction mémoire CUDA 0,88. Unités systemd temporaires, GPU0 seul à 300 W, réseau sortant interdit pendant l’inférence, verrou de campagne et garde GPU/HBM 65/70 °C. Aucun service d’inférence extérieur.

Les masques ont été dessinés avant toute retouche sur les quatre sources, puis conservés sans modification. La seconde passe est une adaptation après observation de la première, et non un essai aveugle pré-enregistré. Seul le prompt positif change dans chaque paire ; source, masque, seed, négatif vide, force, scheduler et guidage sont identiques. Les prompts intégraux sont conservés dans la synthèse et les intentions de chaque génération.

Le collage binaire est volontairement explicite et sans adoucissement : `Image.composite(raw, source, mask)`. Les pixels hors masque proviennent exactement de la source. La sortie brute n’offre pas cette garantie : le contrôle masque vide change 1 048 507 des 1 048 576 pixels, avec un écart moyen par canal de 2,398/255. Ce n’est pas une garantie de raccord visuel ; le collage peut montrer les différences de teinte et de texture au bord du masque.

## Poids

| Composant | Octets | SHA256 |
| --- | ---: | --- |
| text_encoder/model.fp16.safetensors | 246144867 | fc83cf401d930147807e7c44021c164bcc5508c9d4cc0ff35f4e354685ca9cd0 |
| text_encoder_2/model.fp16.safetensors | 1389382884 | a8622bd41f8d359df484fdf9de091edb9337a2fd747f0a5c9c320a62e24d1fd3 |
| unet/diffusion_pytorch_model.fp16.safetensors | 5135178560 | 6470840731e98cc16713ddf3ac7ee458c9fdbcb881a98c6727cd4a938f227d3f |
| vae/diffusion_pytorch_model.fp16.safetensors | 167335338 | 4ad62825e5c8b31eefb77355ba6693785619bf7d669d9b1a6fd9f19dec6d65b3 |

## Mesures appariées

| Passe | N natives | Médiane (s) | Proposées / réserves / rejets | MAE brute hors masque min-max (/255) | Écart maximal observé (/255) |
| --- | ---: | ---: | --- | --- | ---: |
| baseline | 8 | 11.836385 | 0/1/7 | 1.501793-4.992435 | 207 |
| focused | 8 | 11.840959 | 0/1/7 | 1.397405-5.400133 | 208 |

Toutes phases confondues : pic VRAM 10564 Mio, GPU/HBM 44/51 °C, puissance échantillonnée 307.86 W pour une limite configurée à 300 W. GPU1 et GTX1060 au repos. Aucune erreur de télémétrie ; une mesure de puissance instantanée ne donne pas l’énergie totale.

## Revue complète

| Passe / image | Avis GPT | Motif |
| --- | --- | --- |
| baseline/00 | Rejetée | Main très déformée, doigts amalgamés, contours artificiels et raccord du masque nettement visible. Le contrôle 512 valide l'exécution, pas la qualité. |
| baseline/01 | À revoir | Cinq doigts retrouvés, mais les deux doigts centraux se touchent, leur pose reste rigide et un raccord tonal du masque est perceptible. Amélioration anatomique partielle. |
| baseline/02 | Rejetée | La main conserve quatre doigts. Le fond et le poignet montrent aussi une différence de teinte au bord du masque. |
| baseline/03 | Rejetée | Trois récipients persistent : bol bleu à gauche, tasse rouge au centre, grande tasse gris-bleu à droite. L'anse rouge est déformée ; le nombre et la disposition restent incorrects. |
| baseline/04 | Rejetée | Récipients surnuméraires : deux bols imbriqués à gauche, tasse rouge centrale et tasse bleue à droite. La retouche ne corrige ni le comptage ni la disposition. |
| baseline/05 | Rejetée | Aucun fourreau ajouté. La bande masquée devient surtout une zone de tissu légèrement différente ; le sabre est conservé par la recomposition. |
| baseline/06 | Rejetée | Le fourreau reste absent. La retouche remplace essentiellement la texture du tissu dans le masque. |
| baseline/07 | Rejetée | La tenue demeure noire, avec une ceinture rouge remaniée. Le kimono rouge demandé n'apparaît pas ; visages et samouraï sont préservés hors masque par recomposition. |
| baseline/08 | Rejetée | Autre ceinture rouge et bas de vêtement modifié, mais la tenue reste noire. Le changement de couleur demandé échoue. |
| baseline/09 | À revoir | Répétition exacte de 01 dans les sorties brute et recomposée. Même amélioration partielle et mêmes réserves sur les doigts et le raccord. |
| baseline/10 | Contrôle réussi | Masque vide : la recomposition restitue exactement le PNG source. La sortie brute diffère pourtant presque partout, avec un écart moyen de 2,398/255 : le modèle seul n'est pas une opération sans effet. |
| baseline/11 | Rejetée | Masque plein : toute la sortie vient du modèle. Trois récipients persistent, bol à gauche et tasse rouge centrale ; aucune préservation hors masque n'est applicable. |
| focused/01 | À revoir | Cinq doigts sont présents, mais deux doigts centraux restent collés et la pose rigide. Le raccord du poignet et la différence de fond restent perceptibles. Aucun gain décisif face au prompt initial. |
| focused/02 | Rejetée | Toujours quatre doigts, malgré la mention explicite d'un pouce et de quatre doigts longs. Raccord tonal et texture peu naturelle. |
| focused/03 | Rejetée | La formulation ciblée améliore l'anse rouge, mais conserve trois récipients et le bol à gauche. Le défaut principal n'est pas réparé. |
| focused/04 | Rejetée | Le bol imbriqué disparaît, mais il reste un bol bicolore à gauche et deux tasses. Nombre, couleurs et positions ne respectent pas la demande. |
| focused/05 | Rejetée | Aucun fourreau ajouté, même en décrivant uniquement une gaine noire vide. La zone traitée reste du tissu ; le sabre est préservé par le composite. |
| focused/06 | Rejetée | Le fourreau reste absent. Changement de texture dans la bande masquée, sans création de l'objet demandé. |
| focused/07 | Rejetée | La ceinture et son pan deviennent plus rouges, mais manches, épaules et jupe demeurent noires. La consigne ciblant ces surfaces n'est pas satisfaite. |
| focused/08 | Rejetée | Tenue toujours noire et ceinture rouge, proche de la première passe. La recoloration demandée échoue. |
| focused/09 | À revoir | Répétition pixel-identique à 01 pour les versions brute et recomposée. Les cinq doigts et les mêmes réserves sont reproduits. |

## Vérifications et limites opérationnelles

21 générations, 19 appels UNet chacune ; deux répétitions exactes pour les versions brute et recomposée. 84 fichiers PNG vérifiés par SHA (sources et masques de chaque essai inclus) ; quatre originaux G356 et masques figés vérifiés. Aucun paquet/pilote modifié, configurations et sources runtime inchangées. Cinq services Core actifs, VM Memory-engine en marche, aucun client GPU restant. Machine laissée allumée.

L’utilitaire de clôture a initialement été lancé avec le Python système sans PIL, puis avec le venv sans chemin du paquet Core. Résolu en utilisant le venv existant et un chemin explicite vers les sources du résumé télémétrique ; aucune génération affectée ni installation effectuée. Incidents de clôture documentés séparément des journaux de génération.

Prochain essai discriminant possible : varier force/guidage et taille du masque, puis vérifier une retouche à partir d’une autre architecture. Ces variantes ne sont ni exécutées ni validées dans ce lot. Le score de retouche ne remplace pas le classement des modèles de génération.

## Conservation

PDF illustré de 14 pages : `libfile_fde3_f-2f146b9b99f08191bfdcd9229219d8fe_d168d29c22b4819186c4d3b8d1b7451f`. Originaux/masques/sorties : `/srv/eidolon/workspaces/media-20261112/sdxl-inpaint-g357/`. Poids : `/srv/eidolon/data/media-models-20261113/sdxl-inpaint-g357/`. Synthèse : `sdxl-inpaint-validation-g357.json`, preuves : `evidence-g357/`. Aucun avis utilisateur attribué, aucun entraînement ni promotion.
