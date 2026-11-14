# G333 — comparaison SDXL base, RealVisXL V5 et Juggernaut XL v9

Eidolon Core Technologies (ECT), 13/11/2026, Europe/Paris.
Reprise autorisée de la [file des modèles](CANDIDATE-QUEUE-G332.md).

## Protocole déclaré avant inspection

Trois scènes synthétiques non privées : main ouverte face paume, tasse rouge à
gauche et bol bleu à droite, katana et fourreau séparés. Deux seeds fixées à
20261113 et20261114, puis répétition exacte de la première main. Aucun tri des
seeds après observation et aucun LoRA. 1024×1024, DPM++2M Karras,30étapes,
CFG5, prompt négatif vide sur les trois modèles ; même Diffusers0.32.2,
torch2.6.0+cu124, GPU0 V10016Go. Les paramètres complets sont dans le manifeste.

Pour RealVisXL, six essais supplémentaires reprennent les mêmes scènes/seeds
en changeant **seulement les étapes à50**, recommandation de l'auteur pour
DPM++2M Karras. Aucun upscale ni correction manuelle. Les scores de cette
condition restent séparés de la comparaison commune30étapes.

Total prévu :7SDXL base +13RealVisXL +7Juggernaut =27sorties ;24essais de
qualité et3répétitions. Une répétition n'est pas une scène indépendante.
Ce petit échantillon ne permet pas de classer universellement les modèles.
G331/G332 ont d'autres recettes/résolutions : pas de comparaison directe de
leurs temps ou scores avec ce lot. Le témoin SDXL est régénéré ici pour cette raison.

## Sources, licences et téléchargements

[Manifeste de téléchargement figé](candidate-downloads-g333.json). Deux nouveaux
checkpoints safetensors issus des comptes auteurs, vérifiés SHA256 au téléchargement
puis au chargement. Total14 043 413 676octets, sans téléchargement automatique
pendant l'inférence. Aucun pickle, installateur, extension ou code téléchargé exécuté.

