# Juggernaut XL Lightning — G354, 14 novembre 2026

Eidolon Core Technologies (ECT).

## Résultat

Lightning : 1/8 images proposées, contre 3/8 pour v9. Médiane 6.84 s contre 17,60 s pour v9 G353, soit un temps divisé par 2.57 dans ces recettes.

Constat visuel : Les textures restent séduisantes, mais Lightning dédouble une main et manque le comptage, les katanas et les deux duos natifs. Une seule main est proposée.

Comparaison : 12 nouvelles images Lightning ; les 12 images v9 proviennent du lot G353. Scènes, seeds et matériel identiques, mais sampler, étapes et guidage différents. Le gain porte sur la recette complète.

Matériel : une V100 ; maxima GPU/HBM 43/50 °C. Répétition pixel-identique. Temps incluant encodage texte, génération et décodage, hors chargement et sauvegarde.

Décision : Gain de vitesse confirmé, conformité insuffisante : ne pas remplacer v9 ni les références FLUX par cette recette. Avis GPT provisoires, aucune validation utilisateur attribuée.

## Méthode

Plan : douze images Lightning : contrôle 512², huit natives 1024², répétition, duo 1024 × 576 et 768 × 576. Seeds 20261113/20261114, prompts figés, négatif vide. Aucun refiner, LoRA, retouche ni tri des seeds.

Recette : DPM++ SDE Karras via DPMSolverSDEScheduler Diffusers ; 6 étapes nominales et 11 appels UNet mesurés, CFG 1,8. Bruit brownien réinitialisé avec la seed de chaque image. Les deux sorties répétées ont les mêmes pixels et le même SHA PNG.

Choix des réglages : le fichier porte 4Steps ; la carte auteur recommande 5–7 étapes et CFG 1,5–2,0. Ce lot teste 6/1,8, pas une campagne 4 étapes. Son exemple Python utilise un autre scheduler : la recette exacte employée ici est archivée.

Précision et runtime : UNet et encodeurs FP16 GPU0, VAE upcast FP32 et tuilage. PyTorch 2.6.0+cu124, Diffusers 0.32.2, Transformers 4.49.0 et torchsde déjà présents. Aucun paquet ni pilote modifié ; sources et configurations vérifiées avant/après.

Provenance : RunDiffusion/Juggernaut-XL-Lightning, révision 9c35e7ca, fichier 7,105 Go, SHA256 c8df560d…f4b425a5. Carte auteur, OpenRAIL-M et licences OpenRAIL++ SDXL/ByteDance archivées, restriction API payante conservée.

Observation numérique : avertissement torchsde sur une borne brownienne (écart d’arrondi environ 2,3 × 10^-7). Aucun avertissement masqué ; latents et décodage finis vérifiés. Aucun correctif numérique appliqué.

Isolation et mesure : GPU0 V100 à 300 W, garde GPU/HBM 65/70 °C ; réseau sortant interdit pendant la génération, verrou de campagne et limites de ressources. Durée encodage + débruitage + décodage + contrôles ; pics échantillonnés.

Limites : huit images natives, revue GPT non aveugle sur aperçus réduits. V9 G353 historique, recettes distinctes ; aucun classement universel ni effet causal des seuls poids. Machine laissée allumée, GPU libres et services actifs.

## Provenance exacte et choix de recette

Checkpoint RunDiffusion/Juggernaut-XL-Lightning, révision 9c35e7ca1112b7e567ae7b24400b83935909916d, fichier Juggernaut_RunDiffusionPhoto2_Lightning_4Steps.safetensors, 7 105 348 284 octets, SHA256 c8df560d2992ac04299412be6a36fa53a4e7a1b74f27b94867ad3f84f4b425a5. Métadonnées et blob Git de la carte vérifiés avant génération ; téléchargement de poids uniquement, aucune inférence externe. Aucune dépendance ajoutée.

L’auteur donne une plage 5–7 étapes, CFG 1,5–2,0 et DPM++ SDE ou SDE Karras. Son exemple Python emploie DPMSolverSinglestepScheduler sans forcer un algorithme SDE. Pour ce lot, choix explicite de DPMSolverSDEScheduler, Karras, epsilon, six étapes et CFG1,8. Onze évaluations UNet, donc aucun « six étapes = six évaluations » supposé. La graine du bruit brownien est explicitement fixée et le scheduler recréé pour chaque image, afin que la répétition soit indépendante du chemin de bruit précédent. Le fichier 4Steps n’est pas une preuve que cette campagne teste quatre étapes : cette variante de réglage reste à évaluer séparément.

