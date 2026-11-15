# SD3.5 Large - G349, 14 novembre 2026

Eidolon Core Technologies (ECT). Powered by Stability AI.

## Résultat et décision

SD3.5 Large : 2/8 images proposées, à 36.02 s médianes. La peau et les matières gagnent en détail, mais les deux mains ont six doigts et les katanas restent incohérents. Aucun avantage global établi face à Turbo.

Conformité : 2 proposées, 0 à revoir, 6 rejetées sur huit natives. Objets 03/04 conformes ; mains 01/02 et katanas 05/06 rejetés. Duo 07 : rejetée ; duo 08 : rejetée.

Coût : environ 11.5 fois le temps de Turbo (3.13 s), avec les mêmes deux V100. Poids et recette diffèrent : ce n’est pas un test du seul nombre d’étapes. Encodages identiques réutilisés.

Matériel : pics VRAM GPU0/GPU1 : 14 078 / 8 926 Mio. Maxima GPU 46/42 °C, HBM 47/43 °C. Répartition réelle des blocs, aucune erreur de génération et runtime inchangé.

Décision : ne pas remplacer les candidats rapides. Un rendu plus détaillé ne suffit pas à compenser les défauts et le délai sur cette grille. Z-Image G344 conserve son rôle détaillé à la demande selon ta préférence ; aucune promotion.

Douze images examinées. Natives1024² : **2 proposées, 0 à revoir, 6 rejetées**. Médiane36.020450577s, plage35.880614093-36.076484529s. Chargement9.053043013s. Avis GPT provisoires ; aucune validation utilisateur attribuée, aucune promotion.

## Recette, provenance et adaptation

Recette de la fiche auteur : **28 étapes, guidance3,5, sans SLG**, FlowMatchEuler shift3. Même grille, prompts et seeds20261113/20261114 que G348 : huit natives1024², contrôle512², répétition,1024x576 et768x576. Aucun prompt retouché ni seed sélectionnée après observation. Les poids et la recette diffèrent de Turbo : ce lot n’isole pas le seul effet du nombre d’étapes.

Générateur FP16 réparti : blocs0-18 GPU0,19-37 GPU1, entrées et sortie GPU0. Placement réel8 173 096 064 /7 940 158 976octets de paramètres. Compteurs532appels de blocs par GPU et par image (19x28), contrôlés sans modifier les tenseurs. CFG groupé natif de Diffusers. VAE GPU0 FP32 tuilé. La fiche auteur utilise BF16 ; ce lot ne démontre pas une équivalence de qualité FP16/BF16. Pas de mémoire déclarée unifiée ni mesure de débit NVLink revendiquée.

CLIP-L,CLIP-G,T5-XXL CPU FP32,256tokensT5 ; cache G346 réutilisé après vérification SHA des poids, configurations, tokenizers et embeddings. Les42,891310s indiquent le coût historique des cinq textes, sans nouvel encodage G349. PyTorch2.6.0+cu124, Diffusers0.37.0, Transformers4.56.1 inchangés. SDPA EFFICIENT_ATTENTION transformer, MATH VAE. Chronomètre génération/décodage incluant contrôles numériques et sauvegarde du latent, excluant chargement, encodage et sauvegarde PNG finale. Aucune latence depuis clic ni énergie totale.

Auteur `stabilityai/stable-diffusion-3.5-large`, révision `ceddf0a7fdf2064ea28e2213e3b84e4afa170a0f`. Copie publique `adamo1139/stable-diffusion-3.5-large-ungated`, révision `5d868ffde1c2396697cc1ab7555dc5f64e056a63`. Sept fichiers de poids SHA identiques aux métadonnées auteur. Deux nouveaux shards de générateur totalisant16 292 705 296octets téléchargés ; encodeurs et VAE réutilisés par liens physiques après vérification. Configurations/tokenizers/index/licence vérifiés aux blobs/SHA auteur.

Licence Stability AI Community5juillet2024 identique à celle lue pour G348, conservée. Fiche auteur publique consultée sur le Web ; fiche du miroir conservée sous son propre nom, identité de blob consignée. Dépôt auteur gated auto, aucune inscription ou transmission au formulaire. Aucun code du miroir exécuté.

## Exécution et clôture

Préparation puis contrôle512² avant grille native. Génération locale sans réseau sortant, UUID exacts des deux V100, verrou de campagne, limites72GoRAM/800%CPU/90minutes et garde65°C GPU/70°C HBM. Aucun entraînement, déploiement ou changement sur l’autre plateforme.

