# SD3.5 Medium avec Skip Layer Guidance — G347, 14 novembre 2026

Eidolon Core Technologies (ECT). Powered by Stability AI.

## Résultat

Douze images générées et examinées. Huit images principales 1024² : **3 proposées, 0 à revoir, 5 rejetées**, contre **1 proposée, 1 à revoir, 6 rejetées** sans SLG (G346). Une main est corrigée : G347-02 a cinq doigts, contre six en G346-02. L’anse de la tasse04 est désormais ouverte et cohérente. La main01 reste à six doigts ; les deux katanas et les deux duos restent non conformes. Les défauts sont conservés.

Médiane native **24,053769 s**, contre22,376442 s, soit **+7,495951 %**. Plage23,986894–24,135629 s. Une V10016Go, pic10 556Mio, GPU/HBM47/52°C. Aucun gain suffisant pour remplacer Klein (G340 corrigé :5/8,3,396s). Z-Image G344 reste réservé aux demandes détaillées suivant la préférence utilisateur. Petite grille, avis GPT provisoires, aucune promotion et aucun avis utilisateur attribué aux nouvelles images.

## Comparaison contrôlée

Même modèle et poids vérifiés G346, même cache d’encodages SHA256, mêmes prompts et seeds20261113/20261114, mêmes quatre scènes, résolutions et protocole.40étapes,CFG4,5, FlowMatchEuler shift3, négatif vide,256tokensT5. Transformer FP16 GPU0, VAE FP32 tuilé GPU0 ; CLIP-L/CLIP-G/T5-XXL CPU FP32 encodés durant G346. Cache réutilisé, aucun nouvel encodage :42,891310s est le coût initial historique, pas un coût CPU supplémentaire G347. Chargement du lot3,672001s.

Seul réglage génératif ajouté : **SLG couches[7,8,9], force2,8, début0,01, fin0,2**. Diffusers0.37.0 effectue ici sept passes supplémentaires aux indices1..7. Un forward_pre_hook non modifiant contrôle **47appels dont7SLG sur chacune des12images**. La recette garde40étapes etCFG4,5 pour isoler SLG ; elle ne reproduit pas littéralement le workflow ComfyUI auteur, qui a d’autres paramètres.

`controlled-comparison.json` conserve la comparaison des champs modèle/précision/runtime/scheduler/grille/pipeline et SHA des encodages. L’ordre de la liste de métadonnées `_use_default_values` varie avec la sérialisation ; seul cet ordre non numérique est normalisé. Tous les paramètres numériques sont inchangés. Aucune exception de génération. Le runner corrigé G346 est réutilisé ; ses incidents antérieurs ne sont pas de nouveaux incidents G347.

Chronomètre : génération et décodage, contrôles numériques et sauvegarde du latent inclus ; hors chargement, encodage et sauvegarde PNG finale. Médiane sur indices1..8 uniquement. Aucune latence « depuis clic » ni énergie totale revendiquée. L’instrumentation SLG ajoute un compteur Python ; le surcoût est donc celui de la recette instrumentée.

## Reproductibilité, provenance et contrôle matériel

PyTorch2.6.0+cu124, Diffusers0.37.0, Transformers4.56.1, runtime KleinG340 inchangé. SDPA EFFICIENT_ATTENTION transformer, MATH VAE. Pas de quantification, aucune installation nouvelle, aucune génération externe. Verrou de campagne, UUID GPU0 imposé, réseau sortant bloqué,72GoRAM/800%CPU/90minutes, garde65°C GPU et70°C HBM. GPU1 au repos, GTX1060 inchangée.

Poids déjà présents : auteur `stabilityai/stable-diffusion-3.5-medium`, révision `b940f670f0eda2d07fbb75229e779da1ad11eb80` ; copie publique `adamo1139/stable-diffusion-3.5-medium-ungated`, révision `1cb9becf522803da9d25c2713d1a82b41bc6198d`. Six SHA de poids identiques aux métadonnées auteur, fichiers déjà téléchargés et revérifiés. Licence Stability AI Community5juillet2024 archivée. Aucun nouveau téléchargement de poids pour G347. Les champs historiques `source: download` du manifeste désignent leur provenance G346, pas un téléchargement durant ce lot.

