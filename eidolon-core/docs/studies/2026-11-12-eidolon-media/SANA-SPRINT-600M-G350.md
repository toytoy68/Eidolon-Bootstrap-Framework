# Sana Sprint 0,6B — G350, 14 novembre 2026

Eidolon Core Technologies (ECT).

## Résultat et décision

Sana Sprint 0,6B : 2/8 images proposées, à 1.28 s médianes. Rapide et peu gourmand en VRAM, mais aucune amélioration de conformité face à la 1,6B. Les objets réussissent ; mains, katanas et duos échouent.

Conformité : 2 proposées, aucune réserve et 6 rejets sur huit natives. La main 02 a six doigts ; la 01 conserve cinq doigts avec une anatomie incohérente. Duos trop serrés, katanas mal assemblés.

Coût : temps réduit de 30.2 % face à la 1,6B (1.83 s). Même recette, mêmes encodages réutilisés et une seule V100. L’exemple auteur à deux étapes n’est pas testé ici.

Matériel : pic 5336 Mio (5.21 Gio), contre 9184 Mio pour la 1,6B. Maxima GPU 42 °C et HBM 43 °C. Aucun incident de génération.

Décision : candidat aux aperçus simples sous contrainte mémoire ; aucun remplacement de Klein ou des favoris qualitatifs. Z-Image G344 reste réservé au détail à la demande selon ta préférence. Aucune promotion.

Douze images examinées. Sur les huit natives 1024² : **2 proposées, 0 à revoir et 6 rejetées**. Médiane **1.278650064 s**, plage 1.273795048–1.461887833 s. Chargement : 1.924778253 s. Avis GPT provisoires ; aucune validation utilisateur attribuée, aucune promotion.

## Recette et méthode

Recette : Sana Sprint 0,6B, quatre étapes SCM, guidage intégré 4,5, max_timesteps 1,57080, intermediate_timesteps=None. Même grille et réglages que Sprint 1,6B G345. Exemple auteur à deux étapes ; ce lot teste quatre étapes, pas la vitesse minimale.

Calcul : générateur et DC-AE FP32 sur GPU0, décodage tuilé 512. Quatre appels du générateur comptés par image, sans modifier les tenseurs. FP32 conserve la plage numérique nécessaire sur V100 ; aucune équivalence visuelle BF16 revendiquée.

Textes : quatre encodages Gemma2 CPU FP32 réutilisés depuis G345 après contrôle SHA des poids, configurations, tokenizers et cache. 26,76 s est leur coût historique ; aucun nouvel encodage dans ce lot.

Temps : génération, décodage, contrôles et sauvegarde du latent inclus ; chargement (1.92 s), encodage et écriture PNG finale exclus. Médiane de huit natives 1024². Aucune mesure depuis clic ni énergie totale.

Intégrité : 12 PNG vérifiés, répétition pixel et PNG identiques. Consigne 300 W ; pic ponctuel observé 333.46 W. GPU libres, cinq services actifs, VM Memory-engine en marche. Runtime inchangé.

Provenance : dépôt auteur Efficient-Large-Model, révision aa76e7f. Poids et fichiers identifiés par SHA ; licence Apache 2.0 archivée, conditions Gemma et DC-AE conservées séparément. Génération locale sans réseau sortant.

Limites : quatre scènes, deux seeds et revue subjective. PyTorch 2.6.0+cu124, Diffusers 0.37.0, Transformers 4.56.1. Aperçus réduits pour la revue, PNG natifs conservés. Proposée ne vaut pas approbation de toytoy ; machine laissée allumée.

Même grille que G345 et G340 : main ouverte, tasse/bol, katana/fourreau, duo en pied ; seeds 20261113 et 20261114. Huit natives 1024², contrôle 512², répétition, 1024×576 et 768×576. Aucun prompt ajusté ni seed sélectionnée après observation. Identité des prompts, seeds, dimensions et réglages vérifiée avec G345.

Générateur FP32 : 2 374 004 864 octets de paramètres sur GPU0. Attention linéaire Sana native, backend PyTorch MATH pour les autres attentions. Guidage intégré au générateur, pas de CFG doublant le batch. Résolution exacte, sans resolution binning. L’exemple auteur utilise deux étapes ; quatre étapes sont conservées pour comparer directement les deux variantes Sprint. Les poids diffèrent, ce n’est pas un test du seul effet du nombre de paramètres. Le format écran 4:3 dégrade particulièrement les proportions et les visages.

## Provenance et droits

Dépôt auteur `Efficient-Large-Model/Sana_Sprint_0.6B_1024px_diffusers`, révision `aa76e7f4f4928f378716b6716a2130fba3caf5b1`. Générateur téléchargé : 1 187 078 584 octets, SHA256 `9069dd697395b96a59d1f74837461f7aeb3d95e55b67fa85c9f31c9106b65e87`.

Deux shards Gemma2 et DC-AE réutilisés depuis G345 après vérification des empreintes avec les métadonnées auteur. Configurations, tokenizers et cache des embeddings identiques : `encoder-reuse-proof.json`. Les 26,757161908 s sont le coût historique des quatre encodages CPU G345 ; aucune nouvelle dépense d’encodage mesurée ici. Les instructions textuelles standard de Sana sont consignées dans le manifeste, sans réécriture externe des prompts.

