# Juggernaut X v10 face à v9 — G353, 14 novembre 2026

Eidolon Core Technologies (ECT).

## Résultat et décision

Juggernaut v10 : 1/8 images proposées, contre 3/8 en v9. Même recette sur une V100 ; 17.56 s médianes pour v10 et 17.60 s pour v9.

Constat visuel : V10 conserve de belles textures mais perd une main correcte face à v9. Les deux échouent sur les objets comptés et les katanas ; le duo reste sensible à la seed.

Temps : encodage des textes, génération et décodage compris ; chargement et écriture PNG exclus. Les temps FLUX des rapports précédents excluaient l’encodage : comparaison directe de vitesse à éviter.

Matériel : GPU0 seul ; maxima GPU/HBM v10 44/52 °C, v9 46/55 °C. Répétitions pixel-identiques pour les deux modèles.

Décision : V10 ne remplace pas v9 pour cette grille. Conserver les deux comme options spécialisées ; aucun nouveau modèle par défaut. Les propositions sont des avis GPT provisoires, aucune validation utilisateur attribuée.

## Méthode

Plan : douze images par modèle : contrôle 512², huit natives 1024², répétition, 1024 × 576 et 768 × 576. Quatre scènes, seeds 20261113/20261114. Prompts figés et négatif vide, aucun refiner, LoRA, retouche ou tri des seeds.

Recette commune : DPM++ 2M Karras, 30 étapes, CFG 5 ; dimensions originales/cibles égales à la sortie, crop 0. Trente appels UNet mesurés, latents et décodage finis. V9 régénéré dans le même lot. Poids complets de chaque checkpoint, y compris encodeurs et VAE.

Précision : UNet et encodeurs GPU0 FP16, VAE avec upcast FP32 au décodage ; tuilage activé. Même Diffusers 0.32.2 / PyTorch 2.6.0+cu124 / Transformers 4.49.0 que G333. Aucun paquet installé ni runtime modifié.

Provenance : v10 RunDiffusion 35e4f3cc, v9 cf419233 ; fichiers safetensors SHA vérifiés. CreativeML OpenRAIL-M déclaré, restriction de service API payant et conditions du SDXL de base archivées. Essai privé local.

Incident corrigé : premier essai arrêté avant image lors de l’écriture du réglage -inf en JSON. Exporteur corrigé pour représenter cette valeur en texte ; calcul du scheduler inchangé. Essai et source initiaux conservés.

Mesure : temps encodage + débruitage + décodage + contrôles, hors chargement et sauvegarde PNG. Sonde GPU/HBM/VRAM/puissance ; ordre fixe v10 puis v9. Pics thermiques échantillonnés, pas comparaison d’efficacité énergétique.

Isolation : une V100 à 300 W, garde 65 °C GPU / 70 °C HBM. Inférence sans accès réseau sortant, verrou de campagne, limites de ressources. GPU libres et services actifs après les tests ; machine allumée.

Limites : revue GPT non aveugle sur aperçus réduits, huit natives seulement. 1024² sert au comparatif ; les formats auteur 832 × 1216 / 1216 × 832 restent non testés. Aucun score universel ni promotion automatique.

Chaque variante a douze sorties : contrôle main 512², quatre scènes × deux seeds à 1024², répétition de la première main, duo 1024×576 et 768×576. Seeds 20261113/20261114, prompts identiques au lot FLUX pour faciliter la revue de contenu. Comparatif v9/v10 strictement apparié : même DPM++2M Karras, 30 étapes, CFG5, négatif vide, dimensions originales/cibles égales à la sortie, crop0. Aucun upscaling ni refiner ou LoRA. Le carré 1024² sert de géométrie commune, tandis que la carte auteur v10 recommande 832×1216/1216×832 : ces deux géométries restent non testées.

V9 est régénéré pour étendre le témoin G333 au duo et aux formats écran. Les sept comparaisons de pixels avec G333 (six natives communes et répétition) sont toutes identiques. G333 utilisait six natives ; G353 en utilise huit. Ne pas comparer directement les fractions 2/6 et n/8 comme une évolution du modèle. Pas de conclusions de généralisation sur deux seeds.

## Poids et licences

