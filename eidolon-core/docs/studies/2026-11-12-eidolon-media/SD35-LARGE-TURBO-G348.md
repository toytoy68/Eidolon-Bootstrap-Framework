# SD3.5 Large Turbo - G348, 14 novembre 2026

Eidolon Core Technologies (ECT). Powered by Stability AI.

## Résultat et décision

Douze images générées et examinées. Huit natives 1024² : **5 proposées, 0 à revoir, 3 rejetées**. Mains01/02 à cinq doigts, objets03/04 et duo07 proposés. Katanas05/06 rejetés (duplication ou assemblage impossible), duo08 rejeté (passants supplémentaires et mains féminines cachées). Contrôle512² rejeté (quatre doigts apparents, cadrage coupé) ; répétition09 identique à01 et proposée hors score. Formats16:9 et4:3 rejetés pour cadrage.

Médiane native **3,130260 s**, plage **3,123097-3,336172 s**. Klein G340 corrigé :5/8 à3,395657s, soit un temps inférieur de7,82% pour Turbo sur cette petite série. **Turbo emploie deux V100, Klein une seule** ; aucune supériorité énergétique ni générale déduite. Medium SLG G347 :3/8 à24,053769s. Large Turbo améliore les deux mains et un duo face à Medium SLG, mais son rendu reste doux/lissé. Candidat rapide à conserver pour comparaison utilisateur, aucune promotion automatique. Z-Image G344 garde son rôle de génération détaillée à la demande selon toytoy.

## Recette figée avant observation

Recette auteur Turbo : **4 étapes, guidance0, sans SLG**, FlowMatchEuler shift3. Même grille G339-G347 : main ouverte, tasse/bol, katana/fourreau, duo devant château ; seeds20261113/20261114, huit natives1024², répétition, contrôle512² et écrans1024x576/768x576. Aucun prompt ajusté après observation, aucune seed sélectionnée pour améliorer le score.

L’auteur illustre BF16 ; adaptation locale **FP16 sur deux V100 Volta**, sans prétendre valider une équivalence visuelle BF16. VAE FP32 tuilé sur GPU0 ; CLIP-L,CLIP-G,T5-XXL CPU FP32, contexteT5 256. Les quatre poids d’encodeurs, leurs configurations et tokenizers sont identiques à G346 (SHA vérifiés). Cache d’encodages G346 réutilisé avec SHA :42,891310s est le coût initial historique des cinq textes, aucun nouvel encodage G348. VAE identique également réutilisé par lien physique. Aucun nouveau paquet ou pilote installé.

Générateur : blocs0-18 sur GPU0,19-37 sur GPU1, entrées et sortie sur GPU0. Placement réel **8 173 096 064 / 7 940 158 976 octets** de paramètres. Compteurs non modifiants : **76 appels de blocs par GPU et par image**, soit19blocs x4étapes sur chaque carte. Une même image traverse les deux parties du générateur ; pas de mémoire déclarée unifiée. Topologie archivée, aucun volume NVLink mesuré ni revendiqué.

PyTorch2.6.0+cu124, Diffusers0.37.0, Transformers4.56.1 ; runtime G340 identique avant/après. SDPA EFFICIENT_ATTENTION pour le générateur, MATH pour VAE. Chronomètre génération/décodage incluant contrôles numériques et sauvegarde du latent ; hors chargement9,092311s, encodage historique et sauvegarde PNG finale. Pas de latence depuis clic ni énergie totale mesurée. La première native inclut un possible échauffement logiciel ; elle reste conservée dans la série.

## Poids, accès et licence

Auteur `stabilityai/stable-diffusion-3.5-large-turbo`, révision `ec07796fc06b096cc56de9762974a28f4c632eda`. Dépôt auteur gated auto. Copie publique `adamo1139/stable-diffusion-3.5-large-turbo-ungated`, révision `9ad870ac0b0e5e48ced156bb02f85d324b7275d2`. Sept fichiers de poids aux SHA identiques auteur ; les deux shards du nouveau générateur totalisent16 292 705 296octets téléchargés. Quatre fichiers d’encodeurs et le VAE réutilisés après vérification. Fichiers de configuration/tokenizers/index/licence comparés aux blobs ou SHA LFS auteur ; aucun code du miroir exécuté.

Licence Stability AI Community5juillet2024 lue et archivée. Étude personnelle d’évaluation ; aucune inscription ou donnée personnelle transmise au formulaire auteur. La fiche auteur publique a été consultée sur le Web pour la recette ; son téléchargement raw renvoie401, enregistré dans `recipe-source.json`. La fiche du miroir est conservée comme telle (son blob diffère), jamais présentée comme octets de la fiche auteur. Les poids et la licence, eux, correspondent aux métadonnées auteur.

