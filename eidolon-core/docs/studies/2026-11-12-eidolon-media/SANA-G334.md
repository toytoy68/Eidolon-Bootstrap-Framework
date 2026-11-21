# G334 — Sana 600M sur V100 : protocole et validation

Eidolon Core Technologies (ECT), 13 novembre 2026, Europe/Paris.
Candidat I26, reprise demandée par toytoy ; branche média dédiée, base 9a82aca.

## Protocole figé avant inspection

Sana 600M 1024px Diffusers, révision auteur `28f3af7689de15f3883d5863059a2fca0aa9b829`.
[Manifeste des fichiers et SHA256](sana-downloads-g334.json).
Stockage privé sur `/srv/eidolon/data/media-models-20261113/sana-600m` ; le volume
modèles à 97% reste intact. Aucun téléchargement pendant l'inférence.
Poids : 7 661 318 868 octets ; fichiers requis au total : 7 700 014 738 octets.

Diffusers 0.32.2 / torch 2.6.0+cu124 existants, aucune installation. Générateur
FP16 GPU0 V100, encodeur Gemma2 CPU FP32 eager, DC-AE GPU0 FP32, décodage intégral (tiling désactivé après incident run03).
Pas de BF16, FP8, xFormers ou FlashAttention. Deuxième V100 au repos.
Encodeur libéré après calcul des quatre conditions textuelles ; temps CPU
séparé des temps GPU/décodage, embeddings réutilisés entre seeds et formats.
Instruction de conditionnement Sana standard conservée, pas de réécriture par
un LLM distant. Nettoyage optionnel du texte désactivé. Scheduler auteur
DPM++ flow, 20 étapes, CFG 4,5, négatif vide, resolution_binning=False.

12 générations prévues : main 512² de contrôle, main/objets/katana/duo château
à 1024² × seeds 20261113 et 20261114, répétition exacte de la main 1024²,
duo 1024×576 et duo 768×576. Ce dernier est centré sans rééchantillonnage sur
1024×576 avec deux bandes noires de 128px : dérivé, pas treizième génération.
Tous les prompts sont conservés dans le runner/manifest ; aucun choix de seed
après observation. Les formats écran sous un mégapixel restent exploratoires.
Les recettes Sana et SDXL diffèrent : pas de comparaison causale de vitesse.

Runner utilisateur non privilégié, ressources bornées, réseau bloqué sauf
localhost. Arrêt sur PID GPU étranger, GPU≥65°C/HBM≥70°C, encodage/latent ou
décodage non fini. Contrôle de taille et répétition de pixels. Plafond 300W,
pas de modification des services Eva/Core/Memory, pas de promotion/entraînement.

## Sources et licences

