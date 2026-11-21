# Comparaison FLUX.1 dev / Schnell - G339

13 novembre 2026. Suite comparative autorisée par toytoy après G338. Recherche isolée, locale, sans service de génération extérieur.

## Question et protocole

Toytoy distingue le progrès de qualité visuelle de FLUX des défauts de conformité encore observés. Le présent lot sépare donc explicitement **rendu visuel** et **respect des consignes**. Une image peut être réussie esthétiquement et rejetée pour cadrage incomplet. Les verdicts de conformité G338 restent inchangés ; aucun rejet n'est converti rétroactivement en acceptation.

Schnell avait seulement reçu une première validation limitée G332. G339 réalise la même grille de 12 images que dev G338 : main, tasse/bol, katana/fourreau, duo, deux seeds en 1024², contrôle 512², répétition et formats 1024×576/768×576. Prompts, seeds, dimensions et ordre sont vérifiés identiques par préflight. Dev G338 est la référence historique conservée, pas une nouvelle exécution dans ce lot.

Les recettes suivent les variantes : Schnell 4 étapes, guidance 0, sans décalage dynamique ; dev 50 étapes, guidance 3,5, décalage dynamique (contrôle réduit dev à 20 étapes). Ce protocole mesure leur compromis qualité/vitesse dans ces conditions ; il n'isole pas causalement le seul effet du modèle ou du nombre d'étapes. Une seed identique n'impose pas une composition identique entre modèles.

## Exécution

Générateurs complets FP16 répartis sur deux V100 SXM2 16 Go, encodeurs CPU FP32, séquences de 256 tokens, VAE GPU0 FP32. Attention découpée par 256 requêtes et tuiles VAE de 512 pixels avec 25 % de recouvrement, héritées de G338. Pas de quantification, de déchargement CPU du générateur, de changement de pilote ni d'environnement. Les poids existants sont revérifiés par taille/SHA256 avant l'inférence. Les latents sont sauvegardés avant décodage.

Une première unité n'a pas démarré le calcul : PYTHONPATH absent, erreur d'import `eidolon_core`. Journal conservé ; `run02` ajoute le chemin des sources, sans modifier la recette. Ce défaut de lancement n'est pas un échec du modèle. Les tests numériques d'attention CPU FP32/V100 FP16 et la suite média de G338 sont historiques, non rejoués ; vérifications G339 : compilation, égalité du plan et du texte des prompts, chargement strict, poids vérifiés, finitude des latents/pixels et génération réelle de la grille.

Unité limitée à 72 Gio de RAM, 8 cœurs CPU et 20 minutes ; verrou GPU commun, garde de concurrence, seuils GPU 65 °C/HBM 70 °C. Consigne 300 W par V100. Réseau sortant bloqué pendant l'inférence. Les températures et puissances sont des relevés échantillonnés, pas une consommation énergétique à la prise.

## Provenance et limites

Schnell : fichier `flux1-schnell.safetensors`, 23 782 506 688 octets, SHA256 `9403429e0052277ac2a87ad800adece5481eecefd9ed334e1f348723621d2a0a`, distribution Comfy-Org déjà figée en G332. Licence auteur Apache-2.0 archivée. Les encodeurs/VAE partagés et leurs révisions sont documentés dans le manifeste. La licence de dev reste différente.

La configuration HF protégée a répondu 401 ; l'exemple public officiel BFL confirme `shift=(not is_schnell)`. Le code a été lu et archivé, pas exécuté. Documentation primaire : [Diffusers 0.32.2](https://huggingface.co/docs/diffusers/v0.32.2/en/api/pipelines/flux), [exemple BFL](https://github.com/black-forest-labs/flux/blob/main/demo_st.py), [licence Schnell](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-schnell).

Revue GPT sur aperçus de 768 pixels maximum, sans retouche ; huit images natives par modèle, échantillon restreint. L'appréciation du rendu est qualitative, sans évaluation aveugle. Les résultats ne classent pas universellement les modèles et n'établissent pas les performances des versions quantifiées, de Klein ou de nouvelles seeds. PNG et latents natifs conservés sur la X399. Aucun entraînement ni profil promu.

Les résultats et comparaisons détaillées sont dans `flux-comparison-g339.json` ; les éléments de préparation et le journal sont sous `evidence-g339/`. Le PDF présente chaque paire dev/Schnell, y compris les contrôles exclus du score principal.

## Résultats G339

Schnell est une alternative rapide crédible. La grille donne 4 propositions, 2 réserves et 2 rejets pour chaque modèle, sur des images différentes. Dev est plus convaincant sur les katanas et plusieurs détails ; Schnell reste proche sur les objets et réussit un duo en pied. Le score de conformité identique ne signifie pas une qualité visuelle identique.

12 générations Schnell terminées, répétition pixel-identique. Grille native : 4 proposées (01/03/04/08), 2 réserves (02/06), 2 rejets (05/07). Contrôle 512² rejeté (4 doigts), formats écran rejetés pour cadrage incomplet. Dev G338 : 4 proposées (02/03/04/06), 2 réserves (01/05), 2 rejets (07/08). Ces comptes de conformité ne constituent pas un score de beauté.

| Mesure | Dev G338 | Schnell G339 |
| --- | --- | --- |
| Étapes / guidance | 50 / 3,5 | 4 / 0 |
| Médiane GPU + décodage 1024² | 70.577 s | 6.451 s |
| Encodage CPU des 4 prompts | 35.865 s | 35.439 s |
| Chargement/placement | 13.177 s | 13.158 s |
| VRAM maximale GPU0 / GPU1 | 13 366 / 13 082 Mio | 13 346 / 13 082 Mio |
| GPU maximum | 47 / 47 °C | 40 / 40 °C |
| HBM maximum | 48 / 51 °C | 40 / 41 °C |
| Pic de puissance échantillonné | 323,91 / 327,34 W | 320,62 / 313,85 W |

Rapport des médianes GPU/décodage : 10.94 fois. Encodage, chargement et vérification exclus : ce facteur ne représente pas la latence totale à froid. Schnell natif : 6.445–6.474 s. Les durées de charge étant différentes, les températures ne prouvent pas un meilleur rendement énergétique. CPU Tdie Schnell : 55,375 °C maximum. Zéro erreur de mesure.

Après le lot : GPU sans client CUDA, 1 Mio par V100 ; services Core/communication/Ollama/Darme/tunnel actifs, VM Memory-engine en marche. Machine laissée allumée. Suites pertinentes : conserver dev comme référence de rendu et Schnell comme référence de vitesse, puis comparer Klein ou une autre architecture après audit. Aucun nouveau candidat déclaré testé sur cette seule comparaison.