## Exécution et clôture

Préparation et premier contrôle aboutis sans incident de génération. Latents et pixels finis, douze PNG vérifiés par SHA ; répétition09 pixel-identique et PNG-identique à01. Aucun runtime modifié. Réseau sortant bloqué pendant la génération, UUID exacts des deux V100, verrou campagne, limites72GoRAM/800%CPU/90minutes, garde65°C GPU et70°C HBM.

Pics VRAM GPU0/GPU1 **13 692 / 8 550 Mio** ; maxima GPU **40/37°C**, HBM **41/36°C**. Consignes300W chacune, pics ponctuels314,44/304,18W. CPU Tdie46,25°C, zéro erreur télémétrie. GTX1060 inchangée. Contrôle final14/11/2026 à19h37 Paris : GPU sans client, cinq services actifs, VM Memory-engine en marche, runtime inchangé et machine laissée allumée. Aucun entraînement, déploiement ou changement sur l’autre plateforme.

## Revue des images

| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |
| --- | --- | ---: | --- | --- |
| G348-00 | hand / smoke | 1.021 | Rejetée | Quatre doigts apparents seulement, deux extrémités coupées par le cadre. Texture floue ; contrôle 512² hors score. |
| G348-01 | hand / quality | 3.336 | Proposée | Cinq doigts séparés, paume et poignet visibles. Doigts fins et peau lissée, sans anomalie de comptage. |
| G348-02 | hand / quality | 3.126 | Proposée | Cinq doigts distincts et cadrage complet. Paume cohérente, détail de peau assez lissé. |
| G348-03 | objects / quality | 3.123 | Proposée | Une tasse rouge orangé à gauche, un bol bleu à droite, entièrement visibles sur fond gris. Anse ouverte et céramique cohérente. |
| G348-04 | objects / quality | 3.130 | Proposée | Tasse rouge à gauche, bol bleu à droite, complets. Anse lisible et proportions crédibles. |
| G348-05 | katana / quality | 3.130 | Rejetée | Deux poignées et deux lames croisées ; un élément partiellement gainé. Ne représente pas un katana unique avec son fourreau séparé. |
| G348-06 | katana / quality | 3.140 | Rejetée | Lame détachée, poignée sans liaison cohérente et élément supplémentaire ; assemblage impossible. |
| G348-07 | duo / quality | 3.123 | Proposée | Deux adultes en pied, homme en armure noire à gauche et femme en kimono rouge à droite. Mains visibles, détails fins assez doux. |
| G348-08 | duo / quality | 3.132 | Rejetée | Duo principal en pied, mais passants supplémentaires au fond et mains féminines cachées. |
| G348-09 | hand / repeat | 3.124 | Proposée | Répétition exacte de 01 : mêmes pixels, même PNG et cinq doigts. |
| G348-10 | duo / screen16x9 | 1.689 | Rejetée | Format 16:9 : pieds des deux personnages coupés par le bord inférieur. |
| G348-11 | duo / screen4x3 | 1.285 | Rejetée | Format 4:3 : jambes et pieds coupés. Femme de dos, ses deux mains ne sont pas clairement visibles. |

## Livrable, preuves et limites

Rapport illustré `Eidolon-comparatif-SD35LargeTurbo-G348.pdf`,14pages, identité `libfile_fde3_f-f3baafb4cbec8191a2686c5193a47c12_d168d29c22b4819186c4d3b8d1b7451f`,version0. Preuves `evidence-g348/`, synthèse `sd35-large-turbo-validation-g348.json`, scripts préparation/génération/lancement/contrôle et sources du rapport conservés.

PNG/latents/caches : `/srv/eidolon/workspaces/media-20261112/sd35-large-turbo-g348/`,run01(smoke),run02(qualité). Poids : `/srv/eidolon/data/media-models-20261113/sd35-large-turbo`. Les preuves brutes conservent leur état initial PENDING_REVIEW/NOT_REVIEWED ; la synthèse et `visual-reviews.json` portent la revue postérieure.

Quatre scènes seulement et revue subjective explicite. « Proposée » ne vaut pas approbation de toytoy. Comparaison de recettes et matériels différents, pas estimation statistique robuste. [Medium SLG G347](SD35-SLG-G347.md), [Klein G340](KLEIN-G340.md). **SD3.5 Large non Turbo reste non testé.**

[Recette auteur](https://huggingface.co/stabilityai/stable-diffusion-3.5-large-turbo/blob/ec07796fc06b096cc56de9762974a28f4c632eda/README.md) ; [copie publique vérifiée](https://huggingface.co/adamo1139/stable-diffusion-3.5-large-turbo-ungated/tree/9ad870ac0b0e5e48ced156bb02f85d324b7275d2).
