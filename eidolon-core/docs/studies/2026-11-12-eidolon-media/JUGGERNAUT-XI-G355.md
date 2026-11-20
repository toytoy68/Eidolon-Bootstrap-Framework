# Juggernaut XI v11 — G355, 14 novembre 2026

Eidolon Core Technologies (ECT).

## Résultat

XI v11 : 2/8 images proposées, contre 3/8 pour v9. Médiane 17.56 s contre 17,60 s pour v9 G353. Recette commune : 30 étapes, CFG5.

Constat visuel : XI réussit un duo que v9 manquait, mais perd une main correcte. Le second duo garde une réserve sur le sabre ajouté. Comptage des objets et katanas restent non conformes.

Comparaison : 12 nouvelles images v11 face aux 12 références v9 du lot G353. Scènes, seeds, DPM++2M Karras, 30 étapes, CFG5 et matériel identiques ; v9 non régénéré dans ce lot.

Matériel : une V100 ; maxima GPU/HBM 45/52 °C. Répétition pixel-identique. Temps incluant encodage texte, génération et décodage, hors chargement et sauvegarde.

Décision : Conserver XI comme option pour les portraits en duo ; pas de remplacement global du v9 ou des références FLUX sur cette grille. Avis GPT provisoires, aucune validation utilisateur attribuée.

## Méthode

Plan : douze images XI v11 : contrôle 512², huit natives 1024², répétition, duo 1024 × 576 et 768 × 576. Seeds 20261113/20261114, prompts figés et négatif vide. Aucun refiner, LoRA, retouche ni sélection des seeds.

Recette : DPMSolverMultistepScheduler, DPM++2M Karras, 30 étapes, CFG5 ; trente appels UNet mesurés. Dimensions originales/cibles égales à la sortie, crop0. Même recette que v9 G353, dont les résultats sont repris sans nouvelle exécution.

Précision : UNet et deux encodeurs FP16 GPU0, VAE upcast FP32 et tuilage. PyTorch2.6.0+cu124, Diffusers0.32.2, Transformers4.49.0 ; aucun paquet ni pilote modifié. Sources et configurations vérifiées avant/après.

Provenance : RunDiffusion/Juggernaut-XI-v11, révision f836518c, fichier 7,105 Go, SHA256 33e58e86…5b42719e. Checkpoint complet : UNet, encodeurs et VAE propres au modèle. Carte auteur et licences archivées.

Licence et attribution : modèle RunDiffusion / KandooAI, CC BY-NC-ND4.0, conditions auteur additionnelles et licence du SDXL de base. Essai privé non commercial, poids non redistribués. Attribution conservée sur les images du rapport.

Compatibilité : le buffer CLIP position_ids stocké en FP16 contient des valeurs non entières. Transformers l’ignore et recrée la séquence standard0–76. Aucun poids modifié ; équivalence avec d’autres interfaces non vérifiée.

Accès : carte mentionnant un accès soumis à acceptation, mais API officielle gated=false et URL auteur accessible publiquement sans authentification (HTTP200). Aucun formulaire, compte ou renseignement personnel transmis.

Isolation et mesure : une V100 à300W, garde GPU/HBM65/70°C ; inférence sans réseau sortant, verrou et limites de ressources. Latents et décodage finis contrôlés. Temps encodage + débruitage + décodage + contrôles ; pics échantillonnés.

Limites : huit natives, revue GPT non aveugle sur aperçus réduits. Carré1024² commun au comparatif ; formats auteur832×1216/1216×832 non testés. V9 historique, pas de classement universel. Machine allumée, GPU libres et services actifs.

## Provenance exacte

RunDiffusion/Juggernaut-XI-v11, révision f836518c7a75f47a9e26bc661ff9509ef2ceb7c0. Juggernaut-XI-byRunDiffusion.safetensors : 7 105 350 536 octets, SHA256 33e58e86686f6b386c526682b5da9228ead4f91d994abd4b053442dc5b42719e. Métadonnées, taille et SHA vérifiés avant exécution ; carte auteur vérifiée par blob Git. API publique gated=false et téléchargement direct auteur sans authentification malgré la mention gated de la carte. Aucun token ou formulaire utilisé.

Attribution : RunDiffusion / KandooAI, modèle Juggernaut XI v11. Licence CC BY-NC-ND4.0, texte complet archivé depuis Creative Commons, plus conditions auteur et licence de base SDXL. Générations d’évaluation privée non commerciale ; aucune redistribution ni modification des poids sauvegardés. Aucun hébergement comme service. L’auteur demande aussi une attribution pour les sorties, conservée dans le rapport. Aucun consentement marketing ou renseignement personnel soumis.