- [Sana auteur](https://huggingface.co/Efficient-Large-Model/Sana_600M_1024px_diffusers) :
  Apache-2.0, texte intégral archivé et hash dans manifeste. La carte décrit
  une intention de recherche et reconnaît les limites mains/scènes complexes.
- DC-AE fourni dans le dépôt Sana ; source [MIT Han Lab / EfficientViT](https://github.com/mit-han-lab/efficientvit),
  Apache-2.0, texte archivé SHA `3c3976a8a7a11c899b2dcdf71cb61198cb302e9542cd99cdad5f1d5d0afe3803`.
- Encodeur Gemma2 : [conditions](https://ai.google.dev/gemma/terms),
  [usages interdits](https://ai.google.dev/gemma/prohibited_use_policy), lus et
  archivés le 13/11. Les restrictions de Gemma2 s'appliquent aussi à sa copie
  incluse dans Sana. Elles ne sont pas remplacées par Apache ; notamment ce
  composant ne répond pas à une exigence d'usage explicite sans restriction.
  Ce lot porte uniquement sur des scènes synthétiques non explicites d'évaluation.
- Textes Google archivés : SHA `3d71442181ec42c5f63848f7e6d3ec15529f9270ba813385635edfa13c716ede`
  (conditions), `c84e0d91ba856ac88f1de5886a8a7e5bb0d4183c82029f4609562f21db4326d9` (usages).

Connexions initiales : Hugging Face/distribution des fichiers, GitHub pour la
licence DC-AE, ai.google.dev pour les conditions. Aucune inférence distante.
Fichiers Python amont non téléchargés/exécutés ; seules les bibliothèques déjà
installées sont utilisées. Aucun accès à un dépôt gated contourné.

## Résultats

Run04 terminé le 13/11/2026 : **12 générations réelles**, 13 PNG avec le dérivé
à bandes. 8 images natives : **2 propositions de validation, 2 doutes, 4 rejets**.
Revue GPT non aveugle, contrôle toytoy en attente ; aucune donnée promue pour
entraînement. Les objets G334-03/04 sont proposés ; mains et katanas non retenus,
duo G334-07 douteux, G334-08 cadrage rejeté. Le smoke G334-00 possède six doigts.
G334-09 répète exactement les pixels de G334-01, défaut anatomique compris.
16:9 et 4:3 + bandes exacts, mais G334-10 coupe les jambes et G334-11 omet le
samouraï : réussite de format distincte de la conformité du contenu.

| Mesure réelle | Résultat |
| --- | --- |
| Chargement CPU / transfert GPU | 2,758 s / 0,997 s |
| Encodage CPU par prompt nouveau | 22,325–22,391 s |
| GPU + décodage natif 1024² | 2,392–2,403 s ; encodage exclu |
| Nouveau prompt + image native | environ 24,8 s, hors chargement et écritures |
| GPU0 VRAM max | 7 878 Mio (7,69 Gio) |
| GPU0 / HBM max | 40 / 45 °C |
| CPU Tdie max | 54 °C |
| Puissance GPU0 | maximum échantillonné 325,59 W ; limite configurée 300 W |
| GPU1 | au repos, 1 Mio, utilisation 0% |
| Télémétrie | 217 échantillons, zéro erreur |
| Point Shelly configuré | 61 relevés ; moyenne arithmétique 282,91 W, plage 193,5–458,1 W |
| Compteur Shelly | +9,430 Wh sur 121,67 s du run04 |

Le périmètre physique du Shelly n'a pas été revérifié ; ce n'est pas l'énergie
GPU seule. La fenêtre n'inclut pas téléchargement ni tentatives 01–03. Les pics
échantillonnés ne sont pas des maxima électriques absolus. Aucun gain de vitesse
à qualité égale n'est déduit face à SDXL : encodeur, scheduler et recette diffèrent.

Suite média : **249 tests, 244 réussis et 5 ignorés**, ici (11,782 s) et X399
(14,771 s). Le test ciblé contre les méthodes réelles Sana réussit sur X399 et
est ignoré ici faute de runtime Sana. Les autres skips dépendent de l'environnement.
Core, communication, Ollama, Darme et tunnel Memory actifs ; VM Memory en marche,
GPU libérés. Présence des services seulement, pas recette exhaustive de non-régression.
Anciennes unités transitoires Media API/Comfy inactives depuis boot ; Sana n'est
pas intégré à l'API/HUD. Aucun entraînement, LoRA, fusion ou extinction.
V100 laissées à 300 W ; bascule 200 W Eva/discussion non implémentée.

[Preuves structurées et toutes les décisions](sana-validation-g334.json).
Originaux, runners des quatre tentatives, erreurs et mesures brutes conservés
sous `/srv/eidolon/workspaces/media-20261112/sana-g334/` ; run04 est la réussite.
Runner final SHA256 `b9634d9e6a1d7a6738aa47e2777f89d1da9c464e4cf914d1e5574b13a7d4c96e`.
Fichiers privés, poids sur le volume données ; environ 219,69 Gio disponibles
après le lot. Aucun fichier multimédia ajouté à la mémoire sémantique.



### Incident de préparation conservé

`run01` s'arrête avant la première génération : Sana refuse le négatif texte
vide par défaut en présence d'embeddings négatifs. Correction du seul appel :
`negative_prompt=None` puisque son encodage a déjà été fourni. Reproducteur
hors GPU exécuté contre `SanaPipeline.check_inputs` : ancien appel refusé,
appel corrigé accepté. Runner original et failure.json conservés dans run01.
Nouvelle tentative distincte run02, sans changement de modèle, poids ou paramètres.


`run02` s'arrête aussi avant toute image : `encode_prompt` accède toujours au
`tokenizer.padding_side`, même avec les embeddings fournis. Le tokenizer léger
reste désormais attaché au pipeline ; seul le modèle texte lourd est libéré.
Test de régression contre les vraies méthodes `check_inputs` et `encode_prompt`
avec embeddings synthétiques et sans GPU : réussi, en plus des deux tests de
plan et de conservation des pixels. `run03` reprend les mêmes paramètres ;
les deux runners précédents, manifestes et échecs sont conservés.


`run03` atteint le décodage mais échoue avant le PNG : le DC-AE de Diffusers
0.32.2 expose `enable_tiling` alors que `tiled_decode` lève NotImplementedError
et que les attributs tile_latent_min_* manquent. Code installé lu : fonction
incomplète, pas panne matérielle ou échec FP16. `run04` utilise le décodage
intégral FP32, sans patch de bibliothèque ; montée 512 puis 1024, plafond
allocateur 88% de la VRAM conservé. Cette modification de recette est explicite.
