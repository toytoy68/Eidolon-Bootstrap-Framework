# Z-Image non Turbo — G344, 14 novembre 2026

## Résultat final

Douze images terminées, répétition identique pixel à pixel, aucune erreur. Huit natives1024² : **6 proposées,2 à revoir,0 rejet** après revue GPT. Deux mains à cinq doigts, deux scènes d’objets et deux duos en pied proposés. Katanas sous réserve : cohérence lame/fourreau et séparation douteuses. Les formats16:9 et4:3 sont rejetés pour cadrage coupé, hors score principal.

Médiane native **279,383s (4min39s)** ; environ6,1fois le temps de Turbo et82fois Klein dans les recettes testées. Le gain sur ce lot concerne surtout les duos face à Turbo. Petit échantillon, pas de supériorité générale démontrée.

## Protocole fixé avant génération

Même grille G342 : main, deux objets colorés, katana/fourreau, duo en pied ; deux seeds par scène, répétition, formats1024×576 et768×576. Huit natives1024² dans le score principal. Vues et prompts inchangés. Recette Z-Image28étapes, guidance4, normalisationCFGdésactivée, négatif vide ; bas de la plage auteur28–50. Cette campagne ne mesure pas la recette50étapes ni un prompt négatif enrichi.

Révision auteur `Tongyi-MAI/Z-Image` : `04cc4abb7c5069926f75c9bfde9ef43d49423021`, publique, déclaration Apache-2.0. Six fichiers de poids et treize fichiers de configuration/carte/tokenizer vérifiés ; encodeur et VAE réutilisés seulement si SHA identique. Transformeur nouveau. Aucune exécution de code téléchargé, aucune génération externe.

PyTorch2.6.0+cu124, Diffusers0.37.0 et environnement G340 conservés. Générateur FP32 réparti sur les deux V10016 ; Qwen3 CPU FP32 ; VAE FP32 GPU0 avec tuiles512. Attention mathématique découpée G342,256requêtes avec toutes les clés. Pas de quantification ni offload du générateur.

## Guidage et contrôle matériel

Branches positive/négative exécutées séquentiellement pour limiter les activations. Comparaison au calcul groupé sur deux entrées aléatoires512² àt=0,5 : écarts absolus maximaux1,26e-5 et3,25e-5 ; tolérance absolue/relative0,003 respectée. Ce contrôle ne prouve pas une identité sur toute la trajectoire. Le pipeline conserve sa formule native `positif + guidance × (positif - négatif)`.

Encodage des quatre prompts et du négatif vide :69,896s CPU. Contrôle512² :59,816s GPU/décodage,28appels du pipeline et56séquences du générateur. Ce contrôle est exclu du score natif et de sa médiane.

UUID V100 imposés, aucune autre carte utilisée, consigne300W. Verrou de campagne, garde65°C GPU/70°C HBM,72Go RAM maximum,800%CPU ; aucun changement de pilote, runtime historique ni service. Inférence isolée avec réseau sortant bloqué. GPU libres et services actifs avant lancement. Lancement qualité limité à90minutes.

Sources : [carte auteur](https://huggingface.co/Tongyi-MAI/Z-Image/tree/04cc4abb7c5069926f75c9bfde9ef43d49423021), [code auteur](https://github.com/Tongyi-MAI/Z-Image). PNG, latents et journaux sous `/srv/eidolon/workspaces/media-20261112/zimage-base-g344/`. Aucune promotion ni entraînement.


## Clôture

Lot qualité terminé à14h46 le14novembre, heure de Paris. Maxima GPU51/49°C et HBM53/53°C ; pics VRAM14 514/14 494Mio. Pics instantanés323/337,57W malgré consigne300W, pas une énergie ni puissance moyenne. Douze PNG revérifiés, runtime inchangé, aucun client GPU, cinq services actifs et VM Memory-engine en marche. Machine laissée allumée.

Choix toytoy enregistré : rendu de01 très apprécié, délai prohibitif pour les itérations ; réserver ce candidat à la génération détaillée à la demande. Aucune promotion automatique au service.

Rapport illustré complet `Eidolon-suivi-ZImage-G344.pdf`, même identité Library, version1. Les fichiers `*partial*` conservent le point intermédiaire ; les fichiers sans ce suffixe et `zimage-base-validation-g344.json` portent le bilan final.