UNet, deux encodeurs et VAE sont ceux du checkpoint complet. Runtime preference-lab identique à G353, SDPA MATH, quatre threads et fraction VRAM0,88, GPU0 identifié par UUID. VAE force_upcast, tuilage ; latents contrôlés à chaque callback, décodage contrôlé par hook. Le changement des paramètres et du sampler empêche d’attribuer une différence aux seuls poids. V9 est la référence historique G353 : ses résultats et revues sont repris, pas régénérés pour ce lot.

La licence déclarée OpenRAIL-M et la restriction de service API payant de RunDiffusion sont conservées, ainsi que les conditions des modèles de base SDXL et ByteDance Lightning OpenRAIL++-M. Usage d’évaluation locale privée. Aucun droit commercial universel déduit.

Unités isolées, verrou de campagne, pas de réseau sortant pendant l’inférence, aucune modification d’Eva, des VM ou des services. Mémoire72Go, CPU800%, durée maximale90min ; garde65°C GPU/70°C HBM. Ces plafonds sont distincts des mesures réellement observées.

## Mesures

| Recette | Images natives | Médiane (s) | Pic VRAM (Mio) | GPU/HBM max (°C) | Puissance pic (W) | Proposées / réserves / rejets |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| v9 G353 historique | 8 | 17.600301 | 12790 | 46/55 | 313.64 | 3/0/5 |
| lightning G354 | 8 | 6.842521 | 11624 | 43/50 | 316.29 | 1/0/7 |

12 nouvelles générations achevées, 11 appels UNet chacune, répétition exacte. 12 PNG vérifiés, sources/configs/runtime inchangés. GPU libres, cinq services actifs et Memory-engine en marche. Machine allumée. Les maxima thermiques ne classent pas l’efficacité énergétique ; conditions initiales et durée différentes.

## Revue Lightning

| ID | Scène | Temps (s) | Avis GPT | Motif |
| --- | --- | ---: | --- | --- |
| G354-00 | hand / smoke | 1.726 | Rejetée | Cinq doigts apparents, mais paume oblique et poignet arrivant du côté au lieu du bas demandé. |
| G354-01 | hand / quality | 7.114 | Rejetée | Deux mains au lieu d’une, avec doigts manquants ou fusionnés. |
| G354-02 | hand / quality | 6.842 | Proposée | Une main entière, cinq doigts distincts, paume et poignet conformes ; rendu de peau détaillé. |
| G354-03 | objects / quality | 6.843 | Rejetée | Quatre récipients au lieu de deux et supports ajoutés ; comptage non respecté. |
| G354-04 | objects / quality | 6.833 | Rejetée | Trois récipients, bol rouge et tasse bleue ; nombre, couleurs et positions non conformes. |
| G354-05 | katana / quality | 6.839 | Rejetée | Poignées et pièces superposées, lame/fourreau incohérents et poignée coupée au bord inférieur. |
| G354-06 | katana / quality | 6.841 | Rejetée | Deux sabres à poignées au lieu d’un katana et de son fourreau ; aucune paire conforme. |
| G354-07 | duo / quality | 6.843 | Rejetée | Femme à gauche, homme à droite vêtu de rouge ; positions et armure noire demandées non respectées. |
| G354-08 | duo / quality | 6.847 | Rejetée | Trois adultes au lieu de deux, avec un personnage supplémentaire à gauche. |
| G354-09 | hand / repeat | 6.848 | Rejetée | Répétition exacte de 01 : deux mains avec anatomie incorrecte. |
| G354-10 | duo / screen16x9 | 3.528 | Rejetée | Femme à gauche et samurai à droite, vus de dos ; positions inversées et mains masquées. |
| G354-11 | duo / screen4x3 | 2.397 | Rejetée | Personnage de gauche sans l’armure noire demandée ; arme déformée et rendu du visage peu défini. |

## Conservation

PDF illustré 14 pages, 12 images nouvelles face aux 12 références v9 G353 : `libfile_fde3_f-ff0b50ba73c48191b55a58e48e818fdf_d168d29c22b4819186c4d3b8d1b7451f`. PNG originaux : `/srv/eidolon/workspaces/media-20261112/juggernaut-lightning-g354/`. Poids : `/srv/eidolon/data/media-models-20261113/juggernaut-lightning-g354/`. Données : `juggernaut-lightning-validation-g354.json`. Preuves : `evidence-g354/`. Les données brutes restent NOT_REVIEWED ; seule la synthèse ajoute la revue ultérieure, non attribuée à toytoy. Aucun entraînement ni promotion automatique.

[Carte auteur figée](https://huggingface.co/RunDiffusion/Juggernaut-XL-Lightning/tree/9c35e7ca1112b7e567ae7b24400b83935909916d) ; [Référence v9 G353](JUGGERNAUT-X-G353.md).
