# Juggernaut XI Lightning — G356, 14 novembre 2026

Eidolon Core Technologies (ECT).

## Résultat

XI Lightning : 0/8 images proposées. XI standard : 2/8 et 1 réserve ; XL Lightning : 1/8. Médiane 6.84 s, contre 17,56 s pour XI standard.

Constat visuel : La lumière et les matériaux sont convaincants, mais les huit natives échouent : deux mains à quatre doigts, récipients surnuméraires, géométrie du sabre ou fourreau absent, tenue erronée et troisième personnage. Les contrôles 512 pixels et 4:3 sont proposés séparément ; ils ne modifient pas le score 0/8.

Comparaison : 12 nouvelles images XI Lightning. Références historiques XI standard G355 et XL Lightning G354 ; mêmes scènes, seeds et matériel. Les deux Lightning emploient la même recette 6/CFG 1,8 ; XI standard utilise 30/CFG5.

Matériel : une V100 ; maxima GPU/HBM 42/49 °C. Répétition pixel-identique. Temps encodage texte + génération + décodage, hors chargement et sauvegarde.

Décision : Ne pas retenir XI Lightning comme modèle principal avec cette recette. Sa vitesse est utile, mais la conformité est insuffisante sur cette petite grille ; le contrôle 4:3 mérite une confirmation sur plusieurs seeds avant tout usage régulier. Avis GPT provisoires, aucune validation utilisateur attribuée.

## Méthode

Plan : douze nouvelles images : contrôle 512², huit natives 1024², répétition, duo 1024×576 et 768×576. Seeds 20261113/20261114, prompts figés, négatif vide, aucun refiner, LoRA, retouche ou sélection de seeds.

Recette : DPMSolverSDEScheduler, DPM++ SDE Karras, 6 étapes nominales / 11 appels UNet mesurés, CFG 1,8. Scheduler recréé et graine brownienne fixée pour chaque image. Même recette que XL Lightning G354.

Précision : UNet et encodeurs FP16 GPU 0, VAE upcast FP32/tuilage. PyTorch 2.6.0+cu124, Diffusers 0.32.2 et Transformers 4.49.0 ; aucun paquet ni pilote modifié. Sources et configurations vérifiées avant/après.

Poids exacts : RunDiffusion/Juggernaut-XI-Lightning, révision dbb242e5 ; fichier Civitai-Version, SHA256 609fde64…15f37b1a, 7,105 Go, VAE stocké FP32. L’autre fichier du dépôt, VAE stocké FP16, n’est pas testé.

Licence : RunDiffusion / KandooAI, CC BY-NC-ND 4.0 et conditions auteur ; licences de base SDXL/ByteDance conservées. Évaluation locale privée non commerciale, aucune redistribution de poids. Accès public auteur, aucun formulaire transmis.

Compatibilité : buffer CLIP position_ids non entier ignoré par Transformers, qui reconstruit 0–76 ; comportement et source archivés. Avertissements torchsde de borne brownienne conservés ; valeurs finies contrôlées, aucun correctif numérique.

Isolation : GPU 0 seul, 300 W, garde GPU/HBM 65/70 °C, réseau sortant interdit pour l’inférence, verrou et limites de ressources. Temps incluant encodage et contrôles ; pics mémoire/puissance/température échantillonnés.

Limites : huit natives, revue GPT non aveugle sur aperçus réduits. XI standard et XL Lightning repris de G355/G354, pas régénérés. Recette distincte du standard ; aucune attribution du gain aux seuls poids. Machine allumée, GPU libres et services actifs.

## Variante exacte et provenance

RunDiffusion/Juggernaut-XI-Lightning, révision dbb242e5b54f33ce3bde22464f8813c1427bf1d4. Fichier Juggernaut-XI-byRunDiffusion-Lightning-Civitai-Version.safetensors, 7 105 348 616 octets, SHA256 609fde646e7fc60a259ad67351e02258ac7929a0a1f5040049dfec6a15f37b1a. Checkpoint complet, UNet/encodeurs FP16 et VAE stocké FP32. Métadonnées, taille et SHA vérifiés, carte auteur vérifiée par blob Git. Aucun poids redistribué dans le dépôt.

