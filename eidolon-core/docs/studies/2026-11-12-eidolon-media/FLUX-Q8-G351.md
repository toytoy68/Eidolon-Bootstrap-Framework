# FLUX.1 Schnell GGUF Q8 — G351, 14 novembre 2026

Eidolon Core Technologies (ECT).

## Résultat et décision

FLUX Schnell Q8 : une V100 suffit, mais le calcul prend 2.42 fois plus de temps. 4/8 images proposées à 15.61 s médianes. Le gain est matériel ; les défauts de conformité restent à examiner scène par scène.

Conformité : 4 proposées, 2 à revoir, 2 rejetées sur huit natives. Le détail des mains, des katanas et du cadrage figure dans les pages suivantes. Score du complet G339 : 4/8 ; Klein : 5/8.

Temps : 15.61 s contre 6.45 s pour le complet réparti sur deux V100. Même recette Schnell ; quantification et nombre de cartes changent ensemble. Le Q8 n’apporte pas de gain de vitesse dans cette configuration.

Mémoire : pic 15158 Mio (14.80 Gio) sur GPU0 ; GPU1 au repos. Le complet utilisait 13 346 / 13 082 Mio sur deux cartes. Maxima GPU 43 °C et HBM 50 °C.

Décision : conserver comme option Schnell sur une carte, quand libérer la seconde est prioritaire. Aucun remplacement automatique des favoris ; Klein reste plus rapide avec une seule carte dans notre recette. Aucune promotion.

Douze images examinées. Huit natives 1024² : **4 proposées, 2 à revoir et 2 rejetées**. Médiane **15.613132624 s**, plage 15.599104248–15.755211225 s. Chargement : 9.892053374 s. Avis GPT provisoires ; aucune validation utilisateur attribuée et aucune promotion.

## Recette et méthode

Recette : même grille, prompts, seeds et moteur que Schnell G339. Quatre étapes, guidage 0, scheduler FlowMatchEuler shift 1 sans décalage dynamique. Attention découpée en 256 requêtes, VAE FP32 tuilé à 512 pixels.

Q8 sur GPU0 : poids Q8_0 et F16, déquantification dynamique et calcul FP16. 494 modules quantifiés, tous les paramètres sur GPU0 ; aucun offload CPU du générateur. Quatre appels du modèle et 228 appels de blocs contrôlés par image.

Textes et temps : CLIP-L/T5 CPU FP32, 256 tokens. Quatre nouveaux encodages : 39.78 s, puis cache réutilisé. Temps affichés hors chargement (9.89 s), encodage et écriture PNG ; contrôles et sauvegarde du latent inclus.

Incident corrigé : premier chargement resté sur CPU, détecté avant génération. Transfert GPU explicite ajouté au runner ; essai échoué conservé. Les douze images suivantes sont terminées, répétition pixel et PNG identiques.

Environnement : PyTorch 2.6.0+cu124 / Diffusers 0.32.2 / Transformers 4.49.0 inchangés. gguf 0.17.1 ajouté dans un dossier isolé. Aucun kernel distant. Conversion city96 f495746, empreinte du fichier vérifiée ; Apache 2.0 et licence gguf MIT archivées.

Matériel : consigne 300 W ; pic ponctuel 315.28 W, sans mesure d’énergie totale. Garde 65 °C GPU / 70 °C HBM. Après le lot : GPU libres, cinq services actifs et Memory-engine en marche, machine allumée.

Limites : huit natives, revue subjective sur aperçus réduits. Les PNG natifs sont conservés. Quantification et répartition matérielle varient ensemble ; ce comparatif n’isole pas leur coût respectif. Proposée ne signifie pas approuvée par toytoy.

Même grille et mêmes prompts que G339 : main ouverte, tasse/bol, katana/fourreau, duo en pied ; seeds 20261113 et 20261114. Huit natives 1024², contrôle 512², répétition, 1024×576 et 768×576. Aucun prompt retouché ni sélection de seed après observation.

