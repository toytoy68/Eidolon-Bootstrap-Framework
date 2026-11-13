# FLUX.2 Klein 4B - G340

13 novembre 2026. Poursuite comparative demandée par toytoy, avec séparation du rendu visuel et du respect des consignes. Lot de recherche isolé ; aucune intégration automatique au service ni entraînement.

## Protocole

La grille reprend exactement les quatre prompts, les seeds et les dimensions G338/G339 : main ouverte, tasse rouge à gauche/bol bleu à droite, katana/fourreau, duo devant château. Contrôle 512², huit images 1024² (deux seeds), répétition, 1024×576 et 768×576. Les contrôles et formats écran sont exclus du score natif. Dev G338 et Schnell G339 sont des références historiques, pas de nouvelles générations dans ce lot.

Klein utilise sa recette distillée à quatre étapes, guidance1, encodeur Qwen3 FP32 CPU avec 512 tokens et couches9/18/27. Le générateur et le VAE sont propres à FLUX.2 : ne pas réutiliser ceux de FLUX.1. La configuration de scheduler vient du dépôt auteur, avec le calcul de décalage du pipeline Diffusers0.37.0.

Les recettes ne diffèrent pas seulement par le modèle : encodeur, séquence, scheduler et implémentation d'attention changent. Les temps mesurent les configurations testées, sans isoler le seul effet du nombre de paramètres. Même seed ne signifie pas même composition entre architectures.

## Poids et environnement

Tous les fichiers viennent de `black-forest-labs/FLUX.2-klein-4B`, révision `e7b7dc27f91deacad38e78976d1f2b499d76a294`. Quatre fichiers de poids (générateur, deux parties Qwen3, VAE), 15 964 212 614 octets au total ; SHA256 LFS contrôlés. Seize fichiers de configuration/tokenizer/licence/carte sont vérifiés par empreinte Git blob ou LFS, puis archivés dans le manifeste. Licence auteur Apache-2.0, licence Qwen3 également archivée.

Le runtime précédent est copié dans un environnement indépendant : PyTorch2.6.0+cu124 conservé, Diffusers0.37.0, Transformers4.56.1, Hub0.36.2, Tokenizers0.22.2. PEFT0.14 copié était incompatible avec le nouveau Diffusers ; ce module optionnel, inutile sans LoRA, a été retiré seulement de la copie. `pip check` et imports réussis ; comparaison de `pip freeze` de l'environnement original inchangée. Aucun pilote, CUDA système, service ni runtime dev/Schnell modifié.

L'attention efficace native PyTorch est vérifiée sur V100 (FP16, forme1×24×512×128) face au calcul mathématique : écart maximal0,00048828125, valeurs finies, tolérance absolue/relative0,003. Ce test ponctuel ne prouve pas une équivalence exacte sur le réseau complet. Le backend est imposé explicitement pour le générateur ; le VAE FP32 utilise le backend mathématique et des tuiles512 avec recouvrement par défaut.

## Mesures, garde et conservation

Poids et configurations revérifiés avant inférence, chargement des modules sans clés manquantes/inattendues, contrôle des latents et pixels finis. Verrou GPU, absence de clients concurrents, garde GPU65°C/HBM70°C, plafond RAM72G et CPU800%, durée maximale30minutes, réseau sortant bloqué. Consigne300W par V100. Les pics sont échantillonnés ; aucune énergie à la prise n'est déduite.

Les temps séparent l'encodage CPU, le chargement/placement et le calcul GPU avec décodage. L'encodage est mis en cache pour les seeds répétées ; téléchargement, vérification des fichiers et démarrage ne sont pas inclus dans le temps par image. Les températures de lots de durées différentes ne classent pas leur rendement énergétique.

Les preuves détaillées figurent dans `klein-validation-g340.json` et `evidence-g340/`. Poids sous `/srv/eidolon/data/media-models-20261113/klein-4b`, résultats et latents sous `/srv/eidolon/workspaces/media-20261112/klein-g340/`. Les aperçus de revue sont des JPEG réduits à768pixels maximum, sans retouche ; les PNG natifs sont conservés. Revue GPT qualitative non aveugle, petit échantillon, avis de toytoy en attente.

Sources primaires : [modèle](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B), [code auteur](https://github.com/black-forest-labs/flux2), [Diffusers0.37.0](https://github.com/huggingface/diffusers/tree/v0.37.0/src/diffusers/pipelines/flux2). Les versions et empreintes exactes restent dans les preuves.

## Résultats réels et conclusion

Les 12 images du run01 sont terminées sans non-fini ni erreur d'inférence. Les indices1 et9 ont des pixels identiques. Huit natives1024² : **6 proposées, 0 réserve, 2 rejets** après revue GPT. Deux mains, deux scènes d'objets et deux duos en pied proposés ; deux katanas rejetés pour assemblage impossible ou lame détachée de sa poignée. Le contrôle512² est proposé ; les formats1024×576 et768×576 sont rejetés pour pieds rognés. Aucun ajustement de prompt entre modèles.

| Mesure | Dev G338 | Schnell G339 | Klein G340 |
| --- | --- | --- | --- |
| Étapes natives | 50 | 4 | 4 |
| Médiane GPU + décodage1024² | 70,57697 s | 6,45102 s | 3,39566 s |
| Encodage CPU des4textes | 35,86490 s | 35,43868 s | 57,17462 s |
| Chargement/placement | 13,17699 s | 13,15788 s | 4,62022 s |
| Propositions GPT natives | 4/8 | 4/8 | 6/8 |
| Pic mémoire GPU0/GPU1 | 13 366/13 082 Mio | 13 346/13 082 Mio | 9 728/310 Mio |

Klein : paramètres du générateur7751089152octets sur cuda:0 ; GPU1 sans calcul. Allocation PyTorch maximale8921172992octets GPU0, différente de la mémoire totale NVML. Maxima GPU/HBM41/43°C, CPU Tdie56,875°C ; pic NVML319,62W malgré une consigne300W. Les pics ne sont pas une énergie ni une puissance moyenne. GPU1 reste à0%utilisation.

Le rendu des textures et des portraits est convaincant, avec parfois une lumière trop forte et des visages lissés. Klein satisfait mieux le cadrage carré sur ce lot ; dev reste plus crédible sur les katanas. Six propositions sur huit ne prouvent pas une supériorité générale. Le backend d'attention plus efficace et les différences d'architecture interdisent d'attribuer toute la vitesse au modèle seul. La prochaine étude utile peut comparer les variantes Klein base, ou l'attention efficace sur FLUX.1 dans un lot distinct ; aucune de ces pistes n'est ici exécutée.

État final vérifié : GPU sans client, cinq services actifs, VM Memory-engine en cours ; runtime historique inchangé, machine allumée. PNG natifs revérifiés par SHA256. Aucun entraînement ni promotion. Rapport illustré `Eidolon-comparatif-Klein-G340.pdf`, Library `libfile_60c16c9d7d5c819189777f02ff516bdf`.