- RealVisXL V5.0 FP16 : révision `ac93e0dda1f6d448cae19bbfab8c5e720a5e48bc`,
  6 938 065 488octets, SHA `6a35a785…43b80`. [Carte auteur](https://huggingface.co/SG161222/RealVisXL_V5.0)
  sous OpenRAIL++ déclaré ; pas de fichier LICENSE séparé dans ce dépôt.
  Texte OpenRAIL++-M du modèle SDXL de base archivé localement, restrictions
  d'usage applicables ; aucune qualification d'open source sans restrictions.
- Juggernaut XL v9 : révision `cf419233522daa0b9ea36c3aff98fa2cab1fb0fb`,
  7 105 348 188octets, SHA `c9e3e68f…a8bca`.
  [Carte auteur](https://huggingface.co/RunDiffusion/Juggernaut-XL-v9) : CreativeML
  OpenRAIL-M déclaré, usage personnel/créatif autorisé sous ses conditions ;
  déploiement derrière une API payante soumis à licence explicite. Ce test privé
  local n'est pas un service API payant. Le modèle de base SDXL et ses restrictions
  ne sont pas ignorés. Pas de fichier LICENSE propre ; carte et textes de
  référence conservés, aucune affirmation de droits commerciaux illimités.
- [OpenRAIL-M CompVis](https://huggingface.co/spaces/CompVis/stable-diffusion-license/blob/14d42d09bffd871b1666a084fc954a50cff72ac0/license.txt),
  SHA `be351ebe7ac01bcdbb018639aadcfd38f136b7dc3f2a3d4d3a24db51d1b210ef`.
- [OpenRAIL++-M SDXL](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/462165984030d82259a11f4367a4eed129e94a7b/LICENSE.md),
  SHA `19b6998b569b53ac1fc2158a8a3202c8699a9a4605b47075715d9c96be7fb6d0`.

Notices et reçus complets conservés dans le laboratoire `checkpoints-g333`.
Hugging Face et ses hôtes de distribution servent uniquement au téléchargement.
Pas d'inférence distante, prompt privé transmis ou compte extérieur nécessaire.

## Matériel et isolation

Deux V10016Go et NVLink présents au démarrage. GPU libres à la prise en charge.
GPU0 seul utilisé ici pour que les comparaisons partagent le même matériel ;
la répartition de FLUX sur deux cartes a été testée en G332 et n'est pas
remplacée par ce protocole de checkpoints SDXL.

Décision toytoy du13/11 : **300W par V100 pour image/vidéo,200W pour Eva/discussion**.
Les deux cartes sont déjà à300W après boot, aucun réglage changé dans ce lot.
Refroidissement double300W rapporté validé par toytoy ; températures GPU/HBM
mesurées pendant chaque génération. La bascule automatique de puissance par
charge reste à implémenter avec le bail GPU commun.

Runner utilisateur toytoy, sans privilèges, CPU4équivalents/RAM48Gio, durée
1800s maximum, IPAddressDeny=any sauflocalhost et variables HF offline.
GPU UUID explicitement sélectionné ; arrêt propre sur processus GPU concurrent,
température GPU≥65°C/HBM≥70°C ou latent non fini. Pas d'arrêt Eva.
Les services média temporaires de la veille sont inactifs après reboot : ce
runner ne prétend pas les avoir restaurés ni intégré les nouveaux profils à l'API.
Les services Core/Ollama restent en place. Aucun changement de pilote/runtime.

## Résultats

**27/27 générations terminées réellement le 13/11**, unité terminée avec code0.
[Preuves, paramètres, empreintes et revue de toutes les sorties](checkpoint-validation-g333.json).
PNG originaux1024² conservés dans `checkpoints-g333/run01/{sdxl,realvis,juggernaut}`.
Rapport illustré livré à toytoy : `Eidolon-validations-G333.html`,27aperçus768px.

| Condition | n hors répétitions | Médiane génération | Min–max | Proposées / douteuses / rejetées |
| --- | --- | --- | --- | --- |
| SDXL30 |6|17,55s|17,54–17,99s|1 /1 /4|
| RealVis30 |6|17,55s|17,54–17,56s|1 /1 /4|
| Juggernaut30 |6|17,62s|17,61–17,63s|2 /0 /4|
| RealVis50 |6|28,87s|28,86–28,88s|1 /1 /4|

Chargements3,71/3,53/3,59s respectivement SDXL/RealVis/Juggernaut, cache disque
existant. Le temps génération comprend encodage/débruitage/décodage, sans
chargement ni sauvegarde. Les3répétitions sont pixel-identiques à leur source.
Les six essais50étapes reprennent les seeds30étapes : pas six scènes indépendantes.
RealVis50 coûte64,5% de temps supplémentaire sans gain d'acceptations dans ce lot.

| Modèle | VRAM GPU0 pic | GPU/HBM max | Puissance GPU0 pic |
| --- | --- | --- | --- |
| SDXL |11540Mio|43/51°C|319,41W|
| RealVis,30+50 |11548Mio|47/55°C|322,74W|
| Juggernaut |11548Mio|48/56°C|317,24W|

991relevés,0erreur de sonde. GPU1 à1Mio/0% de charge ; CPU Tdie≤38,375°C.
Consigne GPU0/GPU1=300W, pics transitoires rapportés au-dessus de la consigne.
Ordre fixe et circuit commun : ces pics thermiques ne classent pas les modèles.
Journal Shelly existant192.168.1.197 :278relevés,452,20W moyens échantillonnés,
472,7W max,70,727Wh au compteur entre10:39:33 et10:48:54CET (561,63s).
Branchement physique du point électrique non revérifié pendant ce lot : mesure
du point configuré, **pas énergie attribuée au seul GPU**. Export brut conservé,
SHA `c537c37d0fdff2f487d21a12463557c4b817f61ca5589bb6fdfc083b5d71e52f`.

### Revue visuelle et conclusions limitées

Inspection GPT non aveugle, quatre notes0–4 du protocole G328. Une proposition
d'acceptation exige toutes les notes≥3 et aucun défaut éliminatoire ; un doute
reste exclu de l'acceptation. Toutes les décisions attendent la revue de toytoy.

- Hors répétitions : **5propositions,3doutes,16rejets** sur24conditions.
- Propositions :S00,R01,J00,J01,R08. Préfixe complet `G333-` ; R08=50étapes.
- Doutes :S01(jonction pouce/paume),R00/R07(extrémité du pouce biseautée).
- Rejets :S02–S05,R02–R05,J02–J05,R09–R12. Multiplication/inversion des
  objets, assemblages de sabres incohérents, fourreau trop court, objets tronqués.
- S06/R06/J06 répètent S00/R00/J00 ; hors dénominateur indépendant.

Juggernaut fournit ici deux mains plausibles, pas un vainqueur général. Les
checkpoints alternatifs améliorent certaines textures sans résoudre la fidélité
aux consignes complexes. Les mains proposées ne sont pas une validation
anatomique professionnelle ; aucune paire d'entraînement, LoRA ou promotion.
Ne pas adopter de profil avant la confirmation prévue par QUALITY-PROTOCOL.

### Hors ligne, tests et état final

Inférence avec IPAddressDeny=any,localhost autorisé, variables HF offline.
Le réseau de l'hôte reste connecté ; pas de coupure globale prétendue.
246tests :242réussis/4ignorés localement ;241réussis/5ignorés sur X399.
Les3nouveaux tests contrôlent comparabilité, facteur étapes et refus PID étranger.
Core/communication/Ollama/Darme/tunnel actifs, VM Memory-engine en fonctionnement,
GPU libérés sans processus compute. Ce contrôle n'est pas une recette exhaustive
des fonctions de production. Machine laissée allumée, aucune interruption Eva.
API Media et Comfy transitoires toujours inactifs après boot ; nouveaux
checkpoints non intégrés à l'API. Le test est celui du runner isolé Diffusers.

Volume modèles :15 834 771 456octets libres (~14,75Gio),97% utilisé. Volume
données :243 589 382 144octets libres (~226,86Gio). Avant prochain gros modèle,
préparer un stockage dédié sur ce volume, sans purge implicite. Suite : cas de
confirmation et seeds supplémentaires, formats écran, autres architectures de
la file et vidéo ; ces étapes restent non validées par G333.
