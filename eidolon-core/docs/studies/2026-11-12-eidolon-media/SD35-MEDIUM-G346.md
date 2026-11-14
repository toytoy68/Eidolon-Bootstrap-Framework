# SD3.5 Medium — G346, 14 novembre 2026

Eidolon Core Technologies (ECT). Powered by Stability AI.

## Résultat final

Douze images générées et examinées ; huit natives1024² : **1 proposée, 1 à revoir, 6 rejetées**. Les mains01/02 ont six doigts. Les katanas05/06 ont des structures incohérentes. Le duo07 masque les mains de la femme ;08 coupe les jambes. Tasse/bol03 proposé,04 à revoir pour l’anse. Contrôle512² proposé hors score ; répétition09 exactement identique à01 et rejetée ; écran16:9 rejeté,4:3 à revoir.

Médiane native **22,376442s**, plage22,307727–22,437422s. Encodage initial cinq textes42,891310s ; chargement du lot3,643807s. Chronomètre génération/décodage incluant vérifications numériques et sauvegarde du latent, hors chargement/encodage et sauvegarde PNG finale. Pas de latence « depuis clic » mesurée. KleinG340 corrigé reste5/8 à3,396s ; G344 reste6/8 à279,383s. Comparaison des recettes, pas supériorité générale. Aucun intérêt établi à remplacer Klein avec ce témoin ; aucune promotion.

## Protocole fixé avant observation

Grille identique G339–G345 : main, objets colorés, katana/fourreau, duo, deux seeds20261113/20261114, répétition, contrôle512², formats1024×576/768×576. Recette exemple Diffusers auteur :40étapes,CFG4,5, FlowMatchEuler shift3, négatif vide,256tokensT5. **Sans Skip Layer Guidance** ; la recommandation auteur SLG reste une variante à évaluer séparément. Aucun prompt ajouté après observation ni nouvelle seed sélectionnée.

Transformer FP16 sur GPU0 V10016, trois encodeurs CLIP-L/CLIP-G/T5-XXL CPU FP32, VAE GPU0 FP32 tuilé natif. SDPA EFFICIENT_ATTENTION pour le générateur, MATH pour le VAE. PyTorch2.6.0+cu124, Diffusers0.37.0, Transformers4.56.1, runtime G340 inchangé. Pas de quantification, pas de regroupement implicite des deux VRAM. Génération réseau sortant bloqué, verrou de campagne, UUID GPU imposé, limites72Go RAM/800%CPU/90minutes, garde65°C GPU et70°C HBM.

## Provenance et incidents conservés

Auteur `stabilityai/stable-diffusion-3.5-medium`, révision `b940f670f0eda2d07fbb75229e779da1ad11eb80`. Dépôt auteur soumis à accès accepté ; aucune inscription ni partage d’informations effectués. Poids téléchargés depuis la copie publique `adamo1139/stable-diffusion-3.5-medium-ungated`, révision `1cb9becf522803da9d25c2713d1a82b41bc6198d`. Les six SHA256 de poids sont identiques aux métadonnées auteur, fichiers téléchargés revérifiés. Configurations/tokenizers/licence comparés aux objets auteur ; aucun code du miroir exécuté. Licence Stability AI Community du5juillet2024 archivée ; cette étude n’affirme pas une absence de restrictions d’usage.

Trois incidents de préparation/exécution, tous avant la première génération :

1. Préparation initiale : SentencePiece est un fichier LFS ; le premier contrôleur comparait ses octets au blob du pointeur. Correction SHA256 LFS ; ancien script et journal conservés.
2. run01 : tokenizer rapide demande protobuf absent. Usage de T5Tokenizer standard conforme au tokenizer_class auteur, sans nouvelle installation. Cinq textes comparés au tokenizer.json natif : identités exactes des tokens (33,39,55,64 et1).
3. run02 : notre constructeur de pipeline omettait les quatre paramètres optionnels encoder/tokenizer2/3. Ajout explicite deNone ; ancien runner et journal conservés. Encodages finis conservés et réutilisés avec SHA.

