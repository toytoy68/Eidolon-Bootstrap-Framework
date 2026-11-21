# G335 — Sana 1,6B FP16 sur V100

Eidolon Core Technologies (ECT), 13 novembre 2026, Europe/Paris.
Base `cb33db0cf84bd2f847cff44b604bf3f591a74c79`, branche média dédiée.

## Protocole figé avant inspection

Variante auteur `Efficient-Large-Model/Sana_1600M_1024px_diffusers`, révision
`ac0da2ff55fbe434795be0dce883042e4d49e2fc`, variante FP16 explicite, non BF16.
[Manifeste SHA256](sana-downloads-g335.json). Runner `sana_probe.py` G334
inchangé, SHA256 `b9634d9e6a1d7a6738aa47e2777f89d1da9c464e4cf914d1e5574b13a7d4c96e`.
Les corrections negative_prompt/tokenizer/décodage intégral de G334 sont réutilisées.
Aucun nouveau composant, patch de dépendance ou pilote.

Même grille : contrôle main 512², huit natifs 1024² (main, deux objets,
katana/fourreau, duo château × seeds 20261113/20261114), répétition exacte de
la première main native, duo 1024×576 puis 768×576 avec dérivé à bandes 128px.
12 générations prévues, 13 fichiers ; aucun changement de prompt après observation.
20 étapes, CFG 4,5, scheduler auteur, négatif vide, résolution exacte sans binning.
Générateur GPU0 FP16, encodeur Gemma2 CPU FP32 eager, DC-AE GPU0 FP32 intégral.
Temps d'encodage et chargement séparés ; pas de gain de débit GPU1 revendiqué.

Données privées sous `/srv/eidolon/data/media-models-20261113/sana-1600m`.
Les composants identiques à G334 sont vérifiés contre les empreintes de la
nouvelle révision, puis réutilisés par liens physiques sur le même volume.
Ces fichiers communs ne doivent jamais être modifiés en place. Le modèle est
monté en lecture seule dans le sandbox ; le générateur de 3 208 971 144 octets
est distinct, SHA `30cadbc6ebe74168f109fa14f1bf88badbc18cfad2a673f100322fb49a443c9c`.
Stockage supplémentaire limité aux nouveaux fichiers ; pas de suppression.

## Sources, licences et périmètre

