# Z-Image non Turbo — G344, 14 novembre 2026

## Statut provisoire

Contrôle512² et première native1024² terminés et proposés après revue GPT : cinq doigts, main et poignet visibles. Première native277,686s,28appels/56séquences. La grille qualité est en cours dans `zimage-base-g344/run02` ; aucun résultat final ni score natif annoncé.

## Protocole fixé avant génération

Même grille G342 : main, deux objets colorés, katana/fourreau, duo en pied ; deux seeds par scène, répétition, formats1024×576 et768×576. Huit natives1024² dans le score principal. Vues et prompts inchangés. Recette Z-Image28étapes, guidance4, normalisationCFGdésactivée, négatif vide ; bas de la plage auteur28–50. Cette campagne ne mesure pas la recette50étapes ni un prompt négatif enrichi.

Révision auteur `Tongyi-MAI/Z-Image` : `04cc4abb7c5069926f75c9bfde9ef43d49423021`, publique, déclaration Apache-2.0. Six fichiers de poids et treize fichiers de configuration/carte/tokenizer vérifiés ; encodeur et VAE réutilisés seulement si SHA identique. Transformeur nouveau. Aucune exécution de code téléchargé, aucune génération externe.

PyTorch2.6.0+cu124, Diffusers0.37.0 et environnement G340 conservés. Générateur FP32 réparti sur les deux V10016 ; Qwen3 CPU FP32 ; VAE FP32 GPU0 avec tuiles512. Attention mathématique découpée G342,256requêtes avec toutes les clés. Pas de quantification ni offload du générateur.

## Guidage et contrôle matériel

Branches positive/négative exécutées séquentiellement pour limiter les activations. Comparaison au calcul groupé sur deux entrées aléatoires512² àt=0,5 : écarts absolus maximaux1,26e-5 et3,25e-5 ; tolérance absolue/relative0,003 respectée. Ce contrôle ne prouve pas une identité sur toute la trajectoire. Le pipeline conserve sa formule native `positif + guidance × (positif - négatif)`.

Encodage des quatre prompts et du négatif vide :69,896s CPU. Contrôle512² :59,816s GPU/décodage,28appels du pipeline et56séquences du générateur. Ce contrôle est exclu du score natif et de sa médiane.

UUID V100 imposés, aucune autre carte utilisée, consigne300W. Verrou de campagne, garde65°C GPU/70°C HBM,72Go RAM maximum,800%CPU ; aucun changement de pilote, runtime historique ni service. Inférence isolée avec réseau sortant bloqué. GPU libres et services actifs avant lancement. Lancement qualité limité à90minutes.

Sources : [carte auteur](https://huggingface.co/Tongyi-MAI/Z-Image/tree/04cc4abb7c5069926f75c9bfde9ef43d49423021), [code auteur](https://github.com/Tongyi-MAI/Z-Image). PNG, latents et journaux sous `/srv/eidolon/workspaces/media-20261112/zimage-base-g344/`. Aucune promotion ni entraînement.


## Point de suivi après la première native

La grille continue dans le service `eidolon-media-zimage-base-g344-quality.service`, sans intervention requise pour les dix sorties restantes. Ce fichier et `evidence-g344/*partial*` sont une photographie provisoire, pas un bilan final. Résultats, PNG et mesures sont enregistrés par le processus local ; `completion.json` ou `failure.json` donnera son issue. Revue complète encore à effectuer. Rapport illustré provisoire `Eidolon-suivi-ZImage-G344.pdf`, Library `libfile_fde3_f-a7e55dafbd00819188d3e98b84c1204c_d168d29c22b4819186c4d3b8d1b7451f`, version0.
