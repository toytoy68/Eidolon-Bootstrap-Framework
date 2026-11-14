# Z-Image Turbo - G342, 14 novembre 2026

Poursuite autorisée par toytoy sur Eidolon-OS X399. Les deux V100 SXM2 16 Go portent les mêmes UUID que G340. La plateforme de test V100 distincte n'est pas utilisée. Base locale301f4eab70e9ab09e72b893eaa23f017a3b9dfb3 (G341 et qualification RAM) ; reprise depuis son contenu, sans refaire G341.

## Candidat et protocole

Klein9B reste différé : le dépôt auteur annonce un accès soumis à acceptation sur Hugging Face. Aucun téléchargement de ses poids, aucune recherche de contournement. Le lot continue avec I17, `Tongyi-MAI/Z-Image-Turbo`, révision `f332072aa78be7aecdf3ee76d5c247082da564a6`, carte modèle déclarant Apache-2.0. Licence Apache du code auteur archivée à sa révision exacte, référence Qwen3 conservée.

Sept fichiers de poids et treize fichiers de configuration/tokenizer/carte sont récupérés depuis la révision figée. Chaque poids est contrôlé par taille et SHA256 LFS ; fichiers ordinaires par hash Git blob puis SHA256 local. Le générateur auteur est stocké en FP32 : ce lot conserve FP32. Les poids de Klein ne sont pas substitués à ceux du nouveau modèle. Le téléchargement est séparé de l'inférence, qui fonctionne réseau sortant bloqué.

Mêmes quatre prompts, deux seeds et dimensions que G338/G340 : main ouverte, tasse rouge/bol bleu, katana/fourreau, duo devant château. Contrôle512², huit natives1024², répétition de la main, formats1024×576 et768×576. Aucun prompt amélioré après observation ; quatre textes encodés sur CPU, sans prompt négatif ni génération externe.

Recette auteur : neuf étapes demandées, guidance0. Le nombre d'appels du générateur est mesuré séparément. Qwen3 FP32 CPU, maximum512tokens, avant-dernière couche cachée, template de discussion du tokenizer. Générateur FP32 partagé entre les cartes ; VAE AutoencoderKL FP32 GPU0 en tuiles512. Ce VAE utilise la normalisation spécifique de Z-Image, distincte de celle de Klein.

## Compatibilité V100 et contrôles

Runtime G340 réutilisé sans installation : PyTorch2.6.0+cu124, Diffusers0.37.0, Transformers4.56.1. Attention PyTorch mathématique FP32, tranches de256requêtes gardant toutes les clés/valeurs. L'adaptateur remplace uniquement la fonction dispatch du module Z-Image dans le processus isolé ; aucun fichier de bibliothèque modifié.

Neuf comparaisons d'attention sur CPU et les deux V100, avec masque absent, padding et masque complet : écart maximal1,3411e-7, test de proximité réussi. Un petit ZImage aléatoire comparé avant/après répartition donne un écart nul. Ces contrôles ne constituent pas une comparaison complète du checkpoint réel entre une et deux cartes. La répartition réelle est vérifiée par les dispositifs de tous les paramètres après chargement strict.

Verrou campagne, exclusion des clients GPU concurrents, garde GPU65°C/HBM70°C, consigne300W, RAM72G, CPU800%, durée maximale3600s. Valeurs finies contrôlées après chaque étape et au décodage. Toute erreur interrompt la campagne ; les sorties partielles et journaux sont conservés.

## Lecture des résultats

Le temps par image couvre l'appel du pipeline, l'enregistrement du latent, le décodage et la conversion en image ; PNG final écrit après chronométrage. Encodage, chargement et vérification des poids sont séparés. Le cache d'embeddings est réutilisé pour les seeds. Comparer cette recette FP32 sur deux cartes à Klein FP16 sur une carte n'isole pas l'effet du modèle ni sa vitesse potentielle sur matériel BF16.

Rendu visuel et conformité restent distincts. Revue GPT non aveugle sur aperçus sans retouche ; PNG natifs, latents et hashes conservés. Petit échantillon : aucun classement universel, aucune validation anatomique professionnelle. Avis de toytoy en attente ; aucun entraînement ni profil promu.

Sources : [modèle auteur](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo), [code auteur](https://github.com/Tongyi-MAI/Z-Image), [Diffusers0.37.0](https://github.com/huggingface/diffusers/tree/v0.37.0/src/diffusers/pipelines/z_image). Preuves : `evidence-g342/`, `zimage-validation-g342.json`. Résultats natifs sous `/srv/eidolon/workspaces/media-20261112/zimage-g342/`.

## Résultats réels

12 images terminées sans erreur de calcul, sans non-fini et sans erreur de sonde. Répétition1/9 identique pixel à pixel. **4/8 natives proposées, 2 à revoir, 2 rejetées** après revue GPT. Mains1/2 et objets3/4 proposés. Katanas5/6 : pièce noire portant une garde et une extension évoquant une poignée, fourreau ambigu. Duos7/8 : cadrage en pied correct et rendu photographique convaincant, mais plusieurs visiteurs ajoutés à l'arrière-plan malgré « exactly two adults ». Le contrôle512² est proposé ; les deux formats écran sont rejetés (visiteurs supplémentaires, cadrage coupé en16:9).

| Mesure | Résultat G342 |
| --- | --- |
| Médiane native, n=8 | 45.480961 s |
| Minimum / maximum natifs | 45.293024 / 45.606559 s |
| Encodage CPU des4textes | 64.430332 s |
| Chargement / placement | 9.048138 s |
| Appels générateur par image | 9 constatés, pour9étapes demandées |
| Paramètres GPU0 / GPU1 | 11 594 090 752 / 13 025 544 192 octets |
| Pic NVML mémoire GPU0 / GPU1 | 14 068 / 14 490 Mio |
| Max GPU0 / GPU1 | 47 / 45 °C |
| Max HBM0 / HBM1 | 48 / 48 °C |
| Pics NVML puissance GPU0 / GPU1 | 322,05 / 325,01 W ; consigne300W |
| CPU Tdie maximal | 55,625 °C |

Comparaison de recettes : Klein G340 3,39566s et6/8 proposés ; dev G338 70,57697s et4/8 proposés. Z-Image enrichit le comparatif par ses matières et portraits convaincants, sans résoudre toutes les consignes. Les compteurs identiques à dev ne portent pas sur les mêmes images. FP16 et attention efficace de Z-Image non testés ; aucune conclusion sur leur stabilité/vitesse. La fiche auteur annonce8NFEs pour son exemple9étapes, mais notre pile0.37.0 mesure9appels : la mesure réelle est conservée.

Runtime historique inchangé, PNG natifs revérifiés par SHA256, GPU sans client au contrôle final ; cinq services actifs et VM Memory-engine en marche. Machine laissée allumée. Rapport illustré `Eidolon-comparatif-ZImage-G342.pdf`.

G341 a été retrouvé dans un commit local absent de la référence distante. Son contenu est conservé avec ce lot ; commit original301f4eab70e9ab09e72b893eaa23f017a3b9dfb3 gardé dans la branche locale `codex/archive-g341-before-g342`. La publication inclut les fichiers G341 et les résultats de qualification RAM sans les modifier.