- V10 standard RunDiffusion/Juggernaut-X-v10, révision 35e4f3ccbe745c3e1221715d04a452aaa1ee5761. Fichier Juggernaut-X-RunDiffusion-NSFW.safetensors, 7 105 348 672 octets, SHA256 d91d35736d8f2be038f760a9b0009a771ecf0a417e9b38c244a84ea4cb9c0c45. Le nom du checkpoint ne décrit pas le contenu du benchmark, constitué de quatre scènes publiques non explicites.
- V9 RunDiffusion/Juggernaut-XL-v9, révision cf419233522daa0b9ea36c3aff98fa2cab1fb0fb. Fichier déjà local, 7 105 348 188 octets, SHA256 c9e3e68f89b8e38689e1097d4be4573cf308de4e3fd044c64ca697bdb4aa8bca. Empreinte revérifiée, aucun nouveau téléchargement v9.
- CreativeML OpenRAIL-M déclaré par les cartes auteur, restriction de déploiement derrière une API payante conservée. Carte v10 figée et vérifiée par blob Git, carte v9 G333 et textes OpenRAIL-M/SDXL OpenRAIL++-M archivés. Ce lot est une évaluation privée locale ; aucune affirmation de liberté commerciale universelle.

Chaque checkpoint fournit son UNet, ses encodeurs et son VAE : la comparaison porte sur l’ensemble du checkpoint et pas uniquement les poids du débruiteur. Pas de partage silencieux d’encodeur/VAE entre variantes.

## Exécution et instrumentation

Même runtime preference-lab que G333 : PyTorch2.6.0+cu124, Diffusers0.32.2, Transformers4.49.0 ; aucun paquet installé. Configs SDXL locales et sources du runtime empreintées avant/après. UNet et encodeurs FP16 sur GPU0 ; force_upcast du VAE pour le décodage, tuilage activé. Paramètres de pipeline et scheduler archivés par modèle. Attention PyTorch MATH, Flash/Memory Efficient désactivées, cudnn benchmark désactivé. 4 threads PyTorch, fraction mémoire 0,88 sur une V100 Volta précisément identifiée par UUID.

Instrumentation non modificatrice : 30 appels UNet par image, latents contrôlés après chaque étape et valeurs décodées finies. Les temps incluent encodage texte, débruitage, décodage, contrôles et synchronisation ; ils excluent chargement et sauvegarde du PNG. Les rapports FLUX précédents excluent l’encodage : leurs médianes ne sont pas un chronomètre équivalent. Pics GPU/VRAM/HBM/puissance échantillonnés, pas de Wh secteur attribués aux GPU. Ordre fixe v10 puis v9 : les températures ne classent pas l’efficacité thermique des modèles.

Premier contrôle interrompu avant toute image : l’export JSON strict refusait lambda_min_clipped=-inf du scheduler. Seul l’exporteur transforme maintenant les valeurs non finies en chaînes ; aucune modification du calcul du scheduler. Source initiale et run00-config-json-failed conservés. Contrôle 512² puis campagne complète achevés après correction.

Unités transitoires utilisateur toytoy, réseau sortant interdit, verrou de campagne, 72Go RAM/800%CPU/90min au maximum. GPU0 V100 à 300 W, garde65°C GPU/70°C HBM ; GPU1 et GTX1060 au repos. Aucun arrêt d’Eva ni changement de pilote/service/production. Aucun entraînement, LoRA, déploiement ou promotion.

## Mesures

| Modèle | N natives | Médiane / min / max (s) | Pic VRAM (Mio) | GPU / HBM (°C) | Puissance pic (W) | Proposées / réserves / rejets |
| --- | ---: | --- | ---: | --- | ---: | --- |
| v9 | 8 | 17.600301 / 17.583999 / 17.624992 | 12790 | 46 / 55 | 313.64 | 3 / 0 / 5 |
| v10 | 8 | 17.564765 / 17.537049 / 17.814008 | 11538 | 44 / 52 | 319.36 | 1 / 1 / 6 |

Chargements grille : v10 3.746163s, v9 3.622077s.

24 images terminées après correction de l’export JSON ; 30 appels UNet par image et deux répétitions exactes. Contrôle final 2026-11-14T22:10:49.496490+01:00 : sources et runtime inchangés, empreintes de 24 PNG vérifiées, GPU libres, services actifs et Memory-engine en fonctionnement. Machine laissée allumée.

## Revue de chaque image

