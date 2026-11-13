# FLUX.1 dev sur deux V100 — G338

13 novembre 2026. Lot de recherche demandé par toytoy, sans intégration en production.

## Résultat

Le générateur complet FP16 fonctionne réellement réparti sur les deux V100 SXM2 16 Go. Le lot final produit 12 images : contrôle 512², huit images 1024² (quatre scènes × deux seeds), répétition, formats 16:9 et 4:3. La grille native donne **4 propositions, 2 réserves et 2 rejets**, sous réserve de la revue de toytoy. Les deux duos sont rejetés pour cadrage incomplet malgré un rendu soigné. Aucun entraînement ni profil promu.

Les notes sont une revue qualitative GPT sur aperçus JPEG de 768 pixels maximum, sans retouche, pas une mesure statistique ni une validation anatomique professionnelle. Les PNG et latents natifs restent sur la X399. Les trois prompts main/objets/katana reprennent G332 ; le duo n'est pas une comparaison strictement identique à Sana. Ne pas conclure à une supériorité générale entre modèles sur ces petits échantillons et recettes différentes.

## Recette et mémoire

- PyTorch 2.6.0+cu124, Diffusers 0.32.2, pilote inchangé. Encodeurs CPU FP32, générateur FP16 sans quantification ni déchargement CPU, VAE GPU0 FP32.
- Paramètres du générateur : 11 644 359 680 octets GPU0 et 12 158 456 960 octets GPU1 ; placement réel vérifié après chargement strict.
- 50 étapes, guidance 3,5, scheduler FlowMatchEuler avec décalage dynamique (base 0,5 ; maximum 1,15). Contrôle réduit à 20 étapes.
- Attention découpée par 256 requêtes, avec toutes les clés/valeurs conservées pour chaque tranche ; pas de noyau CUDA externe ni patch global.
- Premier essai : contrôle 512² réussi, puis manque de mémoire au décodage VAE de la première 1024². Le seuil par défaut 1024 ne déclenchait pas le découpage à cette taille. Échec et runner original conservés dans `run01`.
- Correction : tuiles VAE de 512 pixels, recouvrement 25 %, plafond mémoire inchangé. Les latents sont maintenant sauvegardés avant décodage. Le découpage VAE peut modifier les pixels ou introduire des raccords ; aucune équivalence avec un décodage intégral n'est revendiquée.

## Validation logicielle et opérationnelle

Deux tests numériques sur un petit réseau Flux comportant blocs doubles/simples, contexte texte et rotation positionnelle : différence maximale 0 en FP32 CPU et FP16 sur V100 face au processeur amont. Cela ne démontre pas l'équivalence de toutes les tailles du modèle complet. Suite média : 255 tests, 249 réussis et 6 ignorés ; le test V100 ignoré dans la suite générale a été exécuté séparément et réussi. Une première invocation sans PYTHONPATH a échoué à l'import ; journal conservé, invocation corrigée réussie.

Unité isolée, verrou GPU, réseau sortant bloqué pendant l'inférence, poids préalablement vérifiés, garde GPU 65 °C/HBM 70 °C, garde de non-fini et de concurrence. Consigne 300 W par carte. Les compteurs NVLink ont augmenté ; cela ne mesure pas un gain de vitesse dû à NVLink. Les pics de puissance sont échantillonnés et ne sont ni une énergie totale ni la consommation à la prise.

## Provenance

FLUX.1 dev téléchargé depuis Comfy-Org/Flux-1-Dev, révision `10cf201a3d49f7ff4de84d6a97d6a32cdfa8cb86`. 23 802 932 552 octets, SHA256 `4610115bb0c89560703c892c59ac2742fa821e60ef5871b33493ba544683abd7`, identiques aux métadonnées LFS publiques BFL consultées. Les encodeurs et le VAE existants sont réutilisés et vérifiés, sans téléchargement en cours de génération. Les manifestes détaillent chaque fichier.

Licence **FLUX.1 dev Non-Commercial v1.1.1**, différente d'Apache-2.0 ; texte auteur archivé, empreinte Git identique aux métadonnées officielles. Usage expérimental local non commercial. L'endpoint officiel protégé a répondu 401 ; aucune tentative de contournement, distribution publique Comfy utilisée.

Sources primaires : [modèle BFL](https://huggingface.co/black-forest-labs/FLUX.1-dev), [distribution Comfy](https://huggingface.co/Comfy-Org/Flux-1-Dev), [licence auteur](https://github.com/black-forest-labs/flux/blob/main/model_licenses/LICENSE-FLUX1-dev), [Diffusers 0.32.2](https://huggingface.co/docs/diffusers/v0.32.2/en/api/pipelines/flux).

## Preuves et suite

`flux-dev-validation-g338.json` rassemble résultats, empreintes, mesures, verdicts et échec initial. Les preuves complémentaires sont sous `evidence-g338/`. Les artefacts natifs restent sous `/srv/eidolon/workspaces/media-20261112/flux-dev-g338/run02` ; `run01` reste conservé. Le PDF de revue contient les douze images et leurs réserves.

Suite utile : confirmer les images proposées avec toytoy, puis tester la robustesse du cadrage en pied sur de nouvelles seeds et un protocole séparé. L'installation dans l'API locale reste à réaliser après validation ; le succès du runner n'est pas une intégration au service. Les autres candidats et le défaut AnimateDiff restent ouverts.

## Mesures finales

1024² : 70.30–70.81 s, médiane 70.58 s (GPU et décodage). Encodage CPU des quatre prompts : 35.86 s, réutilisé ; chargement/placement : 13.18 s, hors téléchargement/vérification. Formats 16:9 : 35.84 s ; 4:3 : 28.18 s, tous deux rejetés pour cadrage. Répétition pixel-identique.

| Mesure | V100 0 | V100 1 |
| --- | --- | --- |
| VRAM maximale (Mio) | 13 366 | 13 082 |
| GPU maximal (°C) | 47 | 47 |
| HBM maximale (°C) | 48 | 51 |
| Puissance maximale relevée (W) | 323,91 | 327,34 |
| Limite configurée (W) | 300 | 300 |

Les relevés instantanés dépassent brièvement la consigne ; aucune limite supérieure absolue de 300 W n'est déduite. Aucun arrêt thermique, erreur de mesure ou non-fini. CPU Tdie maximum 48,25 °C. Unité terminée avec code 0, aucun client CUDA restant, cartes à 1 Mio au contrôle final. Les cinq services Core/communication/Ollama/Darme/tunnel sont actifs et la VM Memory-engine tourne. Machine laissée allumée.