[Carte auteur et licence](https://huggingface.co/Efficient-Large-Model/Sana_1600M_1024px_diffusers/tree/ac0da2ff55fbe434795be0dce883042e4d49e2fc),
[documentation Diffusers Sana](https://huggingface.co/docs/diffusers/api/pipelines/sana).
Carte et configuration relues ; licence Apache-2.0 strictement identique à G334
par SHA256. Encodeur/DC-AE identiques et conditions par composant de
[SANA-G334](SANA-G334.md#sources-et-licences) conservées. Gemma2 garde ses
restrictions d'usage : le pipeline n'est pas déclaré sans restriction.
L'évaluation porte sur des scènes synthétiques non explicites.

Seules connexions d'installation : API et distribution de fichiers Hugging Face
pour inventaire, carte/configuration et poids auteur. Aucun code amont téléchargé
ou exécuté ; runner existant et safetensors uniquement. Réseau d'inférence
limité à localhost, variables offline, hôte non déconnecté globalement.
Garde PID/VRAM et températures identique : arrêt GPU≥65 °C/HBM≥70 °C ou valeur
non finie. 300 W par V100, aucun arrêt Eva/Core/Memory. GPU1 au repos.

Comparaison à G334 : mêmes conditions d'exécution, prompts, seeds et composants
textuels/VAE ; générateur différent. Leurs entraînements amont peuvent différer : cet essai compare
deux checkpoints, pas un effet causal de la seule quantité de paramètres.
Deux seeds par scène ne permettent pas un classement universel. Revue GPT non aveugle, propositions soumises à toytoy,
aucune mise en entraînement. Les échecs éventuels restent conservés.

## Résultats

**12 générations réussies dès run01**, plus un dérivé à bandes noires.
Répétition G335-09 pixel-identique à G335-01. Aucun OOM, arrêt thermique ou
valeur non finie observé ; 233 sondes sans erreur. Essai un GPU, pas multi-GPU.

| Mesure | Résultat |
| --- | --- |
| Chargement CPU / transfert GPU | 2,769 s / 1,721 s |
| Encodage CPU par nouveau prompt | 22,201–22,335 s |
| GPU + décodage 1024² | 3,357–3,379 s, encodage exclu |
| Nouveau prompt + image native | environ 25,6 s, hors chargement/écritures |
| VRAM GPU0 max | 9 832 Mio (9,60 Gio) |
| GPU0 / HBM max | 41 / 46 °C |
| CPU Tdie max | 50,875 °C |
| Puissance GPU0 max échantillonnée | 309,62 W ; consigne 300 W |
| GPU1 | utilisation 0%, 1 Mio |
| Point Shelly configuré | 65 relevés ; moyenne arithmétique 300,49 W ; 209,5–472,4 W |
| Compteur Shelly | +10,931 Wh sur 129.74 s |

Branchement physique du Shelly non revérifié, pas énergie GPU isolée. Fenêtre
restreinte au run01, téléchargement exclu. Pics observés par échantillonnage,
pas maxima électriques absolus. Le CPU reste le coût dominant d'un prompt nouveau.

## Décisions visuelles proposées

Sur les huit natifs : **1 proposition, 2 doutes, 5 rejets**.

| ID | Proposition GPT | Motif principal |
| --- | --- | --- |
| G335-01 | À revoir | Cinq doigts, mais bourrelets/plis artificiels de paume |
| G335-02 | À revoir | Volumes de paume et séparation des doigts peu convaincants |
| G335-03 | Rejet | Bol bleu dédoublé/empilé, échec du comptage strict |
| G335-04 | Validation proposée | Une tasse rouge à gauche et un bol bleu à droite, cohérents |
| G335-05 | Rejet | Poignée coudée, lame détachée, assemblage incohérent |
| G335-06 | Rejet | Poignée isolée, lame/fourreau fusionnés |
| G335-07 | Rejet | Pieds du samouraï coupés ; détails de mains suspects |
| G335-08 | Rejet | Personnages coupés en bas |

Hors dénominateur natif : G335-00 rejeté (quatre doigts visibles), G335-09
répétition avec les mêmes réserves que 01. G335-10 16:9 rejeté pour cadrage,
G335-11 4:3 rejeté pour absence du samouraï. Les tailles et les bandes noires
sont techniquement exactes ; elles ne corrigent pas le contenu.

[Preuves et toutes les décisions](sana-validation-g335.json). Revue GPT non
aveugle, contrôle toytoy en attente, aucune référence anatomique certifiée.
Les doutes ne deviennent pas des validations. Aucun entraînement/LoRA/promotion.

## Comparaison à G334 et état final

Runner, plan, composants texte/VAE et scheduler identiques vérifiés. Médiane
GPU + décodage : 3,370 s contre 2,397 s, facteur 1,406 (environ +41%).
VRAM max +1 954 Mio. Le 600M avait 2 propositions, 2 doutes, 4 rejets natifs ;
le 1,6B n'établit pas de progrès global sur ce petit lot. Certaines silhouettes
de mains sont plus plausibles, mais pas assez fiables pour promotion.
Ne pas généraliser ni attribuer ces écarts à la seule taille du modèle.

Trois tests ciblés réexécutés sur X399, **3 réussis en 3,793 s** : bornes du
plan, conservation des pixels lors du padding, contrat réel Sana avec embeddings.
La suite 249 tests (244 réussis/5 ignorés) est celle de G334 ; **non réexécutée
G335**, aucun code modifié. Manifeste et plan contrôlés, 13 aperçus vérifiés,
PDF 16 pages rendu et inspecté. Aucune simulation présentée comme essai matériel.

Core, communication, Ollama, Darme, tunnel Memory actifs avant/après ; VM Memory
en marche, aucun PID de calcul GPU restant. Contrôle d'état limité, pas recette
exhaustive de non-régression. Anciennes unités transitoires API/Comfy toujours
inactives après boot ; aucune intégration Sana API/HUD/voix. Machine allumée,
V100 à 300 W ; bascule automatique 200 W Eva/discussion reste à développer.
Poids totaux référencés : 9 686 731 748 octets ; fichiers : 9 725 427 865 octets.
Nouveaux fichiers seulement : 3 208 978 504 octets, autres réutilisés par liens
physiques après vérification. Données libres : 216.70 Gio.

Preuves brutes privées : `/srv/eidolon/workspaces/media-20261112/sana-g335/`.
Runner et environnement inchangés, pas de code de génération nouvellement créé.
Sana Sprint/encodeur GPU1 et autres candidats restent dans la file. La suite
prioritaire est une autre architecture ou la vidéo, sans supposer un gain lié
au seul nombre de paramètres. Aucun profil remplacé et aucune fusion.