| Image | Condition | Temps (s) | Avis GPT | Commentaire |
| --- | --- | ---: | --- | --- |
| G353-v10-00 | hand / smoke | 3.804 | Rejetée | Quatre doigts visibles et main déformée ; poignet sur le côté au lieu du bas. |
| G353-v10-01 | hand / quality | 17.814 | Rejetée | Seulement quatre doigts bien formés visibles, pouce compris ; anatomie non conforme. |
| G353-v10-02 | hand / quality | 17.551 | Proposée | Cinq doigts distincts, main entière et poignet visible ; texture de peau détaillée. |
| G353-v10-03 | objects / quality | 17.537 | Rejetée | Trois objets au lieu de deux : un bol et deux tasses. Le bol est à gauche. |
| G353-v10-04 | objects / quality | 17.550 | Rejetée | Trois objets, couleurs et positions incorrectes : bol bicolore ajouté entre deux tasses. |
| G353-v10-05 | katana / quality | 17.563 | Rejetée | Plusieurs lames et poignées superposées ; assemblage incompatible avec un katana et son fourreau séparés. |
| G353-v10-06 | katana / quality | 17.567 | Rejetée | Deux lames, pièces supplémentaires et fourreau trop court ; géométrie incohérente. |
| G353-v10-07 | duo / quality | 17.573 | À revoir | Deux adultes en pied et tenues correctes, mais visage de la femme flou et main tendue peu définie. |
| G353-v10-08 | duo / quality | 17.578 | Rejetée | Trois adultes au lieu des deux demandés : un second samurai a été ajouté. |
| G353-v10-09 | hand / repeat | 17.573 | Rejetée | Répétition de la main 01 : quatre doigts visibles, anatomie non conforme. |
| G353-v10-10 | duo / screen16x9 | 8.953 | Rejetée | La femme est à gauche et le samurai à droite, contrairement au prompt ; haut du casque coupé. |
| G353-v10-11 | duo / screen4x3 | 5.995 | À revoir | Deux adultes en pied et positions correctes ; tenue de la femme ambiguë, proche d’un pantalon, mains peu définies. |
| G353-v9-00 | hand / smoke | 3.463 | Rejetée | Quatre doigts visibles, pouce compris ; poignet latéral et anatomie déformée. |
| G353-v9-01 | hand / quality | 17.584 | Proposée | Cinq doigts séparés, main entière et poignet visible ; rendu de peau plausible. |
| G353-v9-02 | hand / quality | 17.592 | Proposée | Cinq doigts distincts et main entière ; anatomie visuellement plausible. |
| G353-v9-03 | objects / quality | 17.592 | Rejetée | Quatre récipients au lieu de deux, avec bol à gauche et couleurs répétées. |
| G353-v9-04 | objects / quality | 17.597 | Rejetée | Trois récipients au lieu de deux ; bol bicolore central et tasse rouge à droite. |
| G353-v9-05 | katana / quality | 17.604 | Rejetée | Plusieurs lames et poignées ; éléments tronqués et assemblage incohérent. |
| G353-v9-06 | katana / quality | 17.607 | Rejetée | Plusieurs poignées et éléments de sabre ; géométrie incompatible avec un seul katana et son fourreau. |
| G353-v9-07 | duo / quality | 17.625 | Rejetée | Trois adultes au lieu de deux : le samurai est dupliqué. |
| G353-v9-08 | duo / quality | 17.624 | Proposée | Deux adultes en pied, samurai à gauche et kimono rouge à droite ; positions et tenues respectées. |
| G353-v9-09 | hand / repeat | 17.622 | Proposée | Répétition exacte de la main 01, avec cinq doigts distincts. |
| G353-v9-10 | duo / screen16x9 | 8.946 | Rejetée | Positions inversées et cadrage à mi-corps ; la consigne en pied échoue. |
| G353-v9-11 | duo / screen4x3 | 5.974 | À revoir | Deux adultes en pied, positions et tenues correctes ; rendu flou et décor intérieur ambigu face au château demandé. |

## Conservation

Rapport illustré Eidolon-comparatif-JuggernautX-G353.pdf, 14 pages, identité `libfile_fde3_f-95eaf39652ac8191af9fb8782fa636bb_d168d29c22b4819186c4d3b8d1b7451f`. Synthèse juggernaut-x-validation-g353.json, preuves evidence-g353/. PNG originaux sous /srv/eidolon/workspaces/media-20261112/juggernaut-x-g353/, poids v10 sous /srv/eidolon/data/media-models-20261113/juggernaut-x-g353/.

Avis GPT non aveugles sur aperçus réduits, à distinguer de l’avis de toytoy. Aucune validation anatomique professionnelle. Les résultats bruts gardent NOT_REVIEWED/PENDING_REVIEW ; la synthèse ajoute la revue ultérieure. Erreurs, configurations et sources conservées, aucun échec effacé.

[Auteur v10](https://huggingface.co/RunDiffusion/Juggernaut-X-v10/tree/35e4f3ccbe745c3e1221715d04a452aaa1ee5761) ; [témoin G333](CHECKPOINTS-G333.md) ; [file de candidats](CANDIDATE-QUEUE-G332.md).
