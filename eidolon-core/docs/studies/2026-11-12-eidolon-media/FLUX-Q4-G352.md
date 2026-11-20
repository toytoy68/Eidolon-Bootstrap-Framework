# FLUX.1 Schnell GGUF Q4_0 — G352, 14 novembre 2026

Eidolon Core Technologies (ECT).

## Résultat et décision

Schnell Q4 : 35.2 % de VRAM en moins que Q8. 3/8 images proposées ; 16.21 s médianes contre 15.61 s pour Q8, sur la même V100.

Conformité : 3 proposées, 2 à revoir, 3 rejetées sur huit natives. Q8 et FP16 : 4/8 chacun. La main 01 devient plus floue ; le katana 06 gagne une poignée détachée. Avis GPT provisoires.

Temps : 16.21 s contre 15.61 s en Q8 (+3.8 %). Le complet FP16 réparti sur deux cartes faisait 6.45 s. Temps hors encodage des textes et chargement du modèle.

Mémoire et chauffe : pic 9824 Mio (9.59 Gio), contre 15158 Mio en Q8. GPU1 au repos. Maxima GPU 44 °C / HBM 49 °C.

Décision : à réserver aux contraintes de VRAM. Sur ce lot, moins de mémoire mais une finition moins bonne et aucun gain de vitesse. Aucun remplacement des favoris et aucune promotion.

Huit natives 1024² : **3 proposées, 2 à revoir, 3 rejetées**. Médiane 16.212118706 s, plage 16.191359652–16.372668824 s. Toutes les revues sont provisoires, par GPT ; aucune validation toytoy attribuée.

## Recette et méthode

Comparaison : mêmes prompts, seeds, quatre étapes et guidage 0 que G351/G339. Q8 et Q4 utilisent GPU0 seulement, même runtime et même attention. FP16 complet utilise deux cartes : son temps ne permet pas d’isoler le coût de la quantification.

Précision : fichier Q4_0 avec tenseurs auxiliaires F16 ; déquantification dynamique, calcul FP16, 494 modules GGUFLinear. Tous les paramètres du générateur sur GPU0, sans offload CPU. Quatre appels du modèle et 228 appels de blocs contrôlés par image.

Recette : FlowMatchEuler shift 1, pas de décalage dynamique ; attention découpée en 256 requêtes. VAE Flux FP32 sur GPU0, tuiles de 512 pixels. CLIP-L/T5 CPU FP32, 256 tokens, embeddings FP16.

Chronométrage : quatre nouveaux encodages CPU en 37.33 s, puis cache pour la grille. Chargement grille : 6.15 s. Temps image : génération, décodage, contrôles et sauvegarde du latent ; écriture PNG finale exclue.

Traçabilité : conversion city96 f495746, SHA vérifié ; Apache 2.0 et licence MIT gguf archivées. PyTorch 2.6.0+cu124, Diffusers 0.32.2 et Transformers 4.49.0 inchangés. gguf 0.17.1 isolé ; aucun kernel distant.

Exécution : douze images terminées ; répétition à pixels et PNG identiques. Correction d’un chemin de copie de licence pendant la préparation, conservée dans les preuves. Aucun échec de génération.

Matériel : consigne 300 W, pic ponctuel 323.00 W, sans mesure d’énergie totale. Garde 65 °C GPU / 70 °C HBM. Services actifs et GPU libres après les tests ; machine laissée allumée.

Limites : huit images natives, appréciation subjective sur aperçus réduits ; PNG originaux conservés. Deux seeds ne mesurent pas la fiabilité générale. « Proposée » ne signifie pas approuvée par toytoy.

Même grille que Q8 G351 et complet G339 : main ouverte, tasse/bol, katana/fourreau, duo en pied ; seeds 20261113 et 20261114. Huit natives 1024², contrôle 512², répétition, 1024×576 et 768×576. Prompts et seeds figés avant observation, sans retouche ni sélection a posteriori.

Fichier Q4_0, 776 tenseurs (304 Q4_0, 472 F16). Après conversion des noms et séparation des projections : 494 modules GGUFLinear, 1 156 paramètres sur GPU0 ; 6 770 653 312 octets de paramètres dont 6 656 753 664 quantifiés. Déquantification dynamique PyTorch vers FP16, pas de calcul natif INT4 ni de kernel CUDA distant. Tous les paramètres du générateur résident sur GPU0, sans offload CPU. Quatre appels du générateur et 228 appels de blocs vérifiés par image.

Attention MATH par morceaux de 256 requêtes, VAE Flux FP32 sur GPU0 avec tuiles de 512 pixels. Scheduler FlowMatchEuler shift 1, décalage dynamique désactivé, 4 étapes, guidage 0. CLIP-L et T5-XXL via Comfy CPU FP32, 256 tokens, embeddings enregistrés FP16. Quatre nouveaux encodages G352, puis cache vérifié par SHA réutilisé. L’avertissement CLIP text_projection.weight absent existait déjà dans G339/G351 ; encodeurs inchangés.

## Provenance et environnement

Conversion publique city96/FLUX.1-schnell-gguf, révision f495746ed9c5efcf4661f53ef05401dceadc17d2. Variante exacte flux1-schnell-Q4_0.gguf (pas Q4_K_S). Fichier de 6 770 707 360 octets, SHA256 90a393d3a44bec691c707003f434fdde06064b870bb3c206eb7a4f109b25ff4e. Provenance directe BFL déclarée par le convertisseur, sans audit intégral de conversion. Carte auteur et licence Apache 2.0 de Schnell archivées. Encodeurs et VAE G339 réutilisés après vérification de chaque SHA.