Licence du dépôt Apache 2.0 archivée et identique à G345. Les conditions Gemma et sa politique d’usage restent applicables ; leur présence empêche de qualifier l’ensemble de libre de toute restriction. Licence DC-AE conservée séparément. Aucun code distant exécuté. Fiche auteur et configurations archivées, poids identifiés par SHA.

## Exécution et clôture

Préparation, contrôle 512² puis lot qualité. Génération locale sans réseau sortant, UUID exact de la première V100, verrou de campagne ; limites 72 Go RAM, 800 % CPU, 90 minutes et garde 65 °C GPU / 70 °C HBM. Seule GPU0 calcule ; GPU1 et GTX 1060 restent disponibles. Aucun entraînement, déploiement ou modification sur l’autre plateforme.

Pic VRAM GPU0 : 5336 Mio. Maxima GPU 42 °C, HBM 43 °C. Consigne 300 W, pic ponctuel mesuré 333.46 W ; ce n’est pas une puissance moyenne ni une énergie. CPU Tdie 35.625 °C. Erreurs de télémétrie : 0.

Douze images terminées, latents/pixels finis, répétition pixel et PNG identiques. Aucun incident de génération ni erreur télémétrie. Contrôle final 2026-11-14T20:11:25.661082+01:00 : runtime inchangé, douze SHA PNG vérifiés, aucun client GPU, cinq services actifs et Memory-engine en marche. Machine laissée allumée.

Un premier appel de lancement a visé par erreur un chemin tools absent ; il a échoué avant toute exécution. Le chemin du lanceur a été corrigé, sans changer la recette ni relancer une génération existante. Aucun incident dans les deux lots exécutés.

## Images

| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |
| --- | --- | ---: | --- | --- |
| G350-00 | hand / smoke | 0.492 | À revoir | Cinq doigts visibles, mais paume très segmentée, articulations artificielles et reflets verdâtres. Contrôle 512² hors score. |
| G350-01 | hand / quality | 1.462 | Rejetée | Cinq doigts, mais extrémités et pouce déformés ; des ongles apparaissent côté paume. Anatomie incohérente malgré la texture. |
| G350-02 | hand / quality | 1.279 | Rejetée | Six doigts : quatre doigts centraux et deux appendices latéraux. Défaut anatomique éliminatoire. |
| G350-03 | objects / quality | 1.285 | Proposée | Exactement deux objets entiers : tasse rouge à gauche et bol bleu à droite. Ombres et reflets plausibles. |
| G350-04 | objects / quality | 1.277 | Proposée | Tasse rouge et bol bleu séparés, complets et correctement placés. Céramique et lumière cohérentes. |
| G350-05 | katana / quality | 1.279 | Rejetée | Lame claire détachée de la poignée ; pièce noire à droite avec poignée et garde. Aucun katana complet et fourreau distinct cohérents. |
| G350-06 | katana / quality | 1.277 | Rejetée | Trois éléments au lieu du couple demandé : fragment de lame séparé, pièce centrale hybride et fourreau à poignée. |
| G350-07 | duo / quality | 1.274 | Rejetée | Deux adultes et bonnes couleurs, mais cadrage coupé aux cuisses : jambes et pieds absents. Mains également peu lisibles. |
| G350-08 | duo / quality | 1.279 | Rejetée | Deux adultes correctement placés devant le château ; jambes et pieds coupés par le bord inférieur. |
| G350-09 | hand / repeat | 1.275 | Rejetée | Répétition exacte de G350-01 : mêmes pixels et PNG, donc mêmes défauts anatomiques. Hors score natif. |
| G350-10 | duo / screen16x9 | 0.757 | Rejetée | Format 16:9 : corps coupés vers la taille, mains et pieds hors cadre ; haut de la coiffure rogné. |
| G350-11 | duo / screen4x3 | 0.570 | Rejetée | Format 4:3 : pieds de la femme masqués, proportions tassées, visages et mains déformés. |

## Livrable, preuves et limites

Rapport illustré `Eidolon-comparatif-SanaSprint600M-G350.pdf`, 14 pages, identité `libfile_fde3_f-92c53a5673fc819190dfd80bc6983c8f_d168d29c22b4819186c4d3b8d1b7451f`. Preuves `evidence-g350/`, synthèse `sana-sprint-600m-validation-g350.json`, sources de préparation, génération et rapport conservées.

PNG, latents et cache sous `/srv/eidolon/workspaces/media-20261112/sana-sprint-600m-g350/`, run01 (contrôle) et run02 (qualité). Poids sous `/srv/eidolon/data/media-models-20261113/sana-sprint-600m`. Les preuves brutes gardent PENDING_REVIEW/NOT_REVIEWED ; la revue postérieure est portée par la synthèse et `visual-reviews.json`.

Quatre scènes, deux seeds et avis subjectifs sur aperçus réduits : ce résultat ne valide ni toutes les tâches Sana ni une intégration en production. Le score compte le respect de la consigne, pas seulement la beauté du rendu. Une proposition n’est pas une approbation de toytoy. La comparaison avec Klein concerne des recettes différentes ; la comparaison Sprint garde les mêmes réglages et composants texte/décodage.

[Fiche auteur](https://huggingface.co/Efficient-Large-Model/Sana_Sprint_0.6B_1024px_diffusers/blob/aa76e7f4f4928f378716b6716a2130fba3caf5b1/README.md) ; [Sana Sprint dans Diffusers](https://huggingface.co/docs/diffusers/api/pipelines/sana_sprint).