Poids du générateur stockés en Q8_0 pour les grandes matrices et F16 pour les autres tenseurs ; déquantification dynamique, calcul FP16. Les 776 tenseurs du fichier comprennent 304 Q8_0 et 472 F16. Après conversion de noms et séparation des projections, 494 modules GGUFLinear et 1 156 paramètres sont placés sur GPU0. Stockage de paramètres : 12 687 767 680 octets, dont 12 573 868 032 quantifiés. Tous les paramètres sont effectivement résidents sur GPU0 ; aucun offload du générateur vers CPU. Quatre appels du générateur et 228 appels de blocs par image, contrôlés sans modifier les tenseurs.

Attention par morceaux de 256 requêtes identique à G339, backend MATH. VAE Flux FP32 GPU0 tuilé à 512 pixels, recouvrement standard. Scheduler FlowMatchEuler : shift 1, décalage dynamique désactivé. Quatre étapes, guidage 0, texte T5 de 256 tokens. Encodeurs CLIP-L et T5-XXL via le même moteur Comfy en CPU FP32, embeddings stockés FP16. Nouvel encodage des quatre prompts lors du premier essai G351, puis cache SHA vérifié pour les essais suivants. L’avertissement CLIP `text_projection.weight` absent était déjà présent dans le témoin G339 ; pas de modification des encodeurs.

## Provenance et environnement

Conversion publique `city96/FLUX.1-schnell-gguf`, révision `f495746ed9c5efcf4661f53ef05401dceadc17d2`. Fichier `flux1-schnell-Q8_0.gguf`, 12 687 821 728 octets, SHA256 `f6694941193b10148dbf1f0f498d4ccd3e9875c127fc53946213b68580c66f10`. Conversion directe de BFL Schnell déclarée par city96 ; cela ne signifie pas identité des poids avec le checkpoint FP16. Carte de conversion et licence Apache 2.0 du Schnell d’origine archivées. Encodeurs et VAE G339 réutilisés après vérification SHA.

Même environnement `preference-lab` que G339 : PyTorch 2.6.0+cu124, Diffusers 0.32.2, Transformers 4.49.0. Paquet gguf 0.17.1 ajouté seulement dans `flux-q8-g351/vendor`, roue vérifiée SHA, sans dépendance réinstallée et sans modification du runtime partagé. Licence MIT du paquet archivée. Déquantification PyTorch native, aucun kernel CUDA distant ou compilation supplémentaire. Un contrôle sur 16 blocs Q8 compare les résultats GPU à NumPy (tolérance 0,1 %, écart absolu maximal 0,00003004) : compatibilité limitée, pas audit intégral de la conversion.

Empreintes du moteur, de la pipeline, des fonctions GGUF et de l’attention consignées dans `runtime-provenance.json`. Les empreintes runtime avant/après sont identiques. Aucune fusion mémoire des cartes ni mesure NVLink revendiquée : seule GPU0 calcule.

## Incident conservé et exécution

Premier chargement interrompu avant toute image : le chargeur single-file Diffusers 0.32.2 conserve les paramètres sur CPU et ignore le placement passé au chargement. Le contrôle de placement a refusé cet état. Correction dans le seul runner : transfert explicite `transformer.to('cuda:0')`, puis contrôle des 1 156 paramètres et des matrices quantifiées. Essai échoué conservé dans `run00-placement-failed`, ancienne source archivée. Le contrôle 512² et la grille suivants ont terminé sans incident.

Génération locale, accès réseau sortant interdit dans les unités, verrou de campagne et UUID exact de GPU0. Limites 72 Go RAM, 800 % CPU, 90 minutes ; garde 65 °C GPU / 70 °C HBM. Fraction d’allocation PyTorch bornée à 0,94 sur GPU0. Aucun entraînement ou déploiement. GPU1 et GTX 1060 ne participent pas au calcul.

Pic VRAM GPU0 : 15158 Mio. Maxima GPU 43 °C et HBM 50 °C. Consigne 300 W, pic ponctuel 315.28 W ; aucune mesure d’énergie totale. CPU Tdie 46.500 °C sur la grille à cache chaud. Coût initial des quatre encodages : 39.781231779 s. Erreurs de télémétrie sur la grille : 0.