Contrôle512² en5,654687s : proposé hors score. Répétition09 identique à01 en pixels et PNG, toujours six doigts. Écran16:9 rejeté (mains féminines cachées),4:3 à revoir (anatomie des mains/pieds). Douze PNG vérifiés SHA. Zéro erreur de télémétrie ; limite300W, pic ponctuel309,09W. Contrôle final14/11/2026 à19h25 Paris : aucun client GPU, cinq services actifs, Memory-engine en marche, runtime identique avant/après. Machine laissée allumée. Aucun entraînement ni changement sur l’autre plateforme.

## Images

| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |
| --- | --- | ---: | --- | --- |
| G347-00 | hand / smoke | 5.655 | Proposée | Cinq doigts séparés, paume et poignet visibles. Texture un peu lissée ; contrôle 512² hors score. |
| G347-01 | hand / quality | 24.136 | Rejetée | Six doigts : quatre doigts centraux et deux appendices latéraux. |
| G347-02 | hand / quality | 24.004 | Proposée | Cinq doigts distincts : quatre dressés et un pouce à droite. Paume et poignet cohérents, légère texture lissée. |
| G347-03 | objects / quality | 23.987 | Proposée | Une tasse rouge à gauche et un bol bleu à droite, complets sur fond gris. Anse ouverte et céramique crédible. |
| G347-04 | objects / quality | 24.020 | Proposée | Deux objets complets, couleurs et positions conformes. Anse de la tasse ouverte et lisible. |
| G347-05 | katana / quality | 24.047 | Rejetée | Poignée et pièce ressemblant à une lame séparées ; aucun katana assemblé avec son fourreau cohérent. |
| G347-06 | katana / quality | 24.061 | Rejetée | Plusieurs pièces supplémentaires et dissociées, lame et poignées incompatibles ; katana non cohérent. |
| G347-07 | duo / quality | 24.105 | Rejetée | Deux adultes en pied, mais une main de la femme reste cachée ; pieds et chaussures déformés. |
| G347-08 | duo / quality | 24.123 | Rejetée | Couleurs et duo respectés, mains visibles, mais jambes et pieds coupés par le cadre. |
| G347-09 | hand / repeat | 24.141 | Rejetée | Répétition exacte de 01 : mêmes pixels, même PNG et six doigts. |
| G347-10 | duo / screen16x9 | 11.997 | Rejetée | Format 16:9 : deux adultes en pied, mais mains de la femme cachées dans les manches. |
| G347-11 | duo / screen4x3 | 8.954 | À revoir | Format 4:3 : deux adultes en pied, mains visibles, mais mains/gants peu lisibles et pieds féminins disproportionnés. |

## Rapport et preuves

Rapport illustré `Eidolon-comparatif-SD35-SLG-G347.pdf`,14pages, identité `libfile_fde3_f-22914c86f14081918b4f51946505e3fe_d168d29c22b4819186c4d3b8d1b7451f`,version0. Preuves `evidence-g347/`, synthèse `sd35-slg-validation-g347.json`. Générateur `sd35_slg_probe_g347.py`, lanceur `launch_g347.py`, contrôle `health_g347.py`. Les sources locales du rapport et de la revue sont aussi archivées dans ce lot.

PNG/latents/caches conservés sous `/srv/eidolon/workspaces/media-20261112/sd35-slg-g347/`,run01(smoke),run02(qualité). Poids partagés dans `/srv/eidolon/data/media-models-20261113/sd35-medium`. Les preuves brutes portent encore PENDING_REVIEW/NOT_REVIEWED, leur état au moment de la génération ; la synthèse et `visual-reviews.json` constituent la revue ultérieure.

[G346 sans SLG](SD35-MEDIUM-G346.md). Ce lot ne teste pas SD3.5 Large/Turbo ni une autre force SLG. Comparaison des recettes historiques Klein et Z-Image, sans conclusion de supériorité générale.