PyTorch 2.6.0+cu124, Diffusers 0.32.2, Transformers 4.49.0 ; même environnement preference-lab et mêmes sources de pipeline/attention que Q8. Paquet gguf 0.17.1 installé dans flux-q4-g352/vendor, roue SHA vérifiée, sans dépendances réinstallées. Licence MIT archivées. Test de déquantification de 16 blocs Q4 sur V100 contre NumPy : écart maximal nul sur cet échantillon seulement. Sources et résultat conservés.

## Incident et exécution

Après téléchargement et vérification réussis, la préparation a échoué uniquement à la copie de la licence gguf : le script cherchait dist-info/licenses/LICENSE, alors que la roue fournit dist-info/LICENSE. Chemin corrigé dans la source, licence copiée depuis la roue et comparée à celle de G351 avant tout lancement. Ancienne source, journal et réparation archivés. Ce défaut ne concernait ni les poids ni le runtime d’inférence.

Le transfert explicite transformer.to('cuda:0'), introduit en G351 pour le chargeur single-file Diffusers 0.32.2, est conservé dès le départ. Contrôles de placement effectués avant génération. Contrôle 512² puis grille terminés sans échec de génération.

Générations locales, réseau sortant bloqué dans les unités transitoires, verrou de campagne, UUID exact GPU0. Limites 72 Go RAM, 800 % CPU, 90 minutes ; allocation PyTorch limitée à 0,94 de GPU0 et garde 65 °C GPU / 70 °C HBM. GPU1 et GTX1060 ne participent pas au calcul. Aucun pilote, service de production, entraînement ou modèle favori modifié.

Pic VRAM GPU0 9824 Mio, réduction 35.19 % face à Q8. GPU/HBM 44/49 °C. Consigne 300 W, pic échantillonné 323.00 W ; pas de mesure d’énergie totale. CPU Tdie 39.750 °C sur la grille à cache chaud. Erreurs de télémétrie : 0. Encodages : 37.328070957 s ; chargement grille : 6.153811317 s.

Douze images terminées, latents et pixels finis, répétition pixel et PNG identiques. Incident de préparation limité à la copie de licence, corrigé avant génération et archivé. Contrôle final 2026-11-14T21:49:10.680340+01:00 : runtime partagé inchangé, douze SHA PNG vérifiés, aucun client GPU, cinq services actifs et Memory-engine en marche. Machine laissée allumée.

## Images

| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |
| --- | --- | ---: | --- | --- |
| G352-00 | hand / smoke | 2.820 | Rejetée | Quatre doigts visibles, pouce compris : anatomie non conforme. |
| G352-01 | hand / quality | 16.373 | À revoir | Cinq doigts distincts, mais doigts courts et rendu nettement flou ; plis et contours peu définis. |
| G352-02 | hand / quality | 16.191 | À revoir | Cinq doigts visibles, mais volume excessif à la base du pouce et raccord paume/pouce peu naturel. |
| G352-03 | objects / quality | 16.197 | Proposée | Une tasse rouge à gauche et un bol bleu à droite, complets et bien séparés. |
| G352-04 | objects / quality | 16.210 | Proposée | Deux objets complets, bonnes couleurs et disposition ; céramique détaillée. |
| G352-05 | katana / quality | 16.203 | Rejetée | Deux sabres croisés, sans le fourreau demandé. |
| G352-06 | katana / quality | 16.214 | Rejetée | Katana et fourreau accompagnés d’une poignée supplémentaire détachée ; poignée du sabre trop courte. |
| G352-07 | duo / quality | 16.214 | Rejetée | La femme est coupée en bas du cadre ; les deux adultes ne sont pas visibles en pied. |
| G352-08 | duo / quality | 16.224 | Proposée | Deux adultes complets, tenues et positions respectées ; pieds au bord inférieur et partiellement cachés par le kimono. |
| G352-09 | hand / repeat | 16.211 | À revoir | Répétition de G352-01 : cinq doigts, mais main floue et peu définie. |
| G352-10 | duo / screen16x9 | 7.436 | Rejetée | Les deux personnages sont coupés à mi-corps ; le cadrage en pied est absent. |
| G352-11 | duo / screen4x3 | 5.540 | Rejetée | Les jambes et les pieds des deux adultes sont hors cadre. |

## Livrable et limites

Rapport illustré Eidolon-comparatif-FLUXSchnellQ4-G352.pdf, 14 pages, identité `libfile_fde3_f-7a1cedf9a2308191b0169d8446d07215_d168d29c22b4819186c4d3b8d1b7451f`. Synthèse flux-q4-validation-g352.json et preuves evidence-g352/.

PNG, latents, embeddings et journaux conservés sous /srv/eidolon/workspaces/media-20261112/flux-q4-g352/. Poids sous /srv/eidolon/data/media-models-20261113/flux-schnell-q4/. Les résultats bruts gardent leur statut initial NOT_REVIEWED/PENDING_REVIEW ; la synthèse ajoute la revue ultérieure.

Revue subjective sur aperçus réduits ; PNG natifs conservés. Quatre scènes et deux seeds ne permettent pas de généraliser la fiabilité. Même recette et matériel pour Q8/Q4 ; temps observés sur une exécution, sans intervalle statistique. Comparaison FP16 sur deux cartes : quantification et répartition changent ensemble. Les chronomètres incluent calcul, décodage, contrôles et sauvegarde du latent, mais excluent encodage, chargement et écriture PNG finale. Aucune promesse de latence depuis clic, de performance INT4 native ou de supériorité générale.

[Conversion city96](https://huggingface.co/city96/FLUX.1-schnell-gguf/tree/f495746ed9c5efcf4661f53ef05401dceadc17d2) ; [Q8 G351](FLUX-Q8-G351.md) ; [complet G339](FLUX-COMPARISON-G339.md).