Douze images terminées après correction du placement initial, latents et pixels finis, répétition pixel et PNG identiques. Aucun incident dans les deux lots achevés. Contrôle final 2026-11-14T20:28:44.684896+01:00 : runtime partagé inchangé, douze SHA PNG vérifiés, aucun client GPU, cinq services actifs et Memory-engine en marche. Machine laissée allumée.

## Images

| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |
| --- | --- | ---: | --- | --- |
| G351-00 | hand / smoke | 3.123 | Rejetée | Quatre doigts visibles, pouce compris : anatomie non conforme. |
| G351-01 | hand / quality | 15.755 | Proposée | Cinq doigts distincts, paume et poignet visibles. Peau très lissée et détail limité. |
| G351-02 | hand / quality | 15.601 | À revoir | Cinq doigts visibles, mais volume exagéré à la base du pouce et plis peu naturels. |
| G351-03 | objects / quality | 15.600 | Proposée | Une tasse rouge à gauche, un bol bleu à droite ; objets complets et séparés. |
| G351-04 | objects / quality | 15.599 | Proposée | Disposition et couleurs respectées, deux objets complets ; rendu céramique propre. |
| G351-05 | katana / quality | 15.612 | Rejetée | Deux sabres croisés au lieu d’un katana accompagné de son fourreau. |
| G351-06 | katana / quality | 15.615 | À revoir | Lame et fourreau présents, mais poignée très courte, raccord inhabituel et pointe large. |
| G351-07 | duo / quality | 15.623 | Rejetée | La femme et son kimono sont coupés en bas du cadre ; les deux personnages ne sont pas en pied. |
| G351-08 | duo / quality | 15.619 | Proposée | Les deux personnages et leurs pieds sont visibles ; marge basse étroite, mais cadrage complet. |
| G351-09 | hand / repeat | 15.624 | Proposée | Répétition de G351-01 : cinq doigts, même rendu très lissé. |
| G351-10 | duo / screen16x9 | 6.809 | Rejetée | Les deux personnages sont coupés à mi-corps ; cadrage en pied non respecté. |
| G351-11 | duo / screen4x3 | 4.907 | Rejetée | Bas du corps hors cadre pour les deux personnages. |

## Livrable et limites

Rapport illustré `Eidolon-comparatif-FLUXSchnellQ8-G351.pdf`, 14 pages, identité `libfile_fde3_f-481f0827f80c81919177e865576a6eee_d168d29c22b4819186c4d3b8d1b7451f`. Synthèse `flux-q8-validation-g351.json`, preuves `evidence-g351/`, sources du runner et du rapport conservées.

PNG, latents, encodages et incident conservés sous `/srv/eidolon/workspaces/media-20261112/flux-q8-g351/`. Poids sous `/srv/eidolon/data/media-models-20261113/flux-schnell-q8/`. Les résultats bruts restent NOT_REVIEWED/PENDING_REVIEW ; la synthèse porte la revue ultérieure. Les aperçus sont réduits pour la revue ; les PNG natifs restent disponibles.

Quatre scènes, deux seeds et appréciation subjective. Même recette Schnell, mais quantification et nombre de GPU changent ensemble : ne pas attribuer la totalité du delta de temps à la seule déquantification. Les chronomètres incluent génération, décodage, contrôles et sauvegarde du latent, pas chargement, encodage ou écriture PNG finale. Pas de latence depuis clic, ni de conclusion statistique générale ou d’approbation utilisateur inventée.

[Conversion city96](https://huggingface.co/city96/FLUX.1-schnell-gguf/tree/f495746ed9c5efcf4661f53ef05401dceadc17d2) ; [support GGUF Diffusers](https://huggingface.co/docs/diffusers/quantization/gguf) ; [témoin complet G339](FLUX-COMPARISON-G339.md) ; [Klein G340](KLEIN-G340.md).