L’autre fichier auteur Juggernaut-XI-byRunDiffusion-Lightning.safetensors pèse 6 938 040 706 octets, SHA7782222e931a52aaded32647553ee4162c455046fa6a64ab6176cc1d2bae9da1. Inspection limitée à son en-tête public : VAE stocké FP16. Il n’a pas été téléchargé intégralement ni exécuté ; aucune équivalence numérique des deux fichiers n’est affirmée. La variante Civitai-Version choisie provient directement du dépôt officiel RunDiffusion.

Attribution : RunDiffusion / KandooAI, Juggernaut XI Lightning. CC BY-NC-ND4.0 et conditions auteur additionnelles, licences des bases SDXL et ByteDance Lightning archivées. Usage privé non commercial. Aucune création de compte, aucun formulaire, token ou renseignement personnel transmis ; métadonnées officielles gated=false et URL publique auteur. Aucune API de génération extérieure.

[Carte auteur figée](https://huggingface.co/RunDiffusion/Juggernaut-XI-Lightning/tree/dbb242e5b54f33ce3bde22464f8813c1427bf1d4) ; [licence](https://creativecommons.org/licenses/by-nc-nd/4.0/).

## Comparabilité et limites techniques

Même grille et seeds que G354/G355. Deux références historiques, non régénérées : XI standard G355 (DPM++2M Karras30/CFG5) et XL Lightning G354 (DPM++SDE Karras6/CFG1,8). XI Lightning G356 emploie cette dernière recette avec la même graine du bruit brownien ; onze évaluations UNet pour six étapes nominales. Ces références ne constituent pas un ordre de passage randomisé. Le rapport illustré juxtapose XI standard et XI Lightning ; le tableau inclut aussi XL Lightning.

Chaque checkpoint fournit tous ses poids de pipeline. VAE activé en tuiles et upcast FP32, encodeurs/UNet GPU0 FP16. SDPA MATH, quatre threads, fraction VRAM0,88 ; aucun remplacement de paquet ou pilote. Encodage, débruitage, contrôles et décodage inclus dans le temps ; chargement et sauvegarde PNG exclus. Valeurs latentes et décodage finis contrôlés, appels UNet comptés, répétition vérifiée par pixels et SHA PNG. Les avertissements restent dans les journaux ; inspection CPU dédiée des indices CLIP et des dtypes conservée. Le buffer CLIP position_ids est fractionnaire et ignoré par Transformers, dont le buffer non persistant est la séquence entière0–76 ; équivalence avec un autre lecteur de checkpoint non démontrée. Aucun patch des poids ou du scheduler.

Unités transitoires limitées à72Go/800%CPU/90min, GPU0 V100 précisément identifié,300W ; garde65°C GPU/70°C HBM, verrou de campagne, réseau sortant interdit pendant l’inférence. GPU1 et GTX1060 au repos. Aucun entraînement, intégration ou promotion, aucune modification des VM ou services.

## Mesures

| Recette | N natives | Médiane (s) | Pic VRAM (Mio) | GPU/HBM max (°C) | Pic puissance (W) | Proposées / réserves / rejets |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| v11 | 8 | 17.561640 | 11538 | 45/52 | 332.98 | 2/1/5 |
| xi_lightning | 8 | 6.839986 | 11566 | 42/49 | 324.42 | 0/0/8 |
| xl_lightning | 8 | 6.842521 | 11624 | 43/50 | 316.29 | 1/0/7 |

12 nouvelles générations achevées, 11 appels UNet chacune, répétition exacte. 12 PNG vérifiés, sources/configs/runtime inchangés. GPU libres, cinq services actifs et Memory-engine en marche. Machine allumée. Les maxima échantillonnés ne permettent pas de classer l’efficacité énergétique.

## Revue des nouvelles images

| Image | Condition | Temps (s) | Avis GPT | Motif |
| --- | --- | ---: | --- | --- |
| G356-00 | hand / smoke | 1.722 | Proposée | Une seule main, cinq doigts séparés, paume lisible et fond gris. Le poignet arrive par le bas droit : pose oblique, mais les doigts sont globalement dirigés vers le haut. Contrôle à 512 pixels, hors score principal. |
| G356-01 | hand / quality | 7.124 | Rejetée | Peau et éclairage crédibles, mais seulement quatre doigts : un pouce et trois doigts longs. Le cinquième manque malgré une paume bien orientée. |
| G356-02 | hand / quality | 6.843 | Rejetée | Même défaut décisif : quatre doigts visibles au lieu de cinq. Le bon rendu de peau ne compense pas l'erreur anatomique. |
| G356-03 | objects / quality | 6.836 | Rejetée | Trois récipients au lieu de deux : bol bleu à gauche, tasse rouge au centre et pichet bleu à droite. Socle et petit accessoire supplémentaires ; positions demandées non respectées. |
| G356-04 | objects / quality | 6.835 | Rejetée | Trois tasses ou récipients à anse, dont un grand gris. Le bol bleu séparé demandé à droite est absent ; nombre, formes et couleurs ne correspondent pas. |
| G356-05 | katana / quality | 6.838 | Rejetée | Assemblage incohérent : deux gardes et deux segments de poignée alignés, une lame détachée ou fusionnée avec les éléments noirs. Pas de couple katana et fourreau séparés crédible. |
| G356-06 | katana / quality | 6.836 | Rejetée | Un seul sabre entièrement visible, aux matériaux convaincants. Le fourreau noir séparé demandé est absent. |
| G356-07 | duo / quality | 6.846 | Rejetée | Deux adultes en pied et ordre gauche-droite correct, mais la femme porte une tenue noire avec ceinture rouge, pas un kimono rouge. Une de ses mains est aussi masquée par le samouraï. |
| G356-08 | duo / quality | 6.842 | Rejetée | Trois adultes au lieu des deux demandés. La femme en rouge et le samouraï sont présents, mais un personnage supplémentaire occupe la gauche. |
| G356-09 | hand / repeat | 6.847 | Rejetée | Répétition pixel-identique à 01, donc même main à quatre doigts. La reproductibilité technique est validée, pas l'anatomie. |
| G356-10 | duo / screen16x9 | 3.532 | Rejetée | Duo en pied, vêtements et mains visibles, mais positions inversées : femme à gauche et samouraï à droite. |
| G356-11 | duo / screen4x3 | 2.396 | Proposée | Deux adultes en pied, samouraï en armure noire à gauche et femme en tenue rouge à droite, mains visibles. Ensemble cohérent à cette échelle ; détails des doigts peu résolus. Contrôle 4:3 hors score principal. |

## Conservation

PDF illustré de14pages : `libfile_fde3_f-3b8a332ff3688191852dbe284492d550_d168d29c22b4819186c4d3b8d1b7451f`. PNG originaux `/srv/eidolon/workspaces/media-20261112/juggernaut-xi-lightning-g356/`, poids `/srv/eidolon/data/media-models-20261113/juggernaut-xi-lightning-g356/`. Synthèse `juggernaut-xi-lightning-validation-g356.json`, preuves `evidence-g356/`. Les données brutes restent NOT_REVIEWED, la revue ultérieure GPT figure dans la synthèse ; aucun avis utilisateur attribué. Aucune sélection automatique ni promotion.

[XI standard G355](JUGGERNAUT-XI-G355.md) ; [XL Lightning G354](JUGGERNAUT-LIGHTNING-G354.md).