Pics VRAM GPU0/GPU1 : 14078/8926Mio. Maxima GPU : 46/42°C ; HBM : 47/43°C. Consignes300W par V100, pics ponctuels321.79/315.96W. CPU Tdie38.500°C. Erreurs télémétrie :0.

Douze images terminées, latents/pixels finis, répétition pixel et PNG identiques. Aucun incident de génération ni erreur télémétrie. Contrôle final horodaté 2026-11-14T20:00:09.939923+01:00 (Europe/Paris) : runtime inchangé, douze SHA PNG vérifiés, aucun client GPU, cinq services actifs et Memory-engine en marche. Machine laissée allumée.

## Images

| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |
| --- | --- | ---: | --- | --- |
| G349-00 | hand / smoke | 8.834 | Rejetée | Cinq doigts identifiables, mais trois extrémités coupées par le haut du cadre. Contrôle 512² hors score. |
| G349-01 | hand / quality | 36.076 | Rejetée | Six doigts : cinq dressés au-dessus de la paume et un pouce à droite. Texture de peau détaillée, anatomie non conforme. |
| G349-02 | hand / quality | 35.881 | Rejetée | Six doigts distincts, malgré une paume et une texture plausibles. Comptage non conforme. |
| G349-03 | objects / quality | 35.945 | Proposée | Une tasse rouge à gauche, un bol bleu à droite, complets sur fond gris. Céramique détaillée et anse ouverte. |
| G349-04 | objects / quality | 35.945 | Proposée | Deux objets complets, couleurs et positions conformes. Anse de la tasse ouverte et lisible. |
| G349-05 | katana / quality | 36.014 | Rejetée | Poignées supplémentaires, éléments croisés et lame fusionnée avec une longue pièce noire. Assemblage katana/fourreau incohérent. |
| G349-06 | katana / quality | 36.027 | Rejetée | Une lame plausible, mais plusieurs poignées dont une isolée et un fourreau ressemblant à une seconde arme. Éléments supplémentaires. |
| G349-07 | duo / quality | 36.057 | Rejetée | Deux personnages en pied vus de dos dans une composition soignée, mais les mains féminines sont cachées. |
| G349-08 | duo / quality | 36.035 | Rejetée | Duo en pied vu de dos, accompagné d’une foule de visiteurs au fond. Le nombre exact de deux personnes n’est pas respecté. |
| G349-09 | hand / repeat | 36.066 | Rejetée | Répétition exacte de 01 : mêmes pixels, même PNG et six doigts. |
| G349-10 | duo / screen16x9 | 19.096 | Rejetée | Format 16:9 : jambes et pieds coupés par le cadre, mains féminines cachées. |
| G349-11 | duo / screen4x3 | 14.194 | Rejetée | Format 4:3 : jambes et pieds coupés. La femme est de face, mais une main reste cachée dans la manche. |

## Livrable, preuves et limites

Rapport illustré `Eidolon-comparatif-SD35Large-G349.pdf`,14pages, identité `libfile_fde3_f-5e0ae25e7e7c8191b343047dbf5e553c_d168d29c22b4819186c4d3b8d1b7451f`,version0. Preuves `evidence-g349/`, synthèse `sd35-large-validation-g349.json`, sources de préparation/génération/rapport conservées.

PNG/latents/caches sous `/srv/eidolon/workspaces/media-20261112/sd35-large-g349/`,run01(smoke),run02(qualité). Poids sous `/srv/eidolon/data/media-models-20261113/sd35-large`. Preuves brutes conservées en PENDING_REVIEW/NOT_REVIEWED ; revue postérieure dans la synthèse et `visual-reviews.json`.

Quatre scènes, deux seeds et revue subjective ; proposée ne vaut pas approuvée par toytoy. Comparaison de recettes différentes et non étude statistique robuste. [Turbo G348](SD35-LARGE-TURBO-G348.md), [Klein G340](KLEIN-G340.md). Aucune validation générale de toutes les tâches SD3.5 ni intégration en production.

[Fiche auteur](https://huggingface.co/stabilityai/stable-diffusion-3.5-large/blob/ceddf0a7fdf2064ea28e2213e3b84e4afa170a0f/README.md) ; [copie publique vérifiée](https://huggingface.co/adamo1139/stable-diffusion-3.5-large-ungated/tree/5d868ffde1c2396697cc1ab7555dc5f64e056a63).