[Carte auteur figée](https://huggingface.co/RunDiffusion/Juggernaut-XI-v11/tree/f836518c7a75f47a9e26bc661ff9509ef2ceb7c0) ; [CC BY-NC-ND4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/).

## Comparabilité

Même grille que v9 G353 : prompts exacts, seeds20261113/20261114, DPM++2M Karras30/CFG5, négatif vide, FP16 GPU0 avec encodeurs sur GPU, VAE upcast/tuilé et tailles/crops explicites. Carré1024² commun à la campagne ; les formats auteur832×1216/1216×832 restent non testés. Les temps incluent l’encodage texte, les contrôles de valeurs finies, le débruitage et le décodage, pas le chargement ni la sauvegarde PNG. V9 n’a pas été relancé ici : reprise de sa synthèse G353 au commit e72dd12369cbd2e0d2ee4e5d8c9420b0f75c705b, SHA du fichier contrôlé.

Chaque checkpoint fournit son UNet, ses deux encodeurs et son VAE. Aucun composant de poids silencieusement emprunté à v9. Avertissement examiné : le checkpoint stocke position_ids en FP16 avec des valeurs fractionnaires. Transformers4.49.0 ignore ce buffer non persistant et reconstruit arange(77), comme le montre le code chargé. Le premier contrôle supposant un buffer standard a échoué ; les valeurs réelles et cet échec sont conservés dans clip-position-ids-check.json. Aucun correctif du checkpoint appliqué. Ce lot qualifie cette chaîne Diffusers/Transformers ; équivalence avec ComfyUI ou un autre lecteur non démontrée. Trente appels UNet observés, latents finis à chaque étape et décodage fini. SDPA MATH, quatre threads, fraction VRAM0,88. PyTorch2.6.0+cu124 / Diffusers0.32.2 / Transformers4.49.0 inchangés. Export JSON des valeurs de configuration non finies hérité de G353 ; ce mécanisme ne change pas le calcul.

GPU0 seul, identifié par UUID ; GPU1 et GTX1060 au repos. Unités bornées à72Go/800%CPU/90min, verrou de campagne et réseau sortant interdit pour l’inférence ; garde GPU65°C et HBM70°C. Aucun entraînement, intégration, promotion ni arrêt d’Eva. Pas de modification des VM ou services.

## Mesures

| Recette | Images natives | Médiane (s) | Pic VRAM (Mio) | GPU/HBM max (°C) | Puissance pic (W) | Proposées / réserves / rejets |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| v9 G353 historique | 8 | 17.600301 | 12790 | 46/55 | 313.64 | 3/0/5 |
| v11 G355 | 8 | 17.561640 | 11538 | 45/52 | 332.98 | 2/1/5 |

12 nouvelles générations achevées, 30 appels UNet chacune, répétition exacte. 12 PNG vérifiés, sources/configs/runtime inchangés. GPU libres, cinq services actifs et Memory-engine en marche. Machine allumée. Les maxima thermiques ne classent pas l’efficacité énergétique ; conditions initiales et durée différentes.

## Revue XI v11

| ID | Scène | Temps (s) | Avis GPT | Motif |
| --- | --- | ---: | --- | --- |
| G355-00 | hand / smoke | 3.768 | Rejetée | Cinq doigts apparents, mais plusieurs doigts repliés et poignet latéral : pose demandée non respectée. |
| G355-01 | hand / quality | 17.816 | Proposée | Une main entière, cinq doigts distincts et poignet en bas ; anatomie visuellement plausible. |
| G355-02 | hand / quality | 17.557 | Rejetée | Quatre doigts seulement, pouce compris ; un doigt manque. |
| G355-03 | objects / quality | 17.542 | Rejetée | Trois récipients au lieu de deux ; bol à gauche et tasse bleue supplémentaire à droite. |
| G355-04 | objects / quality | 17.551 | Rejetée | Trois récipients, bol bicolore au centre et tasse rouge à droite ; nombre et positions incorrects. |
| G355-05 | katana / quality | 17.563 | Rejetée | Deux lames avec poignées et gardes ; le fourreau séparé demandé n’est pas représenté correctement. |
| G355-06 | katana / quality | 17.561 | Rejetée | Un seul sabre ; aucun fourreau séparé. |
| G355-07 | duo / quality | 17.586 | Proposée | Deux adultes en pied, armure noire à gauche et kimono rouge à droite ; visages et pose cohérents. |
| G355-08 | duo / quality | 17.579 | À revoir | Duo, tenues et positions corrects ; le sabre ajouté présente une lame terminée à plat, peu crédible. |
| G355-09 | hand / repeat | 17.591 | Proposée | Répétition exacte de 01 : une main entière avec cinq doigts distincts. |
| G355-10 | duo / screen16x9 | 8.950 | Rejetée | Deux adultes en pied, mais femme à gauche et samurai à droite : positions inversées. |
| G355-11 | duo / screen4x3 | 5.981 | À revoir | Deux adultes en pied, positions et tenues correctes ; mains peu détaillées et élément de sabre/fourreau ambigu entre les jambes. |

## Conservation

PDF illustré 14 pages, 12 images nouvelles face aux 12 références v9 G353 : `libfile_fde3_f-8431962ca3fc819190a05aa9ede44d70_d168d29c22b4819186c4d3b8d1b7451f`. PNG originaux : `/srv/eidolon/workspaces/media-20261112/juggernaut-xi-g355/`. Poids : `/srv/eidolon/data/media-models-20261113/juggernaut-xi-g355/`. Données : `juggernaut-xi-validation-g355.json`. Preuves : `evidence-g355/`. Les données brutes restent NOT_REVIEWED ; seule la synthèse ajoute la revue ultérieure, non attribuée à toytoy. Aucun entraînement ni promotion automatique.

[Référence v9 G353](JUGGERNAUT-X-G353.md).