run03 : contrôle512² terminé en5,228927s. run04 : onze images terminées, aucune exception de génération, latents/décodages finis à chaque étape. Répétition pixel-identique et PNG-identique. La validationFP16 porte sur cette recette ; aucun comparatifFP32 de qualité n’a été fait.

## Matériel et clôture

Maximum GPU46°C, HBM49°C, VRAM10 552Mio ; seconde V100 au repos, GTX1060 inchangée. Consigne300W, pic ponctuel315,12W, aucune mesure d’énergie revendiquée. Zéro erreur de télémétrie. Lot terminé à18h51 heure de Paris ; contrôle final : douze PNG intègres, aucun client GPU, runtime identique avant/après, cinq services actifs et VM Memory-engine en marche. Machine laissée allumée. Aucun entraînement, déploiement ou changement sur l’autre plateforme.

Préférence toytoy conservée : G344 pour les demandes détaillées malgré sa lenteur. Aucun avis utilisateur inventé sur G346.

## Revue image par image

| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |
| --- | --- | ---: | --- | --- |
| G346-00 | hand / smoke | 5.229 | Proposée | Cinq doigts séparés, paume et poignet visibles. Texture un peu lissée ; contrôle technique hors score natif. |
| G346-01 | hand / quality | 22.437 | Rejetée | Six doigts : un pouce à gauche, quatre doigts centraux et un appendice supplémentaire à droite. |
| G346-02 | hand / quality | 22.308 | Rejetée | Six doigts distincts : cinq doigts dressés au-dessus de la paume et un pouce à droite. |
| G346-03 | objects / quality | 22.319 | Proposée | Exactement une tasse rouge à gauche et un bol bleu à droite, complets, sur fond gris. Céramique et ombres crédibles. |
| G346-04 | objects / quality | 22.320 | À revoir | Couleurs et comptage respectés. Anse de la tasse aplatie et accolée au corps, sans ouverture convaincante. |
| G346-05 | katana / quality | 22.372 | Rejetée | Lame fortement recourbée, assemblage poignée/garde incohérent, extrémité inférieure coupée ; fourreau incompatible. |
| G346-06 | katana / quality | 22.381 | Rejetée | Arme désassemblée en plusieurs pièces et éléments supplémentaires ; aucun katana complet cohérent. |
| G346-07 | duo / quality | 22.400 | Rejetée | Deux adultes en pied et couleurs conformes, mais les mains de la femme sont masquées ; pieds et chaussures déformés. |
| G346-08 | duo / quality | 22.410 | Rejetée | Deux adultes et mains visibles, mais jambes et pieds coupés par le cadre. |
| G346-09 | hand / repeat | 22.415 | Rejetée | Répétition exacte de01, mêmes pixels et même PNG : six doigts, rejet confirmé. |
| G346-10 | duo / screen16x9 | 11.100 | Rejetée | Format16:9 : deux adultes en pied, mais mains de la femme cachées dans les manches. |
| G346-11 | duo / screen4x3 | 8.278 | À revoir | Format4:3 : deux adultes en pied, mains visibles. Proportions du samurai et détails des mains/orteils discutables. |

## Preuves et rapport

Rapport illustré `Eidolon-comparatif-SD35Medium-G346.pdf`,14pages, identité `libfile_fde3_f-fe3c98de2adc819194c0a08d8525965d_d168d29c22b4819186c4d3b8d1b7451f`,version0. Preuves dans `evidence-g346/` et `sd35-medium-validation-g346.json`. PNG/latents/caches conservés sous `/srv/eidolon/workspaces/media-20261112/sd35-medium-g346/`, runs01–04. Poids dans `/srv/eidolon/data/media-models-20261113/sd35-medium`.

[Modèle auteur](https://huggingface.co/stabilityai/stable-diffusion-3.5-medium/tree/b940f670f0eda2d07fbb75229e779da1ad11eb80) ; [copie publique vérifiée](https://huggingface.co/adamo1139/stable-diffusion-3.5-medium-ungated/tree/1cb9becf522803da9d25c2713d1a82b41bc6198d). Scripts préparation/recette/lancement/contrôle et tentatives antérieures conservés. Petite grille, revue subjective explicite ; proposée ne vaut pas approbation utilisateur. Large/Turbo et SLG restent non testés par ce lot.
