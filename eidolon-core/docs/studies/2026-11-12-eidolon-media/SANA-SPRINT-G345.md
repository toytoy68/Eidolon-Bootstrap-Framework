# Sana Sprint 1,6B — G345, 14 novembre 2026

Eidolon Core Technologies (ECT) — recherche locale, revue GPT provisoire.

## Résultat

Douze images générées et examinées. Huit natives 1024² : **2 proposées, 1 à revoir, 5 rejetées**. Les deux scènes tasse rouge/bol bleu sont conformes. La main01 a cinq doigts mais une morphologie discutable ; la main02 en a six. Les deux katanas multiplient les lames et accessoires. Les duos échouent par mains/pieds masqués ou cadrage incomplet. Contrôle512² rejeté, deux formats écran rejetés. Répétition09 exactement identique à01, mêmes réserves ; pas de double comptage.

Médiane **1,832853 s GPU + décodage**, hors encodage et chargement. Klein G340 :3,396s et5/8 après correction des six doigts ; Z-Image base G344 :279,383s et6/8. Recettes différentes : ce lot ne démontre pas une supériorité générale. Sprint semble utile aux aperçus et objets simples, sans remplacer Klein pour les itérations exigeantes. Z-Image reste réservé aux générations détaillées à la demande selon toytoy.

## Recette fixée avant génération

Même grille que G339–G344 : quatre prompts, deux seeds20261113/20261114, huit natives1024², contrôle512², répétition et formats1024×576/768×576. Sana Sprint1,6B public, révision `19683c58b7ea290e55cedd8950ae1d86ada7ef96` du dépôt `Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers`. Quatre fichiers de poids vérifiés SHA-256 et configurations contrôlées ; poids Gemma2 réutilisés seulement après contrôle d’identité. Nouveaux poids transformeur et VAE téléchargés ; aucun code distant exécuté.

Quatre étapes SCMScheduler, guidance intégrée4,5, max_timesteps1,57080, intermediate_timesteps=None. Transformer et DC-AE FP32 sur GPU0 V10016 ; Gemma2 CPU FP32/eager,300tokens. Préambule officiel complex_human_instruction conservé dans l’encodage, sans génération d’un prompt réécrit. Binning désactivé, VAE tuilé512. Préservation de la plage des poidsBF16 par FP32 ; pas de FP16/quantification revendiqués. Attention linéaire native Sana.

Runtime G340 inchangé : PyTorch2.6.0+cu124, Diffusers0.37.0, Transformers4.56.1. Encodage initial des quatre textes26,757s, cache réutilisé pour run02/03 ; chargement transformeur/VAE du lot qualité3,498s. Mesures inférence séparées, aucun temps « depuis clic » revendiqué.

## Incident conservé

run01 s’arrête avant la première génération : `ValueError: Intermediate timesteps for SCM is not supported when num_inference_steps != 2.` La valeur par défaut1,3 de la pipeline ne convient qu’à deux étapes. Correction explicite `intermediate_timesteps=None`, conservation de quatre étapes et de toutes les autres conditions. run02 produit le contrôle, run03 le lot complet. L’ancien script, les journaux et failure.json sont conservés ; aucune image échouée cachée ou réussite inventée.

## Matériel, intégrité et fin

Une V100 utilisée, seconde au repos, GTX1060 inchangée. Limite300W, verrou de campagne, garde65°C GPU/70°C HBM, mémoire72Go et CPU800% plafonnés ; inférence sans réseau sortant. Maximum GPU42°C, HBM44°C, VRAM9 184Mio ; CPU Tdie40,75°C ; zéro erreur de télémétrie. Pic ponctuel310,52W malgré consigne300W, non assimilable à une consommation moyenne ou une énergie.

Douze PNG vérifiés SHA-256, répétition pixel/PNG identique, runtime avant/après identique. GPU sans client et cinq services actifs ; VM Memory-engine en cours. Machine laissée allumée. Aucun entraînement, aucune intégration production, aucune modification de l’autre plateforme.

## Sources et preuves

[Carte et révision auteur](https://huggingface.co/Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers/tree/19683c58b7ea290e55cedd8950ae1d86ada7ef96). Modèle déclaré Apache-2.0, encodeur soumis aux conditions Gemma2 ; textes et licence DC-AE archivés. PDF `Eidolon-comparatif-SanaSprint-G345.pdf`,14pages avec les12images et référencesG344/Klein, identité `libfile_fde3_f-bacba2da46dc81918dd7e66e8b87e6e5_d168d29c22b4819186c4d3b8d1b7451f`,version0. Aucun avis utilisateur attribué à G345.

Données : `sana-sprint-validation-g345.json`, `evidence-g345/`. PNG, latents et caches : `/srv/eidolon/workspaces/media-20261112/sana-sprint-g345/`, runs01–03. Scripts préparation et exécution conservés dans l’étude. Résultats valables pour cette recette et ces huit images seulement ; variante600M non testée.
